"""Exact authenticated identity is recoverable; absence never authorizes a retry."""
import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta
from threading import Barrier
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import IntegrityError, close_old_connections, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse

from schemes.instalment_order_recovery import recover_instalment_order
from schemes.instalment_selectors import durable_order_request, instalment_payment_ledger_summary, owner_instalment_review_periods
from schemes.models import Contribution, InstalmentOrderRecovery, InstalmentPaymentDecision, MetalAllocation
from schemes.payments import PaymentGatewayError, PaymentInspection, PaymentOrderIdentity, PaymentOrderInspection, RazorpayPaymentGateway
from schemes.services import reconcile_abandoned_razorpay_contribution, reconcile_razorpay_webhook
from schemes.tests import test_instalment_reviews as reviews
from schemes.tests import test_razorpay as razorpay_tests
from schemes.tests.test_instalment_payments import NOW


class RecoveryFixture(reviews.ReviewFixture):
    def lost(self):
        self.gateway.create_order.side_effect = PaymentGatewayError("Provider response lost")
        with self.assertRaises(PaymentGatewayError):
            self.online()
        contribution = Contribution.objects.get()
        intent = durable_order_request(contribution)
        self.identity = PaymentOrderIdentity(order_id="order_recovered", receipt=f"inst_{intent.request_token.hex}",
            contribution_id=str(contribution.pk), request_token=str(intent.request_token), amount_subunits=100000,
            currency="INR", status="created", created_at=int(NOW.timestamp()))
        self.gateway.inspect_order_identity.return_value = self.identity
        return contribution, intent

    def values(self, contribution, **changes):
        values = dict(contribution_id=contribution.pk, order_id="order_recovered", actor=self.owner,
            reason="Investigated interrupted provider response", evidence_reference="RZP-SUPPORT-1",
            idempotency_key=uuid.uuid4(), expected_payment_sequence=contribution.instalment_reservation.decisions.order_by("-sequence").first().sequence,
            gateway=self.gateway)
        values.update(changes)
        return values

    def recover(self, contribution, **changes):
        return recover_instalment_order(**self.values(contribution, **changes))


