from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils import timezone

from .models import RateSnapshot


RATE_QUANTUM = Decimal("0.0001")
PURITY_QUANTUM = Decimal("0.0001")


@dataclass(frozen=True)
class MetalRateQuote:
    metal: str
    provider: str
    provider_timestamp: datetime
    provider_rate: Decimal
    applied_rate: Decimal
    purity: Decimal


class MetalRateProvider(ABC):
    @abstractmethod
    def get_rate(self, metal):
        raise NotImplementedError


class MockMetalRateProvider(MetalRateProvider):
    name = "mock"

    rate_settings = {
        RateSnapshot.Metal.GOLD: ("MOCK_GOLD_RATE", "MOCK_GOLD_PURITY"),
        RateSnapshot.Metal.SILVER: ("MOCK_SILVER_RATE", "MOCK_SILVER_PURITY"),
    }

    def get_rate(self, metal):
        try:
            rate_setting, purity_setting = self.rate_settings[metal]
        except KeyError:
            raise ImproperlyConfigured(f"Unsupported mock metal: {metal}") from None

        try:
            rate = Decimal(str(getattr(settings, rate_setting))).quantize(
                RATE_QUANTUM, rounding=ROUND_HALF_UP
            )
            purity = Decimal(str(getattr(settings, purity_setting))).quantize(
                PURITY_QUANTUM, rounding=ROUND_HALF_UP
            )
        except (InvalidOperation, TypeError, ValueError):
            raise ImproperlyConfigured(
                f"{rate_setting} and {purity_setting} must be valid decimals."
            ) from None
        if rate <= 0:
            raise ImproperlyConfigured(f"{rate_setting} must be greater than zero.")
        if purity <= 0 or purity > 1:
            raise ImproperlyConfigured(f"{purity_setting} must be greater than 0 and at most 1.")

        return MetalRateQuote(
            metal=metal,
            provider=self.name,
            provider_timestamp=timezone.now(),
            provider_rate=rate,
            applied_rate=rate,
            purity=purity,
        )


def mock_metal_rate_is_enabled():
    return settings.DEBUG and settings.METAL_RATE_PROVIDER == "mock"


def get_metal_rate_provider():
    if not mock_metal_rate_is_enabled():
        raise ImproperlyConfigured(
            "Mock metal rates require DEBUG=True and METAL_RATE_PROVIDER=mock."
        )
    return MockMetalRateProvider()
