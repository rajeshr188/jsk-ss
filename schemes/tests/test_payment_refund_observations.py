"""Provider evidence is not hold clearance or permission to mutate entitlements."""
from copy import deepcopy
from decimal import Decimal
from unittest.mock import Mock, patch

from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import SimpleTestCase, TransactionTestCase

from schemes.models import Contribution, InrPrincipalReceipt, MetalAllocation, PaymentRefundObservation, PaymentWebhookEvent
from schemes.payment_refund_observations import inspect_payment_error_refund
from schemes.payment_refund_evidence import REFUND_MAX_PAGES, REFUND_PAGE_SIZE, validate_snapshot
from schemes.payments import PaymentGatewayError, PaymentGatewayValidationError, RazorpayPaymentGateway
from schemes.tests.test_inr_api_payments import ApiHelpers
from schemes.tests import test_independent_payment_entry as entry


def payment(**changes):
    return dict(entity="payment", id="pay_example", order_id="order_example", amount=50000,
        currency="INR", status="refunded", captured=True, amount_refunded=50000, refund_status="full") | changes


def refund(**changes):
    return dict(entity="refund", id="rfnd_example", payment_id="pay_example", amount=50000,
        currency="INR", status="processed", created_at=1790000000) | changes


def page(*items):
    return dict(entity="collection", count=len(items), items=list(items))


def gateway_for(raw=None, pages=None, final=None):
    gateway = RazorpayPaymentGateway(mode="live", key_id="rzp_live_synthetic", key_secret="synthetic",
        webhook_secret="synthetic")
    raw = payment() if raw is None else raw
    pages = [page(refund())] if pages is None else pages
    gateway._request_json = Mock(side_effect=[raw, *pages, deepcopy(raw) if final is None else final])
    return gateway


