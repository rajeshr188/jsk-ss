from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import OperationalError
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from wagtail.models import (
    Collection,
    Locale,
    Page,
    PageLogEntry,
    Site,
    WorkflowPage,
    WorkflowState,
)

from catalog.permissions import (
    CATALOG_EDITOR_GROUP,
    catalog_permission_configuration_errors,
)
from pages.models import AboutPage, OurStoryPage
from pages.permissions import (
    EDITORIAL_ADMIN_GROUP,
    EDITORIAL_EDITOR_GROUP,
    EDITORIAL_MEDIA_COLLECTION,
    EDITORIAL_PUBLISHER_GROUP,
    EDITORIAL_ROLES,
    EDITORIAL_WORKFLOW,
    editorial_permission_configuration_errors,
)
from schemes.models import SchemePlan


@override_settings(PUBLIC_CATALOGUE_ENABLED=False)
class PublicPageTests(SimpleTestCase):
    def test_home_is_branded(self):
        response = self.client.get(reverse("home"))
        self.assertContains(response, "Jai Sri Krishna Jewellery")
        self.assertContains(
            response, "Plan today. Choose the jewellery you love tomorrow."
        )
        self.assertContains(
            response,
            "Your INR contributions accumulate a recorded quantity",
        )
        self.assertContains(response, "A contribution does not reserve or purchase")
        self.assertContains(response, "It is not a bank deposit")
        self.assertContains(response, "From contribution to jewellery")
        self.assertContains(response, "Lock the rate")
        self.assertNotContains(response, "Build gold grams")
        self.assertNotContains(response, "Build silver grams")
        self.assertContains(response, "BIS-hallmarked jewellery")
        self.assertContains(response, "Hallmark and HUID verification at purchase")
        self.assertContains(response, "images/home-jewellery.webp")
        self.assertContains(response, "Illustrative jewellery")
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
        self.assertContains(response, "About Jai Sri Krishna Jewellery")
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


