"""Captured API principal, with real adapter validation and disposable DB evidence."""
import hashlib
import hmac
from importlib import import_module
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from threading import Barrier
from unittest.mock import Mock, patch

from django.core.exceptions import ValidationError
from django.db import IntegrityError, close_old_connections, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase, override_settings

from schemes.inr_selectors import get_inr_principal_summary
from schemes.models import (Contribution, InrPaymentCaptureEvidence, InrPrincipalReceipt,
    MetalAllocation, PaymentWebhookEvent, SchemeAccount)
from schemes.payments import RazorpayPaymentGateway, PaymentGatewayError, PaymentGatewayValidationError
from schemes.services import confirm_razorpay_contribution, process_razorpay_webhook, reconcile_razorpay_webhook
from schemes.tests import test_inr_payment_integration as integration
from schemes.tests import test_independent_payment_entry as entry
from schemes.tests.test_independent_instalment_ledger import NOW


class ApiHelpers:
    account = integration.InrPaymentIntegrationTests.account

    def setUp(self):
        entry.IndependentPaymentEntryTests.setUp(self)
        # Model defaults retain the original callable, unlike module time calls.
        from schemes.models import InrSettlementProposal, InrSettlementFulfilment, SchemeClosureEvent, SchemeClosureRequest
        for model, field in ((InrSettlementProposal, "recorded_at"), (InrSettlementFulfilment, "recorded_at"),
                             (SchemeClosureEvent, "created_at"), (SchemeClosureRequest, "requested_at")):
            clock = patch.object(model._meta.get_field(field), "_get_default", lambda: NOW)
            clock.start()
            self.addCleanup(clock.stop)

    def attempt(self, monthly=False):
        c, payload, body = integration.online(self.account(monthly), monthly, captured_at=NOW)
        c.refresh_from_db()
        gateway = RazorpayPaymentGateway(mode="live", key_id="rzp_live_synthetic", key_secret="synthetic-secret",
            webhook_secret="synthetic-webhook")
        gateway._request_json = Mock(return_value=payload["payload"]["payment"]["entity"].copy())
        return c, gateway, payload, body

    def confirm(self, c, gateway, **changes):
        payment_id = f"pay_{c.pk}"
        signature = hmac.new(b"synthetic-secret", f"{c.gateway_order_id}|{payment_id}".encode(), hashlib.sha256).hexdigest()
        return confirm_razorpay_contribution(**(dict(contribution_id=c.pk, callback_order_id=c.gateway_order_id,
            payment_id=payment_id, signature=signature, gateway=gateway) | changes))

    def event(self, c, body):
        return PaymentWebhookEvent.objects.create(contribution=c, gateway="razorpay", gateway_mode="live",
            event_type="payment.captured", event_id=uuid.uuid4().hex, status="RECEIVED",
            gateway_reference=f"pay_{c.pk}", gateway_order_id=c.gateway_order_id,
            payload_sha256=hashlib.sha256(body).hexdigest())

    def recover(self, e, gateway, **changes):
        return reconcile_razorpay_webhook(**(dict(webhook_event_id=e.pk, gateway=gateway,
            performed_by=self.owner, reason="Checked exact captured payment") | changes))

    def deliver(self, payload, body, event_id=None):
        return process_razorpay_webhook(gateway_mode="live", event_id=event_id or uuid.uuid4().hex,
            payload=payload, body=body)


