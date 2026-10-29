"""Actual creation services on synthetic contracts; only readiness is simulated."""
import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone as datetime_timezone
from decimal import Decimal
from threading import Barrier
from unittest.mock import Mock, patch

from django.core.exceptions import ValidationError
from django.db import close_old_connections
from django.test import TestCase, TransactionTestCase, override_settings

from schemes.instalments import prepare_instalment_periods
from schemes.inr_selectors import get_inr_principal_summary
from schemes.models import (Contribution, InrPrincipalReceipt, InStoreCashReceipt, MetalAllocation,
    PaymentOperationsControl, PaymentScheduleWindow, SchemeAccount, SchemeRate, AuditEvent)
from schemes.operations import get_payment_availability
from schemes.payments import PaymentOrder
from schemes.services import (initiate_contribution, initiate_razorpay_contribution,
    record_in_store_cash_contribution, preview_in_store_cash_contribution,
    validate_contribution_allowed, publish_scheme_rate, process_razorpay_webhook,
    reverse_in_store_cash_contribution)
from schemes.tests.test_audit_exceptions import make_owner, make_customer
from schemes.tests.test_independent_agreement_storage import stored_future
from schemes.tests.test_independent_policy_fields import independent_values, required_values
from schemes.tests.test_independent_instalment_ledger import NOW


