from pathlib import Path

from PIL import Image
from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse


PLAY_APP_SIGNING_SHA256_REGISTERED = (
    "25:78:42:37:4E:7A:C9:62:C8:AF:90:11:E3:8C:86:32:"
    "E2:08:DF:E4:6E:77:C0:86:59:7F:31:E7:32:D7:07:97"
)
PLAY_APP_SIGNING_SHA256_DELIVERED = (
    "B8:A3:25:32:0B:80:2C:2A:E1:9B:EA:F7:30:27:C4:89:"
    "E5:2D:D6:1F:E4:60:F2:99:2F:6E:C6:54:14:24:17:B4"
)
UPLOAD_KEY_SHA256 = (
    "F1:EF:0D:80:86:ED:08:9B:D1:3E:41:FF:03:F4:E3:06:"
    "7D:31:7D:AD:AB:73:F1:C3:37:C7:BC:7D:F5:C8:2B:A6"
)


class AndroidAssetLinksTests(TestCase):
    @override_settings(ANDROID_TWA_ASSET_LINKS_ENABLED=False)
    def test_asset_links_is_closed_by_default(self):
        self.assertEqual(
            self.client.get("/.well-known/assetlinks.json").status_code,
            404,
        )

    @override_settings(ANDROID_TWA_ASSET_LINKS_ENABLED=True)
    def test_asset_links_binds_only_the_play_signed_customer_app(self):
        response = self.client.get("/.well-known/assetlinks.json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertEqual(response["Cache-Control"], "public, max-age=3600")
        self.assertEqual(response["X-Robots-Tag"], "noindex, nofollow")
        self.assertEqual(
            response.json(),
            [
                {
                    "relation": ["delegate_permission/common.handle_all_urls"],
                    "target": {
                        "namespace": "android_app",
                        "package_name": "com.jaishrikrishnajewellery.savings",
                        "sha256_cert_fingerprints": [
                            PLAY_APP_SIGNING_SHA256_REGISTERED,
                            PLAY_APP_SIGNING_SHA256_DELIVERED,
                        ],
                    },
                }
            ],
        )
        fingerprints = response.json()[0]["target"]["sha256_cert_fingerprints"]
        self.assertEqual(len(fingerprints), 2)
        self.assertEqual(len(set(fingerprints)), len(fingerprints))
        self.assertNotIn(UPLOAD_KEY_SHA256, fingerprints)
        for fingerprint in fingerprints:
            with self.subTest(fingerprint=fingerprint):
                self.assertEqual(len(fingerprint.split(":")), 32)
                self.assertRegex(fingerprint, r"^(?:[0-9A-F]{2}:){31}[0-9A-F]{2}$")
        self.assertEqual(
            reverse("android_asset_links"),
            "/.well-known/assetlinks.json",
        )

    @override_settings(ANDROID_TWA_ASSET_LINKS_ENABLED=True)
    def test_asset_links_is_read_only(self):
        self.assertEqual(
            self.client.post("/.well-known/assetlinks.json").status_code,
            405,
        )


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
class PwaFoundationTests(TestCase):
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

        self.assertContains(response, "viewport-fit=cover")
        self.assertContains(response, f'href="{reverse("pwa_manifest")}"')
        self.assertContains(response, "images/pwa-icon-192.png")
        self.assertContains(response, "js/pwa.js")
        self.assertContains(response, 'data-pwa-enabled="true"')

        responsive_source = (
            Path(settings.BASE_DIR) / "static" / "css" / "base.css"
        ).read_text(encoding="utf-8")
        self.assertIn("env(safe-area-inset-top)", responsive_source)
        self.assertIn("env(safe-area-inset-bottom)", responsive_source)
        self.assertIn("min-height: 2.75rem", responsive_source)

    def test_pwa_endpoints_are_read_only(self):
        for route_name in ("pwa_manifest", "service_worker", "pwa_offline"):
            with self.subTest(route_name=route_name):
                self.assertEqual(self.client.post(reverse(route_name)).status_code, 405)
