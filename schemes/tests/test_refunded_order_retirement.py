"""Synthetic provider reads; exact resolutions never erase other payment exposure."""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from io import StringIO
import json
from threading import Barrier
import uuid
from unittest.mock import Mock, patch

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError, close_old_connections, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.db.models import Exists, OuterRef
from django.test import SimpleTestCase, TransactionTestCase, override_settings

from schemes.agreement_eligibility import get_independent_eligibility
from schemes.closure_selectors import closure_payment_review
from schemes.inr_settlement_selectors import inr_payment_source_evidence
from schemes.instalment_selectors import instalment_payment_ledger_summary, unresolved_instalment_captures
from schemes.models import (Contribution, InrPrincipalReceipt, InstalmentReservation, MetalAllocation,
    PaymentWebhookEvent, RefundedPaymentOrderClosure, SchemeInstalmentPeriod)
from schemes.payment_refund_resolutions import payment_refund_review_token
from schemes.payment_refund_selectors import unresolved_payment_events
from schemes.payments import PaymentGatewayError, PaymentOrderInspection
from schemes.refunded_order_evidence import inspect_refunded_order
from schemes.refunded_orders import refunded_order_review_token, retire_refunded_order, validate_refunded_order_closure
from schemes.selectors import get_financial_exception_counts, get_owner_exception_keys
from schemes.services import initiate_razorpay_contribution, reconcile_abandoned_razorpay_contribution
from schemes.settlement_selectors import full_settlement_evidence
from schemes.tests.test_inr_api_payments import ApiHelpers
from schemes.tests.test_independent_instalment_ledger import NOW
from schemes.tests import test_independent_payment_entry as entry
from schemes.tests import test_payment_refund_observations as provider
from schemes.tests import test_payment_refund_resolutions as resolution
from schemes.tests.test_independent_metal_settlement import MetalClosureFixture
from schemes.tests.test_benefit_awards import future_award_readiness


def order_gateway(order_id="order_example", payment_id="pay_example", *, order_changes=None, payments=None, final=None):
    order = dict(entity="order", id=order_id, currency="INR", amount=50000,
        amount_paid=50000, amount_due=0, status="paid", attempts=1) | (order_changes or {})
    payments = [provider.payment(id=payment_id, order_id=order_id)] if payments is None else payments
    gateway = provider.gateway_for()
    gateway._request_json = Mock(side_effect=[order, provider.page(*payments), deepcopy(order) if final is None else final])
    return gateway


class RefundedOrderProviderTests(SimpleTestCase):
    def test_complete_stable_paid_order_is_read_only_and_minimal(self):
        gateway = order_gateway(payments=[provider.payment(email="private", notes={"secret": "private"})])
        evidence = inspect_refunded_order(gateway=gateway, order_id="order_example")
        self.assertNotIn("private", str(evidence))
        self.assertEqual(gateway._request_json.call_args_list, [
            (("GET", "/orders/order_example"),), (("GET", "/orders/order_example/payments"),),
            (("GET", "/orders/order_example"),)])
        failed = provider.payment(id="pay_failed", status="failed", captured=False, amount_refunded=0, refund_status=None)
        result = inspect_refunded_order(gateway=order_gateway(order_changes={"attempts": 2},
            payments=[failed, provider.payment()]), order_id="order_example")
        self.assertEqual(len(result["payments"]), 2)

    def test_incomplete_changing_nonterminal_mismatched_or_excess_evidence_refused(self):
        cases = [dict(order_changes={"attempts": 2}), dict(order_changes={"attempts": True}),
            dict(order_changes={"status": "attempted"}), dict(order_changes={"amount_paid": 0}),
            dict(order_changes={"currency": "USD"}), dict(final={}),
            dict(payments=[provider.payment(order_id="order_other")]),
            dict(payments=[provider.payment(amount=60000, amount_refunded=60000)]),
            dict(order_changes={"attempts": 2}, payments=[provider.payment(), provider.payment()])]
        for state in ("created", "authorized", "captured", "failed"):
            cases.append(dict(payments=[provider.payment(status=state, captured=state == "captured",
                amount_refunded=0, refund_status=None)]))
        for changes in cases:
            with self.subTest(changes=changes), self.assertRaises(PaymentGatewayError):
                inspect_refunded_order(gateway=order_gateway(**changes), order_id="order_example")