@override_settings(IN_STORE_CASH_CONTRIBUTIONS_ENABLED=True, PAYMENT_INITIATION_KILL_SWITCH=False)
class IndependentPaymentEntryTests(TestCase):
    def setUp(self):
        self.owner, self.customer = make_owner(), make_customer()
        self.clock = patch("django.utils.timezone.now", return_value=NOW)
        self.clock.start()
        self.addCleanup(self.clock.stop)
        self.ready = patch("schemes.plan_policies.require_current_payment_workflow")
        self.ready.start()
        self.addCleanup(self.ready.stop)
        self.control, _ = PaymentOperationsControl.objects.get_or_create(pk=1)

    def account(self, monthly=False, metal=False, **changes):
        values = (required_values if monthly else independent_values)(
            accumulation="EXACT_METAL" if metal else "INR_PURCHASE_CREDIT", **changes)
        account = stored_future(self.owner, self.customer, values)
        if monthly:
            prepare_instalment_periods(account_id=account.pk, actor=self.owner, reason="Accepted synthetic terms")
        if metal:
            publish_scheme_rate(metal_grade=account.metal_grade, rate_per_gram=Decimal("10000"), published_by=self.owner)
        return account

    def cash(self, account, **changes):
        rate = SchemeRate.objects.filter(metal_grade=account.metal_grade).first() if account.metal_grade_id else None
        return record_in_store_cash_contribution(**(dict(scheme_account=account, amount=Decimal("500"),
            expected_scheme_rate_id=rate.pk if rate else None, received_by=self.owner,
            idempotency_key=uuid.uuid4()) | changes))

    def gateway(self):
        gateway = Mock()
        gateway.name, gateway.mode = "razorpay", "live"
        gateway.create_order.side_effect = lambda c: PaymentOrder(f"order_{c.pk}", 50000, "INR")
        return gateway

    def test_cash_optional_and_required_both_denominations_no_unit_mixing(self):
        for monthly in (False, True):
            for metal in (False, True):
                account = self.account(monthly, metal)
                preview = preview_in_store_cash_contribution(scheme_account=account, amount=Decimal("500"))
                c = self.cash(account)
                self.assertEqual(c.status, "PAID")
                self.assertEqual(c.frequency_rule_snapshot, "ONCE_PER_PERIOD" if monthly else "FLEXIBLE")
                self.assertEqual(bool(c.scheme_rate_id), metal)
                self.assertEqual(bool(c.rate_locked_at), metal)
                self.assertEqual(MetalAllocation.objects.filter(contribution=c).exists(), metal)
                self.assertEqual(InrPrincipalReceipt.objects.filter(contribution=c).exists(), not metal)
                self.assertEqual(preview.quantity, Decimal("0.050000") if metal else None)
                if monthly:
                    self.assertEqual(c.instalment_reservation.state, "QUALIFIED")
                if not metal:
                    self.assertEqual(get_inr_principal_summary(account).principal_recorded, Decimal("500"))

    def test_cash_retry_does_not_duplicate_principal_or_audit(self):
        account = self.account(True)
        key = uuid.uuid4()
        first = self.cash(account, idempotency_key=key)
        self.assertEqual(self.cash(account, idempotency_key=key).pk, first.pk)
        self.assertEqual(InStoreCashReceipt.objects.count(), 1)
        self.assertEqual(InrPrincipalReceipt.objects.count(), 1)
        self.assertEqual(AuditEvent.objects.filter(contribution=first, action="IN_STORE_CASH_RECEIPT").count(), 1)
        with self.assertRaises(ValidationError):
            self.cash(account, idempotency_key=key, amount=Decimal("600"))

    def test_principal_failure_rolls_back_new_cash_source_receipt_and_schedule_claim(self):
        account = self.account(True)
        with patch("schemes.inr_principal.record_cash_inr_principal", side_effect=ValidationError("Injected failure")):
            with self.assertRaises(ValidationError):
                self.cash(account)
        self.assertFalse(Contribution.objects.exists())
        self.assertFalse(InStoreCashReceipt.objects.exists())
        self.assertFalse(account.instalment_periods.filter(reservations__isnull=False).exists())

    def test_inr_never_accepts_a_metal_preview_rate(self):
        with self.assertRaises(ValidationError):
            self.cash(self.account(), expected_scheme_rate_id=1)
        self.assertFalse(Contribution.objects.exists())

    def test_fixed_amount_step_bounds_and_frozen_snapshot_enforced(self):
        fixed = self.account(True)
        with self.assertRaises(ValidationError):
            self.cash(fixed, amount=Decimal("501"))
        variable = self.account(amount_step=Decimal("50"))
        for amount in (Decimal("99"), Decimal("151"), Decimal("10001"), 500.0, True):
            with self.subTest(amount=amount), self.assertRaises(ValidationError):
                self.cash(variable, amount=amount)
        SchemeAccount.objects.filter(pk=variable.pk).update(minimum_amount_snapshot=Decimal("1"))
        with self.assertRaises(ValidationError):
            self.cash(variable)
        self.assertFalse(Contribution.objects.exists())

    def test_optional_ceiling_calendar_and_original_anniversary_anchor(self):
        for basis in ("CALENDAR_MONTH", "ANNIVERSARY"):
            account = self.account(frequency_rule="ONCE_PER_PERIOD", period_basis=basis,
                allow_contributions_after_eligibility=True)
            self.cash(account)
            boundary = datetime(2026, 2, 1 if basis == "CALENDAR_MONTH" else 28, tzinfo=datetime_timezone.utc) - timedelta(hours=5, minutes=30)
            with patch("django.utils.timezone.now", return_value=boundary - timedelta(microseconds=1)):
                with self.assertRaises(ValidationError):
                    self.cash(account)
            with patch("django.utils.timezone.now", return_value=boundary):
                self.cash(account)
            self.assertFalse(account.instalment_periods.exists())
            self.assertEqual(account.contributions.count(), 2)

    def test_optional_anytime_continued_contributions_are_explicit(self):
        for allow in (False, True):
            account = self.account(allow_contributions_after_eligibility=allow)
            self.cash(account)
            if allow:
                self.cash(account)
            else:
                with self.assertRaises(ValidationError):
                    self.cash(account)

    def test_duration_boundary_and_no_backdating_or_month_override(self):
        account = self.account(eligibility_policy="CALENDAR", duration_months=1)
        for changes in (dict(contribution_date=NOW.date()-timedelta(days=1)),
                        dict(contribution_period=NOW.date().replace(month=2, day=1))):
            with self.assertRaises(ValidationError):
                validate_contribution_allowed(account, Decimal("500"), **changes)
        with patch("django.utils.timezone.now", return_value=NOW.replace(month=2, day=28)):
            with self.assertRaises(ValidationError):
                self.cash(account)

    def test_closed_cancelled_or_contained_agreement_cannot_collect(self):
        account = self.account()
        for status in ("REDEEMED", "CANCELLED", "CLOSURE_PENDING"):
            SchemeAccount.objects.filter(pk=account.pk).update(status=status)
            with self.assertRaises(ValidationError):
                self.cash(account)
        self.assertFalse(Contribution.objects.exists())

    def test_inr_respects_global_kill_and_schedule_but_needs_no_metal_rate(self):
        account = self.account()
        self.control.global_pause = True
        self.control.save()
        with self.assertRaises(ValidationError):
            self.cash(account)
        self.control.global_pause = False
        self.control.gold_pause = self.control.silver_pause = True
        self.control.save()
        self.assertTrue(get_payment_availability(metal_grade=None, savings_mode="INR_CREDIT").allowed)
        with override_settings(PAYMENT_INITIATION_KILL_SWITCH=True), self.assertRaises(ValidationError):
            self.cash(account)
        self.control.schedule_enabled = True
        self.control.save()
        PaymentScheduleWindow.objects.filter(control=self.control).delete()
        with self.assertRaises(ValidationError):
            self.cash(account)
        self.assertFalse(SchemeRate.objects.exists())

    def test_required_online_creation_resumption_and_capture_real_services(self):
        for metal in (False, True):
            account, gateway = self.account(True, metal), self.gateway()
            c = initiate_razorpay_contribution(scheme_account=account, amount=Decimal("500"), gateway=gateway)
            self.assertEqual(initiate_razorpay_contribution(scheme_account=account, amount=Decimal("500"), gateway=gateway).pk, c.pk)
            self.assertEqual(gateway.create_order.call_count, 1)
            self.assertEqual(c.instalment_reservation.state, "RESERVED")
            self.assertEqual(c.frequency_rule_snapshot, "ONCE_PER_PERIOD")
            with self.assertRaises(ValidationError):
                self.cash(account)
            payload = {"event": "payment.captured", "created_at": int(NOW.timestamp()), "payload": {"payment": {"entity": {
                "id": f"pay_{c.pk}", "order_id": c.gateway_order_id, "created_at": int(NOW.timestamp()),
                "amount": 50000, "currency": "INR", "status": "captured", "captured": True}}}}
            event = process_razorpay_webhook(gateway_mode="live", event_id=uuid.uuid4().hex,
                body=json.dumps(payload).encode(), payload=payload)
            self.assertEqual(event.status, "PROCESSED")
            c.refresh_from_db()
            self.assertEqual(c.instalment_reservation.state, "QUALIFIED")
            with self.assertRaises(ValidationError):
                self.cash(account)

    def test_uncertain_online_request_not_repeated(self):
        account, gateway = self.account(True), self.gateway()
        gateway.create_order.side_effect = TimeoutError("Synthetic lost response")
        with self.assertRaises(TimeoutError):
            initiate_razorpay_contribution(scheme_account=account, amount=Decimal("500"), gateway=gateway)
        with self.assertRaises(ValidationError):
            initiate_razorpay_contribution(scheme_account=account, amount=Decimal("500"), gateway=gateway)
        self.assertEqual(gateway.create_order.call_count, 1)

    def test_count_is_independent_of_duration_and_stops_further_collection(self):
        account = self.account(True, required_count=1, eligibility_policy="CALENDAR_AND_COUNT", duration_months=18)
        self.cash(account)
        with patch("django.utils.timezone.now", return_value=NOW.replace(month=2, day=1)):
            with self.assertRaises(ValidationError):
                self.cash(account)
        self.assertEqual(account.contributions.count(), 1)

    def test_unrecorded_paid_sources_block_further_collection(self):
        from schemes.tests.test_independent_instalment_ledger import source
        for metal in (False, True):
            account = self.account(metal=metal, allow_contributions_after_eligibility=True)
            source(account, gateway="in_store_cash", status="PAID")
            with self.assertRaises(ValidationError):
                self.cash(account)
            self.assertEqual(account.contributions.count(), 1)

    def test_cash_period_uses_receipt_instant_not_insertion_timestamp(self):
        account = self.account(frequency_rule="ONCE_PER_PERIOD", period_basis="CALENDAR_MONTH",
            allow_contributions_after_eligibility=True)
        c = self.cash(account)
        # Simulate insertion after midnight; the immutable receipt instant remains January.
        Contribution.objects.filter(pk=c.pk).update(created_at=NOW.replace(month=2, day=1))
        with self.assertRaises(ValidationError):
            self.cash(account)
        with patch("django.utils.timezone.now", return_value=NOW.replace(month=2, day=1)):
            self.cash(account)

    def test_full_cash_correction_releases_only_its_payment_ceiling(self):
        from schemes.models import InStoreCashContributionReversal
        account = self.account(frequency_rule="ONCE_PER_PERIOD", period_basis="ANNIVERSARY",
            allow_contributions_after_eligibility=True)
        c = self.cash(account)
        with patch.object(InStoreCashContributionReversal._meta.get_field("reversed_at"), "_get_default", lambda: NOW):
            reverse_in_store_cash_contribution(contribution=c, processed_by=self.owner,
                reason_code="WRONG_AMOUNT", reason="Synthetic wrong amount correction")
        self.cash(account)
        summary = get_inr_principal_summary(account)
        self.assertEqual((summary.received, summary.corrected, summary.principal_recorded),
                         (Decimal("1000"), Decimal("500"), Decimal("500")))
        self.assertFalse(summary.needs_review)

    def test_test_mock_still_rejected_before_provider(self):
        account = self.account(True)
        for name, mode in (("mock", ""), ("razorpay", "test")):
            with self.assertRaises(ValidationError):
                initiate_contribution(scheme_account=account, amount=Decimal("500"), payment_gateway=name, gateway_mode=mode)
        gateway = self.gateway()
        gateway.mode = "test"
        with self.assertRaises(ValidationError):
            initiate_razorpay_contribution(scheme_account=self.account(), amount=Decimal("500"), gateway=gateway)
        gateway.create_order.assert_not_called()
        self.assertFalse(Contribution.objects.exists())

    def test_changed_contract_blocks_collection_with_either_intake_flag(self):
        account = self.account(True)
        type(account).objects.filter(pk=account.pk).update(plan_name_snapshot="Unaccepted changed terms")
        account.plan_name_snapshot = "Unaccepted changed terms"
        self.ready.stop()
        for enabled in (False, True):
            with override_settings(CONFIGURED_PLANS_ENABLED=enabled):
                with self.assertRaises(ValidationError):
                    self.cash(account)
                with self.assertRaises(ValidationError):
                    initiate_razorpay_contribution(scheme_account=account, amount=Decimal("500"), gateway=self.gateway())
        self.assertFalse(Contribution.objects.exists())


