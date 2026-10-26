"""Independent eligibility reads on synthetic contracts; no release-gate bypass."""
from datetime import datetime, time, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext

from schemes.agreement_eligibility import get_independent_eligibility
from schemes.instalments import AGREEMENT_TIMEZONE
from schemes.models import (Contribution, InrPrincipalReceipt, InStoreCashContributionReversal,
    InstalmentReservation, MetalAllocation, PaymentWebhookEvent, SchemeAccount)
from schemes.payments import PaymentGatewayError
from schemes.selectors import (eligibility_reminder_terms, get_customer_payment_availability,
    get_upcoming_monthly_completion_accounts)
from schemes.services import publish_scheme_rate, reverse_in_store_cash_contribution
from schemes.tests import test_independent_payment_entry as entry
from schemes.tests.test_independent_instalment_reviews import IndependentReviewFixture, instant
from schemes.tests.test_independent_instalment_ledger import NOW


BENEFIT = dict(eligibility_policy="CALENDAR", duration_months=12, required_count=2,
    missed_payment_policy="LOSE_UNEARNED_BENEFIT", max_extension_months=None,
    benefit_policy="VA_DISCOUNT", benefit_percentage=Decimal("5"), benefit_cap_inr=Decimal("500"),
    benefit_qualification="REQUIRED_SCHEDULE", benefit_on_miss="DISQUALIFY_UNEARNED",
    eligible_charge_definition="Making charges excluding taxes")


