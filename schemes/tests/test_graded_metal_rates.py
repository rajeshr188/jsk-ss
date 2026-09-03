from datetime import date
from decimal import Decimal
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone

from schemes.models import (
    Contribution,
    MetalAllocation,
    MetalGrade,
    SchemeAccount,
    SchemePlan,
)
from schemes.selectors import get_metal_balance
from schemes.services import (
    allocate_metal,
    create_customer,
    enroll_customer,
    publish_scheme_rate,
)
from schemes.tests.grade_helpers import ensure_metal_grades, grade_for_mode


class GradedMetalRateTests(TestCase):
    def setUp(self):
        ensure_metal_grades()
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(
            username="graded-owner@example.com",
            email="graded-owner@example.com",
            password="OwnerPass123!",
            role=user_model.Role.OWNER,
        )
        self.customer = create_customer(
            full_name="Graded Customer",
            email="graded-customer@example.com",
            mobile_number="9000000777",
            password="CustomerPass123!",
        )
        self.plan = SchemePlan.objects.create(
            name="Graded savings",
            code="GRADED-SAVINGS",
            amount_rule=SchemePlan.AmountRule.VARIABLE,
            frequency_rule=SchemePlan.FrequencyRule.FLEXIBLE,
            minimum_contribution=Decimal("100.00"),
            maximum_contribution=Decimal("100000.00"),
        )
        self.gold_22k = grade_for_mode(
            self.plan,
            SchemeAccount.SavingsMode.GOLD,
            code=MetalGrade.GOLD_22K_916,
        )
        self.gold_24k = grade_for_mode(
            self.plan,
            SchemeAccount.SavingsMode.GOLD,
            code=MetalGrade.GOLD_24K_9999,
        )

    def make_account(self, grade):
        return enroll_customer(
            customer=self.customer,
            plan=self.plan,
            metal_grade=grade,
            start_date=date(2026, 9, 1),
        )

    def test_22k_account_locks_only_22k_rate_and_allocates_six_decimal_grams(self):
        account = self.make_account(self.gold_22k)
        rate_22k = publish_scheme_rate(
            metal_grade=self.gold_22k,
            rate_per_gram=Decimal("10000.0000"),
            published_by=self.owner,
        )
        publish_scheme_rate(
            metal_grade=self.gold_24k,
            rate_per_gram=Decimal("12000.0000"),
            published_by=self.owner,
        )
        contribution = Contribution.objects.create(
            scheme_account=account,
            amount=Decimal("1234.56"),
            contribution_period=date(2026, 9, 1),
            frequency_rule_snapshot=SchemePlan.FrequencyRule.FLEXIBLE,
            status=Contribution.Status.PAID_UNALLOCATED,
            payment_gateway="mock",
            gateway_reference="graded-payment",
            scheme_rate=rate_22k,
            rate_locked_at=timezone.now(),
            paid_at=timezone.now(),
        )

        allocation = allocate_metal(contribution=contribution)

        self.assertEqual(allocation.metal_grade, self.gold_22k)
        self.assertEqual(allocation.scheme_rate, rate_22k)
        self.assertEqual(allocation.quantity, Decimal("0.123456"))
        self.assertEqual(get_metal_balance(account), Decimal("0.123456"))

    def test_account_grade_is_immutable_and_must_match_base_metal(self):
        account = self.make_account(self.gold_22k)
        account.metal_grade = self.gold_24k

        with self.assertRaisesMessage(ValidationError, "immutable"):
            account.full_clean()
        with self.assertRaisesMessage(ValidationError, "immutable"):
            account.save(update_fields=["metal_grade"])

    def test_grade_definition_is_immutable_on_direct_save(self):
        self.gold_22k.fineness = Decimal("0.915000")

        with self.assertRaisesMessage(ValidationError, "immutable"):
            self.gold_22k.save(update_fields=["fineness"])

    def test_integrity_command_passes_for_seeded_definitions(self):
        output = StringIO()

        call_command("check_graded_metal_rates", stdout=output)

        self.assertIn("graded_metal_rate_check status=ok", output.getvalue())

    def test_integrity_command_blocks_modified_grade_definition(self):
        MetalGrade.objects.filter(pk=self.gold_22k.pk).update(
            fineness=Decimal("0.915000")
        )

        with self.assertRaises(CommandError):
            call_command("check_graded_metal_rates", stdout=StringIO())
