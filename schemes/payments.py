import base64
import hashlib
import hmac
import json
import re
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


RAZORPAY_API_BASE_URL = "https://api.razorpay.com/v1"
RAZORPAY_MIN_AMOUNT_SUBUNITS = 100
RAZORPAY_RESPONSE_LIMIT = 64 * 1024
RAZORPAY_ID_PATTERN = re.compile(r"^[A-Za-z0-9_]+$")
RAZORPAY_KEY_PREFIXES = {
    "test": "rzp_test_",
    "live": "rzp_live_",
}


def validate_razorpay_mode(*, mode, key_id):
    normalized_mode = str(mode or "").strip().lower()
    if normalized_mode not in RAZORPAY_KEY_PREFIXES:
        raise ImproperlyConfigured("RAZORPAY_MODE must be test or live.")
    expected_prefix = RAZORPAY_KEY_PREFIXES[normalized_mode]
    if not str(key_id or "").startswith(expected_prefix):
        raise ImproperlyConfigured(
            "RAZORPAY_KEY_ID must match the configured RAZORPAY_MODE."
        )
    return normalized_mode


class PaymentGatewayError(Exception):
    """A safe, customer-displayable payment provider failure."""

    status_code = 500


class PaymentGatewayAuthenticationError(PaymentGatewayError):
    status_code = 401


class PaymentGatewayValidationError(PaymentGatewayError):
    status_code = 400


@dataclass(frozen=True)
class PaymentResult:
    successful: bool
    verified: bool
    gateway_reference: str


@dataclass(frozen=True)
class PaymentOrder:
    order_id: str
    amount_subunits: int
    currency: str


@dataclass(frozen=True)
class PaymentOrderInspection:
    order_id: str
    status: str
    amount_subunits: int
    amount_paid_subunits: int
    amount_due_subunits: int
    currency: str
    attempts: int
    payment_count: int
    payment_statuses: tuple[str, ...]


@dataclass(frozen=True)
class PaymentInspection:
    payment_id: str
    order_id: str
    amount_subunits: int
    currency: str
    status: str
    captured: bool


class PaymentGateway(ABC):
    name: str

    @abstractmethod
    def create_order(self, contribution):
        raise NotImplementedError

    @abstractmethod
    def verify_payment(
        self, *, order_id, payment_id, signature, expected_amount
    ):
        raise NotImplementedError

    @abstractmethod
    def verify_webhook(self, *, body, signature):
        raise NotImplementedError


class MockPaymentGateway(PaymentGateway):
    name = "mock"

    def create_order(self, contribution):
        return PaymentOrder(
            order_id=f"mock_order_{uuid.uuid4().hex}",
            amount_subunits=_amount_to_subunits(contribution.amount),
            currency="INR",
        )

    def verify_payment(self, *, order_id, payment_id, signature, expected_amount):
        return bool(order_id and payment_id and signature == "mock_verified")

    def verify_webhook(self, *, body, signature):
        return signature == "mock_verified"

    def charge(self, contribution):
        return PaymentResult(
            successful=True,
            verified=True,
            gateway_reference=f"mock_{uuid.uuid4().hex}",
        )


