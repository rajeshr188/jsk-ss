from datetime import date
from decimal import Decimal
from io import StringIO

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from schemes.forms import EnrolmentForm, SchemePlanForm
from schemes.models import Contribution, SchemeAccount, SchemePlan
from schemes.services import create_customer, enroll_customer, initiate_contribution


PRODUCTION_PAYMENT_SETTINGS = {
    "DEBUG": False,
    "PAYMENT_GATEWAY": "razorpay",
    "RAZORPAY_KEY_ID": "rzp_test_boundary",
    "RAZORPAY_KEY_SECRET": "test-only-secret",
    "RAZORPAY_WEBHOOK_SECRET": "test-only-webhook-secret",
}


@override_settings(**PRODUCTION_PAYMENT_SETTINGS)
class MetalOnlyProductionBoundaryTests(TestCase):
    def setUp(self):
        self.customer = create_customer(
            full_name="Legacy Cash Customer",
            email="legacy-cash@example.com",
            mobile_number="9000000099",
            password="customer-password-strong",
        )
        self.plan = SchemePlan.objects.create(
            name="Monthly jewellery plan",
            code="METAL-ONLY-BOUNDARY",
            minimum_months=12,
            default_months=12,
            amount_rule=SchemePlan.AmountRule.FIXED,
            frequency_rule=SchemePlan.FrequencyRule.ONCE_PER_MONTH,
            fixed_contribution_amount=Decimal("1000.00"),
            minimum_contribution=Decimal("1000.00"),
            maximum_contribution=Decimal("1000.00"),
        )
        # Production already has one empty historical CASH account. Build the same
        # shape under the development-only compatibility boundary for read tests.
        with override_settings(DEBUG=True):
            self.legacy_cash_account = enroll_customer(
                customer=self.customer,
                plan=self.plan,
                savings_mode=SchemeAccount.SavingsMode.CASH,
                start_date=date(2026, 8, 1),
            )

    def test_cash_is_absent_from_production_enrolment_choices(self):
        form = EnrolmentForm()

        self.assertEqual(
            [value for value, _label in form.fields["savings_mode"].choices],
            [SchemeAccount.SavingsMode.GOLD, SchemeAccount.SavingsMode.SILVER],
        )

    def test_service_rejects_new_cash_enrolment(self):
        with self.assertRaises(ValidationError) as raised:
            enroll_customer(
                customer=self.customer,
                plan=self.plan,
                savings_mode=SchemeAccount.SavingsMode.CASH,
                start_date=date(2026, 8, 1),
            )

        self.assertIn("savings_mode", raised.exception.message_dict)
        self.assertEqual(SchemeAccount.objects.count(), 1)

    def test_metal_enrolment_remains_available(self):
        account = enroll_customer(
            customer=self.customer,
            plan=self.plan,
            savings_mode=SchemeAccount.SavingsMode.GOLD,
            start_date=date(2026, 8, 1),
        )

        self.assertEqual(account.savings_mode, SchemeAccount.SavingsMode.GOLD)

    def test_legacy_cash_account_cannot_initiate_a_contribution(self):
        with self.assertRaisesMessage(
            ValidationError,
            "Cash savings are closed to new activity",
        ):
            initiate_contribution(
                scheme_account=self.legacy_cash_account,
                amount=Decimal("1000.00"),
                payment_gateway="razorpay",
            )

        self.assertFalse(Contribution.objects.exists())

    def test_legacy_cash_history_remains_visible_but_payment_is_blocked(self):
        self.client.force_login(self.customer.user)

        summary = self.client.get(reverse("schemes:my_schemes"))
        detail = self.client.get(
            reverse(
                "schemes:my_scheme_detail",
                args=[self.legacy_cash_account.scheme_number],
            )
        )
        payment_url = reverse(
            "schemes:pay_contribution",
            args=[self.legacy_cash_account.scheme_number],
        )
        payment = self.client.get(payment_url)

        self.assertContains(summary, "retained for historical reference")
        self.assertNotContains(summary, payment_url)
        self.assertContains(detail, "retained for historical reference")
        self.assertNotContains(detail, payment_url)
        self.assertEqual(payment.status_code, 403)
        self.assertContains(
            payment,
            "New cash contributions are unavailable",
            status_code=403,
        )

    def test_cash_bonus_configuration_is_hidden_in_production(self):
        form = SchemePlanForm(instance=self.plan)

        self.assertNotIn("cash_bonus_percentage", form.fields)
        self.assertNotIn("cash_bonus_minimum_months", form.fields)

    def test_cash_boundary_preflight_accepts_the_empty_legacy_record(self):
        output = StringIO()

        call_command("check_cash_boundary", stdout=output)

        rendered = output.getvalue()
        self.assertIn("cash_boundary_check status=ok", rendered)
        self.assertIn("cash_accounts_total=1", rendered)
        self.assertIn("verified_cash_amount_inr=0", rendered)
        self.assertNotIn(self.customer.email, rendered)

    def test_cash_boundary_preflight_fails_closed_on_verified_money(self):
        Contribution.objects.create(
            scheme_account=self.legacy_cash_account,
            amount=Decimal("1000.00"),
            contribution_period=date(2026, 8, 1),
            frequency_rule_snapshot=SchemePlan.FrequencyRule.ONCE_PER_MONTH,
            status=Contribution.Status.PAID,
            payment_gateway="legacy",
            gateway_reference="legacy-cash-payment",
            paid_at=timezone.now(),
        )

        with self.assertRaises(CommandError):
            call_command("check_cash_boundary", stdout=StringIO())
