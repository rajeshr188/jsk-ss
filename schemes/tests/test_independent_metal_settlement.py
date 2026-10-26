"""Real closure/award/invoice transactions on gated synthetic independent contracts."""
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from io import StringIO
from threading import Barrier
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.core.management import call_command, CommandError
from django.db import connections
from django.test import TestCase, TransactionTestCase, override_settings

from schemes.agreement_eligibility import get_independent_eligibility, get_closure_eligibility
from schemes.benefit_selectors import get_benefit_qualification
from schemes.closures import request_scheme_closure, review_scheme_closure
from schemes.independent_settlement_selectors import validate_independent_settlement_benefit
from schemes.models import (SchemeAccount, SchemeBenefitAward, BenefitInvoiceFulfilment,
    BenefitInvoiceReversal, ConfiguredSettlement, ConfiguredSettlementReversal,
    Contribution, MetalAllocation, Redemption, RedemptionReversal, AuditEvent)
from schemes.selectors import get_metal_balance
from schemes.settlements import preview_full_settlement, settle_configured_agreement, reverse_configured_settlement
from schemes.tests.test_benefit_awards import AwardFixture, future_award_readiness
from schemes.tests.test_independent_instalment_ledger import NOW, source
from schemes.tests.test_independent_instalment_reviews import instant


class MetalClosureFixture(AwardFixture):
    def accepted(self, account):
        with future_award_readiness():
            request = request_scheme_closure(account_id=account.pk, actor=self.customer.user,
                reason="Customer requests full jewellery settlement", idempotency_key=uuid.uuid4())
            return review_scheme_closure(request_id=request.pk, actor=self.owner, action="ACCEPT",
                expected_sequence=1, reason="Review customer request", idempotency_key=uuid.uuid4())

    def invoice(self):
        return dict(invoice_before_benefit=Decimal("1000.00"), eligible_charges=Decimal("200.00"),
            invoice_evidence_reference="Itemised jewellery invoice", eligible_charge_reference="Making charge line",
            customer_receipt_reference="Signed jewellery handover")

    def prepared(self, request, *, benefit=True):
        with future_award_readiness():
            return preview_full_settlement(request_id=request.pk, actor=self.owner,
                benefit_invoice=self.invoice() if benefit else None)

    def settlement_values(self, request, token, **changes):
        return dict(request_id=request.pk, actor=self.owner, preview_token=token,
            invoice_reference="INV-" + uuid.uuid4().hex, authorization_reference="Customer approved exact final handover",
            reason="Full principal and contracted benefit", idempotency_key=uuid.uuid4()) | changes

    def settle(self, values):
        with future_award_readiness():
            return settle_configured_agreement(**values)

    def reversal_values(self, r, *, benefit=True):
        return dict(settlement_id=r.configured_settlement.pk, actor=self.owner, reason="Full goods return and invoice correction",
            authorization_reference="Signed full return", expected_sequence=3, idempotency_key=uuid.uuid4(),
            benefit_return=dict(invoice_correction_reference="COR-" + uuid.uuid4().hex,
                customer_confirmation="Customer signed full return", returned_at=NOW) if benefit else None)

    def reverse(self, values):
        with future_award_readiness():
            return reverse_configured_settlement(**values)


