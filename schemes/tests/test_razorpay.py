import hashlib
import hmac
import json
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch
from urllib.error import HTTPError

from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from schemes.models import (
    Contribution,
    MetalAllocation,
    PaymentWebhookEvent,
    SchemeAccount,
    SchemePlan,
    SchemeRate,
)
from schemes.payments import (
    PaymentGatewayAuthenticationError,
    PaymentGatewayError,
    PaymentGatewayValidationError,
    PaymentOrder,
    RazorpayPaymentGateway,
)
from schemes.selectors import get_cash_balance
from schemes.services import (
    confirm_razorpay_contribution,
    create_customer,
    enroll_customer,
    initiate_contribution,
    initiate_razorpay_contribution,
    process_razorpay_webhook,
    publish_scheme_rate,
)


RAZORPAY_SETTINGS = {
    "DEBUG": False,
    "PAYMENT_GATEWAY": "razorpay",
    "RAZORPAY_KEY_ID": "rzp_test_public_key",
    "RAZORPAY_KEY_SECRET": "test-key-secret",
    "RAZORPAY_WEBHOOK_SECRET": "test-webhook-secret",
    "RAZORPAY_TIMEOUT_SECONDS": "2",
}


class FakeResponse:
    def __init__(self, payload):
        self.body = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self, _limit):
        return self.body


class FakeRazorpayGateway:
    name = "razorpay"

    def __init__(self, *, verified=True):
        self.verified = verified
        self.order_calls = 0
        self.verify_calls = 0

    def create_order(self, contribution):
        self.order_calls += 1
        return PaymentOrder(
            order_id=f"order_test_{contribution.pk}",
            amount_subunits=int(contribution.amount * 100),
            currency="INR",
        )

    def verify_payment(self, **_kwargs):
        self.verify_calls += 1
        return self.verified


def make_account(*, email, mode=SchemeAccount.SavingsMode.CASH, frequency=None):
    customer = create_customer(
        full_name=email.split("@")[0].title(),
        email=email,
        mobile_number="9000000099",
        password="customer-password-strong",
    )
    frequency = frequency or SchemePlan.FrequencyRule.ONCE_PER_MONTH
    plan = SchemePlan.objects.create(
        name=f"Razorpay {email}",
        code=f"RZP-{customer.pk}",
        amount_rule=SchemePlan.AmountRule.FIXED,
        frequency_rule=frequency,
        fixed_contribution_amount=Decimal("5000.00"),
        minimum_contribution=Decimal("5000.00"),
        maximum_contribution=Decimal("5000.00"),
    )
    account = enroll_customer(
        customer=customer,
        plan=plan,
        savings_mode=mode,
        start_date=timezone.localdate(),
    )
    return customer, account


