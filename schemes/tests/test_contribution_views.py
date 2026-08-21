from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from schemes.models import Contribution, SchemeAccount, SchemePlan
from schemes.services import create_customer, enroll_customer


def make_cash_account(*, email):
    customer = create_customer(
        full_name=email.split("@")[0].title(),
        email=email,
        mobile_number="9000000020",
        password="customer-password-strong",
    )
    plan = SchemePlan.objects.create(
        name=f"Cash plan {email}",
        code=f"CASH-{customer.pk}",
        amount_rule=SchemePlan.AmountRule.FIXED,
        frequency_rule=SchemePlan.FrequencyRule.ONCE_PER_MONTH,
        fixed_contribution_amount=Decimal("5000.00"),
        minimum_contribution=Decimal("5000.00"),
        maximum_contribution=Decimal("5000.00"),
    )
    account = enroll_customer(
        customer=customer,
        plan=plan,
        savings_mode=SchemeAccount.SavingsMode.CASH,
        start_date=timezone.localdate(),
    )
    return customer, account


@override_settings(DEBUG=True, PAYMENT_GATEWAY="mock")
class ContributionViewTests(TestCase):
    def setUp(self):
        self.customer, self.account = make_cash_account(email="payer@example.com")
        self.client.force_login(self.customer.user)

    def test_customer_mock_payment_updates_balance_and_history(self):
        response = self.client.post(
            reverse("schemes:pay_contribution", args=[self.account.scheme_number]),
            {"amount": "5000.00"},
            follow=True,
        )
        self.assertContains(response, "Mock payment successful")
        self.assertContains(response, "₹5000.00")
        self.assertContains(response, 'class="card mobile-history-card"')
        contribution = Contribution.objects.get(scheme_account=self.account)
        self.assertEqual(contribution.status, Contribution.Status.PAID)
        self.assertTrue(contribution.gateway_reference.startswith("mock_"))

    def test_customer_cannot_view_or_pay_another_customer_scheme(self):
        _, other_account = make_cash_account(email="other-payer@example.com")
        detail = self.client.get(
            reverse("schemes:my_scheme_detail", args=[other_account.scheme_number])
        )
        payment = self.client.get(
            reverse("schemes:pay_contribution", args=[other_account.scheme_number])
        )
        self.assertEqual(detail.status_code, 404)
        self.assertEqual(payment.status_code, 404)

    def test_owner_can_see_customer_contribution(self):
        self.client.post(
            reverse("schemes:pay_contribution", args=[self.account.scheme_number]),
            {"amount": "5000.00"},
        )
        owner = get_user_model().objects.create_user(
            username="owner-contributions@example.com",
            email="owner-contributions@example.com",
            password="owner-password-strong",
            role=get_user_model().Role.OWNER,
        )
        self.client.force_login(owner)
        response = self.client.get(reverse("schemes:contribution_list"))
        self.assertContains(response, self.customer.full_name)
        self.assertContains(response, "₹5000.00")
