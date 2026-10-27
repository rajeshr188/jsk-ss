"""Operator comparison and confirmation over real recovery services; no live I/O."""
from datetime import timedelta
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import connection
from django.test import Client, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from accounts.models import CustomUser
from schemes.models import Contribution, InrPrincipalReceipt, InrPaymentCaptureEvidence, MetalAllocation, PaymentWebhookEvent
from schemes.payments import PaymentGatewayError
from schemes.services import reconcile_razorpay_webhook
from schemes.tests.test_inr_api_payments import ApiHelpers
from schemes.tests.test_independent_instalment_ledger import NOW
from schemes.tests.test_audit_exceptions import make_owner
from schemes.tests import test_razorpay as legacy


class ReviewHelpers:
    def url(self, event):
        return reverse("schemes:webhook_recovery", args=[event.pk])

    def inspect(self, event, gateway):
        with patch("schemes.services.get_payment_gateway", return_value=gateway):
            response = self.client.post(self.url(event), {"action": "INSPECT", "reason": "Compare exact original capture"})
        self.assertRedirects(response, self.url(event))
        return self.client.get(self.url(event))

    def apply_values(self, response):
        return dict(action="APPLY", reason="Reviewed exact original capture",
            review_token=response.context["form"]["review_token"].value(), confirmed="on")


@override_settings(PAYMENT_INITIATION_KILL_SWITCH=False)
class CaptureWorkspaceTests(ReviewHelpers, ApiHelpers, TestCase):
    def test_optional_and_required_inr_comparison_apply_and_repeat_never_double_credit(self):
        self.client.force_login(self.owner)
        for monthly in (False, True):
            with self.subTest(monthly=monthly):
                c, gateway, _, body = self.attempt(monthly)
                event = self.event(c, body)
                before = (c.scheme_rate_id, c.checkout_expires_at)
                with CaptureQueriesContext(connection) as queries:
                    page = self.client.get(self.url(event))
                gateway._request_json.assert_not_called()
                self.assertFalse(any(q["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")) for q in queries))
                self.assertIn("no-store", page.headers["Cache-Control"])
                self.assertIn("Cookie", page.headers["Vary"])
                page = self.inspect(event, gateway)
                self.assertContains(page, "Latest provider comparison")
                self.assertContains(page, "500.00")
                self.assertContains(page, "purchase-credit principal only")
                self.assertContains(page, 'id="id_reason_helptext"')
                self.assertTrue(page.context["can_apply_recovery"])
                self.assertFalse(InrPrincipalReceipt.objects.filter(contribution=c).exists())
                values = self.apply_values(page)
                with patch("schemes.services.get_payment_gateway", return_value=gateway):
                    refused = self.client.post(self.url(event), values | {"confirmed": ""})
                    self.assertContains(refused, "confirm before applying")
                    self.assertEqual(gateway._request_json.call_count, 1)
                    self.assertEqual(self.client.post(self.url(event), values).status_code, 302)
                    self.assertEqual(self.client.post(self.url(event), values).status_code, 200)
                self.assertEqual(InrPrincipalReceipt.objects.filter(contribution=c).count(), 1)
                self.assertEqual(InrPaymentCaptureEvidence.objects.filter(contribution=c).count(), 1)
                self.assertFalse(MetalAllocation.objects.exists())
                c.refresh_from_db()
                self.assertEqual((c.scheme_rate_id, c.checkout_expires_at), before)
                if monthly:
                    self.assertEqual(c.instalment_reservation.state, "AWAITING")

    def test_token_requires_same_owner_event_fresh_inspection_and_unchanged_local_state(self):
        c, gateway, _, body = self.attempt()
        event = self.event(c, body)
        self.client.force_login(self.owner)
        values = self.apply_values(self.inspect(event, gateway))
        other_event = self.event(c, body)
        other_owner = make_owner("other-review@example.com")
        with patch("schemes.services.get_payment_gateway", return_value=gateway):
            for token in ("", values["review_token"] + "tampered"):
                self.assertEqual(self.client.post(self.url(event), values | {"review_token": token}).status_code, 200)
            self.assertEqual(self.client.post(self.url(other_event), values).status_code, 200)
            self.client.force_login(other_owner)
            self.assertEqual(self.client.post(self.url(event), values).status_code, 200)
            self.client.force_login(self.owner)
            with patch("django.utils.timezone.now", return_value=NOW + timedelta(minutes=11)):
                self.assertFalse(self.client.get(self.url(event)).context["can_apply_recovery"])
                self.assertEqual(self.client.post(self.url(event), values).status_code, 200)
            Contribution.objects.filter(pk=c.pk).update(status="FAILED")
            self.assertFalse(self.client.get(self.url(event)).context["can_apply_recovery"])
            self.assertEqual(self.client.post(self.url(event), values).status_code, 200)
        self.assertEqual(gateway._request_json.call_count, 1)
        self.assertFalse(InrPrincipalReceipt.objects.exists())

    def test_new_mismatch_or_provider_failure_invalidates_old_success(self):
        c, gateway, _, body = self.attempt()
        event = self.event(c, body)
        self.client.force_login(self.owner)
        values = self.apply_values(self.inspect(event, gateway))
        gateway._request_json.return_value["amount"] = 50001
        page = self.inspect(event, gateway)
        self.assertFalse(page.context["can_apply_recovery"])
        self.assertContains(page, "500.01")
        with patch("schemes.services.get_payment_gateway", return_value=gateway):
            self.assertEqual(self.client.post(self.url(event), values).status_code, 200)
        self.assertEqual(gateway._request_json.call_count, 2)
        gateway._request_json.side_effect = PaymentGatewayError("PRIVATE-provider-payload")
        with patch("schemes.services.get_payment_gateway", return_value=gateway):
            page = self.client.post(self.url(event), {"action": "INSPECT", "reason": "Retry provider"})
        self.assertContains(page, "comparison is unavailable")
        self.assertNotContains(page, "PRIVATE-provider-payload")
        self.assertFalse(page.context["can_apply_recovery"])
        self.assertNotIn("PRIVATE-provider-payload", event.processing_attempts.first().detail)
        self.assertFalse(InrPrincipalReceipt.objects.exists())

    def test_apply_refetches_provider_and_keeps_refund_case_unresolved(self):
        c, gateway, _, body = self.attempt()
        event = self.event(c, body)
        self.client.force_login(self.owner)
        values = self.apply_values(self.inspect(event, gateway))
        gateway._request_json.return_value["captured"] = False
        with patch("schemes.services.get_payment_gateway", return_value=gateway):
            self.assertEqual(self.client.post(self.url(event), values).status_code, 302)
        self.assertEqual(gateway._request_json.call_count, 2)
        self.assertFalse(self.client.get(self.url(event)).context["can_apply_recovery"])
        c.refresh_from_db()
        event.refresh_from_db()
        self.assertEqual((c.status, event.status), ("PENDING", "RECEIVED"))
        self.assertFalse(InrPrincipalReceipt.objects.exists())

    def test_owner_authority_is_reloaded_before_io_and_before_credit(self):
        c, gateway, payload, body = self.attempt()
        event = self.event(c, body)
        self.recover(event, gateway)
        CustomUser.objects.filter(pk=self.owner.pk).update(role="CUSTOMER")
        with self.assertRaises(ValidationError):
            self.recover(event, gateway, apply=True)
        self.assertEqual(gateway._request_json.call_count, 1)
        CustomUser.objects.filter(pk=self.owner.pk).update(role="OWNER")
        def revoke(*args):
            CustomUser.objects.filter(pk=self.owner.pk).update(is_active=False)
            return payload["payload"]["payment"]["entity"]
        gateway._request_json.side_effect = revoke
        with self.assertRaises(ValidationError):
            self.recover(event, gateway, apply=True)
        self.assertFalse(InrPrincipalReceipt.objects.exists())
        self.assertFalse(InrPaymentCaptureEvidence.objects.exists())

    def test_customer_csrf_and_unsafe_methods_are_rejected(self):
        c, _, _, body = self.attempt()
        event = self.event(c, body)
        self.assertEqual(self.client.get(self.url(event)).status_code, 302)
        self.client.force_login(self.customer.user)
        self.assertEqual(self.client.get(self.url(event)).status_code, 403)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.put(self.url(event)).status_code, 405)
        secure = Client(enforce_csrf_checks=True)
        secure.force_login(self.owner)
        self.assertEqual(secure.post(self.url(event), {"action": "INSPECT"}).status_code, 403)
        self.assertFalse(event.processing_attempts.exists())


