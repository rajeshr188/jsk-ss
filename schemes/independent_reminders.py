"""Gated date-progress reminders; count-only and anytime have no forecast date."""
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils import timezone

from .agreement_eligibility import get_independent_eligibility
from .instalments import AGREEMENT_TIMEZONE
from .models import SchemeAccount, SchemeReminder
from .plan_policies import require_operational_configuration


def reminder_workflow_available(account):
    if not settings.CONFIGURED_PLANS_ENABLED or not account.configuration_snapshot_id:
        return False
    try:
        require_operational_configuration(account.configuration_snapshot)
    except ValidationError:
        return False
    return True


def independent_reminder_terms(account, *, as_of):
    if (as_of != timezone.localdate(timezone=AGREEMENT_TIMEZONE)
            or account.status != SchemeAccount.Status.ACTIVE
            or not reminder_workflow_available(account)):
        return None
    progress = get_independent_eligibility(account, as_of=as_of)
    if progress.state == "WAITING_DURATION" and progress.eligibility_policy == "DURATION":
        return SchemeReminder.Kind.UPCOMING_ELIGIBILITY, progress.completion_date
    if progress.state == "WAITING_PERIOD_END" and progress.eligibility_policy == "DURATION_AND_COUNT":
        return SchemeReminder.Kind.UPCOMING_MONTHLY_COMPLETION, progress.completion_date
    return None


def upcoming_independent_accounts(*, as_of, lead_days):
    if not settings.CONFIGURED_PLANS_ENABLED or as_of != timezone.localdate(timezone=AGREEMENT_TIMEZONE):
        return SchemeAccount.objects.none()
    dates = [as_of + timedelta(days=days) for days in lead_days]
    return SchemeAccount.objects.filter(agreement_schema_version=2, status="ACTIVE").filter(
        Q(eligible_from__in=dates) | Q(instalment_periods__ends_before__in=dates)
    ).select_related("customer__user", "configuration_snapshot", "plan", "metal_grade").distinct().order_by("pk")
