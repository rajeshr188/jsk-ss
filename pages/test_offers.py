from decimal import Decimal

from django.apps import apps
from django.test import TestCase, override_settings
from django.urls import reverse

from pages.offer_selectors import offer_facts
from schemes.models import MetalGrade
from schemes.plan_governance import plan_edit_digest
from schemes.plan_publication import set_configured_plan_publication
from schemes.tests.test_audit_exceptions import make_owner, make_customer
from schemes.tests.test_independent_plan_drafts import draft
from schemes.tests.test_independent_policy_fields import independent_values, required_values


@override_settings(CONFIGURED_PLANS_ENABLED=True, PUBLIC_CUSTOMER_REGISTRATION_ENABLED=True,
                   CUSTOMER_ENROLMENT_REQUESTS_ENABLED=True, PUBLIC_FUNNEL_MEASUREMENT_ENABLED=False)
class PublicOfferTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner, cls.customer = make_owner(), make_customer()
        cls.grade = MetalGrade.objects.get(code="GOLD_22K_916")

    def offer(self, *, inr=False, values=None, publish=True):
        values = values or independent_values()
        values = {**values, "accumulation": "INR_PURCHASE_CREDIT" if inr else "EXACT_METAL"}
        plan = draft(self.owner, values, [] if inr else [self.grade])
        if publish:
            set_configured_plan_publication(plan_id=plan.pk, publish=True, actor=self.owner,
                reason="Synthetic reviewed offer", expected_digest=plan_edit_digest(plan), confirmed=True)
            plan.refresh_from_db()
        return plan

    def detail(self, plan, params=None):
        return self.client.get(reverse("plan_detail", args=[plan.pk]), params or {})

    def test_public_paths_separate_denomination_and_preserve_terms(self):
        metal, credit = self.offer(), self.offer(inr=True)
        for route in ("home", "pricing", "how_it_works", "terms", "cancellation_refund"):
            with self.subTest(route=route):
                response = self.client.get(reverse(route))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "INR")
        for plan in (metal, credit):
            self.assertContains(self.client.get(reverse("pricing")), reverse("plan_detail", args=[plan.pk]))
        response = self.detail(credit)
        self.assertContains(response, "INR jewellery purchase credit")
        self.assertContains(response, "No grams or metal rate.")
        self.assertNotContains(response, 'name="rate"')
        self.assertNotContains(response, 'name="grade"')
        self.assertContains(response, "original-source refund")

    def test_read_only_examples_cannot_create_financial_records_or_edit_terms(self):
        plan = self.offer()
        before = {m._meta.label: list(m.objects.order_by('pk').values()) for m in apps.get_app_config('schemes').get_models()}
        response = self.detail(plan, {"amount": "3333.33", "grade": self.grade.code, "rate": "14667.0000"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["illustration"]["quantity"], Decimal("0.227267"))
        self.assertContains(response, "0.227 g")
        self.assertContains(response, "hypothetical assumption")
        self.assertContains(response, "Taxes and purchase-time charges are excluded")
        after = {m._meta.label: list(m.objects.order_by('pk').values()) for m in apps.get_app_config('schemes').get_models()}
        self.assertEqual(before, after)

    def test_required_count_period_basis_and_duration_are_not_interchanged(self):
        plan = self.offer(values=required_values(eligibility_policy="CALENDAR_AND_COUNT", duration_months=18, required_count=10))
        response = self.detail(plan)
        self.assertContains(response, "10 qualifying monthly payments")
        self.assertContains(response, "18 months")
        self.assertContains(response, "both duration and final qualifying period ended")
        self.assertContains(response, "enrolment month counts")
        self.assertContains(response, "Three ordinary replacement periods")
        self.assertContains(response, "One final full settlement")

    def test_each_supported_eligibility_family_is_explained_from_policy(self):
        for values, expected in (
            (independent_values(), "Positive verified entitlement; no maturity wait"),
            (independent_values(eligibility_policy="CALENDAR", duration_months=3), "Agreed duration; schedule compliance"),
            (required_values(), "Final required payment verified and conclusively attributed"),
            (required_values(eligibility_policy="CALENDAR", duration_months=12,
                missed_payment_policy="LOSE_UNEARNED_BENEFIT", max_extension_months=None,
                benefit_policy="VA_DISCOUNT", benefit_percentage=Decimal("5.00"), benefit_cap_inr=Decimal("500.00"),
                benefit_qualification="REQUIRED_SCHEDULE", benefit_on_miss="DISQUALIFY_UNEARNED",
                eligible_charge_definition="Recorded eligible making charges"), "Loss of the named unearned benefit, not principal"),
        ):
            with self.subTest(expected=expected):
                self.assertContains(self.detail(self.offer(values=values)), expected)

    def test_non_public_and_disabled_configured_offers_have_no_detail_or_application(self):
        draft_plan = self.offer(publish=False)
        published = self.offer()
        self.assertEqual(self.detail(draft_plan).status_code, 404)
        with self.settings(CONFIGURED_PLANS_ENABLED=False):
            self.assertEqual(self.detail(published).status_code, 404)
            self.assertNotContains(self.client.get(reverse("pricing")), reverse("plan_detail", args=[published.pk]))
        set_configured_plan_publication(plan_id=published.pk, publish=False, actor=self.owner,
            reason="Synthetic withdrawal", expected_digest=plan_edit_digest(published), confirmed=True)
        self.assertEqual(self.detail(published).status_code, 404)

    def test_invalid_assumptions_fail_closed_without_echoing_markup(self):
        plan = self.offer(values=independent_values(amount_step=Decimal("100.00")))
        for changes in ({"amount": "150.00"}, {"rate": "0"}, {"rate": "NaN"},
                        {"grade": "GOLD_24K_9999"}, {"amount": "999999999999999999999"},
                        {"rate": "<script>alert(1)</script>"}):
            with self.subTest(changes=changes):
                response = self.detail(plan, {"amount": "200.00", "rate": "10000", "grade": self.grade.code, **changes})
                self.assertIsNone(response.context["illustration"])
                self.assertContains(response, "Correct the highlighted assumptions")
                self.assertNotContains(response, "<script>alert(1)</script>")

    def test_customer_fixed_amount_and_small_gram_display_preserve_precision(self):
        plan = self.offer(values=independent_values(amount_policy="CUSTOMER_FIXED"))
        response = self.detail(plan, {"amount": "100.01", "rate": "999999.0000", "grade": self.grade.code})
        self.assertEqual(response.context["illustration"]["quantity"], Decimal("0.000100"))
        self.assertContains(response, "less than 0.001 g")
        self.assertEqual(offer_facts(plan)["amount"], "Customer-selected amount, fixed at enrolment")

    def test_tiny_zero_allocation_is_explained_not_shown_as_credit(self):
        plan = self.offer()
        response = self.detail(plan, {"amount": "100.00", "rate": "9999999999.9999", "grade": self.grade.code})
        self.assertIsNone(response.context["illustration"])
        self.assertContains(response, "too small to illustrate an allocation")
        large = self.offer(values=independent_values(maximum_amount=Decimal("999999999999.99")))
        response = self.detail(large, {"amount": "999999999999.99", "rate": "0.0001", "grade": self.grade.code})
        self.assertIsNone(response.context["illustration"])
        self.assertContains(response, "exceed the supported metal quantity")

    def test_purchase_only_bonus_uses_recorded_percentage_and_cap(self):
        plan = self.offer(inr=True, values=independent_values(benefit_policy="INR_PURCHASE_BONUS",
            benefit_percentage=Decimal("5.00"), benefit_cap_inr=Decimal("123.45"), benefit_qualification="NORMAL_ELIGIBILITY"))
        response = self.detail(plan, {"amount": "5000.00", "rate": "1", "grade": self.grade.code})
        result = response.context["illustration"]
        self.assertEqual(result["principal"], Decimal("5000.00"))
        self.assertEqual(result["benefit"].amount, Decimal("123.45"))
        self.assertNotIn("quantity", result)
        self.assertContains(response, "separate from paid principal")
        self.assertContains(response, "one contribution does not establish that")

    def test_va_example_is_discount_on_defined_charges_not_gold_value(self):
        plan = self.offer(values=independent_values(benefit_policy="VA_DISCOUNT", benefit_percentage=Decimal("11.00"),
            benefit_cap_inr=Decimal("1000.00"), benefit_qualification="NORMAL_ELIGIBILITY",
            eligible_charge_definition="Eligible making charges <script>blocked</script>"))
        response = self.detail(plan, {"amount": "10000.00", "rate": "10000.0000", "grade": self.grade.code, "eligible_charges": "1500.00"})
        self.assertEqual(response.context["illustration"]["benefit"].amount, Decimal("165.00"))
        self.assertContains(response, "not a waiver calculated on gold value")
        self.assertNotContains(response, "<script>blocked</script>")

    def test_fixed_offer_does_not_allow_query_to_change_the_example_amount(self):
        plan = self.offer(values=independent_values(amount_policy="PLAN_FIXED", fixed_amount=Decimal("5000.00"),
            minimum_amount=Decimal("5000.00"), maximum_amount=Decimal("5000.00")))
        result = self.detail(plan, {"amount": "1.00", "rate": "10000", "grade": self.grade.code}).context["illustration"]
        self.assertEqual(result["amount"], Decimal("5000.00"))

    def test_single_application_action_obeys_role_and_intake_flags(self):
        plan = self.offer()
        self.assertContains(self.detail(plan), "Apply for this plan", count=1)
        with self.settings(PUBLIC_CUSTOMER_REGISTRATION_ENABLED=False):
            self.assertNotContains(self.detail(plan), "Apply for this plan")
        self.client.force_login(self.customer.user)
        self.assertContains(self.detail(plan), "Apply for this plan", count=1)
        with self.settings(CUSTOMER_ENROLMENT_REQUESTS_ENABLED=False):
            self.assertNotContains(self.detail(plan), "Apply for this plan")
        self.client.force_login(self.owner)
        self.assertNotContains(self.detail(plan), "Apply for this plan")

    def test_illustration_is_get_only_and_does_not_advance_application_analytics(self):
        plan = self.offer()
        self.assertEqual(self.client.post(reverse("plan_detail", args=[plan.pk]), {}).status_code, 405)
        with self.settings(PUBLIC_FUNNEL_MEASUREMENT_ENABLED=True):
            from pages.models import PublicFunnelDailyCount
            self.detail(plan)
            self.assertFalse(PublicFunnelDailyCount.objects.exists())

    def test_legacy_frequency_limit_does_not_become_required_instalments(self):
        from pages import tests as legacy_helpers
        plan = legacy_helpers.PublicPricingPageTests.make_plan(self, code="LEGACY-DETAIL", publicly_listed=True)
        response = self.detail(plan)
        self.assertContains(response, "No mandatory instalments")
        self.assertContains(response, "A frequency limit does not require twelve paid instalments")
        self.assertContains(response, "recorded agreement")
        self.assertNotContains(response, "Configured agreements use one final full jewellery settlement")

    def test_silver_example_uses_its_own_grade_and_clean_canonical_url(self):
        silver = MetalGrade.objects.get(code="SILVER_999")
        plan = draft(self.owner, independent_values(), [silver])
        set_configured_plan_publication(plan_id=plan.pk, publish=True, actor=self.owner,
            reason="Synthetic silver offer", expected_digest=plan_edit_digest(plan), confirmed=True)
        response = self.detail(plan, {"amount": "500.00", "grade": silver.code, "rate": "100.0000"})
        self.assertEqual(response.context["illustration"]["quantity"], Decimal("5.000000"))
        self.assertEqual(response.context["illustration"]["grade"].code, silver.code)
        self.assertContains(response, '<link rel="canonical" href="http://testserver'+reverse("plan_detail", args=[plan.pk])+'">', html=True)
