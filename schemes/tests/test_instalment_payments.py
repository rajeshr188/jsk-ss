"""Internal ledger tests use synthetic agreements; configured enrolment stays shut."""
import hashlib
import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone as datetime_timezone
from io import StringIO
from threading import Barrier
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, close_old_connections, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase

from schemes.instalments import prepare_instalment_periods
from schemes.instalment_payments import (
    reserve_instalment, attribute_cash_instalment, attribute_razorpay_instalment, reverse_cash_instalment,
)
from schemes.instalment_selectors import instalment_payment_ledger_summary
from schemes.models import (
    Contribution, InstalmentReservation, InstalmentPaymentDecision, PaymentWebhookEvent,
    InStoreCashReceipt, InStoreCashContributionReversal, MetalAllocation,
)
from schemes.tests.test_instalment_schedules import fixture, synthetic_account
from schemes.tests.test_audit_exceptions import make_owner

NOW = datetime(2026, 2, 10, 8, tzinfo=datetime_timezone.utc)


def payment(account, gateway="razorpay", **changes):
    with patch("django.utils.timezone.now", return_value=NOW):
        return Contribution.objects.create(**{
            "scheme_account": account, "amount": "1000.00", "contribution_period": NOW.date().replace(day=1),
            "frequency_rule_snapshot": "FLEXIBLE", "payment_gateway": gateway,
            "gateway_mode": "live" if gateway == "razorpay" else "", "status": "PENDING",
            "checkout_expires_at": NOW + timedelta(minutes=10) if gateway == "razorpay" else None,
            **changes,
        })


