from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from schemes.inr_selectors import get_inr_principal_summary
from schemes.inr_settlement_selectors import inr_settlement_balance
from schemes.models import SchemeAccount, InrPrincipalReceipt


class Command(BaseCommand):
    help = "Read-only INR purchase-credit principal evidence check; not activation or settlement readiness."

    def handle(self, *args, **options):
        accounts = SchemeAccount.objects.filter(savings_mode="INR_CREDIT").select_related("configuration_snapshot", "plan_revision")
        contracts = missing = source_errors = 0
        settlement_errors = 0
        outstanding = refund_pending = Decimal("0.00")
        for account in accounts:
            try:
                summary = get_inr_principal_summary(account)
            except ValidationError:
                contracts += 1
                continue
            missing += summary.unrecorded_sources
            source_errors += summary.source_errors
            try:
                balance = inr_settlement_balance(account)
                outstanding += balance.outstanding
                refund_pending += balance.refund_pending
                from schemes.inr_correction_selectors import validate_inr_disposition_state
                validate_inr_disposition_state(account)
            except ValidationError:
                settlement_errors += 1
        wrong_denomination = InrPrincipalReceipt.objects.exclude(scheme_account__savings_mode="INR_CREDIT").count()
        errors = contracts + missing + source_errors + wrong_denomination + settlement_errors
        self.stdout.write(f"inr_principal_check status={'error' if errors else 'ok'} release={settings.APP_RELEASE} "
                          f"workflow=not_activated accounts={len(accounts)} contract_errors={contracts} "
                          f"unrecorded_sources={missing} source_errors={source_errors} wrong_denomination={wrong_denomination} "
                          f"settlement_errors={settlement_errors} outstanding_inr={outstanding} refund_pending_inr={refund_pending}")
        if errors:
            raise CommandError("INR principal evidence requires review; no records were changed.")
