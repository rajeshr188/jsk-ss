from io import BytesIO

from PIL import Image as PillowImage
from django.core.exceptions import ImproperlyConfigured
from django.core.files.images import ImageFile
from django.core.files.storage import storages
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings
from storages.backends.s3 import S3Storage
from wagtail.images import get_image_model
from wagtail.models import Collection

from django_project.media_storage import build_media_storage_config


R2_ENVIRONMENT = {
    "MEDIA_STORAGE_BACKEND": "r2",
    "R2_ACCOUNT_ID": "0123456789abcdef0123456789abcdef",
    "R2_ACCESS_KEY_ID": "test-access-key",
    "R2_SECRET_ACCESS_KEY": "test-secret-key",
    "R2_BUCKET_NAME": "jsk-media-test",
}

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


class MediaStorageConfigurationTests(SimpleTestCase):
    def test_filesystem_is_the_safe_local_default(self):
        config = build_media_storage_config({})

        self.assertEqual(config.backend, "filesystem")
        self.assertEqual(
            config.default_storage["BACKEND"],
            "django.core.files.storage.FileSystemStorage",
        )

    def test_unknown_backend_is_rejected(self):
        with self.assertRaisesMessage(
            ImproperlyConfigured,
            "MEDIA_STORAGE_BACKEND must be either filesystem or r2",
        ):
            build_media_storage_config({"MEDIA_STORAGE_BACKEND": "unknown"})

    def test_r2_requires_every_server_side_value(self):
        with self.assertRaisesMessage(
            ImproperlyConfigured,
            "R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET_NAME",
        ):
            build_media_storage_config(
                {
                    "MEDIA_STORAGE_BACKEND": "r2",
                    "R2_ACCOUNT_ID": R2_ENVIRONMENT["R2_ACCOUNT_ID"],
                }
            )

    def test_private_r2_configuration_uses_short_lived_signed_urls(self):
        config = build_media_storage_config(R2_ENVIRONMENT)
        options = config.default_storage["OPTIONS"]

        self.assertEqual(
            options["endpoint_url"],
            "https://0123456789abcdef0123456789abcdef.r2.cloudflarestorage.com",
        )
        self.assertEqual(options["region_name"], "auto")
        self.assertEqual(options["addressing_style"], "path")
        self.assertTrue(options["querystring_auth"])
        self.assertEqual(options["querystring_expire"], 900)
        self.assertFalse(options["file_overwrite"])
        self.assertIsNone(options["default_acl"])
        self.assertEqual(
            options["object_parameters"]["CacheControl"],
            "private, max-age=900",
        )

    def test_custom_domain_produces_unsigned_public_rendition_urls(self):
        environment = {
            **R2_ENVIRONMENT,
            "R2_CUSTOM_DOMAIN": "media.jaishrikrishnajewellery.com",
        }
        config = build_media_storage_config(environment)
        options = config.rendition_storage["OPTIONS"]
        storage = S3Storage(**options)
        private_storage = S3Storage(**config.default_storage["OPTIONS"])

        url = storage.url("images/example.width-800.jpg")
        original_url = private_storage.url("original_images/example.jpg")

        self.assertEqual(
            url,
            "https://media.jaishrikrishnajewellery.com/images/example.width-800.jpg",
        )
        self.assertNotIn(environment["R2_ACCESS_KEY_ID"], url)
        self.assertNotIn(environment["R2_SECRET_ACCESS_KEY"], url)
        self.assertNotIn("media.jaishrikrishnajewellery.com", original_url)
        self.assertIn("X-Amz-Signature", original_url)
        self.assertFalse(options["querystring_auth"])
        self.assertEqual(
            options["object_parameters"]["CacheControl"],
            "public, max-age=86400",
        )

    def test_custom_domain_rejects_a_scheme_or_path(self):
        for custom_domain in (
            "https://media.example.com",
            "media.example.com/path",
            "media.example.com/",
        ):
            with self.subTest(custom_domain=custom_domain):
                with self.assertRaisesMessage(
                    ImproperlyConfigured,
                    "R2_CUSTOM_DOMAIN must be a hostname",
                ):
                    build_media_storage_config(
                        {
                            **R2_ENVIRONMENT,
                            "R2_CUSTOM_DOMAIN": custom_domain,
                        }
                    )


@override_settings(
    MEDIA_STORAGE_BACKEND="r2",
    STORAGES=IN_MEMORY_STORAGES,
)
class WagtailMediaPipelineTests(TestCase):
    def setUp(self):
        storages._storages.clear()
        self.collection = Collection.get_first_root_node()
        if self.collection is None:
            self.collection = Collection.add_root(name="Root")

    def tearDown(self):
        storages._storages.clear()

    def test_wagtail_image_upload_and_rendition_use_default_storage(self):
        image_bytes = BytesIO()
        PillowImage.new("RGB", (12, 8), color=(184, 134, 11)).save(
            image_bytes,
            format="PNG",
        )
        image_bytes.seek(0)
        image = get_image_model().objects.create(
            title="Storage pipeline test",
            file=ImageFile(image_bytes, name="pipeline-test.png"),
            collection=self.collection,
        )

        rendition = image.get_rendition("fill-6x4")

        self.assertTrue(image.file.storage.exists(image.file.name))
        self.assertTrue(rendition.file.storage.exists(rendition.file.name))
        self.assertIsNot(image.file.storage, rendition.file.storage)
        self.assertEqual((rendition.width, rendition.height), (6, 4))

    def test_smoke_command_cleans_up_image_and_rendition_records(self):
        image_model = get_image_model()
        image_count = image_model.objects.count()

        call_command("check_media_storage")

        self.assertEqual(image_model.objects.count(), image_count)
