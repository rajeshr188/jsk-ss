"""Outage amendments preserve money and original terms; uncertain payments stay held."""
import io
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, time, timedelta
from threading import Barrier
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError, close_old_connections, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse

from schemes.instalment_outages import resolve_instalment_outage
from schemes.instalment_selectors import current_instalment_period, instalment_payment_ledger_summary, validated_instalment_periods
from schemes.instalments import AGREEMENT_TIMEZONE, compensation_window, prepare_instalment_periods
from schemes.models import Contribution, InstalmentOutageResolution, MetalAllocation, PaymentWebhookEvent, SchemeAccount
from schemes.tests import test_instalment_reviews as reviews
from schemes.tests.test_instalment_payments import NOW


class OutageFixture(reviews.ReviewFixture):
    def hold(self, number=1):
        period = self.account.instalment_periods.get(number=number)
        last = period.reviews.order_by("-sequence").first()
        return self.submit(action="OUTAGE_HOLD", period_id=period.pk,
            expected_review_sequence=last.sequence if last else 0)

    def values(self, hold, **changes):
        period = hold.period
        values = dict(hold_id=hold.pk, actor=self.owner, outcome="COMPENSATE",
            reason="Exceptional provider outage prevented the scheduled payment; restored and reconciled.",
            evidence_reference="INC-RESTORED", incident_started_at=datetime.combine(period.starts_on, time.min, AGREEMENT_TIMEZONE),
            service_restored_at=datetime.combine(period.ends_before, time.min, AGREEMENT_TIMEZONE),
            customer_acknowledged_at=NOW.replace(month=7), acknowledgement_reference="CUSTOMER-ACCEPTANCE-1",
            idempotency_key=uuid.uuid4(), expected_review_sequence=hold.sequence,
            expected_period_count=self.account.instalment_periods.count())
        values.update(changes)
        return values

    def resolve(self, hold, **changes):
        with patch("django.utils.timezone.now", return_value=NOW.replace(month=7)):
            return resolve_instalment_outage(**self.values(hold, **changes))