@override_settings(IN_STORE_CASH_CONTRIBUTIONS_ENABLED=True, PAYMENT_INITIATION_KILL_SWITCH=False)
class IndependentCashConcurrencyTests(TransactionTestCase):
    def test_optional_period_cannot_be_paid_twice_concurrently(self):
        owner, customer = make_owner(), make_customer()
        PaymentOperationsControl.objects.get_or_create(pk=1)
        account = stored_future(owner, customer, independent_values(accumulation="INR_PURCHASE_CREDIT",
            frequency_rule="ONCE_PER_PERIOD", period_basis="ANNIVERSARY", allow_contributions_after_eligibility=True))
        barrier = Barrier(2)
        def submit():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                try:
                    record_in_store_cash_contribution(scheme_account=account, amount=Decimal("500"),
                        expected_scheme_rate_id=None, received_by=owner, idempotency_key=uuid.uuid4())
                    return "recorded"
                except ValidationError:
                    return "blocked"
            finally:
                close_old_connections()
        with patch("django.utils.timezone.now", return_value=NOW), patch("schemes.plan_policies.require_current_payment_workflow"):
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = [f.result(timeout=30) for f in (pool.submit(submit), pool.submit(submit))]
        self.assertCountEqual(results, ["recorded", "blocked"])
        self.assertEqual(InrPrincipalReceipt.objects.count(), 1)
