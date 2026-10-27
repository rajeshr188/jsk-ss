import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from decimal import Decimal
from io import StringIO
from importlib import import_module
from threading import Barrier
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, close_old_connections, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from schemes.closure_selectors import validate_closure_history
from schemes.inr_principal import record_inr_principal
from schemes.inr_settlement_selectors import inr_settlement_balance
from schemes.inr_settlements import preview_inr_settlement, propose_inr_settlement, record_inr_fulfilment, complete_inr_settlement
from schemes.models import (SchemeAccount, SchemeClosureRequest, SchemeClosureEvent, InrSettlementProposal,
    InrSettlementFulfilment, InrSettlementCompletion, Contribution, MetalAllocation, Redemption)
from schemes.selectors import get_outstanding_entitlement, get_owner_liability_summary
from schemes.tests.test_inr_principal import future_contract, cash_source, online_source, record
from schemes.tests.test_audit_exceptions import make_owner, make_customer


def accepted_request(account, owner):
    """Synthetic future contract/closure in disposable DB; runtime enrolment stays blocked."""
    key = uuid.uuid4()
    request = SchemeClosureRequest.objects.create(scheme_account=account, requested_by=owner,
        source="OWNER_ASSISTED", status="ACCEPTED", actor_label="Owner", reason="Customer early closure",
        authorization_reference="Signed customer closure request", idempotency_key=key)
    SchemeClosureEvent.objects.create(request=request, sequence=1, action="REQUESTED", resulting_status="PENDING",
        actor=owner, actor_label="Owner", reason=request.reason, authorization_reference=request.authorization_reference,
        idempotency_key=key)
    SchemeClosureEvent.objects.create(request=request, sequence=2, action="ACCEPT", resulting_status="ACCEPTED",
        actor=owner, actor_label="Owner", reason="Review accepted", idempotency_key=uuid.uuid4())
    return request


def propose(request, owner, invoice=Decimal("800.00"), key=None, token=None, reference=None):
    if token is None:
        _, token = preview_inr_settlement(request_id=request.pk, actor=owner, invoice_payable=invoice)
    return propose_inr_settlement(request_id=request.pk, actor=owner, preview_token=token,
        invoice_reference=reference or ("INV-" + uuid.uuid4().hex if invoice else ""),
        authorization_reference="Customer signed exact split", reason="Manual final disposition",
        idempotency_key=key or uuid.uuid4())


def fulfil(p, owner, kind="JEWELLERY", receipt=None, key=None, **changes):
    values = dict(proposal_id=p.pk, actor=owner, kind=kind,
        method="SHOWROOM" if kind == "JEWELLERY" else ("CASH_RETURN" if receipt.cash_receipt_id else "PROVIDER_DASHBOARD"),
        external_reference=p.invoice_reference if kind == "JEWELLERY" else "REF-" + uuid.uuid4().hex,
        customer_receipt_reference="Signed handover/credited refund receipt", fulfilled_at=timezone.now(),
        reason="Completed physical fulfilment", idempotency_key=key or uuid.uuid4(),
        receipt_id=receipt.pk if receipt else None, top_up_reference="TOPUP" if p.separate_top_up else "")
    values.update(changes)
    return record_inr_fulfilment(**values)


def complete(p, owner, key=None):
    return complete_inr_settlement(proposal_id=p.pk, actor=owner, reason="All principal fulfilled and reconciled",
                                   idempotency_key=key or uuid.uuid4())


class InrSettlementTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner, cls.customer = make_owner(), make_customer()
        cls.account = future_contract(cls.owner, cls.customer)
        source, cash = cash_source(cls.account, cls.owner)
        cls.receipt = record(cls.owner, source, cash=cash)
        cls.request = accepted_request(cls.account, cls.owner)

    def test_invoice_below_principal_keeps_refund_liability_until_actual_fulfilment(self):
        p = propose(self.request, self.owner)
        self.account.refresh_from_db()
        self.assertEqual(self.account.status, "CLOSURE_PENDING")
        self.assertEqual(get_outstanding_entitlement(self.account), Decimal("1000"))
        self.assertEqual(p.principal_refund, Decimal("200"))
        call_command("check_scheme_closures", stdout=StringIO())
        with self.assertRaises(ValidationError):
            complete(p, self.owner)
        fulfil(p, self.owner)
        balance = inr_settlement_balance(self.account)
        self.assertEqual(balance.outstanding, Decimal("200"))
        self.assertEqual(balance.refund_pending, Decimal("200"))
        self.assertEqual(get_owner_liability_summary().inr_purchase_principal, Decimal("200"))
        with self.assertRaises(ValidationError):
            complete(p, self.owner)
        fulfil(p, self.owner, "REFUND", self.receipt)
        key = uuid.uuid4()
        closed = complete(p, self.owner, key)
        self.assertEqual(complete(p, self.owner, key).pk, closed.pk)
        self.account.refresh_from_db()
        self.request.refresh_from_db()
        self.assertEqual(self.account.status, "REDEEMED")
        self.assertEqual(self.request.status, "SETTLED")
        self.assertEqual(validate_closure_history(self.request), 3)
        self.assertEqual(get_outstanding_entitlement(self.account), 0)
        self.assertEqual(get_owner_liability_summary().inr_purchase_principal, 0)
        self.assertEqual(Contribution.objects.get(pk=self.receipt.contribution_id).status, "PAID")
        self.assertEqual(MetalAllocation.objects.count(), 0)
        self.assertEqual(Redemption.objects.count(), 0)
        output = StringIO()
        call_command("check_inr_principal", stdout=output)
        self.assertIn("settlement_errors=0", output.getvalue())
        call_command("check_scheme_closures", stdout=StringIO())

    def test_refund_first_does_not_close_before_jewellery_handover(self):
        p = propose(self.request, self.owner)
        fulfil(p, self.owner, "REFUND", self.receipt)
        self.assertEqual(inr_settlement_balance(self.account).jewellery_pending, Decimal("800"))
        with self.assertRaises(ValidationError):
            complete(p, self.owner)

    def test_all_refund_has_no_invoice_or_fake_jewellery(self):
        p = propose(self.request, self.owner, Decimal("0.00"))
        self.assertIsNone(p.invoice_reference)
        with self.assertRaises(ValidationError):
            fulfil(p, self.owner)
        fulfil(p, self.owner, "REFUND", self.receipt)
        complete(p, self.owner)
        self.assertEqual(inr_settlement_balance(self.account).outstanding, 0)

    def test_invoice_equal_principal_has_no_refund_leg(self):
        p = propose(self.request, self.owner, Decimal("1000"))
        self.assertEqual(p.evidence["refunds"], [])
        with self.assertRaises(ValidationError):
            fulfil(p, self.owner, "REFUND", self.receipt)
        fulfil(p, self.owner)
        complete(p, self.owner)

    def test_invoice_above_principal_requires_external_topup_not_new_contribution(self):
        p = propose(self.request, self.owner, Decimal("1200"))
        self.assertEqual(p.separate_top_up, Decimal("200"))
        with self.assertRaises(ValidationError):
            fulfil(p, self.owner, top_up_reference="")
        fulfil(p, self.owner)
        complete(p, self.owner)
        self.assertEqual(Contribution.objects.count(), 1)

    def test_mixed_sources_refund_original_live_source_not_cash(self):
        source, event = online_source(self.account)
        online = record(self.owner, source, event=event)
        p = propose(self.request, self.owner, Decimal("1200"))
        self.assertEqual(p.evidence["refunds"], [dict(receipt=online.pk, amount="300.00", method="PROVIDER_DASHBOARD")])
        with self.assertRaises(ValidationError):
            fulfil(p, self.owner, "REFUND", online, method="CASH_RETURN")
        with self.assertRaises(ValidationError):
            fulfil(p, self.owner, "REFUND", self.receipt)
        fulfil(p, self.owner)
        fulfil(p, self.owner, "REFUND", online)
        complete(p, self.owner)

    def test_proposal_replay_conflict_and_one_full_disposition(self):
        key = uuid.uuid4()
        _, token = preview_inr_settlement(request_id=self.request.pk, actor=self.owner, invoice_payable=Decimal("800"))
        p = propose(self.request, self.owner, key=key, token=token, reference="INV-ONE")
        self.assertEqual(propose(self.request, self.owner, key=key, token=token, reference="INV-ONE").pk, p.pk)
        with self.assertRaises(ValidationError):
            propose(self.request, self.owner, key=key, token=token, reference="CHANGED")
        with self.assertRaises(ValidationError):
            propose(self.request, self.owner, token=token)
        self.assertEqual(InrSettlementProposal.objects.count(), 1)

    def test_stale_expired_or_wrong_owner_preview_rejected(self):
        _, token = preview_inr_settlement(request_id=self.request.pk, actor=self.owner, invoice_payable=Decimal("800"))
        with patch("django.core.signing.time.time", return_value=timezone.now().timestamp() + 601):
            with self.assertRaises(ValidationError):
                propose(self.request, self.owner, token=token)
        with self.assertRaises(ValidationError):
            propose(self.request, self.owner, token=token + "tampered")
        other_owner = make_owner("other-owner-inr@example.com")
        with self.assertRaises(ValidationError):
            propose(self.request, other_owner, token=token)
        source, cash = cash_source(self.account, self.owner)
        record(self.owner, source, cash=cash)
        with self.assertRaises(ValidationError):
            propose(self.request, self.owner, token=token)
        with self.assertRaises(ValidationError):
            preview_inr_settlement(request_id=self.request.pk, actor=self.customer.user, invoice_payable=Decimal("800"))

    def test_fulfilment_idempotency_duplicate_evidence_and_immutability(self):
        p = propose(self.request, self.owner)
        key, when = uuid.uuid4(), timezone.now()
        f = fulfil(p, self.owner, key=key, fulfilled_at=when)
        self.assertEqual(fulfil(p, self.owner, key=key, fulfilled_at=when).pk, f.pk)
        with self.assertRaises(ValidationError):
            fulfil(p, self.owner, key=key, fulfilled_at=when, reason="Different")
        with self.assertRaises(ValidationError):
            fulfil(p, self.owner)
        for obj in (p, f):
            with self.assertRaises(ValidationError):
                obj.save()
            with self.assertRaises(ValidationError):
                obj.delete()

    def test_future_dates_missing_receipts_and_partial_amount_rejected(self):
        p = propose(self.request, self.owner)
        for changes in ({"fulfilled_at": timezone.now() + timedelta(days=1)},
                        {"fulfilled_at": p.recorded_at - timedelta(seconds=1)},
                        {"customer_receipt_reference": ""}, {"external_reference": "OTHER-INVOICE"}):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                fulfil(p, self.owner, **changes)
        f = InrSettlementFulfilment(proposal=p, kind="JEWELLERY", amount=Decimal("1"), method="SHOWROOM",
            external_reference=p.invoice_reference, customer_receipt_reference="Proof", fulfilled_at=timezone.now(),
            recorded_by=self.owner, actor_label="Owner", reason="Attempt partial", idempotency_key=uuid.uuid4())
        with self.assertRaises(ValidationError):
            f.save()

    def test_late_payment_after_proposal_blocks_debits_and_closure(self):
        p = propose(self.request, self.owner)
        source, cash = cash_source(self.account, self.owner)
        with self.assertRaises(ValidationError):
            record(self.owner, source, cash=cash)
        with self.assertRaises(ValidationError):
            fulfil(p, self.owner)
        with self.assertRaises(ValidationError):
            complete(p, self.owner)
        with self.assertRaises(CommandError):
            call_command("check_inr_principal", stdout=StringIO())
        self.assertEqual(Contribution.objects.get(pk=source.pk).status, "PAID")

    def test_pending_and_failed_provider_history_is_not_cleared_by_zero_balance(self):
        source, event = online_source(self.account)
        for status in ("PENDING", "FAILED", "ABANDONED", "PAID_UNALLOCATED"):
            Contribution.objects.filter(pk=source.pk).update(status=status, checkout_expires_at=timezone.now(),
                paid_at=source.paid_at if status == "PAID_UNALLOCATED" else None,
                gateway_reference=source.gateway_reference if status == "PAID_UNALLOCATED" else "")
            with self.subTest(status=status), self.assertRaises(ValidationError):
                propose(self.request, self.owner)

    def test_drift_after_fulfilment_preserves_history_and_blocks_false_balance(self):
        p = propose(self.request, self.owner)
        fulfil(p, self.owner)
        Contribution.objects.filter(pk=self.receipt.contribution_id).update(amount=Decimal("999"))
        with self.assertRaises(ValidationError):
            get_outstanding_entitlement(self.account)
        self.assertEqual(p.fulfilments.get().amount, Decimal("800"))

    def test_reloaded_owner_and_no_legacy_account_reuse(self):
        self.owner.is_active = False
        self.owner.save(update_fields=["is_active"])
        with self.assertRaises(ValidationError):
            propose(self.request, self.owner)

    def test_normal_and_early_are_explicit_without_awarding_benefits(self):
        p = propose(self.request, self.owner)
        self.assertEqual(p.basis, "EARLY")
        other = future_contract(self.owner, self.customer)
        source, cash = cash_source(other, self.owner)
        record(self.owner, source, cash=cash)
        request = accepted_request(other, self.owner)
        with patch("schemes.inr_settlements.timezone.localdate", return_value=date(2027, 1, 1)):
            normal = propose(request, self.owner)
        self.assertEqual(normal.basis, "NORMAL")
        self.assertEqual(normal.principal, Decimal("1000"))

    def test_missing_acceptance_and_altered_contract_date_are_blocked(self):
        SchemeClosureRequest.objects.filter(pk=self.request.pk).update(status="PENDING")
        with self.assertRaises(ValidationError):
            propose(self.request, self.owner)
        SchemeClosureRequest.objects.filter(pk=self.request.pk).update(status="ACCEPTED")
        SchemeAccount.objects.filter(pk=self.account.pk).update(eligible_from=date(2026, 1, 1))
        with self.assertRaises(ValidationError):
            propose(self.request, self.owner)

    def test_cross_account_refund_and_customer_fulfilment_are_blocked(self):
        p = propose(self.request, self.owner)
        other = future_contract(self.owner, self.customer)
        source, cash = cash_source(other, self.owner)
        receipt = record(self.owner, source, cash=cash)
        with self.assertRaises(ValidationError):
            fulfil(p, self.owner, "REFUND", receipt)
        with self.assertRaises(ValidationError):
            fulfil(p, self.customer.user)

    def test_duplicate_invoice_cannot_be_applied_to_second_agreement(self):
        propose(self.request, self.owner, reference="INV-EXCLUSIVE")
        other = future_contract(self.owner, self.customer)
        source, cash = cash_source(other, self.owner)
        record(self.owner, source, cash=cash)
        with self.assertRaises(ValidationError):
            propose(accepted_request(other, self.owner), self.owner, reference="INV-EXCLUSIVE")

    def test_sql_conservation_and_duplicate_leg_constraints(self):
        p = propose(self.request, self.owner)
        for values in ({"principal_refund": Decimal("100")},
                       {"invoice_reference": None}, {"principal_to_invoice": Decimal("-1")}):
            with self.subTest(values=values), self.assertRaises(IntegrityError), transaction.atomic():
                InrSettlementProposal.objects.filter(pk=p.pk).update(**values)
        f = fulfil(p, self.owner)
        for table, field, pk in (("schemes_inrsettlementproposal", "principal", p.pk),
                                 ("schemes_inrsettlementfulfilment", "amount", f.pk)):
            with self.assertRaises(IntegrityError), transaction.atomic(), connection.cursor() as cursor:
                cursor.execute(f"UPDATE {table} SET {field} = 'NaN'::numeric WHERE id = %s", [pk])


