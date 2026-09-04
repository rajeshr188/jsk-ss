import os
from pathlib import Path
from urllib.parse import parse_qsl, unquote, urlparse

from django.core.exceptions import ImproperlyConfigured

from .media_storage import build_media_storage_config

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ImproperlyConfigured(f"{name} must be a boolean value")


def env_int(name, default, *, minimum=None, maximum=None):
    value = os.getenv(name, str(default))
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ImproperlyConfigured(f"{name} must be an integer") from exc
    if minimum is not None and parsed < minimum:
        raise ImproperlyConfigured(f"{name} must be at least {minimum}")
    if maximum is not None and parsed > maximum:
        raise ImproperlyConfigured(f"{name} must be at most {maximum}")
    return parsed


def env_list(name, default=""):
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


def env_int_list(name, default, *, minimum=None, maximum=None, max_items=None):
    raw_items = env_list(name, default)
    values = []
    for raw_item in raw_items:
        try:
            value = int(raw_item)
        except ValueError as exc:
            raise ImproperlyConfigured(
                f"{name} must be a comma-separated list of integers"
            ) from exc
        if minimum is not None and value < minimum:
            raise ImproperlyConfigured(f"{name} values must be at least {minimum}")
        if maximum is not None and value > maximum:
            raise ImproperlyConfigured(f"{name} values must be at most {maximum}")
        values.append(value)
    if len(values) != len(set(values)):
        raise ImproperlyConfigured(f"{name} must not contain duplicate values")
    if max_items is not None and len(values) > max_items:
        raise ImproperlyConfigured(f"{name} may contain at most {max_items} values")
    return tuple(values)


def postgres_database_from_url(url):
    parsed = urlparse(url)
    if parsed.scheme not in {"postgres", "postgresql"}:
        raise ImproperlyConfigured("DATABASE_URL must use postgres:// or postgresql://")
    if not parsed.path.lstrip("/"):
        raise ImproperlyConfigured("DATABASE_URL must include a database name")

    config = {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": unquote(parsed.path.lstrip("/")),
        "USER": unquote(parsed.username or ""),
        "PASSWORD": unquote(parsed.password or ""),
        "HOST": parsed.hostname or "",
        "PORT": str(parsed.port or 5432),
    }
    options = dict(parse_qsl(parsed.query))
    if options:
        config["OPTIONS"] = options
    return config


SECRET_KEY = os.getenv("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set")
SECRET_KEY_FALLBACKS = env_list("DJANGO_SECRET_KEY_FALLBACKS")

# Use an application-specific name so generic host variables such as DEBUG do not
# silently alter Django's security posture.
DEBUG = env_bool("DJANGO_DEBUG")
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "localhost,127.0.0.1")
APP_RELEASE = os.getenv("APP_RELEASE", "unknown").strip() or "unknown"


# Application definition
# https://docs.djangoproject.com/en/dev/ref/settings/#installed-apps
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.postgres",
    "django.contrib.sessions",
    "django.contrib.messages",
    "whitenoise.runserver_nostatic",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    # Third-party
    "allauth",
    "allauth.account",
    "crispy_forms",
    "crispy_bootstrap5",
    "wagtail.contrib.forms",
    "wagtail.contrib.redirects",
    "wagtail.embeds",
    "wagtail.sites",
    "wagtail.users",
    "wagtail.snippets",
    "wagtail.documents",
    "wagtail.images",
    "wagtail.search",
    "wagtail.admin",
    "wagtail",
    "modelcluster",
    "taggit",
    "django_filters",
    # Local
    "accounts",
    "catalog.apps.CatalogConfig",
    "pages",
    "schemes",
]

# https://docs.djangoproject.com/en/dev/ref/settings/#middleware
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # WhiteNoise
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",  # django-allauth
    "accounts.middleware.SensitiveAuthPathMiddleware",
    "wagtail.contrib.redirects.middleware.RedirectMiddleware",
]

if DEBUG:
    INSTALLED_APPS.append("debug_toolbar")
    MIDDLEWARE.insert(
        MIDDLEWARE.index("django.middleware.csrf.CsrfViewMiddleware"),
        "debug_toolbar.middleware.DebugToolbarMiddleware",
    )

# https://docs.djangoproject.com/en/dev/ref/settings/#root-urlconf
ROOT_URLCONF = "django_project.urls"

# https://docs.djangoproject.com/en/dev/ref/settings/#wsgi-application
WSGI_APPLICATION = "django_project.wsgi.application"

