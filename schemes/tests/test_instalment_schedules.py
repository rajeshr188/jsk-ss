"""Schedule foundation fixtures never enable configured enrolment or real payments."""
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone as datetime_timezone
from decimal import Decimal
from io import StringIO
from threading import Barrier
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, close_old_connections, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse

from schemes.eligibility import add_calendar_months
from schemes.forms import PlanConfigurationForm
from schemes.instalments import (
    build_instalment_windows, prepare_instalment_periods, preview_monthly_completion, window_for_instant,
)
from schemes.models import Contribution, MetalAllocation, SchemeAccount, SchemeInstalmentPeriod, SchemePlan, SchemePlanConfiguration
from schemes.plan_configuration import (
    MONTHLY_COMPLETION_POLICY, agreement_snapshot_values, configuration_evidence,
    create_configuration_version, create_configured_plan_draft, preview_configuration_agreement,
)
from schemes.services import enroll_customer, validate_contribution_allowed, validate_redemption_amount
from schemes.tests.grade_helpers import grade_for_mode
from schemes.tests.test_audit_exceptions import make_owner, make_customer, make_plan


def monthly_values():
    return {"name": "Monthly metal completion", "amount_policy": "CUSTOMER_FIXED",
            "minimum_amount": Decimal("500"), "maximum_amount": Decimal("10000"),
            "amount_step": Decimal("100"), "frequency_rule": "ONCE_PER_PERIOD", **MONTHLY_COMPLETION_POLICY}


def fixture(owner):
    customer = make_customer()
    grade = grade_for_mode(make_plan(), "GOLD")
    config = create_configuration_version(values=monthly_values(), actor=owner, reason="Synthetic monthly policy")
    plan = create_configured_plan_draft(configuration_id=config.pk, name="Monthly draft", code="MONTHLY-DRAFT",
        metal_grades=[grade], actor=owner, reason="Synthetic draft")
    return customer, grade, config, plan


def synthetic_account(customer, grade, plan, start=date(2026, 1, 31)):
    account = SchemeAccount(scheme_number=f"MONTH-{uuid.uuid4().hex[:10]}", customer=customer, plan=plan,
        plan_revision=plan.revisions.first(), plan_name_snapshot=plan.name, plan_code_snapshot=plan.code,
        start_date=start, agreed_months=12, eligible_from=add_calendar_months(start, 12),
        savings_mode="GOLD", metal_grade=grade,
        **agreement_snapshot_values(plan=plan, selected_amount=Decimal("1000")))
    account.full_clean()
    account.save()
    return account


