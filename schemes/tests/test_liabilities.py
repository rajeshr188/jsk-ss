from datetime import date, datetime, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from schemes.models import Contribution, MetalAllocation, SchemeAccount, SchemePlan, SchemeRate
from schemes.selectors import get_owner_activity_summary, get_owner_liability_summary
from schemes.services import create_customer, enroll_customer, publish_scheme_rate


def make_owner(suffix="liability"):
    return get_user_model().objects.create_user(
        username=f"{suffix}-owner@example.com",
        email=f"{suffix}-owner@example.com",
        password="owner-password-strong",
        role=get_user_model().Role.OWNER,
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
    accounts = {
        mode: enroll_customer(
            customer=customer,
            plan=plan,
            savings_mode=mode,
            start_date=date(2026, 1, 1),
        )
        for mode in SchemeAccount.SavingsMode.values
    }
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


def make_allocation(contribution, metal, quantity, historical_rate, effective_from=None):
    rate = SchemeRate.objects.create(
        metal=metal,
        rate_per_gram=historical_rate,
        purity=Decimal("0.9999") if metal == SchemeRate.Metal.GOLD else Decimal("0.9990"),
        effective_from=effective_from or timezone.now(),
    )
    contribution.scheme_rate = rate
    contribution.rate_locked_at = contribution.created_at
    contribution.save(update_fields=["scheme_rate", "rate_locked_at"])
    return MetalAllocation.objects.create(
        contribution=contribution,
        scheme_rate=rate,
        metal=metal,
        quantity=quantity,
    )


@override_settings(DEBUG=True)
class OwnerLiabilitySelectorTests(TestCase):
    def setUp(self):
        self.customer, self.accounts = make_liability_accounts()

    def test_summary_reconciles_paid_obligations_in_separate_dimensions(self):
        make_contribution(
            self.accounts[SchemeAccount.SavingsMode.CASH],
            Decimal("12500.00"), Contribution.Status.PAID, "cash-paid", timezone.now(),
        )
        make_contribution(
            self.accounts[SchemeAccount.SavingsMode.CASH],
            Decimal("9000.00"), Contribution.Status.FAILED, "cash-failed",
        )
        gold = make_contribution(
            self.accounts[SchemeAccount.SavingsMode.GOLD],
            Decimal("10000.00"), Contribution.Status.PAID, "gold-paid", timezone.now(),
        )
        make_allocation(gold, SchemeRate.Metal.GOLD, Decimal("0.800000"), Decimal("12500.0000"))
        silver = make_contribution(
            self.accounts[SchemeAccount.SavingsMode.SILVER],
            Decimal("10000.00"), Contribution.Status.PAID, "silver-paid", timezone.now(),
        )
        make_allocation(silver, SchemeRate.Metal.SILVER, Decimal("66.666667"), Decimal("150.0000"))
        failed_gold = make_contribution(
            self.accounts[SchemeAccount.SavingsMode.GOLD],
            Decimal("5000.00"), Contribution.Status.FAILED, "gold-failed",
        )
        make_allocation(failed_gold, SchemeRate.Metal.GOLD, Decimal("0.400000"), Decimal("12500.0000"))
        owner = make_owner()
        publish_scheme_rate(metal="GOLD", rate_per_gram=Decimal("14000.0000"), published_by=owner)
        publish_scheme_rate(metal="SILVER", rate_per_gram=Decimal("155.0000"), published_by=owner)

        summary = get_owner_liability_summary()

        self.assertEqual(summary.cash_principal, Decimal("12500.00"))
        self.assertEqual(summary.gold.quantity, Decimal("0.800000"))
        self.assertEqual(summary.gold.scheme_rate, Decimal("14000.0000"))
        self.assertEqual(summary.gold.indicative_exposure, Decimal("11200.00"))
        self.assertEqual(summary.silver.quantity, Decimal("66.666667"))
        self.assertEqual(summary.silver.scheme_rate, Decimal("155.0000"))
        self.assertEqual(summary.silver.indicative_exposure, Decimal("10333.33"))

    def test_missing_current_rate_preserves_authoritative_gram_liability(self):
        gold = make_contribution(
            self.accounts[SchemeAccount.SavingsMode.GOLD],
            Decimal("10000.00"), Contribution.Status.PAID, "gold-no-current-rate", timezone.now(),
        )
        make_allocation(
            gold,
            SchemeRate.Metal.GOLD,
            Decimal("0.800000"),
            Decimal("12500.0000"),
            effective_from=timezone.now() + timedelta(days=1),
        )

        summary = get_owner_liability_summary()

        self.assertEqual(summary.gold.quantity, Decimal("0.800000"))
        self.assertIsNone(summary.gold.scheme_rate)
        self.assertIsNone(summary.gold.indicative_exposure)

    def test_activity_counts_only_successful_payments_in_india_periods(self):
        local_timezone = timezone.get_current_timezone()
        today_paid_at = timezone.make_aware(datetime(2026, 8, 18, 0, 1), local_timezone)
        month_paid_at = timezone.make_aware(datetime(2026, 8, 1, 12, 0), local_timezone)
        previous_month_paid_at = timezone.make_aware(datetime(2026, 7, 31, 23, 59), local_timezone)
        cash_account = self.accounts[SchemeAccount.SavingsMode.CASH]
        make_contribution(cash_account, Decimal("1000.00"), Contribution.Status.PAID, "activity-today", today_paid_at)
        make_contribution(cash_account, Decimal("1000.00"), Contribution.Status.PAID, "activity-month", month_paid_at)
        make_contribution(cash_account, Decimal("1000.00"), Contribution.Status.PAID, "activity-previous", previous_month_paid_at)
        make_contribution(cash_account, Decimal("1000.00"), Contribution.Status.FAILED, "activity-failed")
        make_contribution(
            self.accounts[SchemeAccount.SavingsMode.GOLD],
            Decimal("1000.00"), Contribution.Status.PAID_UNALLOCATED,
            "activity-unallocated", today_paid_at,
        )
        self.accounts[SchemeAccount.SavingsMode.SILVER].status = SchemeAccount.Status.REDEEMED
        self.accounts[SchemeAccount.SavingsMode.SILVER].save(update_fields=["status"])

        summary = get_owner_activity_summary(as_of=date(2026, 8, 18))

        self.assertEqual(summary.customer_count, 1)
        self.assertEqual(summary.active_account_count, 2)
        self.assertEqual(summary.contribution_count_today, 2)
        self.assertEqual(summary.contribution_count_month, 3)
        self.assertEqual(summary.unallocated_payment_count, 1)


@override_settings(DEBUG=True)
class OwnerLiabilityDashboardTests(TestCase):
    def setUp(self):
        self.owner = make_owner("dashboard")
        self.customer, self.accounts = make_liability_accounts()
        gold = make_contribution(
            self.accounts[SchemeAccount.SavingsMode.GOLD],
            Decimal("10000.00"), Contribution.Status.PAID, "dashboard-gold", timezone.now(),
        )
        make_allocation(gold, SchemeRate.Metal.GOLD, Decimal("0.800000"), Decimal("12500.0000"))
        publish_scheme_rate(metal="GOLD", rate_per_gram=Decimal("14000.0000"), published_by=self.owner)
        publish_scheme_rate(metal="SILVER", rate_per_gram=Decimal("155.0000"), published_by=self.owner)

    def test_owner_sees_liabilities_scheme_rates_and_activity(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse("schemes:owner_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["liabilities"].gold.quantity, Decimal("0.800000"))
        self.assertContains(response, "Outstanding customer liabilities")
        self.assertContains(response, "0.800000 g")
        self.assertContains(response, "14000.0000")
        self.assertContains(response, "11200.00")
        self.assertContains(response, "Current Scheme Rate")

    def test_customer_cannot_view_liability_dashboard(self):
        self.client.force_login(self.customer.user)
        self.assertEqual(self.client.get(reverse("schemes:owner_dashboard")).status_code, 403)

    def test_dashboard_warns_about_paid_unallocated_payments(self):
        make_contribution(
            self.accounts[SchemeAccount.SavingsMode.SILVER],
            Decimal("1000.00"), Contribution.Status.PAID_UNALLOCATED,
            "dashboard-unallocated", timezone.now(),
        )
        self.client.force_login(self.owner)
        response = self.client.get(reverse("schemes:owner_dashboard"))
        self.assertContains(response, "1 verified payment awaiting metal allocation")
        self.assertContains(response, "Review and retry")
