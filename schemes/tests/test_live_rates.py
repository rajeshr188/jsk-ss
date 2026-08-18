from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from schemes.models import Contribution, MetalAllocation, RateSnapshot, SchemeAccount, SchemePlan
from schemes.rates import (
    GoldApiMetalRateProvider,
    MetalRateProviderError,
    get_metal_rate_provider,
    metal_rate_provider_is_configured,
)
from schemes.services import create_customer, enroll_customer, process_mock_contribution


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self, limit):
        return self.payload[:limit]


def gold_payload(*, metal=b"XAU", currency=b"INR", rate=b"12750.26275"):
    return (
        b'{"timestamp":1767225600,"metal":"'
        + metal
        + b'","currency":"'
        + currency
        + b'","price_gram_24k":'
        + rate
        + b"}"
    )


@override_settings(
    METAL_RATE_PROVIDER="goldapi",
    GOLDAPI_API_KEY="test-secret-token",
    GOLDAPI_TIMEOUT_SECONDS="5",
    GOLDAPI_CACHE_SECONDS="0",
)
class GoldApiMetalRateProviderTests(SimpleTestCase):
    def test_gold_quote_uses_header_auth_inr_gram_rate_and_provider_timestamp(self):
        calls = []

        def http_open(request, timeout):
            calls.append((request, timeout))
            return FakeResponse(gold_payload())

        quote = GoldApiMetalRateProvider(http_open=http_open).get_rate(
            RateSnapshot.Metal.GOLD
        )

        request, timeout = calls[0]
        headers = {key.lower(): value for key, value in request.header_items()}
        self.assertEqual(request.full_url, "https://www.goldapi.io/api/XAU/INR")
        self.assertEqual(headers["x-access-token"], "test-secret-token")
        self.assertNotIn("test-secret-token", request.full_url)
        self.assertEqual(timeout, 5.0)
        self.assertEqual(quote.provider, "goldapi")
        self.assertEqual(quote.provider_rate, Decimal("12750.2628"))
        self.assertEqual(quote.applied_rate, Decimal("12750.2628"))
        self.assertEqual(quote.purity, Decimal("0.9999"))
        self.assertEqual(
            quote.provider_timestamp,
            datetime.fromtimestamp(1767225600, tz=UTC),
        )

    def test_silver_quote_uses_xag_and_silver_purity(self):
        calls = []

        def http_open(request, timeout):
            calls.append(request.full_url)
            return FakeResponse(
                gold_payload(metal=b"XAG", rate=b"184.33634")
            )

        quote = GoldApiMetalRateProvider(http_open=http_open).get_rate(
            RateSnapshot.Metal.SILVER
        )

        self.assertEqual(calls, ["https://www.goldapi.io/api/XAG/INR"])
        self.assertEqual(quote.provider_rate, Decimal("184.3363"))
        self.assertEqual(quote.purity, Decimal("0.9990"))

    @override_settings(GOLDAPI_CACHE_SECONDS="60")
    def test_short_cache_avoids_duplicate_provider_requests(self):
        cache.clear()
        call_count = 0

        def http_open(request, timeout):
            nonlocal call_count
            call_count += 1
            return FakeResponse(gold_payload())

        provider = GoldApiMetalRateProvider(http_open=http_open)
        first = provider.get_rate(RateSnapshot.Metal.GOLD)
        second = provider.get_rate(RateSnapshot.Metal.GOLD)

        self.assertEqual(first, second)
        self.assertEqual(call_count, 1)
        cache.clear()

    def test_http_and_network_failures_become_safe_provider_errors(self):
        failures = [
            HTTPError("https://example.invalid", 503, "Unavailable", None, None),
            URLError("offline"),
            TimeoutError(),
        ]
        for failure in failures:
            with self.subTest(failure=type(failure).__name__):
                def http_open(request, timeout):
                    raise failure

                with self.assertRaises(MetalRateProviderError) as raised:
                    GoldApiMetalRateProvider(http_open=http_open).get_rate(
                        RateSnapshot.Metal.GOLD
                    )
                self.assertNotIn("test-secret-token", str(raised.exception))

    def test_invalid_responses_are_rejected(self):
        payloads = [
            b"not-json",
            gold_payload(metal=b"XAG"),
            gold_payload(currency=b"USD"),
            gold_payload(rate=b"0"),
            b'{"metal":"XAU","currency":"INR"}',
        ]
        for payload in payloads:
            with self.subTest(payload=payload):
                provider = GoldApiMetalRateProvider(
                    http_open=lambda request, timeout: FakeResponse(payload)
                )
                with self.assertRaises(MetalRateProviderError):
                    provider.get_rate(RateSnapshot.Metal.GOLD)

    def test_provider_resolution_allows_live_rates_outside_debug(self):
        with override_settings(DEBUG=False):
            provider = get_metal_rate_provider()
        self.assertIsInstance(provider, GoldApiMetalRateProvider)
        self.assertTrue(metal_rate_provider_is_configured())

    @override_settings(GOLDAPI_API_KEY="")
    def test_live_provider_requires_api_key(self):
        self.assertFalse(metal_rate_provider_is_configured())
        with self.assertRaises(ImproperlyConfigured):
            get_metal_rate_provider()

    @override_settings(GOLDAPI_TIMEOUT_SECONDS="60")
    def test_timeout_is_bounded(self):
        with self.assertRaises(ImproperlyConfigured):
            GoldApiMetalRateProvider()


