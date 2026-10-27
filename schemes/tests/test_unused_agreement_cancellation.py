"""B2: no-history cancellation, not a zero-balance settlement shortcut."""
import uuid
from concurrent.futures import ThreadPoolExecutor
from io import StringIO
from threading import Barrier
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import close_old_connections, connection, transaction, IntegrityError
from django.db.migrations.executor import MigrationExecutor
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse

from schemes.closures import cancel_unused_agreement
from schemes.closure_selectors import validate_closure_history
from schemes.models import Contribution, MetalAllocation, Redemption, SchemeAccount, SchemeClosureEvent, SchemeClosureRequest
from schemes.selectors import get_customer_payment_availability, get_customer_plan_next_action, get_owner_activity_summary, get_redemption_eligibility_summary
from schemes.services import reverse_in_store_cash_contribution
from schemes.tests.test_scheme_closures import ClosureFixture
from schemes.tests import test_configured_agreements as calendar_fixtures


class CancellationFixture(ClosureFixture):
    def cancel(self, request, **changes):
        values = dict(request_id=request.pk, actor=self.owner, reason="Customer no longer needs this unused agreement",
            idempotency_key=uuid.uuid4(), expected_sequence=request.events.count())
        values.update(changes)
        return cancel_unused_agreement(**values)


