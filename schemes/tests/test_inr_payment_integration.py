"""Verified-source integration; no live provider calls or collection activation."""
import hashlib
from importlib import import_module
import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from threading import Barrier
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import IntegrityError, close_old_connections, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase

from schemes.inr_principal import (record_captured_inr_principal, record_cash_inr_principal,
    record_cash_inr_correction)
from schemes.inr_selectors import get_inr_principal_summary
from schemes.instalments import prepare_instalment_periods
from schemes.instalment_payments import reserve_instalment
from schemes.models import (Contribution, InrPrincipalReceipt, InrPrincipalCorrection,
    InStoreCashReceipt, InStoreCashContributionReversal, MetalAllocation, PaymentWebhookEvent)
from schemes.payments import PaymentInspection
from schemes.services import process_razorpay_webhook, reverse_in_store_cash_contribution, _classify_webhook_recovery
from schemes.tests.test_audit_exceptions import make_owner, make_customer
from schemes.tests.test_independent_agreement_storage import stored_future
from schemes.tests.test_independent_policy_fields import independent_values, required_values
from schemes.tests.test_independent_instalment_ledger import NOW, source


def online(account, monthly=False, captured_at=None):
    with patch("django.utils.timezone.now", return_value=NOW):
        contribution = source(account)
        if monthly:
            reserve_instalment(contribution_id=contribution.pk)
    order = f"order_{contribution.pk}"
    Contribution.objects.filter(pk=contribution.pk).update(gateway_order_id=order)
    payload = {"event": "payment.captured", "created_at": int((captured_at or NOW + timedelta(seconds=30)).timestamp()),
        "payload": {"payment": {"entity": {"id": f"pay_{contribution.pk}", "order_id": order,
            "created_at": int(NOW.timestamp()), "status": "captured", "captured": True,
            "currency": "INR", "amount": 50000}}}}
    return contribution, payload, json.dumps(payload).encode()


class InrPaymentIntegrationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner, cls.customer = make_owner(), make_customer()

    def account(self, monthly=False):
        account = stored_future(self.owner, self.customer,
            (required_values if monthly else independent_values)(accumulation="INR_PURCHASE_CREDIT"))
        if monthly:
            prepare_instalment_periods(account_id=account.pk, actor=self.owner, reason="Synthetic accepted contract")
        return account

    def process(self, payload, body, event_id=None):
        # Simulate readiness only. Signature verification is upstream of this
        # existing internal service; no HTTP authentication is bypassed here.
        with patch("schemes.plan_policies.require_current_payment_workflow"), \
             patch("django.utils.timezone.now", return_value=NOW + timedelta(days=2)):
            return process_razorpay_webhook(gateway_mode="live", event_id=event_id or uuid.uuid4().hex,
                body=body, payload=payload)

    def cash(self, account, monthly=False):
        with patch("django.utils.timezone.now", return_value=NOW):
            contribution = source(account, gateway="in_store_cash")
            cash = InStoreCashReceipt.objects.create(contribution=contribution,
                receipt_reference=contribution.gateway_reference, received_by=self.owner,
                received_by_label="Owner", received_at=NOW)
            if monthly:
                reserve_instalment(contribution_id=contribution.pk)
        return contribution, cash

    def test_processed_capture_records_principal_and_monthly_evidence_once(self):
        for monthly in (False, True):
            account = self.account(monthly)
            contribution, payload, body = online(account, monthly)
            event = self.process(payload, body)
            self.assertEqual(event.status, "PROCESSED")
            receipt = InrPrincipalReceipt.objects.get(contribution=contribution)
            self.assertIsNone(receipt.recorded_by_id)
            self.assertEqual(receipt.actor_label, "system:razorpay-capture")
            self.assertEqual(receipt.amount, Decimal("500"))
            self.process(payload, body, event.event_id)
            self.process(payload, body)  # Different event ID, same captured payment.
            self.assertEqual(InrPrincipalReceipt.objects.filter(contribution=contribution).count(), 1)
            self.assertEqual(get_inr_principal_summary(account).principal_recorded, Decimal("500"))
            if monthly:
                self.assertEqual(contribution.instalment_reservation.state, "QUALIFIED")
        self.assertFalse(MetalAllocation.objects.exists())

    def test_late_capture_retains_principal_but_requires_timing_review(self):
        account = self.account(True)
        contribution, payload, body = online(account, True, captured_at=NOW + timedelta(minutes=11))
        event = self.process(payload, body)
        self.assertEqual(event.status, "PROCESSED")
        self.assertEqual(get_inr_principal_summary(account).principal_recorded, Decimal("500"))
        self.assertEqual(contribution.instalment_reservation.state, "REVIEW")

    def test_runtime_gate_stays_closed(self):
        contribution, payload, body = online(self.account())
        event = process_razorpay_webhook(gateway_mode="live", event_id=uuid.uuid4().hex, body=body, payload=payload)
        self.assertEqual(event.status, "REVIEW_REQUIRED")
        contribution.refresh_from_db()
        self.assertEqual(contribution.status, "PENDING")
        self.assertFalse(InrPrincipalReceipt.objects.exists())

    def test_failure_rolls_back_confirmation_credit_and_qualification(self):
        account = self.account(True)
        contribution, payload, body = online(account, True)
        with patch("schemes.instalment_payments.attribute_razorpay_instalment", side_effect=ValidationError("Injected failure")):
            event = self.process(payload, body)
        self.assertEqual(event.status, "REVIEW_REQUIRED")
        contribution.refresh_from_db()
        self.assertEqual(contribution.status, "PENDING")
        self.assertFalse(InrPrincipalReceipt.objects.exists())
        self.assertEqual(contribution.instalment_reservation.state, "RESERVED")

    def test_bad_body_or_amount_or_mode_never_creates_system_credit(self):
        contribution, payload, body = online(self.account())
        Contribution.objects.filter(pk=contribution.pk).update(status="PAID", paid_at=NOW,
            gateway_reference=f"pay_{contribution.pk}")
        event = PaymentWebhookEvent.objects.create(contribution=contribution, gateway="razorpay", gateway_mode="live",
            event_type="payment.captured", event_id=uuid.uuid4().hex, status="PROCESSED", processed_at=NOW,
            gateway_reference=f"pay_{contribution.pk}", gateway_order_id=f"order_{contribution.pk}",
            payload_sha256=hashlib.sha256(body).hexdigest())
        with self.assertRaises(ValidationError):
            record_captured_inr_principal(event_id=event.pk, body=body + b" ")
        payload["payload"]["payment"]["entity"]["amount"] = 50100
        wrong = json.dumps(payload).encode()
        PaymentWebhookEvent.objects.filter(pk=event.pk).update(payload_sha256=hashlib.sha256(wrong).hexdigest())
        with self.assertRaises(ValidationError):
            record_captured_inr_principal(event_id=event.pk, body=wrong)
        PaymentWebhookEvent.objects.filter(pk=event.pk).update(gateway_mode="test", payload_sha256=hashlib.sha256(body).hexdigest())
        with self.assertRaises(ValidationError):
            record_captured_inr_principal(event_id=event.pk, body=body)
        self.assertFalse(InrPrincipalReceipt.objects.exists())

    def test_cash_credit_and_real_correction_service_preserve_source_history(self):
        for monthly in (False, True):
            account = self.account(monthly)
            contribution, cash = self.cash(account, monthly)
            receipt = record_cash_inr_principal(cash_receipt_id=cash.pk)
            self.assertEqual(record_cash_inr_principal(cash_receipt_id=cash.pk).pk, receipt.pk)
            self.assertEqual(receipt.recorded_by_id, self.owner.pk)
            with patch("schemes.plan_policies.require_current_payment_workflow"), \
                 patch("django.utils.timezone.now", return_value=NOW + timedelta(minutes=2)), \
                 patch.object(InStoreCashContributionReversal._meta.get_field("reversed_at"),
                              "_get_default", lambda: NOW + timedelta(minutes=2)):
                reversal = reverse_in_store_cash_contribution(contribution=contribution, processed_by=self.owner,
                    reason_code="WRONG_AMOUNT", reason="Recorded amount was incorrect")
                correction = record_cash_inr_correction(cash_reversal_id=reversal.pk, actor=self.owner)
            self.assertEqual(correction.receipt_id, receipt.pk)
            summary = get_inr_principal_summary(account)
            self.assertEqual((summary.received, summary.corrected, summary.principal_recorded), (Decimal("500"), Decimal("500"), Decimal("0")))
            self.assertFalse(summary.needs_review)
            if monthly:
                self.assertEqual(contribution.instalment_reservation.state, "REVERSED")

    def test_failed_cash_attribution_rolls_back_principal(self):
        contribution, cash = self.cash(self.account(True), True)
        with patch("schemes.instalment_payments.attribute_cash_instalment", side_effect=ValidationError("Attribution failed")):
            with self.assertRaises(ValidationError):
                record_cash_inr_principal(cash_receipt_id=cash.pk)
        self.assertFalse(InrPrincipalReceipt.objects.exists())

    def test_correction_failure_rolls_back_source_and_instalment_reversal(self):
        account = self.account(True)
        contribution, cash = self.cash(account, True)
        record_cash_inr_principal(cash_receipt_id=cash.pk)
        with patch("schemes.plan_policies.require_current_payment_workflow"), \
             patch("django.utils.timezone.now", return_value=NOW + timedelta(minutes=2)), \
             patch.object(InStoreCashContributionReversal._meta.get_field("reversed_at"),
                          "_get_default", lambda: NOW + timedelta(minutes=2)), \
             patch.object(InrPrincipalCorrection, "save", side_effect=ValidationError("Correction failed")):
            with self.assertRaisesMessage(ValidationError, "Correction failed"):
                reverse_in_store_cash_contribution(contribution=contribution, processed_by=self.owner,
                    reason_code="WRONG_AMOUNT", reason="Synthetic correction")
        contribution.refresh_from_db()
        self.assertEqual(contribution.status, "PAID")
        self.assertEqual(contribution.instalment_reservation.state, "QUALIFIED")
        self.assertFalse(InStoreCashContributionReversal.objects.exists())
        self.assertFalse(InrPrincipalCorrection.objects.exists())
        self.assertEqual(get_inr_principal_summary(account).principal_recorded, Decimal("500"))

    def test_api_recovery_cannot_silently_mark_inr_processed_without_principal(self):
        contribution, _, body = online(self.account())
        contribution.refresh_from_db()
        event = PaymentWebhookEvent.objects.create(contribution=contribution, gateway="razorpay", gateway_mode="live",
            event_type="payment.captured", event_id=uuid.uuid4().hex, status="REVIEW_REQUIRED",
            gateway_reference=f"pay_{contribution.pk}", gateway_order_id=contribution.gateway_order_id,
            payload_sha256=hashlib.sha256(body).hexdigest())
        inspection = PaymentInspection(event.gateway_reference, event.gateway_order_id, 50000, "INR", "captured", True)
        outcome, reason = _classify_webhook_recovery(event=event, contribution=contribution, inspection=inspection)
        self.assertEqual(outcome, "MANUAL_REVIEW_REQUIRED")
        self.assertIn("reconciliation", reason)
        contribution.refresh_from_db()
        event.refresh_from_db()
        self.assertEqual(contribution.status, "PENDING")
        self.assertEqual(event.status, "REVIEW_REQUIRED")
        self.assertFalse(InrPrincipalReceipt.objects.exists())

    def test_missing_or_other_contribution_event_is_refused_before_inr_readiness(self):
        contribution, _, _ = online(self.account())
        other, _, body = online(self.account())
        other.refresh_from_db()
        event = PaymentWebhookEvent.objects.create(contribution=other, gateway="razorpay", gateway_mode="live",
            event_type="payment.captured", event_id=uuid.uuid4().hex, status="REVIEW_REQUIRED",
            gateway_reference=f"pay_{other.pk}", gateway_order_id=other.gateway_order_id,
            payload_sha256=hashlib.sha256(body).hexdigest())
        with patch("schemes.plan_policies.require_current_payment_workflow") as readiness:
            for candidate_event in (None, event):
                with self.subTest(event=getattr(candidate_event, "pk", None)):
                    outcome, _ = _classify_webhook_recovery(
                        event=candidate_event, contribution=contribution, inspection=None)
                    self.assertEqual(outcome, "MANUAL_REVIEW_REQUIRED")
            readiness.assert_not_called()
        self.assertFalse(InrPrincipalReceipt.objects.exists())
        self.assertFalse(Contribution.objects.exclude(status="PENDING").exists())

    def test_database_rejects_unattributed_cash_and_wrong_system_label(self):
        _, cash = self.cash(self.account())
        receipt = record_cash_inr_principal(cash_receipt_id=cash.pk)
        with self.assertRaises(IntegrityError), transaction.atomic():
            InrPrincipalReceipt.objects.filter(pk=receipt.pk).update(recorded_by=None)
        contribution, payload, body = online(self.account())
        self.process(payload, body)
        with self.assertRaises(IntegrityError), transaction.atomic():
            InrPrincipalReceipt.objects.filter(contribution=contribution).update(actor_label="unknown")