@override_settings(IN_STORE_CASH_CONTRIBUTIONS_ENABLED=True, PAYMENT_INITIATION_KILL_SWITCH=False)
class IndependentEligibilityTests(IndependentReviewFixture, TestCase):
    account = entry.IndependentPaymentEntryTests.account

    def pay(self, account, number):
        period = account.instalment_periods.get(number=number)
        at = max(NOW, instant(period.starts_on))
        with patch("django.utils.timezone.now", return_value=at):
            values = {}
            if account.metal_grade_id:
                rate = publish_scheme_rate(metal_grade=account.metal_grade, rate_per_gram=Decimal("10000"), published_by=self.owner)
                values["expected_scheme_rate_id"] = rate.pk
            c = self.cash(account, **values)
        return c, at

    def evaluate(self, account, at):
        with patch("django.utils.timezone.now", return_value=at):
            return get_independent_eligibility(account)

    def test_count_only_is_immediate_but_both_waits_for_duration_and_period_end(self):
        for metal in (False, True):
            for basis in ("CALENDAR_MONTH", "ANNIVERSARY"):
                for eligibility, duration in (("COUNT", None), ("CALENDAR_AND_COUNT", 1), ("CALENDAR_AND_COUNT", 18)):
                    with self.subTest(metal=metal, basis=basis, eligibility=eligibility, duration=duration):
                        account = self.account(True, metal, required_count=2, period_basis=basis,
                            eligibility_policy=eligibility, duration_months=duration)
                        original = SchemeAccount.objects.values().get(pk=account.pk)
                        self.pay(account, 1)
                        _, at = self.pay(account, 2)
                        result = self.evaluate(account, at)
                        self.assertEqual(result.qualified_payments, 2)
                        self.assertEqual(result.count_verified_at, at)
                        self.assertTrue(result.positive_entitlement)
                        if eligibility == "COUNT":
                            self.assertTrue(result.policy_eligible)
                            self.assertIsNone(result.original_date)
                            self.assertEqual(result.completion_date, at.date())
                        else:
                            self.assertEqual(result.state, "WAITING_PERIOD_END")
                            end = max(account.eligible_from, account.instalment_periods.get(number=2).ends_before)
                            boundary = datetime.combine(end, time.min, AGREEMENT_TIMEZONE)
                            self.assertEqual(result.completion_date, end)
                            self.assertFalse(self.evaluate(account, boundary - timedelta(microseconds=1)).policy_eligible)
                            self.assertTrue(self.evaluate(account, boundary).policy_eligible)
                        self.assertEqual(SchemeAccount.objects.values().get(pk=account.pk), original)

    def test_optional_anytime_needs_real_entitlement_and_has_no_invented_date(self):
        for metal in (False, True):
            account = self.account(metal=metal)
            self.assertEqual(get_independent_eligibility(account).state, "NO_ENTITLEMENT")
            c = self.cash(account)
            result = get_independent_eligibility(account)
            self.assertTrue(result.policy_eligible)
            self.assertIsNone(result.original_date)
            self.assertIsNone(result.completion_date)
            self.assertIsNone(result.required_payments)
            with patch.object(InStoreCashContributionReversal._meta.get_field("reversed_at"), "_get_default", lambda: NOW):
                reverse_in_store_cash_contribution(contribution=c, processed_by=self.owner,
                    reason="Duplicate receipt corrected", reason_code="WRONG_AMOUNT")
            self.assertEqual(get_independent_eligibility(account).state, "NO_ENTITLEMENT")

    def test_optional_duration_is_not_a_required_count_or_free_entitlement(self):
        for metal in (False, True):
            account = self.account(metal=metal, eligibility_policy="CALENDAR", duration_months=1)
            at = datetime.combine(account.eligible_from, time.min, AGREEMENT_TIMEZONE)
            self.assertEqual(self.evaluate(account, at).state, "NO_ENTITLEMENT")
            self.cash(account)
            self.assertEqual(self.evaluate(account, at - timedelta(microseconds=1)).state, "WAITING_DURATION")
            self.assertTrue(self.evaluate(account, at).policy_eligible)
            self.assertFalse(account.instalment_periods.exists())

    def test_benefit_schedule_miss_does_not_extend_principal_maturity_or_award_benefit(self):
        for metal in (False, True):
            account = self.account(True, metal, **BENEFIT)
            self.pay(account, 1)
            at = datetime.combine(account.eligible_from, time.min, AGREEMENT_TIMEZONE)
            result = self.evaluate(account, at)
            self.assertTrue(result.policy_eligible)
            self.assertTrue(result.rule_satisfied)
            self.assertTrue(result.benefit_review_required)
            self.assertEqual(result.qualified_payments, 1)
            self.assertIsNone(result.count_verified_at)
            self.assertEqual(result.completion_date, account.eligible_from)
            self.assertIn("not a bonus or discount award", result.message)

    def test_benefit_outage_hold_is_review_not_a_new_principal_date(self):
        account = self.account(True, **BENEFIT)
        self.pay(account, 1)
        self.hold(account, 2)
        result = self.evaluate(account, instant(account.eligible_from))
        self.assertEqual(result.state, "REVIEW")
        self.assertTrue(result.rule_satisfied)
        self.assertEqual(result.original_date, account.eligible_from)
        self.assertEqual(result.completion_date, account.eligible_from)

    def test_replacements_and_exhaustion_use_required_count_not_duration(self):
        for metal in (False, True):
            account = self.account(True, metal, required_count=2)
            self.pay(account, 2)
            _, at = self.pay(account, 3)
            self.assertTrue(self.evaluate(account, at).policy_eligible)
            other = self.account(True, metal, required_count=2)
            self.pay(other, 1)
            at = instant(other.instalment_periods.order_by("number").last().ends_before)
            result = self.evaluate(other, at)
            self.assertEqual(result.state, "DISCONTINUATION_REVIEW")
            self.assertTrue(result.positive_entitlement)

    def test_acknowledged_compensation_counts_only_after_actual_verified_payment(self):
        account = self.account(True, required_count=2)
        resolution = self.resolve(self.hold(account))
        self.pay(account, 2)
        at = instant(resolution.compensation_period.starts_on)
        self.assertFalse(self.evaluate(account, at).policy_eligible)
        _, at = self.pay(account, resolution.compensation_period.number)
        result = self.evaluate(account, at)
        self.assertTrue(result.policy_eligible)
        self.assertEqual(result.qualified_payments, 2)
        self.assertEqual(result.completion_date, at.date())
        self.assertIsNone(result.original_date)

    def test_count_reversal_removes_qualification_without_erasing_evidence(self):
        account = self.account(True, required_count=2)
        self.pay(account, 1)
        c, at = self.pay(account, 2)
        with patch("django.utils.timezone.now", return_value=at), patch.object(
                InStoreCashContributionReversal._meta.get_field("reversed_at"), "_get_default", lambda: at):
            reverse_in_store_cash_contribution(contribution=c, processed_by=self.owner,
                reason="Duplicate receipt corrected", reason_code="WRONG_AMOUNT")
            result = get_independent_eligibility(account)
        self.assertEqual(result.state, "COLLECTING")
        self.assertEqual(result.qualified_payments, 1)
        self.assertIsNone(result.count_verified_at)
        self.assertEqual(Contribution.objects.count(), 2)
        self.assertEqual(InrPrincipalReceipt.objects.count(), 2)

    def test_delayed_verification_never_backdates_count_only_rights(self):
        for metal in (False, True):
            account = self.account(True, metal, required_count=1)
            c = self.online(account)
            self.assertFalse(get_independent_eligibility(account).policy_eligible)
            self.capture(c)
            verified = NOW + timedelta(minutes=12)
            result = self.evaluate(account, verified)
            self.assertTrue(result.policy_eligible)
            self.assertEqual(result.count_verified_at, verified)
            # Current DB evidence cannot be replayed as eligibility before it was known.
            self.assertEqual(self.evaluate(account, verified - timedelta(microseconds=1)).state, "REVIEW")

    def test_unknown_timing_and_ambiguous_orders_do_not_qualify(self):
        account = self.account(True, required_count=1)
        c = self.online(account)
        self.capture(c, at=None)
        result = self.evaluate(account, NOW + timedelta(minutes=12))
        self.assertEqual(result.state, "REVIEW")
        self.assertEqual(result.qualified_payments, 0)
        other = self.account(True, required_count=1)
        gateway = self.gateway()
        gateway.create_order.side_effect = PaymentGatewayError("Uncertain provider response")
        from schemes.services import initiate_razorpay_contribution
        with self.assertRaises(PaymentGatewayError):
            initiate_razorpay_contribution(scheme_account=other, amount=Decimal("500"), gateway=gateway)
        self.assertEqual(get_independent_eligibility(other).state, "REVIEW")

    def test_optional_live_capture_and_pending_or_duplicate_exposure(self):
        for metal in (False, True):
            account = self.account(metal=metal)
            c = self.online(account)
            self.assertFalse(get_independent_eligibility(account).policy_eligible)
            self.capture(c)
            at = NOW + timedelta(minutes=12)
            self.assertTrue(self.evaluate(account, at).policy_eligible)
            event = PaymentWebhookEvent.objects.filter(contribution=c).first()
            PaymentWebhookEvent.objects.filter(pk=event.pk).update(status="FAILED")
            self.assertEqual(self.evaluate(account, at).state, "REVIEW")

    def test_qualification_without_allocated_principal_never_confirms_eligibility(self):
        account = self.account(True, True, required_count=1)
        c = self.online(account)
        with patch("schemes.services.allocate_metal", side_effect=ValidationError("Allocation unavailable")):
            self.capture(c)
        result = self.evaluate(account, NOW + timedelta(minutes=12))
        self.assertEqual(result.qualified_payments, 1)
        self.assertTrue(result.rule_satisfied)
        self.assertEqual(result.state, "REVIEW")
        self.assertFalse(result.policy_eligible)

    def test_invalid_contract_schedule_source_or_decision_fails_closed(self):
        for metal in (False, True):
            account = self.account(True, metal, required_count=1)
            c = self.cash(account)
            if metal:
                MetalAllocation.objects.filter(contribution=c).update(quantity=Decimal("0.060000"))
            else:
                InrPrincipalReceipt.objects.filter(contribution=c).update(amount=Decimal("600"))
            self.assertEqual(get_independent_eligibility(account).state, "REVIEW")
        account = self.account(True, required_count=1)
        c = self.cash(account)
        InstalmentReservation.objects.filter(contribution=c).update(state="REVERSED")
        self.assertEqual(get_independent_eligibility(account).state, "REVIEW")
        other = self.account(True, required_count=1)
        SchemeAccount.objects.filter(pk=other.pk).update(required_count_snapshot=2)
        self.assertEqual(get_independent_eligibility(other).state, "REVIEW")

    def test_future_allocation_and_qualification_evidence_cannot_create_current_rights(self):
        account = self.account(True, True, required_count=1)
        c = self.cash(account)
        MetalAllocation.objects.filter(contribution=c).update(created_at=NOW + timedelta(seconds=1))
        self.assertEqual(get_independent_eligibility(account).state, "REVIEW")
        other = self.account(True, required_count=1)
        c = self.cash(other)
        c.instalment_reservation.decisions.filter(state="QUALIFIED").update(created_at=NOW + timedelta(seconds=1))
        self.assertEqual(get_independent_eligibility(other).state, "REVIEW")

    def test_accepted_closure_requires_disposition_review_not_a_second_eligibility_claim(self):
        from schemes.tests.test_inr_settlements import accepted_request
        account = self.account()
        self.cash(account)
        accepted_request(account, self.owner)
        self.assertEqual(get_independent_eligibility(account).state, "CLOSURE_PENDING")

    def test_test_mode_source_never_grants_anytime_entitlement(self):
        account = self.account(metal=True)
        c = self.cash(account)
        # Deliberate corruption fixture, never an operational transition.
        Contribution.objects.filter(pk=c.pk).update(payment_gateway="razorpay", payment_channel="RAZORPAY", gateway_mode="test")
        self.assertEqual(get_independent_eligibility(account).state, "REVIEW")

    def test_future_as_of_is_not_permission_and_reads_do_not_write(self):
        account = self.account(True, required_count=1)
        self.cash(account)
        for as_of in (account.start_date - timedelta(days=1), account.start_date + timedelta(days=1), NOW):
            with self.assertRaises(ValidationError):
                get_independent_eligibility(account, as_of=as_of)
        original = SchemeAccount.objects.values().get(pk=account.pk)
        with CaptureQueriesContext(connection) as queries:
            self.assertTrue(account.independent_eligibility.policy_eligible)
        self.assertFalse(any(q["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")) for q in queries))
        self.assertEqual(SchemeAccount.objects.values().get(pk=account.pk), original)

    def test_readable_progress_does_not_enable_payments_settlement_or_legacy_reminders(self):
        account = self.account(True, required_count=1)
        self.cash(account)
        for enabled in (False, True):
            with override_settings(CONFIGURED_PLANS_ENABLED=enabled):
                self.assertTrue(get_independent_eligibility(account).policy_eligible)
                self.assertFalse(get_customer_payment_availability(account).allowed)
                with self.assertRaises(ValidationError):
                    account.full_clean()
                self.assertIsNone(eligibility_reminder_terms(account, as_of=account.start_date))
        end = account.instalment_periods.get(number=1).ends_before
        self.assertNotIn(account, get_upcoming_monthly_completion_accounts(as_of=end-timedelta(days=1), lead_days=(1,)))

    def test_terminal_and_stale_account_objects_do_not_resurrect_entitlement(self):
        account = self.account()
        SchemeAccount.objects.filter(pk=account.pk).update(status="CANCELLED")
        self.assertEqual(get_independent_eligibility(account).state, "CANCELLED")
        SchemeAccount.objects.filter(pk=account.pk).update(status="REDEEMED")
        self.assertEqual(get_independent_eligibility(account).state, "CLOSED")
        SchemeAccount.objects.filter(pk=account.pk).update(status="CLOSURE_PENDING")
        self.assertEqual(get_independent_eligibility(account).state, "CLOSURE_PENDING")
