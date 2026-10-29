"""Gated correction generations, never recurring withdrawals or benefit reset."""
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from io import StringIO
from threading import Barrier
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.core.management import call_command, CommandError
from django.db import connections
from django.test import TestCase, TransactionTestCase, override_settings

from schemes.agreement_eligibility import get_independent_eligibility
from schemes.inr_settlements import propose_inr_settlement, preview_inr_settlement
from schemes.inr_settlement_selectors import inr_settlement_balance
from schemes.models import (InrSettlementProposal, SchemeBenefitAward, BenefitInvoiceFulfilment,
    BenefitInvoiceReversal, ConfiguredSettlement, Contribution, InrPrincipalReceipt)
from schemes.selectors import get_metal_balance
from schemes.settlement_selectors import proof_digest
from schemes.tests.test_benefit_awards import future_award_readiness
from schemes.tests.test_independent_inr_settlement import InrClosureFixture
from schemes.tests.test_independent_metal_settlement import MetalClosureFixture
from schemes.tests.test_independent_instalment_ledger import NOW, source
from schemes.tests.test_inr_corrections import return_evidence
from schemes.tests import test_collection_matrix as collection


class ReplacementFixture(InrClosureFixture):
    def fresh(self, request, token, **changes):
        return self.proposal_values(request, token) | dict(
            authorization_reference="Signed replacement " + uuid.uuid4().hex) | changes

    def no_benefit(self, **changes):
        a = self.account(**changes)
        self.cash(a)
        r = self.accepted(a)
        _, token = self.prepare(r, "300")
        return a, r, self.propose(self.proposal_values(r, token))

    def complete(self, p):
        if p.principal_to_invoice:
            self.fulfil(self.handover_values(p))
        self.refunds(p)
        self.finish(p)

    def return_all(self, p):
        return self.correction(p, [return_evidence(f) for f in p.fulfilments.all()])


