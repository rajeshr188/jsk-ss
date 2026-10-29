"""HTML contracts for owner exception forms; no database or provider access."""
import uuid
from collections import Counter
from html.parser import HTMLParser
from types import SimpleNamespace

from django.template.loader import render_to_string
from django.test import SimpleTestCase

from schemes.instalment_review_forms import (
    InstalmentReviewForm, OrderRecoveryForm, OutageResolutionForm,
)
from schemes.models import InstalmentPaymentDecision


class FormMarkup(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.ids = []
        self.labels = []
        self.controls = {}
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get("id"):
            self.ids.append(attrs["id"])
        if tag == "label" and attrs.get("for"):
            self.labels.append(attrs["for"])
        if tag in ("input", "textarea", "select") and attrs.get("id"):
            self.controls[attrs["id"]] = attrs


class SyntheticRows:
    def order_by(self, *args):
        return self

    def first(self):
        return SimpleNamespace(sequence=1)

    def count(self):
        return 15

    def filter(self, **kwargs):
        return InstalmentPaymentDecision.objects.none()


class InstalmentFormAccessibilityTests(SimpleTestCase):
    def setUp(self):
        self.account = SimpleNamespace(scheme_number="SYNTHETIC", agreed_months=12,
            fixed_amount_snapshot="1000.00", instalment_periods=SyntheticRows())
        self.period = SimpleNamespace(pk=1, number=1, scheme_account=self.account,
            reviews=SyntheticRows())
        self.claim = SimpleNamespace(pk=1, period_id=1, period=self.period,
            contribution_id=1, contribution=SimpleNamespace(amount="1000.00"),
            state="REVIEW", decisions=SyntheticRows())
        self.hold = SimpleNamespace(pk=1, period_id=1, period=self.period)

    def assert_form_links(self, html, forms):
        markup = FormMarkup(html)
        self.assertFalse([key for key, count in Counter(markup.ids).items() if count > 1])
        for target in markup.labels:
            self.assertIn(target, markup.controls)
        for control in markup.controls.values():
            for target in control.get("aria-describedby", "").split():
                self.assertIn(target, markup.ids)
        for form in forms:
            for field in form.visible_fields():
                control = markup.controls[field.auto_id]
                self.assertIn(field.id_for_label, markup.labels)
                described = control.get("aria-describedby", "").split()
                if field.help_text:
                    self.assertIn(f"{field.auto_id}_helptext", described)
                if field.errors:
                    self.assertEqual(control.get("aria-invalid"), "true")
                    self.assertIn(f"{field.auto_id}_error", described)
        return markup

    def render(self, template, **context):
        return render_to_string(template, {"csrf_token": "synthetic-csrf", **context})

    def test_period_review_help_and_errors(self):
        for data in (None, {}):
            with self.subTest(bound=data is not None):
                form = InstalmentReviewForm(data, period=self.period, auto_id="period_%s")
                self.assert_form_links(self.render("schemes/includes/instalment_review_form.html",
                    form=form), [form])

    def test_order_recovery_help_and_errors(self):
        for data in (None, {}):
            with self.subTest(bound=data is not None):
                form = OrderRecoveryForm(data, claim=self.claim)
                self.assert_form_links(self.render("schemes/instalment_order_recovery.html",
                    claim=self.claim, intent=SimpleNamespace(request_token=uuid.uuid4()), form=form), [form])

    def test_outage_resolution_help_errors_and_checkbox_label(self):
        for data in (None, {}):
            with self.subTest(bound=data is not None):
                form = OutageResolutionForm(data, hold=self.hold)
                markup = self.assert_form_links(self.render("schemes/instalment_outage_resolution.html",
                    hold=self.hold, account=self.account, used=0, form=form), [form])
                self.assertEqual(markup.controls[form["evidence_confirmed"].auto_id]["type"], "checkbox")

    def test_multiple_review_forms_keep_unique_labels_help_and_error_targets(self):
        # Mirror the view: one invalid POST uses default IDs; untouched forms have
        # period/claim-specific IDs. Cover invalid period AND invalid claim forms.
        for invalid_index in (None, 0, 1):
            with self.subTest(invalid_index=invalid_index):
                forms = []
                for index, auto_id in enumerate(("period_%s", "claim_1_%s", "claim_2_%s")):
                    forms.append(InstalmentReviewForm(
                        {} if invalid_index == index else None, period=self.period,
                        reservation=self.claim if index else None,
                        auto_id="id_%s" if invalid_index == index else auto_id))
                html = self.render("schemes/instalment_review_period.html", period=self.period,
                    period_form=forms[0], rows=[{"claim": self.claim, "form": form} for form in forms[1:]])
                self.assert_form_links(html, forms)

    def test_non_field_errors_and_escaped_input_remain_visible(self):
        form = InstalmentReviewForm({"reason": '<script>alert("example")</script>'}, period=self.period)
        form.is_valid()
        form.add_error(None, "Evidence changed. Reload before deciding.")
        html = self.render("schemes/includes/instalment_review_form.html", form=form)
        self.assertIn("Evidence changed. Reload before deciding.", html)
        self.assertNotIn('<script>alert("example")</script>', html)
        self.assertIn("&lt;script&gt;", html)
        self.assert_form_links(html, [form])