@override_settings(IN_STORE_CASH_CONTRIBUTIONS_ENABLED=True, PAYMENT_INITIATION_KILL_SWITCH=False,
    PAYMENT_GATEWAY="razorpay", RAZORPAY_MODE="live", RAZORPAY_KEY_ID="rzp_live_synthetic",
    RAZORPAY_KEY_SECRET="synthetic", RAZORPAY_WEBHOOK_SECRET="synthetic")
class RefundedOrderLifecycleTests(ApiHelpers, TransactionTestCase):
    account = entry.IndependentPaymentEntryTests.account
    cash = entry.IndependentPaymentEntryTests.cash
    gateway = resolution.RefundResolutionTests.gateway
    inspect = resolution.RefundResolutionTests.inspect
    resolve = resolution.RefundResolutionTests.resolve

    def prepare(self, monthly=False, metal=False):
        account = self.account(monthly, metal)
        c = initiate_razorpay_contribution(scheme_account=account, amount=Decimal("500"),
            gateway=entry.IndependentPaymentEntryTests.gateway(self))
        payload = dict(event="payment.captured", created_at=int(NOW.timestamp()), payload={"payment": {"entity": {
            "id": f"pay_{c.pk}", "order_id": c.gateway_order_id, "amount": 50000, "currency": "INR",
            "status": "captured", "captured": True, "created_at": int(NOW.timestamp())}}})
        body = json.dumps(payload).encode()
        e = self.event(c, body)
        observation = self.inspect(e, c)
        token = payment_refund_review_token(observation_id=observation.pk, performed_by=self.owner)
        self.resolve(c, token)
        return c, e, payload, body

    def order_review(self, c, **changes):
        return refunded_order_review_token(contribution_id=c.pk, performed_by=self.owner,
            gateway=order_gateway(c.gateway_order_id, f"pay_{c.pk}", **changes))

    def retire(self, c, token, **changes):
        return retire_refunded_order(**(dict(review_token=token, confirmed=True, performed_by=self.owner,
            reason="Reviewed every provider attempt and its full original-source refund",
            gateway=order_gateway(c.gateway_order_id, f"pay_{c.pk}")) | changes))

    def test_resolution_only_clears_exact_event_not_pending_order_and_diagnostics_agree(self):
        c, e, _, _ = self.prepare(True)
        e.status = "REVIEW_REQUIRED"
        e.save(update_fields=["status"])
        self.assertEqual(closure_payment_review(c.scheme_account)["unresolved_webhooks"], 0)
        self.assertEqual(closure_payment_review(c.scheme_account)["pending_payments"], 1)
        self.assertEqual(c.instalment_reservation.state, "RESERVED")
        self.assertEqual(get_financial_exception_counts().failed_webhooks, 0)
        self.assertFalse(list(get_owner_exception_keys()))
        out = StringIO()
        call_command("check_razorpay_live_readiness", stdout=out)
        self.assertIn("failed_live_webhooks=0", out.getvalue())
        # This helper also appears inside an Exists with two correlation levels.
        query = SchemeInstalmentPeriod.objects.alias(held=Exists(
            unresolved_instalment_captures(period_id=OuterRef(OuterRef("pk")))))
        self.assertFalse(query.filter(held=True).exists())
        self.assertEqual(instalment_payment_ledger_summary(account_id=c.scheme_account_id)["unresolved_capture_events"], 0)

    def test_other_payload_payment_order_mode_link_and_invalid_proof_stay_held(self):
        c, e, _, _ = self.prepare()
        for changes in (dict(payload_sha256="f" * 64), dict(gateway_reference="pay_other"),
                        dict(gateway_order_id="order_other"), dict(gateway_mode="test"), dict(event_type="payment.failed")):
            other = PaymentWebhookEvent.objects.create(contribution=c, gateway="razorpay",
                **(dict(gateway_mode="live", gateway_reference=e.gateway_reference, gateway_order_id=e.gateway_order_id,
                    event_type=e.event_type, payload_sha256=e.payload_sha256) | changes), event_id=uuid.uuid4().hex,
                status="REVIEW_REQUIRED")
            self.assertTrue(unresolved_payment_events(PaymentWebhookEvent.objects.filter(pk=other.pk)).exists())
        with self.assertRaises(ValidationError):
            self.order_review(c)
        with patch("schemes.payment_refund_selectors.validate_resolution", side_effect=ValidationError("Invalid retained proof")):
            self.assertTrue(unresolved_payment_events(PaymentWebhookEvent.objects.filter(pk=e.pk)).exists())

    def test_both_denominations_and_schedules_retire_without_credit_then_allow_legitimate_replacement(self):
        for monthly in (False, True):
            for metal in (False, True):
                c, e, _, _ = self.prepare(monthly, metal)
                before = Contribution.objects.filter(pk=c.pk).values().get()
                record = self.retire(c, self.order_review(c))
                c.refresh_from_db()
                after = Contribution.objects.filter(pk=c.pk).values().get()
                self.assertEqual(after, before | {"status": "ABANDONED"})
                validate_refunded_order_closure(record)
                self.assertEqual(get_independent_eligibility(c.scheme_account).state, "NO_ENTITLEMENT")
                self.assertFalse(InrPrincipalReceipt.objects.filter(contribution=c).exists())
                self.assertFalse(MetalAllocation.objects.filter(contribution=c).exists())
                if monthly:
                    claim = c.instalment_reservation
                    self.assertEqual(claim.state, "RELEASED")
                    self.assertEqual(claim.decisions.last().refund_order_closure_id, record.pk)
                    ledger = instalment_payment_ledger_summary(account_id=c.scheme_account_id)
                    self.assertEqual((ledger["integrity_errors"], ledger["qualified_payments"]), (0, 0))
                replacement = self.cash(c.scheme_account)
                self.assertEqual(replacement.status, "PAID")
                if monthly:
                    ledger = instalment_payment_ledger_summary(account_id=c.scheme_account_id)
                    self.assertEqual((ledger["integrity_errors"], ledger["qualified_payments"]), (0, 1))
                if not metal:
                    proof = inr_payment_source_evidence(c.scheme_account)
                    self.assertEqual(proof["principal"], "500.00")
                    self.assertEqual(proof["refunded_orders"][0]["id"], record.pk)
                else:
                    with future_award_readiness():
                        closure = MetalClosureFixture.accepted(self, c.scheme_account)
                        proof = full_settlement_evidence(c.scheme_account, closure)
                    self.assertEqual(proof["quantity"], "0.050000")
                    self.assertEqual([p["id"] for p in proof["payments"]], [replacement.pk])
                    self.assertEqual(proof["refunded_orders"][0]["id"], record.pk)

    def test_exact_replay_does_not_reopen_reservation_but_new_capture_does(self):
        c, _, payload, body = self.prepare(True)
        self.retire(c, self.order_review(c))
        event = self.deliver(payload, body)
        self.assertEqual(event.failure_code, "REFUNDED_PAYMENT_REPLAY")
        c.refresh_from_db()
        self.assertEqual(c.instalment_reservation.state, "RELEASED")
        changed = deepcopy(payload)
        changed["payload"]["payment"]["entity"]["id"] = "pay_unaccounted"
        event = self.deliver(changed, json.dumps(changed).encode())
        self.assertEqual(event.failure_code, "LATE_CAPTURE_ABANDONED")
        c.refresh_from_db()
        self.assertEqual(c.instalment_reservation.state, "RELEASED_REVIEW")
        self.assertEqual(closure_payment_review(c.scheme_account)["unresolved_webhooks"], 1)
        with self.assertRaises(ValidationError):
            self.cash(c.scheme_account)

    def test_fresh_order_read_and_owner_bound_review_cannot_be_bypassed(self):
        c, _, _, _ = self.prepare()
        token = self.order_review(c)
        for changes in (dict(confirmed=False), dict(confirmed="yes"), dict(reason=" "),
                        dict(performed_by=self.customer.user), dict(review_token="bad")):
            gateway = Mock()
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                self.retire(c, token, gateway=gateway, **changes)
            gateway._request_json.assert_not_called()
        with patch("django.utils.timezone.now", return_value=NOW + timedelta(minutes=11)):
            with self.assertRaises(ValidationError):
                self.retire(c, token)
        with self.assertRaises(PaymentGatewayError):
            self.retire(c, token, gateway=order_gateway(c.gateway_order_id, f"pay_{c.pk}", order_changes={"attempts": 2}))
        self.assertFalse(RefundedPaymentOrderClosure.objects.exists())
        record = self.retire(c, token)
        gateway = Mock()
        self.assertEqual(self.retire(c, token, gateway=gateway).pk, record.pk)
        gateway._request_json.assert_not_called()

    def test_contradictory_event_arriving_during_fresh_read_prevents_retirement(self):
        c, e, _, _ = self.prepare()
        token = self.order_review(c)
        gateway = order_gateway(c.gateway_order_id, f"pay_{c.pk}")
        original = gateway._request_json.side_effect
        def fetch(*args):
            result = next(original)
            if args[1].endswith("/payments"):
                PaymentWebhookEvent.objects.create(contribution=c, gateway="razorpay", gateway_mode="live",
                    gateway_order_id=c.gateway_order_id, gateway_reference="pay_unaccounted", event_type="payment.captured",
                    payload_sha256="f" * 64, event_id=uuid.uuid4().hex, status="REVIEW_REQUIRED")
            return result
        gateway._request_json.side_effect = fetch
        with self.assertRaises(ValidationError):
            self.retire(c, token, gateway=gateway)
        c.refresh_from_db()
        self.assertEqual(c.status, "PENDING")
        self.assertFalse(RefundedPaymentOrderClosure.objects.exists())

    def test_concurrent_retirement_appends_one_release_and_preserves_migration_evidence(self):
        c, _, _, _ = self.prepare(True)
        token = self.order_review(c)
        barrier = Barrier(2)
        def run():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                try:
                    return self.retire(c, token).pk
                except ValidationError:
                    return None  # Losing stale reinspection is safely refused.
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = [f.result(timeout=60) for f in (pool.submit(run), pool.submit(run))]
        record = RefundedPaymentOrderClosure.objects.get()
        self.assertIn(record.pk, results)
        self.assertEqual(c.instalment_reservation.decisions.filter(refund_order_closure=record).count(), 1)
        for operation in (record.save, record.delete):
            with self.assertRaises(ValidationError):
                operation()
        for operation in (lambda: RefundedPaymentOrderClosure.objects.filter(pk=record.pk).update(reason="rewrite"),
                          lambda: RefundedPaymentOrderClosure.objects.filter(pk=record.pk).delete()):
            with self.assertRaises(IntegrityError), transaction.atomic():
                operation()
        with self.assertRaisesMessage(RuntimeError, "Cannot reverse 0054"):
            MigrationExecutor(connection).migrate([("schemes", "0053_payment_error_refund_resolution")])

    def test_refunded_late_capture_releases_review_without_touching_existing_replacement(self):
        account = self.account(True)
        gateway = entry.IndependentPaymentEntryTests.gateway(self)
        c = initiate_razorpay_contribution(scheme_account=account, amount=Decimal("500"), gateway=gateway)
        gateway.inspect_order.return_value = PaymentOrderInspection(c.gateway_order_id,
            "created", 50000, 0, 50000, "INR", 0, 0, ())
        with patch("django.utils.timezone.now", return_value=NOW + timedelta(minutes=11)):
            reconcile_abandoned_razorpay_contribution(contribution_id=c.pk, cutoff=NOW, gateway=gateway, apply=True)
            replacement = self.cash(account)
        payload = dict(event="payment.captured", created_at=int((NOW + timedelta(minutes=12)).timestamp()),
            payload={"payment": {"entity": dict(id=f"pay_{c.pk}", order_id=c.gateway_order_id,
                amount=50000, currency="INR", status="captured", captured=True, created_at=int(NOW.timestamp()))}})
        body = json.dumps(payload).encode()
        with patch("django.utils.timezone.now", return_value=NOW + timedelta(minutes=13)):
            e = self.deliver(payload, body)
            c.refresh_from_db()
            self.assertEqual(c.instalment_reservation.state, "RELEASED_REVIEW")
            before = list(InrPrincipalReceipt.objects.values())
            obs = self.inspect(e, c)
            self.resolve(c, payment_refund_review_token(observation_id=obs.pk, performed_by=self.owner))
            self.assertEqual(InstalmentReservation.objects.get(contribution=c).state, "RELEASED_REVIEW")
            self.retire(c, self.order_review(c))
            summary = instalment_payment_ledger_summary(account_id=account.pk)
            self.assertEqual((summary["integrity_errors"], summary["review_required"], summary["qualified_payments"]), (0, 0, 1))
            self.assertEqual(InstalmentReservation.objects.get(contribution=replacement).state, "QUALIFIED")
            self.assertEqual(list(InrPrincipalReceipt.objects.values()), before)
            self.deliver(payload, body)
            self.assertEqual(InstalmentReservation.objects.get(contribution=c).state, "RELEASED")

    def test_revoked_owner_and_unresolved_additional_refund_cannot_retire(self):
        c, _, _, _ = self.prepare()
        with self.assertRaises(ValidationError):
            self.order_review(c, payments=[provider.payment(id="pay_unresolved", order_id=c.gateway_order_id)])
        token = self.order_review(c)
        gateway = order_gateway(c.gateway_order_id, f"pay_{c.pk}")
        original = gateway._request_json.side_effect
        def revoke(*args):
            result = next(original)
            type(self.owner).objects.filter(pk=self.owner.pk).update(is_active=False)
            return result
        gateway._request_json.side_effect = revoke
        with self.assertRaises(ValidationError):
            self.retire(c, token, gateway=gateway)
        self.assertFalse(RefundedPaymentOrderClosure.objects.exists())

    def test_corrupt_retirement_or_wrong_event_link_is_not_silently_cleared(self):
        c, e, _, _ = self.prepare()
        self.retire(c, self.order_review(c))
        Contribution.objects.filter(pk=c.pk).update(status="FAILED")  # Simulate projection corruption.
        self.assertEqual(get_financial_exception_counts().refund_disposition_errors, 1)
        with self.assertRaises(ValidationError):
            inr_payment_source_evidence(c.scheme_account)
        Contribution.objects.filter(pk=c.pk).update(status="ABANDONED")
        other, _, _, _ = self.prepare()
        wrong = PaymentWebhookEvent.objects.create(contribution=other, gateway="razorpay", gateway_mode="live",
            gateway_reference=e.gateway_reference, gateway_order_id=e.gateway_order_id, payload_sha256=e.payload_sha256,
            event_type="payment.captured", event_id=uuid.uuid4().hex, status="REVIEW_REQUIRED")
        self.assertTrue(unresolved_payment_events(PaymentWebhookEvent.objects.filter(pk=wrong.pk)).exists())
        self.assertEqual(closure_payment_review(c.scheme_account)["unresolved_webhooks"], 1)
