"""Actual publication/enrolment integration; no readiness function is mocked."""
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse

from schemes.catalogue_lifecycle import close_catalogue_item
from schemes.catalogue_selectors import catalogue_closure_preview
from schemes.models import AuditEvent, Contribution, MetalGrade, SchemeAccount, SchemePlanOffering
from schemes.plan_governance import plan_edit_digest
from schemes.plan_publication import set_configured_plan_publication, validate_publication_evidence
from schemes.publication_selectors import get_publication_blockers
from schemes.selectors import get_public_scheme_plans
from schemes.services import enroll_customer
from schemes.tests.test_audit_exceptions import make_owner, make_customer
from schemes.tests.test_independent_plan_drafts import draft
from schemes.tests.test_independent_policy_fields import independent_values, required_values


@override_settings(CONFIGURED_PLANS_ENABLED=True)
class IndependentPublicationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner, cls.customer = make_owner(), make_customer()
        cls.grade = MetalGrade.objects.get(code="GOLD_22K_916")

    def offer(self, **values):
        values = independent_values(**values)
        return draft(self.owner, values, [self.grade] if values.get("accumulation", "EXACT_METAL") == "EXACT_METAL" else [])

    def publish(self, plan, publish=True, **changes):
        result, _ = set_configured_plan_publication(**dict(plan_id=plan.pk, publish=publish,
            actor=self.owner, expected_digest=plan_edit_digest(plan), confirmed=True,
            reason="Synthetic reviewed offer", **changes))
        plan.refresh_from_db()
        return result

    def test_actual_publication_requires_intake_flag_and_preserves_existing_evidence(self):
        for denomination in ("EXACT_METAL", "INR_PURCHASE_CREDIT"):
            plan = self.offer(accumulation=denomination)
            with self.settings(CONFIGURED_PLANS_ENABLED=False):
                self.assertIn("The configured-plan release gate is disabled.", get_publication_blockers(plan))
                with self.assertRaises(ValidationError):
                    self.publish(plan)
            self.assertEqual(get_publication_blockers(plan), ())
            self.publish(plan)
            with self.settings(CONFIGURED_PLANS_ENABLED=False):
                validate_publication_evidence(plan)
                self.publish(plan, publish=False)
            self.assertFalse(plan.active or plan.publicly_listed)

    def test_five_families_publish_and_enrol_without_metal_on_inr(self):
        for denomination in ("EXACT_METAL", "INR_PURCHASE_CREDIT"):
            cases = [independent_values(accumulation=denomination),
                independent_values(accumulation=denomination, eligibility_policy="CALENDAR", duration_months=12),
                required_values(accumulation=denomination),
                required_values(accumulation=denomination, eligibility_policy="CALENDAR_AND_COUNT", duration_months=18),
                required_values(accumulation=denomination, eligibility_policy="CALENDAR", duration_months=12,
                    missed_payment_policy="LOSE_UNEARNED_BENEFIT", max_extension_months=None,
                    benefit_policy="VA_DISCOUNT", benefit_percentage=Decimal("5.00"), benefit_cap_inr=Decimal("500.00"),
                    benefit_qualification="REQUIRED_SCHEDULE", benefit_on_miss="DISQUALIFY_UNEARNED",
                    eligible_charge_definition="Invoice making charges before tax")]
            for values in cases:
                with self.subTest(denomination=denomination, eligibility=values["eligibility_policy"]):
                    plan = self.offer(**values)
                    self.assertEqual(get_publication_blockers(plan), ())
                    self.publish(plan)
                    validate_publication_evidence(plan)
                    self.assertIn(plan, get_public_scheme_plans())
                    account = enroll_customer(customer=self.customer, plan=plan,
                        metal_grade=self.grade if denomination == "EXACT_METAL" else None,
                        selected_contribution_amount=Decimal("500"), selected_amount_confirmed=True,
                        start_date=date(2026, 1, 30), expected_configuration_id=plan.configuration_id,
                        expected_plan_digest=plan_edit_digest(plan), performed_by=self.owner)
                    self.assertEqual(account.configuration_snapshot_id, plan.configuration_id)
                    self.assertEqual(account.plan_revision_id, plan.publication_revision_id)
                    self.assertEqual(account.metal_grade_id, self.grade.pk if denomination == "EXACT_METAL" else None)
        self.assertEqual(SchemeAccount.objects.count(), 10)
        self.assertFalse(Contribution.objects.exists())

    def test_denomination_mismatch_rejected_even_with_workflow_acceptance(self):
        metal = self.offer()
        metal.metal_offerings.update(active=False)
        credit = self.offer(accumulation="INR_PURCHASE_CREDIT")
        SchemePlanOffering.objects.create(plan=credit, metal_grade=self.grade)
        for plan in (metal, credit):
            self.assertTrue(get_publication_blockers(plan))
            with self.assertRaises(ValidationError):
                self.publish(plan)
            plan.refresh_from_db()
            self.assertFalse(plan.active or plan.publicly_listed)

    def test_post_publication_denomination_corruption_is_not_valid_evidence(self):
        for denomination in ("EXACT_METAL", "INR_PURCHASE_CREDIT"):
            plan = self.offer(accumulation=denomination)
            self.publish(plan)
            if denomination == "EXACT_METAL":
                plan.metal_offerings.update(active=False)
            else:
                SchemePlanOffering.objects.create(plan=plan, metal_grade=self.grade)
            with self.assertRaises(ValidationError):
                validate_publication_evidence(plan)

    def test_withdrawal_preserves_publication_revision_and_survives_release_disabled(self):
        plan = self.offer(accumulation="INR_PURCHASE_CREDIT")
        self.publish(plan)
        revision = plan.publication_revision_id
        with self.settings(CONFIGURED_PLANS_ENABLED=False):
            self.publish(plan, publish=False)
        self.assertFalse(plan.active or plan.publicly_listed)
        self.assertEqual(plan.publication_revision_id, revision)
        self.assertNotIn(plan, get_public_scheme_plans())

    def test_review_uses_real_blockers_and_ready_ui_does_not_bypass_service(self):
        plan = self.offer(accumulation="INR_PURCHASE_CREDIT")
        self.client.force_login(self.owner)
        url = reverse("schemes:configured_plan_publication", args=[plan.pk])
        with self.settings(CONFIGURED_PLANS_ENABLED=False):
            response = self.client.get(url)
            self.assertContains(response, 'class="btn btn-jsk" disabled')
        response = self.client.get(url)
        self.assertNotContains(response, 'class="btn btn-jsk" disabled')
        self.assertContains(response, "INR purchase credit: no metal grade")
        # A ready GET cannot authorize a later POST after intake is disabled.
        with self.settings(CONFIGURED_PLANS_ENABLED=False):
            response = self.client.post(url, dict(expected_digest=plan_edit_digest(plan),
                reason="Ready page became stale", confirmed="on"))
        self.assertEqual(response.status_code, 200)
        plan.refresh_from_db()
        self.assertFalse(plan.active)

    def test_retired_plan_cannot_be_republished_after_acceptance(self):
        plan = self.offer(accumulation="INR_PURCHASE_CREDIT")
        self.publish(plan)
        close_catalogue_item(actor=self.owner, reason="Retire synthetic offer", confirmed=True,
            expected_digest=catalogue_closure_preview(plan=plan)["expected_digest"], plan_id=plan.pk)
        plan.refresh_from_db()
        self.assertTrue(get_publication_blockers(plan))
        with self.assertRaises(ValidationError):
            self.publish(plan)

    def test_audit_failure_rolls_back_publication_and_revision(self):
        plan = self.offer(accumulation="INR_PURCHASE_CREDIT")
        before = AuditEvent.objects.count()
        with patch("schemes.services.record_scheme_plan_change", side_effect=RuntimeError("audit unavailable")):
            with self.assertRaises(RuntimeError):
                self.publish(plan)
        plan.refresh_from_db()
        self.assertFalse(plan.active or plan.publicly_listed)
        self.assertEqual(plan.revisions.count(), 1)
        self.assertEqual(AuditEvent.objects.count(), before)
