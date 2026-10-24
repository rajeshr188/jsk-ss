"""Real service paths with synthetic gated agreements and a local fake provider."""
import json
import hashlib
import hmac
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from unittest.mock import Mock, patch
from threading import Barrier

from django.core.exceptions import ValidationError
from django.db import close_old_connections, connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse

from schemes.instalments import prepare_instalment_periods
from schemes.instalment_selectors import instalment_payment_ledger_summary
from schemes.models import Contribution, InstalmentReservation, MetalAllocation, PaymentOperationsControl, PaymentWebhookEvent
from schemes.payments import PaymentGatewayError, PaymentOrder, PaymentOrderInspection, PaymentInspection
from schemes.services import (
    initiate_razorpay_contribution, initiate_contribution, confirm_razorpay_contribution,
    process_razorpay_webhook, publish_scheme_rate, record_in_store_cash_contribution,
    reverse_in_store_cash_contribution, reconcile_abandoned_razorpay_contribution, reconcile_razorpay_webhook,
)
from schemes.tests.test_instalment_payments import NOW
from schemes.tests.test_instalment_schedules import fixture, synthetic_account
from schemes.tests.test_audit_exceptions import make_owner


@override_settings(IN_STORE_CASH_CONTRIBUTIONS_ENABLED=True, RAZORPAY_CHECKOUT_EXPIRY_MINUTES=10)
class InstalmentPaymentIntegrationTests(TestCase):
    def setUp(self):
        self.clock = patch("django.utils.timezone.now", return_value=NOW)
        self.clock.start()
        self.addCleanup(self.clock.stop)
        self.owner = make_owner()
        customer, self.grade, config, plan = fixture(self.owner)
        self.account = synthetic_account(customer, self.grade, plan)
        prepare_instalment_periods(account_id=self.account.pk, actor=self.owner, reason="Integration fixture")
        self.rate = publish_scheme_rate(metal_grade=self.grade, rate_per_gram=Decimal("10000"), published_by=self.owner)
        self.gateway = Mock(name="fake-provider")
        self.gateway.name, self.gateway.mode = "razorpay", "live"
        self.gateway.create_order.side_effect = self.create_order
        self.gateway.verify_payment.return_value = True

    def create_order(self, contribution):
        self.assertTrue(InstalmentReservation.objects.filter(contribution=contribution, state="ORDERING").exists())
        return PaymentOrder(f"order_{contribution.pk}", 100000, "INR")

    def online(self, **changes):
        return initiate_razorpay_contribution(scheme_account=self.account, amount=Decimal("1000"), gateway=self.gateway, **changes)

    def cash(self, key=None):
        return record_in_store_cash_contribution(scheme_account=self.account, amount=Decimal("1000"),
            expected_scheme_rate_id=self.rate.pk, received_by=self.owner, idempotency_key=key or uuid.uuid4())

    def callback(self, c):
        return confirm_razorpay_contribution(contribution_id=c.pk, callback_order_id=c.gateway_order_id,
            payment_id=f"pay_{c.pk}", signature="fixture", gateway=self.gateway)

    def webhook(self, c, *, captured_at=NOW + timedelta(seconds=30), delivered_at=NOW + timedelta(seconds=40), event_id=None):
        payload = {"event": "payment.captured", "created_at": int(captured_at.timestamp()) if captured_at else None,
            "payload": {"payment": {"entity": {"id": f"pay_{c.pk}", "order_id": c.gateway_order_id,
                "created_at": int(c.created_at.timestamp()), "amount": 100000, "currency": "INR",
                "captured": True, "status": "captured"}}}}
        body = json.dumps(payload).encode()
        with patch("django.utils.timezone.now", return_value=delivered_at):
            return process_razorpay_webhook(gateway_mode="live", event_id=event_id or uuid.uuid4().hex, body=body, payload=payload)

    @override_settings(PAYMENT_GATEWAY="razorpay", RAZORPAY_MODE="live", RAZORPAY_KEY_ID="rzp_live_fixture",
        RAZORPAY_KEY_SECRET="fixture-secret", RAZORPAY_WEBHOOK_SECRET="fixture-webhook")
    def test_signed_http_webhook_qualifies_but_invalid_signature_does_not(self):
        c = self.online()
        body = json.dumps({"event": "payment.captured", "created_at": int(NOW.timestamp()),
            "payload": {"payment": {"entity": {"id": f"pay_{c.pk}", "order_id": c.gateway_order_id,
                "created_at": int(NOW.timestamp()), "amount": 100000, "currency": "INR",
                "captured": True, "status": "captured"}}}}).encode()
        url = reverse("schemes:razorpay_webhook")
        with patch("schemes.payments.urlopen", side_effect=AssertionError("No network in this test")):
            response = self.client.post(url, body, content_type="application/json", HTTP_X_RAZORPAY_SIGNATURE="invalid")
            self.assertEqual(response.status_code, 400)
            self.assertFalse(PaymentWebhookEvent.objects.exists())
            signature = hmac.new(b"fixture-webhook", body, hashlib.sha256).hexdigest()
            response = self.client.post(url, body, content_type="application/json", HTTP_X_RAZORPAY_SIGNATURE=signature)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(c.instalment_reservation.state, "QUALIFIED")

    def test_failed_callback_verification_does_not_qualify_or_allocate(self):
        c = self.online()
        self.gateway.verify_payment.return_value = False
        with self.assertRaises(ValidationError):
            self.callback(c)
        c.refresh_from_db()
        self.assertEqual(c.status, "PENDING")
        self.assertEqual(c.instalment_reservation.state, "RESERVED")
        self.assertFalse(MetalAllocation.objects.exists())

    def test_online_reserves_before_provider_and_resumes_without_duplicate_order(self):
        c = self.online()
        self.assertEqual(self.online().pk, c.pk)
        self.assertEqual(self.gateway.create_order.call_count, 1)
        self.assertEqual(Contribution.objects.count(), 1)
        with self.assertRaises(ValidationError):
            self.cash()
        with patch("django.utils.timezone.now", return_value=NOW + timedelta(minutes=11)), self.assertRaises(ValidationError):
            self.online()
        self.assertEqual(c.instalment_reservation.state, "RESERVED")

    def test_callback_awaits_timing_then_delayed_webhook_qualifies_once_during_pause(self):
        c = self.online()
        self.callback(c)
        c.refresh_from_db()
        self.assertEqual(c.status, "PAID")
        self.assertEqual(c.instalment_reservation.state, "AWAITING")
        with self.assertRaises(ValidationError):
            self.online()
        PaymentOperationsControl.objects.update(global_pause=True)
        event = self.webhook(c, delivered_at=NOW + timedelta(days=35), event_id="delayed")
        self.assertEqual(event.status, "PROCESSED")
        self.webhook(c, delivered_at=NOW + timedelta(days=36), event_id="delayed")
        c.instalment_reservation.refresh_from_db()
        self.assertEqual(c.instalment_reservation.state, "QUALIFIED")

        self.assertEqual(MetalAllocation.objects.count(), 1)
        self.assertEqual(instalment_payment_ledger_summary()["integrity_errors"], 0)

    def test_webhook_first_missing_timing_never_loses_captured_funds(self):
        c = self.online()
        event = self.webhook(c, captured_at=None)
        self.assertEqual(event.status, "PROCESSED")
        c.refresh_from_db()
        self.assertEqual(c.status, "PAID")
        self.assertEqual(c.instalment_reservation.state, "REVIEW")
        self.assertEqual(c.metal_allocation.quantity, Decimal("0.100000"))
        self.callback(c)
        self.assertEqual(instalment_payment_ledger_summary()["qualified_payments"], 0)

    def test_paid_unallocated_can_qualify_without_invented_grams(self):
        c = self.online()
        with patch("schemes.services.allocate_metal", side_effect=ValidationError("Allocation fixture")):
            event = self.webhook(c)
        self.assertEqual(event.status, "PROCESSED")
        c.refresh_from_db()
        self.assertEqual(c.status, "PAID_UNALLOCATED")
        self.assertEqual(c.instalment_reservation.state, "QUALIFIED")
        self.assertFalse(MetalAllocation.objects.exists())

    def test_cash_reversal_and_replacement_are_atomic_and_keep_original_evidence(self):
        key = uuid.uuid4()
        c = self.cash(key)
        self.assertEqual(self.cash(key).pk, c.pk)
        self.assertEqual(c.instalment_reservation.state, "QUALIFIED")
        with self.assertRaises(ValidationError):
            self.online()
        reverse_in_store_cash_contribution(contribution=c, processed_by=self.owner,
            reason_code="WRONG_AMOUNT", reason="Correcting fixture")
        replacement = self.cash()
        self.assertNotEqual(c.pk, replacement.pk)
        self.assertEqual(list(c.instalment_reservation.decisions.values_list("state", flat=True)),
            ["RESERVED", "QUALIFIED", "REVERSED"])
        self.assertEqual(instalment_payment_ledger_summary()["qualified_payments"], 1)

    def test_cash_ledger_failure_rolls_back_receipt_contribution_and_audit(self):
        with patch("schemes.services.attribute_cash_instalment", side_effect=ValidationError("Fixture failure")):
            with self.assertRaises(ValidationError):
                self.cash()
        self.assertFalse(Contribution.objects.exists())
        self.assertFalse(InstalmentReservation.objects.exists())

    def test_reconciliation_releases_only_untouched_order_and_late_capture_stays_visible(self):
        c = self.online()
        self.gateway.inspect_order.return_value = PaymentOrderInspection(c.gateway_order_id,
            "created", 100000, 0, 100000, "INR", 0, 0, ())
        with patch("django.utils.timezone.now", return_value=NOW + timedelta(minutes=11)):
            dry = reconcile_abandoned_razorpay_contribution(contribution_id=c.pk, cutoff=NOW, gateway=self.gateway)
            self.assertFalse(dry.applied)
            c.instalment_reservation.refresh_from_db()
            self.assertEqual(c.instalment_reservation.state, "RESERVED")
            reconcile_abandoned_razorpay_contribution(contribution_id=c.pk, cutoff=NOW, gateway=self.gateway, apply=True)
            replacement = self.online()
        c.instalment_reservation.refresh_from_db()
        self.assertEqual(c.instalment_reservation.state, "RELEASED")
        event = self.webhook(c, captured_at=NOW + timedelta(minutes=12), delivered_at=NOW + timedelta(minutes=13))
        self.assertEqual((event.status, event.failure_code), ("REVIEW_REQUIRED", "LATE_CAPTURE_ABANDONED"))
        c.instalment_reservation.refresh_from_db()
        self.assertEqual(c.instalment_reservation.state, "RELEASED_REVIEW")
        self.assertEqual(replacement.instalment_reservation.state, "RESERVED")
        with self.assertRaises(ValidationError):
            self.online()
        self.assertFalse(MetalAllocation.objects.exists())
        self.assertEqual(instalment_payment_ledger_summary()["integrity_errors"], 0)

    def test_failure_after_provider_response_does_not_allow_second_order(self):
        with patch("schemes.services.complete_instalment_order_request", side_effect=RuntimeError("Simulated local write failure")):
            with self.assertRaises(RuntimeError):
                self.online()
        c = Contribution.objects.get()
        self.assertFalse(c.gateway_order_id)
        self.assertEqual(c.instalment_reservation.state, "ORDERING")
        with self.assertRaises(ValidationError):
            self.online()
        self.assertEqual(self.gateway.create_order.call_count, 1)
        self.assertEqual(instalment_payment_ledger_summary()["order_requests_pending"], 1)

    def test_provider_order_creation_failure_keeps_claim_for_manual_review(self):
        self.gateway.create_order.side_effect = PaymentGatewayError("Ambiguous timeout")
        with self.assertRaises(PaymentGatewayError):
            self.online()
        self.assertEqual(Contribution.objects.get().status, "FAILED")
        self.assertEqual(InstalmentReservation.objects.get().state, "ORDERING")
        with self.assertRaises(ValidationError):
            self.cash()

    def test_mock_test_backdated_and_paused_initiation_never_create_payment(self):
        self.gateway.mode = "test"
        with self.assertRaises(ValidationError):
            self.online()
        self.gateway.mode = "live"
        with self.assertRaises(ValidationError):
            initiate_contribution(scheme_account=self.account, amount=Decimal("1000"), payment_gateway="mock")
        with self.assertRaises(ValidationError):
            self.online(contribution_date=(NOW - timedelta(days=1)).date())
        PaymentOperationsControl.objects.update(global_pause=True)
        with self.assertRaises(ValidationError):
            self.online()
        self.assertFalse(Contribution.objects.exists())

    def test_extension_period_can_accept_payment_without_granting_eligibility(self):
        extension = NOW.replace(year=2027)
        with patch("django.utils.timezone.now", return_value=extension):
            publish_scheme_rate(metal_grade=self.grade, rate_per_gram=Decimal("10000"), published_by=self.owner)
            c = self.online()
        self.assertEqual(c.instalment_reservation.period.number, 13)
        self.assertEqual(self.account.status, "ACTIVE")

    def test_owner_api_recovery_awaits_signed_timing_evidence(self):
        c = self.online()
        with patch("schemes.services._complete_captured_webhook", side_effect=ValidationError("Fixture review")):
            event = self.webhook(c, event_id="recovery")
        self.gateway.inspect_payment.return_value = PaymentInspection(f"pay_{c.pk}", c.gateway_order_id,
            100000, "INR", "captured", True)
        reconcile_razorpay_webhook(webhook_event_id=event.pk, gateway=self.gateway, performed_by=self.owner, reason="Check fixture")
        reconcile_razorpay_webhook(webhook_event_id=event.pk, gateway=self.gateway, performed_by=self.owner, reason="Recover fixture", apply=True)
        c.refresh_from_db()
        self.assertEqual(c.instalment_reservation.state, "AWAITING")
        self.webhook(c, event_id="recovery")
        c.instalment_reservation.refresh_from_db()
        self.assertEqual(c.instalment_reservation.state, "QUALIFIED")