class InstalmentPaymentTests(TestCase):
    def setUp(self):
        self.owner = make_owner()
        customer, grade, config, plan = fixture(self.owner)
        self.account = synthetic_account(customer, grade, plan)
        prepare_instalment_periods(account_id=self.account.pk, actor=self.owner, reason="Ledger fixture")
        self.clock = patch("django.utils.timezone.now", return_value=NOW)
        self.clock.start()
        self.addCleanup(self.clock.stop)

    def reserve(self, **changes):
        c = payment(self.account, **changes)
        return c, reserve_instalment(contribution_id=c.pk)

    def capture(self, c, earliest=NOW, latest=NOW + timedelta(seconds=30), **changes):
        Contribution.objects.filter(pk=c.pk).update(status="PAID_UNALLOCATED", paid_at=NOW,
            gateway_reference=f"pay_{c.pk}", gateway_order_id=f"order_{c.pk}")
        payload = {"event": "payment.captured", "created_at": int(latest.timestamp()) if latest else None,
            "payload": {"payment": {"entity": {"id": f"pay_{c.pk}", "order_id": f"order_{c.pk}",
                "status": "captured", "captured": True, "currency": "INR", "amount": 100000,
                "created_at": int(earliest.timestamp()) if earliest else None, **changes}}}}
        body = json.dumps(payload).encode()
        with patch("django.utils.timezone.now", return_value=NOW + timedelta(days=40)):
            event = PaymentWebhookEvent.objects.create(gateway="razorpay", gateway_mode="live",
                event_id=uuid.uuid4().hex, event_type="payment.captured", status="PROCESSED",
                contribution=c, gateway_reference=f"pay_{c.pk}", gateway_order_id=f"order_{c.pk}",
                payload_sha256=hashlib.sha256(body).hexdigest())
        return event, body

    def cash(self):
        c, claim = self.reserve(gateway="in_store_cash", status="PAID_UNALLOCATED", paid_at=NOW,
            gateway_reference=uuid.uuid4().hex)
        InStoreCashReceipt.objects.create(contribution=c, receipt_reference=uuid.uuid4().hex,
            received_at=NOW, received_by=self.owner, received_by_label="owner")
        return c, claim

    def test_reservation_idempotent_cross_channel_exclusive_and_expiry_not_release(self):
        c, claim = self.reserve()
        self.assertEqual(reserve_instalment(contribution_id=c.pk).pk, claim.pk)
        other = payment(self.account, gateway="in_store_cash", status="PAID_UNALLOCATED", paid_at=NOW,
            gateway_reference="CASH-OTHER")
        for instant in (NOW, NOW + timedelta(hours=1), NOW + timedelta(days=30)):
            with patch("django.utils.timezone.now", return_value=instant), self.assertRaises(ValidationError):
                reserve_instalment(contribution_id=other.pk)
        self.assertEqual(claim.decisions.count(), 1)
        self.assertEqual(InstalmentReservation.objects.count(), 1)
        self.assertFalse(MetalAllocation.objects.exists())

    def test_delayed_verified_capture_qualifies_once_without_allocating_or_eligibility(self):
        c, claim = self.reserve()
        event, body = self.capture(c)
        d = attribute_razorpay_instalment(event_id=event.pk, body=body)
        self.assertEqual(d.state, "QUALIFIED")
        self.assertEqual(attribute_razorpay_instalment(event_id=event.pk, body=body).pk, d.pk)
        second, body2 = self.capture(c)
        attribute_razorpay_instalment(event_id=second.pk, body=body2)
        summary = instalment_payment_ledger_summary(account_id=self.account.pk)
        self.assertEqual(summary["qualified_payments"], 1)
        self.assertEqual(summary["paid_unallocated"], 1)
        self.assertEqual(summary["integrity_errors"], 0)
        self.assertEqual(claim.decisions.count(), 3)
        self.assertFalse(MetalAllocation.objects.exists())
        self.account.refresh_from_db()
        self.assertEqual(self.account.status, "ACTIVE")

    def test_missing_timing_stays_review_even_after_later_valid_event(self):
        c, claim = self.reserve()
        event, body = self.capture(c, earliest=None)
        self.assertEqual(attribute_razorpay_instalment(event_id=event.pk, body=body).state, "REVIEW")
        event2, body2 = self.capture(c)
        d = attribute_razorpay_instalment(event_id=event2.pk, body=body2)
        self.assertEqual(d.reason_code, "PRIOR_REVIEW_UNRESOLVED")
        self.assertEqual(instalment_payment_ledger_summary()["qualified_payments"], 0)

    def test_bad_identity_hash_or_unverified_source_never_qualifies(self):
        c, claim = self.reserve()
        event, body = self.capture(c)
        with self.assertRaises(ValidationError):
            attribute_razorpay_instalment(event_id=event.pk, body=body + b" ")
        for changes in ({"gateway_mode": "test"}, {"status": "REVIEW_REQUIRED"}, {"gateway_reference": "wrong"}):
            with transaction.atomic():
                PaymentWebhookEvent.objects.filter(pk=event.pk).update(**changes)
                with self.assertRaises(ValidationError):
                    attribute_razorpay_instalment(event_id=event.pk, body=body)
                transaction.set_rollback(True)
        malformed, bad = self.capture(c, amount=True)
        with self.assertRaises(ValidationError):
            attribute_razorpay_instalment(event_id=malformed.pk, body=bad)
        self.assertEqual(claim.decisions.count(), 1)

    def test_provider_timestamps_are_not_coerced_and_financial_rows_unchanged(self):
        c, claim = self.reserve()
        for value in (True, "1780000000", 1780000000.5, 1780000000000):
            event, body = self.capture(c, created_at=value)
            before = Contribution.objects.filter(pk=c.pk).values().get()
            decision = attribute_razorpay_instalment(event_id=event.pk, body=body)
            self.assertEqual(decision.state, "REVIEW")
            self.assertEqual(Contribution.objects.filter(pk=c.pk).values().get(), before)
        self.assertFalse(MetalAllocation.objects.exists())

    def test_completed_online_payment_cannot_acquire_reservation_retroactively(self):
        for changes in ({"status": "PAID_UNALLOCATED", "paid_at": NOW, "gateway_reference": "already-paid"},
            {"gateway_order_id": "order_already_created"}):
            with transaction.atomic():
                c = payment(self.account, **changes)
                with self.assertRaises(ValidationError):
                    reserve_instalment(contribution_id=c.pk)
                transaction.set_rollback(True)
        self.assertFalse(InstalmentReservation.objects.exists())

    def test_boundary_deadline_future_and_inconsistent_timing_require_review(self):
        c, claim = self.reserve()
        cases = [
            (NOW, NOW + timedelta(minutes=10, seconds=-1), "CHECKOUT_DEADLINE_REVIEW"),
            (NOW, NOW + timedelta(minutes=10), "CHECKOUT_DEADLINE_REVIEW"),
            (NOW, datetime(2026, 2, 27, 18, 30, tzinfo=datetime_timezone.utc), "PERIOD_BOUNDARY_REVIEW"),
            (NOW + timedelta(minutes=2), NOW, "INCONSISTENT_PAYMENT_TIMING"),
            (NOW, NOW + timedelta(days=41), "INCONSISTENT_PAYMENT_TIMING"),
        ]
        for start, end, code in cases:
            event, body = self.capture(c, earliest=start, latest=end)
            d = attribute_razorpay_instalment(event_id=event.pk, body=body)
            self.assertEqual((d.state, d.reason_code), ("REVIEW", code))

    def test_reversal_preserves_history_and_permits_replacement_not_recredit(self):
        c, claim = self.cash()
        first = attribute_cash_instalment(contribution_id=c.pk)
        self.assertEqual(first.state, "QUALIFIED")
        self.assertEqual(attribute_cash_instalment(contribution_id=c.pk).pk, first.pk)
        with self.assertRaises(ValidationError):
            reverse_cash_instalment(contribution_id=c.pk)
        Contribution.objects.filter(pk=c.pk).update(status="REVERSED")
        InStoreCashContributionReversal.objects.create(contribution=c, reversal_number="REV-1",
            reason_code="WRONG_AMOUNT", reason="Correction fixture", processed_by=self.owner, processed_by_label="owner")
        reverse = reverse_cash_instalment(contribution_id=c.pk)
        self.assertEqual(reverse_cash_instalment(contribution_id=c.pk).pk, reverse.pk)
        with self.assertRaises(ValidationError):
            attribute_cash_instalment(contribution_id=c.pk)
        replacement, replacement_claim = self.cash()
        attribute_cash_instalment(contribution_id=replacement.pk)
        self.assertEqual(list(claim.decisions.values_list("state", flat=True)), ["RESERVED", "QUALIFIED", "REVERSED"])
        summary = instalment_payment_ledger_summary()
        self.assertEqual((summary["qualified_payments"], summary["reversed"], summary["integrity_errors"]), (1, 1, 0))

    def test_test_mock_wrong_amount_expired_and_corrupt_schedule_rejected(self):
        for changes in ({"gateway_mode": "test"}, {"gateway": "mock"}, {"amount": "999"},
            {"checkout_expires_at": NOW}):
            with transaction.atomic():
                c = payment(self.account, **changes)
                with self.assertRaises(ValidationError):
                    reserve_instalment(contribution_id=c.pk)
                transaction.set_rollback(True)
        self.account.instalment_periods.filter(number=2).update(amount="2000")
        c = payment(self.account)
        with self.assertRaises(ValidationError):
            reserve_instalment(contribution_id=c.pk)
        self.assertFalse(InstalmentReservation.objects.exists())

    def test_database_constraints_and_immutable_models_and_read_only_checker(self):
        c, claim = self.reserve()
        with self.assertRaises(IntegrityError), transaction.atomic():
            other = payment(self.account)
            InstalmentReservation.objects.bulk_create([InstalmentReservation(period=claim.period,
                contribution=other, reserved_at=NOW, expires_at=NOW + timedelta(minutes=1))])
        for obj in (claim, claim.decisions.first()):
            with self.assertRaises(ValidationError):
                obj.save()
            with self.assertRaises(ValidationError):
                obj.delete()
        with self.assertRaises(IntegrityError), transaction.atomic():
            InstalmentPaymentDecision.objects.filter(reservation=claim).update(state="QUALIFIED")
        for enabled in (False, True):
            with self.settings(CONFIGURED_PLANS_ENABLED=enabled):
                stream = StringIO()
                call_command("check_instalment_payments", stdout=stream)
                self.assertIn(f"integration=gated_services configured_intake_enabled={str(enabled).lower()}", stream.getvalue())
        InstalmentReservation.objects.filter(pk=claim.pk).update(state="REVIEW")
        with self.assertRaises(CommandError):
            call_command("check_instalment_payments", stdout=StringIO())
        self.assertEqual(claim.decisions.count(), 1)

    def test_reservation_deadline_is_capped_at_india_anniversary_boundary(self):
        instant = datetime(2026, 2, 27, 18, 25, tzinfo=datetime_timezone.utc)
        c = payment(self.account, checkout_expires_at=instant + timedelta(minutes=10))
        Contribution.objects.filter(pk=c.pk).update(created_at=instant)
        with patch("django.utils.timezone.now", return_value=instant):
            claim = reserve_instalment(contribution_id=c.pk)
        self.assertEqual(claim.expires_at, datetime(2026, 2, 27, 18, 30, tzinfo=datetime_timezone.utc))


class InstalmentReservationConcurrencyTests(TransactionTestCase):
    def test_competing_online_and_cash_claims_serialize_on_agreement(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        owner = make_owner()
        customer, grade, config, plan = fixture(owner)
        account = synthetic_account(customer, grade, plan)
        prepare_instalment_periods(account_id=account.pk, actor=owner, reason="Concurrent fixture")
        online = payment(account)
        cash = payment(account, gateway="in_store_cash", status="PAID_UNALLOCATED", paid_at=NOW, gateway_reference="CASH-RACE")
        barrier = Barrier(2)

        def reserve(pk):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                try:
                    reserve_instalment(contribution_id=pk)
                    return True
                except ValidationError:
                    return False
            finally:
                close_old_connections()

        with patch("django.utils.timezone.now", return_value=NOW), ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(reserve, c.pk) for c in (online, cash)]
            results = [future.result(timeout=30) for future in futures]
        self.assertEqual(sorted(results), [False, True])
        self.assertEqual(InstalmentReservation.objects.count(), 1)
        self.assertEqual(InstalmentPaymentDecision.objects.count(), 1)