@override_settings(IN_STORE_CASH_CONTRIBUTIONS_ENABLED=True, PAYMENT_INITIATION_KILL_SWITCH=False)
class ReplacementSettlementTests(ReplacementFixture, TestCase):
    def test_void_chain_reuses_one_unconsumed_bonus_or_va_award(self):
        for kind, net in (("INR_PURCHASE_BONUS", "360"), ("VA_DISCOUNT", "380")):
            a = self.benefit_account(kind=kind)
            self.cash(a)
            r = self.accepted(a)
            _, token = self.prepare(r, net, invoice=self.invoice(kind))
            p = self.propose(self.proposal_values(r, token))
            award = SchemeBenefitAward.objects.values().get(scheme_account=a)
            originals = list(a.contributions.values())
            for _ in range(2):
                self.correction(p, kind="VOID")
                self.assertEqual(get_independent_eligibility(a).state, "CLOSURE_PENDING")
                _, token = self.prepare(r, net, invoice=self.invoice(kind))
                values = self.fresh(r, token)
                replacement = self.propose(values)
                self.assertEqual(self.propose(values).pk, replacement.pk)
                self.assertEqual(replacement.previous_id, p.pk)
                self.assertEqual(award, SchemeBenefitAward.objects.values().get(scheme_account=a))
                p = replacement
            self.complete(p)
            self.assertEqual(BenefitInvoiceFulfilment.objects.filter(award__scheme_account=a).count(), 1)
            self.assertEqual(inr_settlement_balance(a).outstanding, 0)
            self.assertEqual(originals, list(a.contributions.values()))
        call_command("check_inr_principal", stdout=StringIO())
        call_command("check_scheme_closures", stdout=StringIO())

    def test_unconsumed_award_survives_refund_only_return_before_handover(self):
        a, r, p = self.prepared_bonus()
        self.refunds(p)
        self.return_all(p)
        self.assertFalse(BenefitInvoiceFulfilment.objects.exists())
        _, token = self.prepare(r, invoice=self.invoice())
        p2 = self.propose(self.fresh(r, token))
        self.complete(p2)
        self.assertEqual(SchemeBenefitAward.objects.count(), 1)
        self.assertEqual(BenefitInvoiceFulfilment.objects.count(), 1)
        self.assertEqual(inr_settlement_balance(a).outstanding, 0)

    def test_principal_only_full_return_chain_before_and_after_completion(self):
        for completed in (False, True):
            a, r, p = self.no_benefit()
            self.fulfil(self.handover_values(p))
            if completed:
                self.refunds(p)
                self.finish(p)
            original = list(a.contributions.values())
            self.return_all(p)
            _, token = self.prepare(r, "500")
            p2 = self.propose(self.fresh(r, token))
            self.complete(p2)
            self.return_all(p2)
            _, token = self.prepare(r, "0")
            p3 = self.propose(self.fresh(r, token, invoice_reference=""))
            self.complete(p3)
            self.assertEqual([p.previous_id for p in a.inr_settlements.order_by("pk")], [None, p.pk, p2.pk])
            self.assertEqual(inr_settlement_balance(a).outstanding, 0)
            self.assertEqual(original, list(a.contributions.values()))
        self.assertFalse(SchemeBenefitAward.objects.exists())

    def test_fresh_authorization_invoice_and_owner_are_required_with_either_intake_flag(self):
        a, r, p = self.no_benefit()
        correction = self.correction(p, kind="VOID")
        _, token = self.prepare(r, "500")
        values = self.fresh(r, token)
        for changes in (
            dict(authorization_reference=p.authorization_reference.upper()),
            dict(authorization_reference=correction.event.authorization_reference),
            dict(invoice_reference=p.invoice_reference.lower()),
            dict(actor=self.customer.user), dict(preview_token=token + "bad"),
        ):
            with self.assertRaises(ValidationError):
                self.propose(values | changes)
        for enabled in (False, True):
            with override_settings(CONFIGURED_PLANS_ENABLED=enabled), self.assertRaises(ValidationError):
                propose_inr_settlement(**(values | {"actor": self.customer.user}))
        with patch("django.core.signing.time.time", return_value=time.time() + 601), self.assertRaises(ValidationError):
            propose_inr_settlement(**values)
        with self.assertRaises(ValidationError):
            preview_inr_settlement(request_id=r.pk, actor=self.owner, invoice_payable=Decimal("500"))
        self.assertEqual(a.inr_settlements.count(), 1)
        propose_inr_settlement(**values)

    def test_later_calendar_date_does_not_reearn_an_unearned_benefit(self):
        a = self.benefit_account(monthly=False, eligibility_policy="CALENDAR", duration_months=1)
        self.cash(a)
        r = self.accepted(a)
        _, token = self.prepare(r, "300")
        p = self.propose(self.proposal_values(r, token))
        self.assertEqual(p.basis, "EARLY")
        self.correction(p, kind="VOID")
        with patch("django.utils.timezone.now", return_value=NOW + timedelta(days=400)):
            with self.assertRaises(ValidationError):
                self.prepare(r, invoice=self.invoice())
            _, token = self.prepare(r, "500")
            p2 = self.propose(self.fresh(r, token))
            self.assertEqual(p2.basis, "EARLY")
            self.complete(p2)
        self.assertFalse(SchemeBenefitAward.objects.exists())

    def test_new_source_and_mutated_chain_block_replacement_without_erasing_history(self):
        a, r, p = self.no_benefit()
        self.correction(p, kind="VOID")
        _, token = self.prepare(r, "500")
        pending = source(a)
        with self.assertRaises(ValidationError):
            self.propose(self.fresh(r, token))
        self.assertTrue(Contribution.objects.filter(pk=pending.pk, status="PENDING").exists())
        b, s, q = self.no_benefit()
        self.correction(q, kind="VOID")
        _, token = self.prepare(s, "500")
        q2 = self.propose(self.fresh(s, token))
        # Privileged corruption fixture: a digest alone is not proof of a valid chain.
        bad = dict(q2.evidence)
        bad["independent"] = bad["independent"] | {"replacement_history": []}
        InrSettlementProposal.objects.filter(pk=q2.pk).update(evidence=bad, evidence_digest=proof_digest(bad))
        with self.assertRaises(ValidationError):
            self.fulfil(self.handover_values(q2))
        with self.assertRaises(CommandError):
            call_command("check_inr_principal", stdout=StringIO())

    def test_original_online_refund_capacity_is_not_reset_by_money_returned(self):
        a = self.account(allow_contributions_after_eligibility=True)
        self.cash(a)
        c = self.online(a)
        collection.CollectionMatrixTests.capture(self, c)
        r = self.accepted(a)
        _, token = self.prepare(r, "0")
        p = self.propose(self.proposal_values(r, token, reference=False))
        self.complete(p)
        self.return_all(p)
        self.assertEqual(inr_settlement_balance(a).outstanding, Decimal("1000"))
        with self.assertRaisesMessage(ValidationError, "refund capacity"):
            self.prepare(r, "500")
        # Full jewellery application needs no second provider refund or extra credit.
        _, token = self.prepare(r, "1000")
        p2 = self.propose(self.fresh(r, token))
        self.complete(p2)
        self.assertEqual(InrPrincipalReceipt.objects.count(), 2)
        self.assertEqual(Contribution.objects.count(), 2)

    def test_consumed_and_returned_benefit_remains_held(self):
        a, r, p = self.prepared_bonus()
        self.complete(p)
        self.return_all(p)
        before = (SchemeBenefitAward.objects.count(), BenefitInvoiceFulfilment.objects.count(), BenefitInvoiceReversal.objects.count())
        with self.assertRaisesMessage(ValidationError, "reapplication"):
            self.prepare(r, invoice=self.invoice())
        self.assertEqual(before, (1, 1, 1))
        self.assertEqual(inr_settlement_balance(a).outstanding, Decimal("500"))

    def test_replacement_insert_failure_preserves_retired_predecessor_and_award(self):
        a, r, p = self.prepared_bonus()
        self.correction(p, kind="VOID")
        _, token = self.prepare(r, invoice=self.invoice())
        values = self.fresh(r, token)
        create = InrSettlementProposal.objects.create
        def fail(**kwargs):
            create(**kwargs)
            raise ValidationError("Injected after replacement insert")
        with patch("schemes.inr_settlements.InrSettlementProposal.objects.create", side_effect=fail), self.assertRaises(ValidationError):
            self.propose(values)
        self.assertEqual(a.inr_settlements.count(), 1)
        self.assertTrue(InrSettlementProposal.objects.get(pk=p.pk).retired)
        self.assertEqual(SchemeBenefitAward.objects.count(), 1)
        self.assertEqual(inr_settlement_balance(a).outstanding, Decimal("500"))
        self.propose(values)


