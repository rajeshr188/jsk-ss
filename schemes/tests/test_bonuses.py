import uuid
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from schemes.bonuses import CASH_BONUS_POLICY_VERSION
from schemes.models import Contribution, Redemption, SchemeAccount, SchemePlan
from schemes.selectors import (
    get_cash_balance,
    get_cash_bonus_summary,
    get_outstanding_entitlement,
    get_owner_liability_summary,
)
from schemes.services import complete_redemption, create_customer, enroll_customer


def paid_at(value):
    return timezone.make_aware(
        datetime.combine(value, time(hour=12)),
        timezone.get_current_timezone(),
    )


def make_paid_contribution(account, amount, reference, payment_date):
    return Contribution.objects.create(
        scheme_account=account,
        amount=amount,
        contribution_period=payment_date.replace(day=1),
        frequency_rule_snapshot=SchemePlan.FrequencyRule.FLEXIBLE,
        status=Contribution.Status.PAID,
        payment_gateway="bonus-test",
        gateway_reference=reference,
        paid_at=paid_at(payment_date),
    )


@override_settings(DEBUG=True)
class CashBonusTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.owner = get_user_model().objects.create_user(
            username="bonus-owner@example.com",
            email="bonus-owner@example.com",
            password="owner-password-strong",
            role=get_user_model().Role.OWNER,
        )
        self.customer = create_customer(
            full_name="Bonus Customer",
            email="bonus-customer@example.com",
            mobile_number="9000000091",
            password="customer-password-strong",
        )
        self.plan = SchemePlan.objects.create(
            name="Five Percent Cash Bonus",
            code="BONUS-5",
            amount_rule=SchemePlan.AmountRule.VARIABLE,
            frequency_rule=SchemePlan.FrequencyRule.FLEXIBLE,
            minimum_contribution=Decimal("100.00"),
            maximum_contribution=Decimal("100000.00"),
            cash_bonus_percentage=Decimal("5.00"),
            cash_bonus_minimum_months=12,
        )

    def make_account(self, *, eligible=True, agreed_months=12, mode="CASH"):
        account = enroll_customer(
            customer=self.customer,
            plan=self.plan,
            savings_mode=mode,
            start_date=date(2025, 1, 1),
            agreed_months=agreed_months,
        )
        account.eligible_from = self.today + timedelta(days=-1 if eligible else 1)
        account.save(update_fields=["eligible_from"])
        return account

    def test_enrolment_snapshots_versioned_policy_terms(self):
        account = self.make_account()
        self.plan.cash_bonus_percentage = Decimal("10.00")
        self.plan.cash_bonus_minimum_months = 24
        self.plan.save(update_fields=["cash_bonus_percentage", "cash_bonus_minimum_months"])
        account.refresh_from_db()

        self.assertEqual(
            account.cash_bonus_policy_version_snapshot,
            CASH_BONUS_POLICY_VERSION,
        )
        self.assertEqual(account.cash_bonus_percentage_snapshot, Decimal("5.00"))
        self.assertEqual(account.cash_bonus_minimum_months_snapshot, 12)

    def test_projected_bonus_is_not_redeemable_or_an_actual_liability(self):
        account = self.make_account(eligible=False)
        make_paid_contribution(
            account,
            Decimal("10000.00"),
            "bonus-projected",
            self.today,
        )

        summary = get_cash_bonus_summary(account)
        owner = get_owner_liability_summary()

        self.assertEqual(summary.principal_paid, Decimal("10000.00"))
        self.assertEqual(summary.principal_outstanding, Decimal("10000.00"))
        self.assertEqual(summary.earned_bonus, Decimal("0.00"))
        self.assertEqual(summary.projected_bonus, Decimal("500.00"))
        self.assertEqual(summary.redeemable_amount, Decimal("10000.00"))
        self.assertEqual(get_outstanding_entitlement(account), Decimal("10000.00"))
        self.assertEqual(owner.cash_earned_bonus, Decimal("0.00"))
        self.assertEqual(owner.cash_projected_bonus, Decimal("500.00"))
        self.assertEqual(owner.cash_redeemable_amount, Decimal("10000.00"))

    def test_earned_bonus_uses_only_principal_paid_by_eligibility_cutoff(self):
        account = self.make_account()
        make_paid_contribution(
            account,
            Decimal("10000.00"),
            "bonus-before-cutoff",
            account.eligible_from,
        )
        make_paid_contribution(
            account,
            Decimal("2000.00"),
            "bonus-after-cutoff",
            account.eligible_from + timedelta(days=1),
        )

        summary = get_cash_bonus_summary(account)

        self.assertEqual(summary.principal_paid, Decimal("12000.00"))
        self.assertEqual(summary.principal_outstanding, Decimal("12000.00"))
        self.assertEqual(summary.earned_bonus, Decimal("500.00"))
        self.assertEqual(summary.projected_bonus, Decimal("0.00"))
        self.assertEqual(summary.redeemable_amount, Decimal("12500.00"))

    def test_contract_below_minimum_duration_never_projects_or_earns_bonus(self):
        self.plan.cash_bonus_minimum_months = 18
        self.plan.save(update_fields=["cash_bonus_minimum_months"])
        account = self.make_account(agreed_months=12)
        make_paid_contribution(
            account,
            Decimal("10000.00"),
            "bonus-duration",
            account.eligible_from,
        )

        summary = get_cash_bonus_summary(account)

        self.assertFalse(summary.contract_qualifies)
        self.assertEqual(summary.earned_bonus, Decimal("0.00"))
        self.assertEqual(summary.projected_bonus, Decimal("0.00"))
        self.assertEqual(summary.redeemable_amount, Decimal("10000.00"))

    def test_bonus_rounds_money_half_up(self):
        account = self.make_account()
        make_paid_contribution(
            account,
            Decimal("100.10"),
            "bonus-rounding",
            account.eligible_from,
        )

        self.assertEqual(
            get_cash_bonus_summary(account).earned_bonus,
            Decimal("5.01"),
        )

    def test_redemption_allocates_principal_first_then_bonus(self):
        account = self.make_account()
        make_paid_contribution(
            account,
            Decimal("10000.00"),
            "bonus-redemption",
            account.eligible_from,
        )

        partial = complete_redemption(
            scheme_account=account,
            settlement_type=Redemption.SettlementType.CASH,
            amount=Decimal("10100.00"),
            processed_by=self.owner,
            idempotency_key=uuid.uuid4(),
        )
        remaining = get_cash_bonus_summary(account)
        account.refresh_from_db()

        self.assertEqual(partial.cash_principal_amount, Decimal("10000.00"))
        self.assertEqual(partial.cash_bonus_amount, Decimal("100.00"))
        self.assertEqual(get_cash_balance(account), Decimal("0.00"))
        self.assertEqual(remaining.earned_bonus, Decimal("400.00"))
        self.assertEqual(remaining.redeemable_amount, Decimal("400.00"))
        self.assertEqual(account.status, SchemeAccount.Status.ACTIVE)

        final = complete_redemption(
            scheme_account=account,
            settlement_type=Redemption.SettlementType.CASH,
            amount=Decimal("400.00"),
            processed_by=self.owner,
            idempotency_key=uuid.uuid4(),
        )
        account.refresh_from_db()

        self.assertEqual(final.cash_principal_amount, Decimal("0.00"))
        self.assertEqual(final.cash_bonus_amount, Decimal("400.00"))
        self.assertEqual(account.status, SchemeAccount.Status.REDEEMED)
        self.assertEqual(
            get_cash_bonus_summary(account).redeemable_amount,
            Decimal("0.00"),
        )

    def test_owner_liability_separates_earned_and_projected_bonus(self):
        earned_account = self.make_account()
        make_paid_contribution(
            earned_account,
            Decimal("10000.00"),
            "bonus-owner-earned",
            earned_account.eligible_from,
        )
        other_customer = create_customer(
            full_name="Projected Bonus Customer",
            email="bonus-projected-customer@example.com",
            mobile_number="9000000092",
            password="customer-password-strong",
        )
        projected_account = enroll_customer(
            customer=other_customer,
            plan=self.plan,
            savings_mode=SchemeAccount.SavingsMode.CASH,
            start_date=self.today,
        )
        make_paid_contribution(
            projected_account,
            Decimal("10000.00"),
            "bonus-owner-projected",
            self.today,
        )

        summary = get_owner_liability_summary()

        self.assertEqual(summary.cash_principal, Decimal("20000.00"))
        self.assertEqual(summary.cash_earned_bonus, Decimal("500.00"))
        self.assertEqual(summary.cash_projected_bonus, Decimal("500.00"))
        self.assertEqual(summary.cash_redeemable_amount, Decimal("20500.00"))

    def test_gold_scheme_ignores_cash_bonus_policy(self):
        account = self.make_account(mode=SchemeAccount.SavingsMode.GOLD)
        make_paid_contribution(
            account,
            Decimal("10000.00"),
            "bonus-gold-ignored",
            account.eligible_from,
        )

        summary = get_cash_bonus_summary(account)

        self.assertEqual(summary.earned_bonus, Decimal("0.00"))
        self.assertEqual(summary.projected_bonus, Decimal("0.00"))

    def test_database_constraints_reject_invalid_policy_and_components(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            SchemePlan.objects.filter(pk=self.plan.pk).update(
                cash_bonus_percentage=Decimal("100.01")
            )

        account = self.make_account()
        with self.assertRaises(IntegrityError), transaction.atomic():
            Redemption.objects.create(
                redemption_number="RED-BONUS-MISMATCH",
                scheme_account=account,
                settlement_type=Redemption.SettlementType.CASH,
                cash_amount=Decimal("100.00"),
                cash_principal_amount=Decimal("90.00"),
                cash_bonus_amount=Decimal("5.00"),
                processed_by=self.owner,
            )

    def test_unknown_policy_version_is_rejected(self):
        account = self.make_account()
        account.cash_bonus_policy_version_snapshot = "UNKNOWN"
        with self.assertRaises(ValidationError):
            get_cash_bonus_summary(account)

    def test_customer_owner_and_plan_views_show_bonus_breakdown(self):
        account = self.make_account()
        make_paid_contribution(
            account,
            Decimal("10000.00"),
            "bonus-view",
            account.eligible_from,
        )

        self.client.force_login(self.customer.user)
        customer_page = self.client.get(
            reverse("schemes:my_scheme_detail", args=[account.scheme_number])
        )
        self.assertContains(customer_page, "Earned bonus")
        self.assertContains(customer_page, "500.00")
        self.assertContains(customer_page, "Redeemable cash amount")

        self.client.force_login(self.owner)
        owner_page = self.client.get(reverse("schemes:owner_dashboard"))
        plan_page = self.client.get(reverse("schemes:plan_list"))
        redemption_page = self.client.get(
            reverse("schemes:redemption_create", args=[account.scheme_number])
        )
        self.assertContains(owner_page, "Projected bonus")
        self.assertContains(owner_page, "Cash redeemable obligation")
        self.assertContains(plan_page, "5.00%")
        self.assertContains(redemption_page, "Earned bonus")
