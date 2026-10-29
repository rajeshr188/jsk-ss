"""Queued event notices must still describe the retained financial state."""
from dataclasses import replace
from datetime import timedelta
from unittest.mock import patch

from django.core import mail
from django.test import TestCase, override_settings

from schemes.models import Contribution, SchemeReminder, SchemeReminderDeliveryAttempt
from schemes.reminders import build_scheme_reminder_plan, deliver_scheme_reminder
from schemes.services import retry_metal_allocation, reverse_redemption
from schemes.tests import test_reminders as baseline
from schemes.tests.test_independent_metal_settlement import MetalClosureFixture
from schemes.tests.test_independent_instalment_ledger import NOW

REMINDER_SETTINGS = baseline.REMINDER_SETTINGS


@override_settings(**REMINDER_SETTINGS)
class EventReminderRevalidationTests(TestCase):
    setUp = baseline.SchemeReminderTests.setUp
    _aware_at_noon = baseline.SchemeReminderTests._aware_at_noon
    _make_allocation_exception = baseline.SchemeReminderTests._make_allocation_exception
    _make_redemption = baseline.SchemeReminderTests._make_redemption

    def candidates(self, kind):
        return [c for c in build_scheme_reminder_plan(as_of=self.as_of).candidates if c.kind == kind]

    def assert_skipped(self, candidate):
        self.assertEqual(deliver_scheme_reminder(candidate).outcome, "SKIPPED")
        self.assertFalse(SchemeReminder.objects.exists())
        self.assertFalse(SchemeReminderDeliveryAttempt.objects.exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_resolved_allocation_is_not_sent_from_retained_candidate(self):
        contribution = self._make_allocation_exception()
        candidate, = self.candidates("ALLOCATION_EXCEPTION")
        retry_metal_allocation(contribution=contribution, performed_by=self.owner,
                               reason="Resolve the exception before dispatch")
        contribution.refresh_from_db()
        self.assertEqual(contribution.status, "PAID")
        allocation = contribution.metal_allocation
        before = (allocation.pk, allocation.quantity)
        self.assert_skipped(candidate)
        allocation.refresh_from_db()
        self.assertEqual((allocation.pk, allocation.quantity), before)

    def test_reversed_redemption_is_not_sent_to_either_audience(self):
        redemption = self._make_redemption()
        candidates = self.candidates("COMPLETED_REDEMPTION")
        self.assertEqual(len(candidates), 2)
        reverse_redemption(redemption=redemption, processed_by=self.owner, reason="Complete return before dispatch")
        for candidate in candidates:
            self.assert_skipped(candidate)

    def test_event_settings_are_rechecked_at_dispatch(self):
        self._make_allocation_exception()
        self._make_redemption()
        exception, = self.candidates("ALLOCATION_EXCEPTION")
        with self.settings(SCHEME_REMINDER_OWNER_ALLOCATION_EXCEPTIONS=False):
            self.assert_skipped(exception)
        for candidate in self.candidates("COMPLETED_REDEMPTION"):
            flag = "SCHEME_REMINDER_" + candidate.audience + "_REDEMPTIONS"
            with self.settings(**{flag: False}):
                self.assert_skipped(candidate)
        self.assertEqual(deliver_scheme_reminder(exception).outcome, "SENT")
        self.assertEqual(deliver_scheme_reminder(exception).outcome, "ALREADY_SENT")

    def test_bad_event_shape_date_and_account_do_not_create_delivery_evidence(self):
        contribution = self._make_allocation_exception()
        redemption = self._make_redemption()
        exception, = self.candidates("ALLOCATION_EXCEPTION")
        completed = self.candidates("COMPLETED_REDEMPTION")[0]
        for candidate in (
            replace(exception, kind="UNSUPPORTED"),
            replace(exception, contribution=None),
            replace(exception, redemption=redemption),
            replace(exception, eligibility_lead_days=7),
            replace(exception, audience="CUSTOMER", recipient_email=self.customer.email),
            replace(exception, event_date=self.as_of + timedelta(days=1)),
            replace(completed, redemption=None),
            replace(completed, contribution=contribution),
            replace(completed, eligibility_lead_days=7),
            replace(completed, event_date=self.as_of + timedelta(days=1)),
        ):
            with self.subTest(kind=candidate.kind, candidate=candidate):
                self.assert_skipped(candidate)
        # A second real agreement must not inherit the first agreement's event.
        from schemes.services import enroll_customer
        from schemes.tests.grade_helpers import enrolment_grade_kwargs
        other = enroll_customer(customer=self.customer, plan=self.plan,
            **enrolment_grade_kwargs(self.plan, self.account.savings_mode), start_date=self.account.start_date)
        self.assert_skipped(replace(exception, scheme_account=other))
        self.assert_skipped(replace(completed, scheme_account=other))

    def test_new_exception_detection_date_invalidates_old_candidate(self):
        contribution = self._make_allocation_exception()
        candidate, = self.candidates("ALLOCATION_EXCEPTION")
        Contribution.objects.filter(pk=contribution.pk).update(
            allocation_attempted_at=contribution.allocation_attempted_at + timedelta(days=1))
        self.assert_skipped(candidate)
        current, = self.candidates("ALLOCATION_EXCEPTION")
        self.assertEqual(deliver_scheme_reminder(current).outcome, "SENT")

    def test_failed_email_is_not_retried_after_allocation_resolution(self):
        contribution = self._make_allocation_exception()
        candidate, = self.candidates("ALLOCATION_EXCEPTION")
        with patch("schemes.reminders.EmailMultiAlternatives.send", side_effect=RuntimeError("SMTP unavailable")):
            self.assertEqual(deliver_scheme_reminder(candidate).outcome, "FAILED")
        original_attempts = list(SchemeReminderDeliveryAttempt.objects.values())
        retry_metal_allocation(contribution=contribution, performed_by=self.owner,
                               reason="Resolve before SMTP retry")
        self.assertEqual(deliver_scheme_reminder(candidate).outcome, "SKIPPED")
        self.assertEqual(list(SchemeReminderDeliveryAttempt.objects.values()), original_attempts)
        self.assertEqual(SchemeReminder.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 0)


@override_settings(**REMINDER_SETTINGS, CONFIGURED_PLANS_ENABLED=True,
    IN_STORE_CASH_CONTRIBUTIONS_ENABLED=True, PAYMENT_INITIATION_KILL_SWITCH=False)
class ConfiguredEventReminderTests(MetalClosureFixture, TestCase):
    def test_actual_full_return_suppresses_queued_configured_completion(self):
        account = self.benefit_account(monthly=False, metal=True, kind="VA_DISCOUNT")
        self.cash(account)
        request = self.accepted(account)
        _, token = self.prepared(request)
        redemption = self.settle(self.settlement_values(request, token))
        candidates = [c for c in build_scheme_reminder_plan(as_of=NOW.date()).candidates
                      if c.redemption and c.redemption.pk == redemption.pk]
        self.assertEqual(len(candidates), 2)
        # Queue candidates before a real return; delivery must recheck current rights.
        self.reverse(self.reversal_values(redemption))
        for candidate in candidates:
            self.assertEqual(deliver_scheme_reminder(candidate).outcome, "SKIPPED")
        self.assertFalse(SchemeReminder.objects.exists())
        self.assertEqual(len(mail.outbox), 0)
