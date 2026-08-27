from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.management.base import BaseCommand, CommandError

from schemes.models import Contribution, PaymentWebhookEvent
from schemes.payments import RazorpayPaymentGateway


class Command(BaseCommand):
    help = (
        "Verify live Razorpay configuration and ensure no pending contribution from "
        "another provider mode would be stranded by activation."
    )

    def handle(self, *args, **options):
        configuration_error = ""
        if settings.PAYMENT_GATEWAY != "razorpay":
            configuration_error = "PAYMENT_GATEWAY must be razorpay."
        else:
            try:
                gateway = RazorpayPaymentGateway()
            except ImproperlyConfigured as error:
                configuration_error = str(error)
            else:
                if gateway.mode != "live":
                    configuration_error = "RAZORPAY_MODE must be live."

        razorpay_contributions = Contribution.objects.filter(
            payment_gateway="razorpay"
        )
        pending_other_mode = razorpay_contributions.filter(
            status=Contribution.Status.PENDING,
        ).exclude(gateway_mode="live")
        pending_other_mode_contributions = pending_other_mode.count()
        open_other_mode_orders = (
            pending_other_mode.filter(
                gateway_order_id__isnull=False,
            )
            .exclude(gateway_order_id="")
            .count()
        )
        missing_contribution_modes = razorpay_contributions.filter(
            gateway_mode=""
        ).count()
        missing_webhook_modes = PaymentWebhookEvent.objects.filter(
            gateway="razorpay",
            gateway_mode="",
        ).count()
        failed_live_webhooks = PaymentWebhookEvent.objects.filter(
            gateway="razorpay",
            gateway_mode="live",
            status=PaymentWebhookEvent.Status.FAILED,
        ).count()
        blockers = {
            "configuration_error": bool(configuration_error),
            "pending_other_mode_contributions": pending_other_mode_contributions,
            "missing_contribution_modes": missing_contribution_modes,
            "missing_webhook_modes": missing_webhook_modes,
            "failed_live_webhooks": failed_live_webhooks,
        }
        status = "blocked" if any(blockers.values()) else "ok"
        self.stdout.write(
            " ".join(
                [
                    f"razorpay_live_readiness status={status}",
                    f"release={settings.APP_RELEASE}",
                    "pending_other_mode_contributions="
                    f"{pending_other_mode_contributions}",
                    f"open_other_mode_orders={open_other_mode_orders}",
                    f"missing_contribution_modes={missing_contribution_modes}",
                    f"missing_webhook_modes={missing_webhook_modes}",
                    f"failed_live_webhooks={failed_live_webhooks}",
                ]
            )
        )
        if configuration_error:
            self.stderr.write(configuration_error)
        if status == "blocked":
            names = [name for name, value in blockers.items() if value]
            raise CommandError(
                "Razorpay live activation is blocked by: " + ", ".join(names)
            )
