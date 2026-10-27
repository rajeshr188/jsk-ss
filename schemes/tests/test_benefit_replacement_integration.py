"""Atomic replacement invoices on retained returned rights, not new awards."""
import uuid
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from io import StringIO
from threading import Barrier
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.core.management import call_command, CommandError
from django.db import connection, connections, IntegrityError, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase, override_settings

from schemes.benefit_application_selectors import application_history
from schemes.benefit_fulfilment_selectors import get_benefit_invoice_status
from schemes.benefit_reapplication_selectors import reapplication_review_status
from schemes.inr_settlements import record_inr_fulfilment
from schemes.models import (BenefitInvoiceFulfilment, BenefitInvoiceReversal, SchemeBenefitAward,
    BenefitReapplicationDecision, Contribution, InrPrincipalReceipt, MetalAllocation)
from schemes.selectors import get_metal_balance
from schemes.settlements import preview_full_settlement, settle_configured_agreement
from schemes.tests.test_benefit_awards import future_award_readiness
from schemes.tests.test_benefit_reapplications import ReapplicationFixture
from schemes.tests.test_independent_metal_settlement import MetalClosureFixture


class IntegrationFixture(ReapplicationFixture):
    def approve(self, a, reversal):
        return self.decide(self.review_values(a, self.review_preview(a, reversal)))

    def replacement_inr(self, a, r, kind="INR_PURCHASE_BONUS"):
        _, token = self.prepare(r, "360" if kind == "INR_PURCHASE_BONUS" else "380", invoice=self.invoice(kind))
        return self.propose(self.fresh(r, token))

    def metal_values(self, r, *, charges="200.00"):
        invoice = MetalClosureFixture.invoice(self) | dict(eligible_charges=Decimal(charges))
        with future_award_readiness():
            proof, token = preview_full_settlement(request_id=r.pk, actor=self.owner, benefit_invoice=invoice)
        return proof, self.settlement_values(r, token, authorization_reference="New signed invoice " + uuid.uuid4().hex)


