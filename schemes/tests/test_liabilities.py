from datetime import date, datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from schemes.models import (
    Contribution,
    MetalAllocation,
    RateSnapshot,
    SchemeAccount,
    SchemePlan,
)
from schemes.rates import MetalRateQuote
from schemes.selectors import (
    get_owner_activity_summary,
    get_owner_liability_summary,
)
from schemes.services import create_customer, enroll_customer


class FixedRateProvider:
    rates = {
        RateSnapshot.Metal.GOLD: Decimal("14000.0000"),
        RateSnapshot.Metal.SILVER: Decimal("155.0000"),
    }

    def get_rate(self, metal):
        return MetalRateQuote(
            metal=metal,
            provider="fixed-test",
            provider_timestamp=timezone.now(),
            provider_rate=self.rates[metal],
            applied_rate=self.rates[metal],
            purity=Decimal("0.9999"),
        )


def make_liability_accounts():
    customer = create_customer(
        full_name="Liability Customer",
        email="liability@example.com",
        mobile_number="9000000050",
        password="customer-password-strong",
    )
    plan = SchemePlan.objects.create(
        name="Flexible Savings",
        code="LIABILITY-FLEX",
        amount_rule=SchemePlan.AmountRule.VARIABLE,
        frequency_rule=SchemePlan.FrequencyRule.FLEXIBLE,
        minimum_contribution=Decimal("100.00"),
        maximum_contribution=Decimal("100000.00"),
    )
    accounts = {}
    for mode in SchemeAccount.SavingsMode.values:
        accounts[mode] = enroll_customer(
            customer=customer,
            plan=plan,
            savings_mode=mode,
            start_date=date(2026, 1, 1),
        )
    return customer, accounts


def make_contribution(account, amount, status, reference, paid_at=None):
    payment_succeeded = status in {
        Contribution.Status.PAID,
        Contribution.Status.PAID_UNALLOCATED,
    }
    return Contribution.objects.create(
        scheme_account=account,
        amount=amount,
        contribution_period=date(2026, 8, 1),
        frequency_rule_snapshot=SchemePlan.FrequencyRule.FLEXIBLE,
        status=status,
        payment_gateway="test",
        gateway_reference=reference if payment_succeeded else None,
        paid_at=paid_at if payment_succeeded else None,
    )


def make_allocation(contribution, metal, quantity, historical_rate):
    snapshot = RateSnapshot.objects.create(
        metal=metal,
        provider="historical-test",
        provider_timestamp=timezone.now(),
        provider_rate=historical_rate,
        applied_rate=historical_rate,
        purity=Decimal("0.9999"),
    )
    return MetalAllocation.objects.create(
        contribution=contribution,
        rate_snapshot=snapshot,
        metal=metal,
        quantity=quantity,
    )


