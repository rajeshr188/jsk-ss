"""Completion emails derive from real full disposition, never a proposed split."""
from dataclasses import replace
from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.core import mail
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import connection, transaction, IntegrityError
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from schemes.models import (SchemeReminder, SchemeReminderDeliveryAttempt, InrSettlementProposal,
                            Contribution, InrPrincipalReceipt, InrSettlementFulfilment, SchemeAccount)
from schemes.reminders import build_scheme_reminder_plan, deliver_scheme_reminder
from schemes.tests.test_independent_inr_settlement import InrClosureFixture
from schemes.tests.test_inr_corrections import return_evidence
from schemes.tests.test_independent_instalment_reviews import instant
from schemes.tests.test_reminders import REMINDER_SETTINGS
from schemes.tests import test_reminders as legacy


class InrReminderFixture(InrClosureFixture):
    def candidates(self):
        with patch("schemes.independent_reminders.require_operational_configuration"):
            return [c for c in build_scheme_reminder_plan(as_of=timezone.localdate()).candidates
                    if c.kind == "COMPLETED_INR_SETTLEMENT"]

    def send(self, candidate):
        with patch("schemes.independent_reminders.require_operational_configuration"):
            return deliver_scheme_reminder(candidate)

    def completed(self):
        account, request, proposal = self.prepared_bonus(monthly=False)
        self.fulfil(self.handover_values(proposal))
        self.refunds(proposal)
        completion = self.finish(proposal)
        return account, proposal, completion


@override_settings(**REMINDER_SETTINGS, CONFIGURED_PLANS_ENABLED=True,
    IN_STORE_CASH_CONTRIBUTIONS_ENABLED=True, PAYMENT_INITIATION_KILL_SWITCH=False)