# https://docs.djangoproject.com/en/dev/ref/settings/#templates
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "catalog.context_processors.public_catalogue_navigation",
            ],
        },
    },
]

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ImproperlyConfigured("DATABASE_URL must be set to a PostgreSQL database")
DATABASES = {"default": postgres_database_from_url(DATABASE_URL)}
DATABASES["default"]["CONN_MAX_AGE"] = env_int(
    "DATABASE_CONN_MAX_AGE", 0 if DEBUG else 60, minimum=0
)
DATABASES["default"]["CONN_HEALTH_CHECKS"] = not DEBUG

PAYMENT_GATEWAY = os.getenv("PAYMENT_GATEWAY", "").strip().lower()
PAYMENT_INITIATION_KILL_SWITCH = env_bool("PAYMENT_INITIATION_KILL_SWITCH")
IN_STORE_CASH_CONTRIBUTIONS_ENABLED = env_bool(
    "IN_STORE_CASH_CONTRIBUTIONS_ENABLED"
)
IN_STORE_CASH_REVERSAL_HOURS = env_int(
    "IN_STORE_CASH_REVERSAL_HOURS",
    24,
    minimum=1,
    maximum=168,
)
RAZORPAY_MODE = os.getenv("RAZORPAY_MODE", "").strip().lower()
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "").strip()
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "").strip()
RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET", "").strip()
RAZORPAY_TIMEOUT_SECONDS = os.getenv("RAZORPAY_TIMEOUT_SECONDS", "10")
RAZORPAY_CHECKOUT_EXPIRY_MINUTES = env_int(
    "RAZORPAY_CHECKOUT_EXPIRY_MINUTES",
    10,
    minimum=3,
    maximum=15,
)

# Password validation
# https://docs.djangoproject.com/en/dev/ref/settings/#auth-password-validators
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/dev/topics/i18n/
# https://docs.djangoproject.com/en/dev/ref/settings/#language-code
LANGUAGE_CODE = "en-us"

# https://docs.djangoproject.com/en/dev/ref/settings/#time-zone
TIME_ZONE = "Asia/Kolkata"

# https://docs.djangoproject.com/en/dev/ref/settings/#std:setting-USE_I18N
USE_I18N = True

# https://docs.djangoproject.com/en/dev/ref/settings/#use-tz
USE_TZ = True

# https://docs.djangoproject.com/en/dev/ref/settings/#locale-paths
LOCALE_PATHS = [BASE_DIR / "locale"]

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.0/howto/static-files/

# https://docs.djangoproject.com/en/dev/ref/settings/#static-root
STATIC_ROOT = BASE_DIR / "staticfiles"

# https://docs.djangoproject.com/en/dev/ref/settings/#static-url
STATIC_URL = "/static/"

# https://docs.djangoproject.com/en/dev/ref/contrib/staticfiles/#std:setting-STATICFILES_DIRS
STATICFILES_DIRS = [BASE_DIR / "static"]

# Local uploaded-media storage remains the development default. Production must
# select the Cloudflare R2 backend and provide server-side credentials.
MEDIA_ROOT = BASE_DIR / "media"
MEDIA_URL = "/media/"

MEDIA_STORAGE_CONFIG = build_media_storage_config(os.environ)
MEDIA_STORAGE_BACKEND = MEDIA_STORAGE_CONFIG.backend
R2_ACCOUNT_ID = MEDIA_STORAGE_CONFIG.account_id
R2_ACCESS_KEY_ID = MEDIA_STORAGE_CONFIG.access_key_id
R2_SECRET_ACCESS_KEY = MEDIA_STORAGE_CONFIG.secret_access_key
R2_BUCKET_NAME = MEDIA_STORAGE_CONFIG.bucket_name
R2_CUSTOM_DOMAIN = MEDIA_STORAGE_CONFIG.custom_domain

# https://whitenoise.readthedocs.io/en/latest/django.html
STORAGES = {
    "default": MEDIA_STORAGE_CONFIG.default_storage,
    "renditions": MEDIA_STORAGE_CONFIG.rendition_storage,
    "staticfiles": {
        "BACKEND": (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
            if DEBUG
            else "whitenoise.storage.CompressedManifestStaticFilesStorage"
        ),
    },
}

