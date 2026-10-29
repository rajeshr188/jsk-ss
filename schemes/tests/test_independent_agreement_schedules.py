"""Prospective schedules never create obligations or unlock financial workflows."""
from dataclasses import FrozenInstanceError
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from itertools import product

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings

from schemes.agreement_contracts import resolve_independent_agreement_schedule
from schemes.instalments import build_instalment_windows, window_for_instant
from schemes.models import (AuditEvent, Contribution, InrPrincipalReceipt, MetalAllocation,
    MetalGrade, SchemeAccount, SchemeInstalmentPeriod, SchemePlanConfiguration)
from schemes.plan_configuration import create_configuration_version
from schemes.plan_policies import require_operational_configuration
from schemes.tests.test_audit_exceptions import make_owner
from schemes.tests.test_independent_policy_fields import independent_values, required_values


class IndependentAgreementScheduleTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = make_owner()
        cls.grade = MetalGrade.objects.get(code="GOLD_22K_916")

    def create(self, values):
        return create_configuration_version(values=values, actor=self.owner, reason="Schedule preparation")

    def resolve(self, config, **changes):
        return resolve_independent_agreement_schedule(**dict(configuration_id=config.pk,
            start_date=date(2026, 1, 30), selected_amount=Decimal("500"),
            metal_grade_id=self.grade.pk if config.accumulation == "EXACT_METAL" else None) | changes)

    def test_required_matrix_uses_count_not_duration_and_keeps_exact_fixed_amount(self):
        for accumulation, basis, amount, eligibility in product(
                ("EXACT_METAL", "INR_PURCHASE_CREDIT"), ("CALENDAR_MONTH", "ANNIVERSARY"),
                ("PLAN_FIXED", "CUSTOMER_FIXED"), ("COUNT", "CALENDAR_AND_COUNT")):
            with self.subTest(accumulation=accumulation, basis=basis, amount=amount, eligibility=eligibility):
                config = self.create(required_values(accumulation=accumulation, period_basis=basis,
                    amount_policy=amount, fixed_amount=Decimal("500") if amount == "PLAN_FIXED" else None,
                    minimum_amount=Decimal("500") if amount == "PLAN_FIXED" else Decimal("100"),
                    maximum_amount=Decimal("500") if amount == "PLAN_FIXED" else Decimal("10000"),
                    eligibility_policy=eligibility, duration_months=18 if eligibility == "CALENDAR_AND_COUNT" else None))
                result = self.resolve(config)
                self.assertEqual(len(result.windows), 13)
                self.assertEqual([w.number for w in result.windows if not w.extension], list(range(1, 11)))
                self.assertEqual([w.number for w in result.windows if w.extension], [11, 12, 13])
                self.assertTrue(all(w.amount == Decimal("500") for w in result.windows))
                self.assertEqual(result.terms.duration_not_before,
                    date(2027, 7, 30) if eligibility == "CALENDAR_AND_COUNT" else None)
                self.assertEqual(result.windows[0].ends_before,
                    date(2026, 2, 1) if basis == "CALENDAR_MONTH" else date(2026, 2, 28))
                for previous, following in zip(result.windows, result.windows[1:]):
                    self.assertEqual(previous.ends_before, following.starts_on)

    def test_short_calendar_first_month_and_exact_india_midnight(self):
        result = self.resolve(self.create(required_values()))
        boundary = datetime(2026, 1, 31, 18, 30, tzinfo=timezone.utc)
        self.assertEqual(window_for_instant(result.windows, boundary - timedelta(microseconds=1)).number, 1)
        self.assertEqual(window_for_instant(result.windows, boundary).number, 2)
        before_start = datetime(2026, 1, 29, 18, 29, tzinfo=timezone.utc)
        self.assertIsNone(window_for_instant(result.windows, before_start))
        after_end = datetime(2027, 2, 1, tzinfo=timezone.utc)
        self.assertIsNone(window_for_instant(result.windows, after_end))
        with self.assertRaises(ValidationError):
            window_for_instant(result.windows, datetime(2026, 1, 31))

    def test_anniversary_clamping_uses_original_anchor_including_leap_year(self):
        config = self.create(required_values(period_basis="ANNIVERSARY"))
        result = self.resolve(config, start_date=date(2028, 1, 31))
        self.assertEqual(result.windows[0].ends_before, date(2028, 2, 29))
        self.assertEqual(result.windows[1].ends_before, date(2028, 3, 31))
        self.assertEqual(result.windows[12].ends_before, date(2029, 2, 28))

    def test_benefit_schedule_has_no_ordinary_replacements_or_implied_eligibility(self):
        config = self.create(required_values(eligibility_policy="CALENDAR", duration_months=18,
            missed_payment_policy="LOSE_UNEARNED_BENEFIT", max_extension_months=None,
            benefit_policy="VA_DISCOUNT", benefit_percentage=Decimal("5"), benefit_cap_inr=Decimal("500"),
            benefit_qualification="REQUIRED_SCHEDULE", benefit_on_miss="DISQUALIFY_UNEARNED",
            eligible_charge_definition="Published making charges excluding taxes"))
        result = self.resolve(config)
        self.assertEqual(len(result.windows), 10)
        self.assertFalse(any(w.extension for w in result.windows))
        self.assertEqual(result.terms.duration_not_before, date(2027, 7, 30))
        self.assertEqual(result.terms.policy.benefit_kind, "VA_DISCOUNT")

    def test_optional_ceiling_never_creates_instalment_debt(self):
        for basis, eligibility in product((None, "CALENDAR_MONTH", "ANNIVERSARY"), ("ANYTIME", "CALENDAR")):
            result = self.resolve(self.create(independent_values(period_basis=basis,
                frequency_rule="ONCE_PER_PERIOD" if basis else "FLEXIBLE",
                eligibility_policy=eligibility, duration_months=1 if eligibility == "CALENDAR" else None)))
            self.assertEqual(result.windows, ())
            self.assertIsNone(result.terms.policy.required_count)
            self.assertEqual(result.terms.policy.period_basis, basis)

    def test_invalid_dates_and_amounts_are_rejected_and_maximum_count_retains_replacements(self):
        config = self.create(required_values())
        for change in (dict(start_date=date(9999, 12, 31)), dict(start_date="2026-01-30"),
                       dict(start_date=datetime(2026, 1, 30)), dict(selected_amount=None),
                       dict(selected_amount=500.0), dict(selected_amount=Decimal("NaN"))):
            with self.subTest(change=change), self.assertRaises(ValidationError):
                self.resolve(config, **change)
        result = self.resolve(self.create(required_values(required_count=32767)))
        self.assertEqual(len(result.windows), 32770)
        self.assertEqual(result.windows[-1].number, 32770)
        self.assertEqual(sum(w.extension for w in result.windows), 3)

    def test_independent_read_only_schedule_and_legacy_projection_boundary(self):
        config = self.create(required_values())
        models = (SchemeAccount, SchemeInstalmentPeriod, Contribution, InrPrincipalReceipt,
                  MetalAllocation, AuditEvent, SchemePlanConfiguration)
        before = [list(model.objects.values()) for model in models]
        for enabled in (False, True):
            with override_settings(CONFIGURED_PLANS_ENABLED=enabled):
                result = self.resolve(config)
                with self.assertRaises(FrozenInstanceError):
                    result.windows = ()
                with self.assertRaises(FrozenInstanceError):
                    result.windows[0].amount = Decimal("1")
                require_operational_configuration(config)
                with self.assertRaises(ValidationError):
                    build_instalment_windows(configuration=config, start_date=date(2026, 1, 30),
                        agreed_months=12, amount=Decimal("500"))
        self.assertEqual(before, [list(model.objects.values()) for model in models])