class RefundProviderInspectionTests(SimpleTestCase):
    def test_exact_full_refund_uses_get_only_and_excludes_sensitive_payload(self):
        raw = payment(email="private@example.invalid", notes={"secret": "never retain"})
        gateway = gateway_for(raw, [page(refund(acquirer_data={"account": "private"}))])
        inspection = gateway.inspect_payment_refunds(payment_id="pay_example")
        self.assertTrue(inspection.fully_refunded)
        self.assertEqual(inspection, validate_snapshot(inspection.snapshot()))
        self.assertNotIn("private", str(inspection.snapshot()))
        self.assertNotIn("secret", str(inspection.snapshot()))
        self.assertEqual(gateway._request_json.call_args_list, [
            (("GET", "/payments/pay_example"),),
            (("GET", "/payments/pay_example/refunds?count=25&skip=0"),),
            (("GET", "/payments/pay_example"),),
        ])

    def test_all_pages_and_stable_payment_are_required(self):
        rows = [refund(id=f"rfnd_{n}", amount=2000) for n in range(25)]
        gateway = gateway_for(pages=[page(*rows), page()])
        self.assertTrue(gateway.inspect_payment_refunds(payment_id="pay_example").fully_refunded)
        self.assertIn("skip=25", gateway._request_json.call_args_list[2].args[1])
        changing = gateway_for(final=payment(amount_refunded=20000, refund_status="partial", status="captured"))
        with self.assertRaises(PaymentGatewayError):
            changing.inspect_payment_refunds(payment_id="pay_example")

    def test_partial_pending_failed_or_zero_refunds_never_qualify(self):
        cases = [
            (payment(status="captured", amount_refunded=0, refund_status=None), page()),
            (payment(status="captured", amount_refunded=20000, refund_status="partial"), page(refund(amount=20000))),
            (payment(status="captured", amount_refunded=0, refund_status=None), page(refund(status="pending"))),
            (payment(status="captured", amount_refunded=0, refund_status=None), page(refund(status="failed"))),
            (payment(), page(refund(), refund(id="rfnd_failed", status="failed"))),
        ]
        for raw, refunds in cases:
            with self.subTest(raw=raw, refunds=refunds):
                self.assertFalse(gateway_for(raw, [refunds]).inspect_payment_refunds(payment_id="pay_example").fully_refunded)

    def test_bad_payment_shapes_fail_closed(self):
        changes = [dict(id="pay_other"), dict(entity="refund"), dict(order_id="../secret"),
            dict(amount=True), dict(amount=50000.0), dict(amount="50000"), dict(amount=99),
            dict(currency="USD"), dict(captured=1), dict(captured=False), dict(status=[]),
            dict(status="captured"), dict(refund_status="partial"), dict(refund_status=[]),
            dict(amount_refunded=True), dict(amount_refunded=50001)]
        for change in changes:
            with self.subTest(change=change), self.assertRaises(PaymentGatewayError):
                gateway_for(payment(**change)).inspect_payment_refunds(payment_id="pay_example")

    def test_bad_refund_shapes_wrong_identity_and_totals_fail_closed(self):
        changes = [dict(id="bad"), dict(entity="payment"), dict(payment_id="pay_other"),
            dict(currency="USD"), dict(amount=True), dict(amount=50000.0), dict(amount=0),
            dict(status="unknown"), dict(status=[]), dict(created_at=True), dict(created_at=0), dict(amount=49999)]
        for change in changes:
            with self.subTest(change=change), self.assertRaises(PaymentGatewayError):
                gateway_for(pages=[page(refund(**change))]).inspect_payment_refunds(payment_id="pay_example")

    def test_incomplete_duplicate_or_unbounded_collection_fails_closed(self):
        for bad in (None, [], {}, dict(entity="collection", count=True, items=[]),
                    dict(entity="collection", count=1, items=[]), page(refund(), refund())):
            with self.subTest(bad=bad), self.assertRaises(PaymentGatewayError):
                gateway_for(pages=[bad]).inspect_payment_refunds(payment_id="pay_example")
        rows = [refund(id=f"rfnd_{n}", amount=100) for n in range(REFUND_PAGE_SIZE)]
        with self.assertRaises(PaymentGatewayError):
            gateway_for(pages=[page(*rows), page(rows[0])]).inspect_payment_refunds(payment_id="pay_example")
        pages = [page(*[refund(id=f"rfnd_{p}_{n}", amount=1) for n in range(REFUND_PAGE_SIZE)])
                 for p in range(REFUND_MAX_PAGES)]
        gateway = gateway_for(pages=pages)
        with self.assertRaises(PaymentGatewayError):
            gateway.inspect_payment_refunds(payment_id="pay_example")
        self.assertEqual(gateway._request_json.call_count, 1 + REFUND_MAX_PAGES)

    def test_invalid_ids_or_test_mode_make_no_provider_call(self):
        for identity in (None, "", "pay_", "pay_bad/path", "pay_bad?skip=0", "pay_" + "a" * 120):
            gateway = gateway_for()
            with self.subTest(identity=identity), self.assertRaises(PaymentGatewayValidationError):
                gateway.inspect_payment_refunds(payment_id=identity)
            gateway._request_json.assert_not_called()
        gateway = gateway_for()
        gateway.mode = "test"
        with self.assertRaises(PaymentGatewayValidationError):
            gateway.inspect_payment_refunds(payment_id="pay_example")
        gateway._request_json.assert_not_called()

    def test_timeout_and_unexpected_snapshot_fields_cannot_form_evidence(self):
        gateway = gateway_for()
        gateway._request_json.side_effect = PaymentGatewayError("Provider unavailable")
        with self.assertRaises(PaymentGatewayError):
            gateway.inspect_payment_refunds(payment_id="pay_example")
        snapshot = gateway_for().inspect_payment_refunds(payment_id="pay_example").snapshot()
        for field, value in (("private", "do not store"), ("refunds", {}), ("payment_id", "pay_other")):
            with self.subTest(field=field), self.assertRaises(PaymentGatewayError):
                validate_snapshot(snapshot | {field: value})


