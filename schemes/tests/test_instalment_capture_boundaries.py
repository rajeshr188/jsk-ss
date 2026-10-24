"""Capture evidence is retained; exceptions never manufacture a second credit."""
import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from threading import Barrier
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import close_old_connections, connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse

from schemes.instalment_selectors import (
    instalment_payment_ledger_summary, owner_instalment_review_periods,
    unresolved_instalment_captures,
)
from schemes.models import Contribution, MetalAllocation, PaymentOperationsControl
from schemes.payments import PaymentInspection, PaymentOrderInspection
from schemes.selectors import get_customer_payment_availability
from schemes.services import WebhookTransientProcessingError, process_razorpay_webhook, publish_scheme_rate, reconcile_abandoned_razorpay_contribution, reconcile_razorpay_webhook
from schemes.tests import test_instalment_reviews as reviews
from schemes.tests.test_instalment_payments import NOW


class CaptureFixture(reviews.ReviewFixture):
    def capture(self, c, *, payment_id=None, event_id=None, captured_at=None, mode="live"):
        payload = {"event": "payment.captured", "created_at": int((captured_at or NOW + timedelta(seconds=30)).timestamp()),
            "payload": {"payment": {"entity": {"id": payment_id or f"pay_{c.pk}", "order_id": c.gateway_order_id,
                "created_at": int(c.created_at.timestamp()), "amount": 100000, "currency": "INR",
                "captured": True, "status": "captured"}}}}
        body = json.dumps(payload).encode()
        # The public signed HTTP boundary is covered by integration tests; this is
        # its internal consumer with controlled provider facts and no network.
        return process_razorpay_webhook(gateway_mode=mode, event_id=event_id or uuid.uuid4().hex, body=body, payload=payload)

    def future(self):
        clock = patch("django.utils.timezone.now", return_value=NOW.replace(month=3))
        clock.start()
        self.addCleanup(clock.stop)
        self.rate = publish_scheme_rate(metal_grade=self.grade, rate_per_gram=Decimal("11000"), published_by=self.owner)

    def duplicate(self, c):
        with patch("django.utils.timezone.now", return_value=NOW + timedelta(minutes=1)):
            self.capture(c)
            return self.capture(c, payment_id="pay_additional", event_id="additional_capture")


