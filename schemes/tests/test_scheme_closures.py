"""Synthetic configured contracts only; no real provider or SMTP calls."""
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from io import StringIO
from unittest.mock import patch
from threading import Barrier, Event

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, close_old_connections, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse

from schemes.closures import request_scheme_closure, review_scheme_closure
from schemes.closure_selectors import accepted_closure, closure_payment_review, validate_closure_history
from schemes.models import Contribution, MetalAllocation, SchemeAccount, SchemeClosureRequest, SchemeClosureEvent
from schemes.selectors import get_customer_payment_availability, get_metal_balance, eligibility_reminder_terms
from schemes.services import retry_metal_allocation, reverse_in_store_cash_contribution, validate_contribution_allowed
from schemes.tests.test_instalment_outages import OutageFixture
from schemes.tests.test_instalment_payments import NOW


class ClosureFixture(OutageFixture):
    def request_closure(self, **changes):
        values = dict(account_id=self.account.pk,
            actor=self.account.customer.user, reason="Customer requests discontinuation",
            idempotency_key=uuid.uuid4())
        values.update(changes)
        return request_scheme_closure(**values)

    def review(self, request, action="ACCEPT", **changes):
        values = dict(request_id=request.pk, actor=self.owner, action=action,
            reason="Review customer request", idempotency_key=uuid.uuid4(), expected_sequence=request.events.count())
        values.update(changes)
        return review_scheme_closure(**values)


@override_settings(IN_STORE_CASH_CONTRIBUTIONS_ENABLED=True, PAYMENT_GATEWAY="razorpay",
    RAZORPAY_MODE="live", RAZORPAY_KEY_ID="rzp_live_fixture", RAZORPAY_KEY_SECRET="fixture",
    RAZORPAY_WEBHOOK_SECRET="fixture-webhook")