class RefundObservationTests(ApiHelpers, TransactionTestCase):
    def inspect(self, event, gateway, **changes):
        return inspect_payment_error_refund(**(dict(webhook_event_id=event.pk,
            performed_by=self.owner, reason="Investigate manually completed payment-error refund", gateway=gateway) | changes))

    def refund_gateway(self, c, payment_id=None):
        identity = payment_id or f"pay_{c.pk}"
        return gateway_for(payment(id=identity, order_id=c.gateway_order_id), [page(refund(payment_id=identity))])

    def test_observation_preserves_finances_event_and_every_hold_for_both_schedules(self):
        from schemes.closure_selectors import closure_payment_review
        from schemes.instalment_selectors import unresolved_instalment_captures
        for monthly in (False, True):
            c, _, _, body = self.attempt(monthly)
            Contribution.objects.filter(pk=c.pk).update(status="ABANDONED")
            event = self.event(c, body)
            PaymentWebhookEvent.objects.filter(pk=event.pk).update(status="REVIEW_REQUIRED")
            before = Contribution.objects.filter(pk=c.pk).values().get()
            event_before = PaymentWebhookEvent.objects.filter(pk=event.pk).values().get()
            gateway = self.refund_gateway(c)
            real_request = gateway._request_json
            def request(*args):
                self.assertFalse(connection.in_atomic_block)
                return real_request(*args)
            gateway._request_json = request
            observation = self.inspect(event, gateway)
            self.assertTrue(observation.fully_refunded)
            self.assertTrue(observation.no_entitlement)
            self.assertEqual(Contribution.objects.filter(pk=c.pk).values().get(), before)
            self.assertEqual(PaymentWebhookEvent.objects.filter(pk=event.pk).values().get(), event_before)
            self.assertEqual(closure_payment_review(c.scheme_account)["unresolved_webhooks"], 1)
            if monthly:
                self.assertEqual(unresolved_instalment_captures(account_id=c.scheme_account_id).count(), 1)
            self.assertFalse(InrPrincipalReceipt.objects.filter(contribution=c).exists())
            self.assertFalse(MetalAllocation.objects.filter(contribution=c).exists())
        self.assertEqual(PaymentRefundObservation.objects.count(), 2)

    def test_credited_payment_remains_ineligible_but_different_duplicate_does_not_erase_first(self):
        c, gateway, _, body = self.attempt()
        self.confirm(c, gateway)
        event = self.event(c, body)
        observed = self.inspect(event, self.refund_gateway(c))
        self.assertFalse(observed.no_entitlement)
        PaymentWebhookEvent.objects.filter(pk=event.pk).update(gateway_reference="pay_duplicate")
        observed = self.inspect(event, self.refund_gateway(c, "pay_duplicate"))
        self.assertTrue(observed.no_entitlement)
        self.assertEqual(InrPrincipalReceipt.objects.get(contribution=c).amount, c.amount)

    def test_revoked_owner_crosslinked_wrong_mode_and_nested_transaction_fail_before_io(self):
        c, _, _, body = self.attempt()
        e = self.event(c, body)
        gateway = self.refund_gateway(c)
        with transaction.atomic(), self.assertRaisesMessage(ValidationError, "outside"):
            self.inspect(e, gateway)
        with self.assertRaises(ValidationError):
            self.inspect(e, gateway, reason=" ")
        type(self.owner).objects.filter(pk=self.owner.pk).update(is_active=False)
        with self.assertRaises(ValidationError):
            self.inspect(e, gateway)
        type(self.owner).objects.filter(pk=self.owner.pk).update(is_active=True)
        PaymentWebhookEvent.objects.filter(pk=e.pk).update(gateway_mode="test")
        with self.assertRaises(ValidationError):
            self.inspect(e, gateway)
        other, _, _, _ = self.attempt()
        PaymentWebhookEvent.objects.filter(pk=e.pk).update(gateway_mode="live", contribution=other)
        with self.assertRaises(ValidationError):
            self.inspect(e, gateway)
        gateway._request_json.assert_not_called()
        self.assertFalse(PaymentRefundObservation.objects.exists())

    def test_owner_revocation_local_change_and_provider_mismatch_during_inspection_leave_no_evidence(self):
        c, _, _, body = self.attempt()
        e = self.event(c, body)
        for mutation in (lambda: type(self.owner).objects.filter(pk=self.owner.pk).update(is_active=False),
                         lambda: PaymentWebhookEvent.objects.filter(pk=e.pk).update(status="FAILED")):
            gateway = self.refund_gateway(c)
            original = gateway.inspect_payment_refunds
            def inspect(**kwargs):
                result = original(**kwargs)
                mutation()
                return result
            gateway.inspect_payment_refunds = inspect
            with self.assertRaises(ValidationError):
                self.inspect(e, gateway)
            type(self.owner).objects.filter(pk=self.owner.pk).update(is_active=True)
            PaymentWebhookEvent.objects.filter(pk=e.pk).update(status="RECEIVED")
        with self.assertRaises(ValidationError):
            self.inspect(e, gateway_for(payment(id=e.gateway_reference),
                [page(refund(payment_id=e.gateway_reference))]))
        self.assertFalse(PaymentRefundObservation.objects.exists())

    def test_capture_during_network_inspection_cannot_leave_stale_no_entitlement_proof(self):
        c, capture_gateway, _, body = self.attempt()
        e = self.event(c, body)
        gateway = self.refund_gateway(c)
        original = gateway.inspect_payment_refunds
        def inspect(**kwargs):
            result = original(**kwargs)
            self.confirm(c, capture_gateway)
            return result
        gateway.inspect_payment_refunds = inspect
        with self.assertRaisesMessage(ValidationError, "changed during inspection"):
            self.inspect(e, gateway)
        self.assertFalse(PaymentRefundObservation.objects.exists())
        self.assertEqual(InrPrincipalReceipt.objects.filter(contribution=c).count(), 1)

    def test_metal_receipt_and_grade_are_preserved_and_customer_cannot_inspect(self):
        from schemes.services import initiate_razorpay_contribution
        account = entry.IndependentPaymentEntryTests.account(self, False, True)
        creation_gateway = entry.IndependentPaymentEntryTests.gateway(self)
        c = initiate_razorpay_contribution(scheme_account=account, amount=Decimal("500"),
            gateway=creation_gateway)
        capture_gateway = gateway_for()
        capture_gateway.key_secret = "synthetic-secret"
        capture_gateway._request_json = Mock(return_value=payment(id=f"pay_{c.pk}", order_id=c.gateway_order_id,
            status="captured", amount_refunded=0, refund_status=None))
        self.confirm(c, capture_gateway)
        event = self.event(c, b"retained synthetic metal capture")
        allocation = MetalAllocation.objects.filter(contribution=c).values().get()
        observed = self.inspect(event, self.refund_gateway(c))
        self.assertFalse(observed.no_entitlement)
        self.assertEqual(MetalAllocation.objects.filter(contribution=c).values().get(), allocation)
        gateway = self.refund_gateway(c)
        with self.assertRaises(ValidationError):
            self.inspect(event, gateway, performed_by=self.customer.user)
        gateway._request_json.assert_not_called()

    def test_malformed_evidence_is_not_stored_and_valid_repeat_is_new_observation(self):
        c, _, _, body = self.attempt()
        e = self.event(c, body)
        gateway = self.refund_gateway(c)
        gateway._request_json.side_effect = PaymentGatewayError("unsafe secret payload")
        with self.assertRaises(PaymentGatewayError):
            self.inspect(e, gateway)
        self.assertFalse(PaymentRefundObservation.objects.exists())
        first = self.inspect(e, self.refund_gateway(c))
        second = self.inspect(e, self.refund_gateway(c))
        self.assertNotEqual(first.pk, second.pk)
        self.assertEqual(first.evidence_sha256, second.evidence_sha256)
        self.assertEqual(first.actor_id, self.owner.pk)
        for action in (first.save, first.delete):
            with self.assertRaises(ValidationError):
                action()
        for action in (lambda: PaymentRefundObservation.objects.filter(pk=first.pk).update(reason="rewrite"),
                       lambda: PaymentRefundObservation.objects.filter(pk=first.pk).delete()):
            with self.assertRaises(IntegrityError), transaction.atomic():
                action()
        second.provider_snapshot["extra"] = "private"
        with self.assertRaises(ValidationError):
            second.full_clean()

    def test_migration_roundtrip_preserves_finances_and_refuses_evidence_loss(self):
        leaves = MigrationExecutor(connection).loader.graph.leaf_nodes()
        self.addCleanup(lambda: MigrationExecutor(connection).migrate(leaves))
        c, _, _, body = self.attempt()
        before = Contribution.objects.filter(pk=c.pk).values().get()
        MigrationExecutor(connection).migrate([("schemes", "0051_inr_completion_reminders")])
        MigrationExecutor(connection).migrate(leaves)
        self.assertEqual(Contribution.objects.filter(pk=c.pk).values().get(), before)
        self.inspect(self.event(c, body), self.refund_gateway(c))
        with self.assertRaisesMessage(RuntimeError, "Cannot reverse 0052"):
            MigrationExecutor(connection).migrate([("schemes", "0051_inr_completion_reminders")])
        self.assertEqual(PaymentRefundObservation.objects.count(), 1)
