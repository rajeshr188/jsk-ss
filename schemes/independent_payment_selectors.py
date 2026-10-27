"""Schema-2 new-payment selectors; no activation, qualification or settlement permission."""
from datetime import datetime, time

from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils import timezone

from schemes.payment_refund_selectors import unresolved_payment_events

from .agreement_contracts import validate_independent_account_terms
from .instalments import AGREEMENT_TIMEZONE, period_boundary
from .models import PaymentWebhookEvent, OptionalPaymentOrderRequest, Contribution


def unbound_optional_order_contributions():
    """Durable requests needing identity investigation, even before checkout expiry."""
    return Contribution.objects.filter(optional_order_request__isnull=False,
        optional_order_request__binding__isnull=True)


def optional_order_summary():
    result = dict(requests=0, unbound_requests=0, recovered_orders=0, pending_without_request=0, integrity_errors=0)
    sources = Contribution.objects.filter(scheme_account__agreement_schema_version=2,
        payment_gateway="razorpay").exclude(scheme_account__configuration_snapshot__instalment_policy="MONTHLY_COMPLETION")
    missing = sources.filter(optional_order_request__isnull=True)
    unstarted = Q(status="PENDING") & (Q(gateway_order_id="") | Q(gateway_order_id__isnull=True))
    result["pending_without_request"] = missing.filter(unstarted).count()
    result["integrity_errors"] = missing.exclude(unstarted).count()
    for intent in OptionalPaymentOrderRequest.objects.select_related("contribution__scheme_account", "binding").iterator():
        result["requests"] += 1
        binding = getattr(intent, "binding", None)
        result["unbound_requests"] += int(binding is None)
        result["recovered_orders"] += int(binding is not None and binding.recovered)
        try:
            intent.full_clean()
            if binding:
                binding.full_clean()
            elif intent.contribution.gateway_order_id or intent.contribution.status not in ("PENDING", "FAILED"):
                raise ValidationError("Unbound request has contradictory source state.")
        except ValidationError:
            result["integrity_errors"] += 1
    return result


def optional_order_request(contribution):
    intent = OptionalPaymentOrderRequest.objects.select_related("contribution__scheme_account").get(contribution=contribution)
    intent.full_clean()
    return intent


def require_optional_order_integrity(account, *, exclude_contribution_id=None):
    """Account-locked callers may resume one attempt, never discard uncertainty."""
    unstarted = Q(status="PENDING") & (Q(gateway_order_id="") | Q(gateway_order_id__isnull=True))
    if account.contributions.filter(payment_gateway="razorpay", optional_order_request__isnull=True).exclude(unstarted).exists():
        raise ValidationError("Optional provider history without durable request evidence requires reconciliation.")
    for intent in OptionalPaymentOrderRequest.objects.select_related(
            "contribution__scheme_account", "binding").filter(contribution__scheme_account=account):
        intent.full_clean()
        c = intent.contribution
        binding = getattr(intent, "binding", None)
        if binding is None:
            raise ValidationError("An optional order request is unresolved; recover its exact provider identity before another payment.")
        binding.full_clean()
        if c.status == "FAILED":
            raise ValidationError("A failed optional order still needs provider reconciliation.")
        from .payment_refund_selectors import is_refunded_order_retired
        if c.status == "ABANDONED" and not is_refunded_order_retired(c) and not c.audit_events.filter(action="PAYMENT_ORDER_RECONCILIATION",
                details__applied=True, details__outcome="ELIGIBLE_FOR_ABANDONMENT",
                details__gateway_order_id=c.gateway_order_id).exists():
            raise ValidationError("An abandoned optional order needs its retained provider reconciliation evidence.")
    pending = account.contributions.filter(payment_gateway="razorpay", status="PENDING")
    if exclude_contribution_id is not None:
        pending = pending.exclude(pk=exclude_contribution_id)
    if pending.exists():
        raise ValidationError("Complete or reconcile the existing optional checkout before another payment.")


def resumable_optional_contribution(account):
    pending = list(account.contributions.filter(payment_gateway="razorpay", status="PENDING").order_by("pk")[:2])
    if not pending:
        require_optional_order_integrity(account)
        return None
    if len(pending) != 1:
        raise ValidationError("Multiple pending optional checkouts require reconciliation.")
    contribution = pending[0]
    require_optional_order_integrity(account, exclude_contribution_id=contribution.pk)
    if contribution.gateway_mode != "live" or contribution.razorpay_checkout_expired:
        raise ValidationError("This checkout is expired or mode-mismatched; reconcile it before another payment.")
    intent = getattr(contribution, "optional_order_request", None)
    if contribution.gateway_order_id:
        if intent is None or not hasattr(intent, "binding") or intent.binding.recovered:
            raise ValidationError("Recovered or unproven orders are reconciliation-only, not resumable checkout.")
    elif intent is not None:
        raise ValidationError("This order request is already underway; do not send it again.")
    return contribution


def optional_checkout_deadline(account, deadline, *, at):
    terms = validate_independent_account_terms(account)
    if terms.policy.payment_limit == "ONCE_PER_PERIOD":
        _, end = optional_payment_window(terms, at.astimezone(AGREEMENT_TIMEZONE).date())
        deadline = min(deadline, datetime.combine(end, time.min, tzinfo=AGREEMENT_TIMEZONE))
    if terms.duration_not_before and not terms.policy.allow_post_eligibility:
        deadline = min(deadline, datetime.combine(terms.duration_not_before, time.min, tzinfo=AGREEMENT_TIMEZONE))
    return deadline


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
    if policy.obligation == "OPTIONAL":
        require_optional_order_integrity(account, exclude_contribution_id=exclude_contribution_id)
    unresolved = PaymentWebhookEvent.objects.filter(gateway="razorpay", gateway_mode="live",
        event_type="payment.captured").filter(Q(contribution__in=sources) | Q(
            gateway_order_id__in=sources.exclude(gateway_order_id="").values("gateway_order_id"))
        )
    unresolved = unresolved_payment_events(unresolved)
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
