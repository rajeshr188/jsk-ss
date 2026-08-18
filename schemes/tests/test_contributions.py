from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.utils import timezone

from schemes.models import Contribution, MetalAllocation, SchemeAccount, SchemePlan
from schemes.payments import get_payment_gateway
from schemes.selectors import get_cash_balance
from schemes.services import (
    confirm_contribution,
    create_customer,
    enroll_customer,
    fail_contribution,
    initiate_contribution,
    process_mock_contribution,
    validate_contribution_amount,
)


def make_account(*, frequency_rule, amount_rule=SchemePlan.AmountRule.FIXED):
    customer = create_customer(
        full_name=f"Customer {frequency_rule}",
        email=f"{frequency_rule.lower()}-{amount_rule.lower()}@example.com",
        mobile_number="9000000010",
        password="customer-password-strong",
    )
    fixed_amount = Decimal("5000.00") if amount_rule == SchemePlan.AmountRule.FIXED else None
    minimum = fixed_amount or Decimal("1000.00")
    plan = SchemePlan.objects.create(
        name=f"{amount_rule} {frequency_rule}",
        code=f"{amount_rule}-{frequency_rule}",
        amount_rule=amount_rule,
        frequency_rule=frequency_rule,
        fixed_contribution_amount=fixed_amount,
        minimum_contribution=minimum,
        maximum_contribution=Decimal("10000.00"),
    )
    return enroll_customer(
        customer=customer,
        plan=plan,
        savings_mode=SchemeAccount.SavingsMode.CASH,
        start_date=timezone.localdate(),
    )


class MockGatewayBoundaryTests(TestCase):
    @override_settings(DEBUG=False, PAYMENT_GATEWAY="mock")
    def test_mock_gateway_is_disabled_outside_debug(self):
        with self.assertRaises(ImproperlyConfigured):
            get_payment_gateway()

    @override_settings(DEBUG=True, PAYMENT_GATEWAY="")
    def test_mock_gateway_requires_explicit_setting(self):
        with self.assertRaises(ImproperlyConfigured):
            get_payment_gateway()


