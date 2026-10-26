"""Review returned rights through real settlement services; no activation or spend."""
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from io import StringIO
from threading import Barrier
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.core.management import call_command, CommandError
from django.db import connection, connections, IntegrityError, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase, override_settings

from schemes.benefit_reapplications import preview_benefit_reapplication, record_benefit_reapplication
from schemes.benefit_reapplication_selectors import decision_history, reapplication_review_status
from schemes.closures import review_scheme_closure
from schemes.models import (BenefitReapplicationDecision, BenefitInvoiceReversal, BenefitInvoiceFulfilment,
    SchemeBenefitAward, SchemeAccount, Contribution, MetalAllocation, InrPrincipalReceipt)
from schemes.settlements import preview_full_settlement
from schemes.tests.test_benefit_awards import future_award_readiness
from schemes.tests.test_replacement_settlements import ReplacementFixture
from schemes.tests.test_independent_metal_settlement import MetalClosureFixture


class ReapplicationFixture(ReplacementFixture):
    def returned_benefit(self, *, kind="INR_PURCHASE_BONUS", metal=False):
        a = self.benefit_account(kind=kind, metal=metal)
        self.cash(a)
        r = self.accepted(a)
        if metal:
            with future_award_readiness():
                _, token = preview_full_settlement(request_id=r.pk, actor=self.owner,
                    benefit_invoice=MetalClosureFixture.invoice(self))
            s = self.settle(self.settlement_values(r, token))
            self.reverse(self.reversal_values(s))
        else:
            _, token = self.prepare(r, "360" if kind == "INR_PURCHASE_BONUS" else "380", invoice=self.invoice(kind))
            p = self.propose(self.proposal_values(r, token))
            self.complete(p)
            self.return_all(p)
        return a, r, BenefitInvoiceReversal.objects.get(fulfilment__award__scheme_account=a)

    def review_preview(self, a, reversal, outcome="APPROVE", **changes):
        values = dict(account_id=a.pk, reversal_id=reversal.pk, actor=self.owner, outcome=outcome,
            authorization_reference="Signed returned-benefit review " + uuid.uuid4().hex if outcome == "APPROVE" else "") | changes
        with future_award_readiness():
            return preview_benefit_reapplication(**values)

    def review_values(self, a, token, **changes):
        return dict(account_id=a.pk, actor=self.owner, preview_token=token,
            reason="Check full goods/money return and retained contractual benefit", idempotency_key=uuid.uuid4()) | changes

    def decide(self, values):
        with future_award_readiness():
            return record_benefit_reapplication(**values)

    def note(self, r):
        with future_award_readiness():
            return review_scheme_closure(request_id=r.pk, actor=self.owner, action="NOTE",
                reason="New customer contact requires a fresh review", expected_sequence=r.events.count(),
                idempotency_key=uuid.uuid4())


