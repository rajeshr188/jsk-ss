import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from io import StringIO
from threading import Barrier
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, connection, transaction, close_old_connections
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from schemes.closure_selectors import validate_closure_history, require_no_accepted_closure
from schemes.inr_corrections import preview_inr_resolution, resolve_inr_settlement
from schemes.inr_settlement_selectors import inr_settlement_balance, validate_inr_completion
from schemes.models import (InrSettlementResolution, InrFulfilmentReturn, InrSettlementProposal,
    InrSettlementFulfilment, Contribution)
from schemes.tests.test_inr_settlements import accepted_request, propose, fulfil, complete
from schemes.tests.test_inr_principal import future_contract, cash_source, online_source, record
from schemes.tests.test_audit_exceptions import make_owner, make_customer


def return_evidence(f):
    jewellery = f.kind == "JEWELLERY"
    return dict(fulfilment_id=f.pk, method="GOODS_RETURN" if jewellery else "BANK_CREDIT",
        external_reference="RETURN-" + uuid.uuid4().hex, customer_confirmation="Signed receipt of full reversal",
        invoice_correction_reference="CREDIT-NOTE-" + uuid.uuid4().hex if jewellery else "",
        top_up_refund_reference="TOPUP-REFUND" if jewellery and f.proposal.separate_top_up else "",
        returned_at=timezone.now())


def resolve(p, owner, rows=(), kind="FULL_RETURN", token=None, key=None, **changes):
    if token is None:
        token = preview_inr_resolution(proposal_id=p.pk, actor=owner, kind=kind, return_evidence=rows)
    facts = dict(proposal_id=p.pk, actor=owner, kind=kind, return_evidence=rows, preview_token=token,
        authorization_reference="Customer signed correction/restored principal", reason="Actual return checked in showroom",
        idempotency_key=key or uuid.uuid4())
    facts.update(changes)
    return resolve_inr_settlement(**facts)


class InrCorrectionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner, cls.customer = make_owner(), make_customer()
        cls.account = future_contract(cls.owner, cls.customer)
        source, cash = cash_source(cls.account, cls.owner)
        cls.receipt = record(cls.owner, source, cash=cash)
        cls.request = accepted_request(cls.account, cls.owner)

    def assert_contained(self, outstanding=Decimal("1000")):
        self.account.refresh_from_db()
        self.request.refresh_from_db()
        self.assertEqual(self.account.status, "CLOSURE_PENDING")
        self.assertEqual(self.request.status, "ACCEPTED")
        self.assertEqual(inr_settlement_balance(self.account).outstanding, outstanding)
        validate_closure_history(self.request)
        with self.assertRaises(ValidationError):
            require_no_accepted_closure(self.account)
        call_command("check_inr_principal", stdout=StringIO())
        call_command("check_scheme_closures", stdout=StringIO())

    def test_void_unfulfilled_then_fresh_full_replacement(self):
        p = propose(self.request, self.owner)
        resolution = resolve(p, self.owner, kind="VOID")
        self.assertEqual(resolution.event.action, "NOTE")
        self.assertEqual(InrFulfilmentReturn.objects.count(), 0)
        self.assert_contained()
        replacement = propose(self.request, self.owner, Decimal("1000"))
        self.assertEqual(replacement.previous_id, p.pk)
        fulfil(replacement, self.owner)
        complete(replacement, self.owner)
        self.assertEqual(inr_settlement_balance(self.account).outstanding, 0)
        self.assertEqual(InrSettlementProposal.objects.count(), 2)

    def test_void_rejects_any_handover_or_completed_settlement(self):
        p = propose(self.request, self.owner, Decimal("1000"))
        fulfil(p, self.owner)
        with self.assertRaises(ValidationError):
            resolve(p, self.owner, kind="VOID")
        complete(p, self.owner)
        with self.assertRaises(ValidationError):
            resolve(p, self.owner, kind="VOID")
        self.assertEqual(InrSettlementResolution.objects.count(), 0)

    def test_pending_partial_fulfilment_return_restores_only_actual_debit(self):
        p = propose(self.request, self.owner)
        f = fulfil(p, self.owner)
        self.assertEqual(inr_settlement_balance(self.account).outstanding, Decimal("200"))
        resolution = resolve(p, self.owner, [return_evidence(f)])
        self.assertEqual(resolution.event.action, "NOTE")
        self.assertEqual(resolution.returns.get().amount, Decimal("800"))
        self.assert_contained()
        with self.assertRaises(ValidationError):
            fulfil(p, self.owner, "REFUND", self.receipt)
        with self.assertRaises(ValidationError):
            complete(p, self.owner)

    def test_completed_split_requires_all_physical_returns_and_can_settle_again(self):
        p = propose(self.request, self.owner)
        f = fulfil(p, self.owner)
        refund = fulfil(p, self.owner, "REFUND", self.receipt)
        completion = complete(p, self.owner)
        rows = [return_evidence(f), return_evidence(refund)]
        with self.assertRaises(ValidationError):
            resolve(p, self.owner, rows[:1])
        self.assertEqual(inr_settlement_balance(self.account).outstanding, 0)
        resolution = resolve(p, self.owner, rows)
        self.assertEqual(resolution.event.action, "REVERSE")
        validate_inr_completion(completion)
        self.assert_contained()
        replacement = propose(self.request, self.owner, Decimal("500"))
        fulfil(replacement, self.owner)
        fulfil(replacement, self.owner, "REFUND", self.receipt)
        complete(replacement, self.owner)
        self.request.refresh_from_db()
        validate_closure_history(self.request)
        self.assertEqual(inr_settlement_balance(self.account).outstanding, 0)
        self.assertEqual(InrSettlementFulfilment.objects.count(), 4)
        self.assertEqual(Contribution.objects.count(), 1)

    def test_topup_requires_actual_external_refund_and_never_becomes_principal(self):
        p = propose(self.request, self.owner, Decimal("1200"))
        f = fulfil(p, self.owner)
        complete(p, self.owner)
        row = return_evidence(f)
        with self.assertRaises(ValidationError):
            resolve(p, self.owner, [dict(row, top_up_refund_reference="")])
        resolution = resolve(p, self.owner, [row])
        self.assertEqual(resolution.returns.get().amount, Decimal("1000"))
        self.assert_contained()
        self.assertEqual(Contribution.objects.count(), 1)

    def test_mixed_cash_and_online_refund_returns_do_not_change_original_sources(self):
        source, event = online_source(self.account)
        online = record(self.owner, source, event=event)
        p = propose(self.request, self.owner, Decimal("0"))
        cash_f = fulfil(p, self.owner, "REFUND", self.receipt)
        online_f = fulfil(p, self.owner, "REFUND", online)
        complete(p, self.owner)
        resolve(p, self.owner, [dict(return_evidence(cash_f), method="CASH_RECEIPT"), return_evidence(online_f)])
        self.assert_contained(Decimal("1500"))
        self.assertEqual(online_f.method, "PROVIDER_DASHBOARD")
        self.assertEqual(cash_f.method, "CASH_RETURN")

    def test_customer_return_does_not_reset_original_provider_refund_limit(self):
        source, event = online_source(self.account)
        online = record(self.owner, source, event=event)
        p = propose(self.request, self.owner, Decimal("1000"))
        jewellery = fulfil(p, self.owner)
        refund = fulfil(p, self.owner, "REFUND", online)
        complete(p, self.owner)
        resolve(p, self.owner, [return_evidence(jewellery), return_evidence(refund)])
        self.assert_contained(Decimal("1500"))
        with self.assertRaisesMessage(ValidationError, "refund capacity"):
            propose(self.request, self.owner, Decimal("1000"))
        self.assertEqual(InrSettlementProposal.objects.count(), 1)
        # Complete invoice disposition needs no second provider refund and is valid.
        replacement = propose(self.request, self.owner, Decimal("1500"))
        fulfil(replacement, self.owner)
        complete(replacement, self.owner)
        self.assertEqual(inr_settlement_balance(self.account).outstanding, 0)

    def test_provider_refund_capacity_is_cumulative_with_exact_boundary_allowed(self):
        source, event = online_source(self.account)
        online = record(self.owner, source, event=event)
        for invoice in (Decimal("1300"), Decimal("1200")):
            p = propose(self.request, self.owner, invoice)
            jewellery = fulfil(p, self.owner)
            refund = fulfil(p, self.owner, "REFUND", online)
            complete(p, self.owner)
            resolve(p, self.owner, [return_evidence(jewellery), return_evidence(refund)])
        # 200 + 300 exhausted the original 500 receipt, even though both returned.
        with self.assertRaisesMessage(ValidationError, "refund capacity"):
            propose(self.request, self.owner, Decimal("1499"))
        self.assert_contained(Decimal("1500"))

    def test_idempotent_resolution_and_conflicting_replay(self):
        p = propose(self.request, self.owner)
        token = preview_inr_resolution(proposal_id=p.pk, actor=self.owner, kind="VOID", return_evidence=[])
        key = uuid.uuid4()
        first = resolve(p, self.owner, kind="VOID", token=token, key=key)
        self.assertEqual(resolve(p, self.owner, kind="VOID", token=token, key=key).pk, first.pk)
        with self.assertRaises(ValidationError):
            resolve(p, self.owner, kind="VOID", token=token, key=key, reason="Changed")
        with self.assertRaises(ValidationError):
            resolve(p, self.owner, kind="VOID", token=token)
        self.assertEqual(InrSettlementResolution.objects.count(), 1)

    def test_stale_expired_forged_wrong_owner_preview(self):
        p = propose(self.request, self.owner)
        token = preview_inr_resolution(proposal_id=p.pk, actor=self.owner, kind="VOID", return_evidence=[])
        with patch("django.core.signing.time.time", return_value=timezone.now().timestamp() + 601):
            with self.assertRaises(ValidationError):
                resolve(p, self.owner, kind="VOID", token=token)
        with self.assertRaises(ValidationError):
            resolve(p, self.owner, kind="VOID", token=token + "bad")
        other = make_owner("other-return-owner@example.com")
        with self.assertRaises(ValidationError):
            resolve(p, other, kind="VOID", token=token)
        fulfil(p, self.owner)
        with self.assertRaises(ValidationError):
            resolve(p, self.owner, kind="VOID", token=token)

    def test_customer_or_deactivated_owner_cannot_resolve(self):
        p = propose(self.request, self.owner)
        with self.assertRaises(ValidationError):
            resolve(p, self.customer.user, kind="VOID")
        self.owner.is_active = False
        self.owner.save(update_fields=["is_active"])
        with self.assertRaises(ValidationError):
            resolve(p, self.owner, kind="VOID")

    def test_wrong_method_missing_evidence_wrong_time_and_partial_amount_rejected(self):
        p = propose(self.request, self.owner)
        f = fulfil(p, self.owner)
        row = return_evidence(f)
        for changes in ({"method": "BANK_CREDIT"}, {"invoice_correction_reference": ""},
                {"customer_confirmation": ""}, {"top_up_refund_reference": "Unexpected"},
                {"returned_at": timezone.now() + timedelta(days=1)},
                {"returned_at": f.fulfilled_at - timedelta(seconds=1)}, {"amount": Decimal("1")}):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                resolve(p, self.owner, [dict(row, **changes)])
        self.assertEqual(InrSettlementResolution.objects.count(), 0)

    def test_foreign_or_duplicate_legs_and_empty_return_rejected(self):
        p = propose(self.request, self.owner)
        f = fulfil(p, self.owner)
        row = return_evidence(f)
        for rows in ([], [row, row], [dict(row, fulfilment_id=f.pk + 1000)]):
            with self.subTest(rows=rows), self.assertRaises(ValidationError):
                resolve(p, self.owner, rows)

    def test_indian_local_return_time_normalizes_without_losing_actual_time(self):
        p = propose(self.request, self.owner)
        row = return_evidence(fulfil(p, self.owner))
        row["returned_at"] = row["returned_at"].astimezone(ZoneInfo("Asia/Kolkata"))
        resolution = resolve(p, self.owner, [row])
        self.assertEqual(resolution.returns.get().returned_at, row["returned_at"])
        self.assert_contained()

    def test_repeated_full_replacement_returns_do_not_compound_principal(self):
        p = propose(self.request, self.owner, Decimal("1000"))
        first = None
        for _ in range(2):
            f = fulfil(p, self.owner)
            completion = complete(p, self.owner)
            first = first or completion
            resolve(p, self.owner, [return_evidence(f)])
            self.assert_contained()
            p = propose(self.request, self.owner, Decimal("1000"))
        validate_inr_completion(first)
        self.assertEqual(InrSettlementProposal.objects.count(), 3)
        self.assertEqual(InrFulfilmentReturn.objects.count(), 2)
        self.assertEqual(Contribution.objects.count(), 1)

    def test_return_evidence_is_bound_to_preview_and_requires_customer_authorization(self):
        p = propose(self.request, self.owner)
        row = return_evidence(fulfil(p, self.owner))
        token = preview_inr_resolution(proposal_id=p.pk, actor=self.owner, kind="FULL_RETURN", return_evidence=[row])
        with self.assertRaises(ValidationError):
            resolve(p, self.owner, [dict(row, external_reference="Changed")], token=token)
        with self.assertRaises(ValidationError):
            resolve(p, self.owner, [row], token=token, authorization_reference="")

    def test_resolution_and_return_immutable_and_projection_tamper_fails_closed(self):
        p = propose(self.request, self.owner)
        resolution = resolve(p, self.owner, [return_evidence(fulfil(p, self.owner))])
        for obj in (resolution, resolution.returns.get()):
            with self.assertRaises(ValidationError):
                obj.save()
            with self.assertRaises(ValidationError):
                obj.delete()
        InrSettlementProposal.objects.filter(pk=p.pk).update(retired=False)
        with self.assertRaises(ValidationError):
            inr_settlement_balance(self.account)
        with self.assertRaises(CommandError):
            call_command("check_inr_principal", stdout=StringIO())

    def test_return_amount_tamper_and_nan_database_constraint(self):
        p = propose(self.request, self.owner)
        resolution = resolve(p, self.owner, [return_evidence(fulfil(p, self.owner))])
        row = resolution.returns.get()
        with self.assertRaises(IntegrityError), transaction.atomic(), connection.cursor() as cursor:
            cursor.execute("UPDATE schemes_inrfulfilmentreturn SET amount = 'NaN'::numeric WHERE id = %s", [row.pk])
        InrFulfilmentReturn.objects.filter(pk=row.pk).update(amount=Decimal("1"))
        with self.assertRaises(ValidationError):
            inr_settlement_balance(self.account)

    def test_failed_second_return_rolls_back_entire_resolution(self):
        p = propose(self.request, self.owner)
        f = fulfil(p, self.owner)
        refund = fulfil(p, self.owner, "REFUND", self.receipt)
        complete(p, self.owner)
        rows = [return_evidence(f), return_evidence(refund)]
        token = preview_inr_resolution(proposal_id=p.pk, actor=self.owner, kind="FULL_RETURN", return_evidence=rows)
        original = InrFulfilmentReturn.save

        def fail_second(obj, *args, **kwargs):
            if obj.fulfilment_id == refund.pk:
                raise ValidationError("Simulated evidence persistence failure")
            return original(obj, *args, **kwargs)

        with patch.object(InrFulfilmentReturn, "save", fail_second), self.assertRaises(ValidationError):
            resolve(p, self.owner, rows, token=token)
        self.assertFalse(InrSettlementResolution.objects.exists())
        self.assertFalse(InrFulfilmentReturn.objects.exists())
        p.refresh_from_db()
        self.assertFalse(p.retired)
        self.assertEqual(inr_settlement_balance(self.account).outstanding, 0)
        self.request.refresh_from_db()
        self.assertEqual(validate_closure_history(self.request), 3)

    def test_late_sources_after_return_are_held_not_added_to_replacement(self):
        p = propose(self.request, self.owner)
        resolve(p, self.owner, kind="VOID")
        source, cash = cash_source(self.account, self.owner)
        with self.assertRaises(ValidationError):
            record(self.owner, source, cash=cash)
        with self.assertRaises(ValidationError):
            propose(self.request, self.owner)

    def test_replacement_must_use_new_invoice_and_chain_cannot_skip(self):
        p = propose(self.request, self.owner, reference="ORIGINAL-INVOICE")
        resolve(p, self.owner, kind="VOID")
        with self.assertRaises(ValidationError):
            propose(self.request, self.owner, reference=p.invoice_reference)
        replacement = propose(self.request, self.owner)
        self.assertEqual(replacement.previous_id, p.pk)
        with self.assertRaises(IntegrityError), transaction.atomic():
            InrSettlementProposal.objects.filter(pk=replacement.pk).update(previous=None)
        with self.assertRaises(IntegrityError), transaction.atomic():
            InrSettlementProposal.objects.filter(pk=p.pk).update(retired=False)


