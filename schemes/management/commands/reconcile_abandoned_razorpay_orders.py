from datetime import timedelta

from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from schemes.models import Contribution
from schemes.payments import PaymentGatewayError, get_payment_gateway
from schemes.services import reconcile_abandoned_razorpay_contribution


class Command(BaseCommand):
    help = (
        "Inspect aged pending Razorpay orders and, with --apply, mark only provider-"
        "verified untouched orders as application-side abandoned."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--older-than-hours",
            type=int,
            default=24,
            help="Inspect pending orders created at least this many hours ago (default: 24).",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=100,
            help="Maximum number of orders to inspect (default: 100).",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Apply eligible abandonment decisions and write immutable audit events.",
        )

    def handle(self, *args, **options):
        hours = options["older_than_hours"]
        limit = options["limit"]
        apply = options["apply"]
        if hours < 1:
            raise CommandError("--older-than-hours must be at least 1.")
        if limit < 1 or limit > 1000:
            raise CommandError("--limit must be between 1 and 1000.")

        try:
            gateway = get_payment_gateway()
        except ImproperlyConfigured as error:
            raise CommandError(str(error)) from None
        if gateway.name != "razorpay":
            raise CommandError("PAYMENT_GATEWAY must be configured as razorpay.")

        cutoff = timezone.now() - timedelta(hours=hours)
        candidate_ids = list(
            Contribution.objects.filter(
                status=Contribution.Status.PENDING,
                payment_gateway="razorpay",
                gateway_mode=gateway.mode,
                gateway_order_id__isnull=False,
                created_at__lte=cutoff,
            )
            .exclude(gateway_order_id="")
            .order_by("created_at", "pk")
            .values_list("pk", flat=True)[:limit]
        )
        eligible = reviewed = abandoned = errors = 0
        for contribution_id in candidate_ids:
            try:
                result = reconcile_abandoned_razorpay_contribution(
                    contribution_id=contribution_id,
                    cutoff=cutoff,
                    apply=apply,
                    gateway=gateway,
                    reason=(
                        f"Aged Razorpay order reconciliation after at least {hours} hours."
                    ),
                )
            except (PaymentGatewayError, ValidationError) as error:
                errors += 1
                self.stderr.write(
                    f"contribution={contribution_id} outcome=ERROR error={error}"
                )
                continue

            if result.outcome == "ELIGIBLE_FOR_ABANDONMENT":
                eligible += 1
            else:
                reviewed += 1
            if result.applied:
                abandoned += 1
            self.stdout.write(
                " ".join(
                    [
                        f"contribution={contribution_id}",
                        f"order={result.inspection.order_id}",
                        f"provider_status={result.inspection.status}",
                        f"attempts={result.inspection.attempts}",
                        f"payments={result.inspection.payment_count}",
                        f"outcome={result.outcome}",
                        f"applied={str(result.applied).lower()}",
                    ]
                )
            )

        mode = "apply" if apply else "dry-run"
        self.stdout.write(
            " ".join(
                [
                    "razorpay_order_reconciliation",
                    f"mode={mode}",
                    f"gateway_mode={gateway.mode}",
                    f"candidates={len(candidate_ids)}",
                    f"eligible={eligible}",
                    f"review_required={reviewed}",
                    f"abandoned={abandoned}",
                    f"errors={errors}",
                ]
            )
        )
        if errors:
            raise CommandError(
                "One or more Razorpay orders could not be reconciled; no failing "
                "candidate was closed."
            )
