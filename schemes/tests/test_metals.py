from decimal import Decimal

from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.test import TestCase, override_settings
from django.utils import timezone

from schemes.models import (
    Contribution,
    MetalAllocation,
    RateSnapshot,
    SchemeAccount,
    SchemePlan,
)
from schemes.rates import get_metal_rate_provider
from schemes.selectors import get_metal_balance
from schemes.services import (
    allocate_metal,
    create_customer,
    enroll_customer,
    fail_contribution,
    initiate_contribution,
    process_mock_contribution,
    retry_metal_allocation,
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
        savings_mode=metal,
        start_date=timezone.localdate(),
    )


class MockMetalRateBoundaryTests(TestCase):
    @override_settings(DEBUG=False, METAL_RATE_PROVIDER="mock")
    def test_mock_rates_are_disabled_outside_debug(self):
        with self.assertRaises(ImproperlyConfigured):
            get_metal_rate_provider()

    @override_settings(DEBUG=True, METAL_RATE_PROVIDER="external")
    def test_mock_rates_require_explicit_provider_setting(self):
        with self.assertRaises(ImproperlyConfigured):
            get_metal_rate_provider()


@override_settings(
    DEBUG=True,
    PAYMENT_GATEWAY="mock",
    METAL_RATE_PROVIDER="mock",
    MOCK_GOLD_RATE="12500.0000",
    MOCK_SILVER_RATE="150.0000",
    MOCK_GOLD_PURITY="0.9999",
    MOCK_SILVER_PURITY="0.9990",
)
class MetalAllocationTests(TestCase):
    def test_gold_allocation_uses_exact_historical_rate(self):
        account = make_metal_account()
        contribution = process_mock_contribution(
            scheme_account=account, amount=Decimal("10000.00")
        )
        allocation = contribution.metal_allocation
        self.assertEqual(allocation.quantity, Decimal("0.800000"))
        self.assertEqual(allocation.rate_snapshot.provider_rate, Decimal("12500.0000"))
        self.assertEqual(allocation.rate_snapshot.applied_rate, Decimal("12500.0000"))
        self.assertEqual(allocation.rate_snapshot.purity, Decimal("0.9999"))
        self.assertEqual(get_metal_balance(account), Decimal("0.800000"))

    def test_silver_allocation_rounds_half_up_to_six_decimal_places(self):
        account = make_metal_account(
            metal=SchemeAccount.SavingsMode.SILVER, suffix="silver"
        )
        contribution = process_mock_contribution(
            scheme_account=account, amount=Decimal("10000.00")
        )
        self.assertEqual(contribution.metal_allocation.quantity, Decimal("66.666667"))

    def test_later_rate_change_does_not_rewrite_historical_allocation(self):
        account = make_metal_account(suffix="history")
        first = process_mock_contribution(
            scheme_account=account, amount=Decimal("10000.00")
        )
        first_allocation_id = first.metal_allocation.pk

        with override_settings(MOCK_GOLD_RATE="14000.0000"):
            second = process_mock_contribution(
                scheme_account=account, amount=Decimal("10000.00")
            )

        historical = MetalAllocation.objects.select_related("rate_snapshot").get(
            pk=first_allocation_id
        )
        self.assertEqual(historical.quantity, Decimal("0.800000"))
        self.assertEqual(historical.rate_snapshot.applied_rate, Decimal("12500.0000"))
        self.assertEqual(second.metal_allocation.quantity, Decimal("0.714286"))
        self.assertEqual(get_metal_balance(account), Decimal("1.514286"))

    def test_duplicate_allocation_processing_is_idempotent(self):
        account = make_metal_account(suffix="idempotent")
        contribution = process_mock_contribution(
            scheme_account=account, amount=Decimal("10000.00")
        )
        first = allocate_metal(contribution=contribution)
        second = allocate_metal(contribution=contribution)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(MetalAllocation.objects.filter(contribution=contribution).count(), 1)
        self.assertEqual(RateSnapshot.objects.count(), 1)

    def test_rate_snapshot_and_allocation_cannot_be_edited(self):
        account = make_metal_account(suffix="immutable")
        contribution = process_mock_contribution(
            scheme_account=account, amount=Decimal("10000.00")
        )
        allocation = contribution.metal_allocation
        snapshot = allocation.rate_snapshot
        snapshot.applied_rate = Decimal("1.0000")
        with self.assertRaises(ValidationError):
            snapshot.save()
        allocation.quantity = Decimal("999.000000")
        with self.assertRaises(ValidationError):
            allocation.save()

    def test_failed_metal_payment_creates_no_allocation(self):
        account = make_metal_account(suffix="failed")
        contribution = initiate_contribution(
            scheme_account=account,
            amount=Decimal("10000.00"),
            payment_gateway="mock",
        )
        fail_contribution(contribution_id=contribution.pk, gateway_reference="mock_metal_fail")
        self.assertFalse(MetalAllocation.objects.filter(contribution=contribution).exists())
        self.assertEqual(get_metal_balance(account), Decimal("0.000000"))

    @override_settings(MOCK_GOLD_RATE="0")
    def test_invalid_rate_preserves_payment_for_controlled_retry(self):
        account = make_metal_account(suffix="invalid-rate")
        contribution = process_mock_contribution(
            scheme_account=account, amount=Decimal("10000.00")
        )

        contribution.refresh_from_db()
        self.assertEqual(contribution.status, Contribution.Status.PAID_UNALLOCATED)
        self.assertIsNotNone(contribution.paid_at)
        self.assertTrue(contribution.gateway_reference.startswith("mock_"))
        self.assertIn("MOCK_GOLD_RATE", contribution.allocation_error)
        self.assertIsNotNone(contribution.allocation_attempted_at)
        self.assertFalse(MetalAllocation.objects.filter(contribution__scheme_account=account).exists())
        self.assertFalse(RateSnapshot.objects.exists())

        with override_settings(MOCK_GOLD_RATE="12500.0000"):
            allocation = retry_metal_allocation(contribution=contribution)

        contribution.refresh_from_db()
        self.assertEqual(contribution.status, Contribution.Status.PAID)
        self.assertEqual(contribution.allocation_error, "")
        self.assertEqual(allocation.quantity, Decimal("0.800000"))
        self.assertEqual(MetalAllocation.objects.count(), 1)
        self.assertEqual(RateSnapshot.objects.count(), 1)

    @override_settings(MOCK_GOLD_RATE="0")
    def test_paid_unallocated_consumes_once_per_month_opportunity(self):
        account = make_metal_account(
            suffix="unallocated-monthly",
            frequency_rule=SchemePlan.FrequencyRule.ONCE_PER_MONTH,
        )
        contribution = process_mock_contribution(
            scheme_account=account, amount=Decimal("10000.00")
        )
        self.assertEqual(contribution.status, Contribution.Status.PAID_UNALLOCATED)

        with self.assertRaises(ValidationError):
            process_mock_contribution(
                scheme_account=account, amount=Decimal("10000.00")
            )
        self.assertEqual(Contribution.objects.filter(scheme_account=account).count(), 1)
