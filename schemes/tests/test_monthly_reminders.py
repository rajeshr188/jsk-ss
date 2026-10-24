"""Policy-aware notices use current evidence; they never authorize settlement."""
import io
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from threading import Barrier, Event
from unittest.mock import patch

from django.core import mail
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError, close_old_connections, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase, override_settings

from schemes.models import Contribution, MetalAllocation, SchemeAccount, SchemeReminder, SchemeReminderDeliveryAttempt
from schemes.reminders import build_scheme_reminder_plan, deliver_scheme_reminder
from schemes.services import publish_scheme_rate, reverse_in_store_cash_contribution
from schemes.tests.test_instalment_outages import OutageFixture
from schemes.tests import test_monthly_eligibility as eligibility_tests
from schemes.tests.test_reminders import REMINDER_SETTINGS


class MonthlyReminderFixture(OutageFixture):
    instant = eligibility_tests.MonthlyEligibilityTests.instant
    pay_periods = eligibility_tests.MonthlyEligibilityTests.pay_periods

    def complete(self, *, extended=False):
        self.pay_periods(range(2, 13) if extended else range(1, 12))
        self.processing_at = self.instant(13 if extended else 12, end=True) - timedelta(days=7)
        clock = patch("django.utils.timezone.now", return_value=self.processing_at)
        clock.start()
        self.addCleanup(clock.stop)
        self.rate = publish_scheme_rate(metal_grade=self.grade, rate_per_gram=Decimal("10000"), published_by=self.owner)
        self.last_payment = self.cash()
        return self.candidate()

    def candidate(self):
        return next(c for c in self.plan().candidates if c.kind == "UPCOMING_MONTHLY_COMPLETION" and c.audience == "CUSTOMER")

    def plan(self):
        return build_scheme_reminder_plan(as_of=self.processing_at.date())

    def reverse_last(self):
        reverse_in_store_cash_contribution(contribution=self.last_payment, processed_by=self.owner,
            reason_code="WRONG_AMOUNT", reason="Correcting the physical receipt")