@override_settings(IN_STORE_CASH_CONTRIBUTIONS_ENABLED=True)
class UnusedCancellationTests(CancellationFixture, TestCase):
    def test_unused_cancellation_preserves_terms_periods_login_and_creates_no_finances(self):
        before = SchemeAccount.objects.values().get(pk=self.account.pk)
        periods = list(self.account.instalment_periods.values())
        request = self.review(self.request_closure())
        self.cancel(request)
        self.account.refresh_from_db()
        after = SchemeAccount.objects.values().get(pk=self.account.pk)
        for name in before.keys() - {"status", "updated_at"}:
            self.assertEqual(before[name], after[name], name)
        self.assertEqual(list(self.account.instalment_periods.values()), periods)
        self.assertEqual(self.account.status, "CANCELLED")
        self.assertEqual(self.account.effective_status, "CANCELLED")
        self.assertEqual(self.account.effective_status_label, "Cancelled unused agreement")
        self.assertEqual(self.account.monthly_eligibility.state, "CANCELLED")
        self.assertEqual(get_customer_payment_availability(self.account).code, "CANCELLED")
        self.assertEqual(get_customer_plan_next_action(self.account)["stage"], "Unused agreement cancelled")
        self.assertEqual(get_owner_activity_summary().active_account_count, 0)
        self.assertEqual(get_redemption_eligibility_summary().configured, ())
        self.assertTrue(self.account.customer.user.is_active)
        self.assertFalse(Contribution.objects.exists())
        self.assertFalse(MetalAllocation.objects.exists())
        self.assertFalse(Redemption.objects.exists())
        request.refresh_from_db()
        self.assertEqual(validate_closure_history(request), 3)
        self.assertEqual(list(request.events.values_list("action", flat=True)), ["REQUESTED", "ACCEPT", "CANCEL"])
        out = StringIO()
        call_command("check_scheme_closures", stdout=out)
        self.assertIn("cancelled_unused=1 integrity_errors=0", out.getvalue())

    def test_pending_request_and_non_owner_cannot_cancel(self):
        request = self.request_closure()
        with self.assertRaisesMessage(ValidationError, "accepted closure"):
            self.cancel(request)
        self.review(request)
        with self.assertRaisesMessage(ValidationError, "Only an active owner"):
            self.cancel(request, actor=self.account.customer.user)
        self.owner.is_active = False
        self.owner.save(update_fields=["is_active"])
        with self.assertRaises(ValidationError):
            self.cancel(request)
        self.assertFalse(request.events.filter(action="CANCEL").exists())

    def test_idempotent_replay_changed_key_facts_and_stale_sequence(self):
        request = self.review(self.request_closure())
        with self.assertRaisesMessage(ValidationError, "evidence changed"):
            self.cancel(request, expected_sequence=1)
        key = uuid.uuid4()
        self.cancel(request, idempotency_key=key, expected_sequence=2)
        self.cancel(request, idempotency_key=key, expected_sequence=2)
        with self.assertRaises(ValidationError):
            self.cancel(request, idempotency_key=key, reason="Changed reason")
        with self.assertRaises(ValidationError):
            self.cancel(request)
        self.assertEqual(request.events.filter(action="CANCEL").count(), 1)

    def test_paid_cash_and_reversed_zero_balance_are_both_not_unused(self):
        c = self.cash()
        request = self.review(self.request_closure())
        with self.assertRaisesMessage(ValidationError, "cannot be cancelled as unused"):
            self.cancel(request)
        reverse_in_store_cash_contribution(contribution=c, processed_by=self.owner,
            reason="Wrong cash amount", reason_code="WRONG_AMOUNT")
        with self.assertRaisesMessage(ValidationError, "cannot be cancelled as unused"):
            self.cancel(request)
        self.assertEqual(Contribution.objects.count(), 1)
        self.assertFalse(request.events.filter(action="CANCEL").exists())

    def test_all_online_attempt_states_block_even_without_a_balance(self):
        contribution = self.online()
        request = self.review(self.request_closure())
        # Deliberate historical-state fixtures: no claimed provider cancellation.
        for state in ("PENDING", "FAILED", "ABANDONED"):
            Contribution.objects.filter(pk=contribution.pk).update(status=state)
            with self.subTest(state=state), self.assertRaisesMessage(ValidationError, "cannot be cancelled as unused"):
                self.cancel(request)
        self.assertEqual(self.gateway.create_order.call_count, 1)

    def test_instalment_investigation_without_a_payment_stays_for_review(self):
        self.hold()
        request = self.review(self.request_closure())
        self.assertFalse(Contribution.objects.exists())
        with self.assertRaisesMessage(ValidationError, "instalment-review history"):
            self.cancel(request)

    def test_cancelled_agreement_cannot_restart_or_gain_reviews(self):
        self.cancel(self.review(self.request_closure()))
        for action in (self.cash, self.online, self.hold, self.request_closure):
            with self.assertRaises(ValidationError):
                action()
        self.account.refresh_from_db()
        self.account.status = "ACTIVE"
        with self.assertRaises(ValidationError):
            self.account.save(update_fields=["status"])
        self.assertFalse(Contribution.objects.exists())

    def test_no_direct_model_cancellation_and_legacy_db_guard(self):
        self.account.status = "CANCELLED"
        with self.assertRaises(ValidationError):
            self.account.save(update_fields=["status"])
        from schemes.tests.test_audit_exceptions import make_account
        with patch("schemes.tests.test_audit_exceptions.make_customer", return_value=self.account.customer):
            legacy = make_account(mode="GOLD", plan=self.account.plan.__class__.objects.get(code="AUDIT-PLAN"))
        with self.assertRaises(IntegrityError), transaction.atomic():
            SchemeAccount.objects.filter(pk=legacy.pk).update(status="CANCELLED")

    def test_integrity_check_detects_missing_cancellation_and_reopened_projection(self):
        request = self.review(self.request_closure())
        SchemeAccount.objects.filter(pk=self.account.pk).update(status="CANCELLED")
        with self.assertRaises(CommandError):
            call_command("check_scheme_closures", stdout=StringIO())
        SchemeAccount.objects.filter(pk=self.account.pk).update(status="ACTIVE")
        self.cancel(request)
        SchemeAccount.objects.filter(pk=self.account.pk).update(status="ACTIVE")
        with self.assertRaises(CommandError):
            call_command("check_scheme_closures", stdout=StringIO())

    def test_private_owner_form_confirmation_csrf_and_customer_history(self):
        request = self.review(self.request_closure())
        url = reverse("schemes:closure_workspace", args=[self.account.scheme_number])
        data = dict(operation="cancel_unused", request_id=request.pk, expected_sequence=2,
            idempotency_key=uuid.uuid4(), reason="Confirmed unused cancellation", confirm_unused_cancellation="on")
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        response = client.get(url)
        self.assertContains(response, "Cancel unused agreement")
        self.assertContains(response, 'id="cancel_reason"', count=1)
        self.assertContains(response, 'id="id_reason"', count=1)
        self.assertEqual(client.post(url, data).status_code, 403)
        data["csrfmiddlewaretoken"] = client.cookies["csrftoken"].value
        missing = data.copy()
        missing.pop("confirm_unused_cancellation")
        self.assertEqual(client.post(url, missing).status_code, 200)
        self.assertFalse(request.events.filter(action="CANCEL").exists())
        self.assertEqual(client.post(url, data).status_code, 302)
        self.assertEqual(client.post(url, data).status_code, 302)
        client.force_login(self.account.customer.user)
        self.assertContains(client.get(url), "This unused agreement has been cancelled")
        data["csrfmiddlewaretoken"] = client.cookies["csrftoken"].value
        self.assertEqual(client.post(url, data).status_code, 403)

    def test_foreign_customer_cannot_read_or_cancel_and_other_agreement_is_unchanged(self):
        from schemes.tests.test_audit_exceptions import make_customer
        from schemes.tests.test_instalment_schedules import synthetic_account
        other = synthetic_account(make_customer("other-unused@example.com"), self.grade, self.account.plan)
        request = self.review(self.request_closure())
        self.client.force_login(other.customer.user)
        url = reverse("schemes:closure_workspace", args=[self.account.scheme_number])
        self.assertEqual(self.client.get(url).status_code, 404)
        with self.assertRaises(ValidationError):
            self.cancel(request, actor=other.customer.user)
        self.cancel(request)
        other.refresh_from_db()
        self.assertEqual(other.status, "ACTIVE")