class RazorpayGatewayTests(TestCase):
    def test_live_key_is_rejected_during_test_mode_milestone(self):
        with self.assertRaises(ImproperlyConfigured):
            RazorpayPaymentGateway(
                key_id="rzp_live_forbidden",
                key_secret="secret",
                webhook_secret="webhook",
                timeout_seconds=2,
            )

    def test_create_order_uses_authenticated_fixed_https_api(self):
        gateway = RazorpayPaymentGateway(
            key_id="rzp_test_key",
            key_secret="secret",
            webhook_secret="webhook",
            timeout_seconds=2,
        )
        contribution = SimpleNamespace(pk=42, amount=Decimal("5000.00"))
        response = FakeResponse(
            {"id": "order_created_42", "amount": 500000, "currency": "INR"}
        )
        with patch("schemes.payments.urlopen", return_value=response) as urlopen_mock:
            order = gateway.create_order(contribution)

        request = urlopen_mock.call_args.args[0]
        self.assertEqual(request.full_url, "https://api.razorpay.com/v1/orders")
        self.assertEqual(request.get_method(), "POST")
        self.assertTrue(request.get_header("Authorization").startswith("Basic "))
        self.assertNotIn("secret", request.full_url)
        self.assertEqual(order.amount_subunits, 500000)

    def test_create_order_rejects_less_than_one_rupee_without_network_call(self):
        gateway = RazorpayPaymentGateway(
            key_id="rzp_test_key",
            key_secret="secret",
            webhook_secret="webhook",
            timeout_seconds=2,
        )
        contribution = SimpleNamespace(pk=42, amount=Decimal("0.99"))
        with patch("schemes.payments.urlopen") as urlopen_mock:
            with self.assertRaises(PaymentGatewayValidationError):
                gateway.create_order(contribution)
        urlopen_mock.assert_not_called()

    def test_provider_authentication_failure_is_safely_classified(self):
        gateway = RazorpayPaymentGateway(
            key_id="rzp_test_key",
            key_secret="secret",
            webhook_secret="webhook",
            timeout_seconds=2,
        )
        contribution = SimpleNamespace(pk=42, amount=Decimal("5000.00"))
        failure = HTTPError(
            "https://api.razorpay.com/v1/orders",
            401,
            "Unauthorized",
            hdrs=None,
            fp=None,
        )
        with patch("schemes.payments.urlopen", side_effect=failure):
            with self.assertRaises(PaymentGatewayAuthenticationError) as raised:
                gateway.create_order(contribution)
        self.assertNotIn("secret", str(raised.exception))
        self.assertEqual(raised.exception.status_code, 401)

    def test_callback_signature_and_captured_payment_are_both_verified(self):
        gateway = RazorpayPaymentGateway(
            key_id="rzp_test_key",
            key_secret="secret",
            webhook_secret="webhook",
            timeout_seconds=2,
        )
        signature = hmac.new(
            b"secret", b"order_local|pay_test_1", hashlib.sha256
        ).hexdigest()
        response = FakeResponse(
            {
                "id": "pay_test_1",
                "order_id": "order_local",
                "amount": 500000,
                "currency": "INR",
                "status": "captured",
                "captured": True,
            }
        )
        with patch("schemes.payments.urlopen", return_value=response):
            verified = gateway.verify_payment(
                order_id="order_local",
                payment_id="pay_test_1",
                signature=signature,
                expected_amount=Decimal("5000.00"),
            )
        self.assertTrue(verified)

    def test_invalid_callback_signature_does_not_call_provider(self):
        gateway = RazorpayPaymentGateway(
            key_id="rzp_test_key",
            key_secret="secret",
            webhook_secret="webhook",
            timeout_seconds=2,
        )
        with patch("schemes.payments.urlopen") as urlopen_mock:
            verified = gateway.verify_payment(
                order_id="order_local",
                payment_id="pay_test_1",
                signature="invalid",
                expected_amount=Decimal("5000.00"),
            )
        self.assertFalse(verified)
        urlopen_mock.assert_not_called()

    def test_webhook_signature_uses_unmodified_raw_body(self):
        gateway = RazorpayPaymentGateway(
            key_id="rzp_test_key",
            key_secret="secret",
            webhook_secret="webhook",
            timeout_seconds=2,
        )
        body = b'{"event":"payment.captured"}'
        signature = hmac.new(b"webhook", body, hashlib.sha256).hexdigest()
        self.assertTrue(gateway.verify_webhook(body=body, signature=signature))
        self.assertFalse(
            gateway.verify_webhook(body=body + b" ", signature=signature)
        )


