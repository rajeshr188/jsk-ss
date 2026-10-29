from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from schemes.instalment_selectors import instalment_payment_ledger_summary


class Command(BaseCommand):
    help = "Read-only gated instalment ledger integrity; not eligibility or rollout acceptance."

    def handle(self, *args, **options):
        summary = instalment_payment_ledger_summary()
        self.stdout.write(
            f"instalment_payment_check status={'error' if summary['integrity_errors'] else 'ok'} "
            f"release={settings.APP_RELEASE} integration=gated_services "
            f"configured_intake_enabled={str(settings.CONFIGURED_PLANS_ENABLED).lower()} "
            + " ".join(f"{key}={value}" for key, value in summary.items())
        )
        if summary["integrity_errors"]:
            raise CommandError("Instalment payment evidence needs review; no records were changed.")