# Default primary key field type
# https://docs.djangoproject.com/en/stable/ref/settings/#default-auto-field
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Wagtail is a bounded catalogue CMS. Existing public and financial routes remain
# ordinary Django views until their own approved implementation phase.
WAGTAIL_SITE_NAME = "Jai Sri Krishna Jewellery Catalogue"
WAGTAILADMIN_BASE_URL = os.getenv(
    "WAGTAILADMIN_BASE_URL",
    "http://localhost:8000" if DEBUG else "https://jaishrikrishnajewellery.com",
).strip().rstrip("/")
# Activate public navigation only after the catalogue root has been reviewed and
# published. The context processor still resolves live/public state when enabled.
PUBLIC_CATALOGUE_ENABLED = env_bool("PUBLIC_CATALOGUE_ENABLED", False)
# About and Our Story retain their reviewed Django fallbacks until their live Wagtail
# revisions have passed rollout checks and this separate gate is enabled.
PUBLIC_EDITORIAL_PAGES_ENABLED = env_bool("PUBLIC_EDITORIAL_PAGES_ENABLED", False)
WAGTAILSEARCH_BACKENDS = {
    "default": {
        "BACKEND": "wagtail.search.backends.database",
    }
}
DATA_UPLOAD_MAX_NUMBER_FIELDS = 10_000
WAGTAILDOCS_EXTENSIONS = ["csv", "docx", "odt", "pdf", "pptx", "rtf", "txt", "xlsx"]
WAGTAILDOCS_MAX_UPLOAD_SIZE = 10 * 1024 * 1024
WAGTAILDOCS_SERVE_METHOD = "serve_view"
WAGTAILIMAGES_MAX_UPLOAD_SIZE = 10 * 1024 * 1024
WAGTAILIMAGES_RENDITION_STORAGE = "renditions"

# django-crispy-forms
# https://django-crispy-forms.readthedocs.io/en/latest/install.html#template-packs
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

# Email defaults remain convenient locally. The deployment check rejects console or
# dummy delivery outside development so password-reset messages cannot disappear.
EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend"
).strip()
EMAIL_HOST = os.getenv("EMAIL_HOST", "localhost").strip()
EMAIL_PORT = env_int("EMAIL_PORT", 25, minimum=1, maximum=65535)
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "").strip()
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS")
EMAIL_USE_SSL = env_bool("EMAIL_USE_SSL")
EMAIL_TIMEOUT = env_int("EMAIL_TIMEOUT", 10, minimum=1, maximum=60)
if EMAIL_USE_TLS and EMAIL_USE_SSL:
    raise ImproperlyConfigured("EMAIL_USE_TLS and EMAIL_USE_SSL cannot both be enabled")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "noreply@jskjewellery.local")
SERVER_EMAIL = os.getenv("SERVER_EMAIL", DEFAULT_FROM_EMAIL)

# Transactional scheme reminders are scheduled externally through the
# send_scheme_reminders management command. Every audience can be disabled
# independently, while the master switch defaults off for controlled rollout.
SCHEME_REMINDERS_ENABLED = env_bool("SCHEME_REMINDERS_ENABLED", False)
SCHEME_REMINDER_ELIGIBILITY_DAYS = env_int_list(
    "SCHEME_REMINDER_ELIGIBILITY_DAYS",
    "30,7,1",
    minimum=1,
    maximum=90,
    max_items=10,
)
SCHEME_REMINDER_CUSTOMER_ELIGIBILITY = env_bool(
    "SCHEME_REMINDER_CUSTOMER_ELIGIBILITY", True
)
SCHEME_REMINDER_OWNER_ELIGIBILITY = env_bool(
    "SCHEME_REMINDER_OWNER_ELIGIBILITY", True
)
SCHEME_REMINDER_OWNER_ALLOCATION_EXCEPTIONS = env_bool(
    "SCHEME_REMINDER_OWNER_ALLOCATION_EXCEPTIONS", True
)
SCHEME_REMINDER_CUSTOMER_REDEMPTIONS = env_bool(
    "SCHEME_REMINDER_CUSTOMER_REDEMPTIONS", True
)
SCHEME_REMINDER_OWNER_REDEMPTIONS = env_bool(
    "SCHEME_REMINDER_OWNER_REDEMPTIONS", True
)
SCHEME_REMINDER_RETRY_LIMIT = env_int(
    "SCHEME_REMINDER_RETRY_LIMIT", 3, minimum=1, maximum=10
)
SCHEME_REMINDER_BASE_URL = os.getenv(
    "SCHEME_REMINDER_BASE_URL", WAGTAILADMIN_BASE_URL
).strip().rstrip("/")
if (
    SCHEME_REMINDER_CUSTOMER_ELIGIBILITY
    or SCHEME_REMINDER_OWNER_ELIGIBILITY
) and not SCHEME_REMINDER_ELIGIBILITY_DAYS:
    raise ImproperlyConfigured(
        "SCHEME_REMINDER_ELIGIBILITY_DAYS cannot be empty while eligibility "
        "reminders are enabled"
    )