@override_settings(DEBUG=True)
class RazorpayServiceTests(TestCase):
    def test_monthly_pending_order_is_reused(self):
        _, account = make_account(email="pending@example.com")
        gateway = FakeRazorpayGateway()
        first = initiate_razorpay_contribution(
            scheme_account=account, amount=Decimal("5000.00"), gateway=gateway
        )
        second = initiate_razorpay_contribution(
            scheme_account=account, amount=Decimal("5000.00"), gateway=gateway
        )
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(gateway.order_calls, 1)
        self.assertEqual(Contribution.objects.count(), 1)

    def test_invalid_server_verification_creates_no_entitlement(self):
        _, account = make_account(email="invalid@example.com")
        gateway = FakeRazorpayGateway(verified=False)
        contribution = initiate_razorpay_contribution(
            scheme_account=account, amount=Decimal("5000.00"), gateway=gateway
        )
        with self.assertRaises(ValidationError):
            confirm_razorpay_contribution(
                contribution_id=contribution.pk,
                callback_order_id=contribution.gateway_order_id,
                payment_id="pay_invalid",
                signature="invalid",
                gateway=gateway,
            )
        contribution.refresh_from_db()
        self.assertEqual(contribution.status, Contribution.Status.PENDING)
        self.assertEqual(get_cash_balance(account), Decimal("0.00"))

    def test_duplicate_callback_benefits_cash_account_once(self):
        _, account = make_account(email="callback@example.com")
        gateway = FakeRazorpayGateway()
        contribution = initiate_razorpay_contribution(
            scheme_account=account, amount=Decimal("5000.00"), gateway=gateway
        )
        for _ in range(2):
            confirmed = confirm_razorpay_contribution(
                contribution_id=contribution.pk,
                callback_order_id=contribution.gateway_order_id,
                payment_id="pay_callback_once",
                signature="verified-signature",
                gateway=gateway,
            )
        self.assertEqual(confirmed.status, Contribution.Status.PAID)
        self.assertEqual(gateway.verify_calls, 1)
        self.assertEqual(get_cash_balance(account), Decimal("5000.00"))

    def test_validated_order_settles_after_eligibility_boundary(self):
        _, account = make_account(email="delayed-callback@example.com")
        gateway = FakeRazorpayGateway()
        contribution = initiate_razorpay_contribution(
            scheme_account=account, amount=Decimal("5000.00"), gateway=gateway
        )
        account.eligible_from = timezone.localdate()
        account.save(update_fields=["eligible_from"])
        confirmed = confirm_razorpay_contribution(
            contribution_id=contribution.pk,
            callback_order_id=contribution.gateway_order_id,
            payment_id="pay_delayed_callback",
            signature="verified-signature",
            gateway=gateway,
        )
        self.assertEqual(confirmed.status, Contribution.Status.PAID)
        self.assertEqual(get_cash_balance(account), Decimal("5000.00"))

    def test_duplicate_webhook_creates_one_metal_allocation(self):
        owner = get_user_model().objects.create_user(
            username="webhook-rate-owner@example.com",
            email="webhook-rate-owner@example.com",
            password="owner-password-strong",
            role=get_user_model().Role.OWNER,
        )
        publish_scheme_rate(
            metal=SchemeRate.Metal.GOLD,
            rate_per_gram=Decimal("12500.0000"),
            published_by=owner,
        )
        _, account = make_account(
            email="webhook-metal@example.com",
            mode=SchemeAccount.SavingsMode.GOLD,
        )
        contribution = initiate_contribution(
            scheme_account=account,
            amount=Decimal("5000.00"),
            payment_gateway="razorpay",
        )
        contribution.gateway_order_id = "order_webhook_gold"
        contribution.save(update_fields=["gateway_order_id"])
        payload = {
            "event": "payment.captured",
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_webhook_gold",
                        "order_id": "order_webhook_gold",
                        "amount": 500000,
                        "currency": "INR",
                        "status": "captured",
                        "captured": True,
                    }
                }
            },
        }
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        for _ in range(2):
            process_razorpay_webhook(
                event_id="event_gold_once", body=body, payload=payload
            )
        contribution.refresh_from_db()
        self.assertEqual(contribution.status, Contribution.Status.PAID)
        self.assertEqual(MetalAllocation.objects.count(), 1)
        self.assertEqual(PaymentWebhookEvent.objects.count(), 1)
        self.assertEqual(
            contribution.metal_allocation.quantity, Decimal("0.400000")
        )

    def test_no_gold_rate_prevents_razorpay_order_creation(self):
        _, account = make_account(
            email="no-rate-order@example.com",
            mode=SchemeAccount.SavingsMode.GOLD,
        )
        gateway = FakeRazorpayGateway()

        with self.assertRaisesMessage(ValidationError, "has not been published"):
            initiate_razorpay_contribution(
                scheme_account=account,
                amount=Decimal("5000.00"),
                gateway=gateway,
            )

        self.assertEqual(gateway.order_calls, 0)
        self.assertFalse(Contribution.objects.filter(scheme_account=account).exists())


