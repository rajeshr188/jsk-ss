"""Owner evidence review cannot manufacture funds, grace, credit or eligibility."""
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import IntegrityError, close_old_connections, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from schemes.instalment_reviews import record_instalment_review
from schemes.instalment_selectors import current_instalment_period, instalment_payment_ledger_summary
from schemes.models import Contribution, InstalmentReview, MetalAllocation
from schemes.tests import test_instalment_payment_integration as integration
from schemes.tests.test_instalment_payments import NOW


class ReviewFixture:
    setUp = integration.InstalmentPaymentIntegrationTests.setUp
    create_order = integration.InstalmentPaymentIntegrationTests.create_order
    online = integration.InstalmentPaymentIntegrationTests.online
    cash = integration.InstalmentPaymentIntegrationTests.cash
    webhook = integration.InstalmentPaymentIntegrationTests.webhook

    def submit(self, claim=None, **changes):
        period = claim.period if claim else self.account.instalment_periods.get(number=1)
        last = period.reviews.order_by("-sequence").first()
        values = dict(period_id=period.pk, actor=self.owner, action="NOTE", reason="Investigated recorded evidence",
            evidence_reference="INC-123", idempotency_key=uuid.uuid4(), expected_review_sequence=last.sequence if last else 0,
            reservation_id=claim.pk if claim else None,
            expected_payment_sequence=claim.decisions.order_by("-sequence").first().sequence if claim else None)
        values.update(changes)
        return record_instalment_review(**values)

    def missing_then_valid(self):
        c = self.online()
        self.webhook(c, captured_at=None)
        self.webhook(c)
        claim = c.instalment_reservation
        claim.refresh_from_db()
        self.assertEqual(claim.state, "REVIEW")
        return c, claim, claim.decisions.order_by("-sequence").first()


