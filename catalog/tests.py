from decimal import Decimal
from io import BytesIO

from PIL import Image as PillowImage
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ValidationError
from django.core.files.images import ImageFile
from django.db import IntegrityError, transaction
from django.test import RequestFactory, TestCase, override_settings
from wagtail.images import get_image_model
from wagtail.models import Collection, Locale, Page

from .models import (
    CatalogIndexPage,
    ProductCategory,
    ProductCollection,
    ProductImage,
    ProductPage,
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
