from datetime import timedelta

from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from schemes.payments import PaymentGatewayError, get_payment_gateway
from schemes.selectors import get_expired_pending_checkouts
from schemes.services import reconcile_abandoned_razorpay_contribution


class Command(BaseCommand):
    help = "Inspect expired Razorpay checkouts; dry-run by default. Only provider-verified untouched orders can be closed with --apply."

    def add_arguments(self, parser):
        parser.add_argument("--older-than-hours", type=int, default=None,
                            help="Optional minimum age from creation; no 24-hour wait by default.")
        parser.add_argument("--grace-minutes", type=int, default=5,
                            help="Wait this many minutes after the stored Checkout deadline (default: 5).")
        parser.add_argument("--contribution-id", type=int, default=None,
                            help="Inspect only this exact pending contribution in the configured mode.")
        parser.add_argument("--limit", type=int, default=50, help="Maximum provider inspections (default: 50).")
        parser.add_argument("--apply", action="store_true", help="Apply eligible decisions with immutable audit events.")
        parser.add_argument("--summary-only", action="store_true", help="Print aggregate counts only, suitable for monitoring.")
        parser.add_argument("--fail-on-pending", action="store_true", help="Exit nonzero if expired pending attempts remain, including uninspected or other-mode records.")

    def handle(self, *args, **options):
        hours, grace, limit = options["older_than_hours"], options["grace_minutes"], options["limit"]
        if hours is not None and hours < 1:
            raise CommandError("--older-than-hours must be at least 1.")
        if not 0 <= grace <= 60:
            raise CommandError("--grace-minutes must be between 0 and 60.")
        if not 1 <= limit <= 1000:
            raise CommandError("--limit must be between 1 and 1000.")
        contribution_id = options["contribution_id"]
        if contribution_id is not None and contribution_id < 1:
            raise CommandError("--contribution-id must be positive.")
        try:
            gateway = get_payment_gateway()
        except ImproperlyConfigured:
            raise CommandError("A configured Razorpay gateway is required.") from None
        if gateway.name != "razorpay":
            raise CommandError("PAYMENT_GATEWAY must be configured as razorpay.")
        now = timezone.now()
        cutoff = now - timedelta(hours=hours) if hours is not None else now
        expired = get_expired_pending_checkouts(at=now)
        if contribution_id is not None:
            expired = expired.filter(pk=contribution_id)
        candidates = expired.filter(
            gateway_mode=gateway.mode, gateway_order_id__isnull=False,
            checkout_expires_at__lte=now - timedelta(minutes=grace), created_at__lte=cutoff,
        ).exclude(gateway_order_id="").order_by("checkout_expires_at", "pk")
        candidate_ids = list(candidates.values_list("pk", flat=True)[:limit])
        if contribution_id is not None and not candidate_ids:
            raise CommandError("The selected contribution is not an eligible expired pending order in the configured mode and age window.")
        eligible = reviewed = abandoned = errors = 0
        for selected_id in candidate_ids:
            try:
                result = reconcile_abandoned_razorpay_contribution(
                    contribution_id=selected_id, cutoff=cutoff, apply=options["apply"], gateway=gateway,
                    reason=f"Expired Checkout provider reconciliation after {grace} minutes of grace; operator age filter {hours} hours.",
                )
            except (PaymentGatewayError, ValidationError):
                errors += 1
                if not options["summary_only"]:
                    self.stderr.write(f"contribution={selected_id} outcome=INSPECTION_FAILED")
                continue
            eligible += result.outcome == "ELIGIBLE_FOR_ABANDONMENT"
            reviewed += result.outcome == "REVIEW_REQUIRED"
            abandoned += result.applied
            if not options["summary_only"]:
                self.stdout.write(
                    f"contribution={selected_id} order={result.inspection.order_id} "
                    f"provider_status={result.inspection.status} attempts={result.inspection.attempts} "
                    f"payments={result.inspection.payment_count} outcome={result.outcome} applied={str(result.applied).lower()}"
                )
        remaining = expired.count()
        self.stdout.write(
            f"razorpay_order_reconciliation mode={'apply' if options['apply'] else 'dry-run'} "
            f"gateway_mode={gateway.mode} candidates={len(candidate_ids)} eligible={eligible} "
            f"review_required={reviewed} abandoned={abandoned} errors={errors} expired_pending={remaining}"
        )
        if errors or (options["fail_on_pending"] and remaining):
            raise CommandError("Expired checkout reconciliation needs owner review; see the private exception queue.")