@override_settings(IN_STORE_CASH_CONTRIBUTIONS_ENABLED=True)
class InstalmentOrderRecoveryTests(RecoveryFixture, TestCase):
    def test_binding_preserves_terms_money_rate_deadline_and_is_idempotent(self):
        c, intent = self.lost()
        before = Contribution.objects.filter(pk=c.pk).values().get()
        result = self.recover(c)
        after = Contribution.objects.filter(pk=c.pk).values().get()
        self.assertEqual({k:v for k,v in before.items() if k not in ("status", "gateway_order_id")},
            {k:v for k,v in after.items() if k not in ("status", "gateway_order_id")})
        self.assertEqual(after["status"], "PENDING")
        self.assertEqual(after["gateway_order_id"], "order_recovered")
        self.assertEqual(result.request_decision_id, intent.pk)
        self.assertEqual(result.decision.state, "RESERVED")
        self.assertFalse(MetalAllocation.objects.exists())
        again = self.recover(c, idempotency_key=result.idempotency_key, expected_payment_sequence=intent.sequence)
        self.assertEqual(result.pk, again.pk)
        self.assertEqual(self.gateway.inspect_order_identity.call_count, 1)
        self.assertEqual(self.gateway.create_order.call_count, 1)
        for initiate in (self.online, self.cash):
            with self.assertRaises(ValidationError):
                initiate()
        self.assertEqual(instalment_payment_ledger_summary()["integrity_errors"], 0)
        self.assertEqual(instalment_payment_ledger_summary()["recovered_orders"], 1)
        for mutate in (result.save, result.delete):
            with self.assertRaises(ValidationError):
                mutate()
        with self.assertRaises(ValidationError):
            self.recover(c, idempotency_key=result.idempotency_key, reason="Different")

    def test_paid_provider_order_is_only_linked_then_signed_capture_verifies_funds(self):
        c, _ = self.lost()
        self.gateway.inspect_order_identity.return_value = replace(self.identity, status="paid")
        self.recover(c)
        c.refresh_from_db()
        self.assertEqual(c.status, "PENDING")
        self.assertFalse(MetalAllocation.objects.exists())
        event = self.webhook(c)
        c.refresh_from_db()
        self.assertEqual((event.status, c.status, c.instalment_reservation.state), ("PROCESSED", "PAID", "QUALIFIED"))
        self.webhook(c)
        self.assertEqual(MetalAllocation.objects.count(), 1)
        self.assertEqual(instalment_payment_ledger_summary()["qualified_payments"], 1)

    def test_recovered_expired_untouched_order_uses_existing_release_and_late_capture_review(self):
        c, _ = self.lost()
        with patch("django.utils.timezone.now", return_value=NOW + timedelta(minutes=11)):
            self.recover(c)
            c.refresh_from_db()
            self.gateway.inspect_order.return_value = PaymentOrderInspection(c.gateway_order_id,
                "created", 100000, 0, 100000, "INR", 0, 0, ())
            result = reconcile_abandoned_razorpay_contribution(contribution_id=c.pk, cutoff=NOW,
                gateway=self.gateway, apply=True)
        self.assertTrue(result.applied)
        c.instalment_reservation.refresh_from_db()
        self.assertEqual(c.instalment_reservation.state, "RELEASED")
        event = self.webhook(c, captured_at=NOW + timedelta(minutes=12), delivered_at=NOW + timedelta(minutes=13))
        self.assertEqual(event.status, "REVIEW_REQUIRED")
        self.assertFalse(MetalAllocation.objects.exists())
        self.assertEqual(instalment_payment_ledger_summary()["review_required"], 1)

    def test_mismatched_identity_or_old_future_time_never_binds(self):
        c, _ = self.lost()
        for changes in ({"order_id":"order_other"}, {"receipt":"contribution_1"},
            {"request_token":str(uuid.uuid4())}, {"contribution_id":"999"}, {"amount_subunits":100001},
            {"currency":"USD"}, {"status":"refunded"}, {"created_at":int(NOW.timestamp())-1},
            {"created_at":int(NOW.timestamp())+1}, {"created_at":True}, {"created_at":10**30}):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                self.gateway.inspect_order_identity.return_value = replace(self.identity, **changes)
                self.recover(c)
        c.refresh_from_db()
        self.assertEqual(c.status, "FAILED")
        self.assertFalse(c.gateway_order_id)
        self.assertFalse(InstalmentOrderRecovery.objects.exists())

    def test_no_match_timeout_and_old_uncorrelated_intent_stay_held(self):
        c, intent = self.lost()
        self.gateway.inspect_order_identity.side_effect = PaymentGatewayError("Order not found or request failed")
        with self.assertRaises(PaymentGatewayError):
            self.recover(c)
        self.gateway.inspect_order_identity.side_effect = None
        InstalmentPaymentDecision.objects.filter(pk=intent.pk).update(request_token=None)
        with self.assertRaisesMessage(ValidationError, "No durable unique"):
            self.recover(c)
        self.assertEqual(self.gateway.inspect_order_identity.call_count, 1)
        self.assertEqual(instalment_payment_ledger_summary()["uncorrelated_order_requests"], 1)
        self.assertFalse(InstalmentOrderRecovery.objects.exists())

    def test_wrong_role_mode_stale_sequence_and_conflicting_key_rejected(self):
        c, _ = self.lost()
        with self.assertRaises(ValidationError):
            self.recover(c, actor=self.account.customer.user)
        self.gateway.mode = "test"
        with self.assertRaises(ValidationError):
            self.recover(c)
        self.gateway.mode = "live"
        with self.assertRaises(ValidationError):
            self.recover(c, expected_payment_sequence=0)
        result = self.recover(c)
        with self.assertRaises(ValidationError):
            self.recover(c, order_id="order_another", idempotency_key=result.idempotency_key)

    def test_investigation_hold_does_not_prevent_identity_or_capture_reconciliation(self):
        c, _ = self.lost()
        self.submit(action="OUTAGE_HOLD")
        self.recover(c)
        c.refresh_from_db()
        self.assertEqual(self.webhook(c).status, "PROCESSED")
        self.assertEqual(instalment_payment_ledger_summary()["outage_held_accounts"], 1)

    def test_unknown_capture_remains_review_until_separate_provider_reconciliation(self):
        c, _ = self.lost()
        c.gateway_order_id = "order_recovered"  # Provider knows it, database does not yet.
        event = self.webhook(c, event_id="capture_before_binding")
        self.assertEqual(event.status, "REVIEW_REQUIRED")
        self.recover(c)
        c.refresh_from_db()
        self.assertEqual(self.webhook(c, event_id="capture_before_binding").status, "REVIEW_REQUIRED")
        self.assertEqual(instalment_payment_ledger_summary()["unresolved_capture_events"], 1)
        self.assertTrue(owner_instalment_review_periods().get(pk=c.instalment_reservation.period_id).has_capture_review)
        with self.assertRaisesMessage(ValidationError, "captured-payment exception"):
            self.online()
        self.assertFalse(MetalAllocation.objects.exists())
        self.gateway.inspect_payment.return_value = PaymentInspection(
            f"pay_{c.pk}", c.gateway_order_id, 100000, "INR", "captured", True)
        for apply in (False, True):
            result = reconcile_razorpay_webhook(webhook_event_id=event.pk, apply=apply,
                gateway=self.gateway, performed_by=self.owner, reason="Reconcile previously unidentified capture")
        self.assertTrue(result.applied)
        c.refresh_from_db()
        self.assertEqual((c.status, c.instalment_reservation.state), ("PAID", "AWAITING"))
        self.webhook(c, event_id="capture_before_binding")
        c.instalment_reservation.refresh_from_db()
        self.assertEqual(c.instalment_reservation.state, "QUALIFIED")
        self.assertEqual(MetalAllocation.objects.count(), 1)

    def test_local_write_failure_after_provider_response_retains_recoverable_identity(self):
        with patch("schemes.services.complete_instalment_order_request", side_effect=RuntimeError("Local write failure")):
            with self.assertRaises(RuntimeError):
                self.online()
        c = Contribution.objects.get()
        intent = durable_order_request(c)
        self.gateway.inspect_order_identity.return_value = PaymentOrderIdentity(
            "order_recovered", f"inst_{intent.request_token.hex}", str(c.pk), str(intent.request_token),
            100000, "INR", "created", int(NOW.timestamp()))
        self.recover(c)
        c.refresh_from_db()
        self.assertEqual((c.status, c.gateway_order_id), ("PENDING", "order_recovered"))
        self.assertEqual(self.gateway.create_order.call_count, 1)

    def test_state_is_rechecked_after_provider_read(self):
        c, _ = self.lost()
        def changed_state(**kwargs):
            Contribution.objects.filter(pk=c.pk).update(gateway_order_id="order_bound_elsewhere")
            return self.identity
        self.gateway.inspect_order_identity.side_effect = changed_state
        with self.assertRaisesMessage(ValidationError, "Payment evidence changed"):
            self.recover(c)
        self.assertFalse(InstalmentOrderRecovery.objects.exists())
        self.assertFalse(MetalAllocation.objects.exists())

    def test_database_and_integrity_checks_preserve_recovery_evidence(self):
        c, intent = self.lost()
        result = self.recover(c)
        with self.assertRaises(IntegrityError), transaction.atomic():
            InstalmentPaymentDecision.objects.filter(pk=result.decision_id).update(request_token=uuid.uuid4())
        with self.assertRaises(IntegrityError), transaction.atomic():
            InstalmentOrderRecovery.objects.filter(pk=result.pk).update(currency="USD")
        InstalmentOrderRecovery.objects.filter(pk=result.pk).update(receipt="wrong")
        self.assertGreater(instalment_payment_ledger_summary()["integrity_errors"], 0)

    @override_settings(PAYMENT_GATEWAY="razorpay", RAZORPAY_MODE="live", RAZORPAY_KEY_ID="rzp_live_fixture", RAZORPAY_KEY_SECRET="fixture", RAZORPAY_WEBHOOK_SECRET="fixture")
    def test_owner_ui_private_csrf_and_customer_checkout_cannot_resume(self):
        c, intent = self.lost()
        claim = c.instalment_reservation
        url = reverse("schemes:instalment_order_recovery", args=[claim.pk])
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.account.customer.user)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_login(self.owner)
        response = self.client.get(url)
        self.assertContains(response, f"inst_{intent.request_token.hex}")
        self.assertIn("no-store", response.headers["Cache-Control"])
        secure = Client(enforce_csrf_checks=True)
        secure.force_login(self.owner)
        self.assertEqual(secure.post(url, {}).status_code, 403)
        values = self.values(c)
        for name in ("gateway", "actor", "contribution_id"):
            values.pop(name)
        with patch("schemes.instalment_order_recovery.get_payment_gateway", return_value=self.gateway):
            self.assertEqual(self.client.post(url, values).status_code, 302)
            self.assertEqual(self.client.post(url, values).status_code, 302)
        self.client.force_login(self.account.customer.user)
        checkout = reverse("schemes:razorpay_checkout", args=[c.pk])
        response = self.client.get(checkout)
        self.assertEqual(response.status_code, 302)
        self.assertNotContains(response, "checkout.razorpay.com", status_code=302)
        history = self.client.get(reverse("schemes:my_scheme_detail", args=[self.account.scheme_number]))
        self.assertContains(history, "Payment under reconciliation")
        self.assertNotContains(history, "Resume payment")
        self.assertNotContains(history, f'href="{checkout}"')


