from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from schemes.benefit_award_selectors import get_benefit_award_status
from schemes.benefit_fulfilment_selectors import get_benefit_invoice_status
from schemes.models import SchemeBenefitAward


class Command(BaseCommand):
    help = "Read-only retained benefit award check, not fulfilment or builder activation."

    def handle(self, *args, **options):
        awards = SchemeBenefitAward.objects.select_related("scheme_account")
        count = review = fulfilled = reversed_count = 0
        for award in awards:
            count += 1
            if award.invoice_fulfilments.exists():
                fulfilled += award.invoice_fulfilments.count()
                reversed_count += award.invoice_fulfilments.filter(reversal__isnull=False).count()
                review += int(get_benefit_invoice_status(award).needs_review)
            else:
                review += int(get_benefit_award_status(award.scheme_account).needs_review)
        self.stdout.write(f"benefit_awards status={'error' if review else 'ok'} release={settings.APP_RELEASE} "
            f"workflow=validated_existing_agreements awards={count} review_required={review} "
            f"invoice_fulfilments={fulfilled} invoice_reversals={reversed_count}")
        if review:
            raise CommandError("Retain the awards and reconcile source/closure evidence; no records were changed.")