@override_settings(**RAZORPAY_SETTINGS)
class RazorpayViewTests(TestCase):
    def setUp(self):
        self.customer, self.account = make_account(email="view-rzp@example.com")
        self.client.force_login(self.customer.user)

    def test_customer_creates_order_and_sees_checkout(self):
        order = PaymentOrder("order_view", 500000, "INR")
        with patch(
            "schemes.payments.RazorpayPaymentGateway.create_order", return_value=order
        ):
            response = self.client.post(
                reverse("schemes:pay_contribution", args=[self.account.scheme_number]),
                {"amount": "5000.00"},
                follow=True,
            )
        self.assertContains(response, "Razorpay test checkout")
        self.assertContains(response, "rzp_test_public_key")
        self.assertContains(response, 'checkout.on("payment.failed"', html=False)
        self.assertContains(response, "Checkout was cancelled", html=False)
        self.assertEqual(Contribution.objects.get().gateway_order_id, "order_view")

    def test_order_authentication_failure_returns_401_and_no_entitlement(self):
        with patch(
            "schemes.payments.RazorpayPaymentGateway.create_order",
            side_effect=PaymentGatewayAuthenticationError(
                "Razorpay authentication failed."
            ),
        ):
            response = self.client.post(
                reverse("schemes:pay_contribution", args=[self.account.scheme_number]),
                {"amount": "5000.00"},
            )
        self.assertEqual(response.status_code, 401)
        self.assertContains(
            response,
            "Razorpay authentication failed.",
            status_code=401,
        )
        contribution = Contribution.objects.get()
        self.assertEqual(contribution.status, Contribution.Status.FAILED)
        self.assertEqual(get_cash_balance(self.account), Decimal("0.00"))

    def test_order_provider_failure_returns_500_and_no_entitlement(self):
        with patch(
            "schemes.payments.RazorpayPaymentGateway.create_order",
            side_effect=PaymentGatewayError("Razorpay could not be reached."),
        ):
            response = self.client.post(
                reverse("schemes:pay_contribution", args=[self.account.scheme_number]),
                {"amount": "5000.00"},
            )
        self.assertEqual(response.status_code, 500)
        self.assertEqual(Contribution.objects.get().status, Contribution.Status.FAILED)
        self.assertEqual(get_cash_balance(self.account), Decimal("0.00"))

    def test_customer_cannot_open_another_customers_checkout(self):
        other_customer, other_account = make_account(email="other-rzp@example.com")
        contribution = initiate_contribution(
            scheme_account=other_account,
            amount=Decimal("5000.00"),
            payment_gateway="razorpay",
        )
        contribution.gateway_order_id = "order_other"
        contribution.save(update_fields=["gateway_order_id"])
        response = self.client.get(
            reverse("schemes:razorpay_checkout", args=[contribution.pk])
        )
        self.assertEqual(response.status_code, 404)
        self.assertNotEqual(other_customer.pk, self.customer.pk)

    def test_verified_callback_marks_contribution_paid(self):
        contribution = initiate_contribution(
            scheme_account=self.account,
            amount=Decimal("5000.00"),
            payment_gateway="razorpay",
        )
        contribution.gateway_order_id = "order_callback_view"
        contribution.save(update_fields=["gateway_order_id"])
        with patch(
            "schemes.payments.RazorpayPaymentGateway.verify_payment",
            return_value=True,
        ):
            response = self.client.post(
                reverse("schemes:razorpay_confirm", args=[contribution.pk]),
                {
                    "razorpay_order_id": "order_callback_view",
                    "razorpay_payment_id": "pay_callback_view",
                    "razorpay_signature": "signed",
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        detail = self.client.get(response.json()["redirect_url"])
        self.assertContains(detail, "verified successfully")
        contribution.refresh_from_db()
        self.assertEqual(contribution.status, Contribution.Status.PAID)
        self.assertEqual(get_cash_balance(self.account), Decimal("5000.00"))

    def test_missing_verification_fields_return_400_and_no_entitlement(self):
        contribution = initiate_contribution(
            scheme_account=self.account,
            amount=Decimal("5000.00"),
            payment_gateway="razorpay",
        )
        contribution.gateway_order_id = "order_missing_fields"
        contribution.save(update_fields=["gateway_order_id"])
        response = self.client.post(
            reverse("schemes:razorpay_confirm", args=[contribution.pk]),
            {"razorpay_order_id": "order_missing_fields"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["success"])
        contribution.refresh_from_db()
        self.assertEqual(contribution.status, Contribution.Status.PENDING)
        self.assertEqual(get_cash_balance(self.account), Decimal("0.00"))

    def test_signature_mismatch_returns_400_and_no_entitlement(self):
        contribution = initiate_contribution(
            scheme_account=self.account,
            amount=Decimal("5000.00"),
            payment_gateway="razorpay",
        )
        contribution.gateway_order_id = "order_bad_signature"
        contribution.save(update_fields=["gateway_order_id"])
        with patch(
            "schemes.payments.RazorpayPaymentGateway.verify_payment",
            return_value=False,
        ):
            response = self.client.post(
                reverse("schemes:razorpay_confirm", args=[contribution.pk]),
                {
                    "razorpay_order_id": "order_bad_signature",
                    "razorpay_payment_id": "pay_bad_signature",
                    "razorpay_signature": "invalid",
                },
            )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["success"])
        contribution.refresh_from_db()
        self.assertEqual(contribution.status, Contribution.Status.PENDING)
        self.assertEqual(get_cash_balance(self.account), Decimal("0.00"))

    def test_invalid_webhook_signature_creates_no_event(self):
        response = self.client.post(
            reverse("schemes:razorpay_webhook"),
            data=b'{"event":"payment.captured"}',
            content_type="application/json",
            HTTP_X_RAZORPAY_SIGNATURE="invalid",
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(PaymentWebhookEvent.objects.exists())

    def test_signed_captured_webhook_confirms_payment(self):
        contribution = initiate_contribution(
            scheme_account=self.account,
            amount=Decimal("5000.00"),
            payment_gateway="razorpay",
        )
        contribution.gateway_order_id = "order_signed_webhook"
        contribution.save(update_fields=["gateway_order_id"])
        payload = {
            "event": "payment.captured",
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_signed_webhook",
                        "order_id": "order_signed_webhook",
                        "amount": 500000,
                        "currency": "INR",
                        "status": "captured",
                        "captured": True,
                    }
                }
            },
        }
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        signature = hmac.new(
            b"test-webhook-secret", body, hashlib.sha256
        ).hexdigest()
        response = self.client.post(
            reverse("schemes:razorpay_webhook"),
            data=body,
            content_type="application/json",
            HTTP_X_RAZORPAY_SIGNATURE=signature,
            HTTP_X_RAZORPAY_EVENT_ID="event_signed_webhook",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "processed"})
        contribution.refresh_from_db()
        self.assertEqual(contribution.status, Contribution.Status.PAID)
        self.assertEqual(get_cash_balance(self.account), Decimal("5000.00"))