@override_settings(IN_STORE_CASH_CONTRIBUTIONS_ENABLED=True)
class OutageResolutionTests(OutageFixture, TestCase):
    def test_compensation_preserves_original_terms_finances_and_appends_one_month(self):
        hold = self.hold()
        original = list(self.account.instalment_periods.order_by("number").values())
        account_before = SchemeAccount.objects.filter(pk=self.account.pk).values().get()
        key = uuid.uuid4()
        result = self.resolve(hold, idempotency_key=key)
        self.assertEqual(result.compensation_number, 1)
        self.assertEqual(result.compensation_period.number, 16)
        self.assertEqual(result.compensation_period.starts_on.isoformat(), "2027-04-30")
        self.assertEqual(result.compensation_period.ends_before.isoformat(), "2027-05-31")
        self.assertEqual(list(self.account.instalment_periods.filter(number__lte=15).order_by("number").values()), original)
        self.assertEqual(SchemeAccount.objects.filter(pk=self.account.pk).values().get(), account_before)
        self.assertEqual(len(validated_instalment_periods(self.account)), 16)
        self.assertEqual(len(prepare_instalment_periods(account_id=self.account.pk, actor=self.owner, reason="Idempotent schedule read")), 16)
        self.assertFalse(Contribution.objects.exists())
        self.assertFalse(MetalAllocation.objects.exists())
        again = self.resolve(hold, idempotency_key=key, expected_period_count=15)
        self.assertEqual(result.pk, again.pk)
        self.assertEqual(instalment_payment_ledger_summary()["outage_held_accounts"], 0)
        self.assertEqual(instalment_payment_ledger_summary()["outage_compensation_months"], 1)
        self.assertEqual(instalment_payment_ledger_summary()["integrity_errors"], 0)
        call_command("check_instalment_schedules", stdout=io.StringIO())
        for action in (result.save, result.delete):
            with self.assertRaises(ValidationError):
                action()
        with self.assertRaises(ValidationError):
            self.resolve(hold, idempotency_key=key, reason="Changed")
        with self.assertRaises(ValidationError):
            self.resolve(hold)

    def test_cap_is_three_separate_months_and_never_duplicates_an_affected_period(self):
        with patch("django.utils.timezone.now", return_value=NOW.replace(month=7)):
            for number in range(1, 4):
                result = self.resolve(self.hold(number))
                self.assertEqual(result.compensation_number, number)
            self.assertEqual(self.account.instalment_periods.count(), 18)
            with self.assertRaisesMessage(ValidationError, "at most three"):
                self.resolve(self.hold(4))
            with self.assertRaisesMessage(ValidationError, "already received"):
                self.resolve(self.hold(1))
        self.assertEqual(self.account.instalment_periods.count(), 18)
        self.assertEqual(InstalmentOutageResolution.objects.count(), 3)

    def test_compensating_period_uses_current_rate_and_normal_cash_ledger(self):
        from schemes.services import publish_scheme_rate
        from decimal import Decimal
        result = self.resolve(self.hold())
        at = datetime.combine(result.compensation_period.starts_on, time(10), AGREEMENT_TIMEZONE)
        with patch("django.utils.timezone.now", return_value=at):
            self.rate = publish_scheme_rate(metal_grade=self.grade, rate_per_gram=Decimal("20000"), published_by=self.owner)
            cash = self.cash()
        self.assertEqual(cash.instalment_reservation.period_id, result.compensation_period_id)
        self.assertEqual(cash.instalment_reservation.state, "QUALIFIED")
        self.assertEqual(cash.scheme_rate_id, self.rate.pk)
        self.assertEqual(instalment_payment_ledger_summary()["qualified_payments"], 1)

    def test_restore_within_window_closes_hold_without_extra_period_or_payment(self):
        hold = self.hold()
        # Resolve helper runs in July: a formerly-open window is not enough.
        with self.assertRaisesMessage(ValidationError, "remains open"):
            self.resolve(hold, outcome="RESTORED", service_restored_at=NOW - timedelta(hours=1),
                customer_acknowledged_at=NOW)

    def test_current_window_restoration_and_other_holds(self):
        hold = self.hold()
        values = self.values(hold, outcome="RESTORED", service_restored_at=NOW - timedelta(hours=1), customer_acknowledged_at=NOW)
        result = resolve_instalment_outage(**values)
        self.assertIsNone(result.compensation_period_id)
        self.assertEqual(self.account.instalment_periods.count(), 15)
        self.assertEqual(current_instalment_period(self.account).number, 1)
        self.hold()
        with self.assertRaisesMessage(ValidationError, "outage"):
            current_instalment_period(self.account)
        with self.assertRaisesMessage(ValidationError, "already has"):
            self.submit(action="OUTAGE_HOLD")

    def test_already_qualified_capture_closes_hold_without_compensation(self):
        contribution = self.online()
        hold = self.hold()
        self.webhook(contribution)
        before = (list(Contribution.objects.values()), list(MetalAllocation.objects.values()))
        with self.assertRaises(ValidationError):
            self.resolve(hold)
        resolution = self.resolve(hold, outcome="QUALIFIED")
        self.assertIsNone(resolution.compensation_period_id)
        self.assertEqual(resolution.qualification_decision.reservation.contribution_id, contribution.pk)
        with self.assertRaises(IntegrityError), transaction.atomic():
            InstalmentOutageResolution.objects.filter(pk=resolution.pk).update(qualification_decision=None)
        self.assertEqual(before, (list(Contribution.objects.values()), list(MetalAllocation.objects.values())))

    def test_unpaid_cannot_be_waived_qualified_or_compensated_before_end(self):
        hold = self.hold()
        with self.assertRaises(ValidationError):
            self.resolve(hold, outcome="QUALIFIED")
        with self.assertRaises(ValidationError):
            self.resolve(hold, outcome="WAIVE")
        with self.assertRaisesMessage(ValidationError, "ended unpaid"):
            resolve_instalment_outage(**self.values(hold, service_restored_at=NOW - timedelta(hours=1), customer_acknowledged_at=NOW))

    def test_unknown_or_pending_provider_order_cannot_be_cleared(self):
        from schemes.payments import PaymentGatewayError
        self.gateway.create_order.side_effect = PaymentGatewayError("Lost order response")
        with self.assertRaises(PaymentGatewayError):
            self.online()
        hold = self.hold()
        with self.assertRaisesMessage(ValidationError, "Reconcile"):
            self.resolve(hold)
        self.assertEqual(Contribution.objects.get().instalment_reservation.state, "ORDERING")
        self.assertEqual(InstalmentOutageResolution.objects.count(), 0)

    def test_pending_and_missing_timing_block_closure(self):
        contribution = self.online()
        hold = self.hold()
        with self.assertRaisesMessage(ValidationError, "Reconcile"):
            self.resolve(hold)
        self.webhook(contribution, captured_at=None)
        with self.assertRaisesMessage(ValidationError, "Reconcile"):
            self.resolve(hold)

    def test_unresolved_webhook_and_paid_unallocated_block_closure(self):
        contribution = self.online()
        hold = self.hold()
        event = self.webhook(contribution)
        PaymentWebhookEvent.objects.filter(pk=event.pk).update(status="FAILED")
        with self.assertRaisesMessage(ValidationError, "Reconcile"):
            self.resolve(hold, outcome="QUALIFIED")
        PaymentWebhookEvent.objects.filter(pk=event.pk).update(status="PROCESSED")
        Contribution.objects.filter(pk=contribution.pk).update(status="PAID_UNALLOCATED")
        with self.assertRaisesMessage(ValidationError, "Reconcile"):
            self.resolve(hold, outcome="QUALIFIED")

    def test_stale_schedule_review_missing_or_future_acknowledgement_rejected(self):
        hold = self.hold()
        for changes in (
            {"expected_period_count": 14}, {"expected_review_sequence": 0},
            {"acknowledgement_reference": " "}, {"customer_acknowledged_at": NOW},
            {"customer_acknowledged_at": NOW.replace(year=2028)},
            {"service_restored_at": NOW.replace(tzinfo=None)}, {"actor": self.account.customer.user},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                self.resolve(hold, **changes)
        self.assertEqual(self.account.instalment_periods.count(), 15)

    def test_incident_must_overlap_and_extra_window_must_be_fully_future(self):
        hold = self.hold()
        with self.assertRaisesMessage(ValidationError, "overlap"):
            self.resolve(hold, incident_started_at=NOW.replace(month=4), service_restored_at=NOW.replace(month=5))
        window = compensation_window(self.account, 1)
        at = datetime.combine(window.starts_on, time.min, AGREEMENT_TIMEZONE)
        with patch("django.utils.timezone.now", return_value=at), self.assertRaisesMessage(ValidationError, "already begun"):
            resolve_instalment_outage(**self.values(hold, customer_acknowledged_at=at))
        self.assertEqual(self.account.instalment_periods.count(), 15)

    def test_database_constraints_and_cross_agreement_integrity(self):
        resolution = self.resolve(self.hold())
        for changes in ({"compensation_number": 4}, {"compensation_number": None},
            {"policy_version": "OTHER"}, {"acknowledgement_reference": ""}, {"outcome": "WAIVE"}):
            with self.assertRaises(IntegrityError), transaction.atomic():
                InstalmentOutageResolution.objects.filter(pk=resolution.pk).update(**changes)
        from schemes.tests.test_instalment_schedules import synthetic_account
        other = synthetic_account(self.account.customer, self.grade, self.account.plan)
        InstalmentOutageResolution.objects.filter(pk=resolution.pk).update(scheme_account=other)
        self.assertGreater(instalment_payment_ledger_summary()["integrity_errors"], 0)

    def test_owner_ui_authorization_csrf_preview_and_idempotent_submission(self):
        hold = self.hold()
        url = reverse("schemes:instalment_outage_resolution", args=[hold.pk])
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.account.customer.user)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_login(self.owner)
        response = self.client.get(url)
        self.assertContains(response, "Separate outage compensation used: 0 of 3")
        self.assertIn("no-store", response.headers["Cache-Control"])
        secure = Client(enforce_csrf_checks=True)
        secure.force_login(self.owner)
        self.assertEqual(secure.post(url, {}).status_code, 403)
        values = self.values(hold)
        values.pop("actor")
        values.pop("hold_id")
        values["evidence_confirmed"] = True
        for key in ("incident_started_at", "service_restored_at", "customer_acknowledged_at"):
            values[key] = values[key].isoformat()
        with patch("django.utils.timezone.now", return_value=NOW.replace(month=7)):
            self.client.force_login(self.owner)
            self.assertEqual(self.client.post(url, values).status_code, 302)
            self.assertEqual(self.client.post(url, values).status_code, 302)
        self.assertEqual(InstalmentOutageResolution.objects.count(), 1)


