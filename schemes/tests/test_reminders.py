import io
from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from schemes.models import (
    Contribution,
    Redemption,
    SchemeAccount,
    SchemePlan,
    SchemeRate,
    SchemeReminder,
    SchemeReminderDeliveryAttempt,
)
from schemes.reminders import build_scheme_reminder_plan
from schemes.services import create_customer, enroll_customer
from schemes.tests.grade_helpers import enrolment_grade_kwargs


REMINDER_SETTINGS = {
    "EMAIL_BACKEND": "django.core.mail.backends.locmem.EmailBackend",
    "DEFAULT_FROM_EMAIL": "Jai Sri Krishna Jewellery <admin@example.com>",
    "SCHEME_REMINDERS_ENABLED": True,
    "SCHEME_REMINDER_ELIGIBILITY_DAYS": (30, 7, 1),
    "SCHEME_REMINDER_CUSTOMER_ELIGIBILITY": True,
    "SCHEME_REMINDER_OWNER_ELIGIBILITY": True,
    "SCHEME_REMINDER_OWNER_ALLOCATION_EXCEPTIONS": True,
    "SCHEME_REMINDER_CUSTOMER_REDEMPTIONS": True,
    "SCHEME_REMINDER_OWNER_REDEMPTIONS": True,
    "SCHEME_REMINDER_RETRY_LIMIT": 3,
    "SCHEME_REMINDER_BASE_URL": "https://example.com",
}