@override_settings(IN_STORE_CASH_CONTRIBUTIONS_ENABLED=True)
class InstalmentReviewTests(ReviewFixture, TestCase):
    def test_verified_resolution_is_append_only_idempotent_and_does_not_change_finances(self):
        c, claim, source = self.missing_then_valid()
        before = (list(Contribution.objects.values()), list(MetalAllocation.objects.values()))
        key = uuid.uuid4()
        review = self.submit(claim, action="ACCEPT_TIMING", source_decision_id=source.pk, idempotency_key=key)
        again = self.submit(claim, action="ACCEPT_TIMING", source_decision_id=source.pk, idempotency_key=key,
            expected_review_sequence=0, expected_payment_sequence=0)
        self.assertEqual(again.pk, review.pk)
        claim.refresh_from_db()
        self.assertEqual(claim.state, "QUALIFIED")
        decision = claim.decisions.order_by("-sequence").first()
        self.assertEqual(decision.owner_review_id, review.pk)
        self.assertEqual((decision.earliest_at, decision.latest_at), (source.earliest_at, source.latest_at))
        self.assertEqual(before, (list(Contribution.objects.values()), list(MetalAllocation.objects.values())))
        self.assertEqual(instalment_payment_ledger_summary()["integrity_errors"], 0)
        self.assertEqual(instalment_payment_ledger_summary()["qualified_payments"], 1)
        with self.assertRaises(ValidationError):
            self.submit(claim, action="ACCEPT_TIMING", source_decision_id=source.pk, idempotency_key=key, reason="Different action")
        with self.assertRaises(ValidationError):
            review.save()
        with self.assertRaises(ValidationError):
            review.delete()

    def test_conflicting_or_expired_timing_cannot_be_overridden(self):
        c = self.online()
        self.webhook(c, captured_at=NOW + timedelta(minutes=20), delivered_at=NOW + timedelta(minutes=21))
        self.webhook(c)
        claim = c.instalment_reservation
        source = claim.decisions.order_by("-sequence").first()
        with self.assertRaisesMessage(ValidationError, "Conflicting"):
            self.submit(claim, action="ACCEPT_TIMING", source_decision_id=source.pk)
        self.assertEqual(InstalmentReview.objects.count(), 0)

    def test_missing_evidence_and_unverified_funds_cannot_qualify(self):
        c = self.online()
        self.webhook(c, captured_at=None)
        claim = c.instalment_reservation
        source = claim.decisions.order_by("-sequence").first()
        with self.assertRaises(ValidationError):
            self.submit(claim, action="ACCEPT_TIMING", source_decision_id=source.pk)
        with self.assertRaises(ValidationError):
            self.submit(claim, action="ACCEPT_TIMING", source_decision_id=999999)
        self.assertEqual(InstalmentReview.objects.count(), 0)

    def test_stale_review_or_payment_evidence_rejected(self):
        c, claim, source = self.missing_then_valid()
        self.submit(claim)
        with self.assertRaisesMessage(ValidationError, "Another owner review"):
            self.submit(claim, expected_review_sequence=0)
        with self.assertRaisesMessage(ValidationError, "Payment evidence changed"):
            self.submit(claim, action="ACCEPT_TIMING", source_decision_id=source.pk, expected_payment_sequence=1)

    def test_evidence_from_another_agreement_cannot_be_attached(self):
        from schemes.instalments import prepare_instalment_periods
        from schemes.tests.test_instalment_schedules import synthetic_account
        c, claim, source = self.missing_then_valid()
        original = self.account
        self.account = synthetic_account(original.customer, self.grade, original.plan)
        prepare_instalment_periods(account_id=self.account.pk, actor=self.owner, reason="Separate synthetic agreement")
        _, other_claim, other_source = self.missing_then_valid()
        with self.assertRaises(ValidationError):
            self.submit(claim, action="ACCEPT_TIMING", source_decision_id=other_source.pk)
        with self.assertRaises(ValidationError):
            self.submit(other_claim, period_id=claim.period_id)
        self.assertFalse(InstalmentReview.objects.exists())

    def test_only_active_owner_can_mutate_and_reference_is_required(self):
        customer = self.account.customer.user
        with self.assertRaisesMessage(ValidationError, "active owner"):
            self.submit(actor=customer)
        self.owner.is_active = False
        with self.assertRaises(ValidationError):
            self.submit()
        self.owner.is_active = True
        for changes in ({"reason": " "}, {"evidence_reference": " "}, {"action": "MARK_PAID"}):
            with self.assertRaises(ValidationError):
                self.submit(**changes)

    def test_outage_hold_blocks_both_channels_without_inventing_payment(self):
        review = self.submit(action="OUTAGE_HOLD")
        self.assertIsNone(review.reservation_id)
        self.assertFalse(Contribution.objects.exists())
        for initiate in (self.online, self.cash):
            with self.assertRaisesMessage(ValidationError, "outage"):
                initiate()
        self.assertEqual(instalment_payment_ledger_summary()["outage_held_accounts"], 1)
        self.assertEqual(instalment_payment_ledger_summary()["qualified_payments"], 0)
        with self.assertRaises(ValidationError):
            self.submit(action="OUTAGE_HOLD", period_id=self.account.instalment_periods.get(number=2).pk)

    def test_outage_does_not_reject_already_in_flight_verified_capture(self):
        c = self.online()
        self.submit(action="OUTAGE_HOLD")
        event = self.webhook(c)
        self.assertEqual(event.status, "PROCESSED")
        c.refresh_from_db()
        self.assertEqual(c.status, "PAID")
        self.assertEqual(c.instalment_reservation.state, "QUALIFIED")
        self.assertTrue(MetalAllocation.objects.filter(contribution=c).exists())
        with self.assertRaises(ValidationError):
            current_instalment_period(self.account)

    def test_outage_period_uses_agreement_india_date_not_request_timezone(self):
        from schemes.instalment_selectors import owner_instalment_review_periods
        with timezone.override("UTC"), patch("django.utils.timezone.now", return_value=NOW.replace(month=1, day=30, hour=19)):
            review = self.submit(action="OUTAGE_HOLD")
            self.assertTrue(owner_instalment_review_periods().filter(pk=review.period_id).exists())

    def test_notes_do_not_release_uncertain_order_or_grant_credit(self):
        from schemes.payments import PaymentGatewayError
        self.gateway.create_order.side_effect = PaymentGatewayError("Uncertain response")
        with self.assertRaises(PaymentGatewayError):
            self.online()
        c = Contribution.objects.get()
        claim = c.instalment_reservation
        self.submit(claim)
        claim.refresh_from_db()
        self.assertEqual(claim.state, "ORDERING")
        self.assertFalse(MetalAllocation.objects.exists())
        with self.assertRaises(ValidationError):
            self.submit(claim, action="ACCEPT_TIMING", source_decision_id=1)

    def test_database_rejects_blank_evidence_and_bad_action_shape(self):
        review = self.submit()
        for changes in ({"reason": ""}, {"action": "ACCEPT_TIMING"}, {"sequence": 0}):
            with self.assertRaises(IntegrityError), transaction.atomic():
                InstalmentReview.objects.filter(pk=review.pk).update(**changes)

    def test_integrity_check_detects_missing_qualification_for_accepted_review(self):
        _, claim, source = self.missing_then_valid()
        review = self.submit(claim, action="ACCEPT_TIMING", source_decision_id=source.pk)
        claim.decisions.filter(owner_review=review).delete()
        self.assertGreater(instalment_payment_ledger_summary()["integrity_errors"], 0)

    def test_owner_ui_permissions_csrf_private_cache_and_scoped_choices(self):
        c, claim, source = self.missing_then_valid()
        url = reverse("schemes:instalment_review_period", args=[claim.period_id])
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.account.customer.user)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_login(self.owner)
        response = self.client.get(url)
        self.assertContains(response, "No timestamp can be entered manually")
        self.assertIn("no-store", response.headers["Cache-Control"])
        secure = Client(enforce_csrf_checks=True)
        secure.force_login(self.owner)
        self.assertEqual(secure.post(url, {}).status_code, 403)
        data = dict(action="ACCEPT_TIMING", reason="Matched signed event", evidence_reference="INC-UI",
            source_decision=source.pk, reservation_id=claim.pk, expected_payment_sequence=source.sequence,
            expected_review_sequence=0, idempotency_key=uuid.uuid4())
        self.assertEqual(self.client.post(url, data).status_code, 302)
        self.assertEqual(self.client.post(url, data).status_code, 302)
        self.assertEqual(InstalmentReview.objects.count(), 1)
        data["reservation_id"] = 999999
        self.assertEqual(self.client.post(url, data).status_code, 404)
        data["reservation_id"] = "²"
        self.assertEqual(self.client.post(url, data).status_code, 404)


