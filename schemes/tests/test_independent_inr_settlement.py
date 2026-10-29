"""Real independent INR disposition/benefit services on gated synthetic contracts."""
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
from django.utils import timezone

from schemes.independent_inr_settlement_selectors import validate_independent_inr_benefit
from schemes.inr_settlements import (preview_independent_inr_settlement, preview_inr_settlement,
    propose_inr_settlement, record_inr_fulfilment, complete_inr_settlement)
from schemes.inr_settlement_selectors import inr_settlement_balance
from schemes.models import (InrSettlementProposal, InrSettlementFulfilment, InrSettlementCompletion,
    InrSettlementResolution, InrFulfilmentReturn, SchemeBenefitAward, BenefitInvoiceFulfilment,
    BenefitInvoiceReversal, Contribution, InrPrincipalReceipt)
from schemes.tests.test_independent_metal_settlement import MetalClosureFixture
from schemes.tests.test_benefit_awards import future_award_readiness
from schemes.tests.test_independent_instalment_ledger import NOW, source
from schemes.tests.test_independent_instalment_reviews import instant
from schemes.tests.test_inr_corrections import resolve, return_evidence


class InrClosureFixture(MetalClosureFixture):
    def invoice(self, kind="INR_PURCHASE_BONUS", gross="400.00"):
        return dict(invoice_before_benefit=Decimal(gross),
            eligible_charges=Decimal("200.00") if kind == "VA_DISCOUNT" else None,
            invoice_evidence_reference="Retained itemised final invoice",
            eligible_charge_reference="Making charges excluding tax" if kind == "VA_DISCOUNT" else "")

    def prepare(self, request, net="360.00", *, invoice=None):
        with future_award_readiness():
            return preview_independent_inr_settlement(request_id=request.pk, actor=self.owner,
                invoice_payable=Decimal(net), benefit_invoice=invoice)

    def proposal_values(self, request, token, *, reference=True):
        return dict(request_id=request.pk, actor=self.owner, preview_token=token,
            invoice_reference="INV-" + uuid.uuid4().hex if reference else "",
            authorization_reference="Customer signed the complete net invoice/refund split",
            reason="Manual final disposition agreed", idempotency_key=uuid.uuid4())

    def propose(self, values):
        with future_award_readiness():
            return propose_inr_settlement(**values)

    def handover_values(self, p):
        return dict(proposal_id=p.pk, actor=self.owner, kind="JEWELLERY", method="SHOWROOM",
            external_reference=p.invoice_reference, customer_receipt_reference="Actual signed jewellery receipt",
            fulfilled_at=timezone.now(), reason="Jewellery handed over", idempotency_key=uuid.uuid4(),
            top_up_reference="External top-up receipt" if p.separate_top_up else "")

    def fulfil(self, values):
        with future_award_readiness():
            return record_inr_fulfilment(**values)

    def refunds(self, p):
        for leg in p.evidence["refunds"]:
            self.fulfil(dict(proposal_id=p.pk, actor=self.owner, kind="REFUND", method=leg["method"],
                receipt_id=leg["receipt"], external_reference="REF-" + uuid.uuid4().hex,
                customer_receipt_reference="Customer received original-source refund",
                fulfilled_at=timezone.now(), reason="Refund completed", idempotency_key=uuid.uuid4()))

    def finish(self, p, *, key=None):
        with future_award_readiness():
            return complete_inr_settlement(proposal_id=p.pk, actor=self.owner,
                reason="All legs reconciled", idempotency_key=key or uuid.uuid4())

    def correction(self, p, rows=(), **kwargs):
        with future_award_readiness():
            return resolve(p, self.owner, rows, **kwargs)

    def prepared_bonus(self, **changes):
        a = self.benefit_account(**changes)
        self.cash(a)
        request = self.accepted(a)
        _, token = self.prepare(request, invoice=self.invoice())
        p = self.propose(self.proposal_values(request, token))
        return a, request, p


