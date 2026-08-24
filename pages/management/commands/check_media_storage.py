from io import BytesIO
from uuid import uuid4

from PIL import Image as PillowImage
from django.conf import settings
from django.core.files.images import ImageFile
from django.core.management.base import BaseCommand, CommandError
from wagtail.images import get_image_model


class Command(BaseCommand):
    help = "Exercise R2 upload, read, Wagtail rendition, and cleanup without retaining data."

    def handle(self, *args, **options):
        if settings.MEDIA_STORAGE_BACKEND != "r2":
            raise CommandError("MEDIA_STORAGE_BACKEND must be r2 for this smoke check")

        image_model = get_image_model()
        image = None
        stored_names = []
        passed = False
        try:
            image_bytes = BytesIO()
            PillowImage.new("RGB", (8, 8), color=(184, 134, 11)).save(
                image_bytes,
                format="PNG",
            )
            image_bytes.seek(0)
            image = image_model(
                title="Temporary R2 storage check",
                file=ImageFile(
                    image_bytes,
                    name=f"r2-storage-check-{uuid4().hex}.png",
                ),
            )
            image.save()
            stored_names.append((image.file.storage, image.file.name))

            rendition = image.get_rendition("fill-4x4")
            stored_names.append((rendition.file.storage, rendition.file.name))

            for storage, name in stored_names:
                if not storage.exists(name):
                    raise CommandError("R2 did not report an uploaded smoke object")
                with storage.open(name, "rb") as stored_file:
                    if not stored_file.read(8):
                        raise CommandError("R2 returned an empty smoke object")
            passed = True
        finally:
            for storage, name in reversed(stored_names):
                storage.delete(name)
            if image is not None and image.pk:
                image.delete()

        if passed:
            self.stdout.write(
                self.style.SUCCESS(
                    "R2 media storage passed upload, read, rendition, and cleanup checks."
                )
            )
