from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured
from django.utils import timezone

from .models import RateSnapshot


RATE_QUANTUM = Decimal("0.0001")
PURITY_QUANTUM = Decimal("0.0001")
MAX_RESPONSE_BYTES = 64 * 1024


class MetalRateProviderError(Exception):
    """A live rate could not be obtained or validated."""


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


class GoldApiMetalRateProvider(MetalRateProvider):
    name = "goldapi"
    base_url = "https://www.goldapi.io/api"
    symbols = {
        RateSnapshot.Metal.GOLD: "XAU",
        RateSnapshot.Metal.SILVER: "XAG",
    }
    purities = {
        RateSnapshot.Metal.GOLD: Decimal("0.9999"),
        RateSnapshot.Metal.SILVER: Decimal("0.9990"),
    }

    def __init__(self, *, api_key=None, http_open=None):
        self.api_key = (
            settings.GOLDAPI_API_KEY if api_key is None else str(api_key).strip()
        )
        if not self.api_key:
            raise ImproperlyConfigured(
                "GOLDAPI_API_KEY must be set when METAL_RATE_PROVIDER=goldapi."
            )
        self.timeout = _decimal_setting(
            "GOLDAPI_TIMEOUT_SECONDS",
            minimum=Decimal("0.1"),
            maximum=Decimal("30"),
        )
        cache_seconds = _decimal_setting(
            "GOLDAPI_CACHE_SECONDS",
            minimum=Decimal("0"),
            maximum=Decimal("3600"),
        )
        if cache_seconds != cache_seconds.to_integral_value():
            raise ImproperlyConfigured("GOLDAPI_CACHE_SECONDS must be a whole number.")
        self.cache_seconds = int(cache_seconds)
        self.http_open = http_open or urlopen

    def get_rate(self, metal):
        try:
            symbol = self.symbols[metal]
            purity = self.purities[metal]
        except KeyError:
            raise ImproperlyConfigured(f"Unsupported GoldAPI metal: {metal}") from None

        cache_key = f"schemes:goldapi:INR:{symbol}"
        if self.cache_seconds:
            cached_quote = cache.get(cache_key)
            if cached_quote is not None:
                return cached_quote

        request = Request(
            f"{self.base_url}/{symbol}/INR",
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "JaiShriKrishnaSavings/0.1",
                "x-access-token": self.api_key,
            },
            method="GET",
        )
        try:
            with self.http_open(request, timeout=float(self.timeout)) as response:
                payload = response.read(MAX_RESPONSE_BYTES + 1)
        except HTTPError as error:
            raise MetalRateProviderError(
                f"GoldAPI request failed with HTTP status {error.code}."
            ) from None
        except (TimeoutError, URLError, OSError):
            raise MetalRateProviderError(
                "GoldAPI could not be reached within the configured timeout."
            ) from None
        if len(payload) > MAX_RESPONSE_BYTES:
            raise MetalRateProviderError("GoldAPI returned an unexpectedly large response.")

        try:
            data = json.loads(payload.decode("utf-8"), parse_float=Decimal)
            if str(data["metal"]).upper() != symbol:
                raise ValueError
            if str(data["currency"]).upper() != "INR":
                raise ValueError
            provider_timestamp = datetime.fromtimestamp(int(data["timestamp"]), tz=UTC)
            rate = Decimal(str(data["price_gram_24k"])).quantize(
                RATE_QUANTUM, rounding=ROUND_HALF_UP
            )
        except (
            json.JSONDecodeError,
            KeyError,
            TypeError,
            ValueError,
            InvalidOperation,
            OSError,
            OverflowError,
        ):
            raise MetalRateProviderError(
                "GoldAPI returned an invalid metal-rate response."
            ) from None
        if rate <= 0:
            raise MetalRateProviderError("GoldAPI returned a non-positive per-gram rate.")

        quote = MetalRateQuote(
            metal=metal,
            provider=self.name,
            provider_timestamp=provider_timestamp,
            provider_rate=rate,
            applied_rate=rate,
            purity=purity,
        )
        if self.cache_seconds:
            cache.set(cache_key, quote, self.cache_seconds)
        return quote


def _decimal_setting(name, *, minimum, maximum):
    try:
        value = Decimal(str(getattr(settings, name)))
    except (InvalidOperation, TypeError, ValueError):
        raise ImproperlyConfigured(f"{name} must be a valid number.") from None
    if value < minimum or value > maximum:
        raise ImproperlyConfigured(
            f"{name} must be between {minimum} and {maximum}."
        )
    return value


def mock_metal_rate_is_enabled():
    return settings.DEBUG and settings.METAL_RATE_PROVIDER == "mock"


def metal_rate_provider_is_configured():
    if settings.METAL_RATE_PROVIDER == "mock":
        return mock_metal_rate_is_enabled()
    if settings.METAL_RATE_PROVIDER == "goldapi":
        return bool(settings.GOLDAPI_API_KEY)
    return False


def get_metal_rate_provider():
    if settings.METAL_RATE_PROVIDER == "mock":
        if mock_metal_rate_is_enabled():
            return MockMetalRateProvider()
        raise ImproperlyConfigured(
            "Mock metal rates require DEBUG=True and METAL_RATE_PROVIDER=mock."
        )
    if settings.METAL_RATE_PROVIDER == "goldapi":
        return GoldApiMetalRateProvider()
    raise ImproperlyConfigured(
        "METAL_RATE_PROVIDER must be configured as mock or goldapi."
    )