class RazorpayPaymentGateway(PaymentGateway):
    name = "razorpay"

    def __init__(
        self,
        *,
        mode=None,
        key_id=None,
        key_secret=None,
        webhook_secret=None,
        timeout_seconds=None,
    ):
        raw_mode = mode if mode is not None else settings.RAZORPAY_MODE
        self.key_id = key_id if key_id is not None else settings.RAZORPAY_KEY_ID
        self.mode = validate_razorpay_mode(mode=raw_mode, key_id=self.key_id)
        self.key_secret = (
            key_secret if key_secret is not None else settings.RAZORPAY_KEY_SECRET
        )
        self.webhook_secret = (
            webhook_secret
            if webhook_secret is not None
            else settings.RAZORPAY_WEBHOOK_SECRET
        )
        raw_timeout = (
            timeout_seconds
            if timeout_seconds is not None
            else settings.RAZORPAY_TIMEOUT_SECONDS
        )
        try:
            self.timeout_seconds = min(max(float(raw_timeout), 0.1), 30.0)
        except (TypeError, ValueError):
            raise ImproperlyConfigured(
                "RAZORPAY_TIMEOUT_SECONDS must be a number between 0.1 and 30."
            ) from None
        if not self.key_secret:
            raise ImproperlyConfigured("RAZORPAY_KEY_SECRET must be set.")
        if not self.webhook_secret:
            raise ImproperlyConfigured("RAZORPAY_WEBHOOK_SECRET must be set.")

    def create_order(self, contribution):
        amount_subunits = _amount_to_subunits(contribution.amount)
        if amount_subunits < RAZORPAY_MIN_AMOUNT_SUBUNITS:
            raise PaymentGatewayValidationError(
                "Razorpay requires a minimum payment amount of ₹1.00."
            )
        payload = self._request_json(
            "POST",
            "/orders",
            payload={
                "amount": amount_subunits,
                "currency": "INR",
                "receipt": f"contribution_{contribution.pk}",
                "notes": {"contribution_id": str(contribution.pk)},
            },
        )
        order_id = payload.get("id")
        if (
            not isinstance(order_id, str)
            or not order_id.startswith("order_")
            or payload.get("amount") != amount_subunits
            or payload.get("currency") != "INR"
        ):
            raise PaymentGatewayError("Razorpay returned an invalid order response.")
        return PaymentOrder(
            order_id=order_id,
            amount_subunits=amount_subunits,
            currency="INR",
        )

    def verify_payment(
        self, *, order_id, payment_id, signature, expected_amount
    ):
        if not all(
            isinstance(value, str) and value
            for value in (order_id, payment_id, signature)
        ):
            return False
        if not payment_id.startswith("pay_") or not RAZORPAY_ID_PATTERN.fullmatch(
            payment_id
        ):
            return False
        expected_signature = hmac.new(
            self.key_secret.encode("utf-8"),
            f"{order_id}|{payment_id}".encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected_signature, signature):
            return False

        payment = self._request_json("GET", f"/payments/{payment_id}")
        return (
            payment.get("id") == payment_id
            and payment.get("order_id") == order_id
            and payment.get("amount") == _amount_to_subunits(expected_amount)
            and payment.get("currency") == "INR"
            and payment.get("status") == "captured"
            and payment.get("captured") is True
        )

    def verify_webhook(self, *, body, signature):
        if not isinstance(body, bytes) or not isinstance(signature, str) or not signature:
            return False
        expected_signature = hmac.new(
            self.webhook_secret.encode("utf-8"), body, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected_signature, signature)

    def inspect_order(self, *, order_id):
        if (
            not isinstance(order_id, str)
            or not order_id.startswith("order_")
            or not RAZORPAY_ID_PATTERN.fullmatch(order_id)
        ):
            raise PaymentGatewayValidationError("The Razorpay order ID is invalid.")

        order = self._request_json("GET", f"/orders/{order_id}")
        payments = self._request_json("GET", f"/orders/{order_id}/payments")
        items = payments.get("items")
        payment_count = payments.get("count")
        if (
            not isinstance(items, list)
            or not isinstance(payment_count, int)
            or isinstance(payment_count, bool)
            or payment_count < 0
            or payment_count != len(items)
        ):
            raise PaymentGatewayError("Razorpay returned an invalid payment list.")
        statuses = []
        for payment in items:
            if not isinstance(payment, dict) or not isinstance(
                payment.get("status"), str
            ):
                raise PaymentGatewayError("Razorpay returned an invalid payment list.")
            statuses.append(payment["status"])

        integer_fields = ("amount", "amount_paid", "amount_due", "attempts")
        if (
            order.get("id") != order_id
            or order.get("status") not in {"created", "attempted", "paid"}
            or order.get("currency") != "INR"
            or any(
                not isinstance(order.get(field), int)
                or isinstance(order.get(field), bool)
                or order[field] < 0
                for field in integer_fields
            )
        ):
            raise PaymentGatewayError("Razorpay returned an invalid order response.")

        return PaymentOrderInspection(
            order_id=order_id,
            status=order["status"],
            amount_subunits=order["amount"],
            amount_paid_subunits=order["amount_paid"],
            amount_due_subunits=order["amount_due"],
            currency=order["currency"],
            attempts=order["attempts"],
            payment_count=payment_count,
            payment_statuses=tuple(statuses),
        )

    def inspect_payment(self, *, payment_id):
        if (
            not isinstance(payment_id, str)
            or not payment_id.startswith("pay_")
            or not RAZORPAY_ID_PATTERN.fullmatch(payment_id)
        ):
            raise PaymentGatewayValidationError("The Razorpay payment ID is invalid.")

        payment = self._request_json("GET", f"/payments/{payment_id}")
        order_id = payment.get("order_id")
        amount = payment.get("amount")
        currency = payment.get("currency")
        status = payment.get("status")
        captured = payment.get("captured")
        if (
            payment.get("id") != payment_id
            or not isinstance(order_id, str)
            or not order_id.startswith("order_")
            or not RAZORPAY_ID_PATTERN.fullmatch(order_id)
            or not isinstance(amount, int)
            or isinstance(amount, bool)
            or amount < 0
            or not isinstance(currency, str)
            or not isinstance(status, str)
            or not status
            or not isinstance(captured, bool)
        ):
            raise PaymentGatewayError("Razorpay returned an invalid payment response.")
        return PaymentInspection(
            payment_id=payment_id,
            order_id=order_id,
            amount_subunits=amount,
            currency=currency,
            status=status,
            captured=captured,
        )

    def _request_json(self, method, path, payload=None):
        encoded_payload = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            encoded_payload = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        credentials = base64.b64encode(
            f"{self.key_id}:{self.key_secret}".encode("utf-8")
        ).decode("ascii")
        headers["Authorization"] = f"Basic {credentials}"
        request = Request(
            f"{RAZORPAY_API_BASE_URL}{path}",
            data=encoded_payload,
            headers=headers,
            method=method,
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                raw_body = response.read(RAZORPAY_RESPONSE_LIMIT + 1)
        except HTTPError as error:
            if error.code in {401, 403}:
                raise PaymentGatewayAuthenticationError(
                    "Razorpay authentication failed. Check the configured credentials and mode."
                ) from None
            raise PaymentGatewayError(
                f"Razorpay rejected the server request (HTTP {error.code})."
            ) from None
        except (URLError, OSError, TimeoutError):
            raise PaymentGatewayError(
                "Razorpay could not be reached. Please try again shortly."
            ) from None
        if len(raw_body) > RAZORPAY_RESPONSE_LIMIT:
            raise PaymentGatewayError("Razorpay returned an oversized response.")
        try:
            parsed = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise PaymentGatewayError("Razorpay returned an invalid response.") from None
        if not isinstance(parsed, dict):
            raise PaymentGatewayError("Razorpay returned an invalid response.")
        return parsed


def _amount_to_subunits(amount):
    return int(Decimal(amount) * 100)


def mock_payment_is_enabled():
    return settings.DEBUG and settings.PAYMENT_GATEWAY == "mock"


def razorpay_payment_is_enabled():
    if settings.PAYMENT_GATEWAY != "razorpay":
        return False
    try:
        RazorpayPaymentGateway()
    except ImproperlyConfigured:
        return False
    return True


def payment_gateway_is_configured():
    return mock_payment_is_enabled() or razorpay_payment_is_enabled()


def get_payment_gateway():
    if settings.PAYMENT_GATEWAY == "mock":
        if not mock_payment_is_enabled():
            raise ImproperlyConfigured(
                "The mock payment gateway requires DEBUG=True and PAYMENT_GATEWAY=mock."
            )
        return MockPaymentGateway()
    if settings.PAYMENT_GATEWAY == "razorpay":
        return RazorpayPaymentGateway()
    raise ImproperlyConfigured(
        "PAYMENT_GATEWAY must be configured as mock or razorpay."
    )
