"""Calendar obligations preserve duration, exact entitlement and existing contracts."""
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.core import mail
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse

from schemes.forms import PlanConfigurationForm
from schemes.instalments import (AGREEMENT_TIMEZONE, build_instalment_windows,
    compensation_window, prepare_instalment_periods, preview_monthly_completion, window_for_instant)
from schemes.instalment_selectors import get_monthly_eligibility, instalment_payment_ledger_summary
from schemes.models import SchemePlanConfiguration, SchemeInstalmentPeriod, SchemeReminder
from schemes.plan_configuration import (MONTHLY_COMPLETION_POLICY, configuration_evidence,
    create_configuration_version, create_configured_plan_draft)
from schemes.reminders import build_scheme_reminder_plan, deliver_scheme_reminder
from schemes.selectors import get_customer_payment_availability, get_metal_balance
from schemes.services import publish_scheme_rate
from schemes.settlements import preview_full_settlement
from schemes.tests.test_audit_exceptions import make_owner
from schemes.tests.test_configured_settlements import SettlementFixture
from schemes.tests.test_instalment_schedules import fixture, monthly_values, synthetic_account
from schemes.tests.test_reminders import REMINDER_SETTINGS
from schemes.tests.test_plan_publication import PublicationFixture
from schemes.tests.test_instalment_outages import OutageFixture
from schemes.tests.test_instalment_payments import NOW
from schemes.instalment_outages import resolve_instalment_outage


class CalendarFixture(SettlementFixture):
    def setUp(self):
        super().setUp()
        self.anniversary_account = self.account
        self.config = create_configuration_version(values={**monthly_values(), "period_basis": "CALENDAR_MONTH"},
            actor=self.owner, reason="Approved short first calendar month")
        self.plan = create_configured_plan_draft(configuration_id=self.config.pk, name="Calendar obligations",
            code="CAL-REQUIRED", metal_grades=[self.grade], actor=self.owner, reason="Synthetic contract")
        self.account = synthetic_account(self.account.customer, self.grade, self.plan, start=date(2026, 1, 30))
        prepare_instalment_periods(account_id=self.account.pk, actor=self.owner, reason="Calendar fixture")

    def at(self, day, hour=12, minute=0, second=0):
        return datetime.combine(day, time(hour, minute, second), AGREEMENT_TIMEZONE)

    def publish(self):
        self.rate = publish_scheme_rate(metal_grade=self.grade, rate_per_gram=Decimal("10000"), published_by=self.owner)


@override_settings(**REMINDER_SETTINGS, IN_STORE_CASH_CONTRIBUTIONS_ENABLED=True,
    PAYMENT_GATEWAY="razorpay", RAZORPAY_MODE="live", RAZORPAY_KEY_ID="rzp_live_fixture", RAZORPAY_KEY_SECRET="fixture")
