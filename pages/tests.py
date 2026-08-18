from unittest.mock import patch

from django.db import OperationalError
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse


class PublicPageTests(SimpleTestCase):
    def test_home_is_branded(self):
        response = self.client.get(reverse("home"))
        self.assertContains(response, "Jai Shri Krishna Jewellery")
        self.assertNotContains(response, "Django starter project")

    def test_about_page(self):
        response = self.client.get(reverse("about"))
        self.assertContains(response, "About our savings scheme")


@override_settings(APP_RELEASE="test-release")
class HealthEndpointTests(TestCase):
    def test_liveness_reports_release_without_caching(self):
        response = self.client.get(reverse("health_live"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "release": "test-release"})
        self.assertEqual(response["Cache-Control"], "no-store")

    def test_readiness_checks_database(self):
        response = self.client.get(reverse("health_ready"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "release": "test-release"})

    @patch("pages.views.connection.cursor", side_effect=OperationalError("private detail"))
    def test_readiness_returns_sanitized_service_unavailable(self, cursor):
        response = self.client.get(reverse("health_ready"))

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json(),
            {"status": "unavailable", "release": "test-release"},
        )
        self.assertNotContains(response, "private detail", status_code=503)
        self.assertEqual(response["Cache-Control"], "no-store")

    def test_health_endpoints_reject_post(self):
        self.assertEqual(self.client.post(reverse("health_live")).status_code, 405)
        self.assertEqual(self.client.post(reverse("health_ready")).status_code, 405)