if SCHEME_REMINDERS_ENABLED and not any(
    [
        SCHEME_REMINDER_CUSTOMER_ELIGIBILITY,
        SCHEME_REMINDER_OWNER_ELIGIBILITY,
        SCHEME_REMINDER_OWNER_ALLOCATION_EXCEPTIONS,
        SCHEME_REMINDER_CUSTOMER_REDEMPTIONS,
        SCHEME_REMINDER_OWNER_REDEMPTIONS,
    ]
):
    raise ImproperlyConfigured(
        "SCHEME_REMINDERS_ENABLED requires at least one reminder audience"
    )
if not SCHEME_REMINDER_BASE_URL.startswith(("http://", "https://")):
    raise ImproperlyConfigured(
        "SCHEME_REMINDER_BASE_URL must be an absolute HTTP or HTTPS URL"
    )
if not DEBUG and not SCHEME_REMINDER_BASE_URL.startswith("https://"):
    raise ImproperlyConfigured(
        "SCHEME_REMINDER_BASE_URL must use HTTPS outside development"
    )
if (
    not DEBUG
    and SCHEME_REMINDERS_ENABLED
    and urlparse(SCHEME_REMINDER_BASE_URL).hostname not in ALLOWED_HOSTS
):
    raise ImproperlyConfigured(
        "SCHEME_REMINDER_BASE_URL host must be present in ALLOWED_HOSTS"
    )

# django-debug-toolbar
# https://django-debug-toolbar.readthedocs.io/en/latest/installation.html
# https://docs.djangoproject.com/en/dev/ref/settings/#internal-ips
INTERNAL_IPS = ["127.0.0.1"]

# https://docs.djangoproject.com/en/dev/topics/auth/customizing/#substituting-a-custom-user-model
AUTH_USER_MODEL = "accounts.CustomUser"

# django-allauth config
# https://docs.djangoproject.com/en/dev/ref/settings/#site-id
SITE_ID = 1

# https://docs.djangoproject.com/en/dev/ref/settings/#login-redirect-url
LOGIN_REDIRECT_URL = "schemes:post_login"

# https://django-allauth.readthedocs.io/en/latest/views.html#logout-account-logout
ACCOUNT_LOGOUT_REDIRECT_URL = "home"

# https://django-allauth.readthedocs.io/en/latest/installation.html?highlight=backends
AUTHENTICATION_BACKENDS = (
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
)
# https://django-allauth.readthedocs.io/en/latest/configuration.html
ACCOUNT_SESSION_REMEMBER = True
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*"]
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_ADAPTER = "accounts.adapters.AccountAdapter"
CUSTOMER_INVITATION_EXPIRY_HOURS = env_int(
    "CUSTOMER_INVITATION_EXPIRY_HOURS",
    72,
    minimum=1,
    maximum=168,
)

# https://docs.djangoproject.com/en/dev/ref/settings/#csrf-trusted-origins
CSRF_TRUSTED_ORIGINS = env_list(
    "CSRF_TRUSTED_ORIGINS",
    "http://localhost:8000,http://127.0.0.1:8000",
)

# Secure-by-default production cookies and transport. Deployments terminating TLS
# at a trusted proxy may explicitly override the redirect setting.
SESSION_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SAMESITE = "Lax"
SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", not DEBUG)
SECURE_HSTS_SECONDS = env_int(
    "SECURE_HSTS_SECONDS", 0 if DEBUG else 3600, minimum=0
)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", False)
SECURE_HSTS_PRELOAD = env_bool("SECURE_HSTS_PRELOAD", False)
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
X_FRAME_OPTIONS = "DENY"

# Enable this only when every request reaches Django through a trusted proxy that
# overwrites X-Forwarded-Proto. Blindly trusting this header permits spoofing.
if env_bool("TRUST_PROXY_SSL_HEADER"):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").strip().upper()
if LOG_LEVEL not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
    raise ImproperlyConfigured("LOG_LEVEL must be a standard Python logging level")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "redact_sensitive_auth_paths": {
            "()": "accounts.logging.SensitiveAuthPathFilter",
        }
    },
    "formatters": {
        "standard": {
            "format": "{asctime} {levelname} {name} {message}",
            "style": "{",
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
            "filters": ["redact_sensitive_auth_paths"],
        }
    },
    "root": {"handlers": ["console"], "level": LOG_LEVEL},
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": LOG_LEVEL,
            "propagate": False,
        }
    },
}