class CalendarCancellationTests(TestCase):
    setUp = calendar_fixtures.ConfiguredAgreementTests.setUp
    account = calendar_fixtures.ConfiguredAgreementTests.account

    def test_unused_calendar_agreement_can_be_cancelled(self):
        from schemes.closures import request_scheme_closure, review_scheme_closure
        account = self.account()
        request = request_scheme_closure(account_id=account.pk, actor=self.customer.user,
            reason="Never used", idempotency_key=uuid.uuid4())
        review_scheme_closure(request_id=request.pk, actor=self.owner, action="ACCEPT", reason="Accept",
            idempotency_key=uuid.uuid4(), expected_sequence=1)
        cancel_unused_agreement(request_id=request.pk, actor=self.owner, reason="No attempts",
            idempotency_key=uuid.uuid4(), expected_sequence=2)
        account.refresh_from_db()
        self.assertEqual(account.effective_status, "CANCELLED")


@override_settings(IN_STORE_CASH_CONTRIBUTIONS_ENABLED=True)
class CancellationRaceTests(CancellationFixture, TransactionTestCase):
    def setUp(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().setUp()

    def test_concurrent_same_cancellation_appends_once(self):
        request = self.review(self.request_closure())
        barrier, key = Barrier(2), uuid.uuid4()
        def submit():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return self.cancel(request, idempotency_key=key, expected_sequence=2).pk
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            jobs = [pool.submit(submit), pool.submit(submit)]
            self.assertEqual(jobs[0].result(timeout=60), jobs[1].result(timeout=60))
        self.assertEqual(request.events.filter(action="CANCEL").count(), 1)

    def test_cancellation_racing_cash_after_acceptance_never_creates_money(self):
        request = self.review(self.request_closure())
        barrier = Barrier(2)
        def run(cancel):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                if cancel:
                    return self.cancel(request)
                with self.assertRaises(ValidationError):
                    self.cash()
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            jobs = [pool.submit(run, cancel) for cancel in (True, False)]
            for job in jobs:
                job.result(timeout=60)
        self.assertFalse(Contribution.objects.exists())
        self.account.refresh_from_db()
        self.assertEqual(self.account.status, "CANCELLED")


class CancellationMigrationTests(TransactionTestCase):
    def test_0032_preserves_existing_records_without_cancelling_anything(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        # Current service factories require the current schema (including later
        # publication columns). Create legacy evidence before the old-schema rehearsal.
        from schemes.tests.test_audit_exceptions import make_account, make_paid_contribution
        account = make_account(mode="GOLD")
        make_paid_contribution(account)
        try:
            executor = MigrationExecutor(connection)
            previous = [("schemes", "0031_scheme_closure_lifecycle")]
            executor.migrate(previous)
            old_apps = executor.loader.project_state(previous).apps
            before = (list(old_apps.get_model("schemes", "SchemeAccount").objects.values()),
                list(old_apps.get_model("schemes", "Contribution").objects.values()))
            executor = MigrationExecutor(connection)
            target = [("schemes", "0032_unused_agreement_cancellation")]
            executor.migrate(target)
            new_apps = executor.loader.project_state(target).apps
            self.assertEqual(before, (list(new_apps.get_model("schemes", "SchemeAccount").objects.values()),
                list(new_apps.get_model("schemes", "Contribution").objects.values())))
            self.assertFalse(new_apps.get_model("schemes", "SchemeClosureEvent").objects.exists())
            self.assertFalse(new_apps.get_model("schemes", "SchemeAccount").objects.filter(status="CANCELLED").exists())
        finally:
            executor = MigrationExecutor(connection)
            executor.migrate(executor.loader.graph.leaf_nodes())
