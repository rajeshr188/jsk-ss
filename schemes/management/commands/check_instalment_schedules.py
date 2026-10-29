from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from schemes.instalment_selectors import validated_instalment_periods
from schemes.models import SchemeAccount, SchemeInstalmentPeriod


class Command(BaseCommand):
    help = "Read-only check of monthly-completion period snapshots, not payment compliance or eligibility."

    def handle(self, *args, **options):
        accounts = SchemeAccount.objects.filter(
            configuration_snapshot__instalment_policy="MONTHLY_COMPLETION",
        ).select_related("configuration_snapshot", "plan_revision", "metal_grade").prefetch_related("instalment_periods")
        mismatches = 0
        for account in accounts.iterator(chunk_size=100):
            try:
                validated_instalment_periods(account)
            except ValidationError:
                mismatches += 1
        unexpected = SchemeInstalmentPeriod.objects.filter(
            Q(scheme_account__configuration_snapshot__isnull=True)
            | ~Q(scheme_account__configuration_snapshot__instalment_policy="MONTHLY_COMPLETION")
        ).count()
        errors = mismatches + unexpected
        self.stdout.write(
            f"instalment_schedule_check status={'error' if errors else 'ok'} release={settings.APP_RELEASE} "
            f"monthly_agreements={accounts.count()} periods={SchemeInstalmentPeriod.objects.count()} "
            f"schedule_mismatches={mismatches} unexpected_periods={unexpected} "
            "payment_attribution=not_released"
        )
        if errors:
            raise CommandError("Instalment schedule evidence needs review; no records were changed.")
