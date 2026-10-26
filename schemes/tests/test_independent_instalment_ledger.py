"""Internal integration on synthetic contracts; no production enrolment bypass."""
import hashlib
import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone as datetime_timezone
from decimal import Decimal
from threading import Barrier
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import close_old_connections
from django.test import TestCase, TransactionTestCase, override_settings

from schemes.instalments import prepare_instalment_periods, compensation_window
from schemes.instalment_payments import (reserve_instalment, attribute_cash_instalment,
    attribute_razorpay_instalment, reverse_cash_instalment, note_verified_instalment)
from schemes.instalment_selectors import (validated_instalment_periods,
    current_instalment_period, instalment_payment_ledger_summary)
from schemes.instalment_reviews import record_instalment_review
from schemes.instalment_outages import resolve_instalment_outage
from schemes.models import (Contribution, SchemeAccount, SchemeInstalmentPeriod, InstalmentReservation,
    InstalmentReview, InstalmentOutageResolution, InStoreCashReceipt, InStoreCashContributionReversal,
    PaymentWebhookEvent, MetalAllocation, InrPrincipalReceipt)
from schemes.services import validate_contribution_allowed
from schemes.tests.test_audit_exceptions import make_owner, make_customer
from schemes.tests.test_independent_agreement_storage import stored_future
from schemes.tests.test_independent_policy_fields import required_values, independent_values

NOW = datetime(2026, 1, 30, 8, tzinfo=datetime_timezone.utc)


def source(account, *, gateway="razorpay", now=NOW, **changes):
    # A synthetic upstream state only in the disposable DB. Normal creation stays gated.
    cash = gateway == "in_store_cash"
    with patch("django.utils.timezone.now", return_value=now):
        return Contribution.objects.create(**(dict(scheme_account=account, amount=Decimal("500"),
            contribution_period=now.date().replace(day=1), frequency_rule_snapshot="FLEXIBLE",
            payment_gateway=gateway, gateway_mode="" if cash else "live",
            status=("PAID_UNALLOCATED" if account.metal_grade_id else "PAID") if cash else "PENDING", paid_at=now if cash else None,
            gateway_reference=uuid.uuid4().hex if cash else None,
            checkout_expires_at=None if cash else now + timedelta(minutes=10)) | changes))


class IndependentInstalmentLedgerTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner, cls.customer = make_owner(), make_customer()

    def account(self, *, prepare=True, **values):
        account = stored_future(self.owner, self.customer, required_values(**values))
        if prepare:
            prepare_instalment_periods(account_id=account.pk, actor=self.owner, reason="Accepted synthetic contract")
        return account

    def cash(self, account, now=NOW):
        with patch("django.utils.timezone.now", return_value=now):
            contribution = source(account, gateway="in_store_cash", now=now)
            reservation = reserve_instalment(contribution_id=contribution.pk)
            InStoreCashReceipt.objects.create(contribution=contribution,
                receipt_reference=contribution.gateway_reference, received_at=now,
                received_by=self.owner, received_by_label="Owner")
            decision = attribute_cash_instalment(contribution_id=contribution.pk)
        return contribution, reservation, decision

    def capture(self, contribution, *, latest=NOW + timedelta(seconds=30), received=NOW + timedelta(days=35)):
        Contribution.objects.filter(pk=contribution.pk).update(
            status="PAID_UNALLOCATED" if contribution.scheme_account.metal_grade_id else "PAID", paid_at=received,
            gateway_reference=f"pay_{contribution.pk}", gateway_order_id=f"order_{contribution.pk}")
        payload = {"event": "payment.captured", "created_at": int(latest.timestamp()),
            "payload": {"payment": {"entity": {"id": f"pay_{contribution.pk}",
                "order_id": f"order_{contribution.pk}", "created_at": int(NOW.timestamp()),
                "status": "captured", "captured": True, "currency": "INR", "amount": 50000}}}}
        body = json.dumps(payload).encode()
        with patch("django.utils.timezone.now", return_value=received):
            event = PaymentWebhookEvent.objects.create(contribution=contribution,
                gateway="razorpay", gateway_mode="live", status="PROCESSED", processed_at=received,
                event_type="payment.captured", event_id=uuid.uuid4().hex,
                gateway_reference=f"pay_{contribution.pk}", gateway_order_id=f"order_{contribution.pk}",
                payload_sha256=hashlib.sha256(body).hexdigest())
        return event, body

    def test_schedule_persistence_idempotency_and_pinned_contract(self):
        for mode in ("EXACT_METAL", "INR_PURCHASE_CREDIT"):
            for basis in ("CALENDAR_MONTH", "ANNIVERSARY"):
                account = self.account(accumulation=mode, period_basis=basis,
                    eligibility_policy="CALENDAR_AND_COUNT", duration_months=18, required_count=2)
                original = list(account.instalment_periods.values())
                self.assertEqual(len(original), 5)
                type(account.plan).objects.filter(pk=account.plan_id).update(name="Later offer name")
                again = prepare_instalment_periods(account_id=account.pk, actor=self.owner, reason="Idempotent retry")
                self.assertEqual([r.pk for r in again], [r["id"] for r in original])
                self.assertEqual(list(account.instalment_periods.values()), original)
                self.assertEqual(len(validated_instalment_periods(account)), 5)
        self.assertFalse(Contribution.objects.exists())

    def test_no_optional_debt_backfill_or_closed_schedule_creation(self):
        optional = stored_future(self.owner, self.customer, independent_values())
        paid = self.account(prepare=False)
        source(paid)
        closed = self.account(prepare=False)
        SchemeAccount.objects.filter(pk=closed.pk).update(status="CLOSURE_PENDING")
        for account in (optional, paid, closed):
            with self.assertRaises(ValidationError):
                prepare_instalment_periods(account_id=account.pk, actor=self.owner, reason="Must refuse")
        self.assertFalse(SchemeInstalmentPeriod.objects.exists())

    def test_schedule_permissions_rollback_and_corruption_refusal(self):
        account = self.account(prepare=False)
        for actor, reason in ((self.customer.user, "Not owner"), (self.owner, " ")):
            with self.assertRaises(ValidationError):
                prepare_instalment_periods(account_id=account.pk, actor=actor, reason=reason)
        original_insert = SchemeInstalmentPeriod.objects.bulk_create
        def fail_after_insert(rows):
            original_insert(rows)
            raise ValidationError("Injected insertion failure")
        with patch.object(SchemeInstalmentPeriod.objects, "bulk_create", side_effect=fail_after_insert), self.assertRaises(ValidationError):
            prepare_instalment_periods(account_id=account.pk, actor=self.owner, reason="Atomic insert")
        self.assertFalse(account.instalment_periods.exists())
        prepare_instalment_periods(account_id=account.pk, actor=self.owner, reason="Valid insert")
        account.instalment_periods.filter(number=1).update(amount=Decimal("501"))
        before = list(account.instalment_periods.values())
        with self.assertRaises(ValidationError):
            prepare_instalment_periods(account_id=account.pk, actor=self.owner, reason="No silent repair")
        self.assertEqual(list(account.instalment_periods.values()), before)

    def test_cash_qualification_stops_at_explicit_count_not_duration(self):
        account = self.account(accumulation="INR_PURCHASE_CREDIT", required_count=1,
            eligibility_policy="CALENDAR_AND_COUNT", duration_months=18)
        contribution, reservation, decision = self.cash(account)
        self.assertEqual(decision.state, "QUALIFIED")
        self.assertEqual(attribute_cash_instalment(contribution_id=contribution.pk).pk, decision.pk)
        later = NOW.replace(month=2, day=1)
        with patch("django.utils.timezone.now", return_value=later):
            another = source(account, gateway="in_store_cash", now=later)
            with self.assertRaisesMessage(ValidationError, "count is already complete"):
                reserve_instalment(contribution_id=another.pk)
        self.assertEqual(InstalmentReservation.objects.count(), 1)
        account.refresh_from_db()
        self.assertEqual(account.status, "ACTIVE")
        self.assertFalse(InrPrincipalReceipt.objects.exists())
        self.assertFalse(MetalAllocation.objects.exists())

    def test_cash_reversal_retains_history_and_restores_count_capacity(self):
        account = self.account(required_count=1)
        contribution, claim, _ = self.cash(account)
        with patch("django.utils.timezone.now", return_value=NOW + timedelta(minutes=1)):
            Contribution.objects.filter(pk=contribution.pk).update(status="REVERSED")
            InStoreCashContributionReversal.objects.create(contribution=contribution,
                reversal_number=uuid.uuid4().hex, reason_code="WRONG_AMOUNT", reason="Synthetic correction",
                processed_by=self.owner, processed_by_label="Owner")
            reverse_cash_instalment(contribution_id=contribution.pk)
        replacement, _, _ = self.cash(account, NOW + timedelta(minutes=2))
        self.assertNotEqual(replacement.pk, contribution.pk)
        self.assertEqual(list(claim.decisions.values_list("state", flat=True)), ["RESERVED", "QUALIFIED", "REVERSED"])
        summary = instalment_payment_ledger_summary(account_id=account.pk)
        self.assertEqual(summary["qualified_payments"], 1)
        self.assertEqual(summary["integrity_errors"], 0)

    def test_verified_delayed_webhook_qualifies_once_without_ledger_or_account_mutation(self):
        for mode in ("EXACT_METAL", "INR_PURCHASE_CREDIT"):
            account = self.account(accumulation=mode, required_count=1)
            with patch("django.utils.timezone.now", return_value=NOW):
                contribution = source(account)
                claim = reserve_instalment(contribution_id=contribution.pk)
            event, body = self.capture(contribution)
            before = Contribution.objects.values().get(pk=contribution.pk)
            note_verified_instalment(contribution_id=contribution.pk)
            decision = attribute_razorpay_instalment(event_id=event.pk, body=body)
            self.assertEqual(decision.state, "QUALIFIED")
            self.assertEqual(attribute_razorpay_instalment(event_id=event.pk, body=body).pk, decision.pk)
            self.assertEqual(Contribution.objects.values().get(pk=contribution.pk), before)
            self.assertEqual(claim.period.number, 1)
            self.assertEqual(instalment_payment_ledger_summary(account_id=account.pk)["integrity_errors"], 0)
        self.assertFalse(InrPrincipalReceipt.objects.exists())
        self.assertFalse(MetalAllocation.objects.exists())

    def test_late_capture_is_review_and_test_gateway_cannot_reserve(self):
        account = self.account()
        with patch("django.utils.timezone.now", return_value=NOW):
            # Independent invalid-mode and late-capture cases must not create
            # two unresolved online attempts on the same agreement.
            test_payment = source(self.account(), gateway_mode="test")
            with self.assertRaises(ValidationError):
                reserve_instalment(contribution_id=test_payment.pk)
            contribution = source(account)
            reserve_instalment(contribution_id=contribution.pk)
        event, body = self.capture(contribution, latest=NOW + timedelta(minutes=11))
        decision = attribute_razorpay_instalment(event_id=event.pk, body=body)
        self.assertEqual((decision.state, decision.reason_code), ("REVIEW", "CHECKOUT_DEADLINE_REVIEW"))
        with self.assertRaises(ValidationError):
            attribute_razorpay_instalment(event_id=event.pk, body=body + b" ")

    def test_count_only_runtime_gates_stay_closed_and_compensation_preview_is_read_only(self):
        account = self.account()
        for enabled in (False, True):
            with override_settings(CONFIGURED_PLANS_ENABLED=enabled):
                for action in (account.save, lambda: current_instalment_period(account),
                               lambda: validate_contribution_allowed(account, Decimal("500"))):
                    with self.assertRaises(ValidationError):
                        action()
        self.assertEqual(compensation_window(account, 1).number, account.required_count_snapshot + 4)
        self.assertFalse(Contribution.objects.exists())

    def test_owner_review_and_all_outage_resolutions_remain_gated(self):
        account = self.account()
        period = account.instalment_periods.get(number=1)
        for action in ("NOTE", "OUTAGE_HOLD", "ACCEPT_TIMING"):
            with self.assertRaisesMessage(ValidationError, "preparation-only"):
                record_instalment_review(period_id=period.pk, actor=self.owner, action=action,
                    reason="Synthetic review", evidence_reference="TEST-ONLY",
                    idempotency_key=uuid.uuid4(), expected_review_sequence=0)
        self.assertFalse(InstalmentReview.objects.exists())
        # Synthetic historical hold: exercise the resolution guard independently.
        hold = InstalmentReview.objects.create(period=period, actor=self.owner, actor_label="Owner",
            action="OUTAGE_HOLD", sequence=1, reason="Synthetic hold",
            evidence_reference="TEST-ONLY", idempotency_key=uuid.uuid4())
        before = list(account.instalment_periods.values())
        for outcome in ("COMPENSATE", "RESTORED", "QUALIFIED"):
            with self.assertRaisesMessage(ValidationError, "preparation-only"):
                resolve_instalment_outage(hold_id=hold.pk, actor=self.owner, outcome=outcome,
                    reason="Synthetic resolution", evidence_reference="TEST-ONLY",
                    incident_started_at=NOW, service_restored_at=NOW + timedelta(minutes=1),
                    customer_acknowledged_at=NOW + timedelta(minutes=2), acknowledgement_reference="TEST-ACK",
                    idempotency_key=uuid.uuid4(), expected_review_sequence=1, expected_period_count=len(before))
        self.assertFalse(InstalmentOutageResolution.objects.exists())
        self.assertEqual(list(account.instalment_periods.values()), before)


class IndependentScheduleConcurrencyTests(TransactionTestCase):
    def test_two_preparations_create_one_complete_schedule(self):
        owner, customer = make_owner(), make_customer()
        account = stored_future(owner, customer, required_values(required_count=2))
        barrier = Barrier(2)
        def prepare():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return [row.pk for row in prepare_instalment_periods(account_id=account.pk, actor=owner, reason="Concurrent insert")]
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(prepare), pool.submit(prepare)]
            first, second = [future.result(timeout=30) for future in futures]
        self.assertEqual(first, second)
        self.assertEqual(SchemeInstalmentPeriod.objects.count(), 5)
