"""Independent review/amendments on disposable contracts; activation stays closed."""
import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, time, timedelta
from decimal import Decimal
from io import StringIO
from threading import Barrier
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import connections
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse

from schemes.instalment_outages import resolve_instalment_outage
from schemes.instalment_reviews import record_instalment_review
from schemes.instalment_selectors import (current_instalment_period, instalment_payment_ledger_summary,
    validated_instalment_periods)
from schemes.instalments import AGREEMENT_TIMEZONE, compensation_window, prepare_instalment_periods
from schemes.models import (Contribution, InrPrincipalReceipt, InstalmentOutageResolution, InstalmentReview,
    MetalAllocation, PaymentWebhookEvent, SchemeAccount)
from schemes.services import initiate_razorpay_contribution, process_razorpay_webhook, publish_scheme_rate
from schemes.tests.test_independent_instalment_ledger import NOW
from schemes.tests import test_independent_payment_entry as entry
from schemes.tests.test_independent_enrolment import future_readiness_only


def instant(day, hour=10):
    return datetime.combine(day, time(hour), AGREEMENT_TIMEZONE)


class IndependentReviewFixture:
    setUp = entry.IndependentPaymentEntryTests.setUp
    cash = entry.IndependentPaymentEntryTests.cash
    gateway = entry.IndependentPaymentEntryTests.gateway

    def agreement(self, **changes):
        return entry.IndependentPaymentEntryTests.account(self, monthly=True, **changes)

    def review(self, period, **changes):
        last = period.reviews.order_by("-sequence").first()
        values = dict(period_id=period.pk, actor=self.owner, action="OUTAGE_HOLD",
            reason="Exceptional outage investigation", evidence_reference="INC-TEST",
            idempotency_key=uuid.uuid4(), expected_review_sequence=last.sequence if last else 0)
        with future_readiness_only():
            return record_instalment_review(**(values | changes))

    def hold(self, account, number=1):
        period = account.instalment_periods.get(number=number)
        with patch("django.utils.timezone.now", return_value=instant(period.starts_on)):
            return self.review(period)

    def resolution_values(self, hold, **changes):
        at = instant(hold.period.ends_before)
        return dict(hold_id=hold.pk, actor=self.owner, outcome="COMPENSATE", reason="Restored exceptional outage",
            evidence_reference="INC-RECONCILED", incident_started_at=instant(hold.period.starts_on, 0),
            service_restored_at=instant(hold.period.ends_before, 0), customer_acknowledged_at=at,
            acknowledgement_reference="CUSTOMER-PROPOSAL-ACK", idempotency_key=uuid.uuid4(),
            expected_review_sequence=hold.period.reviews.order_by("-sequence").first().sequence,
            expected_period_count=hold.period.scheme_account.instalment_periods.count()) | changes

    def resolve(self, hold, **changes):
        values = self.resolution_values(hold, **changes)
        with future_readiness_only(), patch("django.utils.timezone.now", return_value=values["customer_acknowledged_at"]):
            return resolve_instalment_outage(**values)

    def online(self, account):
        return initiate_razorpay_contribution(scheme_account=account, amount=Decimal("500"), gateway=self.gateway())

    def capture(self, c, *, at=NOW + timedelta(seconds=30)):
        payload = {"event": "payment.captured", "created_at": int(at.timestamp()) if at else None,
            "payload": {"payment": {"entity": {"id": f"pay_{c.pk}", "order_id": c.gateway_order_id,
                "created_at": int(c.created_at.timestamp()), "amount": 50000, "currency": "INR",
                "captured": True, "status": "captured"}}}}
        with patch("django.utils.timezone.now", return_value=NOW + timedelta(minutes=12)):
            return process_razorpay_webhook(gateway_mode="live", event_id=uuid.uuid4().hex,
                payload=payload, body=json.dumps(payload).encode())


