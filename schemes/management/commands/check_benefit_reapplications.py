from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from schemes.benefit_reapplication_selectors import reapplication_review_status
from schemes.models import BenefitInvoiceReversal


class Command(BaseCommand):
    help = "Read-only returned-benefit review history; never authorizes consumption."

    def handle(self, *args, **options):
        counts = dict(UNREVIEWED=0, APPROVED_REVIEW=0, HELD=0, STALE=0, CONSUMED=0, INVALID=0)
        for reversal in BenefitInvoiceReversal.objects.all():
            try:
                state = reapplication_review_status(reversal)
            except ValidationError:
                state = "INVALID"
            counts[state] += 1
        invalid = counts["INVALID"] + counts["STALE"]
        self.stdout.write(f"benefit_reapplications status={'error' if invalid else 'ok'} "
            f"release={settings.APP_RELEASE} workflow=settlement_invoice_integration standalone_spending_enabled=false "
            + " ".join(f"{name.lower()}={count}" for name, count in counts.items()))
        if invalid:
            raise CommandError("Reconcile stale or invalid return-review evidence; nothing was changed.")