class InrCompletionReminderTests(InrReminderFixture, TestCase):
    def test_only_final_completion_sends_exact_principal_split_and_idempotent_history(self):
        account, request, proposal = self.prepared_bonus(monthly=False)
        self.assertEqual(self.candidates(), [])
        self.fulfil(self.handover_values(proposal))
        self.assertEqual(self.candidates(), [])
        self.refunds(proposal)
        self.assertEqual(self.candidates(), [])
        completion = self.finish(proposal)
        # Neither the global flag nor a completed source bypasses real family readiness.
        self.assertFalse(any(c.inr_completion for c in build_scheme_reminder_plan(as_of=timezone.localdate()).candidates))
        candidates = self.candidates()
        self.assertEqual(len(candidates), 2)
        self.assertEqual({c.inr_completion.pk for c in candidates}, {completion.pk})
        with self.settings(CONFIGURED_PLANS_ENABLED=False):
            self.assertEqual(self.candidates(), [])
            self.assertEqual(self.send(candidates[0]).outcome, "SKIPPED")
        self.assertEqual(deliver_scheme_reminder(candidates[0]).outcome, "SKIPPED")
        before = [list(model.objects.values()) for model in
                  (Contribution, InrPrincipalReceipt, InrSettlementProposal, InrSettlementFulfilment, SchemeAccount)]
        for candidate in candidates:
            self.assertEqual(self.send(candidate).outcome, "SENT")
            self.assertEqual(self.send(candidate).outcome, "ALREADY_SENT")
        self.assertEqual(before, [list(model.objects.values()) for model in
                         (Contribution, InrPrincipalReceipt, InrSettlementProposal, InrSettlementFulfilment, SchemeAccount)])
        self.assertEqual(SchemeReminder.objects.count(), 2)
        self.assertEqual(SchemeReminderDeliveryAttempt.objects.count(), 2)
        self.assertEqual(len(mail.outbox), 2)
        for message in mail.outbox:
            self.assertIn("INR 500.00", message.body)
            self.assertIn("INR 360.00 applied toward jewellery", message.body)
            self.assertIn("INR 140.00 returned", message.body)
            self.assertIn("paid principal only", message.body)
            self.assertNotIn("metal allocation", message.body)
            self.assertIn("Final INR purchase-credit settlement", message.alternatives[0].content)
            self.assertEqual(message.extra_headers["X-PM-TrackLinks"], "None")
        self.assertIn("/owner/closures/", next(m.body for m in mail.outbox if m.to == [self.owner.email]))
        output = StringIO()
        with patch("schemes.independent_reminders.require_operational_configuration"):
            call_command("send_scheme_reminders", "--apply", stdout=output)
        self.assertIn("already_sent=2", output.getvalue())
        self.assertEqual(len(mail.outbox), 2)

    def test_five_family_completions_use_final_event_not_maturity(self):
        for family in ("anytime", "duration", "count", "both", "benefit_duration"):
            options = {}
            if family in ("duration", "benefit_duration"):
                options.update(eligibility_policy="CALENDAR", duration_months=1)
            if family == "both":
                options.update(eligibility_policy="CALENDAR_AND_COUNT", duration_months=1)
            if family == "benefit_duration":
                options.update(missed_payment_policy="LOSE_UNEARNED_BENEFIT", max_extension_months=None,
                               benefit_on_miss="DISQUALIFY_UNEARNED")
            account = self.benefit_account(monthly=family not in ("anytime", "duration"),
                kind="VA_DISCOUNT", **options)
            self.cash(account)
            at = instant(account.eligible_from) if account.eligible_from else timezone.now()
            with patch("django.utils.timezone.now", return_value=at):
                request = self.accepted(account)
                _, token = self.prepare(request, "380.00", invoice=self.invoice("VA_DISCOUNT"))
                proposal = self.propose(self.proposal_values(request, token))
                self.fulfil(self.handover_values(proposal))
                self.refunds(proposal)
                completion = self.finish(proposal)
                candidates = [c for c in self.candidates() if c.scheme_account.pk == account.pk]
                self.assertEqual(len(candidates), 2)
                self.assertEqual(candidates[0].event_date, timezone.localdate(completion.event.created_at))
                self.assertEqual(self.send(candidates[0]).outcome, "SENT")

    def test_all_refund_early_exit_does_not_claim_a_jewellery_purchase_or_benefit_award(self):
        account = self.benefit_account(required_count=2)
        self.cash(account)
        request = self.accepted(account)
        _, token = self.prepare(request, "0.00")
        proposal = self.propose(self.proposal_values(request, token, reference=False))
        self.assertEqual(proposal.basis, "EARLY")
        self.refunds(proposal)
        self.finish(proposal)
        self.assertEqual(self.send(self.candidates()[0]).outcome, "SENT")
        self.assertIn("INR 0.00 applied toward jewellery", mail.outbox[0].body)
        self.assertIn("INR 500.00 returned", mail.outbox[0].body)

    def test_full_return_suppresses_selection_and_failed_email_retry_without_erasing_attempt(self):
        account, proposal, completion = self.completed()
        candidates = self.candidates()
        with patch("schemes.reminders.EmailMultiAlternatives.send", side_effect=RuntimeError("SMTP unavailable")):
            self.assertEqual(self.send(candidates[0]).outcome, "FAILED")
        before = list(SchemeReminderDeliveryAttempt.objects.values())
        self.correction(proposal, [return_evidence(f) for f in proposal.fulfilments.all()])
        self.assertEqual(self.candidates(), [])
        for candidate in candidates:
            self.assertEqual(self.send(candidate).outcome, "SKIPPED")
        self.assertEqual(list(SchemeReminderDeliveryAttempt.objects.values()), before)
        self.assertEqual(len(mail.outbox), 0)
        SchemeReminder.objects.get().full_clean()  # History stays valid after return.

    def test_recipient_flags_event_shape_and_current_source_are_rechecked(self):
        account, proposal, completion = self.completed()
        candidates = self.candidates()
        customer = next(c for c in candidates if c.audience == "CUSTOMER")
        owner = next(c for c in candidates if c.audience == "OWNER")
        with self.settings(SCHEME_REMINDER_CUSTOMER_REDEMPTIONS=False):
            self.assertEqual(self.send(customer).outcome, "SKIPPED")
        with self.settings(SCHEME_REMINDER_OWNER_REDEMPTIONS=False):
            self.assertEqual(self.send(owner).outcome, "SKIPPED")
        type(self.customer.user).objects.filter(pk=self.customer.user_id).update(is_active=False)
        self.assertEqual(self.send(customer).outcome, "SKIPPED")
        type(self.customer.user).objects.filter(pk=self.customer.user_id).update(is_active=True)
        other = self.benefit_account(monthly=False)
        for candidate in (replace(customer, inr_completion=None), replace(customer, scheme_account=other),
                          replace(customer, event_date=customer.event_date + timedelta(days=1)),
                          replace(customer, eligibility_lead_days=7),
                          replace(customer, contribution=account.contributions.first()),
                          replace(customer, kind="COMPLETED_REDEMPTION")):
            self.assertEqual(self.send(candidate).outcome, "SKIPPED")
        InrSettlementProposal.objects.filter(pk=proposal.pk).update(evidence_digest="f" * 64)
        self.assertEqual(self.candidates(), [])
        self.assertEqual(self.send(owner).outcome, "SKIPPED")
        self.assertFalse(SchemeReminder.objects.exists())
        self.assertEqual(len(mail.outbox), 0)


