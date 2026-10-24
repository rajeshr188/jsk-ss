"""B4 local HTTP/statement and late-provider acceptance, never real fulfilment."""
import uuid
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from io import StringIO
from threading import Barrier
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import close_old_connections, connection
from django.db.migrations.executor import MigrationExecutor
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse

from schemes.closure_selectors import validate_closure_history
from schemes.models import Contribution, MetalAllocation, Redemption, SchemeAccount, SchemeClosureRequest
from schemes.selectors import get_customer_plan_next_action, get_metal_balance, get_scheme_statement
from schemes.settlements import reverse_configured_settlement, settle_configured_agreement
from schemes.tests.test_configured_settlements import SettlementFixture
from schemes.tests.test_instalment_capture_boundaries import CaptureFixture
from schemes.tests.test_instalment_form_accessibility import FormMarkup
from schemes.tests.test_instalment_payments import NOW
from schemes.tests.test_audit_exceptions import make_customer
from schemes.tests.test_instalment_schedules import synthetic_account


@override_settings(IN_STORE_CASH_CONTRIBUTIONS_ENABLED=True, PAYMENT_GATEWAY="razorpay",
    RAZORPAY_MODE="live", RAZORPAY_KEY_ID="rzp_live_fixture", RAZORPAY_KEY_SECRET="fixture")
