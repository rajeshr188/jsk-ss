from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from schemes.independent_payment_selectors import optional_order_summary


class Command(BaseCommand):
    help = "Inspect independent optional checkout identity evidence without provider calls or writes."

    def handle(self, *args, **options):
        summary = optional_order_summary()
        state = "error" if summary["integrity_errors"] else (
            "review" if summary["unbound_requests"] or summary["pending_without_request"] else "ok")
        self.stdout.write(f"optional_payment_orders status={state} release={settings.APP_RELEASE} "
            + " ".join(f"{key}={value}" for key, value in summary.items()))
        if summary["integrity_errors"]:
            raise CommandError("Optional payment order evidence requires integrity investigation.")