@override_settings(DEBUG=True, PAYMENT_GATEWAY="mock")
class ContributionServiceTests(TestCase):
    def test_fixed_amount_is_enforced(self):
        account = make_account(frequency_rule=SchemePlan.FrequencyRule.FLEXIBLE)
        with self.assertRaises(ValidationError):
            validate_contribution_amount(account, Decimal("4999.00"))
        self.assertEqual(
            validate_contribution_amount(account, Decimal("5000.00")),
            Decimal("5000.00"),
        )

    def test_variable_amount_boundaries_are_enforced(self):
        account = make_account(
            frequency_rule=SchemePlan.FrequencyRule.FLEXIBLE,
            amount_rule=SchemePlan.AmountRule.VARIABLE,
        )
        for invalid in (Decimal("999.99"), Decimal("10000.01")):
            with self.assertRaises(ValidationError):
                validate_contribution_amount(account, invalid)
        self.assertEqual(
            validate_contribution_amount(account, Decimal("2500.25")),
            Decimal("2500.25"),
        )

    def test_once_per_month_counts_only_paid_contributions(self):
        account = make_account(frequency_rule=SchemePlan.FrequencyRule.ONCE_PER_MONTH)
        attempt = initiate_contribution(
            scheme_account=account,
            amount=Decimal("5000.00"),
            payment_gateway="mock",
        )
        fail_contribution(contribution_id=attempt.pk, gateway_reference="mock_failed")
        self.assertEqual(get_cash_balance(account), Decimal("0.00"))

        paid = process_mock_contribution(
            scheme_account=account, amount=Decimal("5000.00")
        )
        self.assertEqual(paid.status, Contribution.Status.PAID)
        self.assertEqual(get_cash_balance(account), Decimal("5000.00"))

        with self.assertRaises(ValidationError):
            process_mock_contribution(
                scheme_account=account, amount=Decimal("5000.00")
            )
        self.assertEqual(
            Contribution.objects.filter(
                scheme_account=account, status=Contribution.Status.PAID
            ).count(),
            1,
        )

    def test_flexible_account_accepts_multiple_successful_contributions(self):
        account = make_account(frequency_rule=SchemePlan.FrequencyRule.FLEXIBLE)
        process_mock_contribution(
            scheme_account=account, amount=Decimal("5000.00")
        )
        process_mock_contribution(
            scheme_account=account, amount=Decimal("5000.00")
        )
        self.assertEqual(get_cash_balance(account), Decimal("10000.00"))
        self.assertFalse(MetalAllocation.objects.exists())

    def test_variable_once_per_month_combination(self):
        account = make_account(
            frequency_rule=SchemePlan.FrequencyRule.ONCE_PER_MONTH,
            amount_rule=SchemePlan.AmountRule.VARIABLE,
        )
        process_mock_contribution(
            scheme_account=account, amount=Decimal("2500.00")
        )
        with self.assertRaises(ValidationError):
            process_mock_contribution(
                scheme_account=account, amount=Decimal("3000.00")
            )
        self.assertEqual(get_cash_balance(account), Decimal("2500.00"))

    def test_database_rejects_paid_and_unallocated_duplicate_monthly_period(self):
        account = make_account(frequency_rule=SchemePlan.FrequencyRule.ONCE_PER_MONTH)
        period = timezone.localdate().replace(day=1)
        Contribution.objects.create(
            scheme_account=account,
            amount=Decimal("5000.00"),
            contribution_period=period,
            frequency_rule_snapshot=SchemePlan.FrequencyRule.ONCE_PER_MONTH,
            status=Contribution.Status.PAID,
            payment_gateway="mock",
            gateway_reference="mock_db_first",
            paid_at=timezone.now(),
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            Contribution.objects.create(
                scheme_account=account,
                amount=Decimal("5000.00"),
                contribution_period=period,
                frequency_rule_snapshot=SchemePlan.FrequencyRule.ONCE_PER_MONTH,
                status=Contribution.Status.PAID_UNALLOCATED,
                payment_gateway="mock",
                gateway_reference="mock_db_duplicate",
                paid_at=timezone.now(),
            )

    def test_confirmation_is_idempotent(self):
        account = make_account(frequency_rule=SchemePlan.FrequencyRule.FLEXIBLE)
        contribution = initiate_contribution(
            scheme_account=account,
            amount=Decimal("5000.00"),
            payment_gateway="mock",
        )
        first = confirm_contribution(
            contribution_id=contribution.pk,
            payment_gateway="mock",
            gateway_reference="mock_idempotent",
            verified=True,
        )
        second = confirm_contribution(
            contribution_id=contribution.pk,
            payment_gateway="mock",
            gateway_reference="mock_idempotent",
            verified=True,
        )
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(get_cash_balance(account), Decimal("5000.00"))

    def test_unverified_confirmation_creates_no_entitlement(self):
        account = make_account(frequency_rule=SchemePlan.FrequencyRule.FLEXIBLE)
        contribution = initiate_contribution(
            scheme_account=account,
            amount=Decimal("5000.00"),
            payment_gateway="mock",
        )
        with self.assertRaises(ValidationError):
            confirm_contribution(
                contribution_id=contribution.pk,
                payment_gateway="mock",
                gateway_reference="mock_unverified",
                verified=False,
            )
        contribution.refresh_from_db()
        self.assertEqual(contribution.status, Contribution.Status.PENDING)
        self.assertEqual(get_cash_balance(account), Decimal("0.00"))

    def test_post_eligibility_contribution_is_rejected_when_not_allowed(self):
        account = make_account(frequency_rule=SchemePlan.FrequencyRule.FLEXIBLE)
        account.eligible_from = timezone.localdate() - timedelta(days=1)
        account.save(update_fields=["eligible_from"])
        with self.assertRaises(ValidationError):
            process_mock_contribution(
                scheme_account=account, amount=Decimal("5000.00")
            )
