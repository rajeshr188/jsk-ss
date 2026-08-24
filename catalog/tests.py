from decimal import Decimal
from io import BytesIO

from PIL import Image as PillowImage
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Group
from django.core.exceptions import ValidationError
from django.core.files.images import ImageFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, transaction
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from wagtail.images import get_image_model
from wagtail.images.permissions import permission_policy as image_permission_policy
from wagtail.models import Collection, Locale, Page, PageLogEntry, Site, WorkflowState

from .models import (
    CatalogIndexPage,
    ProductCategory,
    ProductCollection,
    ProductImage,
    ProductPage,
)
from .permissions import (
    ADMIN_MODEL_PERMISSIONS,
    CATALOG_ADMIN_GROUP,
    CATALOG_EDITOR_GROUP,
    CATALOG_MEDIA_COLLECTION,
    CATALOG_PUBLISHER_GROUP,
    CATALOG_REVIEW_TASK,
    CATALOG_WORKFLOW,
    CATALOG_ROLES,
    catalog_permission_configuration_errors,
)


IN_MEMORY_STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.InMemoryStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
    "renditions": {
        "BACKEND": "django.core.files.storage.InMemoryStorage",
    },
}


@override_settings(STORAGES=IN_MEMORY_STORAGES)
class CatalogueDomainTests(TestCase):
    def setUp(self):
        if not Locale.objects.exists():
            Locale.objects.create(language_code="en")
        self.root = Page.get_first_root_node()
        if self.root is None:
            self.root = Page.add_root(title="Root", slug="root")
        self.catalogue = CatalogIndexPage(
            title="Jewellery catalogue",
            slug="jewellery",
            intro="Explore jewellery for showroom enquiry.",
        )
        self.root.add_child(instance=self.catalogue)
        self.category = ProductCategory.objects.create(
            name="Gold rings",
            slug="gold-rings",
        )

    def make_product(
        self,
        *,
        code="JSK-G-001",
        title="Classic gold ring",
        price=Decimal("25000.00"),
    ):
        product = ProductPage(
            title=title,
            slug=title.lower().replace(" ", "-"),
            product_code=code,
            category=self.category,
            short_description="A classic ring for showroom selection.",
            display_price_inr=price,
        )
        self.catalogue.add_child(instance=product)
        return product

    def make_image(self):
        image_bytes = BytesIO()
        PillowImage.new("RGB", (12, 8), color=(184, 134, 11)).save(
            image_bytes,
            format="PNG",
        )
        image_bytes.seek(0)
        collection = Collection.get_first_root_node()
        if collection is None:
            collection = Collection.add_root(name="Root")
        return get_image_model().objects.create(
            title="Gold ring catalogue image",
            file=ImageFile(image_bytes, name="gold-ring.png"),
            collection=collection,
        )

    def test_catalogue_page_hierarchy_is_bounded(self):
        self.assertTrue(ProductPage.can_create_at(self.catalogue))
        self.assertFalse(ProductPage.can_create_at(self.root))
        self.assertFalse(CatalogIndexPage.can_create_at(self.catalogue))
        self.assertFalse(CatalogIndexPage.can_create_at(self.root))

    def test_product_code_is_normalized_and_case_insensitively_unique(self):
        product = self.make_product(code="  jsk-g-001  ")
        product.refresh_from_db()

        self.assertEqual(product.product_code, "JSK-G-001")

        with self.assertRaises(ValidationError):
            self.make_product(
                code="jsk-g-001",
                title="Another gold ring",
            )

    def test_display_price_must_be_positive_when_present(self):
        product = self.make_product()
        product.display_price_inr = Decimal("0.00")

        with self.assertRaises(ValidationError) as context:
            product.full_clean()

        self.assertIn("display_price_inr", context.exception.error_dict)

    def test_taxonomy_names_are_case_insensitively_unique(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            ProductCategory.objects.create(name="gold RINGS", slug="other-rings")

        collection = ProductCollection.objects.create(
            name="Wedding edit",
            slug="",
        )
        self.assertEqual(collection.slug, "wedding-edit")

    def test_revision_preserves_product_content_and_collections(self):
        collection = ProductCollection.objects.create(
            name="Wedding edit",
            slug="wedding-edit",
        )
        product = self.make_product()
        product.collections.add(collection)
        revision = product.save_revision()

        product.short_description = "Updated description for a later revision."
        product.save_revision()
        historical = revision.as_object()

        self.assertEqual(
            historical.short_description,
            "A classic ring for showroom selection.",
        )
        self.assertEqual(
            list(historical.collections.values_list("name", flat=True)),
            ["Wedding edit"],
        )

    def test_product_preview_renders_showroom_only_language(self):
        product = self.make_product()
        request = RequestFactory().get("/cms/preview/")
        request.user = AnonymousUser()

        response = product.serve_preview(request, "")
        response.render()
        content = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertIn("Classic gold ring", content)
        self.assertIn("JSK-G-001", content)
        self.assertIn("Contact the showroom", content)
        self.assertIn("not a Scheme Rate", content)
        self.assertNotIn("Add to cart", content)

    def test_gallery_image_is_revisioned_and_can_generate_a_rendition(self):
        product = self.make_product()
        image = self.make_image()
        ProductImage.objects.create(
            page=product,
            image=image,
            alt_text="Polished gold ring on a neutral display",
            caption="Illustrative showroom photograph",
        )
        product.refresh_from_db()
        revision = product.save_revision()

        historical = revision.as_object()
        rendition = image.get_rendition("fill-6x4")

        self.assertEqual(historical.gallery_images.count(), 1)
        self.assertEqual(
            historical.gallery_images.first().alt_text,
            "Polished gold ring on a neutral display",
        )
        self.assertEqual((rendition.width, rendition.height), (6, 4))


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class CataloguePublishingAuthorizationTests(TestCase):
    password = "correct-horse-battery-staple"

    def setUp(self):
        if not Locale.objects.exists():
            Locale.objects.create(language_code="en")
        root = Page.get_first_root_node()
        if root is None:
            root = Page.add_root(title="Root", slug="root")

        site = Site.objects.filter(is_default_site=True).first()
        if site is None:
            site_root = root.get_children().first()
            if site_root is None:
                site_root = root.add_child(
                    instance=Page(title="Site root", slug="home")
                )
            Site.objects.create(
                hostname="testserver",
                port=80,
                root_page=site_root,
                is_default_site=True,
            )
        else:
            site.hostname = "testserver"
            site.port = 80
            site.save(update_fields=["hostname", "port"])

        call_command("configure_catalog_permissions", verbosity=0)
        self.catalogue = CatalogIndexPage.objects.get()
        self.groups = {
            role.name: Group.objects.get(name=role.name)
            for role in CATALOG_ROLES
        }

        user_model = get_user_model()
        self.editor = user_model.objects.create_user(
            username="catalog-editor@example.com",
            email="catalog-editor@example.com",
            password=self.password,
            role=user_model.Role.STAFF,
            is_staff=True,
        )
        self.publisher = user_model.objects.create_user(
            username="catalog-publisher@example.com",
            email="catalog-publisher@example.com",
            password=self.password,
            role=user_model.Role.STAFF,
            is_staff=True,
        )
        self.administrator = user_model.objects.create_user(
            username="catalog-administrator@example.com",
            email="catalog-administrator@example.com",
            password=self.password,
            role=user_model.Role.STAFF,
            is_staff=True,
        )
        self.non_staff_group_member = user_model.objects.create_user(
            username="non-staff-catalog-member@example.com",
            email="non-staff-catalog-member@example.com",
            password=self.password,
            role=user_model.Role.CUSTOMER,
            is_staff=False,
        )
        self.editor.groups.add(self.groups[CATALOG_EDITOR_GROUP])
        self.publisher.groups.add(self.groups[CATALOG_PUBLISHER_GROUP])
        self.administrator.groups.add(self.groups[CATALOG_ADMIN_GROUP])

        self.category = ProductCategory.objects.create(
            name="Gold rings",
            slug="gold-rings",
        )

    def make_draft_product(self):
        product = ProductPage(
            title="Workflow gold ring",
            slug="workflow-gold-ring",
            product_code="JSK-WF-001",
            category=self.category,
            short_description="A draft product awaiting catalogue review.",
            live=False,
            owner=self.editor,
        )
        self.catalogue.add_child(instance=product)
        product.save_revision(user=self.editor)
        return product

    def test_configuration_is_idempotent_and_repairs_permission_drift(self):
        self.assertEqual(catalog_permission_configuration_errors(), [])
        self.assertFalse(self.catalogue.live)
        self.assertTrue(
            Collection.get_first_root_node()
            .get_children()
            .filter(name=CATALOG_MEDIA_COLLECTION)
            .exists()
        )

        call_command("configure_catalog_permissions", verbosity=0)
        call_command("configure_catalog_permissions", "--check", verbosity=0)
        self.assertEqual(CatalogIndexPage.objects.count(), 1)

        editor_group = self.groups[CATALOG_EDITOR_GROUP]
        editor_group.permissions.clear()
        with self.assertRaises(CommandError):
            call_command("configure_catalog_permissions", "--check", verbosity=0)

        call_command("configure_catalog_permissions", verbosity=0)
        self.assertEqual(catalog_permission_configuration_errors(), [])

    def test_role_matrix_is_scoped_to_catalogue_content_and_media(self):
        editor_permissions = self.catalogue.permissions_for_user(self.editor)
        publisher_permissions = self.catalogue.permissions_for_user(self.publisher)
        administrator_permissions = self.catalogue.permissions_for_user(
            self.administrator
        )

        self.assertTrue(editor_permissions.can_edit())
        self.assertTrue(editor_permissions.can_add_subpage())
        self.assertFalse(editor_permissions.can_publish())
        self.assertFalse(editor_permissions.can_unlock())

        self.assertTrue(publisher_permissions.can_publish())
        self.assertTrue(publisher_permissions.can_lock())
        self.assertTrue(publisher_permissions.can_unlock())
        self.assertTrue(administrator_permissions.can_publish())
        self.assertFalse(
            Site.objects.get(is_default_site=True)
            .root_page.permissions_for_user(self.editor)
            .can_edit()
        )

        catalogue_media = Collection.get_first_root_node().get_children().get(
            name=CATALOG_MEDIA_COLLECTION
        )
        editable_collections = (
            image_permission_policy.collections_user_has_any_permission_for(
                self.editor,
                ["add", "change"],
            )
        )
        self.assertTrue(editable_collections.filter(pk=catalogue_media.pk).exists())
        self.assertFalse(
            editable_collections.filter(pk=Collection.get_first_root_node().pk).exists()
        )

        administrator_group = self.groups[CATALOG_ADMIN_GROUP]
        self.assertEqual(
            set(
                administrator_group.permissions.values_list(
                    "content_type__app_label",
                    "codename",
                )
            ),
            ADMIN_MODEL_PERMISSIONS,
        )
        self.assertFalse(
            administrator_group.permissions.filter(
                content_type__app_label__in=["accounts", "auth", "schemes"]
            ).exists()
        )
        self.assertFalse(
            administrator_group.permissions.filter(
                content_type__app_label="wagtaildocs"
            ).exists()
        )

        self.client.force_login(self.editor)
        self.assertEqual(self.client.get(reverse("wagtailadmin_home")).status_code, 200)

        self.non_staff_group_member.groups.add(self.groups[CATALOG_EDITOR_GROUP])
        self.client.force_login(self.non_staff_group_member)
        response = self.client.get(reverse("wagtailadmin_home"))
        self.assertRedirects(
            response,
            f'{reverse("wagtailadmin_login")}?next={reverse("wagtailadmin_home")}',
            fetch_redirect_response=False,
        )
        self.assertTrue(
            any(
                "contains a non-staff user" in error
                for error in catalog_permission_configuration_errors()
            )
        )

    def test_editor_submission_requires_publisher_and_retains_audit_history(self):
        self.assertEqual(self.client.get("/jewellery/").status_code, 404)
        self.catalogue.get_latest_revision().publish(user=self.publisher)
        self.catalogue.refresh_from_db()

        product = self.make_draft_product()
        product_url = "/jewellery/workflow-gold-ring/"
        self.assertEqual(self.client.get(product_url).status_code, 404)
        self.assertFalse(product.permissions_for_user(self.editor).can_publish())
        self.assertTrue(product.permissions_for_user(self.publisher).can_publish())

        workflow = product.get_workflow()
        self.assertEqual(workflow.name, CATALOG_WORKFLOW)
        self.assertEqual(workflow.tasks.get().specific.name, CATALOG_REVIEW_TASK)

        workflow_state = workflow.start(product, user=self.editor)
        self.assertEqual(workflow_state.status, WorkflowState.STATUS_IN_PROGRESS)
        self.assertEqual(
            workflow_state.current_task_state.task.specific.get_actions(
                product,
                self.editor,
            ),
            [],
        )
        self.assertIn(
            "approve",
            {
                action[0]
                for action in workflow_state.current_task_state.task.specific.get_actions(
                    product,
                    self.publisher,
                )
            },
        )

        workflow_state.current_task_state.specific.approve(
            user=self.publisher,
            comment="Approved for showroom catalogue publication.",
        )
        workflow_state.refresh_from_db()
        product.refresh_from_db()

        self.assertEqual(workflow_state.status, WorkflowState.STATUS_APPROVED)
        self.assertTrue(product.live)
        self.assertEqual(self.client.get(product_url).status_code, 200)

        product.unpublish(user=self.publisher)
        product.refresh_from_db()
        self.assertFalse(product.live)
        self.assertEqual(self.client.get(product_url).status_code, 404)

        log_entries = PageLogEntry.objects.filter(page=product)
        self.assertTrue(
            log_entries.filter(action="wagtail.workflow.start", user=self.editor).exists()
        )
        self.assertTrue(
            log_entries.filter(
                action="wagtail.workflow.approve",
                user=self.publisher,
            ).exists()
        )
        self.assertTrue(
            log_entries.filter(action="wagtail.publish", user=self.publisher).exists()
        )
        self.assertTrue(
            log_entries.filter(action="wagtail.unpublish", user=self.publisher).exists()
        )
