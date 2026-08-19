from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from schemes.models import SchemeAccount, SchemePlan
from schemes.services import add_calendar_months, create_customer, enroll_customer


def make_plan(**overrides):
    values = {
        "name": "Monthly Gold",
        "code": "GOLD-MONTHLY",
        "minimum_months": 12,
        "default_months": 12,
        "amount_rule": SchemePlan.AmountRule.VARIABLE,
        "frequency_rule": SchemePlan.FrequencyRule.FLEXIBLE,
        "fixed_contribution_amount": None,
        "minimum_contribution": Decimal("1000.00"),
        "maximum_contribution": Decimal("50000.00"),
    }
    values.update(overrides)
    return SchemePlan.objects.create(**values)


class CalendarMonthTests(TestCase):
    def test_month_end_is_clamped_deterministically(self):
        self.assertEqual(add_calendar_months(date(2025, 2, 28), 12), date(2026, 2, 28))
        self.assertEqual(add_calendar_months(date(2024, 2, 29), 12), date(2025, 2, 28))


class EnrolmentServiceTests(TestCase):
    def setUp(self):
        self.customer = create_customer(
            full_name="Radha Sharma",
            email="radha@example.com",
            mobile_number="9876543210",
            address="Mathura",
            password="correct-horse-battery-staple",
        )
        self.plan = make_plan()

    def test_enrolment_snapshots_plan_terms_and_eligibility(self):
        account = enroll_customer(
            customer=self.customer,
            plan=self.plan,
            savings_mode=SchemeAccount.SavingsMode.GOLD,
            start_date=date(2026, 1, 31),
            agreed_months=12,
        )
        self.assertEqual(account.eligible_from, date(2027, 1, 31))
        self.assertEqual(account.amount_rule_snapshot, SchemePlan.AmountRule.VARIABLE)
        self.assertEqual(account.minimum_amount_snapshot, Decimal("1000.00"))
        self.assertTrue(account.scheme_number.startswith("JSK-"))

        self.plan.minimum_contribution = Decimal("2500.00")
        self.plan.save(update_fields=["minimum_contribution"])
        account.refresh_from_db()
        self.assertEqual(account.minimum_amount_snapshot, Decimal("1000.00"))

    def test_duration_below_plan_minimum_is_rejected(self):
        self.plan.minimum_months = 18
        self.plan.default_months = 18
        self.plan.save()
        with self.assertRaises(ValidationError):
            enroll_customer(
                customer=self.customer,
                plan=self.plan,
                savings_mode=SchemeAccount.SavingsMode.GOLD,
                start_date=date(2026, 1, 1),
                agreed_months=12,
            )
    def test_inactive_plan_is_rejected(self):
        self.plan.active = False
        self.plan.save(update_fields=["active"])
        with self.assertRaises(ValidationError):
            enroll_customer(
                customer=self.customer,
                plan=self.plan,
                savings_mode=SchemeAccount.SavingsMode.GOLD,
                agreed_months=12,
            )