@override_settings(IN_STORE_CASH_CONTRIBUTIONS_ENABLED=True, PAYMENT_INITIATION_KILL_SWITCH=False)
class IndependentInrSettlementTests(InrClosureFixture, TestCase):
    def test_five_family_bonus_and_va_matrix_separates_proposal_handover_refund_closure(self):
        for kind, net in (("INR_PURCHASE_BONUS", "360.00"), ("VA_DISCOUNT", "380.00")):
            for family in ("anytime", "duration", "count", "both", "benefit_duration"):
                changes = {}
                if family in ("duration", "benefit_duration"):
                    changes.update(eligibility_policy="CALENDAR", duration_months=1)
                if family == "both":
                    changes.update(eligibility_policy="CALENDAR_AND_COUNT", duration_months=1)
                if family == "benefit_duration":
                    changes.update(missed_payment_policy="LOSE_UNEARNED_BENEFIT", max_extension_months=None,
                        benefit_on_miss="DISQUALIFY_UNEARNED")
                a = self.benefit_account(monthly=family not in ("anytime", "duration"), kind=kind, **changes)
                self.cash(a)
                at = instant(a.eligible_from) if a.eligible_from else NOW
                with patch("django.utils.timezone.now", return_value=at):
                    request = self.accepted(a)
                    before = list(a.contributions.values())
                    split, token = self.prepare(request, net, invoice=self.invoice(kind))
                    self.assertEqual(split.principal_refund, Decimal("500") - Decimal(net))
                    self.assertFalse(SchemeBenefitAward.objects.filter(scheme_account=a).exists())
                    params = self.proposal_values(request, token)
                    p = self.propose(params)
                    self.assertEqual(self.propose(params).pk, p.pk)
                    self.assertEqual(p.basis, "NORMAL")
                    self.assertEqual(inr_settlement_balance(a).outstanding, Decimal("500"))
                    self.assertFalse(p.fulfilments.exists())
                    with self.assertRaises(ValidationError):
                        self.finish(p)
                    values = self.handover_values(p)
                    f = self.fulfil(values)
                    self.assertEqual(self.fulfil(values).pk, f.pk)
                    benefit = BenefitInvoiceFulfilment.objects.get(inr_fulfilment=f)
                    self.assertEqual(benefit.invoice_after_benefit, Decimal(net))
                    self.assertEqual(benefit.customer_receipt_reference, values["customer_receipt_reference"])
                    self.assertEqual(inr_settlement_balance(a).refund_pending, p.principal_refund)
                    with self.assertRaises(ValidationError):
                        self.finish(p)
                    self.refunds(p)
                    key = uuid.uuid4()
                    completed = self.finish(p, key=key)
                    self.assertEqual(self.finish(p, key=key).pk, completed.pk)
                    a.refresh_from_db()
                    self.assertEqual(a.status, "REDEEMED")
                    self.assertEqual(inr_settlement_balance(a).outstanding, 0)
                    self.assertEqual(before, list(a.contributions.values()))
                    validate_independent_inr_benefit(p, current=True)

    def test_early_full_refund_has_no_unearned_bonus_or_fake_invoice(self):
        a = self.benefit_account(required_count=2)
        self.cash(a)
        r = self.accepted(a)
        _, token = self.prepare(r, "0")
        p = self.propose(self.proposal_values(r, token, reference=False))
        self.assertEqual(p.basis, "EARLY")
        self.assertFalse(SchemeBenefitAward.objects.exists())
        self.refunds(p)
        self.finish(p)
        self.assertFalse(BenefitInvoiceFulfilment.objects.exists())
        self.assertEqual(inr_settlement_balance(a).outstanding, 0)

    def test_anytime_and_count_without_benefit_have_no_invented_maturity(self):
        for monthly in (False, True):
            a = self.account(monthly=monthly, **({"required_count": 1} if monthly else {}))
            self.cash(a)
            r = self.accepted(a)
            _, token = self.prepare(r, "500")
            p = self.propose(self.proposal_values(r, token))
            self.assertEqual(p.basis, "NORMAL")
            self.assertIsNone(a.eligible_from)
            self.fulfil(self.handover_values(p))
            self.finish(p)
        self.assertFalse(SchemeBenefitAward.objects.exists())

    def test_small_invoice_net_mismatch_and_earned_all_refund_are_held(self):
        a = self.benefit_account()
        self.cash(a)
        r = self.accepted(a)
        for net, invoice in (("0", None), ("0", self.invoice(gross="20")),
                             ("400", self.invoice()), ("360", self.invoice() | {"eligible_charges": Decimal("1")})):
            with self.assertRaises(ValidationError):
                self.prepare(r, net, invoice=invoice)
        self.assertFalse(InrSettlementProposal.objects.exists())
        self.assertFalse(SchemeBenefitAward.objects.exists())

    def test_missed_benefit_month_does_not_forfeit_date_eligible_principal(self):
        for basis in ("CALENDAR_MONTH", "ANNIVERSARY"):
            a = self.benefit_account(period_basis=basis, eligibility_policy="CALENDAR",
                duration_months=1, required_count=2, missed_payment_policy="LOSE_UNEARNED_BENEFIT",
                max_extension_months=None, benefit_on_miss="DISQUALIFY_UNEARNED")
            self.cash(a)
            with patch("django.utils.timezone.now", return_value=instant(a.instalment_periods.get(number=2).ends_before)):
                r = self.accepted(a)
                _, token = self.prepare(r, "0")
                p = self.propose(self.proposal_values(r, token, reference=False))
                self.assertEqual(p.basis, "NORMAL")
                self.assertEqual(p.evidence["independent"]["qualification"]["state"], "UNQUALIFIED_MISS")
                self.refunds(p)
                self.finish(p)
                self.assertEqual(inr_settlement_balance(a).outstanding, 0)
        self.assertFalse(SchemeBenefitAward.objects.exists())

    def test_new_source_exposure_blocks_later_mutations_with_either_intake_flag(self):
        from schemes.inr_corrections import preview_inr_resolution
        a, r, p = self.prepared_bonus()
        values = self.handover_values(p)
        source(a)  # New unresolved exposure is a real hold, not an intake switch.
        for enabled in (False, True):
            with override_settings(CONFIGURED_PLANS_ENABLED=enabled):
                for action in (
                    lambda: record_inr_fulfilment(**values),
                    lambda: complete_inr_settlement(proposal_id=p.pk, actor=self.owner,
                        reason="Cannot bypass readiness", idempotency_key=uuid.uuid4()),
                    lambda: preview_inr_resolution(proposal_id=p.pk, actor=self.owner,
                        kind="VOID", return_evidence=[]),
                ):
                    with self.assertRaises(ValidationError):
                        action()
        retained_award = SchemeBenefitAward.objects.values().get(scheme_account=a)
        with self.assertRaises(ValidationError):
            self.fulfil(values)
        with self.assertRaises(ValidationError):
            self.correction(p, kind="VOID")
        self.assertFalse(p.fulfilments.exists())
        self.assertEqual(retained_award, SchemeBenefitAward.objects.values().get(scheme_account=a))

    def test_net_invoice_above_principal_requires_separate_topup_not_new_credit(self):
        a = self.benefit_account()
        self.cash(a)
        r = self.accepted(a)
        _, token = self.prepare(r, "560", invoice=self.invoice(gross="600"))
        p = self.propose(self.proposal_values(r, token))
        self.assertEqual(p.separate_top_up, Decimal("60"))
        values = self.handover_values(p)
        with self.assertRaises(ValidationError):
            self.fulfil(values | {"top_up_reference": ""})
        self.fulfil(values)
        self.finish(p)
        self.assertEqual(Contribution.objects.count(), 1)
        self.assertEqual(InrPrincipalReceipt.objects.get().amount, Decimal("500"))

    def test_existing_award_is_reused_and_live_refund_cannot_be_cash_substituted(self):
        a = self.benefit_account(monthly=False, allow_contributions_after_eligibility=True)
        self.cash(a)
        c = self.online(a)
        from schemes.tests.test_collection_matrix import CollectionMatrixTests
        CollectionMatrixTests.capture(self, c)
        receipt = InrPrincipalReceipt.objects.get(contribution=c)
        award = self.record(a, self.preview(a))
        original = SchemeBenefitAward.objects.values().get(pk=award.pk)
        r = self.accepted(a)
        _, token = self.prepare(r, "500", invoice=self.invoice(gross="540"))
        p = self.propose(self.proposal_values(r, token))
        self.assertEqual(p.evidence["refunds"], [dict(receipt=receipt.pk, amount="500.00", method="PROVIDER_DASHBOARD")])
        self.assertEqual(original, SchemeBenefitAward.objects.values().get(pk=award.pk))
        with self.assertRaises(ValidationError):
            self.fulfil(dict(proposal_id=p.pk, actor=self.owner, kind="REFUND", method="CASH_RETURN",
                receipt_id=receipt.pk, external_reference="INVALID-CASH", customer_receipt_reference="Not source first",
                fulfilled_at=NOW, reason="Must refuse", idempotency_key=uuid.uuid4()))
        self.refunds(p)  # Refund-first still does not consume a benefit or close.
        self.assertFalse(BenefitInvoiceFulfilment.objects.exists())
        with self.assertRaises(ValidationError):
            self.finish(p)
        self.fulfil(self.handover_values(p))
        self.finish(p)

    def test_award_proposal_and_handover_benefit_failures_roll_back_together(self):
        a = self.benefit_account()
        self.cash(a)
        r = self.accepted(a)
        _, token = self.prepare(r, invoice=self.invoice())
        params = self.proposal_values(r, token)
        create = InrSettlementProposal.objects.create
        def fail_proposal(**kwargs):
            create(**kwargs)
            raise ValidationError("Injected after proposal")
        with patch("schemes.inr_settlements.InrSettlementProposal.objects.create", side_effect=fail_proposal), self.assertRaises(ValidationError):
            self.propose(params)
        self.assertFalse(SchemeBenefitAward.objects.exists())
        self.assertFalse(InrSettlementProposal.objects.exists())
        p = self.propose(params)
        from schemes.benefit_fulfilments import record_benefit_fulfilment
        def fail_invoice(**kwargs):
            record_benefit_fulfilment(**kwargs)
            raise ValidationError("Injected after invoice")
        values = self.handover_values(p)
        with patch("schemes.benefit_fulfilments.record_benefit_fulfilment", side_effect=fail_invoice), self.assertRaises(ValidationError):
            self.fulfil(values)
        self.assertFalse(InrSettlementFulfilment.objects.exists())
        self.assertFalse(BenefitInvoiceFulfilment.objects.exists())
        self.assertEqual(inr_settlement_balance(a).outstanding, Decimal("500"))
        self.fulfil(values)

    def test_complete_and_pending_full_returns_reverse_consumed_benefit_atomically(self):
        for completed in (False, True):
            a, r, p = self.prepared_bonus()
            f = self.fulfil(self.handover_values(p))
            if completed:
                self.refunds(p)
                self.finish(p)
            rows = [return_evidence(f) for f in p.fulfilments.all()]
            from schemes.benefit_fulfilments import reverse_benefit_fulfilment
            def fail(**kwargs):
                reverse_benefit_fulfilment(**kwargs)
                raise ValidationError("Injected post-return failure")
            with patch("schemes.benefit_fulfilments.reverse_benefit_fulfilment", side_effect=fail), self.assertRaises(ValidationError):
                self.correction(p, rows)
            self.assertFalse(InrSettlementResolution.objects.filter(proposal=p).exists())
            self.assertFalse(InrFulfilmentReturn.objects.filter(fulfilment__proposal=p).exists())
            result = self.correction(p, rows)
            self.assertEqual(BenefitInvoiceReversal.objects.get(fulfilment__inr_fulfilment=f).inr_return.resolution_id, result.pk)
            self.assertEqual(inr_settlement_balance(a).outstanding, Decimal("500"))
            a.refresh_from_db()
            self.assertEqual(a.status, "CLOSURE_PENDING")
            for prepare in (self.prepare, lambda r: preview_inr_settlement(request_id=r.pk, actor=self.owner, invoice_payable=Decimal("500"))):
                with self.assertRaises(ValidationError):
                    prepare(r)
            validate_independent_inr_benefit(InrSettlementProposal.objects.get(pk=p.pk))

    def test_void_retains_unconsumed_right_and_never_creates_fulfilment(self):
        a, r, p = self.prepared_bonus()
        self.correction(p, kind="VOID")
        self.assertTrue(SchemeBenefitAward.objects.filter(scheme_account=a).exists())
        self.assertFalse(BenefitInvoiceFulfilment.objects.exists())
        self.assertEqual(inr_settlement_balance(a).outstanding, Decimal("500"))
        _, token = self.prepare(r, invoice=self.invoice())
        with self.assertRaises(ValidationError):  # Prior authorization cannot be recycled.
            self.propose(self.proposal_values(r, token))

    def test_authority_expiry_and_stale_sources_fail_closed_regardless_of_intake(self):
        a = self.benefit_account()
        self.cash(a)
        r = self.accepted(a)
        _, token = self.prepare(r, invoice=self.invoice())
        values = self.proposal_values(r, token)
        for enabled in (False, True):
            with override_settings(CONFIGURED_PLANS_ENABLED=enabled), self.assertRaises(ValidationError):
                propose_inr_settlement(**(values | {"actor": self.customer.user}))
        for changes in (dict(actor=self.customer.user), dict(preview_token=token + "tampered")):
            with self.assertRaises(ValidationError):
                self.propose(values | changes)
        with patch("django.core.signing.time.time", return_value=time.time() + 601), self.assertRaises(ValidationError):
            self.propose(values)
        source(a)  # Synthetic pending exposure discovered after preview.
        with self.assertRaises(ValidationError):
            self.propose(values)
        self.assertFalse(InrSettlementProposal.objects.exists())

    def test_missing_benefit_invoice_blocks_completion_and_diagnostic(self):
        a, r, p = self.prepared_bonus()
        self.fulfil(self.handover_values(p))
        self.refunds(p)
        BenefitInvoiceFulfilment.objects.all().delete()  # Privileged corruption fixture only.
        with self.assertRaises(ValidationError):
            self.finish(p)
        with self.assertRaises(CommandError):
            call_command("check_inr_principal", stdout=StringIO())
        with self.assertRaises(CommandError):
            call_command("check_scheme_closures", stdout=StringIO())