@override_settings(PAYMENT_INITIATION_KILL_SWITCH=False)
class InrApiPaymentsTests(ApiHelpers, TestCase):
    def test_actual_optional_and_required_order_entry_then_callback_during_pause(self):
        from schemes.services import initiate_razorpay_contribution
        for monthly in (False, True):
            account = self.account(monthly)
            creation_gateway = entry.IndependentPaymentEntryTests.gateway(self)
            c = initiate_razorpay_contribution(scheme_account=account, amount=Decimal("500"), gateway=creation_gateway)
            gateway = RazorpayPaymentGateway(mode="live", key_id="rzp_live_synthetic", key_secret="synthetic-secret",
                webhook_secret="synthetic-webhook")
            gateway._request_json = Mock(return_value=dict(id=f"pay_{c.pk}", order_id=c.gateway_order_id,
                amount=50000, currency="INR", status="captured", captured=True))
            self.control.global_pause = True
            self.control.save()
            self.confirm(c, gateway)  # Pausing new collection must not discard captured funds.
            c.refresh_from_db()
            self.assertEqual(get_inr_principal_summary(account).principal_recorded, Decimal("500"))
            if monthly:
                self.assertEqual(c.instalment_reservation.state, "AWAITING")
            else:
                self.assertEqual(c.optional_order_request.binding.gateway_order_id, c.gateway_order_id)
            self.control.global_pause = False
            self.control.save()

    def test_callback_retains_minimal_capture_and_principal_without_fake_webhook(self):
        for monthly in (False, True):
            c, gateway, _, _ = self.attempt(monthly)
            confirmed = self.confirm(c, gateway)
            self.assertEqual(confirmed.status, "PAID")
            receipt = InrPrincipalReceipt.objects.get(contribution=c)
            evidence = receipt.api_capture
            self.assertEqual((evidence.source, evidence.gateway_mode, evidence.amount_subunits), ("CALLBACK", "live", 50000))
            self.assertIsNone(evidence.actor_id)
            self.assertIsNone(receipt.webhook_event_id)
            self.assertEqual(receipt.actor_label, "system:razorpay-callback")
            self.assertEqual(get_inr_principal_summary(c.scheme_account).principal_recorded, Decimal("500"))
            self.assertFalse(get_inr_principal_summary(c.scheme_account).needs_review)
            gateway._request_json.assert_called_once_with("GET", f"/payments/pay_{c.pk}")
            if monthly:
                self.assertEqual(c.instalment_reservation.state, "AWAITING")
        self.assertFalse(PaymentWebhookEvent.objects.exists())
        self.assertFalse(MetalAllocation.objects.exists())

    def test_callback_duplicate_then_signed_capture_preserves_source_and_qualifies_once(self):
        c, gateway, payload, body = self.attempt(True)
        self.confirm(c, gateway)
        receipt = InrPrincipalReceipt.objects.get(contribution=c)
        self.confirm(c, gateway)
        with patch("django.utils.timezone.now", return_value=NOW + timedelta(minutes=1)):
            e = self.deliver(payload, body)
            self.deliver(payload, body, e.event_id)
            self.confirm(c, gateway)
        receipt.refresh_from_db()
        self.assertIsNotNone(receipt.api_capture_id)
        self.assertIsNone(receipt.webhook_event_id)
        self.assertEqual(InrPrincipalReceipt.objects.count(), 1)
        self.assertEqual(InrPaymentCaptureEvidence.objects.count(), 1)
        self.assertEqual(c.instalment_reservation.state, "QUALIFIED")

    def test_webhook_first_callback_keeps_original_webhook_receipt(self):
        c, gateway, payload, body = self.attempt()
        with patch("django.utils.timezone.now", return_value=NOW + timedelta(minutes=1)):
            e = self.deliver(payload, body)
            self.confirm(c, gateway)
        self.assertEqual(InrPrincipalReceipt.objects.get().webhook_event_id, e.pk)
        self.assertFalse(InrPaymentCaptureEvidence.objects.exists())

    def test_bad_signature_or_order_never_calls_provider(self):
        c, gateway, _, _ = self.attempt()
        with self.assertRaises(PaymentGatewayValidationError):
            self.confirm(c, gateway, signature="bad-signature")
        with self.assertRaises(ValidationError):
            self.confirm(c, gateway, callback_order_id="order_other")
        gateway._request_json.assert_not_called()
        self.assertFalse(InrPrincipalReceipt.objects.exists())

    def test_mismatched_uncaptured_or_malformed_api_never_confirms(self):
        c, gateway, payload, _ = self.attempt()
        original = payload["payload"]["payment"]["entity"]
        for change in ({"id": "pay_other"}, {"order_id": "order_other"}, {"amount": 50001},
                       {"currency": "USD"}, {"captured": False}, {"status": "authorized"},
                       {"amount": True}, {"captured": "true"}):
            with self.subTest(change=change):
                gateway._request_json.return_value = original | change
                with self.assertRaises(PaymentGatewayError):
                    self.confirm(c, gateway)
                c.refresh_from_db()
                self.assertEqual(c.status, "PENDING")
        self.assertFalse(InrPaymentCaptureEvidence.objects.exists())

    def test_network_failure_is_retryable_without_partial_accounting(self):
        c, gateway, _, _ = self.attempt()
        gateway._request_json.side_effect = PaymentGatewayError("Synthetic unavailable provider")
        with self.assertRaises(PaymentGatewayError):
            self.confirm(c, gateway)
        self.assertFalse(InrPrincipalReceipt.objects.exists())
        gateway._request_json.side_effect = None
        self.assertEqual(self.confirm(c, gateway).status, "PAID")

    def test_principal_failure_rolls_back_confirmation_evidence_and_schedule(self):
        c, gateway, _, _ = self.attempt(True)
        with patch.object(InrPrincipalReceipt, "save", side_effect=ValidationError("Interrupted principal")):
            with self.assertRaisesMessage(ValidationError, "Interrupted principal"):
                self.confirm(c, gateway)
        c.refresh_from_db()
        self.assertEqual(c.status, "PENDING")
        self.assertEqual(c.instalment_reservation.state, "RESERVED")
        self.assertFalse(InrPaymentCaptureEvidence.objects.exists())
        self.assertEqual(self.confirm(c, gateway).status, "PAID")

    def test_failed_abandoned_closed_and_test_mode_are_not_credited(self):
        for status in ("FAILED", "ABANDONED"):
            c, gateway, _, _ = self.attempt()
            Contribution.objects.filter(pk=c.pk).update(status=status)
            with self.assertRaises(ValidationError):
                self.confirm(c, gateway)
        c, gateway, _, _ = self.attempt()
        Contribution.objects.filter(pk=c.pk).update(gateway_mode="test")
        with self.assertRaises(ValidationError):
            self.confirm(c, gateway)
        gateway.mode = "test"
        with self.assertRaisesMessage(ValidationError, "Live Razorpay capture"):
            self.confirm(c, gateway)
        gateway._request_json.assert_not_called()
        c, gateway, _, _ = self.attempt()
        SchemeAccount.objects.filter(pk=c.scheme_account_id).update(status="REDEEMED")
        with self.assertRaises(ValidationError):
            self.confirm(c, gateway)
        self.assertFalse(InrPrincipalReceipt.objects.exists())

    def test_changed_order_during_provider_io_is_rejected_under_lock(self):
        c, gateway, payload, _ = self.attempt()
        def response(*args):
            Contribution.objects.filter(pk=c.pk).update(gateway_order_id="order_changed")
            return payload["payload"]["payment"]["entity"]
        gateway._request_json.side_effect = response
        with self.assertRaises(ValidationError):
            self.confirm(c, gateway)
        self.assertFalse(InrPrincipalReceipt.objects.exists())

    def test_changed_contract_blocks_callback_and_recovery_with_either_intake_flag(self):
        c, gateway, _, body = self.attempt()
        e = self.event(c, body)
        type(c.scheme_account).objects.filter(pk=c.scheme_account.pk).update(plan_name_snapshot="Unaccepted changed terms")
        c.scheme_account.plan_name_snapshot = "Unaccepted changed terms"
        self.ready.stop()
        for flag in (False, True):
            with override_settings(CONFIGURED_PLANS_ENABLED=flag):
                with self.assertRaises(ValidationError):
                    self.confirm(c, gateway)
                self.assertEqual(self.recover(e, gateway).outcome, "MANUAL_REVIEW_REQUIRED")
        self.assertFalse(InrPrincipalReceipt.objects.exists())

    def test_recovery_preview_then_apply_is_atomic_and_timing_stays_pending(self):
        c, gateway, payload, body = self.attempt(True)
        e = self.event(c, body)
        with self.assertRaises(ValidationError):
            self.recover(e, gateway, apply=True)
        self.assertEqual(self.recover(e, gateway).outcome, "ELIGIBLE_FOR_RECOVERY")
        self.assertFalse(InrPrincipalReceipt.objects.exists())
        result = self.recover(e, gateway, apply=True)
        self.assertTrue(result.applied)
        evidence = InrPaymentCaptureEvidence.objects.get()
        self.assertEqual((evidence.source, evidence.actor_id, evidence.recovery_event_id), ("OWNER_RECOVERY", self.owner.pk, e.pk))
        self.assertEqual(c.instalment_reservation.state, "AWAITING")
        self.assertTrue(self.recover(e, gateway, apply=True).applied)
        with patch("django.utils.timezone.now", return_value=NOW + timedelta(minutes=1)):
            self.deliver(payload, body, e.event_id)
        c.refresh_from_db()
        self.assertEqual(c.instalment_reservation.state, "QUALIFIED")
        self.assertEqual(InrPrincipalReceipt.objects.count(), 1)

    def test_recovery_mismatch_and_nonowner_do_not_credit(self):
        c, gateway, _, body = self.attempt()
        e = self.event(c, body)
        with self.assertRaises(ValidationError):
            self.recover(e, gateway, performed_by=self.customer.user)
        gateway._request_json.return_value["amount"] = 50001
        self.assertEqual(self.recover(e, gateway).outcome, "MANUAL_REVIEW_REQUIRED")
        self.assertFalse(InrPrincipalReceipt.objects.exists())

    def test_interrupted_recovery_retries_without_fabricating_processed_evidence(self):
        c, gateway, _, body = self.attempt(True)
        e = self.event(c, body)
        self.recover(e, gateway)
        with patch.object(InrPrincipalReceipt, "save", side_effect=ValidationError("Interrupted")):
            with self.assertRaises(ValidationError):
                self.recover(e, gateway, apply=True)
        c.refresh_from_db()
        e.refresh_from_db()
        self.assertEqual((c.status, e.status), ("PENDING", "RECEIVED"))
        self.assertFalse(InrPaymentCaptureEvidence.objects.exists())
        self.assertTrue(self.recover(e, gateway, apply=True).applied)

    def test_recovery_repairs_verified_source_missing_principal(self):
        c, gateway, _, body = self.attempt()
        Contribution.objects.filter(pk=c.pk).update(status="PAID", paid_at=NOW, gateway_reference=f"pay_{c.pk}")
        e = self.event(c, body)
        self.assertTrue(get_inr_principal_summary(c.scheme_account).needs_review)
        self.assertEqual(self.recover(e, gateway).outcome, "ALREADY_PROCESSED")
        self.recover(e, gateway, apply=True)
        self.assertFalse(get_inr_principal_summary(c.scheme_account).needs_review)

    def test_apply_refetches_changed_provider_state_and_rejects_crosslinked_event(self):
        c, gateway, _, body = self.attempt()
        e = self.event(c, body)
        self.recover(e, gateway)
        gateway._request_json.return_value["captured"] = False
        self.assertFalse(self.recover(e, gateway, apply=True).applied)
        gateway._request_json.return_value["captured"] = True
        other, _, _, _ = self.attempt()
        PaymentWebhookEvent.objects.filter(pk=e.pk).update(contribution=other)
        self.assertEqual(self.recover(e, gateway).outcome, "MANUAL_REVIEW_REQUIRED")
        self.assertFalse(InrPrincipalReceipt.objects.exists())

    def test_late_signed_timing_requires_review_without_erasing_api_principal(self):
        import json
        c, gateway, payload, _ = self.attempt(True)
        self.confirm(c, gateway)
        payload["created_at"] = int((NOW + timedelta(minutes=11)).timestamp())
        body = json.dumps(payload).encode()
        with patch("django.utils.timezone.now", return_value=NOW + timedelta(minutes=12)):
            self.deliver(payload, body)
        self.assertEqual(c.instalment_reservation.state, "REVIEW")
        self.assertEqual(get_inr_principal_summary(c.scheme_account).principal_recorded, Decimal("500"))

    def test_api_receipt_retains_source_first_refund_proof_and_disposition_blocks_new_credit(self):
        from schemes.tests.test_independent_agreement_storage import stored_future
        from schemes.tests.test_independent_policy_fields import independent_values
        from schemes.tests.test_inr_settlements import accepted_request, propose, fulfil
        from schemes.inr_settlement_selectors import inr_settlement_balance
        a = stored_future(self.owner, self.customer, independent_values(accumulation="INR_PURCHASE_CREDIT",
            eligibility_policy="CALENDAR", duration_months=1))
        c, _, _ = integration.online(a)
        c.refresh_from_db()
        _, gateway, _, _ = self.attempt()
        gateway._request_json.return_value.update(id=f"pay_{c.pk}", order_id=c.gateway_order_id)
        self.confirm(c, gateway)
        receipt = InrPrincipalReceipt.objects.get(contribution=c)
        request = accepted_request(a, self.owner)
        p = propose(request, self.owner, invoice=Decimal("300"))
        self.assertEqual(p.evidence["sources"]["receipts"][0]["api_capture"], receipt.api_capture_id)
        self.assertEqual(p.evidence["refunds"][0]["method"], "PROVIDER_DASHBOARD")
        late, payload, body = integration.online(a)
        late.refresh_from_db()
        gateway._request_json.return_value = payload["payload"]["payment"]["entity"]
        with self.assertRaises(ValidationError):
            self.confirm(late, gateway)
        event = self.event(late, body)
        self.assertEqual(self.recover(event, gateway).outcome, "MANUAL_REVIEW_REQUIRED")
        late.refresh_from_db()
        self.assertEqual(late.status, "PENDING")
        self.assertEqual(InrPrincipalReceipt.objects.filter(scheme_account=a).count(), 1)
        # Late source history must also hold the existing disposition; do not hide it.
        with self.assertRaises(ValidationError):
            fulfil(p, self.owner)
        with self.assertRaises(ValidationError):
            inr_settlement_balance(a)
        self.assertEqual(get_inr_principal_summary(a).principal_recorded, Decimal("500"))

    def test_api_source_can_complete_one_manual_invoice_and_refund_disposition(self):
        from schemes.tests.test_independent_agreement_storage import stored_future
        from schemes.tests.test_independent_policy_fields import independent_values
        from schemes.tests.test_inr_settlements import accepted_request, propose, fulfil, complete
        from schemes.inr_settlement_selectors import inr_settlement_balance
        a = stored_future(self.owner, self.customer, independent_values(accumulation="INR_PURCHASE_CREDIT",
            eligibility_policy="CALENDAR", duration_months=1))
        c, payload, _ = integration.online(a)
        c.refresh_from_db()
        _, gateway, _, _ = self.attempt()
        gateway._request_json.return_value = payload["payload"]["payment"]["entity"]
        self.confirm(c, gateway)
        receipt = InrPrincipalReceipt.objects.get(contribution=c)
        p = propose(accepted_request(a, self.owner), self.owner, invoice=Decimal("300"))
        fulfil(p, self.owner)
        self.assertEqual(inr_settlement_balance(a).outstanding, Decimal("200"))
        fulfil(p, self.owner, "REFUND", receipt)
        complete(p, self.owner)
        self.assertEqual(inr_settlement_balance(a).outstanding, Decimal("0"))
        a.refresh_from_db()
        self.assertEqual(a.status, "REDEEMED")
        self.confirm(c, gateway)  # Duplicate capture cannot reopen or double credit.
        self.assertEqual(InrPrincipalReceipt.objects.filter(scheme_account=a).count(), 1)

    def test_immutable_evidence_database_shapes_and_drift_detection(self):
        c, gateway, _, _ = self.attempt()
        self.confirm(c, gateway)
        evidence = InrPaymentCaptureEvidence.objects.get()
        for action in (evidence.save, evidence.delete):
            with self.assertRaises(ValidationError):
                action()
        for change in ({"captured": False}, {"gateway_mode": "test"}, {"actor_label": "unknown"}):
            with self.assertRaises(IntegrityError), transaction.atomic():
                InrPaymentCaptureEvidence.objects.filter(pk=evidence.pk).update(**change)
        with self.assertRaises(IntegrityError), transaction.atomic():
            InrPrincipalReceipt.objects.update(api_capture=None)
        InrPaymentCaptureEvidence.objects.filter(pk=evidence.pk).update(amount_subunits=50100)
        self.assertTrue(get_inr_principal_summary(c.scheme_account).needs_review)
        with self.assertRaises(ValidationError):
            self.confirm(c, gateway)