@override_settings(IN_STORE_CASH_CONTRIBUTIONS_ENABLED=True, PAYMENT_INITIATION_KILL_SWITCH=False)
class MetalReplacementTests(MetalClosureFixture, TestCase):
    def test_missing_retained_root_sources_are_a_validation_hold(self):
        a = self.account(metal=True)
        self.cash(a)
        r = self.accepted(a)
        _, token = self.prepared(r, benefit=False)
        s = self.settle(self.settlement_values(r, token))
        self.reverse(self.reversal_values(s, benefit=False))
        retained = s.configured_settlement
        proof = dict(retained.evidence)
        proof["independent"] = {k: v for k, v in proof["independent"].items() if k != "sources"}
        ConfiguredSettlement.objects.filter(pk=retained.pk).update(evidence=proof, evidence_digest=proof_digest(proof))
        with self.assertRaises(ValidationError):
            self.prepared(r, benefit=False)

    def test_complete_return_chain_preserves_exact_grade_and_full_quantity(self):
        for monthly in (False, True):
            a = self.account(monthly=monthly, metal=True, **({"required_count": 1} if monthly else {}))
            self.cash(a)
            r = self.accepted(a)
            original = list(a.contributions.values())
            for generation in range(3):
                proof, token = self.prepared(r, benefit=False)
                values = self.settlement_values(r, token,
                    authorization_reference=f"Customer exact replacement {generation}")
                s = self.settle(values)
                self.assertEqual(self.settle(values).pk, s.pk)
                self.assertEqual((s.gold_quantity, s.metal_grade_id), (Decimal("0.050000"), a.metal_grade_id))
                self.assertEqual(len(proof["redemptions"]), generation)
                self.assertEqual(get_metal_balance(a), 0)
                if generation < 2:
                    self.reverse(self.reversal_values(s, benefit=False) | {"expected_sequence": proof["sequence"] + 1})
                    self.assertEqual(get_metal_balance(a), Decimal("0.050000"))
                    self.assertEqual(get_independent_eligibility(a).state, "CLOSURE_PENDING")
            self.assertEqual(original, list(a.contributions.values()))
        call_command("check_scheme_closures", stdout=StringIO())

    def test_consumed_metal_benefit_still_blocks_automatic_replacement(self):
        a = self.benefit_account(metal=True, kind="VA_DISCOUNT")
        self.cash(a)
        r = self.accepted(a)
        _, token = self.prepared(r)
        s = self.settle(self.settlement_values(r, token))
        self.reverse(self.reversal_values(s))
        with self.assertRaisesMessage(ValidationError, "reapplication"):
            self.prepared(r)
        self.assertEqual(get_metal_balance(a), Decimal("0.050000"))


@override_settings(IN_STORE_CASH_CONTRIBUTIONS_ENABLED=True, PAYMENT_INITIATION_KILL_SWITCH=False)
class ReplacementConcurrencyTests(ReplacementFixture, TransactionTestCase):
    def test_competing_distinct_requests_cannot_fork_the_disposition_chain(self):
        a, r, p = self.no_benefit()
        self.correction(p, kind="VOID")
        _, token = self.prepare(r, "500")
        values = [self.fresh(r, token), self.fresh(r, token)]
        barrier = Barrier(2)
        def run(index):
            try:
                barrier.wait(timeout=10)
                try:
                    return propose_inr_settlement(**values[index]).pk
                except ValidationError:
                    return None
            finally:
                connections.close_all()
        with future_award_readiness(), ThreadPoolExecutor(max_workers=2) as pool:
            ids = list(pool.map(run, range(2)))
        self.assertEqual(sum(pk is not None for pk in ids), 1)
        self.assertEqual(InrSettlementProposal.objects.filter(previous=p).count(), 1)
        self.assertEqual(inr_settlement_balance(a).outstanding, Decimal("500"))

    def test_concurrent_replacement_retries_create_one_successor_and_one_award(self):
        a, r, p = self.prepared_bonus()
        self.correction(p, kind="VOID")
        _, token = self.prepare(r, invoice=self.invoice())
        values = self.fresh(r, token)
        barrier = Barrier(2)
        def run():
            try:
                barrier.wait(timeout=10)
                return propose_inr_settlement(**values).pk
            finally:
                connections.close_all()
        with future_award_readiness(), ThreadPoolExecutor(max_workers=2) as pool:
            ids = list(pool.map(lambda _: run(), range(2)))
        self.assertEqual(ids[0], ids[1])
        self.assertEqual(InrSettlementProposal.objects.filter(previous=p).count(), 1)
        self.assertEqual(SchemeBenefitAward.objects.count(), 1)