@override_settings(IN_STORE_CASH_CONTRIBUTIONS_ENABLED=True, PAYMENT_INITIATION_KILL_SWITCH=False)
class ReapplicationTests(ReapplicationFixture, TestCase):
    def test_review_matrix_preserves_award_principal_invoice_and_containment(self):
        for kind, metal in (("INR_PURCHASE_BONUS", False), ("VA_DISCOUNT", False), ("VA_DISCOUNT", True)):
            a, r, reversal = self.returned_benefit(kind=kind, metal=metal)
            models = (SchemeAccount, SchemeBenefitAward, BenefitInvoiceFulfilment, BenefitInvoiceReversal,
                Contribution, MetalAllocation, InrPrincipalReceipt)
            before = [list(m.objects.values()) for m in models]
            self.assertEqual(reapplication_review_status(reversal), "UNREVIEWED")
            first = self.decide(self.review_values(a, self.review_preview(a, reversal)))
            self.assertEqual(reapplication_review_status(reversal), "APPROVED_REVIEW")
            hold = self.decide(self.review_values(a, self.review_preview(a, reversal, "HOLD")))
            self.assertEqual(reapplication_review_status(reversal), "HELD")
            last = self.decide(self.review_values(a, self.review_preview(a, reversal)))
            self.assertEqual([row.outcome for row in decision_history(reversal)], ["APPROVE", "HOLD", "APPROVE"])
            self.assertEqual((hold.previous_id, last.previous_id), (first.pk, hold.pk))
            self.assertEqual(before, [list(m.objects.values()) for m in models])
            a.refresh_from_db()
            self.assertEqual(a.status, "CLOSURE_PENDING")
            # Review alone must not remove the existing consumption barrier.
            with self.assertRaisesMessage(ValidationError, "reapplication"):
                if metal:
                    with future_award_readiness():
                        preview_full_settlement(request_id=r.pk, actor=self.owner, benefit_invoice=MetalClosureFixture.invoice(self))
                else:
                    self.prepare(r, invoice=self.invoice())
        out = StringIO()
        call_command("check_benefit_reapplications", stdout=out)
        self.assertIn("approved_review=3", out.getvalue())
        self.assertIn("spending_enabled=false", out.getvalue())

    def test_signature_expiry_retries_and_old_approval_cannot_override_hold(self):
        a, _, reversal = self.returned_benefit()
        token = self.review_preview(a, reversal)
        with self.assertRaises(ValidationError):
            self.decide(self.review_values(a, token + "tamper"))
        with patch("django.core.signing.time.time", return_value=time.time() + 601), self.assertRaisesMessage(ValidationError, "expired"):
            self.decide(self.review_values(a, token))
        values = self.review_values(a, token)
        first = self.decide(values)
        self.assertEqual(self.decide(values).pk, first.pk)
        with self.assertRaises(ValidationError):
            self.decide(values | dict(reason="Different purpose"))
        with self.assertRaises(ValidationError):
            self.decide(self.review_values(a, token))
        self.decide(self.review_values(a, self.review_preview(a, reversal, "HOLD")))
        self.assertEqual(self.decide(values).pk, first.pk)
        self.assertEqual(reapplication_review_status(reversal), "HELD")

    def test_return_review_retains_void_predecessors_before_first_consumption(self):
        a, r, p = self.prepared_bonus()
        for _ in range(2):
            self.correction(p, kind="VOID")
            _, token = self.prepare(r, invoice=self.invoice())
            p = self.propose(self.fresh(r, token))
        self.complete(p)
        self.return_all(p)
        reversal = BenefitInvoiceReversal.objects.get(fulfilment__award__scheme_account=a)
        row = self.decide(self.review_values(a, self.review_preview(a, reversal)))
        self.assertEqual(len(row.evidence["basis"]["dispositions"]), 3)
        self.assertEqual(SchemeBenefitAward.objects.filter(scheme_account=a).count(), 1)
        self.assertEqual(BenefitInvoiceFulfilment.objects.filter(award__scheme_account=a).count(), 1)
        self.assertEqual(reapplication_review_status(reversal), "APPROVED_REVIEW")

    def test_preview_and_existing_review_become_stale_on_new_closure_evidence(self):
        a, r, reversal = self.returned_benefit()
        token = self.review_preview(a, reversal)
        first = self.decide(self.review_values(a, token))
        stale = self.review_preview(a, reversal, "HOLD")
        self.note(r)
        self.assertEqual(reapplication_review_status(reversal), "STALE")
        with self.assertRaises(CommandError):
            call_command("check_benefit_reapplications", stdout=StringIO())
        with self.assertRaises(ValidationError):
            self.decide(self.review_values(a, stale))
        last = self.decide(self.review_values(a, self.review_preview(a, reversal, "HOLD")))
        self.assertEqual(last.previous_id, first.pk)
        self.assertEqual(reapplication_review_status(reversal), "HELD")

    def test_owner_authority_is_reloaded_and_cross_account_review_is_rejected(self):
        a, _, reversal = self.returned_benefit()
        token = self.review_preview(a, reversal)
        for operation in (
            lambda: self.review_preview(a, reversal, actor=self.customer.user),
            lambda: self.decide(self.review_values(a, token, actor=self.customer.user)),
            lambda: self.review_preview(self.account(), reversal),
        ):
            with self.assertRaises(ValidationError):
                operation()
        type(self.owner).objects.filter(pk=self.owner.pk).update(is_active=False)
        with self.assertRaises(ValidationError):
            self.decide(self.review_values(a, token))
        self.assertFalse(BenefitReapplicationDecision.objects.exists())

    def test_fresh_authorization_and_outcome_shape(self):
        a, _, reversal = self.returned_benefit()
        old = reversal.fulfilment.inr_fulfilment.proposal.authorization_reference
        for ref in ("", "   ", old.upper(), reversal.customer_confirmation, reversal.fulfilment.customer_receipt_reference):
            with self.assertRaises(ValidationError):
                self.review_preview(a, reversal, authorization_reference=ref)
        for outcome in ("UNKNOWN", "approve"):
            with self.assertRaises(ValidationError):
                self.review_preview(a, reversal, outcome)
        with self.assertRaises(ValidationError):
            self.review_preview(a, reversal, "HOLD", authorization_reference="Pretend approved")
        ref = "Unique signed authorization"
        self.decide(self.review_values(a, self.review_preview(a, reversal, authorization_reference=ref)))
        with self.assertRaises(ValidationError):
            self.review_preview(a, reversal, authorization_reference=ref.upper())

    def test_changed_source_or_missing_full_return_evidence_cannot_be_approved(self):
        a, _, reversal = self.returned_benefit()
        token = self.review_preview(a, reversal)
        # Privileged corruption fixture: a truncated principal-return set is never a full return.
        actual = reversal.inr_return
        actual_type = type(actual)
        actual_type.objects.filter(pk=actual.pk).update(amount=actual.amount - 1)
        with self.assertRaises(ValidationError):
            self.decide(self.review_values(a, token))
        actual_type.objects.filter(pk=actual.pk).update(amount=actual.amount)
        Contribution.objects.filter(scheme_account=a).update(amount=501)
        with self.assertRaises(ValidationError):
            self.review_preview(a, reversal)
        with self.assertRaises(ValidationError):
            self.decide(self.review_values(a, token))
        self.assertFalse(BenefitReapplicationDecision.objects.exists())

    def test_immutable_model_constraints_and_corrupt_evidence_diagnostics(self):
        a, _, reversal = self.returned_benefit()
        row = self.decide(self.review_values(a, self.review_preview(a, reversal)))
        for changes in (dict(sequence=0), dict(sequence=2), dict(outcome="OTHER"),
                dict(authorization_reference=""), dict(actor_label=""), dict(reason="")):
            with self.assertRaises(IntegrityError), transaction.atomic():
                BenefitReapplicationDecision.objects.filter(pk=row.pk).update(**changes)
        for operation in (row.save, row.delete):
            with self.assertRaises(ValidationError):
                operation()
        duplicate = BenefitReapplicationDecision.objects.get(pk=row.pk)
        duplicate.pk, duplicate.idempotency_key = None, uuid.uuid4()
        with self.assertRaises(IntegrityError), transaction.atomic():
            BenefitReapplicationDecision.objects.bulk_create([duplicate])
        BenefitReapplicationDecision.objects.filter(pk=row.pk).update(evidence_digest="0" * 64)
        with self.assertRaises(CommandError):
            call_command("check_benefit_reapplications", stdout=StringIO())
        with self.assertRaises(ValidationError):
            self.review_preview(a, reversal, "HOLD")

    def test_insert_failure_rolls_back_without_erasing_prior_decision(self):
        a, _, reversal = self.returned_benefit()
        first = self.decide(self.review_values(a, self.review_preview(a, reversal)))
        values = self.review_values(a, self.review_preview(a, reversal, "HOLD"))
        save = BenefitReapplicationDecision.save
        def fail(row, *args, **kwargs):
            save(row, *args, **kwargs)
            raise ValidationError("Injected after decision insert")
        with patch.object(BenefitReapplicationDecision, "save", fail), self.assertRaises(ValidationError):
            self.decide(values)
        self.assertEqual(list(reversal.reapplication_decisions.values_list("pk", flat=True)), [first.pk])
        self.assertEqual(self.decide(values).outcome, "HOLD")

    def test_real_gate_remains_closed_even_if_flag_is_true(self):
        a, _, reversal = self.returned_benefit()
        token = self.review_preview(a, reversal)
        for flag in (False, True):
            with override_settings(CONFIGURED_PLANS_ENABLED=flag):
                with self.assertRaises(ValidationError):
                    preview_benefit_reapplication(account_id=a.pk, reversal_id=reversal.pk, actor=self.owner,
                        outcome="HOLD")
                with self.assertRaises(ValidationError):
                    record_benefit_reapplication(**self.review_values(a, token))
        self.assertFalse(BenefitReapplicationDecision.objects.exists())