class InrSettlementTransactionTests(TransactionTestCase):
    def assert_independent_rollback_blocked(self):
        from .migration_helpers import applied_migration_apps
        with self.assertRaisesMessage(RuntimeError, "Retain independent draft policies"):
            MigrationExecutor(connection).migrate([("schemes", "0037_inr_principal_foundation")])
        guard = import_module("schemes.migrations.0040_independent_agreement_storage").preserve_independent_agreements
        with connection.schema_editor() as editor, self.assertRaisesMessage(RuntimeError, "Cannot reverse 0040"):
            guard(applied_migration_apps(), editor)

    def test_concurrent_completion_appends_one_terminal_event(self):
        owner, customer = make_owner(), make_customer()
        account = future_contract(owner, customer)
        source, cash = cash_source(account, owner)
        record(owner, source, cash=cash)
        request = accepted_request(account, owner)
        p = propose(request, owner, Decimal("1000.00"))
        fulfil(p, owner)
        key, barrier = uuid.uuid4(), Barrier(2)

        def worker():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return complete(p, owner, key).pk
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(worker) for _ in range(2)]
            ids = [f.result(timeout=30) for f in futures]
        self.assertEqual(ids[0], ids[1])
        self.assertEqual(InrSettlementCompletion.objects.count(), 1)
        self.assertEqual(SchemeClosureEvent.objects.filter(action="SETTLE").count(), 1)

    def test_independent_agreement_guard_preserves_principal_before_older_migration(self):
        owner, customer = make_owner(), make_customer()
        account = future_contract(owner, customer)
        source, cash = cash_source(account, owner)
        record(owner, source, cash=cash)
        leaves = MigrationExecutor(connection).loader.graph.leaf_nodes()
        self.addCleanup(lambda: MigrationExecutor(connection).migrate(leaves))
        self.assert_independent_rollback_blocked()
        MigrationExecutor(connection).migrate(leaves)
        self.assertEqual(get_outstanding_entitlement(account), Decimal("1000.00"))
        self.assertEqual(InrSettlementProposal.objects.count(), 0)

    def test_concurrent_refund_submissions_discharge_once(self):
        owner, customer = make_owner(), make_customer()
        account = future_contract(owner, customer)
        source, cash = cash_source(account, owner)
        receipt = record(owner, source, cash=cash)
        request = accepted_request(account, owner)
        p = propose(request, owner, Decimal("0.00"))
        key, when, barrier = uuid.uuid4(), timezone.now(), Barrier(2)

        def worker():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return fulfil(p, owner, "REFUND", receipt, key, fulfilled_at=when, external_reference="REF-SAME").pk
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(worker) for _ in range(2)]
            ids = [f.result(timeout=30) for f in futures]
        self.assertEqual(ids[0], ids[1])
        self.assertEqual(InrSettlementFulfilment.objects.count(), 1)
        self.assertEqual(inr_settlement_balance(account).outstanding, 0)

    def test_reverse_migration_preserves_settlement_evidence(self):
        from .migration_helpers import applied_migration_apps
        leaves = MigrationExecutor(connection).loader.graph.leaf_nodes()
        self.addCleanup(lambda: MigrationExecutor(connection).migrate(leaves))
        owner, customer = make_owner(), make_customer()
        account = future_contract(owner, customer)
        source, cash = cash_source(account, owner)
        record(owner, source, cash=cash)
        p = propose(accepted_request(account, owner), owner)
        before = list(InrSettlementProposal.objects.values())
        self.assert_independent_rollback_blocked()
        with connection.schema_editor() as editor, self.assertRaisesMessage(RuntimeError, "Cannot reverse 0038"):
            import_module("schemes.migrations.0038_inr_manual_settlement").preserve_inr_settlement_history(
                applied_migration_apps(), editor)
        self.assertEqual(list(InrSettlementProposal.objects.values()), before)
        # Refused reversal can already have unapplied later, empty migrations.
        # Restore the complete graph before using current runtime selectors.
        MigrationExecutor(connection).migrate(leaves)
        self.assertEqual(get_outstanding_entitlement(account), Decimal("1000.00"))