@override_settings(**REMINDER_SETTINGS)
class SchemeReminderTests(TestCase):
    def setUp(self):
        self.as_of = date(2026, 9, 4)
        self.owner = get_user_model().objects.create_user(
            username="reminder-owner@example.com",
            email="reminder-owner@example.com",
            password="owner-password-strong",
            role=get_user_model().Role.OWNER,
        )
        self.customer = create_customer(
            full_name="Reminder Customer",
            email="reminder-customer@example.com",
            mobile_number="9000000042",
            password="customer-password-strong",
        )
        self.plan = SchemePlan.objects.create(
            name="Reminder Plan",
            code="REMINDER-PLAN",
            amount_rule=SchemePlan.AmountRule.VARIABLE,
            frequency_rule=SchemePlan.FrequencyRule.FLEXIBLE,
            minimum_contribution=Decimal("100.00"),
            maximum_contribution=Decimal("100000.00"),
        )
        self.account = enroll_customer(
            customer=self.customer,
            plan=self.plan,
            **enrolment_grade_kwargs(self.plan, SchemeAccount.SavingsMode.GOLD),
            start_date=date(2025, 9, 11),
        )
        self.account.eligible_from = self.as_of + timedelta(days=7)
        self.account.save(update_fields=["eligible_from"])

    def _aware_at_noon(self):
        return timezone.make_aware(datetime.combine(self.as_of, datetime.min.time()))

    def _make_allocation_exception(self):
        scheme_rate = SchemeRate.objects.create(
            metal_grade=self.account.metal_grade,
            metal=self.account.savings_mode,
            rate_per_gram=Decimal("14667.0000"),
            purity=self.account.metal_grade.fineness,
            effective_from=self._aware_at_noon(),
        )
        return Contribution.objects.create(
            scheme_account=self.account,
            amount=Decimal("150.00"),
            contribution_period=self.as_of.replace(day=1),
            frequency_rule_snapshot=SchemePlan.FrequencyRule.FLEXIBLE,
            status=Contribution.Status.PAID_UNALLOCATED,
            payment_gateway="reminder-test",
            gateway_reference="reminder-allocation-exception",
            scheme_rate=scheme_rate,
            rate_locked_at=self._aware_at_noon(),
            allocation_error="Expected allocation test error.",
            allocation_attempted_at=self._aware_at_noon(),
            paid_at=self._aware_at_noon(),
        )

    def _make_redemption(self):
        return Redemption.objects.create(
            redemption_number="RED-REMINDER-0001",
            scheme_account=self.account,
            settlement_type=Redemption.SettlementType.METAL,
            gold_quantity=Decimal("0.010000"),
            metal_grade=self.account.metal_grade,
            processed_by=self.owner,
            completed_at=self._aware_at_noon(),
        )

    def test_plan_uses_exact_eligibility_date_and_event_audiences(self):
        contribution = self._make_allocation_exception()
        redemption = self._make_redemption()

        plan = build_scheme_reminder_plan(as_of=self.as_of)

        self.assertEqual(plan.owner_recipient_count, 1)
        self.assertEqual(plan.invalid_customer_recipient_count, 0)
        self.assertEqual(len(plan.candidates), 5)
        eligibility = [
            candidate
            for candidate in plan.candidates
            if candidate.kind == SchemeReminder.Kind.UPCOMING_ELIGIBILITY
        ]
        self.assertEqual(len(eligibility), 2)
        self.assertEqual({item.eligibility_lead_days for item in eligibility}, {7})
        self.assertEqual({item.event_date for item in eligibility}, {self.account.eligible_from})
        self.assertEqual(
            {
                candidate.contribution.pk
                for candidate in plan.candidates
                if candidate.kind == SchemeReminder.Kind.ALLOCATION_EXCEPTION
            },
            {contribution.pk},
        )
        self.assertEqual(
            {
                candidate.redemption.pk
                for candidate in plan.candidates
                if candidate.kind == SchemeReminder.Kind.COMPLETED_REDEMPTION
            },
            {redemption.pk},
        )

    def test_dry_run_is_read_only_and_apply_is_idempotent(self):
        contribution = self._make_allocation_exception()
        redemption = self._make_redemption()
        stdout = io.StringIO()

        call_command(
            "send_scheme_reminders",
            "--as-of",
            self.as_of.isoformat(),
            stdout=stdout,
        )

        self.assertIn("mode=dry-run", stdout.getvalue())
        self.assertIn("candidates=5", stdout.getvalue())
        self.assertNotIn(self.customer.email, stdout.getvalue())
        self.assertEqual(SchemeReminder.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 0)

        first_apply = io.StringIO()
        call_command(
            "send_scheme_reminders",
            "--apply",
            "--confirm-date-override",
            "--as-of",
            self.as_of.isoformat(),
            stdout=first_apply,
        )
        self.assertIn("sent=5", first_apply.getvalue())
        self.assertEqual(SchemeReminder.objects.count(), 5)
        self.assertEqual(SchemeReminderDeliveryAttempt.objects.count(), 5)
        self.assertEqual(len(mail.outbox), 5)
        self.assertTrue(
            all(message.extra_headers["X-PM-TrackLinks"] == "None" for message in mail.outbox)
        )
        self.account.refresh_from_db()
        contribution.refresh_from_db()
        redemption.refresh_from_db()
        self.assertEqual(self.account.status, SchemeAccount.Status.ACTIVE)
        self.assertEqual(contribution.status, Contribution.Status.PAID_UNALLOCATED)
        self.assertEqual(redemption.status, Redemption.Status.COMPLETED)

        second_apply = io.StringIO()
        call_command(
            "send_scheme_reminders",
            "--apply",
            "--confirm-date-override",
            "--as-of",
            self.as_of.isoformat(),
            stdout=second_apply,
        )
        self.assertIn("already_sent=5", second_apply.getvalue())
        self.assertIn("sent=0", second_apply.getvalue())
        self.assertEqual(SchemeReminderDeliveryAttempt.objects.count(), 5)
        self.assertEqual(len(mail.outbox), 5)

    @override_settings(SCHEME_REMINDERS_ENABLED=False)
    def test_apply_is_fail_closed_when_master_switch_is_disabled(self):
        stdout = io.StringIO()

        call_command(
            "send_scheme_reminders",
            "--apply",
            "--confirm-date-override",
            "--as-of",
            self.as_of.isoformat(),
            stdout=stdout,
        )

        self.assertIn("status=disabled", stdout.getvalue())
        self.assertEqual(SchemeReminder.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_historical_apply_requires_explicit_date_confirmation(self):
        historical_date = self.as_of - timedelta(days=1)
        with self.assertRaisesMessage(CommandError, "--confirm-date-override"):
            call_command(
                "send_scheme_reminders",
                "--apply",
                "--as-of",
                historical_date.isoformat(),
                stdout=io.StringIO(),
            )
        self.assertEqual(SchemeReminder.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(
        SCHEME_REMINDER_OWNER_ELIGIBILITY=False,
        SCHEME_REMINDER_OWNER_ALLOCATION_EXCEPTIONS=False,
        SCHEME_REMINDER_CUSTOMER_REDEMPTIONS=False,
        SCHEME_REMINDER_OWNER_REDEMPTIONS=False,
    )
    def test_failed_delivery_appends_sanitized_attempt_then_retries(self):
        with patch(
            "schemes.reminders.EmailMultiAlternatives.send",
            side_effect=OSError("sensitive provider detail"),
        ):
            with self.assertRaises(CommandError):
                call_command(
                    "send_scheme_reminders",
                    "--apply",
                    "--confirm-date-override",
                    "--as-of",
                    self.as_of.isoformat(),
                    stdout=io.StringIO(),
                )

        reminder = SchemeReminder.objects.get()
        first_attempt = reminder.delivery_attempts.get()
        self.assertEqual(first_attempt.outcome, SchemeReminderDeliveryAttempt.Outcome.FAILED)
        self.assertEqual(first_attempt.error_code, "OSError")
        self.assertNotIn("sensitive", first_attempt.error_code)

        call_command(
            "send_scheme_reminders",
            "--apply",
            "--confirm-date-override",
            "--as-of",
            self.as_of.isoformat(),
            stdout=io.StringIO(),
        )
        self.assertEqual(reminder.delivery_attempts.count(), 2)
        self.assertEqual(
            reminder.delivery_attempts.last().outcome,
            SchemeReminderDeliveryAttempt.Outcome.ACCEPTED,
        )

    def test_invalid_customer_recipient_is_not_contacted(self):
        self.customer.user.email = "different@example.com"
        self.customer.user.save(update_fields=["email"])
        with override_settings(
            SCHEME_REMINDER_OWNER_ELIGIBILITY=False,
            SCHEME_REMINDER_OWNER_ALLOCATION_EXCEPTIONS=False,
            SCHEME_REMINDER_CUSTOMER_REDEMPTIONS=False,
            SCHEME_REMINDER_OWNER_REDEMPTIONS=False,
        ):
            with self.assertRaises(CommandError):
                call_command(
                    "send_scheme_reminders",
                    "--apply",
                    "--confirm-date-override",
                    "--as-of",
                    self.as_of.isoformat(),
                    stdout=io.StringIO(),
                )
        self.assertEqual(SchemeReminder.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_reminder_and_attempt_are_immutable(self):
        call_command(
            "send_scheme_reminders",
            "--apply",
            "--confirm-date-override",
            "--as-of",
            self.as_of.isoformat(),
            stdout=io.StringIO(),
        )
        reminder = SchemeReminder.objects.first()
        attempt = reminder.delivery_attempts.first()
        reminder.recipient_email = "changed@example.com"
        with self.assertRaisesMessage(ValidationError, "immutable"):
            reminder.save()
        attempt.error_code = "Changed"
        with self.assertRaisesMessage(ValidationError, "immutable"):
            attempt.save()
        with self.assertRaisesMessage(ValidationError, "cannot be deleted"):
            reminder.delete()

    def test_owner_can_review_delivery_evidence_but_customer_cannot(self):
        call_command(
            "send_scheme_reminders",
            "--apply",
            "--confirm-date-override",
            "--as-of",
            self.as_of.isoformat(),
            stdout=io.StringIO(),
        )
        self.client.force_login(self.owner)
        response = self.client.get(reverse("schemes:reminder_delivery_log"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Accepted by email provider")
        self.assertContains(response, self.account.scheme_number)

        self.client.force_login(self.customer.user)
        response = self.client.get(reverse("schemes:reminder_delivery_log"))
        self.assertEqual(response.status_code, 403)
