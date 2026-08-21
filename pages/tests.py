from decimal import Decimal
from unittest.mock import patch

from django.db import OperationalError
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from schemes.models import SchemePlan


class PublicPageTests(SimpleTestCase):
    def test_home_is_branded(self):
        response = self.client.get(reverse("home"))
        self.assertContains(response, "Jai Shri Krishna Jewellery")
        self.assertContains(
            response, "Plan today. Choose the jewellery you love tomorrow."
        )
        self.assertContains(response, "Two clearly recorded paths to jewellery")
        self.assertContains(
            response,
            "that accumulated metal quantity can be applied toward jewellery",
        )
        self.assertContains(response, "A contribution does not reserve or purchase")
        self.assertContains(response, "It is not a bank deposit")
        self.assertContains(response, "From contribution to jewellery")
        self.assertContains(response, "Lock the rate")
        self.assertContains(response, "A plan measured in gold")
        self.assertContains(response, "A plan measured in silver")
        self.assertNotContains(response, "Build gold grams")
        self.assertNotContains(response, "Build silver grams")
        self.assertContains(response, "BIS-hallmarked jewellery where applicable")
        self.assertContains(response, "Hallmark and HUID verification at purchase")
        self.assertContains(response, "images/home-jewellery.webp")
        self.assertContains(response, "sinu sony / Pexels")
        self.assertContains(response, "bi-currency-rupee")
        self.assertContains(response, "bi-patch-check-fill")
        self.assertNotContains(response, "Cash")
        self.assertNotContains(response, "cash")
        self.assertContains(response, "No public signup")
        self.assertContains(response, f'href="{reverse("pricing")}"')
        self.assertContains(response, "Savings plans")
        self.assertNotContains(response, "Plans &amp; pricing")
        self.assertContains(response, f'href="{reverse("contact")}"')
        self.assertContains(response, f'href="{reverse("account_login")}"')
        self.assertNotContains(response, "Django starter project")

    def test_about_page(self):
        response = self.client.get(reverse("about"))
        self.assertContains(response, "About Jai Shri Krishna Jewellery")
        self.assertContains(response, "accumulated metal quantity may be applied")

    def test_our_story_credits_owner_and_developer(self):
        response = self.client.get(reverse("our_story"))

        self.assertContains(response, "Dilip Kumar")
        self.assertContains(response, "Rajesh Rathod H")
        self.assertContains(response, "Computer science engineer by qualification")
        self.assertContains(response, "Software developer by heart")
        self.assertContains(response, "rajeshrathodh@gmail.com")

    def test_our_story_is_not_linked_from_public_pages(self):
        story_url = reverse("our_story")

        for route_name in ("home", "about"):
            with self.subTest(route_name=route_name):
                response = self.client.get(reverse(route_name))
                self.assertNotContains(response, f'href="{story_url}"')

    def test_public_business_and_policy_pages_are_available(self):
        expected_content = {
            "contact": "No. 155, Azad Road",
            "terms": "Terms and conditions",
            "privacy": "Privacy policy",
            "cancellation_refund": "Cancellation and refund policy",
            "shipping_delivery": "Showroom pickup only",
        }

        for route_name, text in expected_content.items():
            with self.subTest(route_name=route_name):
                response = self.client.get(reverse(route_name))
                self.assertContains(response, text)
                self.assertContains(response, "admin@jaishrikrishnajewellery.com")

    def test_footer_exposes_all_compliance_links(self):
        response = self.client.get(reverse("home"))

        for route_name in (
            "about",
            "contact",
            "pricing",
            "terms",
            "privacy",
            "cancellation_refund",
            "shipping_delivery",
        ):
            self.assertContains(response, f'href="{reverse(route_name)}"')


class PublicPricingPageTests(TestCase):
    def make_plan(self, *, code, active=True, publicly_listed=False, variable=False):
        values = {
            "name": f"Plan {code}",
            "code": code,
            "description": f"Customer description for {code}",
            "minimum_months": 12,
            "default_months": 12,
            "amount_rule": (
                SchemePlan.AmountRule.VARIABLE
                if variable
                else SchemePlan.AmountRule.FIXED
            ),
            "frequency_rule": SchemePlan.FrequencyRule.ONCE_PER_MONTH,
            "fixed_contribution_amount": (
                None if variable else Decimal("1000.00")
            ),
            "minimum_contribution": Decimal("500.00") if variable else Decimal("1000.00"),
            "maximum_contribution": Decimal("5000.00") if variable else Decimal("1000.00"),
            "active": active,
            "publicly_listed": publicly_listed,
        }
        return SchemePlan.objects.create(**values)

    def test_only_active_explicitly_published_plans_are_public(self):
        published = self.make_plan(code="PUBLIC", publicly_listed=True)
        private = self.make_plan(code="PRIVATE", publicly_listed=False)
        inactive = self.make_plan(
            code="INACTIVE", active=False, publicly_listed=True
        )

        response = self.client.get(reverse("pricing"))

        self.assertContains(response, published.name)
        self.assertContains(response, "₹1000.00")
        self.assertNotContains(response, f'href="{reverse("our_story")}"')
        self.assertNotContains(response, private.name)
        self.assertNotContains(response, inactive.name)

    def test_variable_plan_displays_public_inr_range_and_enrolment_flow(self):
        plan = self.make_plan(code="VARIABLE", publicly_listed=True, variable=True)

        response = self.client.get(reverse("pricing"))

        self.assertContains(response, plan.name)
        self.assertContains(response, "₹500.00–₹5000.00")
        self.assertContains(response, "Contact us to enrol")
        self.assertContains(response, "Existing customer login")

    def test_unpublished_plan_is_private_by_default(self):
        plan = self.make_plan(code="DEFAULT")

        self.assertFalse(plan.publicly_listed)
        response = self.client.get(reverse("pricing"))
        self.assertNotContains(response, plan.name)

    def test_pricing_explains_contribution_and_jewellery_redemption(self):
        self.make_plan(code="PUBLIC", publicly_listed=True)

        response = self.client.get(reverse("pricing"))

        self.assertContains(response, "Gold and silver savings schemes")
        self.assertContains(response, "Savings plans with clear terms")
        self.assertContains(response, "The displayed INR amount is a plan contribution")
        self.assertContains(response, "accumulated metal quantity may be applied")
        self.assertNotContains(response, "Cash-plan bonus")


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
