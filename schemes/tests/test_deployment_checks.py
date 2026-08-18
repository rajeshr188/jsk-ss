from django.test import SimpleTestCase, override_settings

from schemes.checks import production_configuration


class ProductionConfigurationCheckTests(SimpleTestCase):
    def issue_ids(self):
        return {issue.id for issue in production_configuration(None)}

    @override_settings(
        PAYMENT_GATEWAY="mock",
        METAL_RATE_PROVIDER="mock",
        EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend",
        ALLOWED_HOSTS=["*"],
        CSRF_TRUSTED_ORIGINS=["http://example.com"],
    )
    def test_unsafe_production_adapters_and_origins_are_errors(self):
        self.assertTrue(
            {"jsk.E001", "jsk.E002", "jsk.E003", "jsk.E004", "jsk.E005"}
            <= self.issue_ids()
        )

    @override_settings(
        PAYMENT_GATEWAY="razorpay",
        RAZORPAY_KEY_ID="rzp_test_example",
        RAZORPAY_KEY_SECRET="not-a-real-secret",
        RAZORPAY_WEBHOOK_SECRET="not-a-real-webhook-secret",
        METAL_RATE_PROVIDER="goldapi",
        GOLDAPI_API_KEY="not-a-real-token",
        EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend",
        EMAIL_HOST="smtp.example.com",
        ALLOWED_HOSTS=["savings.example.com"],
        CSRF_TRUSTED_ORIGINS=["https://savings.example.com"],
        APP_RELEASE="abc123",
        DATABASES={"default": {"OPTIONS": {"sslmode": "require"}}},
    )
    def test_production_configuration_can_pass(self):
        self.assertEqual(production_configuration(None), [])

    @override_settings(
        APP_RELEASE="unknown",
        DATABASES={"default": {"OPTIONS": {"sslmode": "prefer"}}},
    )
    def test_release_and_database_transport_are_warnings(self):
        self.assertTrue({"jsk.W001", "jsk.W002"} <= self.issue_ids())

    @override_settings(
        PAYMENT_GATEWAY="razorpay",
        RAZORPAY_KEY_ID="",
        RAZORPAY_KEY_SECRET="",
        RAZORPAY_WEBHOOK_SECRET="",
        METAL_RATE_PROVIDER="goldapi",
        GOLDAPI_API_KEY="",
    )
    def test_missing_provider_credentials_are_errors(self):
        self.assertTrue({"jsk.E006", "jsk.E009"} <= self.issue_ids())