@override_settings(IN_STORE_CASH_CONTRIBUTIONS_ENABLED=True, PAYMENT_INITIATION_KILL_SWITCH=False)
class IndependentInrConcurrencyTests(InrClosureFixture, TransactionTestCase):
    def test_concurrent_proposal_and_full_return_retries_retain_one_benefit_lifecycle(self):
        from schemes.inr_corrections import preview_inr_resolution, resolve_inr_settlement
        a = self.benefit_account()
        self.cash(a)
        r = self.accepted(a)
        _, token = self.prepare(r, invoice=self.invoice())
        values = self.proposal_values(r, token)
        barrier = Barrier(2)
        def propose():
            try:
                barrier.wait(timeout=10)
                return propose_inr_settlement(**values).pk
            finally:
                connections.close_all()
        with future_award_readiness(), ThreadPoolExecutor(max_workers=2) as pool:
            ids = list(pool.map(lambda _: propose(), range(2)))
        self.assertEqual(ids[0], ids[1])
        self.assertEqual(SchemeBenefitAward.objects.count(), 1)
        self.assertEqual(InrSettlementProposal.objects.count(), 1)
        p = InrSettlementProposal.objects.get(pk=ids[0])
        f = self.fulfil(self.handover_values(p))
        rows = [return_evidence(f)]
        with future_award_readiness():
            token = preview_inr_resolution(proposal_id=p.pk, actor=self.owner, kind="FULL_RETURN", return_evidence=rows)
        values = dict(proposal_id=p.pk, actor=self.owner, kind="FULL_RETURN", return_evidence=rows,
            preview_token=token, authorization_reference="Signed complete return", reason="Actual return reconciled",
            idempotency_key=uuid.uuid4())
        barrier = Barrier(2)
        def reverse():
            try:
                barrier.wait(timeout=10)
                return resolve_inr_settlement(**values).pk
            finally:
                connections.close_all()
        with future_award_readiness(), ThreadPoolExecutor(max_workers=2) as pool:
            ids = list(pool.map(lambda _: reverse(), range(2)))
        self.assertEqual(ids[0], ids[1])
        self.assertEqual(InrSettlementResolution.objects.count(), 1)
        self.assertEqual(BenefitInvoiceReversal.objects.count(), 1)
        self.assertEqual(inr_settlement_balance(a).outstanding, Decimal("500"))

    def test_concurrent_handover_and_completion_retries_do_not_duplicate_discharge(self):
        a, r, p = self.prepared_bonus()
        values = self.handover_values(p)
        barrier = Barrier(2)
        def run():
            try:
                barrier.wait(timeout=10)
                return record_inr_fulfilment(**values).pk
            finally:
                connections.close_all()
        with future_award_readiness(), ThreadPoolExecutor(max_workers=2) as pool:
            ids = list(pool.map(lambda _: run(), range(2)))
        self.assertEqual(ids[0], ids[1])
        self.assertEqual(BenefitInvoiceFulfilment.objects.count(), 1)
        self.assertEqual(InrSettlementFulfilment.objects.count(), 1)
        self.refunds(p)
        key, barrier = uuid.uuid4(), Barrier(2)
        def finish():
            try:
                barrier.wait(timeout=10)
                return complete_inr_settlement(proposal_id=p.pk, actor=self.owner,
                    reason="All legs reconciled", idempotency_key=key).pk
            finally:
                connections.close_all()
        with future_award_readiness(), ThreadPoolExecutor(max_workers=2) as pool:
            ids = list(pool.map(lambda _: finish(), range(2)))
        self.assertEqual(ids[0], ids[1])
        self.assertEqual(InrSettlementCompletion.objects.count(), 1)
        self.assertEqual(inr_settlement_balance(a).outstanding, 0)