class InrCorrectionTransactionTests(TransactionTestCase):
    def setup_proposal(self):
        owner, customer = make_owner(), make_customer()
        account = future_contract(owner, customer)
        source, cash = cash_source(account, owner)
        record(owner, source, cash=cash)
        return owner, account, propose(accepted_request(account, owner), owner)

    def test_concurrent_resolution_records_one_return_set(self):
        owner, account, p = self.setup_proposal()
        rows = [return_evidence(fulfil(p, owner))]
        token = preview_inr_resolution(proposal_id=p.pk, actor=owner, kind="FULL_RETURN", return_evidence=rows)
        key, barrier = uuid.uuid4(), Barrier(2)

        def worker():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return resolve(p, owner, rows, token=token, key=key).pk
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(worker) for _ in range(2)]
            ids = [f.result(timeout=45) for f in futures]
        self.assertEqual(ids[0], ids[1])
        self.assertEqual(InrFulfilmentReturn.objects.count(), 1)
        self.assertEqual(inr_settlement_balance(account).outstanding, Decimal("1000"))

    def test_reverse_migration_refuses_to_discard_corrections(self):
        from importlib import import_module
        from types import SimpleNamespace
        from django.apps import apps
        leaves = MigrationExecutor(connection).loader.graph.leaf_nodes()
        self.addCleanup(lambda: MigrationExecutor(connection).migrate(leaves))
        owner, account, p = self.setup_proposal()
        resolution = resolve(p, owner, kind="VOID")
        with self.assertRaisesMessage(RuntimeError, "Cannot reverse 0040"):
            MigrationExecutor(connection).migrate([("schemes", "0038_inr_manual_settlement")])
        with self.assertRaisesMessage(RuntimeError, "Cannot reverse 0039"):
            import_module("schemes.migrations.0039_inr_settlement_corrections").preserve_correction_history(
                apps, SimpleNamespace(connection=connection))
        self.assertTrue(InrSettlementResolution.objects.filter(pk=resolution.pk).exists())

    def test_original_proposal_survives_independent_agreement_rollback_refusal(self):
        owner, account, p = self.setup_proposal()
        leaves = MigrationExecutor(connection).loader.graph.leaf_nodes()
        self.addCleanup(lambda: MigrationExecutor(connection).migrate(leaves))
        with self.assertRaisesMessage(RuntimeError, "Cannot reverse 0040"):
            MigrationExecutor(connection).migrate([("schemes", "0038_inr_manual_settlement")])
        MigrationExecutor(connection).migrate(leaves)
        p.refresh_from_db()
        self.assertFalse(p.retired)
        self.assertIsNone(p.previous_id)
        self.assertEqual(inr_settlement_balance(account).outstanding, Decimal("1000"))