@override_settings(IN_STORE_CASH_CONTRIBUTIONS_ENABLED=True, PAYMENT_INITIATION_KILL_SWITCH=False)
class BenefitReplacementTests(IntegrationFixture, TestCase):
    def test_inr_bonus_and_va_repeated_complete_returns_reuse_one_award(self):
        for kind in ("INR_PURCHASE_BONUS", "VA_DISCOUNT"):
            a, r, reversal = self.returned_benefit(kind=kind)
            award = SchemeBenefitAward.objects.get(scheme_account=a)
            sources = [list(m.objects.values()) for m in (Contribution, InrPrincipalReceipt, MetalAllocation, SchemeBenefitAward)]
            for _ in range(2):
                previous = reversal.fulfilment
                decision = self.approve(a, reversal)
                p = self.replacement_inr(a, r, kind)
                self.assertFalse(hasattr(decision, "consumption"))
                self.complete(p)
                invoice = BenefitInvoiceFulfilment.objects.get(inr_fulfilment__proposal=p)
                self.assertEqual((invoice.previous_id, invoice.reapplication_decision_id), (previous.pk, decision.pk))
                self.assertEqual(reapplication_review_status(reversal), "CONSUMED")
                status = get_benefit_invoice_status(award)
                self.assertFalse(status.needs_review)
                self.assertEqual(status.fulfilled - status.reversed, invoice.benefit_amount)
                with self.assertRaises(ValidationError):
                    self.review_preview(a, reversal, "HOLD")
                self.return_all(p)
                reversal = BenefitInvoiceReversal.objects.get(fulfilment=invoice)
                with self.assertRaises(ValidationError):
                    self.replacement_inr(a, r, kind)
            self.assertEqual(len(application_history(award)), 3)
            self.assertEqual(sources, [list(m.objects.values()) for m in (Contribution, InrPrincipalReceipt, MetalAllocation, SchemeBenefitAward)])
            self.approve(a, reversal)
            self.complete(self.replacement_inr(a, r, kind))
        for command in ("check_benefit_awards", "check_benefit_reapplications", "check_scheme_closures"):
            call_command(command, stdout=StringIO())

    def test_metal_va_replacement_recalculates_invoice_charge_under_same_cap(self):
        a, r, reversal = self.returned_benefit(kind="VA_DISCOUNT", metal=True)
        award = SchemeBenefitAward.objects.get(scheme_account=a)
        before = SchemeBenefitAward.objects.values().get(pk=award.pk)
        for charges in ("400.00", "100.00"):
            decision = self.approve(a, reversal)
            proof, values = self.metal_values(r, charges=charges)
            s = self.settle(values)
            self.assertEqual(self.settle(values).pk, s.pk)
            f = BenefitInvoiceFulfilment.objects.get(metal_settlement=s.configured_settlement)
            self.assertEqual(f.reapplication_decision_id, decision.pk)
            self.assertEqual(f.benefit_amount, min(Decimal(charges) / 10, award.cap_inr))
            self.assertEqual(s.entitlement_amount, Decimal("0.050000"))
            self.assertEqual(get_metal_balance(a), 0)
            self.assertFalse(get_benefit_invoice_status(award).needs_review)
            self.reverse(self.reversal_values(s) | dict(expected_sequence=proof["sequence"] + 1,
                authorization_reference="New complete return " + uuid.uuid4().hex))
            reversal = BenefitInvoiceReversal.objects.get(fulfilment=f)
            self.assertEqual(get_metal_balance(a), Decimal("0.050000"))
        self.assertEqual(before, SchemeBenefitAward.objects.values().get(pk=award.pk))
        self.assertEqual(len(application_history(award)), 3)
        self.assertTrue(get_benefit_invoice_status(award).needs_review)
        call_command("check_scheme_closures", stdout=StringIO())

    def test_hold_after_inr_proposal_blocks_fulfilment_but_allows_void_and_new_review(self):
        a, r, reversal = self.returned_benefit()
        self.approve(a, reversal)
        p = self.replacement_inr(a, r)
        self.decide(self.review_values(a, self.review_preview(a, reversal, "HOLD")))
        with self.assertRaises(ValidationError):
            self.fulfil(self.handover_values(p))
        with self.assertRaises(ValidationError):
            self.refunds(p)
        self.assertFalse(p.fulfilments.exists())
        self.correction(p, kind="VOID")
        self.assertEqual(reapplication_review_status(reversal), "STALE")
        self.approve(a, reversal)
        self.complete(self.replacement_inr(a, r))
        self.assertEqual(reapplication_review_status(reversal), "CONSUMED")

    def test_changed_approval_or_closure_invalidates_signed_settlement(self):
        a, r, reversal = self.returned_benefit()
        self.approve(a, reversal)
        _, token = self.prepare(r, invoice=self.invoice())
        self.decide(self.review_values(a, self.review_preview(a, reversal, "HOLD")))
        with self.assertRaises(ValidationError):
            self.propose(self.fresh(r, token))
        self.approve(a, reversal)
        _, token = self.prepare(r, invoice=self.invoice())
        self.note(r)
        with self.assertRaises(ValidationError):
            self.propose(self.fresh(r, token))
        self.assertEqual(a.inr_settlements.count(), 1)

    def test_refund_only_return_after_hold_keeps_approval_unconsumed(self):
        a, r, reversal = self.returned_benefit()
        decision = self.approve(a, reversal)
        p = self.replacement_inr(a, r)
        self.refunds(p)
        self.decide(self.review_values(a, self.review_preview(a, reversal, "HOLD")))
        with self.assertRaises(ValidationError):
            self.fulfil(self.handover_values(p))
        self.return_all(p)
        self.assertFalse(BenefitInvoiceFulfilment.objects.filter(reapplication_decision=decision).exists())
        self.assertEqual(reapplication_review_status(reversal), "STALE")
        self.approve(a, reversal)
        self.complete(self.replacement_inr(a, r))
        self.assertEqual(BenefitInvoiceFulfilment.objects.filter(award__scheme_account=a).count(), 2)
        call_command("check_scheme_closures", stdout=StringIO())

    def test_invoice_insert_failure_rolls_back_principal_and_consumption_for_both_denominations(self):
        for metal in (False, True):
            a, r, reversal = self.returned_benefit(kind="VA_DISCOUNT" if metal else "INR_PURCHASE_BONUS", metal=metal)
            decision = self.approve(a, reversal)
            if metal:
                _, values = self.metal_values(r)
                action = lambda: self.settle(values)
            else:
                p = self.replacement_inr(a, r)
                values = self.handover_values(p)
                action = lambda: self.fulfil(values)
            original = BenefitInvoiceFulfilment.save
            def fail(row, *args, **kwargs):
                original(row, *args, **kwargs)
                raise ValidationError("Injected after replacement invoice")
            with patch.object(BenefitInvoiceFulfilment, "save", fail), self.assertRaises(ValidationError):
                action()
            self.assertFalse(BenefitInvoiceFulfilment.objects.filter(reapplication_decision=decision).exists())
            a.refresh_from_db()
            self.assertEqual(a.status, "CLOSURE_PENDING")
            if metal:
                self.assertEqual(a.redemptions.count(), 1)
                self.assertEqual(get_metal_balance(a), Decimal("0.050000"))
            else:
                self.assertFalse(p.fulfilments.exists())
            action()
            self.assertTrue(BenefitInvoiceFulfilment.objects.filter(reapplication_decision=decision).exists())

    def test_database_chain_constraints_and_missing_approval_diagnostics(self):
        a, r, reversal = self.returned_benefit()
        self.approve(a, reversal)
        p = self.replacement_inr(a, r)
        self.complete(p)
        f = BenefitInvoiceFulfilment.objects.get(inr_fulfilment__proposal=p)
        for changes in (dict(previous=None), dict(reapplication_decision=None),
                dict(previous=None, reapplication_decision=None)):
            with self.assertRaises(IntegrityError), transaction.atomic():
                BenefitInvoiceFulfilment.objects.filter(pk=f.pk).update(**changes)
        BenefitReapplicationDecision.objects.filter(pk=f.reapplication_decision_id).update(evidence_digest="0" * 64)
        with self.assertRaises(CommandError):
            call_command("check_benefit_awards", stdout=StringIO())
        with self.assertRaises(CommandError):
            call_command("check_benefit_reapplications", stdout=StringIO())