@override_settings(IN_STORE_CASH_CONTRIBUTIONS_ENABLED=True, PAYMENT_INITIATION_KILL_SWITCH=False)
class IndependentReviewTests(IndependentReviewFixture, TestCase):
    def test_compensation_matrix_retains_independent_count_dates_and_finances(self):
        for metal in (False, True):
            for basis in ("CALENDAR_MONTH", "ANNIVERSARY"):
                for eligibility, duration in (("COUNT", None), ("CALENDAR_AND_COUNT", 18), ("CALENDAR", 12)):
                    values = dict(metal=metal, period_basis=basis, required_count=2,
                        eligibility_policy=eligibility, duration_months=duration)
                    if eligibility == "CALENDAR":
                        values.update(missed_payment_policy="LOSE_UNEARNED_BENEFIT", max_extension_months=None,
                            benefit_policy="VA_DISCOUNT", benefit_percentage=Decimal("5"), benefit_cap_inr=Decimal("500"),
                            benefit_qualification="REQUIRED_SCHEDULE", benefit_on_miss="DISQUALIFY_UNEARNED",
                            eligible_charge_definition="Making charges excluding taxes")
                    account = self.agreement(**values)
                    before = SchemeAccount.objects.filter(pk=account.pk).values().get()
                    original = list(account.instalment_periods.order_by("number").values())
                    hold = self.hold(account)
                    key = uuid.uuid4()
                    result = self.resolve(hold, idempotency_key=key)
                    self.assertEqual(self.resolve(hold, idempotency_key=key).pk, result.pk)
                    self.assertEqual(result.compensation_period.number, len(original) + 1)
                    self.assertEqual(SchemeAccount.objects.filter(pk=account.pk).values().get(), before)
                    self.assertEqual(list(account.instalment_periods.filter(number__lte=len(original)).order_by("number").values()), original)
                    self.assertEqual(len(validated_instalment_periods(account)), len(original) + 1)
                    self.assertEqual(len(prepare_instalment_periods(account_id=account.pk, actor=self.owner, reason="Read retry")), len(original) + 1)
                    self.assertEqual(instalment_payment_ledger_summary(account_id=account.pk)["integrity_errors"], 0)
        for model in (Contribution, InrPrincipalReceipt, MetalAllocation):
            self.assertFalse(model.objects.exists())
        call_command("check_instalment_schedules", stdout=StringIO())

    def test_cap_duplicates_future_boundary_and_stale_requests_remain_rejected(self):
        account = self.agreement(required_count=4)
        first = self.hold(account)
        for changes in (dict(expected_period_count=0), dict(expected_review_sequence=0),
                        dict(customer_acknowledged_at=NOW), dict(acknowledgement_reference=" "),
                        dict(actor=self.customer.user), dict(outcome="WAIVE")):
            with self.assertRaises(ValidationError):
                self.resolve(first, **changes)
        for number in (1, 2, 3):
            self.resolve(first if number == 1 else self.hold(account, number))
        with self.assertRaisesMessage(ValidationError, "at most three"):
            self.resolve(self.hold(account, 4))
        with self.assertRaisesMessage(ValidationError, "already received"):
            self.resolve(self.hold(account))
        self.assertEqual(account.instalment_periods.count(), 10)
        other = self.agreement(required_count=1)
        hold = self.hold(other)
        with self.assertRaisesMessage(ValidationError, "already begun"):
            self.resolve(hold, customer_acknowledged_at=instant(compensation_window(other, 1).starts_on, 0))

    def test_compensating_payment_uses_current_rate_or_separate_inr_receipt(self):
        for metal in (False, True):
            account = self.agreement(metal=metal, required_count=2)
            result = self.resolve(self.hold(account))
            with patch("django.utils.timezone.now", return_value=instant(result.compensation_period.starts_on)):
                values = {}
                if metal:
                    rate = publish_scheme_rate(metal_grade=account.metal_grade, rate_per_gram=Decimal("20000"), published_by=self.owner)
                    values["expected_scheme_rate_id"] = rate.pk
                c = self.cash(account, **values)
                self.assertEqual(c.instalment_reservation.period_id, result.compensation_period_id)
                self.assertEqual(c.instalment_reservation.state, "QUALIFIED")
                self.assertEqual(InrPrincipalReceipt.objects.filter(contribution=c).exists(), not metal)
                if metal:
                    self.assertEqual(c.scheme_rate.rate_per_gram, Decimal("20000"))
                    self.assertEqual(c.metal_allocation.quantity, Decimal("0.025000"))

    def test_inr_reconciles_principal_not_metal_and_corrupt_source_stays_held(self):
        account = self.agreement(required_count=2)
        c = self.cash(account)
        hold = self.hold(account)
        InrPrincipalReceipt.objects.filter(contribution=c).update(amount=Decimal("501"))
        with self.assertRaisesMessage(ValidationError, "Reconcile"):
            self.resolve(hold, outcome="QUALIFIED")
        InrPrincipalReceipt.objects.filter(contribution=c).update(amount=Decimal("500"))
        before = list(InrPrincipalReceipt.objects.values())
        result = self.resolve(hold, outcome="QUALIFIED")
        self.assertEqual(result.qualification_decision.reservation.contribution_id, c.pk)
        self.assertFalse(MetalAllocation.objects.exists())
        self.assertEqual(list(InrPrincipalReceipt.objects.values()), before)

    def test_benefit_compensation_cannot_override_closed_contribution_duration(self):
        account = self.agreement(required_count=12, period_basis="ANNIVERSARY", eligibility_policy="CALENDAR",
            duration_months=12, missed_payment_policy="LOSE_UNEARNED_BENEFIT", max_extension_months=None,
            benefit_policy="VA_DISCOUNT", benefit_percentage=Decimal("5"), benefit_cap_inr=Decimal("500"),
            benefit_qualification="REQUIRED_SCHEDULE", benefit_on_miss="DISQUALIFY_UNEARNED",
            eligible_charge_definition="Making charges excluding taxes")
        hold = self.hold(account)
        with self.assertRaisesMessage(ValidationError, "outside the agreed contribution duration"):
            self.resolve(hold)
        self.assertEqual(account.instalment_periods.count(), 12)
        self.assertFalse(InstalmentOutageResolution.objects.exists())
        self.assertEqual(instalment_payment_ledger_summary(account_id=account.pk)["outage_held_accounts"], 1)
        self.client.force_login(self.owner)
        response = self.client.get(reverse("schemes:instalment_outage_resolution", args=[hold.pk]))
        self.assertContains(response, "0 ordinary replacement months")
        self.assertContains(response, "does not extend the original principal maturity")
        self.assertContains(response, "No further compensating month is available")

    def test_pending_missing_timing_conflicting_capture_and_webhook_failures_stay_held(self):
        account = self.agreement()
        c = self.online(account)
        hold = self.hold(account)
        with self.assertRaisesMessage(ValidationError, "Reconcile"):
            self.resolve(hold)
        self.capture(c, at=None)
        with self.assertRaisesMessage(ValidationError, "Reconcile"):
            self.resolve(hold)
        self.capture(c, at=NOW + timedelta(minutes=11))
        claim = c.instalment_reservation
        source = claim.decisions.order_by("-sequence").first()
        with self.assertRaisesMessage(ValidationError, "Conflicting"):
            self.review(claim.period, action="ACCEPT_TIMING", reservation_id=claim.pk,
                source_decision_id=source.pk, expected_payment_sequence=source.sequence)
        self.assertFalse(InstalmentOutageResolution.objects.exists())

    def test_completed_count_cannot_receive_compensation_for_a_different_unpaid_period(self):
        account = self.agreement(required_count=1, eligibility_policy="CALENDAR_AND_COUNT", duration_months=18)
        self.cash(account)
        hold = self.hold(account, number=2)
        with self.assertRaisesMessage(ValidationError, "incomplete payment count"):
            self.resolve(hold)
        self.assertEqual(account.instalment_periods.count(), 4)

    def test_timing_acceptance_uses_signed_evidence_and_never_recredits_principal(self):
        for metal in (False, True):
            account = self.agreement(metal=metal)
            c = self.online(account)
            self.capture(c, at=None)
            self.capture(c)
            claim = c.instalment_reservation
            source = claim.decisions.order_by("-sequence").first()
            before = [list(model.objects.values()) for model in (Contribution, InrPrincipalReceipt, MetalAllocation)]
            key = uuid.uuid4()
            values = dict(action="ACCEPT_TIMING", reservation_id=claim.pk, source_decision_id=source.pk,
                expected_payment_sequence=source.sequence, idempotency_key=key)
            review = self.review(claim.period, **values)
            self.assertEqual(self.review(claim.period, **values).pk, review.pk)
            claim.refresh_from_db()
            self.assertEqual(claim.state, "QUALIFIED")
            self.assertEqual([list(model.objects.values()) for model in (Contribution, InrPrincipalReceipt, MetalAllocation)], before)
            self.assertEqual(instalment_payment_ledger_summary(account_id=account.pk)["integrity_errors"], 0)
            hold = self.hold(account)
            event = PaymentWebhookEvent.objects.filter(contribution=c).first()
            PaymentWebhookEvent.objects.filter(pk=event.pk).update(status="FAILED")
            with self.assertRaisesMessage(ValidationError, "Reconcile"):
                self.resolve(hold, outcome="QUALIFIED")

    def test_resolution_insertion_failure_rolls_back_extra_period_and_hold(self):
        account = self.agreement()
        hold = self.hold(account)
        before = list(account.instalment_periods.values())
        with patch.object(InstalmentOutageResolution, "save", side_effect=ValidationError("Injected failure")):
            with self.assertRaises(ValidationError):
                self.resolve(hold)
        self.assertEqual(list(account.instalment_periods.values()), before)
        self.assertFalse(InstalmentOutageResolution.objects.exists())
        self.assertEqual(instalment_payment_ledger_summary(account_id=account.pk)["outage_held_accounts"], 1)

    def test_enabled_release_flag_does_not_enable_independent_review_writes(self):
        account = self.agreement()
        hold = self.hold(account)
        for enabled in (False, True):
            with override_settings(CONFIGURED_PLANS_ENABLED=enabled), self.assertRaisesMessage(ValidationError, "preparation-only"):
                record_instalment_review(period_id=hold.period_id, actor=self.owner, action="NOTE", reason="Review",
                    evidence_reference="TEST", idempotency_key=uuid.uuid4(), expected_review_sequence=1)
            with override_settings(CONFIGURED_PLANS_ENABLED=enabled), self.assertRaisesMessage(ValidationError, "preparation-only"):
                resolve_instalment_outage(**self.resolution_values(hold))
        self.assertEqual(InstalmentReview.objects.count(), 1)
        self.assertFalse(InstalmentOutageResolution.objects.exists())

    def test_current_window_restoration_and_other_holds_preserve_payment_block(self):
        account = self.agreement()
        hold = self.hold(account)
        with patch("django.utils.timezone.now", return_value=NOW), self.assertRaises(ValidationError):
            current_instalment_period(account)
        result = self.resolve(hold, outcome="RESTORED", service_restored_at=NOW-timedelta(minutes=1),
            customer_acknowledged_at=NOW)
        self.assertIsNone(result.compensation_period_id)
        self.assertEqual(current_instalment_period(account).number, 1)
        self.hold(account)
        with self.assertRaises(ValidationError):
            self.cash(account)

    def test_owner_ui_shows_count_not_duration_and_preserves_auth_csrf(self):
        account = self.agreement(required_count=2, eligibility_policy="CALENDAR_AND_COUNT", duration_months=18)
        hold = self.hold(account)
        url = reverse("schemes:instalment_outage_resolution", args=[hold.pk])
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.customer.user)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_login(self.owner)
        response = self.client.get(url)
        self.assertContains(response, "original 2 required payments")
        self.assertNotContains(response, "18 required payments")
        self.assertIn("no-store", response.headers["Cache-Control"])
        secure = Client(enforce_csrf_checks=True)
        secure.force_login(self.owner)
        self.assertEqual(secure.post(url, {}).status_code, 403)
        values = self.resolution_values(hold)
        values.pop("actor")
        values.pop("hold_id")
        values["evidence_confirmed"] = True
        at = values["customer_acknowledged_at"]
        for field in ("incident_started_at", "service_restored_at", "customer_acknowledged_at"):
            values[field] = values[field].isoformat()
        with future_readiness_only(), patch("django.utils.timezone.now", return_value=at):
            self.assertEqual(self.client.post(url, values).status_code, 302)
            self.assertEqual(self.client.post(url, values).status_code, 302)
        self.assertEqual(InstalmentOutageResolution.objects.count(), 1)


