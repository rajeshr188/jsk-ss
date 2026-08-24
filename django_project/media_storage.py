import re
from collections.abc import Mapping
from dataclasses import dataclass

from django.core.exceptions import ImproperlyConfigured


R2_ACCOUNT_ID_PATTERN = re.compile(r"^[0-9a-fA-F]{32}$")
R2_REQUIRED_SETTINGS = (
    "R2_ACCOUNT_ID",
    "R2_ACCESS_KEY_ID",
    "R2_SECRET_ACCESS_KEY",
    "R2_BUCKET_NAME",
)


@dataclass(frozen=True)
class MediaStorageConfig:
    backend: str
    account_id: str
    access_key_id: str
    secret_access_key: str
    bucket_name: str
    custom_domain: str
    default_storage: dict
    rendition_storage: dict


def _value(environ: Mapping[str, str], name: str) -> str:
    return environ.get(name, "").strip()


def _positive_int(environ: Mapping[str, str], name: str, default: int) -> int:
    raw_value = environ.get(name, str(default)).strip()
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ImproperlyConfigured(f"{name} must be an integer") from exc
    if value < 1:
        raise ImproperlyConfigured(f"{name} must be at least 1")
    return value


def _validate_custom_domain(custom_domain: str) -> None:
    if not custom_domain:
        return
    if (
        "://" in custom_domain
        or "/" in custom_domain
        or ":" in custom_domain
        or custom_domain.startswith(".")
        or custom_domain.endswith(".")
    ):
        raise ImproperlyConfigured(
            "R2_CUSTOM_DOMAIN must be a hostname without a scheme, port, path, "
            "or trailing slash"
        )


def build_media_storage_config(environ: Mapping[str, str]) -> MediaStorageConfig:
    backend = _value(environ, "MEDIA_STORAGE_BACKEND") or "filesystem"
    backend = backend.lower()
    if backend not in {"filesystem", "r2"}:
        raise ImproperlyConfigured(
            "MEDIA_STORAGE_BACKEND must be either filesystem or r2"
        )

    if backend == "filesystem":
        return MediaStorageConfig(
            backend=backend,
            account_id="",
            access_key_id="",
            secret_access_key="",
            bucket_name="",
            custom_domain="",
            default_storage={
                "BACKEND": "django.core.files.storage.FileSystemStorage",
            },
            rendition_storage={
                "BACKEND": "django.core.files.storage.FileSystemStorage",
            },
        )

    values = {name: _value(environ, name) for name in R2_REQUIRED_SETTINGS}
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise ImproperlyConfigured(
            "R2 media storage requires these server-side settings: "
            + ", ".join(missing)
        )

    account_id = values["R2_ACCOUNT_ID"]
    if not R2_ACCOUNT_ID_PATTERN.fullmatch(account_id):
        raise ImproperlyConfigured(
            "R2_ACCOUNT_ID must be a 32-character hexadecimal ID"
        )

    custom_domain = _value(environ, "R2_CUSTOM_DOMAIN").lower()
    _validate_custom_domain(custom_domain)
    signed_url_expiry = _positive_int(environ, "R2_SIGNED_URL_EXPIRY_SECONDS", 900)

    common_options = {
        "access_key": values["R2_ACCESS_KEY_ID"],
        "secret_key": values["R2_SECRET_ACCESS_KEY"],
        "bucket_name": values["R2_BUCKET_NAME"],
        "endpoint_url": f"https://{account_id}.r2.cloudflarestorage.com",
        "region_name": "auto",
        "addressing_style": "path",
        "signature_version": "s3v4",
        "default_acl": None,
        "file_overwrite": False,
        "querystring_expire": signed_url_expiry,
        "max_memory_size": 5 * 1024 * 1024,
    }
    private_options = {
        **common_options,
        "querystring_auth": True,
        "object_parameters": {
            "CacheControl": "private, max-age=900",
        },
    }
    rendition_options = {
        **common_options,
        "querystring_auth": not bool(custom_domain),
        "object_parameters": {
            "CacheControl": "public, max-age=86400",
        },
    }
    if custom_domain:
        rendition_options.update(
            {
                "custom_domain": custom_domain,
                "url_protocol": "https:",
            }
        )

    return MediaStorageConfig(
        backend=backend,
        account_id=account_id,
        access_key_id=values["R2_ACCESS_KEY_ID"],
        secret_access_key=values["R2_SECRET_ACCESS_KEY"],
        bucket_name=values["R2_BUCKET_NAME"],
        custom_domain=custom_domain,
        default_storage={
            "BACKEND": "storages.backends.s3.S3Storage",
            "OPTIONS": private_options,
        },
        rendition_storage={
            "BACKEND": "storages.backends.s3.S3Storage",
            "OPTIONS": rendition_options,
        },
    )
