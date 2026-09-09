import re
from pathlib import Path

from django.test import SimpleTestCase


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_CALL_PATTERN = re.compile(
    r"(?:os\.getenv|env_(?:bool|int|int_list|list))\(\s*['\"]"
    r"([A-Z][A-Z0-9_]*)['\"]"
)
MEDIA_ENVIRONMENT_KEYS = {
    "MEDIA_STORAGE_BACKEND",
    "R2_ACCOUNT_ID",
    "R2_ACCESS_KEY_ID",
    "R2_SECRET_ACCESS_KEY",
    "R2_BUCKET_NAME",
    "R2_CUSTOM_DOMAIN",
    "R2_SIGNED_URL_EXPIRY_SECONDS",
}
PRODUCTION_COMPOSE_KEYS = {
    "ACME_EMAIL",
    "APP_ENV_FILE",
    "APP_IMAGE",
    "LINODE_DB_CA_FILE",
}


def template_keys(filename):
    keys = set()
    for line in (PROJECT_ROOT / filename).read_text(encoding="utf-8").splitlines():
        match = re.match(r"\s*([A-Z][A-Z0-9_]*)=", line)
        if match:
            keys.add(match.group(1))
    return keys


class EnvironmentTemplateCoverageTests(SimpleTestCase):
    def test_application_environment_is_documented_in_both_templates(self):
        settings_source = (PROJECT_ROOT / "django_project" / "settings.py").read_text(
            encoding="utf-8"
        )
        application_keys = set(ENV_CALL_PATTERN.findall(settings_source))
        application_keys.update(MEDIA_ENVIRONMENT_KEYS)

        for filename in (".env.example", ".env.production.example"):
            with self.subTest(filename=filename):
                self.assertEqual(
                    application_keys - template_keys(filename),
                    set(),
                    f"Add undocumented application settings to {filename}",
                )

    def test_production_template_documents_compose_only_environment(self):
        self.assertEqual(
            PRODUCTION_COMPOSE_KEYS - template_keys(".env.production.example"),
            set(),
        )