@override_settings(IN_STORE_CASH_CONTRIBUTIONS_ENABLED=True, PAYMENT_INITIATION_KILL_SWITCH=False)
class IndependentMetalSettlementTests(MetalClosureFixture, TestCase):
    def test_owner_assisted_closure_preserves_24k_and_silver_grade(self):
        from datetime import date
        from schemes.agreement_contracts import resolve_independent_agreement_terms
        from schemes.models import MetalGrade, SchemePlanRevision
        from schemes.services import publish_scheme_rate
        from schemes.tests.test_independent_agreement_storage import preparation
        from schemes.tests.test_independent_policy_fields import independent_values
        for code in ("GOLD_24K_9999", "SILVER_999"):
            grade = MetalGrade.objects.get(code=code)
            config, plan, original, _ = preparation(self.owner, independent_values(
                accumulation="EXACT_METAL", benefit_policy="VA_DISCOUNT",
                benefit_percentage=Decimal("10"), benefit_cap_inr=Decimal("40"),
                benefit_qualification="NORMAL_ELIGIBILITY", benefit_on_miss="NONE",
                eligible_charge_definition="Making charges excluding taxes"))
            revision = SchemePlanRevision.objects.create(plan=plan, number=2, actor=self.owner,
                actor_label="Owner", reason="Synthetic grade-specific offer",
                terms=original.terms | {"metal_grades": [code]})
            terms = resolve_independent_agreement_terms(configuration_id=config.pk,
                start_date=date(2026, 1, 30), selected_amount=Decimal("500"), metal_grade_id=grade.pk)
            a = SchemeAccount(customer=self.customer, scheme_number=uuid.uuid4().hex[:20], plan=plan,
                plan_revision=revision, plan_name_snapshot=plan.name, plan_code_snapshot=plan.code,
                **terms.account_snapshots())
            SchemeAccount.objects.bulk_create([a])  # Unreleased fixture only, no production enrolment bypass.
            rate = publish_scheme_rate(metal_grade=grade, rate_per_gram=Decimal("10000"), published_by=self.owner)
            self.cash(a, expected_scheme_rate_id=rate.pk)
            with future_award_readiness():
                with self.assertRaises(ValidationError):
                    request_scheme_closure(account_id=a.pk, actor=self.owner, reason="Missing authorization",
                        idempotency_key=uuid.uuid4())
                request = request_scheme_closure(account_id=a.pk, actor=self.owner,
                    reason="Customer requests full closure", authorization_reference="Signed customer request",
                    idempotency_key=uuid.uuid4())
                review_scheme_closure(request_id=request.pk, actor=self.owner, action="ACCEPT",
                    expected_sequence=1, reason="Verify request", idempotency_key=uuid.uuid4())
            _, token = self.prepared(request)
            r = self.settle(self.settlement_values(request, token))
            self.assertEqual(r.metal_grade_id, grade.pk)
            self.assertEqual(r.entitlement_amount, Decimal("0.050000"))
            self.assertIsNone(r.gold_quantity if grade.metal == "SILVER" else r.silver_quantity)
            self.reverse(self.reversal_values(r))
            self.assertEqual(get_metal_balance(a), Decimal("0.050000"))

    def test_normal_matrix_creates_award_invoice_and_full_closure_atomically(self):
        for family in ("anytime", "duration", "count", "both", "benefit_duration"):
            values = {}
            monthly = family in ("count", "both", "benefit_duration")
            if family in ("duration", "benefit_duration"):
                values.update(eligibility_policy="CALENDAR", duration_months=1)
            if family == "both":
                values.update(eligibility_policy="CALENDAR_AND_COUNT", duration_months=1)
            if family == "benefit_duration":
                values.update(missed_payment_policy="LOSE_UNEARNED_BENEFIT", max_extension_months=None,
                    benefit_on_miss="DISQUALIFY_UNEARNED")
            a = self.benefit_account(monthly=monthly, metal=True, kind="VA_DISCOUNT", **values)
            self.cash(a)
            at = instant(a.eligible_from) if a.eligible_from else NOW
            with patch("django.utils.timezone.now", return_value=at):
                request = self.accepted(a)
                self.assertEqual(get_independent_eligibility(a).state, "CLOSURE_PENDING")
                self.assertEqual(get_benefit_qualification(a).state, "HISTORY_REVIEW")
                evidence, token = self.prepared(request)
                self.assertEqual(evidence["basis"], "NORMAL")
                self.assertFalse(SchemeBenefitAward.objects.filter(scheme_account=a).exists())
                original = list(a.contributions.values())
                params = self.settlement_values(request, token)
                r = self.settle(params)
                self.assertEqual(self.settle(params).pk, r.pk)
                a.refresh_from_db()
                self.assertEqual(a.status, "REDEEMED")
                self.assertEqual(get_metal_balance(a), 0)
                award = SchemeBenefitAward.objects.get(scheme_account=a)
                f = award.invoice_fulfilments.get()
                self.assertEqual(f.benefit_amount, Decimal("20.00"))
                self.assertEqual(f.metal_settlement.redemption_id, r.pk)
                self.assertEqual(award.evidence["closure"], str(request.pk))
                self.assertEqual(original, list(a.contributions.values()))
                validate_independent_settlement_benefit(r.configured_settlement)
                with self.assertRaises(ValidationError):
                    self.prepared(request)

    def test_early_exit_preserves_all_principal_without_earning_completion_benefit(self):
        a = self.benefit_account(metal=True, kind="VA_DISCOUNT", required_count=2)
        self.cash(a)
        request = self.accepted(a)
        evidence, token = self.prepared(request, benefit=False)
        self.assertEqual(evidence["basis"], "EARLY")
        self.assertEqual(evidence["independent"]["qualification"]["state"], "WAITING_SCHEDULE")
        r = self.settle(self.settlement_values(request, token))
        self.assertEqual(r.gold_quantity, Decimal("0.050000"))
        self.assertFalse(SchemeBenefitAward.objects.exists())
        self.assertFalse(BenefitInvoiceFulfilment.objects.exists())

    def test_no_benefit_count_and_anytime_contracts_redeem_without_invented_dates(self):
        for monthly in (False, True):
            a = self.account(monthly=monthly, metal=True, **({"required_count": 1} if monthly else {}))
            self.cash(a)
            request = self.accepted(a)
            evidence, token = self.prepared(request, benefit=False)
            self.assertEqual(evidence["basis"], "NORMAL")
            self.assertIsNone(a.eligible_from)
            r = self.settle(self.settlement_values(request, token))
            self.assertEqual(get_metal_balance(a), 0)
            self.assertFalse(SchemeBenefitAward.objects.exists())
            self.reverse(self.reversal_values(r, benefit=False))
            self.assertEqual(get_metal_balance(a), Decimal("0.050000"))

    def test_missed_benefit_instalment_does_not_forfeit_date_eligible_principal(self):
        for basis in ("CALENDAR_MONTH", "ANNIVERSARY"):
            a = self.benefit_account(metal=True, kind="VA_DISCOUNT", period_basis=basis,
                eligibility_policy="CALENDAR", duration_months=1, required_count=2,
                missed_payment_policy="LOSE_UNEARNED_BENEFIT", max_extension_months=None,
                benefit_on_miss="DISQUALIFY_UNEARNED")
            self.cash(a)
            ended = instant(a.instalment_periods.get(number=2).ends_before)
            with patch("django.utils.timezone.now", return_value=ended):
                request = self.accepted(a)
                evidence, token = self.prepared(request, benefit=False)
                self.assertEqual(evidence["basis"], "NORMAL")
                self.assertEqual(evidence["independent"]["qualification"]["state"], "UNQUALIFIED_MISS")
                r = self.settle(self.settlement_values(request, token))
                self.assertEqual(r.gold_quantity, Decimal("0.050000"))
                self.assertEqual(get_metal_balance(a), 0)
        self.assertFalse(SchemeBenefitAward.objects.exists())

    def test_pending_provider_payment_blocks_first_settlement_without_discarding_sources(self):
        a = self.benefit_account(monthly=False, metal=True, kind="VA_DISCOUNT",
            allow_contributions_after_eligibility=True)
        self.cash(a)
        request = self.accepted(a)
        _, token = self.prepared(request)
        # Simulate a pending provider exposure discovered after preview in the disposable DB.
        pending = source(a)
        with self.assertRaises(ValidationError):
            self.settle(self.settlement_values(request, token))
        pending.refresh_from_db()
        self.assertEqual(pending.status, "PENDING")
        self.assertFalse(Redemption.objects.exists())
        self.assertFalse(SchemeBenefitAward.objects.exists())
        self.assertEqual(get_metal_balance(a), Decimal("0.050000"))

    def test_previously_retained_award_is_reused_not_replaced_or_stacked(self):
        a = self.benefit_account(metal=True, kind="VA_DISCOUNT")
        self.cash(a)
        award = self.record(a, self.preview(a))
        original = SchemeBenefitAward.objects.values().get(pk=award.pk)
        request = self.accepted(a)
        _, token = self.prepared(request)
        self.settle(self.settlement_values(request, token))
        self.assertEqual(original, SchemeBenefitAward.objects.values().get(pk=award.pk))
        self.assertEqual(SchemeBenefitAward.objects.count(), 1)

    def test_failure_after_invoice_insert_rolls_back_award_principal_audit_and_closure(self):
        a = self.benefit_account(metal=True, kind="VA_DISCOUNT")
        self.cash(a)
        request = self.accepted(a)
        _, token = self.prepared(request)
        params = self.settlement_values(request, token)
        before = [list(m.objects.values()) for m in (SchemeAccount, Contribution, MetalAllocation, AuditEvent)]
        from schemes.benefit_fulfilments import record_benefit_fulfilment
        def fail(**kwargs):
            record_benefit_fulfilment(**kwargs)
            raise ValidationError("Injected post-invoice failure")
        with patch("schemes.benefit_fulfilments.record_benefit_fulfilment", side_effect=fail), self.assertRaises(ValidationError):
            self.settle(params)
        for model in (SchemeBenefitAward, BenefitInvoiceFulfilment, ConfiguredSettlement, Redemption):
            self.assertFalse(model.objects.exists())
        self.assertEqual(request.events.count(), 2)
        self.assertEqual(before, [list(m.objects.values()) for m in (SchemeAccount, Contribution, MetalAllocation, AuditEvent)])
        self.settle(params)

    def test_full_return_reverses_benefit_and_principal_together_and_contains_account(self):
        a = self.benefit_account(metal=True, kind="VA_DISCOUNT")
        self.cash(a)
        request = self.accepted(a)
        _, token = self.prepared(request)
        r = self.settle(self.settlement_values(request, token))
        params = self.reversal_values(r)
        with self.assertRaises(ValidationError):
            self.reverse(params | {"benefit_return": None})
        from schemes.benefit_fulfilments import reverse_benefit_fulfilment
        def fail(**kwargs):
            reverse_benefit_fulfilment(**kwargs)
            raise ValidationError("Injected post-return failure")
        with patch("schemes.benefit_fulfilments.reverse_benefit_fulfilment", side_effect=fail), self.assertRaises(ValidationError):
            self.reverse(params)
        self.assertFalse(RedemptionReversal.objects.exists())
        self.assertFalse(BenefitInvoiceReversal.objects.exists())
        self.assertEqual(get_metal_balance(a), 0)
        reversal = self.reverse(params)
        self.assertEqual(self.reverse(params).pk, reversal.pk)
        self.assertEqual(get_metal_balance(a), Decimal("0.050000"))
        a.refresh_from_db()
        self.assertEqual(a.status, "CLOSURE_PENDING")
        self.assertEqual(BenefitInvoiceReversal.objects.get().amount, Decimal("20.00"))
        with self.assertRaises(ValidationError):
            self.prepared(request)
        validate_independent_settlement_benefit(ConfiguredSettlement.objects.get(redemption=r))

    def test_invalid_authority_stale_preview_expiry_and_outage_hold(self):
        a = self.benefit_account(metal=True, kind="VA_DISCOUNT", required_count=2)
        self.cash(a)
        request = self.accepted(a)
        _, token = self.prepared(request, benefit=False)
        params = self.settlement_values(request, token)
        for changes in (dict(actor=self.customer.user), dict(preview_token=token + "tampered")):
            with self.assertRaises(ValidationError):
                self.settle(params | changes)
        with patch("django.core.signing.time.time", return_value=time.time() + 601), self.assertRaises(ValidationError):
            self.settle(params)
        self.hold(a)
        with self.assertRaises(ValidationError):
            self.settle(params)
        self.assertFalse(Redemption.objects.exists())

    def test_exact_invoice_required_and_inr_stays_outside_this_metal_path(self):
        a = self.benefit_account(metal=True, kind="VA_DISCOUNT")
        self.cash(a)
        request = self.accepted(a)
        with self.assertRaises(ValidationError):
            self.prepared(request, benefit=False)
        with future_award_readiness(), self.assertRaises(ValidationError):
            preview_full_settlement(request_id=request.pk, actor=self.owner,
                benefit_invoice=self.invoice() | {"eligible_charges": Decimal("2000")})
        b = self.benefit_account()
        self.cash(b)
        other = self.accepted(b)
        with self.assertRaises(ValidationError):
            self.prepared(other)
        with self.assertRaises(ValidationError):
            get_closure_eligibility(request.__class__(pk=other.pk, scheme_account=a))

    def test_diagnostic_detects_missing_linked_benefit_and_real_gate_stays_closed(self):
        a = self.benefit_account(metal=True, kind="VA_DISCOUNT")
        self.cash(a)
        request = self.accepted(a)
        _, token = self.prepared(request)
        params = self.settlement_values(request, token)
        for enabled in (False, True):
            with override_settings(CONFIGURED_PLANS_ENABLED=enabled), self.assertRaises(ValidationError):
                settle_configured_agreement(**params)
        r = self.settle(params)
        # Synthetic privileged corruption; no supported service deletes these records.
        BenefitInvoiceFulfilment.objects.all().delete()
        with self.assertRaises(ValidationError):
            validate_independent_settlement_benefit(r.configured_settlement)
        with self.assertRaises(CommandError):
            call_command("check_scheme_closures", stdout=StringIO())


