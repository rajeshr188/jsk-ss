"""Historical cost is a read-only exact-grade metric, never a remaining-cost ledger."""
import uuid
from decimal import Decimal, ROUND_HALF_UP
from types import SimpleNamespace

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from schemes.models import Contribution, MetalAllocation, Redemption, InStoreCashContributionReversal
from schemes.selectors import get_metal_acquisition_summary, get_metal_balance
from schemes.services import (enroll_customer, publish_scheme_rate, record_in_store_cash_contribution,
    reverse_in_store_cash_contribution, complete_redemption)
from schemes.tests.grade_helpers import grade_for_mode
from schemes.tests.test_audit_exceptions import make_customer, make_paid_contribution
from schemes.tests import test_in_store_cash_contributions as cash_cases


@override_settings(DEBUG=False, PAYMENT_INITIATION_KILL_SWITCH=False,
    IN_STORE_CASH_CONTRIBUTIONS_ENABLED=True, IN_STORE_CASH_REVERSAL_HOURS=24)
class MetalAcquisitionTests(TestCase):
    setUp = cash_cases.InStoreCashContributionTests.setUp

    def pay(self, amount, rate, account=None):
        account = account or self.account
        published = publish_scheme_rate(metal_grade=account.metal_grade,
            rate_per_gram=Decimal(rate), published_by=self.owner)
        return record_in_store_cash_contribution(scheme_account=account, amount=Decimal(amount),
            expected_scheme_rate_id=published.pk, received_by=self.owner, idempotency_key=uuid.uuid4())

    def test_weighted_cost_uses_total_paid_and_full_recorded_grams_in_one_read(self):
        self.pay("1000", "10000")
        self.pay("3000", "15000")
        before = [list(m.objects.values()) for m in (Contribution, MetalAllocation, Redemption)]
        with self.assertNumQueries(1):
            summary = get_metal_acquisition_summary(self.account)
        self.assertEqual(summary.paid_amount, Decimal("4000.00"))
        self.assertEqual(summary.allocated_grams, Decimal("0.300000"))
        self.assertEqual(summary.average_cost_per_gram, Decimal("13333.33"))
        self.assertNotEqual(summary.average_cost_per_gram, Decimal("12500.00"))
        self.assertEqual(before, [list(m.objects.values()) for m in (Contribution, MetalAllocation, Redemption)])

    def test_cash_correction_excludes_both_amount_and_grams_without_erasing_history(self):
        first = self.pay("1000", "10000")
        second = self.pay("3000", "15000")
        reverse_in_store_cash_contribution(contribution=second, processed_by=self.owner,
            reason_code=InStoreCashContributionReversal.ReasonCode.WRONG_AMOUNT,
            reason="Synthetic full source correction")
        self.assertEqual(get_metal_acquisition_summary(self.account).average_cost_per_gram, Decimal("10000.00"))
        self.assertEqual(MetalAllocation.objects.count(), 2)
        reverse_in_store_cash_contribution(contribution=first, processed_by=self.owner,
            reason_code=InStoreCashContributionReversal.ReasonCode.WRONG_AMOUNT,
            reason="Synthetic remaining source correction")
        self.assertIsNone(get_metal_acquisition_summary(self.account).average_cost_per_gram)
        self.assertEqual(MetalAllocation.objects.count(), 2)

    def test_no_allocations_or_unallocated_pending_failed_attempts_have_no_average(self):
        self.assertIsNone(get_metal_acquisition_summary(self.account).average_cost_per_gram)
        make_paid_contribution(self.account, status=Contribution.Status.PAID_UNALLOCATED)
        for status in (Contribution.Status.PENDING, Contribution.Status.FAILED):
            Contribution.objects.create(scheme_account=self.account, amount=Decimal("100"),
                contribution_period=timezone.localdate().replace(day=1), frequency_rule_snapshot="FLEXIBLE",
                payment_gateway="mock", status=status)
        summary = get_metal_acquisition_summary(self.account)
        self.assertIsNone(summary.average_cost_per_gram)
        self.assertEqual(summary.paid_amount, 0)
        self.assertEqual(summary.allocated_grams, 0)

    def test_account_grade_and_metal_are_never_pooled(self):
        self.pay("1000", "10000")
        for mode, code, rate in (("GOLD", "GOLD_22K_916", "12000"), ("SILVER", "SILVER_999", "100")):
            grade = grade_for_mode(self.plan, mode, code=code)
            account = enroll_customer(customer=self.customer, plan=self.plan, metal_grade=grade,
                performed_by=self.owner, reason="Synthetic separate grade agreement")
            self.pay("1200", rate, account)
            self.assertEqual(get_metal_acquisition_summary(account).average_cost_per_gram, Decimal(rate))
        self.assertEqual(get_metal_acquisition_summary(self.account).average_cost_per_gram, Decimal("10000.00"))

    def test_redemption_changes_remaining_grams_but_not_historical_acquisition_cost(self):
        self.pay("1000", "10000")
        self.pay("3000", "15000")
        before = get_metal_acquisition_summary(self.account)
        complete_redemption(scheme_account=self.account, settlement_type=Redemption.SettlementType.JEWELLERY_PURCHASE,
            amount=Decimal("0.300000"), processed_by=self.owner, idempotency_key=uuid.uuid4(),
            external_reference="Synthetic jewellery invoice")
        self.assertEqual(get_metal_balance(self.account), 0)
        self.assertEqual(get_metal_acquisition_summary(self.account), before)

    def test_customer_detail_displays_effective_cost_without_rounding_grams_first(self):
        contribution = self.pay("150", "14667")
        grams = contribution.metal_allocation.quantity
        expected = (contribution.amount / grams).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        self.assertEqual(get_metal_acquisition_summary(self.account).average_cost_per_gram, expected)
        self.assertEqual(expected, Decimal("14667.06"))
        self.client.force_login(self.customer.user)
        url = reverse("schemes:my_scheme_detail", args=[self.account.scheme_number])
        response = self.client.get(url)
        self.assertContains(response, "Average acquisition cost")
        self.assertContains(response, "14,667.06/g")
        self.assertContains(response, "Redemptions do not change this historical average")
        self.client.force_login(make_customer().user)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.logout()
        self.assertEqual(self.client.get(url).status_code, 302)

    def test_non_metal_accounts_have_no_metric_or_database_read(self):
        for mode in ("CASH", "INR_CREDIT"):
            with self.subTest(mode=mode), self.assertNumQueries(0):
                self.assertIsNone(get_metal_acquisition_summary(SimpleNamespace(savings_mode=mode, metal_grade_id=None)))