@override_settings(**REMINDER_SETTINGS, CONFIGURED_PLANS_ENABLED=True,
    IN_STORE_CASH_CONTRIBUTIONS_ENABLED=True, PAYMENT_INITIATION_KILL_SWITCH=False)
class InrReminderMigrationTests(InrReminderFixture, TransactionTestCase):
    def test_migration_roundtrip_constraints_and_retained_notification_reverse_guard(self):
        executor = MigrationExecutor(connection)
        leaves = executor.loader.graph.leaf_nodes()
        self.addCleanup(lambda: MigrationExecutor(connection).migrate(leaves))
        current_tables = set(connection.introspection.table_names())
        executor.migrate([("schemes", "0050_independent_plan_drafts")])
        MigrationExecutor(connection).migrate(leaves)
        account, proposal, completion = self.completed()
        candidate = self.candidates()[0]
        self.assertEqual(self.send(candidate).outcome, "SENT")
        reminder = SchemeReminder.objects.get()
        with self.assertRaises(ValidationError):
            reminder.save()
        for values in (dict(inr_completion=None), dict(kind="COMPLETED_REDEMPTION"), dict(eligibility_lead_days=1)):
            with self.assertRaises(IntegrityError), transaction.atomic():
                SchemeReminder.objects.filter(pk=reminder.pk).update(**values)
        with self.assertRaisesMessage(RuntimeError, "Retain INR completion notification evidence"):
            MigrationExecutor(connection).migrate([("schemes", "0050_independent_plan_drafts")])
        # Earlier reverse steps can succeed before the retained-history guard
        # refuses 0051. Restore those newer tables before other tests use models.
        MigrationExecutor(connection).migrate(leaves)
        self.assertEqual(set(connection.introspection.table_names()), current_tables)
        self.assertEqual(SchemeReminder.objects.get().inr_completion_id, completion.pk)
        self.assertEqual(SchemeReminderDeliveryAttempt.objects.count(), 1)


@override_settings(**REMINDER_SETTINGS)
class LegacyReminderMigrationTests(TransactionTestCase):
    setUp = legacy.SchemeReminderTests.setUp
    _aware_at_noon = legacy.SchemeReminderTests._aware_at_noon
    _make_redemption = legacy.SchemeReminderTests._make_redemption

    def test_old_reminder_identity_and_delivery_survive_roundtrip(self):
        self._make_redemption()
        candidate = next(c for c in build_scheme_reminder_plan(as_of=self.as_of).candidates
                         if c.kind == "COMPLETED_REDEMPTION")
        self.assertEqual(deliver_scheme_reminder(candidate).outcome, "SENT")
        original = SchemeReminder.objects.get()
        attempts = list(SchemeReminderDeliveryAttempt.objects.values())
        executor = MigrationExecutor(connection)
        leaves = executor.loader.graph.leaf_nodes()
        self.addCleanup(lambda: MigrationExecutor(connection).migrate(leaves))
        executor.migrate([("schemes", "0050_independent_plan_drafts")])
        executor = MigrationExecutor(connection)
        old_model = executor.loader.project_state([("schemes", "0050_independent_plan_drafts")]).apps.get_model("schemes", "SchemeReminder")
        self.assertEqual(old_model.objects.get(pk=original.pk).idempotency_key, original.idempotency_key)
        executor.migrate(leaves)
        self.assertIsNone(SchemeReminder.objects.get().inr_completion_id)
        self.assertEqual(deliver_scheme_reminder(candidate).outcome, "ALREADY_SENT")
        self.assertEqual(list(SchemeReminderDeliveryAttempt.objects.values()), attempts)