@override_settings(**legacy.RAZORPAY_SETTINGS)
class MetalCaptureWorkspaceTests(ReviewHelpers, TestCase):
    setUp = legacy.RazorpayWebhookRecoveryTests.setUp
    create_review_event = legacy.RazorpayWebhookRecoveryTests.create_review_event
    recovery_gateway = legacy.RazorpayWebhookRecoveryTests.recovery_gateway

    def test_metal_recovery_uses_original_lock_and_crosslinked_event_is_held(self):
        event = self.create_review_event()
        gateway = self.recovery_gateway()
        self.client.force_login(self.owner)
        values = self.apply_values(self.inspect(event, gateway))
        before = self.contribution.scheme_rate_id
        with patch("schemes.services.get_payment_gateway", return_value=gateway):
            self.assertEqual(self.client.post(self.url(event), values).status_code, 302)
        self.assertEqual(MetalAllocation.objects.get().scheme_rate_id, before)
        self.assertFalse(InrPrincipalReceipt.objects.exists())
        # Damaged event linkage must be held for metal as well as INR.
        other = Contribution.objects.create(scheme_account=self.account, amount="5000.00",
            contribution_period=self.contribution.contribution_period, frequency_rule_snapshot="FLEXIBLE",
            payment_gateway="razorpay", gateway_mode="test", status="FAILED")
        PaymentWebhookEvent.objects.filter(pk=event.pk).update(contribution=other)
        result = reconcile_razorpay_webhook(webhook_event_id=event.pk, gateway=gateway,
            performed_by=self.owner, reason="Investigate cross-linked event")
        self.assertEqual(result.outcome, "MANUAL_REVIEW_REQUIRED")
        self.assertEqual(MetalAllocation.objects.count(), 1)
