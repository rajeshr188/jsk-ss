"""Read-only P3 projections using actual payment services on gated fixtures."""
from datetime import datetime, time, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import connection
from django.template.loader import render_to_string
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from schemes.instalment_selectors import get_monthly_eligibility
from schemes.instalments import AGREEMENT_TIMEZONE
from schemes.models import Contribution, InstalmentReservation, MetalAllocation, SchemeAccount
from schemes.payments import PaymentGatewayError
from schemes.selectors import (get_customer_payment_availability, get_customer_plan_next_action,
    get_metal_balance, get_owner_settlement_review_count,
    get_redemption_eligibility_summary, get_upcoming_eligibility_accounts)
from schemes.services import publish_scheme_rate, reverse_in_store_cash_contribution
from schemes.tests.test_instalment_outages import OutageFixture
from schemes.tests.test_instalment_payments import NOW


@override_settings(IN_STORE_CASH_CONTRIBUTIONS_ENABLED=True, PAYMENT_GATEWAY="razorpay",
    RAZORPAY_MODE="live", RAZORPAY_KEY_ID="rzp_live_fixture", RAZORPAY_KEY_SECRET="fixture",
    RAZORPAY_WEBHOOK_SECRET="fixture-webhook")
class MonthlyEligibilityTests(OutageFixture, TestCase):
    @override_settings(RAZORPAY_WEBHOOK_SECRET="")
    def test_missing_webhook_secret_blocks_payment_availability(self):
        availability = get_customer_payment_availability(self.account)
        self.assertFalse(availability.allowed)
        self.assertEqual(availability.code, "UNCONFIGURED")
        self.gateway.create_order.assert_not_called()

    def instant(self, number, *, end=False):
        period = self.account.instalment_periods.get(number=number)
        return datetime.combine(period.ends_before if end else period.starts_on,
                                time.min if end else time(12), AGREEMENT_TIMEZONE)

    def pay_periods(self, numbers):
        last = None
        for number in numbers:
            with patch("django.utils.timezone.now", return_value=self.instant(number)):
                self.rate = publish_scheme_rate(metal_grade=self.grade, rate_per_gram=Decimal("10000"), published_by=self.owner)
                last = self.cash()
        return last

    def test_calendar_date_alone_never_completes_monthly_agreement(self):
        with patch("django.utils.timezone.now", return_value=self.instant(12, end=True)):
            result = get_monthly_eligibility(self.account)
            self.assertEqual(result.state, "COLLECTING")
            self.assertIsNone(result.forecast_date)
            self.assertFalse(result.policy_eligible)
            self.assertEqual(self.account.effective_status, "ACTIVE")
            self.assertFalse(get_redemption_eligibility_summary().eligible_now)
            self.assertEqual(get_redemption_eligibility_summary().configured, (self.account,))

    def test_twelve_payments_wait_for_final_period_end_in_india_time(self):
        self.pay_periods(range(1, 13))
        boundary = self.instant(12, end=True)
        with patch("django.utils.timezone.now", return_value=boundary - timedelta(microseconds=1)):
            result = get_monthly_eligibility(self.account)
            self.assertEqual(result.state, "WAITING_PERIOD_END")
            self.assertEqual(result.qualified_payments, 12)
            self.assertFalse(get_customer_payment_availability(self.account).allowed)
        with patch("django.utils.timezone.now", return_value=boundary):
            result = get_monthly_eligibility(self.account)
            self.assertTrue(result.policy_eligible)
            self.assertEqual(result.completion_date, boundary.date())
            self.assertIn("showroom settlement review", self.account.effective_status_label)
            self.assertFalse(get_customer_plan_next_action(self.account)["can_pay"])

    def test_missed_period_extends_forecast_and_payment_beyond_original_date(self):
        self.pay_periods(range(2, 13))
        original = self.account.eligible_from
        with patch("django.utils.timezone.now", return_value=self.instant(13)):
            result = get_monthly_eligibility(self.account)
            self.assertEqual(result.qualified_payments, 11)
            self.assertEqual(result.forecast_date, self.instant(13, end=True).date())
            self.assertIsNone(result.completion_date)
            self.assertTrue(get_customer_payment_availability(self.account).allowed)
            self.assertTrue(get_customer_plan_next_action(self.account)["can_pay"])
        self.pay_periods([13])
        with patch("django.utils.timezone.now", return_value=self.instant(13, end=True)):
            self.assertTrue(get_monthly_eligibility(self.account).policy_eligible)
        self.account.refresh_from_db()
        self.assertEqual(self.account.eligible_from, original)

    def test_completed_count_blocks_extra_payment_before_completion_date(self):
        self.pay_periods(range(1, 13))
        with patch("django.utils.timezone.now", return_value=self.instant(12)):
            self.assertEqual(get_customer_payment_availability(self.account).code, "INSTALMENT_WAITING_PERIOD_END")

    def test_exhaustion_preserves_money_and_grams_and_never_closes_account(self):
        self.cash()
        before = (get_metal_balance(self.account), list(Contribution.objects.values()), list(MetalAllocation.objects.values()))
        with patch("django.utils.timezone.now", return_value=self.instant(15, end=True)):
            result = get_monthly_eligibility(self.account)
            self.assertEqual(result.state, "DISCONTINUATION_REVIEW")
            self.assertFalse(get_customer_payment_availability(self.account).allowed)
        self.assertEqual(before, (get_metal_balance(self.account), list(Contribution.objects.values()), list(MetalAllocation.objects.values())))
        self.account.refresh_from_db()
        self.assertEqual(self.account.status, "ACTIVE")

    def test_outage_hold_prevents_forecast_and_payment_without_losing_count(self):
        self.cash()
        self.hold()
        result = get_monthly_eligibility(self.account)
        self.assertEqual(result.state, "REVIEW")
        self.assertEqual(result.qualified_payments, 1)
        self.assertIsNone(result.forecast_date)
        self.assertFalse(get_customer_plan_next_action(self.account)["can_pay"])

    def test_compensation_is_only_counted_after_acknowledged_amendment(self):
        self.pay_periods(range(2, 12))
        # No invented compensation: the original 15-window end stays authoritative.
        at = self.instant(14, end=True)
        with patch("django.utils.timezone.now", return_value=at):
            self.assertIsNone(get_monthly_eligibility(self.account).forecast_date)
        hold = self.hold(1)
        # A genuine amendment records owner evidence and acknowledgement through
        # the existing service, before the extra window starts.
        from schemes.instalment_outages import resolve_instalment_outage
        with patch("django.utils.timezone.now", return_value=at):
            resolve_instalment_outage(**self.values(hold, customer_acknowledged_at=at))
            result = get_monthly_eligibility(self.account)
            self.assertEqual(result.forecast_date, self.instant(16, end=True).date())
            self.assertEqual(result.required_payments, 12)
            self.assertEqual(result.qualified_payments, 10)

    def test_cash_reversal_removes_qualification_not_historical_evidence(self):
        c = self.pay_periods(range(1, 13))
        with patch("django.utils.timezone.now", return_value=self.instant(12)):
            reverse_in_store_cash_contribution(contribution=c, processed_by=self.owner,
                reason="Duplicate physical receipt corrected", reason_code="WRONG_AMOUNT")
            result = get_monthly_eligibility(self.account)
            self.assertEqual(result.qualified_payments, 11)
            self.assertIsNone(result.completion_date)
            self.assertEqual(result.state, "COLLECTING")
        self.assertEqual(Contribution.objects.count(), 12)

    def test_reserved_checkout_is_resumable_not_a_new_payment_or_forecast(self):
        self.online()
        self.assertEqual(get_monthly_eligibility(self.account).state, "PAYMENT_PENDING")
        self.assertTrue(get_customer_payment_availability(self.account).allowed)
        self.assertFalse(get_customer_plan_next_action(self.account)["can_pay"])
        with patch("django.utils.timezone.now", return_value=NOW + timedelta(minutes=11)):
            self.assertFalse(get_customer_payment_availability(self.account).allowed)

    def test_missing_timing_blocks_eligibility_and_payment(self):
        c = self.online()
        self.webhook(c, captured_at=None)
        result = get_monthly_eligibility(self.account)
        self.assertEqual(result.state, "REVIEW")
        self.assertEqual(result.qualified_payments, 0)
        self.assertFalse(get_customer_payment_availability(self.account).allowed)

    def test_ambiguous_order_is_review_not_a_missed_or_free_period(self):
        self.gateway.create_order.side_effect = PaymentGatewayError("Uncertain provider response")
        with self.assertRaises(PaymentGatewayError):
            self.online()
        result = get_monthly_eligibility(self.account)
        self.assertEqual(result.state, "REVIEW")
        self.assertEqual(result.qualified_payments, 0)
        self.assertIsNone(result.forecast_date)
        self.assertFalse(get_customer_payment_availability(self.account).allowed)

    def test_duplicate_capture_hold_keeps_original_qualified_count(self):
        from schemes.tests.test_instalment_capture_boundaries import CaptureFixture
        c = self.online()
        with patch("django.utils.timezone.now", return_value=NOW + timedelta(minutes=1)):
            CaptureFixture.capture(self, c)
            CaptureFixture.capture(self, c, payment_id="pay_duplicate", event_id="duplicate")
        result = get_monthly_eligibility(self.account)
        self.assertEqual(result.state, "REVIEW")
        self.assertEqual(result.qualified_payments, 1)
        self.assertEqual(MetalAllocation.objects.count(), 1)
        self.assertFalse(get_customer_payment_availability(self.account).allowed)

    @override_settings(RAZORPAY_MODE="test", RAZORPAY_KEY_ID="rzp_test_fixture")
    def test_test_checkout_is_not_offered_for_real_monthly_qualification(self):
        self.assertEqual(get_customer_payment_availability(self.account).code, "INSTALMENT_REAL_PAYMENT_REQUIRED")

    def test_allocation_failure_does_not_erase_qualified_payment(self):
        c = self.online()
        with patch("schemes.services.allocate_metal", side_effect=ValidationError("Allocation fixture")):
            self.webhook(c)
        result = get_monthly_eligibility(self.account)
        self.assertEqual(result.qualified_payments, 1)
        self.assertTrue(result.allocation_pending)
        self.assertFalse(get_customer_payment_availability(self.account).allowed)

    def test_corrupt_projection_and_incomplete_schedule_fail_closed(self):
        c = self.cash()
        InstalmentReservation.objects.filter(contribution=c).update(state="REVERSED")
        self.assertEqual(get_monthly_eligibility(self.account).state, "REVIEW")
        self.assertFalse(get_customer_payment_availability(self.account).allowed)
        with patch("schemes.instalment_selectors.validated_instalment_periods", side_effect=ValidationError("Missing schedule")):
            self.assertEqual(get_monthly_eligibility(self.account).state, "REVIEW")

    def test_before_start_and_empty_forecast_are_read_only(self):
        before = SchemeAccount.objects.values().get(pk=self.account.pk)
        with CaptureQueriesContext(connection) as queries:
            result = get_monthly_eligibility(self.account, as_of=self.account.start_date - timedelta(days=1))
        self.assertEqual(result.state, "NOT_STARTED")
        self.assertEqual(result.forecast_date, self.account.eligible_from)
        self.assertFalse(any(q["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")) for q in queries))
        self.assertEqual(before, SchemeAccount.objects.values().get(pk=self.account.pk))

    def test_monthly_original_date_does_not_generate_legacy_reminder(self):
        as_of = self.account.eligible_from - timedelta(days=7)
        self.assertNotIn(self.account, get_upcoming_eligibility_accounts(as_of=as_of, lead_days=(7,)))

    def test_agreement_basis_displays_conditional_not_guaranteed_date(self):
        content = render_to_string("schemes/includes/agreement_basis.html", {"scheme_account": self.account})
        self.assertIn("Recorded qualifying payments: 0 of 12", content)
        self.assertIn("Conditional forecast:", content)
        self.assertIn("Settlement uses the full exact-grade balance", content)
        self.assertIn("qualifying payments may continue in available approved extension windows", content)
        self.assertNotIn("Contributions after eligibility: not permitted", content)

    def test_owner_today_does_not_offer_monthly_original_date_as_settlement(self):
        with patch("django.utils.timezone.now", return_value=self.instant(12, end=True)):
            self.client.force_login(self.owner)
            self.assertEqual(get_owner_settlement_review_count(), 0)
            response = self.client.get(reverse("schemes:owner_today"))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context["settlement_due_count"], 0)

    def test_completed_monthly_contract_cannot_open_or_post_legacy_redemption_form(self):
        self.pay_periods(range(1, 13))
        url = reverse("schemes:redemption_create", args=[self.account.scheme_number])
        with patch("django.utils.timezone.now", return_value=self.instant(12, end=True)):
            self.client.force_login(self.owner)
            self.assertTrue(get_monthly_eligibility(self.account).policy_eligible)
            self.assertGreater(get_metal_balance(self.account), 0)
            self.assertEqual(get_owner_settlement_review_count(), 0)
            for method in (self.client.get, self.client.post):
                self.assertEqual(method(url).status_code, 404)
        self.assertFalse(self.account.redemptions.exists())
