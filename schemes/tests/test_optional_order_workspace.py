"""Owner recovery uses real durable intents; only readiness/provider I/O are simulated."""
import uuid
from dataclasses import replace
from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.core.management import call_command, CommandError
from django.test import Client, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.db import connection
from django.urls import reverse

from accounts.models import CustomUser
from schemes.models import Contribution, OptionalPaymentOrderBinding, InrPrincipalReceipt, MetalAllocation
from schemes.payments import PaymentGatewayError
from schemes.selectors import get_owner_exception_keys, get_owner_exception_queue, get_financial_exception_counts
from schemes.tests import test_optional_orders as optional
from schemes.tests.test_independent_instalment_ledger import NOW


@override_settings(IN_STORE_CASH_CONTRIBUTIONS_ENABLED=True, PAYMENT_INITIATION_KILL_SWITCH=False)
class OptionalOrderWorkspaceTests(TestCase):
    setUp = optional.OptionalOrderTests.setUp
    account = optional.OptionalOrderTests.account
    gateway = optional.OptionalOrderTests.gateway
    pay = optional.OptionalOrderTests.pay
    lost = optional.OptionalOrderTests.lost
    recover = optional.OptionalOrderTests.recover

    def values(self):
        return dict(order_id="order_recovered", reason="Investigated original request",
            evidence_reference="provider-support-case", idempotency_key=str(uuid.uuid4()))

    def url(self, contribution):
        return reverse("schemes:optional_order_recovery", args=[contribution.pk])

    def assert_no_credit(self):
        self.assertFalse(InrPrincipalReceipt.objects.exists())
        self.assertFalse(MetalAllocation.objects.exists())

    def test_private_read_only_access_csrf_and_accessible_form(self):
        account, gateway, c, _ = self.lost()
        url = self.url(c)
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.customer.user)
        self.assertEqual(self.client.get(url).status_code, 403)
        CustomUser.objects.filter(pk=self.customer.user_id).update(role="STAFF", is_staff=True)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_login(self.owner)
        with patch("schemes.optional_orders.get_payment_gateway") as provider, CaptureQueriesContext(connection) as queries:
            response = self.client.get(url)
        provider.assert_not_called()
        self.assertFalse(any(q["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")) for q in queries))
        self.assertContains(response, f"opt_{c.optional_order_request.request_token.hex}")
        self.assertContains(response, 'id="id_order_id_helptext"')
        self.assertContains(response, 'aria-describedby="id_order_id_helptext"')
        self.assertIn("no-store", response.headers["Cache-Control"])
        self.assertIn("Cookie", response.headers["Vary"])
        secure = Client(enforce_csrf_checks=True)
        secure.force_login(self.owner)
        self.assertEqual(secure.post(url, self.values()).status_code, 403)
        self.assertEqual(self.client.put(url).status_code, 405)
        self.assertFalse(OptionalPaymentOrderBinding.objects.exists())
        self.assert_no_credit()

    def test_queue_exposes_uncertainty_before_expiry_and_failed_without_duplicates(self):
        _, _, c, _ = self.lost()
        self.client.force_login(self.owner)
        keys = list(get_owner_exception_keys(category="optional_order"))
        self.assertEqual([(k["queue_kind"], k["pk"]) for k in keys], [("optional_order", c.pk)])
        self.assertEqual(get_owner_exception_queue(keys=keys)[0].contribution.pk, c.pk)
        page = self.client.get(reverse("schemes:exception_queue"), {"category": "optional_order"})
        self.assertContains(page, self.url(c))
        self.assertNotContains(page, "Verified payment awaiting allocation")
        with patch("django.utils.timezone.now", return_value=NOW + timedelta(hours=1)):
            all_keys = list(get_owner_exception_keys())
            self.assertEqual(len(all_keys), 1)
            self.assertEqual(all_keys[0]["queue_kind"], "optional_order")
            self.assertEqual(list(get_owner_exception_keys(category="checkout")), [])
            counts = get_financial_exception_counts()
            self.assertEqual((counts.total, counts.unresolved_optional_orders, counts.expired_checkouts), (1, 1, 0))
        output = StringIO()
        with self.assertRaises(CommandError):
            call_command("check_financial_exceptions", stdout=output)
        self.assertIn("unresolved_optional_orders=1", output.getvalue())
        Contribution.objects.filter(pk=c.pk).update(status="FAILED")
        self.assertEqual(get_owner_exception_keys(category="optional_order").count(), 1)

    def test_exact_recovery_retry_both_units_preserves_deadline_and_has_followup(self):
        self.client.force_login(self.owner)
        for metal in (False, True):
            with self.subTest(metal=metal):
                _, gateway, c, identity = self.lost(metal=metal)
                # Each provider identity is unique, as in the merchant account.
                identity = replace(identity, order_id=f"order_recovered_{c.pk}")
                gateway.inspect_order_identity.return_value = identity
                before = (c.checkout_expires_at, c.scheme_rate_id, c.rate_locked_at)
                values = self.values() | {"order_id": identity.order_id}
                with patch("django.utils.timezone.now", return_value=NOW + timedelta(hours=1)), patch(
                        "schemes.optional_orders.get_payment_gateway", return_value=gateway):
                    response = self.client.post(self.url(c), values)
                    self.assertRedirects(response, self.url(c))
                    self.assertEqual(self.client.post(self.url(c), values).status_code, 302)
                    page = self.client.get(self.url(c))
                self.assertContains(page, "Retained order identity")
                self.assertContains(page, reverse("schemes:order_reconciliation", args=[c.pk]))
                self.assertNotContains(page, '<form method="post"')
                self.assertEqual(gateway.inspect_order_identity.call_count, 1)
                self.assertEqual(gateway.create_order.call_count, 1)
                c.refresh_from_db()
                self.assertEqual(c.gateway_order_id, identity.order_id)
                self.assertEqual((c.checkout_expires_at, c.scheme_rate_id, c.rate_locked_at), before)
                self.assertEqual(c.status, "PENDING")
                self.assertFalse(get_owner_exception_keys(category="optional_order").filter(pk=c.pk).exists())
                self.assert_no_credit()
                from schemes.independent_payment_selectors import resumable_optional_contribution
                with self.assertRaises(ValidationError):
                    resumable_optional_contribution(c.scheme_account)

    def test_mismatch_provider_failure_and_invalid_form_keep_request_unbound(self):
        _, gateway, c, identity = self.lost()
        self.client.force_login(self.owner)
        with patch("schemes.optional_orders.get_payment_gateway", return_value=gateway):
            response = self.client.post(self.url(c), self.values() | {"order_id": "invalid"})
            self.assertEqual(response.status_code, 200)
            gateway.inspect_order_identity.assert_not_called()
            gateway.inspect_order_identity.return_value = replace(identity, receipt="different-request")
            response = self.client.post(self.url(c), self.values())
            self.assertContains(response, "does not match")
            gateway.inspect_order_identity.side_effect = PaymentGatewayError("PRIVATE-provider-payload")
            response = self.client.post(self.url(c), self.values())
            self.assertContains(response, "verification is unavailable")
            self.assertNotContains(response, "PRIVATE-provider-payload")
        c.refresh_from_db()
        self.assertFalse(c.gateway_order_id)
        self.assertFalse(OptionalPaymentOrderBinding.objects.exists())
        self.assert_no_credit()

    def test_cross_request_or_changed_retry_cannot_bind(self):
        _, gateway, first, _ = self.lost()
        _, _, other, _ = self.lost()
        self.client.force_login(self.owner)
        values = self.values()
        with patch("schemes.optional_orders.get_payment_gateway", return_value=gateway):
            self.assertContains(self.client.post(self.url(other), values), "does not match")
            self.assertEqual(self.client.post(self.url(first), values).status_code, 302)
            self.assertContains(self.client.post(self.url(first), values | {"reason": "Changed"}), "different recovery")
        self.assertEqual(OptionalPaymentOrderBinding.objects.count(), 1)
        other.refresh_from_db()
        self.assertFalse(other.gateway_order_id)
        self.assert_no_credit()

    def test_persisted_owner_authority_rechecked_before_and_after_provider_io(self):
        _, gateway, c, identity = self.lost()
        CustomUser.objects.filter(pk=self.owner.pk).update(role="CUSTOMER")
        with self.assertRaises(ValidationError):
            self.recover(c, gateway)
        gateway.inspect_order_identity.assert_not_called()
        CustomUser.objects.filter(pk=self.owner.pk).update(role="OWNER")
        def revoke(**kwargs):
            CustomUser.objects.filter(pk=self.owner.pk).update(is_active=False)
            return identity
        gateway.inspect_order_identity.side_effect = revoke
        with self.assertRaises(ValidationError):
            self.recover(c, gateway)
        c.refresh_from_db()
        self.assertFalse(c.gateway_order_id)
        self.assertFalse(OptionalPaymentOrderBinding.objects.exists())
        self.assert_no_credit()
