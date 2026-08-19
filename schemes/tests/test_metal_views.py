from decimal import Decimal

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from django.contrib.auth import get_user_model

from schemes.models import Contribution, MetalAllocation, SchemeAccount, SchemePlan
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
    def test_rate_failure_shows_paid_allocation_pending(self):
        response = self.client.post(
            reverse("schemes:pay_contribution", args=[self.account.scheme_number]),
            {"amount": "10000.00"},
            follow=True,
        )
        contribution = Contribution.objects.get(scheme_account=self.account)
        self.assertEqual(contribution.status, Contribution.Status.PAID_UNALLOCATED)
        self.assertContains(response, "payment was verified")
        self.assertContains(response, "Paid — allocation pending")
        self.assertFalse(MetalAllocation.objects.exists())

    def test_owner_can_retry_a_paid_unallocated_contribution(self):
        with override_settings(MOCK_GOLD_RATE="0"):
            self.client.post(
                reverse("schemes:pay_contribution", args=[self.account.scheme_number]),
                {"amount": "10000.00"},
            )
        contribution = Contribution.objects.get(scheme_account=self.account)
        owner = get_user_model().objects.create_user(
            username="allocation-owner@example.com",
            email="allocation-owner@example.com",
            password="owner-password-strong",
            role=get_user_model().Role.OWNER,
        )
        self.client.force_login(owner)

        response = self.client.post(
            reverse("schemes:retry_contribution_allocation", args=[contribution.pk]),
            {"reason": "Provider recovered; retry verified payment."},
            follow=True,
        )

        contribution.refresh_from_db()
        self.assertEqual(contribution.status, Contribution.Status.PAID)
        self.assertEqual(contribution.metal_allocation.quantity, Decimal("0.800000"))
        self.assertContains(response, "Allocated 0.800000 g")

    def test_customer_cannot_retry_an_unallocated_contribution(self):
        with override_settings(MOCK_GOLD_RATE="0"):
            self.client.post(
                reverse("schemes:pay_contribution", args=[self.account.scheme_number]),
                {"amount": "10000.00"},
            )
        contribution = Contribution.objects.get(scheme_account=self.account)

        response = self.client.post(
            reverse("schemes:retry_contribution_allocation", args=[contribution.pk])
        )

        self.assertEqual(response.status_code, 403)
