from django.test import SimpleTestCase, override_settings

from schemes.checks import production_configuration


class ProductionConfigurationCheckTests(SimpleTestCase):
    def issue_ids(self):
        return {issue.id for issue in production_configuration(None)}

    @override_settings(
        PAYMENT_GATEWAY="mock",
        EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend",
        ALLOWED_HOSTS=["*"],
        CSRF_TRUSTED_ORIGINS=["http://example.com"],
    )
    def test_unsafe_production_adapters_and_origins_are_errors(self):
        self.assertTrue(
            {"jsk.E001", "jsk.E003", "jsk.E004", "jsk.E005"}
            <= self.issue_ids()
        )

    @override_settings(
        DEBUG=False,
        PAYMENT_GATEWAY="razorpay",
        RAZORPAY_KEY_ID="rzp_test_example",
        RAZORPAY_KEY_SECRET="not-a-real-secret",
        RAZORPAY_WEBHOOK_SECRET="not-a-real-webhook-secret",
        EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend",
        EMAIL_HOST="smtp.example.com",
        ALLOWED_HOSTS=["savings.example.com"],
        CSRF_TRUSTED_ORIGINS=["https://savings.example.com"],
        MEDIA_STORAGE_BACKEND="r2",
        R2_CUSTOM_DOMAIN="media.savings.example.com",
        WAGTAILDOCS_SERVE_METHOD="serve_view",
        APP_RELEASE="abc123",
        DATABASES={"default": {"OPTIONS": {"sslmode": "require"}}},
    )
    def test_production_configuration_can_pass(self):
        self.assertEqual(production_configuration(None), [])

    @override_settings(DEBUG=True)
    def test_debug_is_rejected_for_production(self):
        self.assertIn("jsk.E015", self.issue_ids())

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
    )
    def test_missing_payment_credentials_are_errors(self):
        self.assertIn("jsk.E006", self.issue_ids())

    @override_settings(
        MEDIA_STORAGE_BACKEND="filesystem",
        R2_CUSTOM_DOMAIN="",
    )
    def test_local_media_storage_is_rejected_for_production(self):
        self.assertIn("jsk.E012", self.issue_ids())

    @override_settings(
        MEDIA_STORAGE_BACKEND="r2",
        R2_CUSTOM_DOMAIN="temporary.r2.dev",
    )
    def test_r2_development_domain_is_rejected_for_production(self):
        self.assertIn("jsk.E013", self.issue_ids())

    @override_settings(WAGTAILDOCS_SERVE_METHOD="redirect")
    def test_direct_document_serving_is_rejected_for_production(self):
        self.assertIn("jsk.E014", self.issue_ids())