class OwnerLiabilitySelectorTests(TestCase):
    def setUp(self):
        self.customer, self.accounts = make_liability_accounts()

    def test_summary_reconciles_paid_obligations_in_separate_dimensions(self):
        paid_cash = make_contribution(
            self.accounts[SchemeAccount.SavingsMode.CASH],
            Decimal("12500.00"),
            Contribution.Status.PAID,
            "cash-paid",
            timezone.now(),
        )
        self.assertIsNotNone(paid_cash.pk)
        make_contribution(
            self.accounts[SchemeAccount.SavingsMode.CASH],
            Decimal("9000.00"),
            Contribution.Status.FAILED,
            "cash-failed",
        )

        gold_contribution = make_contribution(
            self.accounts[SchemeAccount.SavingsMode.GOLD],
            Decimal("10000.00"),
            Contribution.Status.PAID,
            "gold-paid",
            timezone.now(),
        )
        make_allocation(
            gold_contribution,
            RateSnapshot.Metal.GOLD,
            Decimal("0.800000"),
            Decimal("12500.0000"),
        )

        silver_contribution = make_contribution(
            self.accounts[SchemeAccount.SavingsMode.SILVER],
            Decimal("10000.00"),
            Contribution.Status.PAID,
            "silver-paid",
            timezone.now(),
        )
        make_allocation(
            silver_contribution,
            RateSnapshot.Metal.SILVER,
            Decimal("66.666667"),
            Decimal("150.0000"),
        )

        failed_gold = make_contribution(
            self.accounts[SchemeAccount.SavingsMode.GOLD],
            Decimal("5000.00"),
            Contribution.Status.FAILED,
            "gold-failed",
        )
        make_allocation(
            failed_gold,
            RateSnapshot.Metal.GOLD,
            Decimal("0.400000"),
            Decimal("12500.0000"),
        )

        summary = get_owner_liability_summary(rate_provider=FixedRateProvider())

        self.assertEqual(summary.cash_principal, Decimal("12500.00"))
        self.assertEqual(summary.gold.quantity, Decimal("0.800000"))
        self.assertEqual(summary.gold.reference_rate, Decimal("14000.0000"))
        self.assertEqual(summary.gold.indicative_exposure, Decimal("11200.00"))
        self.assertEqual(summary.silver.quantity, Decimal("66.666667"))
        self.assertEqual(summary.silver.reference_rate, Decimal("155.0000"))
        self.assertEqual(summary.silver.indicative_exposure, Decimal("10333.33"))

    @override_settings(DEBUG=False, METAL_RATE_PROVIDER="")
    def test_rate_failure_preserves_authoritative_gram_liability(self):
        gold_contribution = make_contribution(
            self.accounts[SchemeAccount.SavingsMode.GOLD],
            Decimal("10000.00"),
            Contribution.Status.PAID,
            "gold-no-current-rate",
            timezone.now(),
        )
        make_allocation(
            gold_contribution,
            RateSnapshot.Metal.GOLD,
            Decimal("0.800000"),
            Decimal("12500.0000"),
        )

        summary = get_owner_liability_summary()

        self.assertEqual(summary.gold.quantity, Decimal("0.800000"))
        self.assertIsNone(summary.gold.reference_rate)
        self.assertIsNone(summary.gold.indicative_exposure)
        self.assertIn("METAL_RATE_PROVIDER", summary.gold.rate_error)

    def test_activity_counts_only_successful_payments_in_india_periods(self):
        local_timezone = timezone.get_current_timezone()
        today_paid_at = timezone.make_aware(
            datetime(2026, 8, 18, 0, 1), local_timezone
        )
        month_paid_at = timezone.make_aware(
            datetime(2026, 8, 1, 12, 0), local_timezone
        )
        previous_month_paid_at = timezone.make_aware(
            datetime(2026, 7, 31, 23, 59), local_timezone
        )
        cash_account = self.accounts[SchemeAccount.SavingsMode.CASH]
        make_contribution(
            cash_account,
            Decimal("1000.00"),
            Contribution.Status.PAID,
            "activity-today",
            today_paid_at,
        )
        make_contribution(
            cash_account,
            Decimal("1000.00"),
            Contribution.Status.PAID,
            "activity-month",
            month_paid_at,
        )
        make_contribution(
            cash_account,
            Decimal("1000.00"),
            Contribution.Status.PAID,
            "activity-previous",
            previous_month_paid_at,
        )
        make_contribution(
            cash_account,
            Decimal("1000.00"),
            Contribution.Status.FAILED,
            "activity-failed",
        )
        make_contribution(
            self.accounts[SchemeAccount.SavingsMode.GOLD],
            Decimal("1000.00"),
            Contribution.Status.PAID_UNALLOCATED,
            "activity-unallocated",
            today_paid_at,
        )
        self.accounts[SchemeAccount.SavingsMode.SILVER].status = (
            SchemeAccount.Status.REDEEMED
        )
        self.accounts[SchemeAccount.SavingsMode.SILVER].save(update_fields=["status"])

        summary = get_owner_activity_summary(as_of=date(2026, 8, 18))

        self.assertEqual(summary.customer_count, 1)
        self.assertEqual(summary.active_account_count, 2)
        self.assertEqual(summary.contribution_count_today, 2)
        self.assertEqual(summary.contribution_count_month, 3)
        self.assertEqual(summary.unallocated_payment_count, 1)


@override_settings(
    DEBUG=True,
    METAL_RATE_PROVIDER="mock",
    MOCK_GOLD_RATE="14000.0000",
    MOCK_GOLD_PURITY="0.9999",
    MOCK_SILVER_RATE="155.0000",
    MOCK_SILVER_PURITY="0.9990",
)
class OwnerLiabilityDashboardTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(
            username="liability-owner@example.com",
            email="liability-owner@example.com",
            password="owner-password-strong",
            role=get_user_model().Role.OWNER,
        )
        self.customer, self.accounts = make_liability_accounts()
        gold_contribution = make_contribution(
            self.accounts[SchemeAccount.SavingsMode.GOLD],
            Decimal("10000.00"),
            Contribution.Status.PAID,
            "dashboard-gold",
            timezone.now(),
        )
        make_allocation(
            gold_contribution,
            RateSnapshot.Metal.GOLD,
            Decimal("0.800000"),
            Decimal("12500.0000"),
        )

    def test_owner_sees_liabilities_reference_rates_and_activity(self):
        self.client.force_login(self.owner)

        response = self.client.get(reverse("schemes:owner_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["liabilities"].gold.quantity, Decimal("0.800000")
        )
        self.assertContains(response, "Outstanding customer liabilities")
        self.assertContains(response, "0.800000 g")
        self.assertContains(response, "14000.0000")
        self.assertContains(response, "11200.00")
        self.assertContains(response, "Contributions today")

    def test_customer_cannot_view_liability_dashboard(self):
        self.client.force_login(self.customer.user)

        response = self.client.get(reverse("schemes:owner_dashboard"))

        self.assertEqual(response.status_code, 403)

    @override_settings(MOCK_GOLD_RATE="0")
    def test_invalid_gold_reference_rate_does_not_hide_other_liabilities(self):
        self.client.force_login(self.owner)

        response = self.client.get(reverse("schemes:owner_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "0.800000 g")
        self.assertContains(response, "Reference rate unavailable")
        self.assertContains(response, "155.0000")
        self.assertIsNone(response.context["liabilities"].gold.reference_rate)
        self.assertEqual(
            response.context["liabilities"].silver.reference_rate,
            Decimal("155.0000"),
        )

    def test_dashboard_warns_about_paid_unallocated_payments(self):
        make_contribution(
            self.accounts[SchemeAccount.SavingsMode.SILVER],
            Decimal("1000.00"),
            Contribution.Status.PAID_UNALLOCATED,
            "dashboard-unallocated",
            timezone.now(),
        )
        self.client.force_login(self.owner)

        response = self.client.get(reverse("schemes:owner_dashboard"))

        self.assertContains(response, "1 verified payment awaiting metal allocation")
        self.assertContains(response, "Review and retry")