@override_settings(IN_STORE_CASH_CONTRIBUTIONS_ENABLED=True, PAYMENT_INITIATION_KILL_SWITCH=False)
class IndependentMetalConcurrencyTests(MetalClosureFixture, TransactionTestCase):
    def test_concurrent_settlement_retries_retain_one_complete_lifecycle(self):
        a = self.benefit_account(metal=True, kind="VA_DISCOUNT")
        self.cash(a)
        request = self.accepted(a)
        _, token = self.prepared(request)
        params, barrier = self.settlement_values(request, token), Barrier(2)
        def apply():
            try:
                barrier.wait(timeout=10)
                return settle_configured_agreement(**params).pk
            finally:
                connections.close_all()
        with future_award_readiness(), ThreadPoolExecutor(max_workers=2) as pool:
            ids = list(pool.map(lambda _: apply(), range(2)))
        self.assertEqual(ids[0], ids[1])
        for model in (Redemption, ConfiguredSettlement, SchemeBenefitAward, BenefitInvoiceFulfilment):
            self.assertEqual(model.objects.count(), 1)

    def test_concurrent_full_return_retries_restore_principal_once(self):
        a = self.benefit_account(metal=True, kind="VA_DISCOUNT")
        self.cash(a)
        request = self.accepted(a)
        _, token = self.prepared(request)
        r = self.settle(self.settlement_values(request, token))
        params, barrier = self.reversal_values(r), Barrier(2)
        def apply():
            try:
                barrier.wait(timeout=10)
                return reverse_configured_settlement(**params).pk
            finally:
                connections.close_all()
        with future_award_readiness(), ThreadPoolExecutor(max_workers=2) as pool:
            ids = list(pool.map(lambda _: apply(), range(2)))
        self.assertEqual(ids[0], ids[1])
        for model in (RedemptionReversal, ConfiguredSettlementReversal, BenefitInvoiceReversal):
            self.assertEqual(model.objects.count(), 1)
        self.assertEqual(get_metal_balance(a), Decimal("0.050000"))
