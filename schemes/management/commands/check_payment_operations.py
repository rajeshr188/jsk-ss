from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from schemes.models import PaymentOperationsControl, PaymentScheduleWindow, SchemeRate
from schemes.operations import get_payment_availability
from schemes.selectors import get_pending_payment_exposure


class Command(BaseCommand):
    help = "Validate and summarize the payment operations circuit breaker."

    def handle(self, *args, **options):
        try:
            control = PaymentOperationsControl.objects.prefetch_related(
                "schedule_windows"
            ).get(pk=PaymentOperationsControl.SINGLETON_PK)
        except PaymentOperationsControl.DoesNotExist as error:
            raise CommandError("Payment operations control is missing.") from error

        windows = list(control.schedule_windows.all())
        weekdays = {window.weekday for window in windows}
        expected = set(PaymentScheduleWindow.Weekday.values)
        if len(windows) != 7 or weekdays != expected:
            raise CommandError(
                "Payment operations schedule must contain exactly one window for "
                "each weekday."
            )

        gold = get_payment_availability(metal=SchemeRate.Metal.GOLD)
        silver = get_payment_availability(metal=SchemeRate.Metal.SILVER)
        exposure = get_pending_payment_exposure()
        self.stdout.write(
            " ".join(
                [
                    "payment_operations_check status=ok",
                    f"release={settings.APP_RELEASE}",
                    f"kill_switch={str(settings.PAYMENT_INITIATION_KILL_SWITCH).lower()}",
                    f"schedule_enabled={str(control.schedule_enabled).lower()}",
                    f"gold={gold.code}",
                    f"silver={silver.code}",
                    f"pending_gold={exposure[SchemeRate.Metal.GOLD]['count']}",
                    f"pending_silver={exposure[SchemeRate.Metal.SILVER]['count']}",
                ]
            )
        )
