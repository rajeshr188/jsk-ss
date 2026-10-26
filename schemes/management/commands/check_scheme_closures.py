from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from schemes.closure_selectors import closure_requests, closure_payment_review, validate_closure_history
from schemes.models import SchemeAccount, ConfiguredSettlement, Redemption
from schemes.settlement_selectors import validate_configured_settlement


class Command(BaseCommand):
    help = "Check configured closure lifecycle evidence; never authorize settlement."

    def handle(self, *args, **options):
        errors = pending = accepted = terminal = cancelled = settled = 0
        for request in closure_requests().iterator(chunk_size=100):
            try:
                request.full_clean()
                validate_closure_history(request)
                if not request.scheme_account.configuration_snapshot_id:
                    raise ValidationError("Legacy closure is not enabled.")
                if request.status in ("PENDING", "ACCEPTED") and request.scheme_account.status in ("REDEEMED", "CANCELLED"):
                    raise ValidationError("Open closure on closed agreement.")
            except ValidationError:
                errors += 1
            pending += request.status == "PENDING"
            accepted += request.status == "ACCEPTED"
            terminal += request.status in ("WITHDRAWN", "REJECTED")
            cancelled += request.status == "CANCELLED"
            settled += request.status == "SETTLED"
            if request.status == "SETTLED":
                from schemes.selectors import get_outstanding_entitlement
                review = closure_payment_review(request.scheme_account)
                try:
                    outstanding = get_outstanding_entitlement(request.scheme_account)
                except ValidationError:
                    errors += 1
                    continue
                if outstanding != 0 or any(
                    review[key] for key in ("pending_payments", "allocation_gaps", "unresolved_webhooks")
                ):
                    errors += 1
        for settlement in ConfiguredSettlement.objects.all().iterator(chunk_size=100):
            try:
                validate_configured_settlement(settlement)
                from schemes.independent_settlement_selectors import validate_independent_settlement_benefit
                validate_independent_settlement_benefit(settlement)
            except ValidationError:
                errors += 1
        errors += Redemption.objects.filter(scheme_account__configuration_snapshot__isnull=False, configured_settlement__isnull=True).count()
        errors += SchemeAccount.objects.filter(configuration_snapshot__isnull=False, status="REDEEMED").exclude(closure_requests__status="SETTLED").count()
        errors += SchemeAccount.objects.filter(status="CLOSURE_PENDING").exclude(savings_mode="INR_CREDIT").exclude(closure_requests__status="ACCEPTED", closure_requests__events__action="REVERSE").count()
        for account in SchemeAccount.objects.filter(status="CLOSURE_PENDING", savings_mode="INR_CREDIT"):
            from schemes.inr_settlement_selectors import inr_settlement_balance
            try:
                from schemes.inr_correction_selectors import validate_inr_disposition_state
                validate_inr_disposition_state(account)
                inr_settlement_balance(account)
            except ValidationError:
                errors += 1
        for account in SchemeAccount.objects.filter(status="CANCELLED").iterator(chunk_size=100):
            if account.closure_requests.filter(status="CANCELLED", events__action="CANCEL").count() != 1:
                errors += 1
        self.stdout.write(f"scheme_closures status={'error' if errors else 'ok'} release={settings.APP_RELEASE} pending={pending} accepted={accepted} withdrawn_or_rejected={terminal} cancelled_unused={cancelled} integrity_errors={errors} settled={settled} configured_intake_enabled={str(settings.CONFIGURED_PLANS_ENABLED).lower()}")
        if errors:
            raise CommandError("Closure evidence requires investigation; do not rewrite history.")