@override_settings(
    DEBUG=True,
    PAYMENT_GATEWAY="mock",
    METAL_RATE_PROVIDER="goldapi",
    GOLDAPI_API_KEY="integration-secret-token",
    GOLDAPI_TIMEOUT_SECONDS="5",
    GOLDAPI_CACHE_SECONDS="0",
)
class LiveRateAllocationIntegrationTests(TestCase):
    def setUp(self):
        customer = create_customer(
            full_name="Live Rate Customer",
            email="live-rate@example.com",
            mobile_number="9000000060",
            password="customer-password-strong",
        )
        plan = SchemePlan.objects.create(
            name="Live Gold Flexible",
            code="LIVE-GOLD",
            amount_rule=SchemePlan.AmountRule.VARIABLE,
            frequency_rule=SchemePlan.FrequencyRule.FLEXIBLE,
            minimum_contribution=Decimal("1000.00"),
            maximum_contribution=Decimal("100000.00"),
        )
        self.account = enroll_customer(
            customer=customer,
            plan=plan,
            savings_mode=SchemeAccount.SavingsMode.GOLD,
            start_date=timezone.localdate(),
        )

    @patch("schemes.rates.urlopen")
    def test_live_quote_is_snapshotted_and_allocated(self, mocked_open):
        mocked_open.return_value = FakeResponse(gold_payload())

        contribution = process_mock_contribution(
            scheme_account=self.account,
            amount=Decimal("10000.00"),
        )

        expected_quantity = (
            Decimal("10000.00") / Decimal("12750.2628")
        ).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
        contribution.refresh_from_db()
        allocation = contribution.metal_allocation
        self.assertEqual(contribution.status, Contribution.Status.PAID)
        self.assertEqual(allocation.quantity, expected_quantity)
        self.assertEqual(allocation.rate_snapshot.provider, "goldapi")
        self.assertEqual(
            allocation.rate_snapshot.provider_rate, Decimal("12750.2628")
        )

    @patch("schemes.rates.urlopen", side_effect=URLError("offline"))
    def test_live_outage_preserves_verified_payment_for_retry(self, mocked_open):
        contribution = process_mock_contribution(
            scheme_account=self.account,
            amount=Decimal("10000.00"),
        )

        contribution.refresh_from_db()
        self.assertEqual(contribution.status, Contribution.Status.PAID_UNALLOCATED)
        self.assertIn("could not be reached", contribution.allocation_error)
        self.assertFalse(MetalAllocation.objects.exists())
