import hashlib
import hmac
import json
from datetime import timedelta
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

from schemes.forms import WebhookRecoveryForm
from schemes.tests.grade_helpers import enrolment_grade_kwargs, metal_grade_for
from schemes.models import (
    AuditEvent,
    Contribution,
    MetalAllocation,
    PaymentWebhookEvent,
    SchemeAccount,
    SchemePlan,
    SchemeRate,
    WebhookProcessingAttempt,
)
from schemes.payments import (
    PaymentGatewayAuthenticationError,
    PaymentGatewayError,
    PaymentGatewayValidationError,
    PaymentInspection,
    PaymentOrder,
    PaymentOrderInspection,
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
    reconcile_abandoned_razorpay_contribution,
    reconcile_razorpay_webhook,
    WebhookTransientProcessingError,
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

    def __init__(self, *, verified=True, inspection=None, payment_inspection=None):
        self.verified = verified
        self.inspection = inspection
        self.payment_inspection = payment_inspection
        self.order_calls = 0
        self.verify_calls = 0
        self.inspect_calls = 0
        self.payment_inspect_calls = 0

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

    def inspect_order(self, *, order_id):
        self.inspect_calls += 1
        return self.inspection or PaymentOrderInspection(
            order_id=order_id,
            status="created",
            amount_subunits=500000,
            amount_paid_subunits=0,
            amount_due_subunits=500000,
            currency="INR",
            attempts=0,
            payment_count=0,
            payment_statuses=(),
        )

    def inspect_payment(self, *, payment_id):
        self.payment_inspect_calls += 1
        if self.payment_inspection is None:
            raise AssertionError("Configure payment_inspection for this test.")
        return self.payment_inspection


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
        **enrolment_grade_kwargs(plan, mode),
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

    def test_order_inspection_fetches_order_and_all_payment_attempts(self):
        gateway = RazorpayPaymentGateway(
            mode="test",
            key_id="rzp_test_key",
            key_secret="secret",
            webhook_secret="webhook",
            timeout_seconds=2,
        )
        responses = [
            FakeResponse(
                {
                    "id": "order_inspect_1",
                    "status": "attempted",
                    "amount": 500000,
                    "amount_paid": 0,
                    "amount_due": 500000,
                    "currency": "INR",
                    "attempts": 2,
                }
            ),
            FakeResponse(
                {
                    "entity": "collection",
                    "count": 2,
                    "items": [{"status": "failed"}, {"status": "created"}],
                }
            ),
        ]
        with patch("schemes.payments.urlopen", side_effect=responses) as urlopen_mock:
            inspection = gateway.inspect_order(order_id="order_inspect_1")

        self.assertEqual(inspection.status, "attempted")
        self.assertEqual(inspection.attempts, 2)
        self.assertEqual(inspection.payment_count, 2)
        self.assertEqual(inspection.payment_statuses, ("failed", "created"))
        self.assertEqual(urlopen_mock.call_count, 2)
        self.assertTrue(
            urlopen_mock.call_args_list[1].args[0].full_url.endswith(
                "/orders/order_inspect_1/payments"
            )
        )

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

    def test_payment_inspection_fetches_bounded_provider_state(self):
        gateway = RazorpayPaymentGateway(
            mode="test",
            key_id="rzp_test_key",
            key_secret="secret",
            webhook_secret="webhook",
            timeout_seconds=2,
        )
        response = FakeResponse(
            {
                "id": "pay_inspect_1",
                "order_id": "order_inspect_1",
                "amount": 500000,
                "currency": "INR",
                "status": "captured",
                "captured": True,
            }
        )
        with patch("schemes.payments.urlopen", return_value=response) as urlopen_mock:
            inspection = gateway.inspect_payment(payment_id="pay_inspect_1")

        self.assertEqual(
            inspection,
            PaymentInspection(
                payment_id="pay_inspect_1",
                order_id="order_inspect_1",
                amount_subunits=500000,
                currency="INR",
                status="captured",
                captured=True,
            ),
        )
        self.assertTrue(
            urlopen_mock.call_args.args[0].full_url.endswith(
                "/payments/pay_inspect_1"
            )
        )

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
            metal_grade=account.metal_grade,
            metal=SchemeRate.Metal.GOLD,
            rate_per_gram=Decimal("12500.0000"),
            purity=account.metal_grade.fineness,
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


@override_settings(**{**RAZORPAY_SETTINGS, "DEBUG": True})
class RazorpayOrderReconciliationCommandTests(TestCase):
    def test_command_is_dry_run_by_default_and_apply_closes_eligible_order(self):
        _, account = make_account(email="command-abandoned@example.com")
        contribution = initiate_contribution(
            scheme_account=account,
            amount=Decimal("5000.00"),
            payment_gateway="razorpay",
            gateway_mode="test",
        )
        contribution.gateway_order_id = "order_command_abandoned"
        contribution.save(update_fields=["gateway_order_id"])
        Contribution.objects.filter(pk=contribution.pk).update(
            created_at=timezone.now() - timedelta(hours=48)
        )
        inspection = PaymentOrderInspection(
            order_id=contribution.gateway_order_id,
            status="created",
            amount_subunits=500000,
            amount_paid_subunits=0,
            amount_due_subunits=500000,
            currency="INR",
            attempts=0,
            payment_count=0,
            payment_statuses=(),
        )

        with patch(
            "schemes.payments.RazorpayPaymentGateway.inspect_order",
            return_value=inspection,
        ):
            dry_output = StringIO()
            call_command(
                "reconcile_abandoned_razorpay_orders",
                "--older-than-hours=24",
                stdout=dry_output,
            )
            contribution.refresh_from_db()
            self.assertEqual(contribution.status, Contribution.Status.PENDING)
            self.assertIn("mode=dry-run", dry_output.getvalue())

            apply_output = StringIO()
            call_command(
                "reconcile_abandoned_razorpay_orders",
                "--older-than-hours=24",
                "--apply",
                stdout=apply_output,
            )

        contribution.refresh_from_db()
        self.assertEqual(contribution.status, Contribution.Status.ABANDONED)
        self.assertIn("abandoned=1", apply_output.getvalue())
        self.assertEqual(
            AuditEvent.objects.filter(
                action=AuditEvent.Action.PAYMENT_ORDER_RECONCILIATION
            ).count(),
            1,
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

    def test_aged_untouched_order_is_abandoned_with_immutable_audit(self):
        _, account = make_account(email="abandoned@example.com")
        gateway = FakeRazorpayGateway()
        contribution = initiate_razorpay_contribution(
            scheme_account=account, amount=Decimal("5000.00"), gateway=gateway
        )
        Contribution.objects.filter(pk=contribution.pk).update(
            created_at=timezone.now() - timedelta(hours=48)
        )

        dry_run = reconcile_abandoned_razorpay_contribution(
            contribution_id=contribution.pk,
            cutoff=timezone.now() - timedelta(hours=24),
            gateway=gateway,
        )
        contribution.refresh_from_db()
        self.assertEqual(dry_run.outcome, "ELIGIBLE_FOR_ABANDONMENT")
        self.assertFalse(dry_run.applied)
        self.assertEqual(contribution.status, Contribution.Status.PENDING)
        self.assertFalse(
            AuditEvent.objects.filter(
                action=AuditEvent.Action.PAYMENT_ORDER_RECONCILIATION
            ).exists()
        )

        applied = reconcile_abandoned_razorpay_contribution(
            contribution_id=contribution.pk,
            cutoff=timezone.now() - timedelta(hours=24),
            apply=True,
            gateway=gateway,
        )
        contribution.refresh_from_db()
        self.assertTrue(applied.applied)
        self.assertEqual(contribution.status, Contribution.Status.ABANDONED)
        self.assertEqual(contribution.gateway_order_id, f"order_test_{contribution.pk}")
        event = AuditEvent.objects.get(
            action=AuditEvent.Action.PAYMENT_ORDER_RECONCILIATION
        )
        self.assertEqual(
            event.action, AuditEvent.Action.PAYMENT_ORDER_RECONCILIATION
        )
        self.assertEqual(event.details["provider_order_status"], "created")
        self.assertEqual(event.details["provider_payment_count"], 0)

    def test_attempted_order_requires_review_and_remains_pending(self):
        _, account = make_account(email="attempted-review@example.com")
        contribution = initiate_razorpay_contribution(
            scheme_account=account,
            amount=Decimal("5000.00"),
            gateway=FakeRazorpayGateway(),
        )
        Contribution.objects.filter(pk=contribution.pk).update(
            created_at=timezone.now() - timedelta(hours=48)
        )
        gateway = FakeRazorpayGateway(
            inspection=PaymentOrderInspection(
                order_id=contribution.gateway_order_id,
                status="attempted",
                amount_subunits=500000,
                amount_paid_subunits=0,
                amount_due_subunits=500000,
                currency="INR",
                attempts=1,
                payment_count=1,
                payment_statuses=("failed",),
            )
        )

        result = reconcile_abandoned_razorpay_contribution(
            contribution_id=contribution.pk,
            cutoff=timezone.now() - timedelta(hours=24),
            apply=True,
            gateway=gateway,
        )

        contribution.refresh_from_db()
        self.assertEqual(result.outcome, "REVIEW_REQUIRED")
        self.assertFalse(result.applied)
        self.assertEqual(contribution.status, Contribution.Status.PENDING)
        self.assertEqual(
            AuditEvent.objects.get(
                action=AuditEvent.Action.PAYMENT_ORDER_RECONCILIATION
            ).details["provider_payment_statuses"],
            ["failed"],
        )

    def test_abandoned_monthly_order_releases_a_new_resumable_attempt(self):
        _, account = make_account(email="replacement@example.com")
        gateway = FakeRazorpayGateway()
        first = initiate_razorpay_contribution(
            scheme_account=account, amount=Decimal("5000.00"), gateway=gateway
        )
        Contribution.objects.filter(pk=first.pk).update(
            created_at=timezone.now() - timedelta(hours=48)
        )
        reconcile_abandoned_razorpay_contribution(
            contribution_id=first.pk,
            cutoff=timezone.now() - timedelta(hours=24),
            apply=True,
            gateway=gateway,
        )

        replacement = initiate_razorpay_contribution(
            scheme_account=account, amount=Decimal("5000.00"), gateway=gateway
        )
        resumed = initiate_razorpay_contribution(
            scheme_account=account, amount=Decimal("5000.00"), gateway=gateway
        )

        self.assertNotEqual(first.pk, replacement.pk)
        self.assertEqual(resumed.pk, replacement.pk)
        self.assertEqual(gateway.order_calls, 2)

    def test_flexible_orders_are_reconciled_independently(self):
        _, account = make_account(
            email="flexible-abandoned@example.com",
            frequency=SchemePlan.FrequencyRule.FLEXIBLE,
        )
        gateway = FakeRazorpayGateway()
        first = initiate_razorpay_contribution(
            scheme_account=account, amount=Decimal("5000.00"), gateway=gateway
        )
        second = initiate_razorpay_contribution(
            scheme_account=account, amount=Decimal("5000.00"), gateway=gateway
        )
        Contribution.objects.filter(pk=first.pk).update(
            created_at=timezone.now() - timedelta(hours=48)
        )

        reconcile_abandoned_razorpay_contribution(
            contribution_id=first.pk,
            cutoff=timezone.now() - timedelta(hours=24),
            apply=True,
            gateway=gateway,
        )

        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(first.status, Contribution.Status.ABANDONED)
        self.assertEqual(second.status, Contribution.Status.PENDING)
        self.assertNotEqual(first.gateway_order_id, second.gateway_order_id)

    def test_late_capture_for_abandoned_order_becomes_webhook_exception(self):
        _, account = make_account(email="late-capture@example.com")
        gateway = FakeRazorpayGateway()
        contribution = initiate_razorpay_contribution(
            scheme_account=account, amount=Decimal("5000.00"), gateway=gateway
        )
        Contribution.objects.filter(pk=contribution.pk).update(
            created_at=timezone.now() - timedelta(hours=48)
        )
        reconcile_abandoned_razorpay_contribution(
            contribution_id=contribution.pk,
            cutoff=timezone.now() - timedelta(hours=24),
            apply=True,
            gateway=gateway,
        )
        payload = {
            "event": "payment.captured",
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_late_capture",
                        "order_id": contribution.gateway_order_id,
                        "amount": 500000,
                        "currency": "INR",
                        "status": "captured",
                        "captured": True,
                    }
                }
            },
        }
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")

        result = process_razorpay_webhook(
            gateway_mode="test",
            event_id="event_late_capture",
            body=body,
            payload=payload,
        )

        contribution.refresh_from_db()
        self.assertEqual(contribution.status, Contribution.Status.ABANDONED)
        event = PaymentWebhookEvent.objects.get()
        self.assertEqual(event.status, PaymentWebhookEvent.Status.REVIEW_REQUIRED)
        self.assertEqual(event.failure_code, "LATE_CAPTURE_ABANDONED")
        self.assertEqual(result, event)
        self.assertEqual(event.contribution, contribution)
        self.assertEqual(event.gateway_order_id, contribution.gateway_order_id)
        self.assertEqual(event.gateway_reference, "pay_late_capture")
        self.assertEqual(get_cash_balance(account), Decimal("0.00"))

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
            metal_grade=metal_grade_for(SchemeRate.Metal.GOLD),
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

        result = process_razorpay_webhook(
            gateway_mode="live",
            event_id="event_live_wrong_mode",
            body=body,
            payload=payload,
        )

        contribution.refresh_from_db()
        self.assertEqual(contribution.status, Contribution.Status.PENDING)
        event = PaymentWebhookEvent.objects.get()
        self.assertEqual(event.gateway_mode, "live")
        self.assertEqual(event.status, PaymentWebhookEvent.Status.REVIEW_REQUIRED)
        self.assertEqual(
            event.failure_code,
            "CONTRIBUTION_NOT_FOUND_OR_MODE_MISMATCH",
        )
        self.assertEqual(result, event)

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
class RazorpayWebhookRecoveryTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(
            username="webhook-recovery-owner@example.com",
            email="webhook-recovery-owner@example.com",
            password="owner-password-strong",
            role=get_user_model().Role.OWNER,
        )
        publish_scheme_rate(
            metal_grade=metal_grade_for(SchemeRate.Metal.GOLD),
            rate_per_gram=Decimal("12500.0000"),
            published_by=self.owner,
        )
        self.customer, self.account = make_account(
            email="webhook-recovery@example.com",
            mode=SchemeAccount.SavingsMode.GOLD,
        )
        self.contribution = initiate_contribution(
            scheme_account=self.account,
            amount=Decimal("5000.00"),
            payment_gateway="razorpay",
            gateway_mode="test",
        )
        self.contribution.gateway_order_id = "order_webhook_recovery"
        self.contribution.save(update_fields=["gateway_order_id"])

    def create_review_event(self):
        payload = {
            "event": "payment.captured",
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_webhook_recovery",
                        "order_id": self.contribution.gateway_order_id,
                        "amount": 499999,
                        "currency": "INR",
                        "status": "captured",
                        "captured": True,
                    }
                }
            },
        }
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        return process_razorpay_webhook(
            gateway_mode="test",
            event_id="event_webhook_recovery",
            body=body,
            payload=payload,
        )

    def recovery_gateway(self, **overrides):
        values = {
            "payment_id": "pay_webhook_recovery",
            "order_id": self.contribution.gateway_order_id,
            "amount_subunits": 500000,
            "currency": "INR",
            "status": "captured",
            "captured": True,
        }
        values.update(overrides)
        return FakeRazorpayGateway(payment_inspection=PaymentInspection(**values))

    def test_review_event_retains_provider_ids_and_append_only_attempt(self):
        event = self.create_review_event()

        self.assertEqual(event.status, PaymentWebhookEvent.Status.REVIEW_REQUIRED)
        self.assertEqual(event.gateway_order_id, "order_webhook_recovery")
        self.assertEqual(event.gateway_reference, "pay_webhook_recovery")
        attempt = event.processing_attempts.get()
        self.assertEqual(
            attempt.outcome,
            WebhookProcessingAttempt.Outcome.REVIEW_REQUIRED,
        )
        attempt.detail = "Changed"
        with self.assertRaisesMessage(ValidationError, "immutable"):
            attempt.save()

    def test_transient_delivery_returns_retryable_error_then_recovers_once(self):
        payload = {
            "event": "payment.captured",
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_transient_recovery",
                        "order_id": self.contribution.gateway_order_id,
                        "amount": 500000,
                        "currency": "INR",
                        "status": "captured",
                        "captured": True,
                    }
                }
            },
        }
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        with patch(
            "schemes.services._apply_contribution_entitlement",
            side_effect=RuntimeError("temporary failure that must not be exposed"),
        ):
            with self.assertRaises(WebhookTransientProcessingError):
                process_razorpay_webhook(
                    gateway_mode="test",
                    event_id="event_transient_recovery",
                    body=body,
                    payload=payload,
                )

        event = PaymentWebhookEvent.objects.get(event_id="event_transient_recovery")
        self.assertEqual(event.status, PaymentWebhookEvent.Status.RECEIVED)
        self.assertEqual(event.failure_code, "TRANSIENT_PROCESSING_FAILURE")
        self.assertNotIn("temporary failure", event.error)
        self.assertEqual(
            event.processing_attempts.get().outcome,
            WebhookProcessingAttempt.Outcome.TRANSIENT_FAILURE,
        )

        process_razorpay_webhook(
            gateway_mode="test",
            event_id="event_transient_recovery",
            body=body,
            payload=payload,
        )
        self.contribution.refresh_from_db()
        event.refresh_from_db()
        self.assertEqual(event.status, PaymentWebhookEvent.Status.PROCESSED)
        self.assertEqual(self.contribution.status, Contribution.Status.PAID)
        self.assertEqual(MetalAllocation.objects.filter(contribution=self.contribution).count(), 1)
        self.assertEqual(event.processing_attempts.count(), 2)

    def test_owner_dry_run_then_apply_uses_provider_state_once(self):
        event = self.create_review_event()
        gateway = self.recovery_gateway()

        dry_run = reconcile_razorpay_webhook(
            webhook_event_id=event.pk,
            apply=False,
            gateway=gateway,
            performed_by=self.owner,
            reason="Check the captured provider payment before recovery.",
        )
        self.contribution.refresh_from_db()
        event.refresh_from_db()
        self.assertEqual(dry_run.outcome, "ELIGIBLE_FOR_RECOVERY")
        self.assertFalse(dry_run.applied)
        self.assertEqual(self.contribution.status, Contribution.Status.PENDING)
        self.assertEqual(event.status, PaymentWebhookEvent.Status.REVIEW_REQUIRED)
        self.assertFalse(
            AuditEvent.objects.filter(action=AuditEvent.Action.WEBHOOK_RECOVERY).exists()
        )

        applied = reconcile_razorpay_webhook(
            webhook_event_id=event.pk,
            apply=True,
            gateway=gateway,
            performed_by=self.owner,
            reason="Apply the exact captured payment after provider review.",
        )
        self.contribution.refresh_from_db()
        event.refresh_from_db()
        self.assertTrue(applied.applied)
        self.assertEqual(applied.outcome, "ELIGIBLE_FOR_RECOVERY")
        self.assertEqual(self.contribution.status, Contribution.Status.PAID)
        self.assertEqual(event.status, PaymentWebhookEvent.Status.PROCESSED)
        self.assertEqual(MetalAllocation.objects.filter(contribution=self.contribution).count(), 1)
        audit = AuditEvent.objects.get(action=AuditEvent.Action.WEBHOOK_RECOVERY)
        self.assertEqual(audit.actor, self.owner)
        self.assertEqual(audit.contribution, self.contribution)
        self.assertEqual(audit.details["provider"]["amount_subunits"], 500000)
        self.assertEqual(gateway.payment_inspect_calls, 2)

    def test_mismatched_provider_state_never_applies_entitlement(self):
        event = self.create_review_event()
        result = reconcile_razorpay_webhook(
            webhook_event_id=event.pk,
            apply=False,
            gateway=self.recovery_gateway(amount_subunits=400000),
            performed_by=self.owner,
            reason="Investigate the provider amount mismatch.",
        )

        self.contribution.refresh_from_db()
        event.refresh_from_db()
        self.assertEqual(result.outcome, "MANUAL_REVIEW_REQUIRED")
        self.assertFalse(result.applied)
        self.assertEqual(self.contribution.status, Contribution.Status.PENDING)
        self.assertEqual(event.status, PaymentWebhookEvent.Status.REVIEW_REQUIRED)
        self.assertFalse(MetalAllocation.objects.exists())
        self.assertFalse(
            AuditEvent.objects.filter(action=AuditEvent.Action.WEBHOOK_RECOVERY).exists()
        )
        with self.assertRaisesMessage(ValidationError, "Check provider state"):
            reconcile_razorpay_webhook(
                webhook_event_id=event.pk,
                apply=True,
                gateway=self.recovery_gateway(amount_subunits=400000),
                performed_by=self.owner,
                reason="Do not apply the provider amount mismatch.",
            )

    def test_apply_requires_a_prior_safe_provider_inspection(self):
        event = self.create_review_event()

        with self.assertRaisesMessage(ValidationError, "Check provider state"):
            reconcile_razorpay_webhook(
                webhook_event_id=event.pk,
                apply=True,
                gateway=self.recovery_gateway(),
                performed_by=self.owner,
                reason="Attempt recovery without the required inspection.",
            )

        self.contribution.refresh_from_db()
        self.assertEqual(self.contribution.status, Contribution.Status.PENDING)
        self.assertFalse(MetalAllocation.objects.exists())

    def test_non_owner_cannot_reconcile_webhook(self):
        event = self.create_review_event()
        with self.assertRaisesMessage(ValidationError, "active owner"):
            reconcile_razorpay_webhook(
                webhook_event_id=event.pk,
                apply=False,
                gateway=self.recovery_gateway(),
                performed_by=self.customer.user,
                reason="Unauthorized recovery attempt.",
            )

    def test_recovery_page_is_owner_only_and_posts_provider_check(self):
        event = self.create_review_event()
        self.client.force_login(self.customer.user)
        denied = self.client.get(
            reverse("schemes:webhook_recovery", args=[event.pk])
        )
        self.assertEqual(denied.status_code, 403)

        self.client.force_login(self.owner)
        response = self.client.get(
            reverse("schemes:webhook_recovery", args=[event.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Apply verified recovery")
        with patch(
            "schemes.services.get_payment_gateway",
            return_value=self.recovery_gateway(),
        ):
            response = self.client.post(
                reverse("schemes:webhook_recovery", args=[event.pk]),
                {
                    "action": WebhookRecoveryForm.Action.INSPECT,
                    "reason": "Owner provider comparison before recovery.",
                },
            )
        self.assertRedirects(
            response,
            reverse("schemes:webhook_recovery", args=[event.pk]),
        )
        self.assertTrue(
            event.processing_attempts.filter(
                source=WebhookProcessingAttempt.Source.OWNER_RECOVERY,
                outcome=WebhookProcessingAttempt.Outcome.ELIGIBLE_FOR_RECOVERY,
                actor=self.owner,
            ).exists()
        )


@override_settings(**RAZORPAY_SETTINGS)
class RazorpayViewTests(TestCase):
    def setUp(self):
        self.customer, self.account = make_account(
            email="view-rzp@example.com",
            mode=SchemeAccount.SavingsMode.GOLD,
        )
        SchemeRate.objects.create(
            metal_grade=self.account.metal_grade,
            metal=SchemeRate.Metal.GOLD,
            rate_per_gram=Decimal("12500.0000"),
            purity=self.account.metal_grade.fineness,
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

    def test_signed_permanent_mismatch_returns_200_and_enters_review(self):
        contribution = initiate_contribution(
            scheme_account=self.account,
            amount=Decimal("5000.00"),
            payment_gateway="razorpay",
            gateway_mode="test",
        )
        contribution.gateway_order_id = "order_permanent_mismatch"
        contribution.save(update_fields=["gateway_order_id"])
        payload = {
            "event": "payment.captured",
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_permanent_mismatch",
                        "order_id": "order_permanent_mismatch",
                        "amount": 499999,
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
            HTTP_X_RAZORPAY_EVENT_ID="event_permanent_mismatch",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "review_required"})
        contribution.refresh_from_db()
        event = PaymentWebhookEvent.objects.get(
            event_id="event_permanent_mismatch"
        )
        self.assertEqual(contribution.status, Contribution.Status.PENDING)
        self.assertEqual(event.status, PaymentWebhookEvent.Status.REVIEW_REQUIRED)
        self.assertEqual(event.failure_code, "PAYMENT_DETAILS_MISMATCH")
        self.assertEqual(
            event.processing_attempts.get().outcome,
            WebhookProcessingAttempt.Outcome.REVIEW_REQUIRED,
        )

    def test_signed_transient_failure_returns_503_for_provider_retry(self):
        contribution = initiate_contribution(
            scheme_account=self.account,
            amount=Decimal("5000.00"),
            payment_gateway="razorpay",
            gateway_mode="test",
        )
        contribution.gateway_order_id = "order_transient_failure"
        contribution.save(update_fields=["gateway_order_id"])
        payload = {
            "event": "payment.captured",
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_transient_failure",
                        "order_id": "order_transient_failure",
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

        with patch(
            "schemes.services._apply_contribution_entitlement",
            side_effect=RuntimeError("private transient detail"),
        ):
            response = self.client.post(
                reverse("schemes:razorpay_webhook"),
                data=body,
                content_type="application/json",
                HTTP_X_RAZORPAY_SIGNATURE=signature,
                HTTP_X_RAZORPAY_EVENT_ID="event_transient_failure",
            )

        self.assertEqual(response.status_code, 503)
        self.assertNotContains(
            response,
            "private transient detail",
            status_code=503,
        )
        contribution.refresh_from_db()
        event = PaymentWebhookEvent.objects.get(event_id="event_transient_failure")
        self.assertEqual(contribution.status, Contribution.Status.PAID_UNALLOCATED)
        self.assertEqual(event.status, PaymentWebhookEvent.Status.RECEIVED)
        self.assertEqual(event.failure_code, "TRANSIENT_PROCESSING_FAILURE")
        self.assertEqual(
            event.processing_attempts.get().outcome,
            WebhookProcessingAttempt.Outcome.TRANSIENT_FAILURE,
        )
