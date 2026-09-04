from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class ReminderSystemdUnitTests(SimpleTestCase):
    def test_unit_does_not_depend_on_home_or_compose_plugin(self):
        unit_path = (
            Path(settings.BASE_DIR)
            / "deploy"
            / "systemd"
            / "jsk-scheme-reminders.service"
        )
        unit = unit_path.read_text(encoding="utf-8")

        self.assertIn("ProtectHome=true", unit)
        self.assertIn("RuntimeDirectory=jsk-scheme-reminders", unit)
        self.assertIn(
            "Environment=DOCKER_CONFIG=/run/jsk-scheme-reminders",
            unit,
        )
        self.assertIn(
            "ExecStart=/usr/bin/docker exec jsk-savings-web-1 "
            "python manage.py send_scheme_reminders --apply",
            unit,
        )
        self.assertNotIn("docker compose", unit)
