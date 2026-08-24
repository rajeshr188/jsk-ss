from io import BytesIO
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen
from uuid import uuid4

from PIL import Image as PillowImage
from django.conf import settings
from django.core.files.images import ImageFile
from django.core.management.base import BaseCommand, CommandError
from wagtail.images import get_image_model


class Command(BaseCommand):
    help = (
        "Exercise R2 upload, read, Wagtail rendition, custom-domain controls, "
        "and cleanup without retaining data."
    )

    def _read_public_rendition(self, name):
        url = f"https://{settings.R2_CUSTOM_DOMAIN}/{quote(name, safe='/')}"
        request = Request(url, headers={"User-Agent": "jsk-r2-storage-check/1.0"})
        last_http_status = None
        network_failure = False
        served_rendition = False
        for _ in range(3):
            try:
                with urlopen(request, timeout=10) as response:
                    served_rendition = True
                    last_http_status = None
                    network_failure = False
                    if response.status != 200 or not response.read(8):
                        raise CommandError(
                            "The R2 custom domain did not return the generated rendition"
                        )
                    cache_control = response.headers.get("Cache-Control", "").lower()
                    if (
                        "public" not in cache_control
                        or "max-age=86400" not in cache_control
                    ):
                        raise CommandError(
                            "The public rendition response has an unsafe cache policy"
                        )
                    if response.headers.get("CF-Cache-Status", "").upper() == "HIT":
                        return
            except HTTPError as exc:
                last_http_status = exc.code
            except (URLError, TimeoutError):
                network_failure = True
        if last_http_status is not None:
            raise CommandError(
                f"The R2 custom domain returned HTTP {last_http_status} "
                "for the generated rendition"
            )
        if network_failure and not served_rendition:
            raise CommandError(
                "The R2 custom domain had a DNS, network, or TLS failure while "
                "serving the generated rendition"
            )
        raise CommandError("The public rendition did not produce a Cloudflare cache HIT")

    def _require_blocked_custom_domain_path(self, name):
        url = f"https://{settings.R2_CUSTOM_DOMAIN}/{quote(name, safe='/')}"
        request = Request(url, headers={"User-Agent": "jsk-r2-storage-check/1.0"})
        try:
            with urlopen(request, timeout=10):
                pass
        except HTTPError as exc:
            if exc.code == 403:
                return
            raise CommandError(
                "The R2 custom-domain private-prefix check did not return 403"
            ) from exc
        except (URLError, TimeoutError) as exc:
            raise CommandError(
                "The R2 custom domain was unreachable during its access-control check"
            ) from exc
        raise CommandError("The R2 custom domain exposed a private media prefix")

    def handle(self, *args, **options):
        if settings.MEDIA_STORAGE_BACKEND != "r2":
            raise CommandError("MEDIA_STORAGE_BACKEND must be r2 for this smoke check")

        image_model = get_image_model()
        image = None
        stored_names = []
        operation_error = None
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

            if settings.R2_CUSTOM_DOMAIN:
                self._read_public_rendition(rendition.file.name)
                self._require_blocked_custom_domain_path(image.file.name)
                self._require_blocked_custom_domain_path(
                    f"documents/r2-storage-check-{uuid4().hex}.txt"
                )
        except Exception as exc:
            operation_error = exc

        cleanup_failed = False
        for storage, name in reversed(stored_names):
            try:
                storage.delete(name)
            except Exception:
                cleanup_failed = True
        if image is not None and image.pk:
            try:
                image.delete()
            except Exception:
                cleanup_failed = True

        if operation_error is not None:
            if cleanup_failed:
                self.stderr.write(
                    self.style.WARNING(
                        "The media check failed and automatic cleanup was incomplete; "
                        "inspect temporary smoke records and objects."
                    )
                )
            raise operation_error

        if cleanup_failed:
            raise CommandError(
                "R2 media checks passed, but temporary smoke cleanup was incomplete"
            )

        self.stdout.write(
            self.style.SUCCESS(
                "R2 media storage passed upload, read, rendition, and cleanup checks."
            )
        )