class SchemeClosureTests(ClosureFixture, TestCase):
    @override_settings(RAZORPAY_WEBHOOK_SECRET="")
    def test_missing_webhook_secret_blocks_checkout(self):
        contribution = self.online()
        self.client.force_login(self.account.customer.user)
        with patch("schemes.views.get_payment_gateway") as gateway_factory:
            response = self.client.get(reverse("schemes:razorpay_checkout", args=[contribution.pk]))
        self.assertEqual(response.status_code, 404)
        gateway_factory.assert_not_called()

    def test_pending_request_is_nonfinancial_and_preserves_payment_rights(self):
        before = SchemeAccount.objects.values().get(pk=self.account.pk)
        request = self.request_closure()
        self.assertEqual(request.status, "PENDING")
        self.assertEqual(validate_closure_history(request), 1)
        self.assertEqual(before, SchemeAccount.objects.values().get(pk=self.account.pk))
        self.assertFalse(Contribution.objects.exists())
        self.assertFalse(MetalAllocation.objects.exists())
        self.assertFalse(accepted_closure(self.account))
        self.assertTrue(get_customer_payment_availability(self.account).allowed)
        self.cash()
        self.assertEqual(Contribution.objects.count(), 1)

    def test_owner_assistance_requires_actual_authorization_reference(self):
        with self.assertRaises(ValidationError):
            self.request_closure(actor=self.owner)
        request = self.request_closure(actor=self.owner, authorization_reference="Signed showroom request 42")
        self.assertEqual(request.source, "OWNER_ASSISTED")
        self.assertEqual(request.events.get().authorization_reference, request.authorization_reference)
        self.assertEqual(request.status, "PENDING")

    def test_request_idempotency_duplicates_and_changed_evidence(self):
        key = uuid.uuid4()
        first = self.request_closure(idempotency_key=key)
        self.assertEqual(self.request_closure(idempotency_key=key).pk, first.pk)
        with self.assertRaises(ValidationError):
            self.request_closure(idempotency_key=key, reason="Different intent")
        with self.assertRaises(ValidationError):
            self.request_closure()
        self.assertEqual(SchemeClosureEvent.objects.count(), 1)

    def test_acceptance_blocks_both_channels_without_changing_entitlement_or_login(self):
        self.cash()
        before = (list(Contribution.objects.values()), list(MetalAllocation.objects.values()), get_metal_balance(self.account))
        request = self.review(self.request_closure())
        self.assertEqual(request.status, "ACCEPTED")
        self.assertEqual(self.account.effective_status_label, "Closure accepted — settlement pending")
        self.assertEqual(get_customer_payment_availability(self.account).code, "CLOSURE_PENDING")
        for action in (self.cash, self.online):
            with self.assertRaisesMessage(ValidationError, "Closure has been accepted"):
                action()
        self.assertEqual(before, (list(Contribution.objects.values()), list(MetalAllocation.objects.values()), get_metal_balance(self.account)))
        self.account.refresh_from_db()
        self.assertEqual(self.account.status, "ACTIVE")
        self.assertTrue(self.account.customer.user.is_active)
        self.assertFalse(self.account.redemptions.exists())

    def test_other_agreement_is_not_blocked(self):
        from schemes.tests.test_instalment_schedules import synthetic_account
        other = synthetic_account(self.account.customer, self.grade, self.account.plan)
        self.review(self.request_closure())
        self.assertFalse(accepted_closure(other))
        self.assertTrue(other.customer.user.is_active)

    def test_inflight_capture_still_confirms_and_allocates_after_acceptance(self):
        contribution = self.online()
        request = self.review(self.request_closure())
        self.assertEqual(closure_payment_review(self.account)["pending_payments"], 1)
        with patch("django.utils.timezone.now", return_value=NOW + timedelta(minutes=1)):
            self.webhook(contribution)
            self.webhook(contribution)
        contribution.refresh_from_db()
        self.assertEqual(contribution.status, "PAID")
        self.assertEqual(MetalAllocation.objects.count(), 1)
        self.assertEqual(closure_payment_review(self.account)["pending_payments"], 0)
        request.refresh_from_db()
        self.assertEqual(request.status, "ACCEPTED")
        self.assertFalse(self.account.redemptions.exists())

    def test_allocation_recovery_and_authorized_cash_correction_remain_available(self):
        contribution = self.online()
        self.review(self.request_closure())
        with patch("schemes.services.allocate_metal", side_effect=ValidationError("Temporary allocation failure")):
            self.webhook(contribution)
        self.assertEqual(closure_payment_review(self.account)["allocation_gaps"], 1)
        contribution.refresh_from_db()
        retry_metal_allocation(contribution=contribution, performed_by=self.owner, reason="Recovered allocation")
        self.assertEqual(closure_payment_review(self.account)["allocation_gaps"], 0)
        self.assertTrue(accepted_closure(self.account))

    def test_cash_reversal_keeps_closure_accepted_and_original_history(self):
        c = self.cash()
        self.review(self.request_closure())
        reverse_in_store_cash_contribution(contribution=c, processed_by=self.owner,
            reason="Correct wrong cash amount", reason_code="WRONG_AMOUNT")
        self.assertTrue(accepted_closure(self.account))
        self.assertEqual(Contribution.objects.count(), 1)
        self.assertEqual(closure_payment_review(self.account)["payment_history"], 1)

    def test_checkout_resume_and_provider_creation_are_blocked(self):
        c = self.online()
        self.review(self.request_closure())
        calls = self.gateway.create_order.call_count
        with self.assertRaises(ValidationError):
            self.online()
        self.assertEqual(self.gateway.create_order.call_count, calls)
        self.client.force_login(self.account.customer.user)
        response = self.client.get(reverse("schemes:razorpay_checkout", args=[c.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertIn(self.account.scheme_number, response.url)

    def test_withdraw_reject_notes_and_new_request_preserve_append_only_history(self):
        request = self.request_closure()
        self.review(request, "NOTE")
        self.review(request, "WITHDRAW", actor=self.account.customer.user)
        request.refresh_from_db()
        self.assertEqual(request.status, "WITHDRAWN")
        self.assertEqual(validate_closure_history(request), 3)
        second = self.request_closure()
        self.review(second, "REJECT")
        self.assertFalse(accepted_closure(self.account))
        self.assertEqual(SchemeClosureRequest.objects.count(), 2)
        with self.assertRaises(ValidationError):
            request.save()
        with self.assertRaises(ValidationError):
            request.delete()
        with self.assertRaises(ValidationError):
            request.events.first().save()
        with self.assertRaises(ValidationError):
            request.events.first().delete()

    def test_acceptance_cannot_be_withdrawn_or_rejected_and_stale_reviews_fail(self):
        request = self.request_closure()
        self.review(request, "NOTE")
        with self.assertRaisesMessage(ValidationError, "evidence changed"):
            self.review(request, expected_sequence=1)
        key = uuid.uuid4()
        self.review(request, idempotency_key=key)
        self.review(request, idempotency_key=key, expected_sequence=2)
        for action in ("REJECT", "WITHDRAW", "ACCEPT"):
            with self.assertRaises(ValidationError):
                self.review(request, action, authorization_reference="Actual withdrawal" if action == "WITHDRAW" else "")
        self.review(request, "NOTE")
        request.refresh_from_db()
        self.assertEqual(validate_closure_history(request), 4)

    def test_foreign_staff_inactive_and_customer_decision_permissions(self):
        request = self.request_closure()
        foreign = get_user_model().objects.create_user(username="foreign", role="CUSTOMER")
        staff = get_user_model().objects.create_user(username="cms", is_staff=True)
        for user in (foreign, staff):
            with self.assertRaises(ValidationError):
                self.request_closure(actor=user)
            with self.assertRaises(ValidationError):
                self.review(request, actor=user)
        with self.assertRaises(ValidationError):
            self.review(request, actor=self.account.customer.user)
        get_user_model().objects.filter(pk=self.owner.pk).update(is_active=False)
        with self.assertRaises(ValidationError):
            self.review(request)

    def test_owner_withdrawal_requires_customer_authorization(self):
        request = self.request_closure()
        with self.assertRaises(ValidationError):
            self.review(request, "WITHDRAW")
        self.review(request, "WITHDRAW", authorization_reference="Customer withdrawal request 43")
        request.refresh_from_db()
        self.assertEqual(request.status, "WITHDRAWN")

    def test_projection_corruption_is_reported_and_never_reopens_payments(self):
        request = self.review(self.request_closure())
        SchemeClosureRequest.objects.filter(pk=request.pk).update(status="PENDING")
        self.assertTrue(accepted_closure(self.account))
        with self.assertRaises(CommandError):
            call_command("check_scheme_closures", stdout=StringIO())
        with self.assertRaises(ValidationError):
            self.review(request, "REJECT")

    def test_database_constraints_for_open_requests_and_event_shapes(self):
        request = self.request_closure()
        values = dict(scheme_account=self.account, source="CUSTOMER", status="PENDING",
            requested_by=self.account.customer.user, actor_label="Customer", reason="Duplicate", idempotency_key=uuid.uuid4())
        with self.assertRaises(IntegrityError), transaction.atomic():
            SchemeClosureRequest.objects.create(**values)
        with self.assertRaises(IntegrityError), transaction.atomic():
            SchemeClosureRequest.objects.filter(pk=request.pk).update(source="OWNER_ASSISTED")
        with self.assertRaises(IntegrityError), transaction.atomic():
            request.events.filter(sequence=1).update(resulting_status="ACCEPTED")

    def test_legacy_agreements_remain_outside_b1_cutover(self):
        from schemes.models import SchemePlan
        from schemes.services import enroll_customer
        from schemes.tests.grade_helpers import grade_for_mode
        plan = SchemePlan.objects.get(code="AUDIT-PLAN")
        legacy = enroll_customer(customer=self.account.customer, plan=plan,
            metal_grade=grade_for_mode(plan, "GOLD"), performed_by=self.owner, reason="Legacy fixture")
        with self.assertRaisesMessage(ValidationError, "legacy cutover"):
            self.request_closure(account_id=legacy.pk)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(reverse("schemes:closure_workspace", args=[legacy.scheme_number])).status_code, 404)

    def test_private_csrf_protected_ui_and_customer_owner_workflow(self):
        url = reverse("schemes:closure_workspace", args=[self.account.scheme_number])
        self.assertEqual(self.client.get(url).status_code, 302)
        foreign = get_user_model().objects.create_user(username="ui-foreign", role="CUSTOMER")
        self.client.force_login(foreign)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.force_login(self.account.customer.user)
        response = self.client.get(url)
        self.assertContains(response, "existing contribution rules remain")
        self.assertIn("no-store", response.headers["Cache-Control"])
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.account.customer.user)
        self.assertEqual(strict.post(url, {}).status_code, 403)
        response = self.client.post(url, {"reason": "Request discontinuation", "idempotency_key": uuid.uuid4()})
        self.assertEqual(response.status_code, 302)
        request = SchemeClosureRequest.objects.get()
        self.client.force_login(self.owner)
        self.assertContains(self.client.get(reverse("schemes:closure_queue")), self.account.scheme_number)
        response = self.client.post(url, {"request_id": request.pk, "reason": "Accept customer intent",
            "idempotency_key": uuid.uuid4(), "expected_sequence": 1, "action": "ACCEPT"})
        self.assertEqual(response.status_code, 302)
        self.assertContains(self.client.get(url), "Accepted")
        request.refresh_from_db()
        self.assertEqual(request.status, "ACCEPTED")
        self.assertFalse(self.account.redemptions.exists())

    def test_read_review_reports_history_but_never_cancels_an_unused_account(self):
        request = self.review(self.request_closure())
        counts = closure_payment_review(self.account)
        self.assertTrue(all(count == 0 for count in counts.values()))
        for enabled in (False, True):
            with self.settings(CONFIGURED_PLANS_ENABLED=enabled):
                out = StringIO()
                call_command("check_scheme_closures", stdout=out)
                self.assertIn("integrity_errors=0", out.getvalue())
                self.assertIn(f"configured_intake_enabled={str(enabled).lower()}", out.getvalue())
        self.account.refresh_from_db()
        self.assertEqual(self.account.status, "ACTIVE")
        self.assertEqual(request.status, "ACCEPTED")

    def test_accepted_closure_suppresses_eligibility_reminder_terms(self):
        self.review(self.request_closure())
        self.assertIsNone(eligibility_reminder_terms(self.account, as_of=self.account.eligible_from - timedelta(days=7)))

    def test_existing_cash_receipt_retry_is_not_a_new_payment(self):
        key = uuid.uuid4()
        original = self.cash(key=key)
        self.review(self.request_closure())
        self.assertEqual(self.cash(key=key).pk, original.pk)
        self.assertEqual(Contribution.objects.count(), 1)


from schemes.tests import test_configured_agreements as calendar_fixtures
from schemes.tests import test_monthly_reminders as reminder_fixtures


@override_settings(IN_STORE_CASH_CONTRIBUTIONS_ENABLED=True)
class CalendarClosureTests(TestCase):
    setUp = calendar_fixtures.ConfiguredAgreementTests.setUp
    account = calendar_fixtures.ConfiguredAgreementTests.account

    def test_calendar_cash_online_and_direct_order_creation_respect_acceptance(self):
        from unittest.mock import Mock
        from schemes.services import initiate_contribution, initiate_razorpay_contribution, record_in_store_cash_contribution, _create_razorpay_order
        account = self.account()
        prior = initiate_contribution(scheme_account=account, amount=Decimal("1000"), payment_gateway="razorpay", gateway_mode="live")
        request = request_scheme_closure(account_id=account.pk, actor=self.customer.user,
            reason="Stop this agreement", idempotency_key=uuid.uuid4())
        review_scheme_closure(request_id=request.pk, actor=self.owner, action="ACCEPT", reason="Accept closure intent",
            idempotency_key=uuid.uuid4(), expected_sequence=1)
        gateway = Mock()
        gateway.name, gateway.mode = "razorpay", "live"
        with self.assertRaisesMessage(ValidationError, "Closure has been accepted"):
            initiate_razorpay_contribution(scheme_account=account, amount=Decimal("1000"), gateway=gateway)
        with self.assertRaisesMessage(ValidationError, "Closure has been accepted"):
            _create_razorpay_order(contribution=prior, gateway=gateway)
        with self.assertRaisesMessage(ValidationError, "Closure has been accepted"):
            record_in_store_cash_contribution(scheme_account=account, amount=Decimal("1000"),
                expected_scheme_rate_id=self.rate.pk, received_by=self.owner, idempotency_key=uuid.uuid4())
        gateway.create_order.assert_not_called()
        self.assertEqual(Contribution.objects.count(), 1)


@override_settings(**reminder_fixtures.REMINDER_SETTINGS, IN_STORE_CASH_CONTRIBUTIONS_ENABLED=True)
class ClosureReminderTests(reminder_fixtures.MonthlyReminderFixture, TestCase):
    request_closure = ClosureFixture.request_closure
    review = ClosureFixture.review

    def test_acceptance_after_mail_planning_suppresses_delivery_without_attempt(self):
        from django.core import mail
        from schemes.reminders import deliver_scheme_reminder
        from schemes.models import SchemeReminder, SchemeReminderDeliveryAttempt
        candidate = self.complete()
        request = self.request_closure()
        # Intent alone preserves the existing policy and reminder rights.
        self.assertEqual(len(self.plan().candidates), 2)
        self.review(request)
        self.assertEqual(self.plan().candidates, ())
        self.assertEqual(deliver_scheme_reminder(candidate).outcome, "SKIPPED")
        self.assertFalse(SchemeReminder.objects.exists())
        self.assertFalse(SchemeReminderDeliveryAttempt.objects.exists())
        self.assertEqual(len(mail.outbox), 0)


@override_settings(IN_STORE_CASH_CONTRIBUTIONS_ENABLED=True)
class ClosureRaceTests(ClosureFixture, TransactionTestCase):
    def setUp(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().setUp()

    def test_concurrent_same_request_is_idempotent(self):
        barrier, key = Barrier(2), uuid.uuid4()
        def submit():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return self.request_closure(idempotency_key=key).pk
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            jobs = [pool.submit(submit), pool.submit(submit)]
            self.assertEqual(jobs[0].result(timeout=60), jobs[1].result(timeout=60))
        self.assertEqual(SchemeClosureRequest.objects.count(), 1)
        self.assertEqual(SchemeClosureEvent.objects.count(), 1)

    def test_accept_and_withdraw_cannot_both_win(self):
        request, barrier = self.request_closure(), Barrier(2)
        def decide(action):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                try:
                    self.review(request, action, expected_sequence=1,
                        actor=self.owner if action == "ACCEPT" else self.account.customer.user)
                    return "RECORDED"
                except ValidationError:
                    return "STALE"
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            jobs = [pool.submit(decide, action) for action in ("ACCEPT", "WITHDRAW")]
            self.assertCountEqual([job.result(timeout=60) for job in jobs], ["RECORDED", "STALE"])
        request.refresh_from_db()
        self.assertEqual(validate_closure_history(request), 2)

    def test_accepted_closure_wins_account_lock_before_cash_submission(self):
        request, locked, attempted = self.request_closure(), Event(), Event()
        def accept():
            close_old_connections()
            try:
                with transaction.atomic():
                    SchemeAccount.objects.select_for_update().get(pk=self.account.pk)
                    locked.set()
                    self.assertTrue(attempted.wait(timeout=10))
                    self.review(request)
            finally:
                close_old_connections()
        def pay():
            close_old_connections()
            try:
                self.assertTrue(locked.wait(timeout=10))
                attempted.set()
                with self.assertRaisesMessage(ValidationError, "Closure has been accepted"):
                    self.cash()
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            jobs = [pool.submit(accept), pool.submit(pay)]
            for job in jobs:
                job.result(timeout=60)
        self.assertFalse(Contribution.objects.exists())

    def test_acceptance_and_inflight_capture_both_survive_race(self):
        contribution = self.online()
        request, barrier = self.request_closure(), Barrier(2)
        def run(action):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return self.review(request) if action == "ACCEPT" else self.webhook(contribution)
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            jobs = [pool.submit(run, action) for action in ("ACCEPT", "CAPTURE")]
            for job in jobs:
                job.result(timeout=60)
        request.refresh_from_db()
        contribution.refresh_from_db()
        self.assertEqual(request.status, "ACCEPTED")
        self.assertEqual(contribution.status, "PAID")
        self.assertEqual(MetalAllocation.objects.count(), 1)
        self.assertEqual(validate_closure_history(request), 2)


class ClosureMigrationTests(TransactionTestCase):
    def test_0031_preserves_legacy_financial_records_and_creates_no_requests(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        # Runtime factories need the current plan columns. The legacy records are
        # then carried through the historical-schema migration under test.
        from schemes.tests.test_audit_exceptions import make_account, make_paid_contribution
        account = make_account(mode="GOLD")
        make_paid_contribution(account)
        try:
            executor = MigrationExecutor(connection)
            previous = [("schemes", "0030_monthly_completion_reminders")]
            executor.migrate(previous)
            historical = executor.loader.project_state(previous).apps
            before = tuple(list(historical.get_model("schemes", name).objects.order_by("pk").values())
                for name in ("SchemeAccount", "Contribution"))
            executor = MigrationExecutor(connection)
            target = [("schemes", "0031_scheme_closure_lifecycle")]
            executor.migrate(target)
            historical = executor.loader.project_state(target).apps
            after = tuple(list(historical.get_model("schemes", name).objects.order_by("pk").values())
                for name in ("SchemeAccount", "Contribution"))
            self.assertEqual(before, after)
            self.assertFalse(historical.get_model("schemes", "SchemeClosureRequest").objects.exists())
            self.assertFalse(historical.get_model("schemes", "SchemeClosureEvent").objects.exists())
        finally:
            executor = MigrationExecutor(connection)
            executor.migrate(executor.loader.graph.leaf_nodes())
