from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from schemes.models import Customer, SchemeAccount, SchemePlan
from schemes.services import create_customer, enroll_customer


def make_plan():
    return SchemePlan.objects.create(
        name="Cash Monthly",
        code="CASH-MONTHLY",
        minimum_months=12,
        default_months=12,
        amount_rule=SchemePlan.AmountRule.FIXED,
        frequency_rule=SchemePlan.FrequencyRule.ONCE_PER_MONTH,
        fixed_contribution_amount=Decimal("5000.00"),
        minimum_contribution=Decimal("5000.00"),
        maximum_contribution=Decimal("5000.00"),
    )


class OwnerFlowTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(
            username="owner@example.com",
            email="owner@example.com",
            password="owner-password-strong",
            role=get_user_model().Role.OWNER,
        )
        self.client.force_login(self.owner)

    def test_owner_creates_customer_then_enrols_them(self):
        response = self.client.post(
            reverse("schemes:customer_add"),
            {
                "full_name": "Meera Gupta",
                "email": "meera@example.com",
                "mobile_number": "9988776655",
                "address": "Agra",
                "password1": "customer-password-strong",
                "password2": "customer-password-strong",
            },
        )
        customer = Customer.objects.get(email="meera@example.com")
        self.assertRedirects(response, reverse("schemes:customer_detail", args=[customer.pk]))

        plan = make_plan()
        response = self.client.post(
            reverse("schemes:customer_enroll", args=[customer.pk]),
            {
                "plan": plan.pk,
                "savings_mode": SchemeAccount.SavingsMode.CASH,
                "start_date": "2026-08-01",
                "agreed_months": 12,
            },
        )
        self.assertRedirects(response, reverse("schemes:customer_detail", args=[customer.pk]))
        account = customer.scheme_accounts.get()
        self.assertEqual(account.eligible_from, date(2027, 8, 1))
        self.assertEqual(account.fixed_amount_snapshot, Decimal("5000.00"))

    def test_customer_cannot_open_owner_dashboard(self):
        customer = create_customer(
            full_name="Customer User",
            email="ordinary@example.com",
            mobile_number="9000000000",
            password="customer-password-strong",
        )
        self.client.force_login(customer.user)
        response = self.client.get(reverse("schemes:owner_dashboard"))
        self.assertEqual(response.status_code, 403)


class CustomerIsolationTests(TestCase):
    def test_customer_sees_only_their_own_scheme(self):
        plan = make_plan()
        customer_a = create_customer(
            full_name="Customer A",
            email="a@example.com",
            mobile_number="9000000001",
            password="customer-password-strong",
        )
        customer_b = create_customer(
            full_name="Customer B",
            email="b@example.com",
            mobile_number="9000000002",
            password="customer-password-strong",
        )
        account_a = enroll_customer(
            customer=customer_a,
            plan=plan,
            savings_mode=SchemeAccount.SavingsMode.CASH,
            start_date=date(2026, 8, 1),
        )
        account_b = enroll_customer(
            customer=customer_b,
            plan=plan,
            savings_mode=SchemeAccount.SavingsMode.SILVER,
            start_date=date(2026, 8, 1),
        )

        self.client.force_login(customer_a.user)
        response = self.client.get(reverse("schemes:my_schemes"))
        self.assertContains(response, account_a.scheme_number)
        self.assertNotContains(response, account_b.scheme_number)