class InrApiTransactionTests(ApiHelpers, TransactionTestCase):
    def test_concurrent_callbacks_credit_once(self):
        c, gateway, _, _ = self.attempt()
        barrier = Barrier(2)
        def confirm():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return self.confirm(c, gateway).pk
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = [f.result(timeout=30) for f in (pool.submit(confirm), pool.submit(confirm))]
        self.assertEqual(results, [c.pk, c.pk])
        self.assertEqual(InrPrincipalReceipt.objects.count(), 1)
        self.assertEqual(InrPaymentCaptureEvidence.objects.count(), 1)

    def test_concurrent_callback_and_webhook_keep_one_original_source(self):
        c, gateway, payload, body = self.attempt()
        barrier = Barrier(2)
        def receive(callback):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return self.confirm(c, gateway).status if callback else self.deliver(payload, body).status
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = [f.result(timeout=30) for f in (pool.submit(receive, True), pool.submit(receive, False))]
        self.assertEqual(results, ["PAID", "PROCESSED"])
        self.assertEqual(InrPrincipalReceipt.objects.count(), 1)
        self.assertFalse(get_inr_principal_summary(c.scheme_account).needs_review)

    def test_empty_migration_roundtrip_and_retained_evidence_reverse_guard(self):
        leaves = MigrationExecutor(connection).loader.graph.leaf_nodes()
        self.addCleanup(lambda: MigrationExecutor(connection).migrate(leaves))
        MigrationExecutor(connection).migrate([("schemes", "0043_optional_payment_order_evidence")])
        MigrationExecutor(connection).migrate(leaves)
        c, gateway, _, _ = self.attempt()
        self.confirm(c, gateway)
        before = list(InrPaymentCaptureEvidence.objects.values())
        principal = list(InrPrincipalReceipt.objects.values())
        with self.assertRaisesMessage(RuntimeError, "Retain independent draft policies"):
            MigrationExecutor(connection).migrate([("schemes", "0043_optional_payment_order_evidence")])
        from .migration_helpers import applied_migration_apps
        guard = import_module("schemes.migrations.0044_inr_api_capture_evidence").preserve_api_evidence
        with connection.schema_editor() as editor, self.assertRaisesMessage(RuntimeError, "Cannot reverse 0044"):
            guard(applied_migration_apps(), editor)
        self.assertEqual(list(InrPaymentCaptureEvidence.objects.values()), before)
        self.assertEqual(list(InrPrincipalReceipt.objects.values()), principal)
