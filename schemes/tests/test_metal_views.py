from decimal import Decimal

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from schemes.models import MetalAllocation, SchemeAccount, SchemePlan
from schemes.services import create_customer, enroll_customer


def make_gold_account():
    customer = create_customer(
        full_name="Gold View Customer",
        email="gold-view@example.com",
        mobile_number="9000000040",
        password="customer-password-strong",
    )
    plan = SchemePlan.objects.create(
        name="Gold View Plan",
        code="GOLD-VIEW",
        amount_rule=SchemePlan.AmountRule.VARIABLE,
        frequency_rule=SchemePlan.FrequencyRule.FLEXIBLE,
        minimum_contribution=Decimal("1000.00"),
        maximum_contribution=Decimal("100000.00"),
    )
    account = enroll_customer(
        customer=customer,
        plan=plan,
        savings_mode=SchemeAccount.SavingsMode.GOLD,
        start_date=timezone.localdate(),
    )
    return customer, account


@override_settings(
    DEBUG=True,
    PAYMENT_GATEWAY="mock",
    METAL_RATE_PROVIDER="mock",
    MOCK_GOLD_RATE="12500.0000",
    MOCK_GOLD_PURITY="0.9999",
)
class MetalContributionViewTests(TestCase):
    def setUp(self):
        self.customer, self.account = make_gold_account()
        self.client.force_login(self.customer.user)

    def test_customer_gold_payment_updates_gram_balance_and_history(self):
        response = self.client.post(
            reverse("schemes:pay_contribution", args=[self.account.scheme_number]),
            {"amount": "10000.00"},
            follow=True,
        )
        self.assertContains(response, "0.800000 g")
        self.assertContains(response, "12500.0000")
        self.assertContains(response, "24K Gold was allocated")
        self.assertEqual(MetalAllocation.objects.count(), 1)

    @override_settings(METAL_RATE_PROVIDER="")
    def test_metal_payment_page_is_unavailable_without_rate_provider(self):
        response = self.client.get(
            reverse("schemes:pay_contribution", args=[self.account.scheme_number])
        )
        self.assertEqual(response.status_code, 404)

    @override_settings(MOCK_GOLD_RATE="0")
    def test_invalid_mock_rate_is_shown_without_creating_entitlement(self):
        response = self.client.post(
            reverse("schemes:pay_contribution", args=[self.account.scheme_number]),
            {"amount": "10000.00"},
        )
        self.assertContains(response, "MOCK_GOLD_RATE must be greater than zero")
        self.assertFalse(MetalAllocation.objects.exists())
