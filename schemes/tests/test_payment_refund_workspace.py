"""Owner HTTP journeys over real refund services with synthetic provider responses."""
from datetime import timedelta
from decimal import Decimal
import json
from unittest.mock import patch

from django.db import connection
from django.test import Client, TransactionTestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from schemes.models import (Contribution, InrPrincipalReceipt, MetalAllocation, PaymentErrorRefundResolution,
    PaymentRefundObservation, RefundedPaymentOrderClosure)
from schemes.payments import PaymentGatewayError
from schemes.services import initiate_razorpay_contribution
from schemes.tests.test_inr_api_payments import ApiHelpers
from schemes.tests.test_audit_exceptions import make_owner
from schemes.tests.test_independent_instalment_ledger import NOW
from schemes.tests import test_independent_payment_entry as entry
from schemes.tests import test_payment_refund_observations as provider
from schemes.tests.test_refunded_order_retirement import order_gateway


@override_settings(PAYMENT_INITIATION_KILL_SWITCH=False)
class PaymentRefundWorkspaceTests(ApiHelpers, TransactionTestCase):
    account = entry.IndependentPaymentEntryTests.account

    def prepare(self, monthly=False, metal=False):
        c = initiate_razorpay_contribution(scheme_account=self.account(monthly, metal), amount=Decimal("500"),
            gateway=entry.IndependentPaymentEntryTests.gateway(self))
        payload = dict(event="payment.captured", payload={"payment": {"entity": dict(id=f"pay_{c.pk}",
            order_id=c.gateway_order_id, amount=50000, currency="INR", captured=True, status="captured")}})
        return c, self.event(c, json.dumps(payload).encode())

    def url(self, e):
        return reverse("schemes:payment_refund_review", args=[e.pk])

    def order_url(self, c):
        return reverse("schemes:refunded_order_review", args=[c.pk])

    def gateway(self, c):
        return provider.gateway_for(provider.payment(id=f"pay_{c.pk}", order_id=c.gateway_order_id),
            [provider.page(provider.refund(payment_id=f"pay_{c.pk}"))])

    def inspect(self, c, e, gateway=None):
        with patch("schemes.payment_refund_observations.get_payment_gateway", return_value=gateway or self.gateway(c)):
            response = self.client.post(self.url(e), dict(action="INSPECT", reason="Checked approved original-source refund"))
        self.assertEqual(response.status_code, 302)
        return self.client.get(self.url(e))

    def values(self, page):
        return dict(action="APPLY", confirmed="on", reason="Confirmed exact evidence displayed",
            review_token=page.context["form"]["review_token"].value())

    def resolve(self, c, e, values):
        with patch("schemes.payment_refund_observations.get_payment_gateway", return_value=self.gateway(c)):
            return self.client.post(self.url(e), values)

    def resolved(self, monthly=False, metal=False):
        c, e = self.prepare(monthly, metal)
        page = self.inspect(c, e)
        self.assertEqual(self.resolve(c, e, self.values(page)).status_code, 302)
        return c, e

    def test_get_is_private_read_only_and_authorization_csrf_methods_are_enforced(self):
        c, e = self.prepare()
        urls = [self.url(e), self.order_url(c), reverse("schemes:refund_history")]
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.customer.user)
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_login(self.owner)
        with patch("schemes.payment_refund_observations.get_payment_gateway") as payment_gateway, \
             patch("schemes.refunded_orders.get_payment_gateway") as order_provider:
            for url in urls:
                with CaptureQueriesContext(connection) as queries:
                    response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertIn("no-store", response.headers["Cache-Control"])
                self.assertIn("Cookie", response.headers["Vary"])
                self.assertFalse(any(q["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")) for q in queries))
                self.assertEqual(self.client.put(url).status_code, 405)
            payment_gateway.assert_not_called()
            order_provider.assert_not_called()
        secure = Client(enforce_csrf_checks=True)
        secure.force_login(self.owner)
        for url in urls[:2]:
            self.assertEqual(secure.post(url, dict(action="INSPECT", reason="Check")).status_code, 403)
        self.assertFalse(PaymentRefundObservation.objects.exists())

    def test_optional_and_monthly_both_denominations_require_two_separate_confirmations(self):
        self.client.force_login(self.owner)
        for monthly in (False, True):
            for metal in (False, True):
                c, e = self.prepare(monthly, metal)
                before = Contribution.objects.filter(pk=c.pk).values().get()
                page = self.inspect(c, e)
                self.assertContains(page, "No historical local entitlement")
                self.assertContains(page, "500.00")
                self.assertContains(page, 'id="id_reason_helptext"')
                self.assertTrue(page.context["can_resolve"])
                values = self.values(page)
                self.assertEqual(self.resolve(c, e, values).status_code, 302)
                self.assertEqual(self.resolve(c, e, values).status_code, 302)
                self.assertEqual(Contribution.objects.filter(pk=c.pk).values().get(), before)
                page = self.client.get(self.url(e))
                self.assertContains(page, "This exact capture is resolved")
                self.assertFalse(page.context["can_resolve"])
                self.assertContains(self.client.get(reverse("schemes:refund_history")), f"pay_{c.pk}")
                with patch("schemes.refunded_orders.get_payment_gateway", return_value=order_gateway(c.gateway_order_id, f"pay_{c.pk}")):
                    page = self.client.post(self.order_url(c), dict(action="INSPECT", reason="Review every attempt"))
                self.assertContains(page, "Fresh all-attempt comparison")
                self.assertEqual(Contribution.objects.get(pk=c.pk).status, "PENDING")
                values = self.values(page)
                with patch("schemes.refunded_orders.get_payment_gateway", return_value=order_gateway(c.gateway_order_id, f"pay_{c.pk}")):
                    self.assertEqual(self.client.post(self.order_url(c), values).status_code, 302)
                    self.assertEqual(self.client.post(self.order_url(c), values).status_code, 302)
                page = self.client.get(self.order_url(c))
                self.assertContains(page, "The retirement evidence is valid")
                c.refresh_from_db()
                self.assertEqual(c.status, "ABANDONED")
                if monthly:
                    self.assertEqual(c.instalment_reservation.state, "RELEASED")
                self.assertEqual(PaymentErrorRefundResolution.objects.filter(contribution=c).count(), 1)
        self.assertFalse(InrPrincipalReceipt.objects.exists())
        self.assertFalse(MetalAllocation.objects.exists())
        self.assertEqual(RefundedPaymentOrderClosure.objects.count(), 4)

    def test_payment_confirmation_is_owner_event_and_time_bound_before_provider_io(self):
        self.client.force_login(self.owner)
        c, e = self.prepare()
        values = self.values(self.inspect(c, e))
        other_c, other_e = self.prepare()
        with patch("schemes.payment_refund_observations.get_payment_gateway") as gateway:
            for changed in (values | {"confirmed": ""}, values | {"review_token": "bad"}, values | {"review_token": ""}):
                self.assertEqual(self.client.post(self.url(e), changed).status_code, 200)
            self.assertEqual(self.client.post(self.url(other_e), values).status_code, 200)
            self.client.force_login(make_owner("second-owner@example.invalid"))
            self.assertEqual(self.client.post(self.url(e), values).status_code, 200)
            self.client.force_login(self.owner)
            with patch("django.utils.timezone.now", return_value=NOW + timedelta(minutes=11)):
                self.assertFalse(self.client.get(self.url(e)).context["can_resolve"])
                self.assertEqual(self.client.post(self.url(e), values).status_code, 200)
            gateway.assert_not_called()
        self.assertFalse(PaymentErrorRefundResolution.objects.exists())

    def test_partial_fresh_refund_provider_failure_and_new_inspection_block_apply(self):
        self.client.force_login(self.owner)
        c, e = self.prepare()
        values = self.values(self.inspect(c, e))
        partial = provider.gateway_for(provider.payment(id=f"pay_{c.pk}", order_id=c.gateway_order_id,
            status="captured", amount_refunded=10000, refund_status="partial"),
            [provider.page(provider.refund(payment_id=f"pay_{c.pk}", amount=10000))])
        with patch("schemes.payment_refund_observations.get_payment_gateway", return_value=partial):
            page = self.client.post(self.url(e), values)
        self.assertFalse(page.context["can_resolve"])
        self.assertContains(page, "100.00")
        with patch("schemes.payment_refund_observations.get_payment_gateway") as gateway:
            self.assertEqual(self.client.post(self.url(e), values).status_code, 200)
            gateway.assert_not_called()
        gateway = self.gateway(c)
        gateway._request_json.side_effect = PaymentGatewayError("PRIVATE PROVIDER SECRET")
        with patch("schemes.payment_refund_observations.get_payment_gateway", return_value=gateway):
            page = self.client.post(self.url(e), dict(action="INSPECT", reason="Retry"))
        self.assertContains(page, "Provider inspection is unavailable")
        self.assertNotContains(page, "PRIVATE PROVIDER SECRET")
        self.assertFalse(PaymentErrorRefundResolution.objects.exists())

    def test_order_confirmation_rejects_cross_route_owner_stale_and_fresh_nonterminal_evidence(self):
        self.client.force_login(self.owner)
        c, e = self.resolved(True)
        other, _ = self.resolved()
        with patch("schemes.refunded_orders.get_payment_gateway", return_value=order_gateway(c.gateway_order_id, f"pay_{c.pk}")):
            page = self.client.post(self.order_url(c), dict(action="INSPECT", reason="Review all attempts"))
        values = self.values(page)
        with patch("schemes.refunded_orders.get_payment_gateway") as gateway:
            for url, data in [(self.order_url(other), values), (self.order_url(c), values | {"confirmed": ""}),
                              (self.order_url(c), values | {"review_token": "bad"})]:
                self.assertEqual(self.client.post(url, data).status_code, 200)
            self.client.force_login(make_owner("different@example.invalid"))
            self.assertEqual(self.client.post(self.order_url(c), values).status_code, 200)
            self.client.force_login(self.owner)
            with patch("django.utils.timezone.now", return_value=NOW + timedelta(minutes=11)):
                self.assertEqual(self.client.post(self.order_url(c), values).status_code, 200)
            gateway.assert_not_called()
        with patch("schemes.refunded_orders.get_payment_gateway", return_value=order_gateway(c.gateway_order_id,
                f"pay_{c.pk}", order_changes={"attempts": 2})):
            page = self.client.post(self.order_url(c), values)
        self.assertContains(page, "order remains held")
        self.assertIsNone(page.context["comparison"])
        self.assertFalse(RefundedPaymentOrderClosure.objects.exists())
        self.assertEqual(Contribution.objects.get(pk=c.pk).status, "PENDING")

    def test_credited_payment_and_test_mode_have_no_refund_clearance_path(self):
        self.client.force_login(self.owner)
        c, captured_gateway, _, body = self.attempt()
        self.confirm(c, captured_gateway)
        e = self.event(c, body)
        page = self.inspect(c, e)
        self.assertFalse(page.context["can_resolve"])
        self.assertContains(page, "separate reconciliation")
        self.assertFalse(self.client.get(self.order_url(c)).context["can_inspect_order"])
        from schemes.models import PaymentWebhookEvent
        PaymentWebhookEvent.objects.filter(pk=e.pk).update(gateway_mode="test")
        self.assertEqual(self.client.get(self.url(e)).status_code, 404)
        self.assertEqual(InrPrincipalReceipt.objects.filter(contribution=c).count(), 1)