class CalendarInstalmentTests(CalendarFixture, TestCase):
    @override_settings(CONFIGURED_PLANS_ENABLED=True)
    def test_publication_enrolment_freezes_calendar_basis_and_discloses_short_month(self):
        PublicationFixture.publish(self)
        self.customer = self.account.customer
        enrolled = PublicationFixture.enroll(self, start_date=date(2026, 1, 30))
        self.assertEqual(enrolled.configuration_snapshot.period_basis, "CALENDAR_MONTH")
        self.assertEqual(enrolled.instalment_periods.get(number=1).ends_before, date(2026, 2, 1))
        self.assertEqual(enrolled.eligible_from, date(2027, 1, 30))
        self.assertFalse(enrolled.contributions.exists())
        from django.template.loader import render_to_string
        rendered = render_to_string("schemes/includes/configured_offer_rules.html", {"plan": self.plan})
        self.assertIn("even when you join near month-end", rendered)
        self.assertNotIn("each agreement-anniversary month", rendered)

    def test_short_first_month_leap_year_and_enrolment_day(self):
        for start in (date(2026, 1, 30), date(2026, 1, 31), date(2028, 2, 29), date(2026, 12, 31)):
            with self.subTest(start=start):
                windows = build_instalment_windows(configuration=self.config, start_date=start, agreed_months=12, amount=Decimal("1000"))
                self.assertEqual(windows[0].starts_on, start)
                self.assertEqual(windows[0].ends_before.day, 1)
                self.assertEqual(len(windows), 15)
                self.assertEqual(window_for_instant(windows, self.at(start)).number, 1)
                boundary = self.at(windows[0].ends_before, 0)
                self.assertEqual(window_for_instant(windows, boundary - timedelta(microseconds=1)).number, 1)
                self.assertEqual(window_for_instant(windows, boundary).number, 2)
        self.assertEqual(self.account.instalment_periods.get(number=1).ends_before, date(2026, 2, 1))

    def test_preview_forecast_and_ordinary_extensions_keep_duration_floor(self):
        values = dict(configuration=self.config, start_date=self.account.start_date, agreed_months=12, amount=Decimal("1000"))
        self.assertEqual(preview_monthly_completion(**values)["projected_completion"], date(2027, 1, 30))
        self.assertEqual(preview_monthly_completion(**values, missed_periods=[1])["projected_completion"], date(2027, 2, 1))
        self.assertTrue(preview_monthly_completion(**values, missed_periods=[1, 2, 3, 4])["review_required"])
        result = get_monthly_eligibility(self.account, as_of=date(2026, 1, 30))
        self.assertEqual(result.forecast_date, date(2027, 1, 30))

    def test_enrolment_day_cash_counts_and_next_calendar_month_is_separate(self):
        self.pay_periods([1])
        with patch("django.utils.timezone.now", return_value=self.at(date(2026, 1, 31))):
            self.publish()
            with self.assertRaises(ValidationError):
                self.cash()
        self.pay_periods([2])
        self.assertEqual(instalment_payment_ledger_summary(account_id=self.account.pk)["qualified_payments"], 2)
        self.assertEqual(get_metal_balance(self.account), Decimal("0.200000"))

    def test_count_completion_waits_for_duration_reminder_and_full_settlement_agree(self):
        self.pay_periods(range(1, 13))
        self.assertEqual(self.account.instalment_periods.get(number=12).ends_before, date(2027, 1, 1))
        with patch("django.utils.timezone.now", return_value=self.at(date(2027, 1, 23))):
            result = get_monthly_eligibility(self.account)
            self.assertEqual(result.state, "WAITING_PERIOD_END")
            self.assertEqual(result.completion_date, date(2027, 1, 30))
            self.assertFalse(get_customer_payment_availability(self.account).allowed)
            candidates = [c for c in build_scheme_reminder_plan(as_of=date(2027, 1, 23)).candidates
                          if c.scheme_account.pk == self.account.pk and c.kind == "UPCOMING_MONTHLY_COMPLETION"]
            self.assertTrue(candidates)
            for candidate in candidates:
                self.assertEqual(candidate.event_date, date(2027, 1, 30))
                self.assertEqual(deliver_scheme_reminder(candidate).outcome, "SENT")
            self.assertIn("normal completion date", mail.outbox[-1].body)
            self.assertNotIn("final qualifying period ends on", mail.outbox[-1].body)
            for reminder in SchemeReminder.objects.filter(scheme_account=self.account):
                reminder.full_clean()
            closure = self.accepted()
            evidence, token = preview_full_settlement(request_id=closure.pk, actor=self.owner)
            self.assertEqual(evidence["basis"], "EARLY")
        with patch("django.utils.timezone.now", return_value=self.at(date(2027, 1, 30))):
            evidence, token = preview_full_settlement(request_id=closure.pk, actor=self.owner)
            self.assertEqual(evidence["basis"], "NORMAL")
            settled = self.settle(closure)
            self.assertEqual(settled.configured_settlement.basis, "NORMAL")
            self.assertEqual(get_metal_balance(self.account), Decimal("0"))

    def test_delayed_webhook_uses_original_evidenced_window(self):
        created = self.at(date(2026, 1, 31), 23, 58)
        with patch("django.utils.timezone.now", return_value=created):
            self.publish()
            payment = self.online()
        self.webhook(payment, captured_at=created + timedelta(seconds=20), delivered_at=self.at(date(2026, 2, 2)))
        payment.refresh_from_db()
        self.assertEqual(payment.instalment_reservation.state, "QUALIFIED")
        self.assertEqual(payment.instalment_reservation.period.number, 1)
        self.assertEqual(payment.status, "PAID")

    def test_boundary_crossing_capture_retains_funds_but_does_not_reassign(self):
        created = self.at(date(2026, 1, 31), 23, 58)
        boundary = self.at(date(2026, 2, 1), 0)
        with patch("django.utils.timezone.now", return_value=created):
            self.publish()
            payment = self.online()
        self.assertEqual(payment.instalment_reservation.expires_at, boundary)
        self.webhook(payment, captured_at=boundary + timedelta(seconds=1), delivered_at=boundary + timedelta(minutes=1))
        payment.refresh_from_db()
        self.assertEqual(payment.status, "PAID")
        self.assertEqual(payment.instalment_reservation.state, "REVIEW")
        self.assertEqual(payment.instalment_reservation.period.number, 1)
        self.assertEqual(get_metal_balance(self.account), Decimal("0.100000"))
        self.assertEqual(get_monthly_eligibility(self.account, as_of=boundary.date()).state, "REVIEW")

    def test_outage_compensation_uses_calendar_basis_without_rewriting_originals(self):
        original = list(self.account.instalment_periods.values())
        self.assertEqual(compensation_window(self.account, 1).starts_on, date(2027, 4, 1))
        hold = self.hold()
        with patch("django.utils.timezone.now", return_value=NOW.replace(month=7)):
            resolution = resolve_instalment_outage(**OutageFixture.values(self, hold))
        self.assertEqual(resolution.compensation_period.ends_before, date(2027, 5, 1))
        self.assertEqual(list(self.account.instalment_periods.filter(number__lte=15).values()), original)
        self.assertEqual(self.account.eligible_from, date(2027, 1, 30))
        self.assertEqual(self.anniversary_account.instalment_periods.get(number=1).ends_before, date(2026, 2, 28))

    def test_owner_form_separates_dimensions_and_rejects_unsupported_combinations(self):
        payload = {k: v for k, v in monthly_values().items() if k not in MONTHLY_COMPLETION_POLICY}
        payload.update(minimum_months=12, default_months=12, reason="New calendar version",
            schedule_family="MONTHLY_COMPLETION", schedule_period="CALENDAR_MONTH",
            completion_rule="CALENDAR_AND_COUNT", missed_outcome="EXTEND_THEN_REVIEW")
        form = PlanConfigurationForm(payload)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.configuration_values()["period_basis"], "CALENDAR_MONTH")
        for change in ({"schedule_period": ""}, {"completion_rule": "CALENDAR"},
                       {"missed_outcome": "NONE"}, {"schedule_family": "CALENDAR"},
                       {"completion_rule": "COUNT_ONLY"}, {"benefit_policy": "CASH_BONUS"}):
            with self.subTest(change=change):
                invalid = PlanConfigurationForm(payload | change)
                self.assertFalse(invalid.is_valid())
        for basis in (None, "UNSUPPORTED"):
            with self.assertRaises(IntegrityError), transaction.atomic():
                SchemePlanConfiguration.objects.filter(pk=self.config.pk).update(period_basis=basis)
        self.client.force_login(self.owner)
        page = self.client.get(reverse("schemes:plan_configuration_new_version", args=[self.config.pk]))
        self.assertEqual(page.context["form"].initial["schedule_period"], "CALENDAR_MONTH")
        self.assertContains(page, "Contribution obligation")
        self.assertContains(page, "Payment limit")


class CalendarMigrationTests(TransactionTestCase):
    def test_migration_preserves_old_configuration_evidence_and_periods(self):
        executor = MigrationExecutor(connection)
        leaves = executor.loader.graph.leaf_nodes()
        self.addCleanup(lambda: MigrationExecutor(connection).migrate(leaves))
        owner = make_owner()
        customer, grade, config, plan = fixture(owner)
        account = synthetic_account(customer, grade, plan)
        prepare_instalment_periods(account_id=account.pk, actor=owner, reason="Retained old agreement")
        before = (configuration_evidence(config), list(SchemeInstalmentPeriod.objects.values()))
        # Build fixtures at the current schema; only historical migration models
        # may be queried while newer configuration columns are absent.
        executor.migrate([("schemes", "0034_configured_plan_publication")])
        MigrationExecutor(connection).migrate([("schemes", "0035_calendar_month_instalments")])
        MigrationExecutor(connection).migrate(leaves)
        config.refresh_from_db()
        self.assertEqual(before, (configuration_evidence(config), list(SchemeInstalmentPeriod.objects.values())))
