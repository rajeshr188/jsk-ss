from decimal import Decimal
from datetime import timedelta
from unittest.mock import patch
import json
import re
import shutil
import subprocess
from unittest import skipUnless

from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from schemes.models import Contribution, PaymentOperationsControl
from schemes.services import confirm_razorpay_contribution, initiate_contribution
from schemes.tests import test_razorpay as razorpay_helpers
from schemes.tests.test_razorpay import RAZORPAY_SETTINGS, make_account


@override_settings(**RAZORPAY_SETTINGS)
class CustomerPaymentPresentationTests(TestCase):
    setUp = razorpay_helpers.RazorpayViewTests.setUp

    def attempt(self):
        contribution = initiate_contribution(scheme_account=self.account, amount=Decimal("5000"), payment_gateway="razorpay", gateway_mode="test")
        contribution.gateway_order_id = f"order_presentation_{contribution.pk}"
        contribution.save(update_fields=["gateway_order_id"])
        return contribution

    def test_dashboard_and_detail_hide_payment_during_pause(self):
        # A display restriction must not create an order or change the agreement.
        PaymentOperationsControl.objects.filter(pk=1).update(global_pause=True)
        for url in [reverse("schemes:my_schemes"), reverse("schemes:my_scheme_detail", args=[self.account.scheme_number])]:
            response = self.client.get(url)
            self.assertNotContains(response, ">Pay now<")
            self.assertContains(response, "temporarily paused")
        self.assertEqual(Contribution.objects.count(), 0)

    def test_dashboard_missing_rate_explains_next_action(self):
        # Unused test rates can be removed; no financial history references them.
        from schemes.models import SchemeRate
        SchemeRate.objects.all().delete()
        response = self.client.get(reverse("schemes:my_schemes"))
        self.assertNotContains(response, ">Pay now<")
        self.assertContains(response, "Rate has not been published")

    def test_monthly_paid_or_expired_pending_has_no_new_payment_action(self):
        contribution = self.attempt()
        Contribution.objects.filter(pk=contribution.pk).update(checkout_expires_at=timezone.now() - timedelta(minutes=1))
        response = self.client.get(reverse("schemes:my_schemes"))
        self.assertNotContains(response, ">Pay now<")
        self.assertContains(response, "awaiting provider reconciliation")
        with patch("schemes.payments.RazorpayPaymentGateway.verify_payment", return_value=True):
            confirm_razorpay_contribution(contribution_id=contribution.pk, callback_order_id=contribution.gateway_order_id, payment_id="pay_expired_presentation", signature="signed")
        response = self.client.get(reverse("schemes:my_schemes"))
        self.assertNotContains(response, ">Pay now<")
        self.assertContains(response, "calendar month has been received")

    def test_abandoned_is_never_labelled_pending_in_desktop_or_mobile_history(self):
        contribution = self.attempt()
        Contribution.objects.filter(pk=contribution.pk).update(status=Contribution.Status.ABANDONED)
        response = self.client.get(reverse("schemes:my_scheme_detail", args=[self.account.scheme_number]))
        self.assertContains(response, "Checkout closed after review", count=2)
        self.assertNotContains(response, ">Pending</span>")
        self.assertNotContains(response, "Resume payment")
        self.assertContains(response, reverse("schemes:payment_status", args=[contribution.pk]), count=2)
        response = self.client.get(reverse("schemes:payment_status", args=[contribution.pk]))
        self.assertContains(response, "This attempt has no recorded contribution credit.")
        self.assertNotContains(response, "View receipt")
        user_model = get_user_model()
        owner = user_model.objects.create_user(username="presentation-owner", email="presentation-owner@example.com", role=user_model.Role.OWNER)
        self.client.force_login(owner)
        response = self.client.get(reverse("schemes:contribution_list"))
        self.assertContains(response, "Checkout closed after review", count=1)
        self.assertNotContains(response, ">Pending</span>")

    def test_pending_status_is_read_only_private_and_customer_scoped(self):
        contribution = self.attempt()
        url = reverse("schemes:payment_status", args=[contribution.pk])
        response = self.client.get(url)
        self.assertContains(response, "Payment confirmation is pending")
        self.assertContains(response, "do not pay again")
        self.assertContains(response, "Refresh payment status")
        self.assertIn("no-store", response["Cache-Control"])
        contribution.refresh_from_db()
        self.assertEqual(contribution.status, Contribution.Status.PENDING)
        self.assertEqual(self.client.post(url).status_code, 405)
        other, _ = make_account(email="status-other@example.com", mode="GOLD")
        self.client.force_login(other.user)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.logout()
        self.assertEqual(self.client.get(url).status_code, 302)

    def test_status_uses_confirmed_record_even_without_browser_callback(self):
        contribution = self.attempt()
        with patch("schemes.payments.RazorpayPaymentGateway.verify_payment", return_value=True):
            confirm_razorpay_contribution(contribution_id=contribution.pk, callback_order_id=contribution.gateway_order_id, payment_id="pay_status_record", signature="signed")
        response = self.client.get(reverse("schemes:payment_status", args=[contribution.pk]), {"success": "false"})
        self.assertContains(response, "Payment received.")
        self.assertContains(response, "View receipt")
        self.assertNotContains(response, "confirmation is pending")

    def test_paid_unallocated_is_received_money_not_failure(self):
        contribution = self.attempt()
        with patch("schemes.payments.RazorpayPaymentGateway.verify_payment", return_value=True), patch("schemes.services.allocate_metal", side_effect=ValidationError("Synthetic allocation failure")):
            confirm_razorpay_contribution(contribution_id=contribution.pk, callback_order_id=contribution.gateway_order_id, payment_id="pay_status_unallocated", signature="signed")
        response = self.client.get(reverse("schemes:payment_status", args=[contribution.pk]))
        self.assertContains(response, "Payment received. Metal credit is pending.")
        self.assertContains(response, "Do not pay again")
        self.assertNotContains(response, "Synthetic allocation failure")

    @skipUnless(shutil.which("node"), "Node is needed for the checkout JavaScript behavior regression")
    def test_checkout_browser_failure_and_cancellation_continue_to_server_status(self):
        contribution = self.attempt()
        response = self.client.get(reverse("schemes:razorpay_checkout", args=[contribution.pk]))
        source = re.findall(r"<script>(.*?)</script>", response.content.decode(), re.S)[-1]
        status_url = reverse("schemes:payment_status", args=[contribution.pk])
        harness = r'''
const vm = require('node:vm');
const assert = require('node:assert/strict');
const source = SOURCE;
async function scenario(kind) {
  let options, timer, click, failed;
  const destinations = [];
  const fields = {};
  const button = {disabled: false, addEventListener: (_, handler) => click = handler};
  const form = {action: '/confirm/'};
  const status = {};
  const context = {
    Date, Math,
    document: {getElementById: id => id === 'open-checkout' ? button : id === 'verification-form' ? form : id === 'checkout-status' ? status : (fields[id] ||= {})},
    window: {setTimeout: fn => timer = fn, location: {assign: url => destinations.push(url)}},
    FormData: class {},
    fetch: async () => {
      if (kind === 'network') throw Error('Response lost after capture');
      return {ok: false, json: async () => ({success: false})};
    },
    Razorpay: class {constructor(config) {options = config;} on(_, handler) {failed = handler;} open() {}},
  };
  vm.runInNewContext(source, context);
  click();
  if (kind === 'cancel') options.modal.ondismiss();
  else if (kind === 'provider') failed({error: {description: 'untrusted provider text'}});
  else if (kind === 'expiry') timer();
  else await options.handler({razorpay_payment_id: 'fake', razorpay_order_id: 'fake', razorpay_signature: 'fake'});
  assert.equal(button.disabled, true);
  if (kind === 'expiry') {
    assert.match(status.textContent, /Check recorded payment status/);
    assert.doesNotMatch(status.textContent, /No payment was credited/);
  } else assert.equal(destinations.at(-1), STATUS_URL);
}
(async () => {for (const kind of ['network', 'rejected', 'cancel', 'provider', 'expiry']) await scenario(kind);})().catch(error => {console.error(error); process.exit(1);});
'''.replace("SOURCE", json.dumps(source)).replace("STATUS_URL", json.dumps(status_url))
        result = subprocess.run([shutil.which("node"), "-"], input=harness, text=True, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
