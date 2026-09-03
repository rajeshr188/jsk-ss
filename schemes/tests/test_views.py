from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse

from schemes.models import Customer, SchemeAccount, SchemePlan
from schemes.services import create_customer, enroll_customer
from schemes.tests.grade_helpers import enrolment_grade_kwargs, grade_for_mode
from accounts.models import CustomerInvitation


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


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
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
            },
        )
        customer = Customer.objects.get(email="meera@example.com")
        self.assertRedirects(response, reverse("schemes:customer_detail", args=[customer.pk]))
        self.assertFalse(customer.user.has_usable_password())
        self.assertEqual(CustomerInvitation.objects.filter(user=customer.user).count(), 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/accounts/invitations/", mail.outbox[0].body)
        self.assertEqual(customer.scheme_accounts.count(), 0)

        plan = make_plan()
        grade = grade_for_mode(plan, SchemeAccount.SavingsMode.GOLD)
        response = self.client.post(
            reverse("schemes:customer_enroll", args=[customer.pk]),
            {
                "plan": plan.pk,
                "metal_grade": grade.pk,
                "start_date": "2026-08-01",
                "agreed_months": 12,
                "audit_reason": "Customer requested enrolment at the store.",
            },
        )
        self.assertRedirects(response, reverse("schemes:customer_detail", args=[customer.pk]))
        account = customer.scheme_accounts.get()
        self.assertEqual(account.eligible_from, date(2027, 8, 1))
        self.assertEqual(account.fixed_amount_snapshot, Decimal("5000.00"))

    def test_owner_can_resend_invitation_and_old_invitation_is_superseded(self):
        response = self.client.post(
            reverse("schemes:customer_add"),
            {
                "full_name": "Meera Gupta",
                "email": "meera@example.com",
                "mobile_number": "9988776655",
                "address": "Agra",
            },
        )
        self.assertEqual(response.status_code, 302)
        customer = Customer.objects.get(email="meera@example.com")
        first = CustomerInvitation.objects.get(user=customer.user)

        response = self.client.post(
            reverse("schemes:customer_invitation_resend", args=[customer.pk])
        )

        self.assertRedirects(
            response,
            reverse("schemes:customer_detail", args=[customer.pk]),
        )
        first.refresh_from_db()
        self.assertIsNotNone(first.revoked_at)
        self.assertEqual(CustomerInvitation.objects.filter(user=customer.user).count(), 2)
        self.assertEqual(len(mail.outbox), 2)

    def test_customer_creation_rolls_back_if_invitation_cannot_be_issued(self):
        with patch(
            "schemes.services.issue_customer_invitation",
            side_effect=ValidationError("Invitation setup failed safely."),
        ):
            response = self.client.post(
                reverse("schemes:customer_add"),
                {
                    "full_name": "Rollback Customer",
                    "email": "rollback@example.com",
                    "mobile_number": "9988776655",
                    "address": "Vellore",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Invitation setup failed safely.")
        self.assertFalse(Customer.objects.filter(email="rollback@example.com").exists())
        self.assertFalse(
            get_user_model().objects.filter(email="rollback@example.com").exists()
        )

    def test_customer_cannot_resend_an_invitation(self):
        customer = create_customer(
            full_name="Customer User",
            email="ordinary@example.com",
            mobile_number="9000000000",
            password=None,
        )
        self.client.force_login(customer.user)

        response = self.client.post(
            reverse("schemes:customer_invitation_resend", args=[customer.pk])
        )

        self.assertEqual(response.status_code, 403)

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

    def test_new_plan_must_be_saved_before_owner_can_publish_it(self):
        add_response = self.client.get(reverse("schemes:plan_add"))
        self.assertNotContains(add_response, 'id="id_publicly_listed"')
        self.assertContains(add_response, "Plan identity")
        self.assertContains(add_response, "Contribution rules")

        plan = make_plan()
        edit_response = self.client.get(reverse("schemes:plan_edit", args=[plan.pk]))
        self.assertContains(edit_response, 'id="id_publicly_listed"')
        self.assertFalse(plan.publicly_listed)

    def test_owner_dashboard_prioritizes_common_actions(self):
        response = self.client.get(reverse("schemes:owner_dashboard"))

        self.assertContains(response, "Common actions")
        self.assertContains(response, "Reports and operational records")
        self.assertContains(response, "Manage customers")


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
            **enrolment_grade_kwargs(plan, SchemeAccount.SavingsMode.GOLD),
            start_date=date(2026, 8, 1),
        )
        account_b = enroll_customer(
            customer=customer_b,
            plan=plan,
            **enrolment_grade_kwargs(plan, SchemeAccount.SavingsMode.SILVER),
            start_date=date(2026, 8, 1),
        )

        self.client.force_login(customer_a.user)
        response = self.client.get(reverse("schemes:my_schemes"))
        self.assertContains(response, account_a.scheme_number)
        self.assertNotContains(response, account_b.scheme_number)