@override_settings(IN_STORE_CASH_CONTRIBUTIONS_ENABLED=True)
class CaptureBoundaryTests(CaptureFixture, TestCase):
    def test_same_payment_redelivery_does_not_create_exception_or_second_credit(self):
        c = self.online()
        with patch("django.utils.timezone.now", return_value=NOW + timedelta(minutes=1)):
            self.capture(c, event_id="first")
            self.capture(c, event_id="first")
            self.capture(c, event_id="another_event_same_payment")
        self.assertEqual(MetalAllocation.objects.count(), 1)
        summary = instalment_payment_ledger_summary()
        self.assertEqual((summary["qualified_payments"], summary["unresolved_capture_events"], summary["integrity_errors"]), (1, 0, 0))
        self.future()
        self.cash()
        self.assertEqual(MetalAllocation.objects.count(), 2)

    def test_second_capture_preserves_first_credit_and_blocks_future_both_channels(self):
        c = self.online()
        event = self.duplicate(c)
        self.assertEqual((event.status, event.failure_code), ("REVIEW_REQUIRED", "DUPLICATE_CAPTURE_REVIEW"))
        c.refresh_from_db()
        before = (list(Contribution.objects.values()), list(MetalAllocation.objects.values()))
        self.assertEqual(c.gateway_reference, f"pay_{c.pk}")
        self.assertEqual(c.instalment_reservation.state, "QUALIFIED")
        self.future()
        for initiate in (self.online, self.cash):
            with self.assertRaisesMessage(ValidationError, "captured-payment exception"):
                initiate()
        self.submit(c.instalment_reservation, action="NOTE")
        self.gateway.inspect_payment.return_value = PaymentInspection("pay_additional", c.gateway_order_id, 100000, "INR", "captured", True)
        result = reconcile_razorpay_webhook(webhook_event_id=event.pk, gateway=self.gateway,
            performed_by=self.owner, reason="Investigate additional capture")
        self.assertEqual(result.outcome, "MANUAL_REVIEW_REQUIRED")
        with self.assertRaises(ValidationError):
            reconcile_razorpay_webhook(webhook_event_id=event.pk, gateway=self.gateway,
                performed_by=self.owner, reason="Cannot force duplicate credit", apply=True)
        self.assertEqual(before, (list(Contribution.objects.values()), list(MetalAllocation.objects.values())))
        self.assertEqual(instalment_payment_ledger_summary()["unresolved_capture_events"], 1)

    def test_delayed_delivery_uses_on_time_evidence_but_late_capture_never_qualifies(self):
        c = self.online()
        with patch("django.utils.timezone.now", return_value=NOW + timedelta(days=20)):
            self.capture(c, captured_at=NOW + timedelta(minutes=1))
        c.refresh_from_db()
        self.assertEqual(c.instalment_reservation.state, "QUALIFIED")
        self.assertEqual(MetalAllocation.objects.count(), 1)
        self.future()
        later = self.online()
        with patch("django.utils.timezone.now", return_value=NOW.replace(month=3) + timedelta(minutes=12)):
            self.capture(later, captured_at=NOW.replace(month=3) + timedelta(minutes=11))
        later.refresh_from_db()
        self.assertEqual((later.status, later.instalment_reservation.state), ("PAID", "REVIEW"))
        self.assertEqual(later.instalment_reservation.decisions.last().reason_code, "CHECKOUT_DEADLINE_REVIEW")
        self.assertEqual(MetalAllocation.objects.count(), 2)
        self.assertEqual(instalment_payment_ledger_summary()["qualified_payments"], 1)

    def test_late_capture_after_replacement_preserves_replacement_and_requires_manual_disposition(self):
        original = self.online()
        self.gateway.inspect_order.return_value = PaymentOrderInspection(original.gateway_order_id,
            "created", 100000, 0, 100000, "INR", 0, 0, ())
        with patch("django.utils.timezone.now", return_value=NOW + timedelta(minutes=11)):
            reconcile_abandoned_razorpay_contribution(contribution_id=original.pk, cutoff=NOW, gateway=self.gateway, apply=True)
            replacement = self.cash()
        before = list(MetalAllocation.objects.values())
        with patch("django.utils.timezone.now", return_value=NOW + timedelta(minutes=13)):
            event = self.capture(original, captured_at=NOW + timedelta(minutes=12), event_id="late")
            self.capture(original, captured_at=NOW + timedelta(minutes=12), event_id="late")
        self.assertEqual(event.failure_code, "LATE_CAPTURE_ABANDONED")
        original.refresh_from_db()
        self.assertEqual((original.status, original.instalment_reservation.state), ("ABANDONED", "RELEASED_REVIEW"))
        replacement.instalment_reservation.refresh_from_db()
        self.assertEqual(replacement.instalment_reservation.state, "QUALIFIED")
        self.assertEqual(before, list(MetalAllocation.objects.values()))
        self.assertEqual(instalment_payment_ledger_summary()["qualified_payments"], 1)

    def test_review_blocks_owner_timing_acceptance(self):
        c, claim, source = self.missing_then_valid()
        with patch("django.utils.timezone.now", return_value=NOW + timedelta(minutes=1)):
            self.capture(c, payment_id="pay_additional")
        with self.assertRaisesMessage(ValidationError, "captured-payment exception"):
            self.submit(claim, action="ACCEPT_TIMING", source_decision_id=source.pk)
        self.assertEqual(instalment_payment_ledger_summary()["qualified_payments"], 0)
        self.assertEqual(MetalAllocation.objects.count(), 1)

    def test_inflight_replacement_still_confirms_during_late_capture_review_and_pause(self):
        original = self.online()
        self.gateway.inspect_order.return_value = PaymentOrderInspection(original.gateway_order_id,
            "created", 100000, 0, 100000, "INR", 0, 0, ())
        with patch("django.utils.timezone.now", return_value=NOW + timedelta(minutes=11)):
            reconcile_abandoned_razorpay_contribution(contribution_id=original.pk, cutoff=NOW, gateway=self.gateway, apply=True)
            replacement = self.online()
        PaymentOperationsControl.objects.update(global_pause=True)
        with patch("django.utils.timezone.now", return_value=NOW + timedelta(minutes=14)):
            self.capture(original, captured_at=NOW + timedelta(minutes=12))
            event = self.capture(replacement, captured_at=NOW + timedelta(minutes=13))
        replacement.refresh_from_db()
        self.assertEqual((event.status, replacement.status, replacement.instalment_reservation.state), ("PROCESSED", "PAID", "QUALIFIED"))
        self.assertEqual(MetalAllocation.objects.count(), 1)
        self.assertEqual(instalment_payment_ledger_summary()["unresolved_capture_events"], 1)

    def test_unrelated_test_and_unknown_order_events_do_not_block_real_agreement(self):
        c = self.online()
        with patch("django.utils.timezone.now", return_value=NOW + timedelta(minutes=1)):
            self.capture(c, mode="test")
            c.gateway_order_id = "order_other_account"
            self.capture(c)
            c.refresh_from_db()
            self.capture(c)
        self.assertFalse(unresolved_instalment_captures(account_id=self.account.pk).exists())
        self.future()
        self.cash()

    def test_transient_capture_event_holds_until_successful_provider_redelivery(self):
        c = self.online()
        with patch("django.utils.timezone.now", return_value=NOW + timedelta(minutes=1)):
            self.capture(c)
            with patch("schemes.services._complete_captured_webhook", side_effect=RuntimeError("Transient fixture")):
                with self.assertRaises(WebhookTransientProcessingError):
                    self.capture(c, event_id="retry_capture")
        self.assertEqual(unresolved_instalment_captures(account_id=self.account.pk).get().status, "RECEIVED")
        self.future()
        with self.assertRaisesMessage(ValidationError, "captured-payment exception"):
            self.cash()
        self.assertEqual(self.capture(c, event_id="retry_capture").status, "PROCESSED")
        self.assertFalse(unresolved_instalment_captures(account_id=self.account.pk).exists())
        self.cash()
        self.assertEqual(MetalAllocation.objects.count(), 2)

    @override_settings(PAYMENT_GATEWAY="razorpay", RAZORPAY_MODE="live", RAZORPAY_KEY_ID="rzp_live_fixture", RAZORPAY_KEY_SECRET="fixture", RAZORPAY_WEBHOOK_SECRET="fixture")
    def test_owner_queue_exposes_provider_disposition_and_customer_payment_is_blocked(self):
        c = self.online()
        event = self.duplicate(c)
        period = c.instalment_reservation.period
        flagged = owner_instalment_review_periods().get(pk=period.pk)
        self.assertTrue(flagged.has_capture_review)
        self.assertFalse(owner_instalment_review_periods().filter(pk=self.account.instalment_periods.get(number=2).pk).exists())
        self.client.force_login(self.owner)
        page = self.client.get(reverse("schemes:instalment_review_period", args=[period.pk]))
        self.assertContains(page, "pay_additional")
        self.assertContains(page, reverse("schemes:webhook_recovery", args=[event.pk]))
        self.future()
        self.assertFalse(owner_instalment_review_periods().get(pk=self.account.instalment_periods.get(number=2).pk).has_capture_review)
        availability = get_customer_payment_availability(self.account)
        self.assertEqual((availability.allowed, availability.code), (False, "CAPTURE_REVIEW"))
        self.client.force_login(self.account.customer.user)
        self.assertEqual(self.client.get(reverse("schemes:instalment_review_period", args=[period.pk])).status_code, 403)


@override_settings(IN_STORE_CASH_CONTRIBUTIONS_ENABLED=True)
class CaptureRaceTests(CaptureFixture, TransactionTestCase):
    def setUp(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().setUp()

    def test_two_different_captures_never_credit_twice(self):
        c = self.online()
        barrier = Barrier(2)
        def run(payment_id):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return self.capture(c, payment_id=payment_id).status
            finally:
                close_old_connections()
        with patch("django.utils.timezone.now", return_value=NOW + timedelta(minutes=1)), ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(run, value) for value in ("pay_one", "pay_two")]
            results = [f.result(timeout=40) for f in futures]
        self.assertCountEqual(results, ["PROCESSED", "REVIEW_REQUIRED"])
        self.assertEqual(MetalAllocation.objects.count(), 1)
        summary = instalment_payment_ledger_summary()
        self.assertEqual((summary["qualified_payments"], summary["unresolved_capture_events"], summary["integrity_errors"]), (1, 1, 0))
