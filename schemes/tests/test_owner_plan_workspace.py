"""Owner-only, read-only plan usage with scoped counts and retained history."""
from datetime import date, timedelta
from decimal import Decimal

from django.apps import apps
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import CustomUser, CustomerRegistration, PlanApplication
from schemes.catalogue_lifecycle import close_catalogue_item
from schemes.catalogue_selectors import catalogue_closure_preview
from schemes.models import SchemeAccount, SchemePlanRevision
from schemes.plan_governance import plan_edit_digest, save_scheme_plan
from schemes.plan_workspace_selectors import get_plan_agreements, get_plan_customers
from schemes.services import enroll_customer, submit_scheme_enrolment_request
from schemes.tests.grade_helpers import grade_for_mode
from schemes.tests.test_audit_exceptions import make_owner, make_customer, make_plan
from schemes.tests.test_independent_plan_drafts import draft
from schemes.tests.test_independent_policy_fields import independent_values


@override_settings(CONFIGURED_PLANS_ENABLED=True, CUSTOMER_ENROLMENT_REQUESTS_ENABLED=True)
class OwnerPlanWorkspaceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner, cls.customer = make_owner(), make_customer()
        cls.other_customer = make_customer(email="other-plan-customer@example.com")
        cls.plan, cls.other = make_plan("WORKSPACE"), make_plan("UNRELATED")
        cls.plan.publicly_listed = True
        cls.plan.save()
        cls.grade = grade_for_mode(cls.plan, "GOLD")
        cls.first = enroll_customer(customer=cls.customer, plan=cls.plan, metal_grade=cls.grade,
            start_date=date(2026, 10, 1), performed_by=cls.owner)
        cls.second = enroll_customer(customer=cls.customer, plan=cls.plan, metal_grade=cls.grade,
            start_date=date(2026, 10, 2), performed_by=cls.owner)
        cls.third = enroll_customer(customer=cls.other_customer, plan=cls.plan, metal_grade=cls.grade,
            start_date=date(2026, 10, 3), performed_by=cls.owner)
        cls.unrelated = enroll_customer(customer=cls.customer, plan=cls.other,
            metal_grade=grade_for_mode(cls.other, "GOLD"), start_date=date(2026, 10, 1), performed_by=cls.owner)

    def setUp(self):
        self.client.force_login(self.owner)

    def url(self, plan=None):
        return reverse("schemes:owner_plan_detail", args=[(plan or self.plan).pk])

    def test_owner_counts_distinguish_agreements_unique_customers_and_applicants(self):
        self.make_application(self.plan, "Prospective customer")
        response = self.client.get(self.url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["counts"]["agreements"], 3)
        self.assertEqual(response.context["counts"]["customers"], 2)
        self.assertEqual(response.context["counts"]["open_agreements"], 3)
        self.assertEqual(response.context["counts"]["applications"], 1)
        self.assertContains(response, "Current offer terms")
        self.assertContains(response, "Retirement preserves agreements")

    def test_private_owner_access_get_only_and_never_cached(self):
        self.assertIn("no-store", self.client.get(self.url())["Cache-Control"])
        self.assertEqual(self.client.post(self.url(), {}).status_code, 405)
        self.client.logout()
        self.assertEqual(self.client.get(self.url()).status_code, 302)
        for user in [self.customer.user, CustomUser.objects.create_user(username="staff-workspace", role="STAFF", is_staff=True)]:
            self.client.force_login(user)
            for section in ["overview", "agreements", "customers", "applications", "history"]:
                with self.subTest(role=user.role, section=section):
                    self.assertEqual(self.client.get(self.url(), {"section": section}).status_code, 403)
        self.assertEqual(self.client.get(reverse("schemes:owner_plan_detail", args=[999999])).status_code, 403)

    def test_unknown_id_and_unknown_section(self):
        self.assertEqual(self.client.get(reverse("schemes:owner_plan_detail", args=[999999])).status_code, 404)
        response = self.client.get(self.url(), {"section": "<script>invalid</script>"})
        self.assertEqual(response.context["section"], "overview")
        self.assertNotContains(response, "<script>invalid</script>")

    def test_agreements_keep_original_names_and_never_include_another_plan(self):
        old_name = self.first.display_plan_name
        save_scheme_plan(plan_id=self.plan.pk, values={"name": "New customer-facing name"},
            metal_grades=[self.grade], actor=self.owner, reason="Clearer offer title",
            expected_digest=plan_edit_digest(self.plan))
        response = self.client.get(self.url(), {"section": "agreements"})
        self.assertContains(response, "New customer-facing name")
        self.assertContains(response, old_name)
        self.assertContains(response, self.first.scheme_number)
        self.assertNotContains(response, self.unrelated.scheme_number)
        self.assertEqual(response.context["page_obj"].paginator.count, 3)

    def test_customer_rows_are_unique_and_counts_are_plan_scoped(self):
        with self.assertNumQueries(1):
            customers = list(get_plan_customers(self.plan.pk))
            observed = {c.pk: c.plan_agreement_count for c in customers}
        self.assertEqual(observed, {self.customer.pk: 2, self.other_customer.pk: 1})
        response = self.client.get(self.url(), {"section": "customers"})
        self.assertEqual(response.context["page_obj"].paginator.count, 2)
        self.assertContains(response, reverse("schemes:customer_detail", args=[self.customer.pk]))
        with self.assertNumQueries(1):
            for account in get_plan_agreements(self.plan.pk):
                _ = account.customer.full_name, account.display_plan_name, account.plan_revision.number, account.metal_grade.display_name

    def test_retired_plan_stays_readable_and_does_not_change_existing_accounts(self):
        before = list(SchemeAccount.objects.order_by("pk").values())
        preview = catalogue_closure_preview(plan=self.plan)
        close_catalogue_item(plan_id=self.plan.pk, actor=self.owner, reason="Retire superseded offer",
            confirmed=True, expected_digest=preview["expected_digest"])
        response = self.client.get(self.url())
        self.assertContains(response, "Plan retired")
        self.assertFalse(response.context["publicly_available"])
        self.assertFalse(response.context["enrolment_available"])
        self.assertEqual(before, list(SchemeAccount.objects.order_by("pk").values()))
        self.assertContains(self.client.get(reverse("schemes:plan_list") + "?status=closed"), self.url())

    def test_get_does_not_create_or_change_financial_or_catalogue_records(self):
        before = {m._meta.label: list(m.objects.order_by("pk").values()) for m in apps.get_app_config("schemes").get_models()}
        for section in ["overview", "agreements", "customers", "applications", "history"]:
            self.assertEqual(self.client.get(self.url(), {"section": section}).status_code, 200)
        self.assertEqual(before, {m._meta.label: list(m.objects.order_by("pk").values()) for m in apps.get_app_config("schemes").get_models()})

    def test_new_style_draft_and_release_disabled_are_explained_without_activation(self):
        plan = draft(self.owner, independent_values(accumulation="INR_PURCHASE_CREDIT"), [])
        with self.settings(CONFIGURED_PLANS_ENABLED=False):
            response = self.client.get(self.url(plan))
        self.assertContains(response, "INR jewellery purchase credit")
        self.assertContains(response, "Unpublished draft")
        self.assertContains(response, "Publication review")
        self.assertContains(response, "Positive verified entitlement")
        self.assertFalse(response.context["publicly_available"])
        self.assertFalse(response.context["enrolment_available"])

    def test_intake_sources_are_scoped_and_private_tokens_are_not_rendered(self):
        app = self.make_application(self.plan, "Workspace applicant")
        self.make_application(self.other, "Unrelated applicant")
        request = submit_scheme_enrolment_request(customer=self.customer, plan=self.plan, metal_grade=self.grade,
            requested_contribution_amount=Decimal("500"), requested_months=12, customer_message="Review request",
            actor=self.customer.user).enrolment_request
        response = self.client.get(self.url(), {"section": "applications"})
        self.assertContains(response, "Workspace applicant")
        self.assertNotContains(response, "Unrelated applicant")
        self.assertContains(response, reverse("customer_registration_detail", args=[app.registration_id]))
        self.assertContains(response, reverse("schemes:owner_enrolment_request_detail", args=[request.pk]))
        self.assertNotContains(response, app.registration.email_token_digest)
        self.assertEqual(response.context["counts"]["pending_requests"], 1)

    def test_revision_history_is_bounded_and_list_links_to_details(self):
        self.assertContains(self.client.get(reverse("schemes:plan_list")), self.url())
        source = self.plan.revisions.first()
        for number in range(2, 24):
            SchemePlanRevision.objects.create(plan=self.plan, number=number, terms=source.terms,
                actor=self.owner, actor_label="Synthetic owner", reason="Synthetic retained version")
        first = self.client.get(self.url(), {"section": "history"})
        self.assertEqual(len(first.context["page_obj"]), 20)
        self.assertEqual(first.context["page_obj"].paginator.count, 23)
        self.assertContains(first, "section=history&amp;page=2")
        second = self.client.get(self.url(), {"section": "history", "page": "2"})
        self.assertEqual(len(second.context["page_obj"]), 3)
        self.assertContains(second, "not proof of historical customer acceptance")

    def make_application(self, plan, name):
        suffix = str(CustomerRegistration.objects.count())
        registration = CustomerRegistration.objects.create(full_name=name, email=f"workspace-{suffix}@example.invalid",
            mobile_number=f"910000{int(suffix):04d}", address="Synthetic address", email_token_digest=("workspace-token-" + suffix),
            email_verification_expires_at=timezone.now() + timedelta(days=1), terms_version="test", privacy_version="test",
            consent_accepted_at=timezone.now(), source_ip_digest="synthetic-source")
        return PlanApplication.objects.create(registration=registration, plan=plan, metal_grade=self.grade,
            requested_amount=Decimal("500"), requested_months=12, expires_at=timezone.now() + timedelta(days=1))