@override_settings(IN_STORE_CASH_CONTRIBUTIONS_ENABLED=True, RAZORPAY_CHECKOUT_EXPIRY_MINUTES=10)
class InstalmentServiceRaceTests(TransactionTestCase):
    def setUp(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        self.owner = make_owner()
        customer, self.grade, config, plan = fixture(self.owner)
        self.account = synthetic_account(customer, self.grade, plan)
        prepare_instalment_periods(account_id=self.account.pk, actor=self.owner, reason="Service race fixture")
        with patch("django.utils.timezone.now", return_value=NOW):
            self.rate = publish_scheme_rate(metal_grade=self.grade, rate_per_gram=Decimal("10000"), published_by=self.owner)
        self.gateway = Mock()
        self.gateway.name, self.gateway.mode = "razorpay", "live"
        self.gateway.create_order.side_effect = lambda c: PaymentOrder(f"order_{c.pk}", 100000, "INR")

    def race(self, actions):
        barrier = Barrier(2)
        def perform(action):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                try:
                    return action().pk
                except ValidationError:
                    return None
            finally:
                close_old_connections()
        with patch("django.utils.timezone.now", return_value=NOW), ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(perform, action) for action in actions]
            return [future.result(timeout=40) for future in futures]

    def online(self):
        return initiate_razorpay_contribution(scheme_account=self.account, amount=Decimal("1000"), gateway=self.gateway)

    def test_two_online_requests_resume_one_provider_order(self):
        results = self.race([self.online, self.online])
        completed = [pk for pk in results if pk is not None]
        self.assertTrue(completed)
        self.assertEqual(len(set(completed)), 1)
        self.assertEqual(self.gateway.create_order.call_count, 1)
        self.assertEqual(Contribution.objects.count(), 1)

    def test_online_and_cash_cannot_both_create_payment(self):
        def cash():
            return record_in_store_cash_contribution(scheme_account=self.account, amount=Decimal("1000"),
                expected_scheme_rate_id=self.rate.pk, received_by=self.owner, idempotency_key=uuid.uuid4())
        results = self.race([self.online, cash])
        self.assertEqual(sum(result is not None for result in results), 1)
        self.assertEqual(Contribution.objects.count(), 1)
        self.assertEqual(InstalmentReservation.objects.count(), 1)