@override_settings(**REMINDER_SETTINGS, IN_STORE_CASH_CONTRIBUTIONS_ENABLED=True)
class MonthlyReminderTests(MonthlyReminderFixture, TestCase):
    def test_forecast_or_original_date_without_count_never_sends_monthly_notice(self):
        plan = build_scheme_reminder_plan(as_of=self.account.eligible_from - timedelta(days=7))
        self.assertEqual(plan.candidates, ())
        self.assertFalse(SchemeReminder.objects.exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_extended_completion_has_distinct_identity_and_no_redemption_promise(self):
        candidate = self.complete(extended=True)
        self.assertNotEqual(candidate.event_date, self.account.eligible_from)
        self.assertNotEqual(candidate.idempotency_key,
            replace(candidate, kind="UPCOMING_ELIGIBILITY").idempotency_key)
        before = (list(SchemeAccount.objects.values()), list(Contribution.objects.values()), list(MetalAllocation.objects.values()))
        plan = self.plan()
        self.assertEqual(len(plan.candidates), 2)
        for item in plan.candidates:
            self.assertEqual(deliver_scheme_reminder(item).outcome, "SENT")
            self.assertEqual(deliver_scheme_reminder(item).outcome, "ALREADY_SENT")
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(SchemeReminderDeliveryAttempt.objects.count(), 2)
        message = mail.outbox[0]
        self.assertIn("all 12 required qualifying payments", message.body)
        self.assertIn("not redemption approval", message.body)
        self.assertIn("Full jewellery settlement requires showroom review and customer confirmation", message.body)
        self.assertIn("28 Feb 2027", message.body)
        self.assertIn("31 Jan 2027", message.body)
        self.assertNotIn("becomes eligible for redemption", message.body)
        self.assertIn("not redemption approval", message.alternatives[0].content)
        self.assertEqual(message.extra_headers["X-PM-TrackLinks"], "None")
        self.assertEqual(before, (list(SchemeAccount.objects.values()), list(Contribution.objects.values()), list(MetalAllocation.objects.values())))

    def test_reversal_between_plan_and_delivery_skips_without_attempt(self):
        candidate = self.complete()
        self.reverse_last()
        self.assertEqual(deliver_scheme_reminder(candidate).outcome, "SKIPPED")
        self.assertFalse(SchemeReminder.objects.exists())
        self.assertFalse(SchemeReminderDeliveryAttempt.objects.exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_outage_hold_between_plan_and_delivery_skips(self):
        candidate = self.complete()
        self.hold(12)
        self.assertEqual(deliver_scheme_reminder(candidate).outcome, "SKIPPED")
        self.assertEqual(self.plan().candidates, ())

    def test_paid_row_without_allocation_is_not_treated_as_fully_reconciled(self):
        candidate = self.complete()
        # Deliberate corruption in a disposable test DB, not an operational remedy.
        MetalAllocation.objects.filter(contribution=self.last_payment).delete()
        self.assertTrue(self.account.monthly_eligibility.allocation_pending)
        self.assertEqual(deliver_scheme_reminder(candidate).outcome, "SKIPPED")
        self.assertEqual(self.plan().candidates, ())
        self.assertEqual(len(mail.outbox), 0)

    def test_allocation_pending_suppresses_monthly_notice_but_keeps_owner_exception(self):
        self.pay_periods(range(1, 12))
        self.processing_at = self.instant(12, end=True) - timedelta(days=7)
        with patch("django.utils.timezone.now", return_value=self.processing_at):
            self.rate = publish_scheme_rate(metal_grade=self.grade, rate_per_gram=Decimal("10000"), published_by=self.owner)
            c = self.online()
            with patch("schemes.services.allocate_metal", side_effect=ValidationError("Allocation fixture")):
                self.webhook(c, captured_at=self.processing_at + timedelta(seconds=30),
                             delivered_at=self.processing_at + timedelta(seconds=40))
            candidates = self.plan().candidates
            self.assertEqual([item.kind for item in candidates], ["ALLOCATION_EXCEPTION"])

    def test_fresh_customer_email_and_active_status_are_rechecked(self):
        candidate = self.complete()
        user = self.account.customer.user
        user.is_active = False
        user.save(update_fields=["is_active"])
        self.assertEqual(deliver_scheme_reminder(candidate).outcome, "SKIPPED")
        user.is_active = True
        user.email = "changed@example.com"
        user.save(update_fields=["is_active", "email"])
        self.assertEqual(deliver_scheme_reminder(candidate).outcome, "SKIPPED")
        self.assertEqual(len(mail.outbox), 0)

    def test_owner_permission_and_flags_are_rechecked(self):
        candidate = self.complete()
        owner_candidate = next(c for c in self.plan().candidates if c.audience == "OWNER")
        self.owner.is_active = False
        self.owner.save(update_fields=["is_active"])
        self.assertEqual(deliver_scheme_reminder(owner_candidate).outcome, "SKIPPED")
        with override_settings(SCHEME_REMINDERS_ENABLED=False):
            self.assertEqual(deliver_scheme_reminder(candidate).outcome, "SKIPPED")
        with override_settings(SCHEME_REMINDER_CUSTOMER_ELIGIBILITY=False):
            self.assertEqual(deliver_scheme_reminder(candidate).outcome, "SKIPPED")
        self.assertFalse(SchemeReminder.objects.exists())

    def test_date_rollover_and_confirmed_historical_override_do_not_send_stale_monthly_notice(self):
        candidate = self.complete()
        with patch("django.utils.timezone.now", return_value=self.processing_at + timedelta(days=1)):
            self.assertEqual(deliver_scheme_reminder(candidate, as_of=self.processing_at.date()).outcome, "SKIPPED")
            output = io.StringIO()
            call_command("send_scheme_reminders", "--apply", "--as-of", self.processing_at.date().isoformat(),
                "--confirm-date-override", stdout=output)
            self.assertIn("skipped=2", output.getvalue())
        self.assertEqual(len(mail.outbox), 0)

    def test_forged_date_kind_and_lead_cannot_bypass_evaluation(self):
        candidate = self.complete()
        for forged in (replace(candidate, event_date=candidate.event_date + timedelta(days=1)),
                       replace(candidate, kind="UPCOMING_ELIGIBILITY"),
                       replace(candidate, eligibility_lead_days=1)):
            self.assertEqual(deliver_scheme_reminder(forged).outcome, "SKIPPED")
        self.assertFalse(SchemeReminder.objects.exists())

    def test_failed_mail_retry_rechecks_evidence_and_preserves_attempt(self):
        candidate = self.complete()
        with patch("schemes.reminders.EmailMultiAlternatives.send", side_effect=OSError("Secret transport details")):
            self.assertEqual(deliver_scheme_reminder(candidate).outcome, "FAILED")
        reminder = SchemeReminder.objects.get()
        self.reverse_last()
        self.assertEqual(deliver_scheme_reminder(candidate).outcome, "SKIPPED")
        self.assertEqual(reminder.delivery_attempts.count(), 1)
        self.assertEqual(reminder.delivery_attempts.get().error_code, "OSError")
        reminder.full_clean()  # historical evidence survives today's reversal
        self.assertEqual(len(mail.outbox), 0)

    def test_changed_completion_creates_new_identity_without_rewriting_old_notice(self):
        original = self.complete()
        self.assertEqual(deliver_scheme_reminder(original).outcome, "SENT")
        old = SchemeReminder.objects.values().get()
        self.reverse_last()
        self.processing_at = self.instant(13, end=True) - timedelta(days=7)
        with patch("django.utils.timezone.now", return_value=self.processing_at):
            self.rate = publish_scheme_rate(metal_grade=self.grade, rate_per_gram=Decimal("10000"), published_by=self.owner)
            self.cash()
            revised = self.candidate()
            self.assertNotEqual(original.idempotency_key, revised.idempotency_key)
            self.assertEqual(deliver_scheme_reminder(original).outcome, "SKIPPED")
            self.assertEqual(deliver_scheme_reminder(revised).outcome, "SENT")
        self.assertEqual(old, SchemeReminder.objects.values().get(pk=old["id"]))
        self.assertEqual(SchemeReminder.objects.count(), 2)

    def test_db_and_model_reject_invalid_monthly_reminder_shape(self):
        candidate = self.complete()
        reminder = deliver_scheme_reminder(candidate).reminder
        with self.assertRaises(IntegrityError), transaction.atomic():
            SchemeReminder.objects.filter(pk=reminder.pk).update(eligibility_lead_days=None)
        reminder.event_date += timedelta(days=1)
        with self.assertRaises(ValidationError):
            reminder.full_clean()

    def test_command_dry_run_and_apply_are_idempotent(self):
        self.complete()
        output = io.StringIO()
        call_command("send_scheme_reminders", stdout=output)
        self.assertIn("candidates=2", output.getvalue())
        self.assertFalse(SchemeReminder.objects.exists())
        call_command("send_scheme_reminders", "--apply", stdout=io.StringIO())
        output = io.StringIO()
        call_command("send_scheme_reminders", "--apply", stdout=output)
        self.assertIn("already_sent=2", output.getvalue())
        self.assertEqual(len(mail.outbox), 2)


@override_settings(**REMINDER_SETTINGS, IN_STORE_CASH_CONTRIBUTIONS_ENABLED=True)
class MonthlyReminderRaceTests(MonthlyReminderFixture, TransactionTestCase):
    def setUp(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().setUp()

    def test_two_dispatchers_record_one_accepted_email(self):
        candidate = self.complete()
        barrier = Barrier(2)
        def send():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return deliver_scheme_reminder(candidate).outcome
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(send) for _ in range(2)]
            self.assertCountEqual([f.result(timeout=60) for f in futures], ["SENT", "ALREADY_SENT"])
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(SchemeReminderDeliveryAttempt.objects.count(), 1)

    def test_committed_reversal_wins_over_waiting_dispatch(self):
        candidate = self.complete()
        locked, attempted = Event(), Event()
        def reverse():
            close_old_connections()
            try:
                with transaction.atomic():
                    SchemeAccount.objects.select_for_update().get(pk=self.account.pk)
                    locked.set()
                    self.assertTrue(attempted.wait(timeout=10))
                    self.reverse_last()
            finally:
                close_old_connections()
        def send():
            close_old_connections()
            try:
                self.assertTrue(locked.wait(timeout=10))
                attempted.set()
                return deliver_scheme_reminder(candidate).outcome
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            reversal, delivery = pool.submit(reverse), pool.submit(send)
            reversal.result(timeout=60)
            self.assertEqual(delivery.result(timeout=60), "SKIPPED")
        self.assertEqual(len(mail.outbox), 0)
        self.assertFalse(SchemeReminder.objects.exists())


class MonthlyReminderMigrationTests(TransactionTestCase):
    def test_forward_migration_preserves_legacy_reminder_and_attempt(self):
        executor = MigrationExecutor(connection)
        # Other migration tests may leave unrelated apps at historical versions.
        # Restore their current columns before creating runtime-model fixtures.
        executor.migrate(executor.loader.graph.leaf_nodes())
        from schemes.tests.test_audit_exceptions import make_account
        account = make_account(mode=SchemeAccount.SavingsMode.GOLD)
        executor = MigrationExecutor(connection)
        try:
            executor.migrate([("schemes", "0029_instalment_order_recovery")])
            historical = executor.loader.project_state([("schemes", "0029_instalment_order_recovery")]).apps
            Account = historical.get_model("schemes", "SchemeAccount")
            Reminder = historical.get_model("schemes", "SchemeReminder")
            Attempt = historical.get_model("schemes", "SchemeReminderDeliveryAttempt")
            reminder = Reminder.objects.create(idempotency_key="a" * 64,
                kind="UPCOMING_ELIGIBILITY", audience="CUSTOMER", recipient_email=account.customer.email,
                scheme_account_id=account.pk, event_date=account.eligible_from, eligibility_lead_days=7)
            Attempt.objects.create(reminder=reminder, outcome="ACCEPTED",
                accepted_count=1, backend="django.core.mail.backends.locmem.EmailBackend")
            before = (list(Reminder.objects.values()), list(Attempt.objects.values()),
                      list(Account.objects.values()))
            executor = MigrationExecutor(connection)
            executor.migrate([("schemes", "0030_monthly_completion_reminders")])
            historical = executor.loader.project_state([("schemes", "0030_monthly_completion_reminders")]).apps
            Account = historical.get_model("schemes", "SchemeAccount")
            Reminder = historical.get_model("schemes", "SchemeReminder")
            Attempt = historical.get_model("schemes", "SchemeReminderDeliveryAttempt")
            self.assertEqual(before, (list(Reminder.objects.values()), list(Attempt.objects.values()),
                                     list(Account.objects.values())))
        finally:
            executor = MigrationExecutor(connection)
            executor.migrate(executor.loader.graph.leaf_nodes())
