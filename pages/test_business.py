import json
import re
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from django_project.settings import validate_google_business_profile_url
from .business import showroom_details, showroom_structured_data


class GoogleBusinessProfileUrlTests(SimpleTestCase):
    def test_blank_or_public_google_maps_links_are_accepted(self):
        for value in (
            "", "  ", "https://maps.app.goo.gl/example",
            "https://www.google.com/maps/place/Example/",
            "https://www.google.co.in/maps?cid=123",
            "https://g.page/example", "https://share.google/example",
        ):
            with self.subTest(value=value):
                self.assertEqual(validate_google_business_profile_url(value), value.strip())

    def test_non_google_unsafe_or_private_management_links_are_rejected(self):
        for value in (
            "javascript:alert(1)", "http://maps.app.goo.gl/example",
            "https://maps.app.goo.gl.evil.invalid/example",
            "https://maps.app.goo.gl@evil.invalid/example",
            "https://user:password@maps.app.goo.gl/example",
            "https://business.google.com/locations",
            "https://www.google.com/url?q=https://evil.invalid",
            "https://maps.app.goo.gl/", "https://[invalid",
            'https://maps.app.goo.gl/example\"><script>alert(1)</script>',
        ):
            with self.subTest(value=value):
                with self.assertRaises(ImproperlyConfigured):
                    validate_google_business_profile_url(value)


@override_settings(GOOGLE_BUSINESS_PROFILE_URL="")
class ShowroomMetadataTests(SimpleTestCase):
    def test_metadata_uses_reviewed_identity_without_invented_claims(self):
        data = json.loads(showroom_structured_data())
        self.assertEqual(data["@type"], "JewelryStore")
        self.assertEqual(data["@id"], "https://jaishrikrishnajewellery.com/#showroom")
        self.assertEqual(data["name"], "Jai Sri Krishna Jewellery")
        self.assertEqual(data["telephone"], "+919489481436")
        self.assertEqual(data["address"]["postalCode"], "632001")
        self.assertEqual(data["address"]["addressCountry"], "IN")
        for key in ("sameAs", "hasMap", "aggregateRating", "review", "geo", "image", "offers", "priceRange"):
            self.assertNotIn(key, data)
        weekday, sunday = data["openingHoursSpecification"]
        self.assertEqual(len(weekday["dayOfWeek"]), 6)
        self.assertEqual((weekday["opens"], weekday["closes"]), ("09:00", "21:00"))
        self.assertEqual(sunday["dayOfWeek"], ["https://schema.org/Sunday"])
        self.assertEqual((sunday["opens"], sunday["closes"]), ("09:00", "13:00"))

    def test_directions_use_the_public_address_without_a_customer_origin(self):
        details = showroom_details()
        url = urlparse(details["directions_url"])
        self.assertEqual(url.netloc, "www.google.com")
        self.assertEqual(url.path, "/maps/dir/")
        self.assertEqual(parse_qs(url.query), {
            "api": ["1"],
            "destination": [f'{details["name"]}, {details["full_address"]}'],
        })

    def test_json_ld_cannot_terminate_its_script_element(self):
        details = showroom_details()
        details["name"] = '</script><script>alert("unsafe")</script>&'
        with patch("pages.business.showroom_details", return_value=details):
            serialized = showroom_structured_data()
        self.assertNotIn("<", serialized)
        self.assertNotIn(">", serialized)
        self.assertNotIn("&", serialized)
        self.assertEqual(json.loads(serialized)["name"], details["name"])


@override_settings(PUBLIC_CATALOGUE_ENABLED=False, PUBLIC_BLOG_ENABLED=False)
class ShowroomPageTests(TestCase):
    def metadata(self, response):
        matches = re.findall(
            r'<script type="application/ld\+json" id="showroom-structured-data">(.*?)</script>',
            response.content.decode(), re.DOTALL,
        )
        self.assertEqual(len(matches), 1)
        return json.loads(matches[0])

    @override_settings(GOOGLE_BUSINESS_PROFILE_URL="https://maps.app.goo.gl/example")
    def test_profile_links_and_matching_metadata_on_home_and_contact(self):
        for route in ("home", "contact"):
            with self.subTest(route=route):
                response = self.client.get(reverse(route))
                data = self.metadata(response)
                self.assertEqual(data["sameAs"], ["https://maps.app.goo.gl/example"])
                self.assertEqual(data["hasMap"], data["sameAs"][0])
                self.assertContains(response, data["name"])
                self.assertContains(response, data["address"]["streetAddress"])
                self.assertContains(response, "9:00 AM–9:00 PM")
                self.assertContains(response, "9:00 AM–1:00 PM")
                self.assertContains(response, 'href="https://maps.app.goo.gl/example" target="_blank" rel="noopener noreferrer"', count=2)
                self.assertContains(response, "opens in a new tab")
                self.assertNotContains(response, "Google-certified")
                self.assertNotContains(response, "maps.googleapis.com")
                self.assertNotContains(response, "<iframe")
        self.assertContains(self.client.get(reverse("contact")), "Read reviews on Google")
        self.assertContains(self.client.get(reverse("home")), "Find our showroom on Google")

    @override_settings(GOOGLE_BUSINESS_PROFILE_URL="")
    def test_no_placeholder_profile_links_when_not_configured(self):
        for route in ("home", "contact"):
            response = self.client.get(reverse(route))
            self.assertNotContains(response, "Find our showroom on Google")
            self.assertNotContains(response, "Read reviews on Google")
            self.assertNotContains(response, "Find us on Google Maps")
            self.assertNotIn("sameAs", self.metadata(response))
        self.assertContains(self.client.get(reverse("contact")), "Get directions")

    @override_settings(GOOGLE_BUSINESS_PROFILE_URL="https://maps.app.goo.gl/example")
    def test_metadata_is_not_injected_into_authentication_or_policy_pages(self):
        for route in ("account_login", "privacy", "pricing"):
            response = self.client.get(reverse(route))
            self.assertNotContains(response, 'id="showroom-structured-data"')

    @override_settings(GOOGLE_BUSINESS_PROFILE_URL="")
    def test_schema_identity_does_not_follow_the_request_host(self):
        response = self.client.get(reverse("contact"), HTTP_HOST="localhost")
        self.assertEqual(self.metadata(response)["url"], "https://jaishrikrishnajewellery.com/")
