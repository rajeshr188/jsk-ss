"""Owner handbook HTTP contracts; no database, payment or external-service access."""
from html.parser import HTMLParser

from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase, override_settings
from django.urls import resolve, reverse

from accounts.models import CustomUser
from schemes.manual_views import GUIDE_ASSETS, plan_manual, plan_manual_asset


class ManualMarkup(HTMLParser):
    def __init__(self, content):
        super().__init__()
        self.links = []
        self.images = []
        self.ids = []
        self.feed(content)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            self.ids.append(attrs["id"])
        if tag == "a":
            self.links.append(attrs.get("href", ""))
        if tag == "img":
            self.images.append(attrs)


@override_settings(CONFIGURED_PLANS_ENABLED=False)
class PlanManualTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.owner = CustomUser(role=CustomUser.Role.OWNER, is_active=True)
        self.url = reverse("schemes:plan_manual")

    def request(self, user=None, method="get", path=None):
        request = getattr(self.factory, method)(path or self.url)
        request.user = self.owner if user is None else user
        return request

    def test_owner_can_read_with_gate_off_and_no_database_queries(self):
        response = plan_manual(self.request())
        self.assertContains(response, "Owner reference manual")
        self.assertContains(response, "<strong>disabled</strong>", html=True)
        self.assertContains(response, "Create a monthly configuration")
        self.assertContains(response, "The complete builder: separate rules, one final closure")
        self.assertContains(response, "Close the agreement, not the customer")
        self.assertEqual(resolve(self.url).func, plan_manual)

    @override_settings(CONFIGURED_PLANS_ENABLED=True)
    def test_actual_gate_state_is_reported_without_changing_edition(self):
        response = plan_manual(self.request())
        self.assertContains(response, "<strong>enabled</strong>", html=True)
        self.assertContains(response, "Edition 3")
        self.assertContains(response, "26 October 2026")
        self.assertContains(response, "not a live deployment assessment")

    def test_anonymous_is_redirected_without_document_or_image(self):
        for view, args in ((plan_manual, ()), (plan_manual_asset, ("publication.jpg",))):
            with self.subTest(view=view.__name__):
                response = view(self.request(AnonymousUser()), *args)
                self.assertEqual(response.status_code, 302)
                self.assertIn("login", response["Location"])
                self.assertNotIn(b"Owner reference manual", response.content)
                self.assertIn("no-store", response["Cache-Control"])

    def test_customers_staff_and_inactive_owners_cannot_read_either_resource(self):
        users = [
            CustomUser(role=CustomUser.Role.CUSTOMER, is_active=True),
            CustomUser(role=CustomUser.Role.CUSTOMER, is_active=True, is_staff=True),
            CustomUser(role=CustomUser.Role.OWNER, is_active=False),
            CustomUser(is_superuser=True, is_active=False),
        ]
        for user in users:
            for view, args in ((plan_manual, ()), (plan_manual_asset, ("publication.jpg",))):
                with self.subTest(role=user.role, active=user.is_active, view=view.__name__):
                    with self.assertRaises(PermissionDenied):
                        view(self.request(user), *args)

    def test_active_superuser_follows_existing_owner_permission(self):
        response = plan_manual(self.request(CustomUser(is_active=True, is_superuser=True)))
        self.assertEqual(response.status_code, 200)

    def test_safe_methods_only(self):
        for view, args in ((plan_manual, ()), (plan_manual_asset, ("publication.jpg",))):
            for method in ("post", "put", "patch", "delete"):
                with self.subTest(view=view.__name__, method=method):
                    response = view(self.request(method=method), *args)
                    self.assertEqual(response.status_code, 405)
                    self.assertIn("no-store", response["Cache-Control"])
            response = view(self.request(method="head"), *args)
            self.assertEqual(response.status_code, 200)
            response.close()

    def assert_private(self, response):
        self.assertIn("private", response["Cache-Control"])
        self.assertIn("no-store", response["Cache-Control"])
        self.assertIn("Cookie", response["Vary"])
        self.assertIn("noindex", response["X-Robots-Tag"])
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertIn("frame-ancestors 'none'", response["Content-Security-Policy"])

    def test_manual_is_private_script_free_and_has_no_broken_repository_urls(self):
        response = plan_manual(self.request())
        self.assert_private(response)
        content = response.content.decode()
        self.assertNotIn("<script", content)
        self.assertNotIn('href="../../', content)
        self.assertNotIn('src="assets/', content)
        markup = ManualMarkup(content)
        self.assertEqual(len(markup.ids), len(set(markup.ids)))
        self.assertEqual(len(markup.images), 4)
        for link in markup.links:
            if link.startswith("#"):
                self.assertIn(link[1:], markup.ids)
            else:
                self.assertTrue(link.startswith("/scheme/owner/"), link)
                self.assertIsNotNone(resolve(link))
        for image in markup.images:
            self.assertTrue(image["alt"])
            self.assertEqual(resolve(image["src"]).func, plan_manual_asset)

    def test_all_four_assets_are_owner_protected_private_jpegs(self):
        for filename in GUIDE_ASSETS:
            with self.subTest(filename=filename):
                url = reverse("schemes:plan_manual_asset", args=[filename])
                response = plan_manual_asset(self.request(path=url), filename)
                try:
                    self.assert_private(response)
                    self.assertEqual(response["Content-Type"], "image/jpeg")
                    self.assertTrue(b"".join(response.streaming_content).startswith(b"\xff\xd8\xff"))
                finally:
                    response.close()

    def test_asset_allowlist_rejects_path_traversal_and_other_documents(self):
        for filename in ("../index.html", "../../../../.env", "STATUS.md", "index.html", "missing.jpg", "..\\.env"):
            with self.subTest(filename=filename), self.assertRaises(Http404):
                plan_manual_asset(self.request(), filename)

    def test_owner_entry_points_link_to_manual(self):
        for template, context in (
            ("schemes/plan_list.html", {"plans": []}),
            ("schemes/configuration_list.html", {"page": []}),
        ):
            with self.subTest(template=template):
                self.assertIn(f'href="{self.url}"', render_to_string(template, context))
