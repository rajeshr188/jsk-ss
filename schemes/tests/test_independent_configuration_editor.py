"""Owner preparation is independent of activation; immutable history is preserved."""
from decimal import Decimal

from django.test import Client, TestCase, override_settings
from django.urls import reverse

from schemes.configuration_forms import IndependentConfigurationForm, POLICY_FIELDS
from schemes.models import (SchemePlanConfiguration, SchemePlan, SchemeAccount, Contribution,
    MetalAllocation, InrPrincipalReceipt, SchemeBenefitAward)
from schemes.plan_configuration import create_configuration_version, configuration_evidence
from schemes.tests.test_audit_exceptions import make_owner, make_customer
from schemes.tests.test_independent_policy_fields import independent_values, required_values


@override_settings(CONFIGURED_PLANS_ENABLED=False)
class IndependentConfigurationEditorTests(TestCase):
    def setUp(self):
        self.owner, self.customer = make_owner(), make_customer()
        self.client.force_login(self.owner)
        self.url = reverse("schemes:independent_configuration_create")

    def payload(self, values=None, **changes):
        row = SchemePlanConfiguration(**(values or independent_values()))
        data = {name: str(getattr(row, name)) if getattr(row, name) is not None else "" for name in POLICY_FIELDS}
        data["allow_contributions_after_eligibility"] = row.allow_contributions_after_eligibility
        return data | {"reason": "Owner reviewed independent preparation", "action": "save"} | changes

    def assert_no_financial_writes(self):
        for model in (SchemePlan, SchemeAccount, Contribution, MetalAllocation, InrPrincipalReceipt, SchemeBenefitAward):
            self.assertFalse(model.objects.exists(), model.__name__)

    def test_matrix_families_amounts_bases_and_benefits_validate(self):
        for metal in ("EXACT_METAL", "INR_PURCHASE_CREDIT"):
            for basis in ("CALENDAR_MONTH", "ANNIVERSARY"):
                for amount in ("PLAN_FIXED", "CUSTOMER_FIXED", "VARIABLE"):
                    amounts = dict(amount_policy=amount)
                    if amount == "PLAN_FIXED":
                        amounts.update(minimum_amount=Decimal("500"), maximum_amount=Decimal("500"), fixed_amount=Decimal("500"))
                    cases = [independent_values(accumulation=metal, **amounts),
                        independent_values(accumulation=metal, eligibility_policy="CALENDAR", duration_months=1,
                            period_basis=basis, frequency_rule="ONCE_PER_PERIOD", **amounts)]
                    if amount != "VARIABLE":
                        cases += [required_values(accumulation=metal, period_basis=basis, required_count=2, **amounts),
                            required_values(accumulation=metal, period_basis=basis, required_count=2,
                                eligibility_policy="CALENDAR_AND_COUNT", duration_months=18, **amounts),
                            required_values(accumulation=metal, period_basis=basis, required_count=2,
                                eligibility_policy="CALENDAR", duration_months=12, missed_payment_policy="LOSE_UNEARNED_BENEFIT",
                                max_extension_months=None, benefit_policy="VA_DISCOUNT", benefit_percentage=Decimal("5"),
                                benefit_cap_inr=Decimal("500"), benefit_qualification="REQUIRED_SCHEDULE",
                                benefit_on_miss="DISQUALIFY_UNEARNED", eligible_charge_definition="Making charges excluding tax", **amounts)]
                    for values in cases:
                        form = IndependentConfigurationForm(self.payload(values))
                        self.assertTrue(form.is_valid(), (values, form.errors))
                        self.assertEqual(form.configuration_values()["policy_schema_version"], 2)
                        self.assertIsNone(form.configuration_values()["minimum_months"])
        bonus = independent_values(accumulation="INR_PURCHASE_CREDIT", benefit_policy="INR_PURCHASE_BONUS",
            benefit_percentage=Decimal("3.50"), benefit_cap_inr=Decimal("250"), benefit_qualification="NORMAL_ELIGIBILITY")
        self.assertTrue(IndependentConfigurationForm(self.payload(bonus)).is_valid())
        self.assertFalse(SchemePlanConfiguration.objects.exists())
        self.assert_no_financial_writes()

    def test_preview_saves_nothing_and_save_is_preparation_only(self):
        data = self.payload()
        preview = self.client.post(self.url, data | {"action": "preview"})
        self.assertContains(preview, "Review before saving")
        self.assertContains(preview, "No minimum-duration condition")
        self.assertFalse(SchemePlanConfiguration.objects.exists())
        saved = self.client.post(self.url, data)
        row = SchemePlanConfiguration.objects.get()
        self.assertRedirects(saved, reverse("schemes:plan_configuration_detail", args=[row.pk]))
        self.assertEqual(row.policy_schema_version, 2)
        self.assertEqual(row.created_by, self.owner)
        self.assertEqual(row.reason, data["reason"])
        self.assertEqual(row.settlement_policy, "FULL_ONLY")
        self.assertEqual(row.grace_days, 0)
        self.assert_no_financial_writes()
        for enabled in (False, True):
            with self.settings(CONFIGURED_PLANS_ENABLED=enabled):
                response = self.client.post(reverse("schemes:configured_plan_create", args=[row.pk]),
                    {"name": "Attempted offer", "code": "BLOCKED", "reason": "Test"})
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context["form"].errors)  # Exact-metal draft needs an offered grade.
                self.assertFalse(SchemePlan.objects.exists())

    def test_new_version_appends_and_refuses_stale_predecessor(self):
        original = create_configuration_version(values=required_values(), actor=self.owner, reason="Original")
        before = configuration_evidence(original)
        url = reverse("schemes:plan_configuration_new_version", args=[original.pk])
        page = self.client.get(url)
        self.assertContains(page, "New version of")
        self.assertEqual(page.context["form"].initial["required_count"], 10)
        data = self.payload(required_values(required_count=4), name="Successor")
        self.assertEqual(self.client.post(url, data).status_code, 302)
        successor = original.successor
        self.assertEqual(successor.version, 2)
        self.assertEqual(successor.required_count, 4)
        original.refresh_from_db()
        self.assertEqual(configuration_evidence(original), before)
        rejected = self.client.post(url, data)
        self.assertContains(rejected, "already has a newer version")
        self.assertEqual(SchemePlanConfiguration.objects.count(), 2)
        self.assert_no_financial_writes()

    def test_invalid_combinations_and_forged_controls_are_form_errors(self):
        data = self.payload()
        for change in ({"required_count": 2}, {"duration_months": 12}, {"minimum_amount": "NaN"},
                {"amount_policy": "PLAN_FIXED"}, {"period_basis": "CALENDAR_MONTH"},
                {"benefit_policy": "INR_PURCHASE_BONUS"}, {"benefit_percentage": "1.234"},
                {"eligibility_policy": "COUNT"}, {"frequency_rule": "ONCE_PER_MONTH"},
                {"eligible_charge_definition": "x" * 2001}, {"reason": " "}):
            response = self.client.post(self.url, data | change)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context["form"].errors, change)
        for field in ("policy_schema_version", "settlement_policy", "grace_days", "created_by", "previous_id", "family_id", "minimum_months"):
            response = self.client.post(self.url, data | {field: "forged"})
            self.assertContains(response, "Unsupported policy input")
        self.assertFalse(SchemePlanConfiguration.objects.exists())

    def test_bad_preview_cannot_save_and_missing_action_is_not_a_save(self):
        data = self.payload()
        self.assertEqual(self.client.post(self.url, data | {"action": "preview"}).status_code, 200)
        response = self.client.post(self.url, data | {"required_count": "12"})
        self.assertTrue(response.context["form"].errors)
        self.assertContains(self.client.post(self.url, data | {"action": ""}), "Choose Review configuration")
        self.assertFalse(SchemePlanConfiguration.objects.exists())

    def test_access_csrf_methods_and_old_editor_are_preserved(self):
        response = self.client.get(self.url)
        self.assertContains(response, "Conditional purchase benefit")
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(self.client.put(self.url).status_code, 405)
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.owner)
        self.assertEqual(csrf.post(self.url, self.payload()).status_code, 403)
        self.client.force_login(self.customer.user)
        self.assertEqual(self.client.post(self.url, self.payload()).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 302)
        self.client.force_login(self.owner)
        old = self.client.get(reverse("schemes:plan_configuration_create"))
        self.assertContains(old, "Create configuration")
        self.assertNotContains(old, 'name="benefit_policy"')
        self.assertFalse(SchemePlanConfiguration.objects.exists())
