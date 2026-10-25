"""Schema-2 new-payment selectors; no activation, qualification or settlement permission."""
from datetime import datetime, time

from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils import timezone

from .agreement_contracts import validate_independent_account_terms
from .instalments import AGREEMENT_TIMEZONE, period_boundary
from .models import PaymentWebhookEvent


def optional_payment_window(terms, today):
    """Half-open ceiling only; never creates an instalment obligation."""
    index = (today.year - terms.start_date.year) * 12 + today.month - terms.start_date.month
    if terms.policy.period_basis == "ANNIVERSARY" and today < period_boundary(terms.policy, terms.start_date, index):
        index -= 1
    if index < 0:
        raise ValidationError("Contributions cannot precede enrolment.")
    return (period_boundary(terms.policy, terms.start_date, index),
            period_boundary(terms.policy, terms.start_date, index + 1))


def validate_independent_payment_window(account, *, contribution_date=None,
                                        contribution_period=None, exclude_contribution_id=None, at=None):
    """Called behind runtime readiness; mutation callers must hold the account lock.

    Cash ceilings use the server receipt instant, not a caller-supplied accounting
    month or database insertion timestamp. Online attempts block cash separately.
    """
    terms = validate_independent_account_terms(account)
    policy = terms.policy
    instant = at or timezone.now()
    if timezone.is_naive(instant):
        raise ValidationError("Payment admission needs an aware server instant.")
    today = instant.astimezone(AGREEMENT_TIMEZONE).date()
    accounting_month = today.replace(day=1)
    if contribution_date is not None and contribution_date != today:
        raise ValidationError("Independent payments cannot be backdated or paid in advance.")
    if contribution_period is not None and contribution_period != accounting_month:
        raise ValidationError("The accounting month cannot override the agreed payment window.")
    if account.status not in ("ACTIVE", "REDEMPTION_ELIGIBLE") or today < account.start_date:
        raise ValidationError("This agreement is not open for new contributions.")
    sources = account.contributions.all()
    unresolved = PaymentWebhookEvent.objects.filter(gateway="razorpay", gateway_mode="live",
        event_type="payment.captured").filter(Q(contribution__in=sources) | Q(
            gateway_order_id__in=sources.exclude(gateway_order_id="").values("gateway_order_id"))
        ).exclude(status__in=["PROCESSED", "IGNORED"])
    if sources.filter(status="PAID_UNALLOCATED").exists() or unresolved.exists():
        raise ValidationError("Reconcile unresolved payment or allocation evidence before another contribution.")
    if terms.savings_mode != "INR_CREDIT" and sources.filter(status="PAID", metal_allocation__isnull=True).exists():
        raise ValidationError("Reconcile a paid metal contribution without its allocation before another payment.")
    if terms.savings_mode == "INR_CREDIT":
        from .inr_selectors import get_inr_principal_summary
        if get_inr_principal_summary(account).needs_review:
            raise ValidationError("Reconcile INR principal evidence before another contribution.")
        if account.inr_settlements.exists():
            raise ValidationError("A final disposition blocks further contributions.")
    if not policy.allow_post_eligibility:
        if policy.eligibility == "DURATION" and today >= terms.duration_not_before:
            raise ValidationError("This agreement does not accept contributions after its duration.")
        if policy.eligibility == "ANYTIME" and sources.filter(status__in=["PAID", "PAID_UNALLOCATED"]).exists():
            raise ValidationError("This anytime agreement does not allow further contributions after verified entitlement.")
    if policy.obligation == "REQUIRED_MONTHLY":
        from .instalment_selectors import current_instalment_period
        current_instalment_period(account, exclude_contribution_id=exclude_contribution_id)
    elif policy.payment_limit == "ONCE_PER_PERIOD":
        start, end = optional_payment_window(terms, today)
        start_at = datetime.combine(start, time.min, tzinfo=AGREEMENT_TIMEZONE)
        end_at = datetime.combine(end, time.min, tzinfo=AGREEMENT_TIMEZONE)
        occupied = sources.filter(status__in=["PENDING", "PAID", "PAID_UNALLOCATED"]).filter(
            Q(payment_channel="IN_STORE_CASH", paid_at__gte=start_at, paid_at__lt=end_at)
            | (~Q(payment_channel="IN_STORE_CASH") & Q(created_at__gte=start_at, created_at__lt=end_at)))
        if exclude_contribution_id is not None:
            occupied = occupied.exclude(pk=exclude_contribution_id)
        if occupied.exists():
            raise ValidationError("This optional payment window already has a payment or unresolved attempt.")
    return accounting_month
