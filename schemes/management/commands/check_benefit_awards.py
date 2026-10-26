from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from schemes.benefit_award_selectors import get_benefit_award_status
from schemes.models import SchemeBenefitAward


class Command(BaseCommand):
    help = "Read-only retained benefit award check, not fulfilment or builder activation."

    def handle(self, *args, **options):
        awards = SchemeBenefitAward.objects.select_related("scheme_account")
        count = review = 0
        for award in awards:
            count += 1
            review += int(get_benefit_award_status(award.scheme_account).needs_review)
        self.stdout.write(f"benefit_awards status={'error' if review else 'ok'} release={settings.APP_RELEASE} "
            f"workflow=not_activated awards={count} review_required={review} fulfilment=not_implemented")
        if review:
            raise CommandError("Retain the awards and reconcile source/closure evidence; no records were changed.")
