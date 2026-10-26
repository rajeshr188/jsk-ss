"""Current, fully evidenced INR completion notices; no financial writes."""
from django.conf import settings
from django.core.exceptions import ValidationError

from .models import InrSettlementCompletion
from .independent_reminders import reminder_workflow_available
from .inr_correction_selectors import validate_inr_history
from .independent_inr_settlement_selectors import validate_independent_inr_benefit
from .closure_selectors import validate_closure_history


def completed_inr_events(*, as_of, account=None, completion_id=None):
    if not settings.CONFIGURED_PLANS_ENABLED:
        return
    rows = InrSettlementCompletion.objects.filter(
        event__created_at__date=as_of, proposal__retired=False,
        proposal__resolution__isnull=True, proposal__closure__status="SETTLED",
        proposal__scheme_account__status="REDEEMED",
        proposal__scheme_account__agreement_schema_version=2,
    ).select_related("event", "proposal__closure", "proposal__scheme_account__customer__user",
                     "proposal__scheme_account__configuration_snapshot")
    if account is not None:
        rows = rows.filter(proposal__scheme_account=account)
    if completion_id is not None:
        rows = rows.filter(pk=completion_id)
    for completion in rows.order_by("pk"):
        p = completion.proposal
        if "independent" not in p.evidence or not reminder_workflow_available(p.scheme_account):
            continue
        try:
            validate_inr_history(p.scheme_account)
            validate_closure_history(p.closure)
            validate_independent_inr_benefit(p, current=True)
        except ValidationError:
            # Existing financial integrity diagnostics own the reconciliation alert.
            # Do not turn an uncertain disposition into a completion claim.
            continue
        yield completion
