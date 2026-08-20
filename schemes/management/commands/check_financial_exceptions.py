from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from schemes.selectors import get_financial_exception_counts


class Command(BaseCommand):
    help = "Report aggregate unresolved payment and allocation exception counts."

    def handle(self, *args, **options):
        counts = get_financial_exception_counts()
        status = "ok" if counts.total == 0 else "alert"
        summary = (
            "financial_exception_check "
            f"status={status} release={settings.APP_RELEASE} "
            f"paid_unallocated={counts.paid_unallocated} "
            f"failed_webhooks={counts.failed_webhooks} "
            f"mismatched_webhooks={counts.mismatched_webhooks}"
        )
        self.stdout.write(summary)
        if counts.total:
            raise CommandError(
                f"{counts.total} unresolved financial exception(s) detected."
            )
