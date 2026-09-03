from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from schemes.models import MetalGrade, PaymentOperationsControl, PaymentScheduleWindow
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

        exposure = get_pending_payment_exposure()
        grades = list(MetalGrade.objects.all())
        self.stdout.write(
            " ".join(
                [
                    "payment_operations_check status=ok",
                    f"release={settings.APP_RELEASE}",
                    f"kill_switch={str(settings.PAYMENT_INITIATION_KILL_SWITCH).lower()}",
                    f"schedule_enabled={str(control.schedule_enabled).lower()}",
                    *[
                        f"{grade.code.lower()}="
                        f"{get_payment_availability(metal_grade=grade).code}"
                        for grade in grades
                    ],
                    *[
                        f"pending_{grade.code.lower()}={exposure[grade.code]['count']}"
                        for grade in grades
                    ],
                ]
            )
        )