class OrderIdentityAdapterTests(RecoveryFixture, TestCase):
    def provider(self):
        return RazorpayPaymentGateway(mode="live", key_id="rzp_live_fixture", key_secret="fixture", webhook_secret="fixture")

    def payload(self):
        return dict(id="order_recovered", entity="order", receipt="inst_" + "a"*32,
            amount=100000, currency="INR", status="created", created_at=int(NOW.timestamp()),
            notes={"contribution_id":"42", "instalment_request":str(uuid.uuid4())})

    def test_unique_reference_sent_to_fixed_provider_endpoint(self):
        c, intent = self.lost()
        response = razorpay_tests.FakeResponse({"id":"order_new", "amount":100000, "currency":"INR"})
        with patch("schemes.payments.urlopen", return_value=response) as request:
            self.provider().create_order(c)
        payload = json.loads(request.call_args.args[0].data)
        self.assertEqual(payload["receipt"], f"inst_{intent.request_token.hex}")
        self.assertEqual(payload["notes"]["instalment_request"], str(intent.request_token))
        self.assertLessEqual(len(payload["receipt"]), 40)

    def test_lookup_uses_authenticated_get_and_validates_safe_identity(self):
        with patch("schemes.payments.urlopen", return_value=razorpay_tests.FakeResponse(self.payload())) as request:
            result = self.provider().inspect_order_identity(order_id="order_recovered")
        sent = request.call_args.args[0]
        self.assertEqual(sent.full_url, "https://api.razorpay.com/v1/orders/order_recovered")
        self.assertEqual(sent.get_method(), "GET")
        self.assertTrue(sent.get_header("Authorization").startswith("Basic "))
        self.assertEqual(result.amount_subunits, 100000)
        for changes in ({"id":"order_wrong"}, {"amount":True}, {"entity":"payment"},
            {"notes":[]}, {"notes":{}}, {"created_at":"123"}, {"currency":"USD"}, {"status":[]}):
            with self.subTest(changes=changes), patch("schemes.payments.urlopen", return_value=razorpay_tests.FakeResponse(self.payload() | changes)):
                with self.assertRaises(PaymentGatewayError):
                    self.provider().inspect_order_identity(order_id="order_recovered")

    def test_arbitrary_url_or_path_is_rejected_before_network(self):
        with patch("schemes.payments.urlopen") as request:
            for order_id in ("https://other.invalid", "order_x/../payments", "order_x?expand=anything", "order_"+"x"*120):
                with self.assertRaises(PaymentGatewayError):
                    self.provider().inspect_order_identity(order_id=order_id)
            request.assert_not_called()


class OrderRecoveryRaceTests(RecoveryFixture, TransactionTestCase):
    def setUp(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().setUp()

    def test_concurrent_same_recovery_records_one_binding(self):
        c, _ = self.lost()
        values = self.values(c)
        barrier = Barrier(2)
        def run():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return recover_instalment_order(**values).pk
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = [pool.submit(run) for _ in range(2)]
            ids = [future.result(timeout=40) for future in results]
        self.assertEqual(ids[0], ids[1])
        self.assertEqual(InstalmentOrderRecovery.objects.count(), 1)
        self.assertEqual(self.gateway.create_order.call_count, 1)
