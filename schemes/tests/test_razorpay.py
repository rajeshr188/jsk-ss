import hashlib
import hmac
import json
from io import StringIO
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch
from urllib.error import HTTPError

from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
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
from schemes.selectors import get_cash_balance, get_metal_balance
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
    "RAZORPAY_MODE": "test",
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
    mode = "test"

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
    def test_live_key_is_rejected_when_test_mode_is_configured(self):
        with self.assertRaises(ImproperlyConfigured):
            RazorpayPaymentGateway(
                mode="test",
                key_id="rzp_live_forbidden",
                key_secret="secret",
                webhook_secret="webhook",
                timeout_seconds=2,
            )

    def test_live_key_is_accepted_when_live_mode_is_configured(self):
        gateway = RazorpayPaymentGateway(
            mode="live",
            key_id="rzp_live_example",
            key_secret="secret",
            webhook_secret="webhook",
            timeout_seconds=2,
        )

        self.assertEqual(gateway.mode, "live")

    def test_missing_or_unknown_mode_is_rejected(self):
        for mode in ("", "production"):
            with self.subTest(mode=mode):
                with self.assertRaises(ImproperlyConfigured):
                    RazorpayPaymentGateway(
                        mode=mode,
                        key_id="rzp_live_example",
                        key_secret="secret",
                        webhook_secret="webhook",
                        timeout_seconds=2,
                    )

    def test_create_order_uses_authenticated_fixed_https_api(self):
        gateway = RazorpayPaymentGateway(
            mode="test",
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
            mode="test",
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
            mode="test",
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
            mode="test",
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
            mode="test",
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
            mode="test",
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


@override_settings(
    DEBUG=False,
    PAYMENT_GATEWAY="razorpay",
    RAZORPAY_MODE="live",
    RAZORPAY_KEY_ID="rzp_live_readiness",
    RAZORPAY_KEY_SECRET="live-secret",
    RAZORPAY_WEBHOOK_SECRET="live-webhook-secret",
    APP_RELEASE="readiness-test",
)
class RazorpayLiveReadinessCommandTests(TestCase):
    def test_live_configuration_with_no_cross_mode_orders_passes(self):
        output = StringIO()

        call_command("check_razorpay_live_readiness", stdout=output)

        self.assertIn("status=ok", output.getvalue())

    def test_open_test_order_blocks_live_activation(self):
        _, account = make_account(
            email="readiness-blocker@example.com",
            mode=SchemeAccount.SavingsMode.GOLD,
        )
        SchemeRate.objects.create(
            metal=SchemeRate.Metal.GOLD,
            rate_per_gram=Decimal("12500.0000"),
            purity=Decimal("0.9999"),
            effective_from=timezone.now(),
        )
        contribution = initiate_contribution(
            scheme_account=account,
            amount=Decimal("5000.00"),
            payment_gateway="razorpay",
            gateway_mode="test",
        )
        contribution.gateway_order_id = "order_test_still_open"
        contribution.save(update_fields=["gateway_order_id"])

        with self.assertRaises(CommandError):
            call_command(
                "check_razorpay_live_readiness",
                stdout=StringIO(),
                stderr=StringIO(),
            )


@override_settings(DEBUG=True)
class RazorpayServiceTests(TestCase):
    def test_monthly_pending_cash_order_is_reused_without_scheme_rate(self):
        _, account = make_account(email="pending@example.com")
        self.assertEqual(account.savings_mode, SchemeAccount.SavingsMode.CASH)
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

    def test_pending_order_cannot_cross_provider_modes(self):
        _, account = make_account(email="mode-boundary@example.com")
        test_gateway = FakeRazorpayGateway()
        initiate_razorpay_contribution(
            scheme_account=account,
            amount=Decimal("5000.00"),
            gateway=test_gateway,
        )
        live_gateway = FakeRazorpayGateway()
        live_gateway.mode = "live"

        with self.assertRaisesMessage(
            ValidationError, "different provider mode is already pending"
        ):
            initiate_razorpay_contribution(
                scheme_account=account,
                amount=Decimal("5000.00"),
                gateway=live_gateway,
            )

        self.assertEqual(Contribution.objects.count(), 1)
        self.assertEqual(live_gateway.order_calls, 0)

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
            gateway_mode="test",
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
                gateway_mode="test",
                event_id="event_gold_once",
                body=body,
                payload=payload,
            )
        contribution.refresh_from_db()
        self.assertEqual(contribution.status, Contribution.Status.PAID)
        self.assertEqual(MetalAllocation.objects.count(), 1)
        self.assertEqual(PaymentWebhookEvent.objects.count(), 1)
        self.assertEqual(
            contribution.metal_allocation.quantity, Decimal("0.400000")
        )

    def test_webhook_cannot_confirm_an_order_from_another_mode(self):
        _, account = make_account(email="webhook-mode-boundary@example.com")
        contribution = initiate_contribution(
            scheme_account=account,
            amount=Decimal("5000.00"),
            payment_gateway="razorpay",
            gateway_mode="test",
        )
        contribution.gateway_order_id = "order_test_mode_only"
        contribution.save(update_fields=["gateway_order_id"])
        payload = {
            "event": "payment.captured",
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_live_wrong_mode",
                        "order_id": "order_test_mode_only",
                        "amount": 500000,
                        "currency": "INR",
                        "status": "captured",
                        "captured": True,
                    }
                }
            },
        }
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")

        with self.assertRaises(ValidationError):
            process_razorpay_webhook(
                gateway_mode="live",
                event_id="event_live_wrong_mode",
                body=body,
                payload=payload,
            )

        contribution.refresh_from_db()
        self.assertEqual(contribution.status, Contribution.Status.PENDING)
        event = PaymentWebhookEvent.objects.get()
        self.assertEqual(event.gateway_mode, "live")
        self.assertEqual(event.status, PaymentWebhookEvent.Status.FAILED)

    def test_no_metal_rate_prevents_gold_and_silver_razorpay_orders(self):
        for metal in (SchemeAccount.SavingsMode.GOLD, SchemeAccount.SavingsMode.SILVER):
            with self.subTest(metal=metal):
                _, account = make_account(
                    email=f"no-rate-{metal.lower()}-order@example.com",
                    mode=metal,
                )
                gateway = FakeRazorpayGateway()

                with self.assertRaisesMessage(ValidationError, "has not been published"):
                    initiate_razorpay_contribution(
                        scheme_account=account,
                        amount=Decimal("5000.00"),
                        gateway=gateway,
                    )

                self.assertEqual(gateway.order_calls, 0)
                self.assertFalse(
                    Contribution.objects.filter(scheme_account=account).exists()
                )