class SystemPrincipalMigrationTests(TransactionTestCase):
    def test_concurrent_verified_consumers_credit_once(self):
        account = stored_future(make_owner(), make_customer(), independent_values(accumulation="INR_PURCHASE_CREDIT"))
        contribution, payload, body = online(account)
        Contribution.objects.filter(pk=contribution.pk).update(status="PAID", paid_at=NOW,
            gateway_reference=f"pay_{contribution.pk}")
        event = PaymentWebhookEvent.objects.create(contribution=contribution, gateway="razorpay", gateway_mode="live",
            event_type="payment.captured", event_id=uuid.uuid4().hex, status="PROCESSED", processed_at=NOW,
            gateway_reference=f"pay_{contribution.pk}", gateway_order_id=f"order_{contribution.pk}",
            payload_sha256=hashlib.sha256(body).hexdigest())
        barrier = Barrier(2)
        def record():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return record_captured_inr_principal(event_id=event.pk, body=body).pk
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            first, second = [future.result(timeout=30) for future in [pool.submit(record), pool.submit(record)]]
        self.assertEqual(first, second)
        self.assertEqual(InrPrincipalReceipt.objects.count(), 1)

    def test_system_receipt_blocks_reverse_and_empty_roundtrip_is_safe(self):
        leaves = MigrationExecutor(connection).loader.graph.leaf_nodes()
        self.addCleanup(lambda: MigrationExecutor(connection).migrate(leaves))
        MigrationExecutor(connection).migrate([("schemes", "0040_independent_agreement_storage")])
        MigrationExecutor(connection).migrate(leaves)
        account = stored_future(make_owner(), make_customer(), independent_values(accumulation="INR_PURCHASE_CREDIT"))
        contribution, payload, body = online(account)
        with patch("schemes.plan_policies.require_current_payment_workflow"):
            process_razorpay_webhook(gateway_mode="live", event_id=uuid.uuid4().hex, body=body, payload=payload)
        self.assertTrue(InrPrincipalReceipt.objects.filter(recorded_by=None).exists())
        before = list(InrPrincipalReceipt.objects.values())
        # A later draft-policy guard now protects this complete schema first.
        with self.assertRaisesMessage(RuntimeError, "Retain independent draft policies"):
            MigrationExecutor(connection).migrate([("schemes", "0040_independent_agreement_storage")])
        from .migration_helpers import applied_migration_apps
        guard = import_module("schemes.migrations.0041_inr_system_receipts").preserve_system_receipts
        with connection.schema_editor() as editor, self.assertRaisesMessage(RuntimeError, "Cannot reverse 0041"):
            guard(applied_migration_apps(), editor)
        self.assertEqual(list(InrPrincipalReceipt.objects.values()), before)
