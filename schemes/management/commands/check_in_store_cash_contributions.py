from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from schemes.models import (
    Contribution,
    InStoreCashContributionReversal,
    InStoreCashReceipt,
    PaymentChannel,
    SchemeAccount,
)
from schemes.selectors import get_in_store_cash_daily_summary


class Command(BaseCommand):
    help = "Validate in-store cash receipt and reversal integrity without mutation."

    def handle(self, *args, **options):
        active_statuses = [
            Contribution.Status.PAID,
            Contribution.Status.PAID_UNALLOCATED,
        ]
        checks = {
            "cash_contributions_missing_receipt": Contribution.objects.filter(
                payment_channel=PaymentChannel.IN_STORE_CASH,
            ).filter(cash_receipt__isnull=True).count(),
            "cash_receipts_invalid_contribution": InStoreCashReceipt.objects.exclude(
                contribution__payment_channel=PaymentChannel.IN_STORE_CASH,
                contribution__payment_gateway="in_store_cash",
            ).count(),
            "cash_on_legacy_cash_scheme": InStoreCashReceipt.objects.filter(
                contribution__scheme_account__savings_mode=SchemeAccount.SavingsMode.CASH,
            ).count(),
            "reversed_missing_reversal": Contribution.objects.filter(
                payment_channel=PaymentChannel.IN_STORE_CASH,
                status=Contribution.Status.REVERSED,
                cash_reversal__isnull=True,
            ).count(),
            "reversal_status_mismatch": InStoreCashContributionReversal.objects.filter(
                ~Q(contribution__status=Contribution.Status.REVERSED)
            ).count(),
            "cash_invalid_lifecycle": Contribution.objects.filter(
                payment_channel=PaymentChannel.IN_STORE_CASH,
            ).exclude(
                status__in=[*active_statuses, Contribution.Status.REVERSED]
            ).count(),
        }
        daily = get_in_store_cash_daily_summary()
        status = "ok" if not any(checks.values()) else "error"
        fields = " ".join(f"{name}={value}" for name, value in checks.items())
        self.stdout.write(
            "in_store_cash_check "
            f"status={status} release={settings.APP_RELEASE} "
            f"enabled={str(settings.IN_STORE_CASH_CONTRIBUTIONS_ENABLED).lower()} "
            f"reversal_hours={settings.IN_STORE_CASH_REVERSAL_HOURS} "
            f"today_received={daily.received_amount:.2f} "
            f"today_reversed={daily.reversed_amount:.2f} "
            f"today_net={daily.net_amount:.2f} {fields}"
        )
        if status != "ok":
            raise CommandError(
                "In-store cash integrity failed; keep the feature disabled and "
                "investigate the reported counts."
            )