@override_settings(DEBUG=False)
class MonthlyScheduleTests(TestCase):
    def setUp(self):
        self.owner = make_owner()
        self.customer, self.grade, self.config, self.plan = fixture(self.owner)

    def windows(self, **changes):
        return build_instalment_windows(**{"configuration": self.config, "start_date": date(2026, 1, 31),
            "agreed_months": 12, "amount": Decimal("1000"), **changes})

    def preview(self, **changes):
        return preview_monthly_completion(**{"configuration": self.config, "start_date": date(2026, 1, 31),
            "agreed_months": 12, "amount": Decimal("1000"), **changes})

    def test_approved_policy_is_explicit_and_invalid_partial_combinations_fail(self):
        for field, value in MONTHLY_COMPLETION_POLICY.items():
            self.assertEqual(configuration_evidence(self.config)[field], value)
        invalid = [{"amount_policy": "VARIABLE"}, {"frequency_rule": "ONCE_PER_MONTH"},
                   {"grace_days": None}, {"grace_days": 7}, {"max_extension_months": None},
                   {"max_extension_months": 4}, {"period_basis": None}, {"catch_up_policy": None},
                   {"allow_contributions_after_eligibility": True}, {"accumulation": "INR"}]
        for change in invalid:
            with self.subTest(change=change), self.assertRaises(ValidationError):
                create_configuration_version(values={**monthly_values(), **change}, actor=self.owner, reason="Invalid")
            # QuerySet bypasses model validation: the database must reject NULL loopholes too.
            with self.subTest(db=change), self.assertRaises(IntegrityError), transaction.atomic():
                SchemePlanConfiguration.objects.filter(pk=self.config.pk).update(**change)

    def test_month_end_and_leap_day_do_not_drift(self):
        windows = self.windows()
        self.assertEqual(len(windows), 15)
        self.assertEqual(windows[0].ends_before, date(2026, 2, 28))
        self.assertEqual(windows[1].starts_on, date(2026, 2, 28))
        self.assertEqual(windows[1].ends_before, date(2026, 3, 31))
        self.assertEqual(windows[2].ends_before, date(2026, 4, 30))
        self.assertFalse(windows[11].extension)
        self.assertTrue(windows[12].extension)
        leap = self.windows(start_date=date(2024, 2, 29))
        self.assertEqual(leap[0].ends_before, date(2024, 3, 29))
        self.assertEqual(leap[11].ends_before, date(2025, 2, 28))
        self.assertEqual(leap[12].ends_before, date(2025, 3, 29))
        self.assertTrue(all(a.ends_before == b.starts_on for a, b in zip(leap, leap[1:])))

    @override_settings(TIME_ZONE="America/New_York")
    def test_india_boundary_is_half_open_independent_of_server_timezone(self):
        windows = self.windows()
        just_before = datetime(2026, 2, 27, 18, 29, 59, tzinfo=datetime_timezone.utc)
        boundary = datetime(2026, 2, 27, 18, 30, tzinfo=datetime_timezone.utc)
        self.assertEqual(window_for_instant(windows, just_before).number, 1)
        self.assertEqual(window_for_instant(windows, boundary).number, 2)
        self.assertIsNone(window_for_instant(windows, datetime(2025, 12, 1, tzinfo=datetime_timezone.utc)))
        self.assertIsNone(window_for_instant(windows, datetime(2027, 5, 1, tzinfo=datetime_timezone.utc)))
        with self.assertRaises(ValidationError):
            window_for_instant(windows, boundary.replace(tzinfo=None))

    def test_on_time_and_missed_scenarios_never_accelerate_calendar_completion(self):
        on_time = self.preview()
        self.assertEqual(on_time["projected_completion"], date(2027, 1, 31))
        self.assertEqual(on_time["assumed_payments"], 12)
        self.assertEqual(on_time["rows"][-1]["outcome"], "Not needed")
        two_missed = self.preview(missed_periods=(2, 5))
        self.assertEqual(two_missed["projected_completion"], date(2027, 3, 31))
        self.assertEqual(two_missed["original_date"], on_time["original_date"])
        three = self.preview(missed_periods=(1, 2, 3))
        self.assertEqual(three["projected_completion"], date(2027, 4, 30))
        four = self.preview(missed_periods=(1, 2, 3, 14))
        self.assertTrue(four["review_required"])
        self.assertIsNone(four["projected_completion"])
        self.assertEqual(four["assumed_payments"], 11)

    def test_invalid_dates_durations_amounts_and_periods_rejected(self):
        for change in [{"start_date": datetime(2026, 1, 1)}, {"start_date": date(9999, 1, 1)},
                       {"agreed_months": True}, {"agreed_months": 11}, {"agreed_months": 32768},
                       {"amount": 1000.0}, {"amount": Decimal("1050")}]:
            with self.subTest(change=change), self.assertRaises(ValidationError):
                self.windows(**change)
        for missed in [(0,), (16,), (1.0,), (True,), "1,2"]:
            with self.subTest(missed=missed), self.assertRaises(ValidationError):
                self.preview(missed_periods=missed)

    def test_prepare_is_atomic_idempotent_and_does_not_touch_finance(self):
        account = synthetic_account(self.customer, self.grade, self.plan)
        before = SchemeAccount.objects.filter(pk=account.pk).values().get()
        rows = prepare_instalment_periods(account_id=account.pk, actor=self.owner, reason="Test schedule")
        repeated = prepare_instalment_periods(account_id=account.pk, actor=self.owner, reason="Retry")
        self.assertEqual([row.pk for row in rows], [row.pk for row in repeated])
        self.assertEqual(len(rows), 15)
        self.assertEqual(rows[0].amount, Decimal("1000"))
        self.assertEqual(SchemeAccount.objects.filter(pk=account.pk).values().get(), before)
        self.assertFalse(Contribution.objects.exists())
        self.assertFalse(MetalAllocation.objects.exists())
        out = StringIO()
        call_command("check_instalment_schedules", stdout=out)
        self.assertIn("status=ok", out.getvalue())
        self.assertIn("payment_attribution=not_released", out.getvalue())

    def test_prepare_rolls_back_if_insertion_fails(self):
        account = synthetic_account(self.customer, self.grade, self.plan)
        with patch("django.db.models.query.QuerySet.bulk_create", side_effect=RuntimeError("test failure")), self.assertRaises(RuntimeError):
            prepare_instalment_periods(account_id=account.pk, actor=self.owner, reason="Test")
        self.assertFalse(SchemeInstalmentPeriod.objects.exists())

    def test_legacy_agreements_permissions_and_blank_reason_rejected(self):
        legacy = SchemePlan.objects.get(code="AUDIT-PLAN")
        account = enroll_customer(customer=self.customer, plan=legacy, metal_grade=grade_for_mode(legacy, "GOLD"), performed_by=self.owner)
        for actor, reason in [(self.owner, "Do not reinterpret legacy"), (self.customer.user, "Not owner"), (self.owner, " ")]:
            with self.subTest(actor=actor.pk, reason=reason), self.assertRaises(ValidationError):
                prepare_instalment_periods(account_id=account.pk, actor=actor, reason=reason)
        self.assertFalse(SchemeInstalmentPeriod.objects.exists())

    def test_period_immutability_database_boundaries_and_corruption_checks(self):
        account = synthetic_account(self.customer, self.grade, self.plan)
        rows = prepare_instalment_periods(account_id=account.pk, actor=self.owner, reason="Test")
        rows[0].amount = Decimal("2000")
        with self.assertRaises(ValidationError):
            rows[0].save()
        with self.assertRaises(ValidationError):
            rows[0].delete()
        for change in [{"number": 0}, {"number": 2}, {"amount": 0}, {"ends_before": rows[0].starts_on}, {"reason": ""}]:
            with self.subTest(change=change), self.assertRaises(IntegrityError), transaction.atomic():
                SchemeInstalmentPeriod.objects.filter(pk=rows[0].pk).update(**change)
        SchemeInstalmentPeriod.objects.filter(pk=rows[0].pk).update(amount=Decimal("2000"))
        with self.assertRaises(CommandError):
            call_command("check_instalment_schedules", stdout=StringIO())
        with self.assertRaisesMessage(ValidationError, "requires review"):
            prepare_instalment_periods(account_id=account.pk, actor=self.owner, reason="No silent repair")
        self.assertEqual(SchemeInstalmentPeriod.objects.get(pk=rows[0].pk).amount, Decimal("2000"))

    def test_missing_schedule_is_reported_not_automatically_generated(self):
        synthetic_account(self.customer, self.grade, self.plan)
        with self.assertRaises(CommandError):
            call_command("check_instalment_schedules", stdout=StringIO())
        self.assertFalse(SchemeInstalmentPeriod.objects.exists())

    def test_all_activation_boundaries_stay_closed(self):
        with self.assertRaises(ValidationError):
            enroll_customer(customer=self.customer, plan=self.plan, metal_grade=self.grade, performed_by=self.owner)
        account = synthetic_account(self.customer, self.grade, self.plan)
        prepare_instalment_periods(account_id=account.pk, actor=self.owner, reason="Test")
        # Payment services are now wired for synthetic agreements; public enrolment
        # and full-only settlement remain gated without a DEBUG bypass.
        with patch("django.utils.timezone.now", return_value=datetime(2026, 2, 1, tzinfo=datetime_timezone.utc)):
            self.assertEqual(validate_contribution_allowed(account, Decimal("1000"))[0], Decimal("1000"))
        with self.assertRaisesMessage(ValidationError, "Full-only settlement"):
            validate_redemption_amount(account, Decimal("0.1"))
        self.plan.active = True
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.plan.save()
        self.assertFalse(Contribution.objects.exists())

    def test_owner_form_and_preview_are_explicit_and_read_only(self):
        data = {**monthly_values(), "minimum_months": 12, "default_months": 12, "reason": "Owner review"}
        for field in MONTHLY_COMPLETION_POLICY:
            data.pop(field)
        data["schedule_family"] = "MONTHLY_COMPLETION"
        data.update(schedule_period="ANNIVERSARY", completion_rule="CALENDAR_AND_COUNT", missed_outcome="EXTEND_THEN_REVIEW")
        form = PlanConfigurationForm(data)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.configuration_values()["grace_days"], 0)
        forged = PlanConfigurationForm({**data, "grace_days": 7})
        self.assertFalse(forged.is_valid())
        wrong = PlanConfigurationForm({**data, "frequency_rule": "ONCE_PER_MONTH"})
        self.assertFalse(wrong.is_valid())
        self.client.force_login(self.owner)
        url = reverse("schemes:plan_configuration_detail", args=[self.config.pk])
        response = self.client.post(url, {"amount": "1000", "months": 12, "metal_grade": self.grade.pk,
            "start_date": "2026-01-31", "missed_periods": "2,5"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "31 Mar 2027")
        self.assertContains(response, "Not publishable")
        self.assertContains(response, "No extra grace")
        self.assertFalse(SchemeAccount.objects.exists())
        self.assertFalse(SchemeInstalmentPeriod.objects.exists())
        self.assertFalse(Contribution.objects.exists())
        self.client.force_login(self.customer.user)
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_calendar_evidence_does_not_gain_null_schedule_fields(self):
        values = monthly_values()
        for field in MONTHLY_COMPLETION_POLICY:
            values.pop(field)
        values["frequency_rule"] = "FLEXIBLE"
        calendar = create_configuration_version(values=values, actor=self.owner, reason="Calendar only")
        self.assertNotIn("grace_days", configuration_evidence(calendar))
        with self.assertRaises(ValidationError):
            self.windows(configuration=calendar)
        with self.assertRaises(ValidationError):
            preview_configuration_agreement(configuration=calendar, amount=Decimal("1000"), months=12,
                metal_grade=self.grade, missed_periods=(1,))


class ScheduleConcurrencyTests(TransactionTestCase):
    def test_two_preparations_serialize_to_one_immutable_schedule(self):
        # Earlier legacy migration rehearsals can leave a historical schema behind.
        # Match the other financial concurrency fixtures: restore leaves before setup.
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        owner = make_owner()
        customer, grade, config, plan = fixture(owner)
        account = synthetic_account(customer, grade, plan)
        barrier = Barrier(2)

        def prepare():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return [row.pk for row in prepare_instalment_periods(account_id=account.pk, actor=owner, reason="Concurrent fixture")]
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(prepare) for _ in range(2)]
            first, second = [future.result(timeout=30) for future in futures]
        self.assertEqual(first, second)
        self.assertEqual(SchemeInstalmentPeriod.objects.count(), 15)