class EditorialCmsTests(TestCase):
    password = "correct-horse-battery-staple"

    def setUp(self):
        if not Locale.objects.exists():
            Locale.objects.create(language_code="en")
        root = Page.get_first_root_node()
        if root is None:
            root = Page.add_root(title="Root", slug="root")
        site_root = root.get_children().first()
        if site_root is None:
            site_root = root.add_child(instance=Page(title="Site root", slug="home"))
        Site.objects.update_or_create(
            is_default_site=True,
            defaults={
                "hostname": "testserver",
                "port": 80,
                "root_page": site_root,
            },
        )
        call_command("configure_editorial_pages", verbosity=0)
        self.about = AboutPage.objects.get()
        self.story = OurStoryPage.objects.get()

    def publish(self, page, *, user=None):
        page.save_revision(user=user).publish(user=user)
        page.refresh_from_db()

    def test_configuration_seeds_drafts_and_is_idempotent(self):
        self.assertFalse(self.about.live)
        self.assertFalse(self.story.live)
        self.assertEqual(self.about.slug, "about")
        self.assertEqual(self.story.slug, "our-story")
        self.assertEqual(self.story.developer_name, "Rajesh Rathod H")
        self.assertEqual(self.story.developer_email, "rajeshrathodh@gmail.com")
        self.assertTrue(
            Collection.get_first_root_node()
            .get_children()
            .filter(name=EDITORIAL_MEDIA_COLLECTION)
            .exists()
        )
        self.assertEqual(
            set(Group.objects.filter(name__startswith="Editorial ").values_list("name", flat=True)),
            {role.name for role in EDITORIAL_ROLES},
        )
        self.assertEqual(editorial_permission_configuration_errors(), [])

        self.about.introduction = "Reviewed custom introduction."
        self.about.save_revision()
        call_command("configure_editorial_pages", verbosity=0)
        call_command("configure_editorial_pages", "--check", verbosity=0)

        self.assertEqual(AboutPage.objects.count(), 1)
        self.assertEqual(OurStoryPage.objects.count(), 1)
        self.assertEqual(
            AboutPage.objects.get().get_latest_revision_as_object().introduction,
            "Reviewed custom introduction.",
        )

    @override_settings(PUBLIC_EDITORIAL_PAGES_ENABLED=True)
    def test_draft_pages_keep_reviewed_django_fallbacks(self):
        about_response = self.client.get(reverse("about"))
        story_response = self.client.get(reverse("our_story"))

        self.assertContains(about_response, "About Jai Sri Krishna Jewellery")
        self.assertContains(about_response, "accumulated metal quantity may be applied")
        self.assertContains(story_response, "Dilip Kumar")
        self.assertContains(story_response, "Rajesh Rathod H")

    @override_settings(PUBLIC_EDITORIAL_PAGES_ENABLED=False)
    def test_disabled_rollout_ignores_a_live_cms_revision(self):
        self.about.introduction = "CMS-only introduction marker."
        self.publish(self.about)

        response = self.client.get(reverse("about"))

        self.assertNotContains(response, "CMS-only introduction marker")
        self.assertContains(response, "accumulated metal quantity may be applied")

    @override_settings(PUBLIC_EDITORIAL_PAGES_ENABLED=True)
    def test_live_about_is_served_at_the_stable_named_route(self):
        self.about.introduction = "CMS-managed business introduction."
        self.publish(self.about)

        response = self.client.get(reverse("about"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["page"].specific, self.about)
        self.assertContains(response, "CMS-managed business introduction")
        self.assertContains(response, "accumulated metal quantity may be applied")
        self.assertEqual(reverse("about"), "/about/")

    @override_settings(PUBLIC_EDITORIAL_PAGES_ENABLED=True)
    def test_unpublishing_about_restores_the_static_fallback(self):
        self.about.introduction = "Temporary CMS introduction."
        self.publish(self.about)
        self.about.unpublish()

        response = self.client.get(reverse("about"))

        self.assertNotContains(response, "Temporary CMS introduction")
        self.assertContains(response, "About Jai Sri Krishna Jewellery")

    @override_settings(PUBLIC_EDITORIAL_PAGES_ENABLED=True)
    def test_live_story_uses_cms_content_but_remains_unlinked(self):
        self.story.introduction = "CMS-managed family story."
        self.publish(self.story)

        story_response = self.client.get(reverse("our_story"))
        self.assertContains(story_response, "CMS-managed family story")
        self.assertContains(story_response, "Rajesh Rathod H")

        for route_name in ("home", "about"):
            with self.subTest(route_name=route_name):
                response = self.client.get(reverse(route_name))
                self.assertNotContains(response, f'href="{reverse("our_story")}"')

    def test_profile_images_require_accessible_alt_text(self):
        self.story.business_owner_image_id = 999999
        self.story.business_owner_image_alt = ""

        with self.assertRaises(ValidationError) as raised:
            self.story.clean()

        self.assertIn("business_owner_image_alt", raised.exception.message_dict)

    def test_editorial_roles_are_scoped_to_editorial_pages_and_media(self):
        user_model = get_user_model()
        editor = user_model.objects.create_user(
            username="editorial-editor@example.com",
            email="editorial-editor@example.com",
            password=self.password,
            role=user_model.Role.STAFF,
            is_staff=True,
        )
        publisher = user_model.objects.create_user(
            username="editorial-publisher@example.com",
            email="editorial-publisher@example.com",
            password=self.password,
            role=user_model.Role.STAFF,
            is_staff=True,
        )
        editor.groups.add(Group.objects.get(name=EDITORIAL_EDITOR_GROUP))
        publisher.groups.add(Group.objects.get(name=EDITORIAL_PUBLISHER_GROUP))

        self.assertTrue(self.about.permissions_for_user(editor).can_edit())
        self.assertFalse(self.about.permissions_for_user(editor).can_publish())
        self.assertTrue(self.story.permissions_for_user(publisher).can_publish())
        self.assertFalse(
            Site.objects.get(is_default_site=True)
            .root_page.permissions_for_user(editor)
            .can_edit()
        )
        self.assertEqual(
            WorkflowPage.objects.filter(
                page__in=[self.about, self.story],
                workflow__name=EDITORIAL_WORKFLOW,
            ).count(),
            2,
        )

    def test_editor_submission_requires_publisher_and_retains_audit_history(self):
        user_model = get_user_model()
        editor = user_model.objects.create_user(
            username="editorial-workflow-editor@example.com",
            email="editorial-workflow-editor@example.com",
            password=self.password,
            role=user_model.Role.STAFF,
            is_staff=True,
        )
        publisher = user_model.objects.create_user(
            username="editorial-workflow-publisher@example.com",
            email="editorial-workflow-publisher@example.com",
            password=self.password,
            role=user_model.Role.STAFF,
            is_staff=True,
        )
        editor.groups.add(Group.objects.get(name=EDITORIAL_EDITOR_GROUP))
        publisher.groups.add(Group.objects.get(name=EDITORIAL_PUBLISHER_GROUP))

        self.about.introduction = "Editorial workflow candidate."
        self.about.save_revision(user=editor)
        workflow = self.about.get_workflow()
        workflow_state = workflow.start(self.about, user=editor)

        self.assertEqual(workflow_state.status, WorkflowState.STATUS_IN_PROGRESS)
        self.assertEqual(
            workflow_state.current_task_state.task.specific.get_actions(
                self.about,
                editor,
            ),
            [],
        )
        self.assertIn(
            "approve",
            {
                action[0]
                for action in workflow_state.current_task_state.task.specific.get_actions(
                    self.about,
                    publisher,
                )
            },
        )

        workflow_state.current_task_state.specific.approve(
            user=publisher,
            comment="Approved business editorial copy.",
        )
        workflow_state.refresh_from_db()
        self.about.refresh_from_db()

        self.assertEqual(workflow_state.status, WorkflowState.STATUS_APPROVED)
        self.assertTrue(self.about.live)
        self.assertTrue(
            PageLogEntry.objects.filter(
                page=self.about,
                action="wagtail.workflow.start",
                user=editor,
            ).exists()
        )
        self.assertTrue(
            PageLogEntry.objects.filter(
                page=self.about,
                action="wagtail.workflow.approve",
                user=publisher,
            ).exists()
        )

    def test_non_staff_membership_and_permission_drift_fail_closed(self):
        user_model = get_user_model()
        customer = user_model.objects.create_user(
            username="non-staff-editorial@example.com",
            email="non-staff-editorial@example.com",
            password=self.password,
            role=user_model.Role.CUSTOMER,
            is_staff=False,
        )
        editor_group = Group.objects.get(name=EDITORIAL_EDITOR_GROUP)
        customer.groups.add(editor_group)

        with self.assertRaises(CommandError):
            call_command(
                "configure_editorial_pages",
                "--check",
                stdout=StringIO(),
            )

        customer.groups.clear()
        editor_group.permissions.clear()
        with self.assertRaises(CommandError):
            call_command(
                "configure_editorial_pages",
                "--check",
                stdout=StringIO(),
            )

    def test_catalogue_and_editorial_authorization_remain_independent(self):
        call_command("configure_catalog_permissions", verbosity=0)
        self.assertEqual(catalog_permission_configuration_errors(), [])
        editorial_group_ids = set(
            Group.objects.filter(name__startswith="Editorial ").values_list("pk", flat=True)
        )
        catalogue_group = Group.objects.get(name=CATALOG_EDITOR_GROUP)

        call_command("configure_editorial_pages", verbosity=0)

        self.assertEqual(catalog_permission_configuration_errors(), [])
        self.assertEqual(editorial_permission_configuration_errors(), [])
        self.assertNotIn(catalogue_group.pk, editorial_group_ids)
        self.assertFalse(
            catalogue_group.permissions.filter(
                content_type__app_label="pages"
            ).exists()
        )
