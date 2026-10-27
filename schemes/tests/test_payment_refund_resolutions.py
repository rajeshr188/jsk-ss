"""Payment-level resolution must not release unrelated agreement obligations."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest.mock import Mock, patch

from django.core.exceptions import ValidationError
from django.db import IntegrityError, close_old_connections, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

from schemes.closure_selectors import closure_payment_review
from schemes.models import Contribution, InrPrincipalReceipt, PaymentErrorRefundResolution, PaymentRefundObservation, PaymentWebhookEvent
from schemes.payment_refund_observations import inspect_payment_error_refund
from schemes.payment_refund_resolutions import payment_refund_review_token, resolve_payment_error_refund
from schemes.payments import PaymentGatewayError
from schemes.services import confirm_contribution
from schemes.tests.test_inr_api_payments import ApiHelpers
from schemes.tests.test_independent_instalment_ledger import NOW
from schemes.tests import test_payment_refund_observations as fixtures


class RefundResolutionTests(ApiHelpers, TransactionTestCase):
    def gateway(self, c, payment_id=None):
        return fixtures.gateway_for(fixtures.payment(id=payment_id or f"pay_{c.pk}", order_id=c.gateway_order_id),
            [fixtures.page(fixtures.refund(payment_id=payment_id or f"pay_{c.pk}"))])

    def inspect(self, e, c, **changes):
        return inspect_payment_error_refund(**(dict(webhook_event_id=e.pk, performed_by=self.owner,
            reason="Review the manual original-source refund", gateway=self.gateway(c, e.gateway_reference)) | changes))

    def review(self, monthly=False):
        c, capture_gateway, payload, body = self.attempt(monthly)
        e = self.event(c, body)
        observation = self.inspect(e, c)
        token = payment_refund_review_token(observation_id=observation.pk, performed_by=self.owner)
        return c, e, observation, token, capture_gateway, payload, body

    def resolve(self, c, token, **changes):
        return resolve_payment_error_refund(**(dict(review_token=token, confirmed=True, performed_by=self.owner,
            reason="Provider reports the manually initiated full refund processed", gateway=self.gateway(c)) | changes))

    def test_fresh_resolution_is_idempotent_and_no_agreement_hold_or_finances_change(self):
        for monthly in (False, True):
            c, e, observation, token, _, _, _ = self.review(monthly)
            before = Contribution.objects.filter(pk=c.pk).values().get()
            result = self.resolve(c, token)
            self.assertEqual(result.reviewed_observation_id, observation.pk)
            self.assertNotEqual(result.applied_observation_id, observation.pk)
            retry_gateway = Mock()
            self.assertEqual(self.resolve(c, token, gateway=retry_gateway).pk, result.pk)
            retry_gateway.inspect_payment_refunds.assert_not_called()
            self.assertEqual(Contribution.objects.filter(pk=c.pk).values().get(), before)
            e.refresh_from_db()
            self.assertEqual(e.status, "RECEIVED")
            self.assertEqual(closure_payment_review(c.scheme_account)["unresolved_webhooks"], 1)
            self.assertEqual(closure_payment_review(c.scheme_account)["pending_payments"], 1)
        self.assertEqual(PaymentErrorRefundResolution.objects.count(), 2)
        self.assertFalse(InrPrincipalReceipt.objects.exists())

    def test_callback_signed_webhook_and_direct_confirmation_cannot_credit_resolved_payment(self):
        for monthly in (False, True):
            c, _, _, token, capture_gateway, payload, body = self.review(monthly)
            self.resolve(c, token)
            with self.assertRaisesMessage(ValidationError, "refunded without entitlement"):
                self.confirm(c, capture_gateway)
            with self.assertRaisesMessage(ValidationError, "refunded without entitlement"):
                confirm_contribution(contribution_id=c.pk, payment_gateway="razorpay", gateway_reference=f"pay_{c.pk}", verified=True)
            event = self.deliver(payload, body)
            self.assertEqual(event.status, "REVIEW_REQUIRED")
            c.refresh_from_db()
            self.assertEqual(c.status, "PENDING")
            self.assertFalse(InrPrincipalReceipt.objects.filter(contribution=c).exists())

    def test_owner_confirmation_signature_latest_observation_and_expiry_are_required(self):
        c, e, observation, token, _, _, _ = self.review()
        gateway = Mock()
        for changes in (dict(confirmed=False), dict(confirmed="true"), dict(review_token="bad"),
                        dict(performed_by=self.customer.user), dict(reason=" ")):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                self.resolve(c, token, gateway=gateway, **changes)
        with patch("django.utils.timezone.now", return_value=NOW + timedelta(minutes=11)):
            with self.assertRaises(ValidationError):
                self.resolve(c, token, gateway=gateway)
            with self.assertRaises(ValidationError):
                payment_refund_review_token(observation_id=observation.pk, performed_by=self.owner)
        self.inspect(e, c)
        with self.assertRaises(ValidationError):
            self.resolve(c, token, gateway=gateway)
        gateway.inspect_payment_refunds.assert_not_called()
        self.assertFalse(PaymentErrorRefundResolution.objects.exists())

    def test_partial_or_unavailable_fresh_provider_does_not_resolve_and_invalidates_safe_review(self):
        c, e, observation, token, _, _, _ = self.review()
        gateway = self.gateway(c)
        gateway._request_json.side_effect = PaymentGatewayError("Provider unavailable")
        with self.assertRaises(PaymentGatewayError):
            self.resolve(c, token, gateway=gateway)
        partial = fixtures.gateway_for(fixtures.payment(id=f"pay_{c.pk}", order_id=c.gateway_order_id,
            amount_refunded=10000, refund_status="partial", status="captured"),
            [fixtures.page(fixtures.refund(payment_id=f"pay_{c.pk}", amount=10000))])
        with self.assertRaises(ValidationError):
            self.resolve(c, token, gateway=partial)
        self.assertEqual(PaymentRefundObservation.objects.filter(webhook_event=e).count(), 2)
        with self.assertRaises(ValidationError):
            payment_refund_review_token(observation_id=observation.pk, performed_by=self.owner)
        self.assertFalse(PaymentErrorRefundResolution.objects.exists())

    def test_changed_refund_identity_requires_new_review_even_when_total_is_full(self):
        c, _, _, token, _, _, _ = self.review()
        changed = fixtures.gateway_for(fixtures.payment(id=f"pay_{c.pk}", order_id=c.gateway_order_id),
            [fixtures.page(fixtures.refund(id="rfnd_changed", payment_id=f"pay_{c.pk}"))])
        with self.assertRaises(ValidationError):
            self.resolve(c, token, gateway=changed)
        self.assertFalse(PaymentErrorRefundResolution.objects.exists())

    def test_capture_or_owner_revocation_during_reinspection_refuses_resolution(self):
        c, _, _, token, capture_gateway, _, _ = self.review()
        gateway = self.gateway(c)
        original = gateway.inspect_payment_refunds
        def inspect(**kwargs):
            result = original(**kwargs)
            self.confirm(c, capture_gateway)
            return result
        gateway.inspect_payment_refunds = inspect
        with self.assertRaises(ValidationError):
            self.resolve(c, token, gateway=gateway)
        self.assertEqual(InrPrincipalReceipt.objects.count(), 1)
        self.assertFalse(PaymentErrorRefundResolution.objects.exists())
        c, _, _, token, _, _, _ = self.review()
        gateway = self.gateway(c)
        original = gateway.inspect_payment_refunds
        def revoke(**kwargs):
            result = original(**kwargs)
            type(self.owner).objects.filter(pk=self.owner.pk).update(is_active=False)
            return result
        gateway.inspect_payment_refunds = revoke
        with self.assertRaises(ValidationError):
            self.resolve(c, token, gateway=gateway)
        self.assertFalse(PaymentErrorRefundResolution.objects.exists())

    def test_resolution_of_duplicate_preserves_legitimate_first_payment(self):
        c, capture_gateway, _, body = self.attempt()
        self.confirm(c, capture_gateway)
        e = self.event(c, body)
        PaymentWebhookEvent.objects.filter(pk=e.pk).update(gateway_reference="pay_extra", status="REVIEW_REQUIRED")
        e.refresh_from_db()
        observation = self.inspect(e, c)
        token = payment_refund_review_token(observation_id=observation.pk, performed_by=self.owner)
        self.resolve(c, token, gateway=self.gateway(c, "pay_extra"))
        self.confirm(c, capture_gateway)
        self.assertEqual(InrPrincipalReceipt.objects.filter(contribution=c).count(), 1)
        self.assertEqual(InrPrincipalReceipt.objects.get(contribution=c).source_reference, f"pay_{c.pk}")

    def test_concurrent_capture_and_resolution_can_never_both_succeed(self):
        c, _, _, token, capture_gateway, _, _ = self.review()
        barrier = Barrier(2)
        def run(resolving):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                try:
                    return ("resolved", self.resolve(c, token).pk) if resolving else ("credited", self.confirm(c, capture_gateway).pk)
                except ValidationError:
                    return ("refused", None)
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = [f.result(timeout=30) for f in (pool.submit(run, True), pool.submit(run, False))]
        self.assertEqual(sum(r[0] != "refused" for r in results), 1)
        self.assertEqual(PaymentErrorRefundResolution.objects.count() + InrPrincipalReceipt.objects.count(), 1)

    def test_resolution_database_protection_and_reverse_guard(self):
        leaves = MigrationExecutor(connection).loader.graph.leaf_nodes()
        self.addCleanup(lambda: MigrationExecutor(connection).migrate(leaves))
        MigrationExecutor(connection).migrate([("schemes", "0052_payment_refund_observations")])
        MigrationExecutor(connection).migrate(leaves)
        c, _, _, token, _, _, _ = self.review()
        result = self.resolve(c, token)
        for action in (result.save, result.delete):
            with self.assertRaises(ValidationError):
                action()
        for action in (lambda: PaymentErrorRefundResolution.objects.filter(pk=result.pk).update(reason="rewrite"),
                       lambda: PaymentErrorRefundResolution.objects.filter(pk=result.pk).delete()):
            with self.assertRaises(IntegrityError), transaction.atomic():
                action()
        with self.assertRaisesMessage(RuntimeError, "Cannot reverse 0053"):
            MigrationExecutor(connection).migrate([("schemes", "0052_payment_refund_observations")])
