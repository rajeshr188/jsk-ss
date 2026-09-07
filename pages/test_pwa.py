from pathlib import Path

from PIL import Image
from django.conf import settings
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse


@override_settings(PUBLIC_CATALOGUE_ENABLED=False)
class PwaDisabledTests(TestCase):
    @override_settings(PWA_ENABLED=False)
    def test_pwa_routes_and_document_links_are_closed_by_default(self):
        for route_name in ("pwa_manifest", "service_worker", "pwa_offline"):
            with self.subTest(route_name=route_name):
                self.assertEqual(self.client.get(reverse(route_name)).status_code, 404)

        response = self.client.get(reverse("home"))
        self.assertNotContains(response, 'rel="manifest"')
        self.assertContains(response, "js/pwa.js")
        self.assertContains(response, 'data-pwa-enabled="false"')

        registration_source = (
            Path(settings.BASE_DIR) / "static" / "js" / "pwa.js"
        ).read_text(encoding="utf-8")
        self.assertIn("getRegistrations()", registration_source)
        self.assertIn("registration.unregister()", registration_source)
        self.assertIn('name.startsWith("jsk-pwa-static-")', registration_source)


@override_settings(PWA_ENABLED=True, PUBLIC_CATALOGUE_ENABLED=False)
class PwaFoundationTests(SimpleTestCase):
    def test_manifest_has_installability_and_brand_fields(self):
        response = self.client.get(reverse("pwa_manifest"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/manifest+json")
        self.assertEqual(response["Cache-Control"], "no-cache")
        manifest = response.json()
        self.assertEqual(manifest["id"], "/")
        self.assertEqual(manifest["start_url"], "/")
        self.assertEqual(manifest["scope"], "/")
        self.assertEqual(manifest["display"], "standalone")
        self.assertEqual(manifest["theme_color"], "#2d1811")
        self.assertEqual(manifest["background_color"], "#f8f5ef")
        self.assertFalse(manifest["prefer_related_applications"])
        self.assertEqual(
            {(icon["sizes"], icon["purpose"]) for icon in manifest["icons"]},
            {("192x192", "any"), ("512x512", "any maskable")},
        )

    def test_icon_files_have_declared_dimensions(self):
        for size in (192, 512):
            with self.subTest(size=size):
                path = Path(settings.BASE_DIR) / "static" / "images" / f"pwa-icon-{size}.png"
                with Image.open(path) as icon:
                    self.assertEqual(icon.size, (size, size))
                    self.assertEqual(icon.format, "PNG")

    def test_service_worker_is_updateable_and_network_only_for_navigation(self):
        response = self.client.get(reverse("service_worker"))
        source = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/javascript")
        self.assertEqual(
            response["Cache-Control"], "no-cache, no-store, must-revalidate"
        )
        self.assertEqual(response["Service-Worker-Allowed"], "/")
        self.assertIn('request.method !== "GET"', source)
        self.assertIn('request.mode !== "navigate"', source)
        self.assertIn('fetch(request, { cache: "no-store" })', source)
        self.assertIn('caches.match(OFFLINE_URL', source)
        self.assertNotIn("cache.put(", source)
        self.assertNotIn("backgroundsync", source.lower())
        self.assertNotIn("indexeddb", source.lower())
        self.assertNotIn("/accounts/", source)
        self.assertNotIn("/scheme/", source)
        self.assertNotIn("/health/", source)
        self.assertNotIn("css/base.css", source)
        self.assertIn("images/pwa-icon-192.png", source)
        self.assertIn("images/pwa-icon-512.png", source)

    def test_offline_page_is_generic_and_dependency_free(self):
        response = self.client.get(reverse("pwa_offline"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "public, max-age=86400")
        self.assertEqual(response["X-Robots-Tag"], "noindex, nofollow")
        self.assertContains(response, "Connection required")
        self.assertContains(response, "Nothing was submitted while you were offline")
        self.assertNotContains(response, "bootstrap")
        self.assertNotContains(response, "csrfmiddlewaretoken")

    def test_base_document_enables_manifest_and_worker_registration(self):
        response = self.client.get(reverse("home"))

        self.assertContains(response, f'href="{reverse("pwa_manifest")}"')
        self.assertContains(response, "images/pwa-icon-192.png")
        self.assertContains(response, "js/pwa.js")
        self.assertContains(response, 'data-pwa-enabled="true"')

    def test_pwa_endpoints_are_read_only(self):
        for route_name in ("pwa_manifest", "service_worker", "pwa_offline"):
            with self.subTest(route_name=route_name):
                self.assertEqual(self.client.post(reverse(route_name)).status_code, 405)