@override_settings(IN_STORE_CASH_CONTRIBUTIONS_ENABLED=True)
class InstalmentReviewRaceTests(ReviewFixture, TransactionTestCase):
    def setUp(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().setUp()

    def test_competing_review_submissions_serialize_without_duplicate_qualification(self):
        c, claim, source = self.missing_then_valid()
        barrier = Barrier(2)
        key = uuid.uuid4()
        def submit():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return record_instalment_review(period_id=claim.period_id, actor=self.owner,
                    action="ACCEPT_TIMING", reason="Concurrent owner review", evidence_reference="INC-RACE",
                    idempotency_key=key, expected_review_sequence=0, reservation_id=claim.pk,
                    source_decision_id=source.pk, expected_payment_sequence=source.sequence).pk
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(submit) for _ in range(2)]
            ids = [future.result(timeout=40) for future in futures]
        self.assertEqual(ids[0], ids[1])
        self.assertEqual(InstalmentReview.objects.count(), 1)
        self.assertEqual(claim.decisions.filter(owner_review__isnull=False).count(), 1)

    def test_outage_hold_racing_cash_serializes_without_partial_financial_entries(self):
        barrier = Barrier(2)
        def run(action):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                if action == "hold":
                    return self.submit(action="OUTAGE_HOLD").pk
                try:
                    return self.cash().pk
                except ValidationError:
                    return None
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(run, action) for action in ("hold", "cash")]
            results = [future.result(timeout=40) for future in futures]
        self.assertIsNotNone(results[0])
        count = 0 if results[1] is None else 1
        self.assertEqual(Contribution.objects.count(), count)
        self.assertEqual(MetalAllocation.objects.count(), count)
        self.assertEqual(instalment_payment_ledger_summary()["qualified_payments"], count)
        self.assertEqual(instalment_payment_ledger_summary()["integrity_errors"], 0)
