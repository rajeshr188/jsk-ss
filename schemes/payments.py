import uuid
from dataclasses import dataclass

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


@dataclass(frozen=True)
class PaymentResult:
    successful: bool
    verified: bool
    gateway_reference: str


class MockPaymentGateway:
    name = "mock"

    def charge(self, contribution):
        return PaymentResult(
            successful=True,
            verified=True,
            gateway_reference=f"mock_{uuid.uuid4().hex}",
        )


def mock_payment_is_enabled():
    return settings.DEBUG and settings.PAYMENT_GATEWAY == "mock"


def get_payment_gateway():
    if not mock_payment_is_enabled():
        raise ImproperlyConfigured(
            "The mock payment gateway requires DEBUG=True and PAYMENT_GATEWAY=mock."
        )
    return MockPaymentGateway()