@override_settings(IN_STORE_CASH_CONTRIBUTIONS_ENABLED=True, PAYMENT_INITIATION_KILL_SWITCH=False)
class BenefitReplacementTransactionTests(IntegrationFixture, TransactionTestCase):
    def test_concurrent_handover_retry_consumes_review_once(self):
        a, r, reversal = self.returned_benefit()
        decision = self.approve(a, reversal)
        p = self.replacement_inr(a, r)
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
        self.assertEqual(BenefitInvoiceFulfilment.objects.filter(reapplication_decision=decision).count(), 1)

    def test_competing_metal_settlements_cannot_spend_returned_right_twice(self):
        a, r, reversal = self.returned_benefit(kind="VA_DISCOUNT", metal=True)
        decision = self.approve(a, reversal)
        values = [self.metal_values(r)[1] for _ in range(2)]
        barrier = Barrier(2)
        def run(index):
            try:
                barrier.wait(timeout=10)
                try:
                    return settle_configured_agreement(**values[index]).pk
                except ValidationError:
                    return None
            finally:
                connections.close_all()
        with future_award_readiness(), ThreadPoolExecutor(max_workers=2) as pool:
            ids = list(pool.map(run, range(2)))
        self.assertEqual(sum(pk is not None for pk in ids), 1)
        self.assertEqual(BenefitInvoiceFulfilment.objects.filter(reapplication_decision=decision).count(), 1)

    def test_empty_roundtrip_and_retained_original_proof_refuse_reapplication_rollback(self):
        from importlib import import_module
        from types import SimpleNamespace
        from django.apps import apps
        leaves = MigrationExecutor(connection).loader.graph.leaf_nodes()
        self.addCleanup(lambda: MigrationExecutor(connection).migrate(leaves))
        # Rehearse the empty schema round trip before creating protected history.
        # Current services must run with their complete schema, never an older one.
        MigrationExecutor(connection).migrate([("schemes", "0048_benefit_reapplication_decisions")])
        MigrationExecutor(connection).migrate(leaves)
        a, r, reversal = self.returned_benefit()
        original = reversal.fulfilment
        proof = original.evidence
        with self.assertRaisesMessage(RuntimeError, "Retain independent draft policies"):
            MigrationExecutor(connection).migrate([("schemes", "0048_benefit_reapplication_decisions")])
        MigrationExecutor(connection).migrate(leaves)
        # The earlier guard permits an original invoice, but forbids reapplication.
        import_module("schemes.migrations.0049_benefit_invoice_reapplication").guard_reverse(
            apps, SimpleNamespace(connection=connection))
        original.refresh_from_db()
        self.assertEqual(original.evidence, proof)
        self.assertIsNone(original.previous_id)
        self.approve(a, reversal)
        p = self.replacement_inr(a, r)
        with self.assertRaisesMessage(RuntimeError, "Retain independent draft policies and revisions"):
            MigrationExecutor(connection).migrate([("schemes", "0048_benefit_reapplication_decisions")])
        with self.assertRaisesMessage(RuntimeError, "Retain benefit reapplication"):
            import_module("schemes.migrations.0049_benefit_invoice_reapplication").guard_reverse(
                apps, SimpleNamespace(connection=connection))
        MigrationExecutor(connection).migrate(leaves)
        original.refresh_from_db()
        self.assertEqual(original.evidence, proof)
        self.complete(p)
        with self.assertRaisesMessage(RuntimeError, "Retain independent draft policies and revisions"):
            MigrationExecutor(connection).migrate([("schemes", "0048_benefit_reapplication_decisions")])
        with self.assertRaisesMessage(RuntimeError, "Retain benefit reapplication"):
            import_module("schemes.migrations.0049_benefit_invoice_reapplication").guard_reverse(
                apps, SimpleNamespace(connection=connection))