@override_settings(IN_STORE_CASH_CONTRIBUTIONS_ENABLED=True, PAYMENT_INITIATION_KILL_SWITCH=False)
class ReapplicationTransactionTests(ReapplicationFixture, TransactionTestCase):
    def run_race(self, values):
        barrier = Barrier(2)
        def run(index):
            try:
                barrier.wait(timeout=10)
                try:
                    return record_benefit_reapplication(**values[index]).pk
                except ValidationError:
                    return None
            finally:
                connections.close_all()
        with future_award_readiness(), ThreadPoolExecutor(max_workers=2) as pool:
            return list(pool.map(run, range(2)))

    def test_competing_decisions_cannot_fork_review_history(self):
        a, _, reversal = self.returned_benefit()
        values = [self.review_values(a, self.review_preview(a, reversal, outcome)) for outcome in ("APPROVE", "HOLD")]
        ids = self.run_race(values)
        self.assertEqual(sum(pk is not None for pk in ids), 1)
        self.assertEqual(reversal.reapplication_decisions.count(), 1)

    def test_concurrent_retry_records_exactly_one_decision(self):
        a, _, reversal = self.returned_benefit()
        values = self.review_values(a, self.review_preview(a, reversal))
        ids = self.run_race([values, values])
        self.assertIsNotNone(ids[0])
        self.assertEqual(ids[0], ids[1])
        self.assertEqual(reversal.reapplication_decisions.count(), 1)

    def test_migration_reverse_refuses_existing_decisions(self):
        a, _, reversal = self.returned_benefit()
        row = self.decide(self.review_values(a, self.review_preview(a, reversal)))
        leaves = MigrationExecutor(connection).loader.graph.leaf_nodes()
        self.addCleanup(lambda: MigrationExecutor(connection).migrate(leaves))
        with self.assertRaisesMessage(RuntimeError, "Retain benefit reapplication"):
            MigrationExecutor(connection).migrate([("schemes", "0047_benefit_invoice_fulfilment")])
        self.assertTrue(BenefitReapplicationDecision.objects.filter(pk=row.pk).exists())

    def test_empty_migration_round_trip_retains_old_invoice_uniqueness(self):
        leaves = MigrationExecutor(connection).loader.graph.leaf_nodes()
        self.addCleanup(lambda: MigrationExecutor(connection).migrate(leaves))
        MigrationExecutor(connection).migrate([("schemes", "0047_benefit_invoice_fulfilment")])
        MigrationExecutor(connection).migrate(leaves)
        self.assertFalse(BenefitReapplicationDecision.objects.exists())
        self.assertTrue(BenefitInvoiceFulfilment._meta.get_field("award").one_to_one)