@override_settings(IN_STORE_CASH_CONTRIBUTIONS_ENABLED=True, PAYMENT_INITIATION_KILL_SWITCH=False)
class IndependentReviewConcurrencyTests(IndependentReviewFixture, TransactionTestCase):
    def test_concurrent_resolution_records_one_amendment_and_period(self):
        account = self.agreement(required_count=2)
        hold = self.hold(account)
        values = self.resolution_values(hold)
        barrier = Barrier(2)
        def resolve():
            connections.close_all()
            try:
                barrier.wait(timeout=20)
                return resolve_instalment_outage(**values).pk
            finally:
                connections.close_all()
        with future_readiness_only(), patch("django.utils.timezone.now", return_value=values["customer_acknowledged_at"]), ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: resolve(), range(2)))
        self.assertEqual(results[0], results[1])
        self.assertEqual(account.instalment_periods.count(), 6)
        self.assertEqual(InstalmentOutageResolution.objects.count(), 1)

    def test_outage_resolution_serializes_with_inr_cash_receipt(self):
        account = self.agreement(required_count=2)
        hold = self.hold(account)
        values = self.resolution_values(hold)
        barrier = Barrier(2)
        def action(kind):
            connections.close_all()
            try:
                barrier.wait(timeout=20)
                if kind == "resolve":
                    return resolve_instalment_outage(**values).pk
                try:
                    return self.cash(account).pk
                except ValidationError as error:
                    if "outage" not in str(error).lower():
                        raise
                    return None
            finally:
                connections.close_all()
        with future_readiness_only(), patch("django.utils.timezone.now", return_value=values["customer_acknowledged_at"]), ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(action, ("resolve", "cash")))
        self.assertIsNotNone(results[0])
        self.assertEqual(account.instalment_periods.count(), 6)
        self.assertEqual(InrPrincipalReceipt.objects.count(), int(results[1] is not None))
        if results[1] is not None:
            self.assertEqual(Contribution.objects.get(pk=results[1]).instalment_reservation.period.number, 2)
        summary = instalment_payment_ledger_summary(account_id=account.pk)
        self.assertEqual(summary["integrity_errors"], 0)
        self.assertEqual(summary["outage_held_accounts"], 0)