class ClosureAcceptanceTests(SettlementFixture, TestCase):
    capture = CaptureFixture.capture

    def setUp(self):
        super().setUp()
        self.client = Client(enforce_csrf_checks=True)

    def closure_url(self):
        return reverse("schemes:closure_workspace", args=[self.account.scheme_number])

    def post(self, url, data):
        self.client.get(url)
        return self.client.post(url, data, HTTP_X_CSRFTOKEN=self.client.cookies["csrftoken"].value)

    def accept_through_forms(self):
        self.client.force_login(self.account.customer.user)
        response = self.post(self.closure_url(), dict(reason="Please close my agreement", idempotency_key=uuid.uuid4()))
        self.assertEqual(response.status_code, 302)
        request = SchemeClosureRequest.objects.get(scheme_account=self.account)
        self.assertEqual(request.status, "PENDING")
        self.client.force_login(self.owner)
        response = self.post(self.closure_url(), dict(request_id=request.pk, action="ACCEPT",
            expected_sequence=1, idempotency_key=uuid.uuid4(), reason="Customer request reviewed"))
        self.assertEqual(response.status_code, 302)
        request.refresh_from_db()
        self.assertEqual(request.status, "ACCEPTED")
        return request

    def settlement_post(self, request):
        url = reverse("schemes:configured_settlement", args=[request.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = dict(preview_token=response.context["form"]["preview_token"].value(),
            idempotency_key=uuid.uuid4(), invoice_reference="JEWELLERY-ACCEPTANCE-001",
            authorization_reference="Customer signed full quantity and delivery", reason="Actual full jewellery fulfilment", confirmed=True)
        self.assertEqual(self.post(url, data).status_code, 302)
        return url, data, Redemption.objects.get(scheme_account=self.account)

    def test_unused_customer_to_owner_cancellation_journey(self):
        other = synthetic_account(self.account.customer, self.grade, self.account.plan)
        before = SchemeAccount.objects.values().get(pk=other.pk)
        request = self.accept_through_forms()
        response = self.post(self.closure_url(), dict(operation="cancel_unused", request_id=request.pk,
            expected_sequence=2, idempotency_key=uuid.uuid4(), reason="Unused agreement no longer required",
            confirm_unused_cancellation=True))
        self.assertEqual(response.status_code, 302)
        self.account.refresh_from_db()
        self.assertEqual(self.account.status, "CANCELLED")
        for model in (Contribution, MetalAllocation, Redemption):
            self.assertFalse(model.objects.exists())
        self.assertEqual(before, SchemeAccount.objects.values().get(pk=other.pk))
        self.client.force_login(self.account.customer.user)
        response = self.client.get(reverse("schemes:scheme_statement", args=[self.account.scheme_number]))
        self.assertContains(response, "Cancelled unused agreement")
        self.assertNotContains(response, "qualifying payments may continue")
        self.assertTrue(self.account.customer.user.is_active)
        self.assertEqual(get_customer_plan_next_action(self.account)["stage"], "Unused agreement cancelled")

    def test_three_of_twelve_instalments_full_early_settlement_and_statement(self):
        self.pay_periods([1, 2, 3])
        sources = (list(Contribution.objects.values()), list(MetalAllocation.objects.values()))
        with patch("django.utils.timezone.now", return_value=self.instant(3)):
            request = self.accept_through_forms()
            self.assertEqual(get_customer_plan_next_action(self.account)["stage"], "Closure accepted — settlement pending")
            url, data, redemption = self.settlement_post(request)
        self.assertEqual(redemption.configured_settlement.basis, "EARLY")
        self.assertEqual(redemption.gold_quantity, Decimal("0.300000"))
        self.account.refresh_from_db()
        self.assertEqual(self.account.status, "REDEEMED")
        self.assertEqual(get_metal_balance(self.account), 0)
        self.assertEqual(sources, (list(Contribution.objects.values()), list(MetalAllocation.objects.values())))
        self.client.force_login(self.account.customer.user)
        response = self.client.get(reverse("schemes:scheme_statement", args=[self.account.scheme_number]))
        for text in ("Full jewellery settlement completed", "JEWELLERY-ACCEPTANCE-001", "Customer-authorized early closure", "0.300000"):
            self.assertContains(response, text)
        self.assertNotContains(response, "qualifying payments may continue")
        self.assertEqual(get_customer_plan_next_action(self.account)["stage"], "Full settlement recorded")
        history = self.client.get(self.closure_url())
        self.assertContains(history, "JEWELLERY-ACCEPTANCE-001")
        self.assertNotContains(history, "Customer signed full quantity and delivery")  # owner-only evidence reference
        self.assertTrue(self.account.customer.user.is_active)

    def test_reversal_form_statement_and_replayed_old_submission(self):
        self.cash()
        request = self.accept_through_forms()
        url, data, redemption = self.settlement_post(request)
        response = self.post(url, dict(operation="reverse", **{
            k: v for k, v in self.reversal_values(redemption.configured_settlement).items() if k != "actor"
        }, confirmed=True))
        self.assertEqual(response.status_code, 302)
        self.account.refresh_from_db()
        self.assertEqual(self.account.status, "CLOSURE_PENDING")
        statement = get_scheme_statement(self.account)
        self.assertEqual(statement.remaining_entitlement, Decimal("0.100000"))
        self.assertEqual(len([e for e in statement.entries if e.restoration is not None]), 1)
        response = self.post(url, data)
        self.assertEqual(response.status_code, 302)
        self.assertContains(self.client.get(url), "already recorded and subsequently reversed")
        self.assertEqual(Redemption.objects.count(), 1)
        self.client.force_login(self.account.customer.user)
        response = self.client.get(reverse("schemes:scheme_statement", args=[self.account.scheme_number]))
        for text in ("Settlement was reversed", "JEWELLERY-ACCEPTANCE-001", "0.100000", "restored"):
            self.assertContains(response, text)
        self.assertNotContains(response, "qualifying payments may continue")
        self.assertFalse(get_customer_plan_next_action(self.account)["can_pay"])

    def test_different_customer_cannot_read_or_act_on_closure_or_statement(self):
        self.cash()
        request = self.accepted()
        stranger = make_customer("closure-outsider@example.com")
        self.client.force_login(stranger.user)
        self.assertEqual(self.client.get(self.closure_url()).status_code, 404)
        self.assertEqual(self.client.get(reverse("schemes:scheme_statement", args=[self.account.scheme_number])).status_code, 404)
        self.assertEqual(self.client.get(reverse("schemes:configured_settlement", args=[request.pk])).status_code, 403)
        self.assertFalse(Redemption.objects.exists())

    def test_late_duplicate_capture_after_settlement_is_retained_and_flagged(self):
        payment = self.online()
        self.webhook(payment)
        request = self.accepted()
        redemption = self.settle(request)
        sources = (list(Contribution.objects.values()), list(MetalAllocation.objects.values()), list(Redemption.objects.values()))
        with patch("django.utils.timezone.now", return_value=NOW + timedelta(minutes=2)):
            event = self.capture(payment, payment_id="pay_unexpected_second", event_id="post_settlement_capture")
        self.assertEqual(event.status, "REVIEW_REQUIRED")
        self.assertEqual(sources, (list(Contribution.objects.values()), list(MetalAllocation.objects.values()), list(Redemption.objects.values())))
        self.assertEqual(get_metal_balance(self.account), 0)
        with self.assertRaises(CommandError):
            call_command("check_scheme_closures", stdout=StringIO())
        reverse_configured_settlement(**self.reversal_values(redemption.configured_settlement))
        with self.assertRaises(ValidationError):
            self.values(request)

    def test_same_capture_redelivery_after_settlement_does_not_duplicate_liability(self):
        payment = self.online()
        self.webhook(payment)
        self.settle(self.accepted())
        self.webhook(payment, event_id="same_payment_new_event")
        self.assertEqual(MetalAllocation.objects.count(), 1)
        self.assertEqual(Redemption.objects.count(), 1)
        self.assertEqual(get_metal_balance(self.account), 0)
        call_command("check_scheme_closures", stdout=StringIO())

    def test_owner_forms_have_unique_ids_labels_and_escaped_references(self):
        self.cash()
        request = self.accepted()
        self.client.force_login(self.owner)
        for url in (self.closure_url(), reverse("schemes:configured_settlement", args=[request.pk])):
            response = self.client.get(url)
            markup = FormMarkup(response.content.decode())
            self.assertFalse([key for key, count in Counter(markup.ids).items() if count > 1])
            for target in markup.labels:
                self.assertIn(target, markup.controls)
            self.assertIn("no-store", response.headers["Cache-Control"])
        self.settle(request, invoice_reference='<script>alert("invoice")</script>')
        response = self.client.get(reverse("schemes:scheme_statement", args=[self.account.scheme_number]))
        self.assertContains(response, "&lt;script&gt;")
        self.assertNotContains(response, '<script>alert("invoice")</script>')


@override_settings(IN_STORE_CASH_CONTRIBUTIONS_ENABLED=True)
class ClosureAcceptanceRaceTests(SettlementFixture, TransactionTestCase):
    def setUp(self):
        MigrationExecutor(connection).migrate(MigrationExecutor(connection).loader.graph.leaf_nodes())
        super().setUp()

    def run_race(self, action):
        barrier = Barrier(2)
        def run(_):
            close_old_connections()
            try:
                barrier.wait(timeout=30)
                return action()
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            return list(pool.map(run, range(2)))

    def test_identical_retries_create_only_one_full_settlement(self):
        self.cash()
        request = self.accepted()
        values = self.values(request)
        ids = self.run_race(lambda: settle_configured_agreement(**values).pk)
        self.assertEqual(ids[0], ids[1])
        self.assertEqual(Redemption.objects.count(), 1)
        self.assertEqual(get_metal_balance(self.account), 0)

    def test_identical_reversal_retries_restore_only_once_and_keep_payments_blocked(self):
        self.cash()
        request = self.accepted()
        redemption = self.settle(request)
        values = self.reversal_values(redemption.configured_settlement)
        ids = self.run_race(lambda: reverse_configured_settlement(**values).pk)
        self.assertEqual(ids[0], ids[1])
        self.assertEqual(get_metal_balance(self.account), Decimal("0.100000"))
        self.account.refresh_from_db()
        self.assertEqual(self.account.status, "CLOSURE_PENDING")
        request.refresh_from_db()
        self.assertEqual(validate_closure_history(request), 4)
        with self.assertRaises(ValidationError):
            self.cash()
