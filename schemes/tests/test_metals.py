from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.utils import timezone

from schemes.models import Contribution, MetalAllocation, SchemeAccount, SchemePlan, SchemeRate
from schemes.selectors import get_metal_balance
from schemes.services import (
    allocate_metal,
    confirm_contribution,
    create_customer,
    enroll_customer,
    fail_contribution,
    initiate_contribution,
    process_mock_contribution,
    publish_scheme_rate,
)
from schemes.tests.grade_helpers import enrolment_grade_kwargs, metal_grade_for


def make_owner(suffix="default"):
    return get_user_model().objects.create_user(
        username=f"rate-owner-{suffix}@example.com",
        email=f"rate-owner-{suffix}@example.com",
        password="owner-password-strong",
        role=get_user_model().Role.OWNER,
    )


def make_metal_account(
    *,
    metal=SchemeAccount.SavingsMode.GOLD,
    suffix="default",
    frequency_rule=SchemePlan.FrequencyRule.FLEXIBLE,
):
    customer = create_customer(
        full_name=f"{metal.title()} Customer",
        email=f"{metal.lower()}-{suffix}@example.com",
        mobile_number="9000000030",
        password="customer-password-strong",
    )
    plan = SchemePlan.objects.create(
        name=f"{metal.title()} Flexible",
        code=f"{metal}-{suffix}".upper(),
        amount_rule=SchemePlan.AmountRule.VARIABLE,
        frequency_rule=frequency_rule,
        fixed_contribution_amount=None,
        minimum_contribution=Decimal("1000.00"),
        maximum_contribution=Decimal("100000.00"),
    )
    return enroll_customer(
        customer=customer,
        plan=plan,
        **enrolment_grade_kwargs(plan, metal),
        start_date=timezone.localdate(),
    )


@override_settings(DEBUG=True, PAYMENT_GATEWAY="mock")
class MetalAllocationTests(TestCase):
    def publish(self, metal, rate, suffix="default"):
        return publish_scheme_rate(
            metal_grade=metal_grade_for(metal),
            rate_per_gram=Decimal(rate),
            published_by=make_owner(suffix),
        )

    def test_gold_allocation_uses_locked_scheme_rate(self):
        rate = self.publish(SchemeRate.Metal.GOLD, "12500.0000")
        account = make_metal_account()
        contribution = process_mock_contribution(
            scheme_account=account, amount=Decimal("10000.00")
        )
        allocation = contribution.metal_allocation

        self.assertEqual(contribution.scheme_rate, rate)
        self.assertIsNotNone(contribution.rate_locked_at)
        self.assertEqual(allocation.quantity, Decimal("0.800000"))
        self.assertEqual(allocation.scheme_rate, rate)
        self.assertEqual(allocation.scheme_rate.purity, Decimal("0.9999"))
        self.assertEqual(get_metal_balance(account), Decimal("0.800000"))

    def test_silver_allocation_rounds_half_up_to_six_decimal_places(self):
        self.publish(SchemeRate.Metal.SILVER, "150.0000", "silver")
        account = make_metal_account(
            metal=SchemeAccount.SavingsMode.SILVER, suffix="silver"
        )
        contribution = process_mock_contribution(
            scheme_account=account, amount=Decimal("10000.00")
        )
        self.assertEqual(contribution.metal_allocation.quantity, Decimal("66.666667"))

    def test_rate_change_during_checkout_does_not_change_locked_allocation(self):
        first_rate = self.publish(SchemeRate.Metal.GOLD, "12500.0000", "first")
        account = make_metal_account(suffix="history")
        contribution = initiate_contribution(
            scheme_account=account,
            amount=Decimal("10000.00"),
            payment_gateway="mock",
        )
        self.publish(SchemeRate.Metal.GOLD, "12600.0000", "second")

        contribution = confirm_contribution(
            contribution_id=contribution.pk,
            payment_gateway="mock",
            gateway_reference="mock_locked_rate",
            verified=True,
        )
        self.assertEqual(contribution.status, Contribution.Status.PAID_UNALLOCATED)
        self.assertFalse(MetalAllocation.objects.filter(contribution=contribution).exists())

        allocation = allocate_metal(contribution=contribution)
        contribution.refresh_from_db()
        next_contribution = initiate_contribution(
            scheme_account=account,
            amount=Decimal("10000.00"),
            payment_gateway="mock",
        )

        self.assertEqual(contribution.status, Contribution.Status.PAID)
        self.assertEqual(contribution.scheme_rate, first_rate)
        self.assertEqual(allocation.scheme_rate, first_rate)
        self.assertEqual(allocation.quantity, Decimal("0.800000"))
        self.assertEqual(next_contribution.scheme_rate.rate_per_gram, Decimal("12600.0000"))

    def test_duplicate_allocation_processing_is_idempotent(self):
        self.publish(SchemeRate.Metal.GOLD, "12500.0000")
        account = make_metal_account(suffix="idempotent")
        contribution = process_mock_contribution(
            scheme_account=account, amount=Decimal("10000.00")
        )
        first = allocate_metal(contribution=contribution)
        second = allocate_metal(contribution=contribution)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(MetalAllocation.objects.filter(contribution=contribution).count(), 1)
        self.assertEqual(SchemeRate.objects.count(), 1)

    def test_scheme_rate_and_allocation_cannot_be_edited(self):
        self.publish(SchemeRate.Metal.GOLD, "12500.0000")
        account = make_metal_account(suffix="immutable")
        allocation = process_mock_contribution(
            scheme_account=account, amount=Decimal("10000.00")
        ).metal_allocation
        rate = allocation.scheme_rate
        rate.rate_per_gram = Decimal("1.0000")
        with self.assertRaises(ValidationError):
            rate.save()
        allocation.quantity = Decimal("999.000000")
        with self.assertRaises(ValidationError):
            allocation.save()

    def test_no_published_rate_blocks_gold_and_silver_before_payment(self):
        for metal in (SchemeAccount.SavingsMode.GOLD, SchemeAccount.SavingsMode.SILVER):
            with self.subTest(metal=metal):
                account = make_metal_account(
                    metal=metal,
                    suffix=f"no-rate-{metal.lower()}",
                )
                with self.assertRaisesMessage(ValidationError, "has not been published"):
                    initiate_contribution(
                        scheme_account=account,
                        amount=Decimal("10000.00"),
                        payment_gateway="mock",
                    )
                self.assertFalse(
                    Contribution.objects.filter(scheme_account=account).exists()
                )

    def test_failed_metal_payment_creates_no_allocation(self):
        self.publish(SchemeRate.Metal.GOLD, "12500.0000")
        account = make_metal_account(suffix="failed")
        contribution = initiate_contribution(
            scheme_account=account,
            amount=Decimal("10000.00"),
            payment_gateway="mock",
        )
        fail_contribution(
            contribution_id=contribution.pk,
            gateway_reference="mock_metal_fail",
        )
        self.assertFalse(MetalAllocation.objects.filter(contribution=contribution).exists())
        self.assertEqual(get_metal_balance(account), Decimal("0.000000"))