class OutageResolutionRaceTests(OutageFixture, TransactionTestCase):
    def setUp(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().setUp()

    def test_same_acknowledged_submission_race_adds_only_one_month(self):
        hold = self.hold()
        values = self.values(hold)
        barrier = Barrier(2)
        def run():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return resolve_instalment_outage(**values).pk
            finally:
                close_old_connections()
        with patch("django.utils.timezone.now", return_value=NOW.replace(month=7)), ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(run) for _ in range(2)]
            ids = [future.result(timeout=40) for future in futures]
        self.assertEqual(ids[0], ids[1])
        self.assertEqual(InstalmentOutageResolution.objects.count(), 1)
        self.assertEqual(self.account.instalment_periods.count(), 16)

    def test_two_different_proposals_require_fresh_acknowledgement_after_first(self):
        with patch("django.utils.timezone.now", return_value=NOW.replace(month=7)):
            holds = [self.hold(1), self.hold(2)]
        proposals = [self.values(hold) for hold in holds]
        barrier = Barrier(2)
        def run(values):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                try:
                    return resolve_instalment_outage(**values).pk
                except ValidationError:
                    return None
            finally:
                close_old_connections()
        with patch("django.utils.timezone.now", return_value=NOW.replace(month=7)), ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(run, values) for values in proposals]
            ids = [future.result(timeout=40) for future in futures]
        self.assertEqual(sum(value is not None for value in ids), 1)
        self.assertEqual(InstalmentOutageResolution.objects.count(), 1)
        self.assertEqual(self.account.instalment_periods.count(), 16)
        self.assertEqual(instalment_payment_ledger_summary()["outage_held_accounts"], 1)

    def test_capture_racing_compensation_never_invents_a_replacement_credit(self):
        contribution = self.online()
        hold = self.hold()
        values = self.values(hold)
        barrier = Barrier(2)
        def run(action):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                if action == "capture":
                    return self.webhook(contribution, delivered_at=NOW.replace(month=7)).status
                try:
                    return resolve_instalment_outage(**values).pk
                except ValidationError:
                    return None
            finally:
                close_old_connections()
        with patch("django.utils.timezone.now", return_value=NOW.replace(month=7)), ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(run, action) for action in ("capture", "compensate")]
            results = [future.result(timeout=40) for future in futures]
        self.assertEqual(results, ["PROCESSED", None])
        self.assertFalse(InstalmentOutageResolution.objects.exists())
        self.assertEqual(MetalAllocation.objects.count(), 1)
        self.assertEqual(self.account.instalment_periods.count(), 15)