@override_settings(**RAZORPAY_SETTINGS)
class RazorpayViewTests(TestCase):
    def setUp(self):
        self.customer, self.account = make_account(
            email="view-rzp@example.com",
            mode=SchemeAccount.SavingsMode.GOLD,
        )
        SchemeRate.objects.create(
            metal=SchemeRate.Metal.GOLD,
            rate_per_gram=Decimal("12500.0000"),
            purity=Decimal("0.9999"),
            effective_from=timezone.now(),
        )
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

    @override_settings(
        RAZORPAY_MODE="live",
        RAZORPAY_KEY_ID="rzp_live_public_key",
        RAZORPAY_KEY_SECRET="live-key-secret",
        RAZORPAY_WEBHOOK_SECRET="live-webhook-secret",
    )
    def test_live_checkout_uses_live_copy_and_persists_mode(self):
        order = PaymentOrder("order_live_view", 500000, "INR")
        with patch(
            "schemes.payments.RazorpayPaymentGateway.create_order", return_value=order
        ):
            response = self.client.post(
                reverse("schemes:pay_contribution", args=[self.account.scheme_number]),
                {"amount": "5000.00"},
                follow=True,
            )

        self.assertContains(response, "Live payment:")
        self.assertContains(response, "rzp_live_public_key")
        self.assertNotContains(response, "no real money is collected")
        contribution = Contribution.objects.get()
        self.assertEqual(contribution.gateway_mode, "live")

    @override_settings(
        RAZORPAY_MODE="live",
        RAZORPAY_KEY_ID="rzp_live_public_key",
        RAZORPAY_KEY_SECRET="live-key-secret",
        RAZORPAY_WEBHOOK_SECRET="live-webhook-secret",
    )
    def test_test_order_cannot_be_rendered_or_resumed_with_live_key(self):
        contribution = initiate_contribution(
            scheme_account=self.account,
            amount=Decimal("5000.00"),
            payment_gateway="razorpay",
            gateway_mode="test",
        )
        contribution.gateway_order_id = "order_test_not_live"
        contribution.save(update_fields=["gateway_order_id"])

        response = self.client.get(
            reverse("schemes:razorpay_checkout", args=[contribution.pk]),
            follow=True,
        )

        self.assertContains(response, "different Razorpay mode")
        self.assertNotContains(response, "rzp_live_public_key")
        self.assertNotContains(response, "Resume payment")

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
        self.assertEqual(get_metal_balance(self.account), Decimal("0.000000"))

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
        self.assertEqual(get_metal_balance(self.account), Decimal("0.000000"))

    def test_customer_cannot_open_another_customers_checkout(self):
        other_customer, other_account = make_account(
            email="other-rzp@example.com",
            mode=SchemeAccount.SavingsMode.GOLD,
        )
        contribution = initiate_contribution(
            scheme_account=other_account,
            amount=Decimal("5000.00"),
            payment_gateway="razorpay",
            gateway_mode="test",
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
            gateway_mode="test",
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
        self.assertEqual(get_metal_balance(self.account), Decimal("0.400000"))

    def test_missing_verification_fields_return_400_and_no_entitlement(self):
        contribution = initiate_contribution(
            scheme_account=self.account,
            amount=Decimal("5000.00"),
            payment_gateway="razorpay",
            gateway_mode="test",
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
        self.assertEqual(get_metal_balance(self.account), Decimal("0.000000"))

    def test_signature_mismatch_returns_400_and_no_entitlement(self):
        contribution = initiate_contribution(
            scheme_account=self.account,
            amount=Decimal("5000.00"),
            payment_gateway="razorpay",
            gateway_mode="test",
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
        self.assertEqual(get_metal_balance(self.account), Decimal("0.000000"))

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
            gateway_mode="test",
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
        self.assertEqual(get_metal_balance(self.account), Decimal("0.400000"))
