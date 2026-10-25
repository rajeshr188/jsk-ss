"""Exercise future orchestration, never approve or bypass readiness in runtime code."""
from contextlib import contextmanager
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings

from schemes.models import (AuditEvent, Contribution, InrPrincipalReceipt, MetalAllocation,
    SchemeAccount, SchemeInstalmentPeriod, SchemePlan, SchemePlanOffering)
from schemes.plan_governance import ensure_plan_revision, plan_edit_digest
from schemes.plan_configuration import validate_agreement_configuration
from schemes.services import enroll_customer
from schemes.tests.test_audit_exceptions import make_owner, make_customer
from schemes.tests.test_independent_agreement_storage import preparation
from schemes.tests.test_independent_policy_fields import independent_values, required_values


@contextmanager
def future_readiness_only():
    # Only these two explicit readiness checks are simulated. Keep release flag,
    # publication evidence, consent, model validation, persistence and audits real.
    # Unpatched tests below prove runtime never reaches the new write path today.
    with patch("schemes.plan_publication.require_operational_configuration"), \
         patch("schemes.plan_policies.require_operational_configuration"):
        yield


@override_settings(CONFIGURED_PLANS_ENABLED=True)
class IndependentEnrolmentTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner, cls.customer = make_owner(), make_customer()

    def offer(self, **values):
        config, plan, _, grade = preparation(self.owner, values)
        if grade:
            SchemePlanOffering.objects.create(plan=plan, metal_grade=grade)
        # A synthetic published offer in the disposable DB only. The real
        # publication service remains fail-closed for schema 2.
        plan.active = True
        revision = ensure_plan_revision(plan=plan, actor=self.owner, reason="Synthetic accepted offer")
        SchemePlan.objects.filter(pk=plan.pk).update(active=True, publication_revision=revision)
        plan.refresh_from_db()
        return dict(customer=self.customer, plan=plan, metal_grade=grade,
            start_date=date(2026, 1, 30), selected_contribution_amount=Decimal("500"),
            selected_amount_confirmed=True, expected_configuration_id=config.pk,
            expected_plan_digest=plan_edit_digest(plan), performed_by=self.owner)

    def test_actual_gates_reject_even_when_release_enabled(self):
        for accumulation in ("EXACT_METAL", "INR_PURCHASE_CREDIT"):
            offer = self.offer(**required_values(accumulation=accumulation))
            for enabled in (False, True):
                with self.settings(CONFIGURED_PLANS_ENABLED=enabled), self.assertRaises(ValidationError):
                    enroll_customer(**offer)
        self.assertFalse(SchemeAccount.objects.exists())
        self.assertFalse(SchemeInstalmentPeriod.objects.exists())
        self.assertFalse(AuditEvent.objects.filter(action="CUSTOMER_ENROLMENT").exists())

    def test_accepted_matrix_freezes_terms_schedule_and_audit_atomically(self):
        for accumulation in ("EXACT_METAL", "INR_PURCHASE_CREDIT"):
            for basis in ("CALENDAR_MONTH", "ANNIVERSARY"):
                for eligibility, duration in (("COUNT", None), ("CALENDAR_AND_COUNT", 18)):
                    offer = self.offer(**required_values(accumulation=accumulation,
                        period_basis=basis, required_count=2,
                        eligibility_policy=eligibility, duration_months=duration))
                    with future_readiness_only():
                        account = enroll_customer(**offer)
                    self.assertEqual(account.agreement_schema_version, 2)
                    self.assertEqual(account.agreed_months, duration)
                    self.assertEqual(account.required_count_snapshot, 2)
                    self.assertEqual(account.eligible_from, date(2027, 7, 30) if duration else None)
                    self.assertEqual(account.fixed_amount_snapshot, Decimal("500"))
                    self.assertEqual(account.plan_revision_id, offer["plan"].publication_revision_id)
                    self.assertEqual(account.instalment_periods.count(), 5)
                    self.assertEqual(account.instalment_periods.get(number=1).ends_before,
                        date(2026, 2, 1) if basis == "CALENDAR_MONTH" else date(2026, 2, 28))
                    audit = AuditEvent.objects.get(scheme_account=account, action="CUSTOMER_ENROLMENT")
                    self.assertEqual(audit.details["required_count"], 2)
                    self.assertEqual(audit.details["eligible_from"], "2027-07-30" if duration else None)
                    self.assertEqual(account.plan_revision.terms["eligibility_basis"],
                        "COUNT" if not duration else "DURATION_AND_COUNT")
                    validate_agreement_configuration(account)
        for model in (Contribution, InrPrincipalReceipt, MetalAllocation):
            self.assertFalse(model.objects.exists())

    def test_optional_anytime_preference_never_becomes_fixed_amount_or_obligation(self):
        for accumulation in ("EXACT_METAL", "INR_PURCHASE_CREDIT"):
            offer = self.offer(**independent_values(accumulation=accumulation))
            with future_readiness_only():
                account = enroll_customer(**offer)
            self.assertIsNone(account.agreed_months)
            self.assertIsNone(account.eligible_from)
            self.assertIsNone(account.required_count_snapshot)
            self.assertIsNone(account.fixed_amount_snapshot)
            self.assertFalse(account.instalment_periods.exists())
            self.assertEqual(account.savings_mode, "GOLD" if offer["metal_grade"] else "INR_CREDIT")

    def test_plan_fixed_benefit_schedule_does_not_extend_duration(self):
        offer = self.offer(**required_values(accumulation="INR_PURCHASE_CREDIT",
            amount_policy="PLAN_FIXED", fixed_amount=Decimal("500"),
            minimum_amount=Decimal("500"), maximum_amount=Decimal("500"),
            eligibility_policy="CALENDAR", duration_months=12, required_count=2,
            missed_payment_policy="LOSE_UNEARNED_BENEFIT", max_extension_months=None,
            benefit_policy="VA_DISCOUNT", benefit_percentage=Decimal("5"), benefit_cap_inr=Decimal("500"),
            benefit_qualification="REQUIRED_SCHEDULE", benefit_on_miss="DISQUALIFY_UNEARNED",
            eligible_charge_definition="Published making charges excluding taxes"))
        with future_readiness_only():
            account = enroll_customer(**(offer | dict(selected_contribution_amount=None)))
        self.assertEqual(account.fixed_amount_snapshot, Decimal("500"))
        self.assertEqual(account.instalment_periods.count(), 2)
        self.assertEqual(account.eligible_from, date(2027, 1, 30))
        self.assertEqual(account.cash_bonus_percentage_snapshot, Decimal("0"))
        self.assertFalse(InrPrincipalReceipt.objects.exists())

    def test_confirmation_amount_duration_owner_and_stale_offer_are_required(self):
        offer = self.offer(**required_values())
        changes = [dict(selected_amount_confirmed=False), dict(selected_amount_confirmed="yes"),
            dict(expected_configuration_id=-1), dict(expected_plan_digest="stale"),
            dict(performed_by=self.customer.user), dict(selected_contribution_amount=None),
            dict(selected_contribution_amount=Decimal("99")), dict(agreed_months=12)]
        with future_readiness_only():
            for change in changes:
                with self.subTest(change=change), self.assertRaises(ValidationError):
                    enroll_customer(**(offer | change))
        self.assertFalse(SchemeAccount.objects.exists())
        self.assertFalse(SchemeInstalmentPeriod.objects.exists())

    def test_duration_is_exact_not_a_customer_override(self):
        offer = self.offer(**required_values(eligibility_policy="CALENDAR_AND_COUNT", duration_months=18))
        with future_readiness_only():
            for duration in (0, 12, 19, True, "18"):
                with self.assertRaises(ValidationError):
                    enroll_customer(**(offer | dict(agreed_months=duration)))
            account = enroll_customer(**(offer | dict(agreed_months=18)))
        self.assertEqual(account.agreed_months, 18)

    def test_inr_rejects_grade_and_legacy_cash_mode(self):
        offer = self.offer(**independent_values(accumulation="INR_PURCHASE_CREDIT"))
        metal = self.offer(**independent_values())["metal_grade"]
        with future_readiness_only():
            for change in (dict(metal_grade=metal), dict(savings_mode="CASH"), dict(savings_mode="GOLD")):
                with self.assertRaises(ValidationError):
                    enroll_customer(**(offer | change))
        self.assertFalse(SchemeAccount.objects.exists())

    def test_release_and_publication_checks_not_bypassed_by_orchestration(self):
        offer = self.offer(**required_values())
        with future_readiness_only():
            with self.settings(CONFIGURED_PLANS_ENABLED=False), self.assertRaises(ValidationError):
                enroll_customer(**offer)
            SchemePlan.objects.filter(pk=offer["plan"].pk).update(name="Changed after publication")
            with self.assertRaises(ValidationError):
                enroll_customer(**offer)
        self.assertFalse(SchemeAccount.objects.exists())

    def test_audit_failure_rolls_back_account_and_complete_schedule(self):
        offer = self.offer(**required_values())
        with future_readiness_only(), patch("schemes.services.record_audit_event", side_effect=ValidationError("Audit failure")):
            with self.assertRaisesMessage(ValidationError, "Audit failure"):
                enroll_customer(**offer)
        self.assertFalse(SchemeAccount.objects.exists())
        self.assertFalse(SchemeInstalmentPeriod.objects.exists())

    def test_schedule_failure_rolls_back_account_and_preserves_offer(self):
        offer = self.offer(**required_values())
        before = list(offer["plan"].revisions.values())
        with future_readiness_only(), patch("schemes.instalments.prepare_instalment_periods", side_effect=ValidationError("Schedule failure")):
            with self.assertRaisesMessage(ValidationError, "Schedule failure"):
                enroll_customer(**offer)
        self.assertFalse(SchemeAccount.objects.exists())
        self.assertFalse(AuditEvent.objects.filter(action="CUSTOMER_ENROLMENT").exists())
        self.assertEqual(list(offer["plan"].revisions.values()), before)
