"""Owner review of existing evidence, not a financial/contractual override."""
import uuid

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .instalment_payments import _append, _evidence_target, _timing_state
from .instalments import AGREEMENT_TIMEZONE
from .instalment_selectors import validated_instalment_periods, require_no_capture_exception
from .models import InstalmentReview, SchemeAccount, SchemeInstalmentPeriod


def verified_timing_source(reservation, source_id):
    """Only later signed evidence resolving missing timing, not conflicting evidence."""
    source = reservation.decisions.select_related("webhook_event").filter(pk=source_id).first()
    if source is None or source.webhook_event_id is None:
        raise ValidationError("Choose existing signed capture timing evidence for this payment.")
    event, contribution = source.webhook_event, reservation.contribution
    if (contribution.status not in ("PAID", "PAID_UNALLOCATED")
        or contribution.payment_channel != "RAZORPAY" or contribution.gateway_mode != "live"
        or event.status != "PROCESSED" or event.event_type != "payment.captured"
        or event.gateway != "razorpay" or event.gateway_mode != "live"
        or event.contribution_id != contribution.pk
        or event.gateway_reference != contribution.gateway_reference
        or event.gateway_order_id != contribution.gateway_order_id):
        raise ValidationError("Independently verified Live funds and matching processed evidence are required.")
    if reservation.decisions.filter(state="REVIEW").exclude(
        reason_code__in=["MISSING_PROVIDER_TIMING", "PRIOR_REVIEW_UNRESOLVED"]
    ).exists():
        raise ValidationError("Conflicting or out-of-deadline evidence needs separate investigation; no override is allowed.")
    state, _ = _timing_state(reservation, source.earliest_at, source.latest_at,
        event.received_at, provider_seconds=True)
    if state != "QUALIFIED":
        raise ValidationError("The selected evidence does not prove payment within the original period and checkout deadline.")
    return source


@transaction.atomic
def record_instalment_review(*, period_id, actor, action, reason, evidence_reference,
    idempotency_key, expected_review_sequence, reservation_id=None,
    source_decision_id=None, expected_payment_sequence=None):
    from .services import _validate_owner, _actor_label

    _validate_owner(actor)
    reason, evidence_reference = reason.strip(), evidence_reference.strip()
    if not reason or len(reason) > 2000 or not evidence_reference or len(evidence_reference) > 254:
        raise ValidationError("A concise investigation reason and evidence reference are required.")
    try:
        key = uuid.UUID(str(idempotency_key))
    except (ValueError, TypeError, AttributeError):
        raise ValidationError("A valid review submission identifier is required.") from None
    period = SchemeInstalmentPeriod.objects.get(pk=period_id)
    account = SchemeAccount.objects.select_for_update().get(pk=period.scheme_account_id)
    if account.agreement_schema_version == 2:
        from .plan_policies import require_operational_configuration
        require_operational_configuration(account.configuration_snapshot)
    if account.status == "CANCELLED":
        raise ValidationError("A cancelled unused agreement cannot acquire new instalment reviews.")
    validated_instalment_periods(account)
    facts = dict(period_id=period.pk, actor_id=actor.pk, action=action, reason=reason,
        evidence_reference=evidence_reference, reservation_id=reservation_id, source_decision_id=source_decision_id)
    existing = InstalmentReview.objects.filter(idempotency_key=key).first()
    if existing:
        if any(getattr(existing, name) != value for name, value in facts.items()):
            raise ValidationError("This submission identifier was already used for a different review.")
        return existing
    last = period.reviews.order_by("-sequence").first()
    sequence = last.sequence if last else 0
    if type(expected_review_sequence) is not int or expected_review_sequence != sequence:
        raise ValidationError("Another owner review was recorded. Reload and inspect the updated evidence.")
    reservation = source = None
    if reservation_id is not None:
        claim = period.reservations.filter(pk=reservation_id).first()
        if claim is None:
            raise ValidationError("Select a payment belonging to this period.")
        _, reservation = _evidence_target(claim.contribution_id)
        if type(expected_payment_sequence) is not int or expected_payment_sequence != reservation.decisions.order_by("-sequence").first().sequence:
            raise ValidationError("Payment evidence changed. Reload before making a decision.")
    if action == InstalmentReview.Action.ACCEPT_TIMING:
        require_no_capture_exception(account)
        if reservation is None or reservation.state not in ("REVIEW", "AWAITING"):
            raise ValidationError("Only an unresolved timing review may accept verified timing evidence.")
        source = verified_timing_source(reservation, source_decision_id)
    elif action == InstalmentReview.Action.OUTAGE_HOLD:
        if reservation_id is not None or source_decision_id is not None:
            raise ValidationError("An outage hold records the affected period, not a payment credit.")
        if period.starts_on > timezone.localdate(timezone=AGREEMENT_TIMEZONE):
            raise ValidationError("Record an actual current or past outage, not a future assumption.")
        if period.reviews.filter(action="OUTAGE_HOLD", outage_resolution__isnull=True).exists():
            raise ValidationError("This period already has an unresolved outage hold; add an investigation note instead.")
    elif action != InstalmentReview.Action.NOTE or source_decision_id is not None:
        raise ValidationError("Unsupported review action or evidence selection.")
    review = InstalmentReview.objects.create(**facts, sequence=sequence + 1,
        idempotency_key=key, actor_label=_actor_label(actor))
    if source is not None:
        _append(reservation, "QUALIFIED", "OWNER_VERIFIED_TIMING", owner_review=review,
            earliest_at=source.earliest_at, latest_at=source.latest_at, actor_label=review.actor_label)
    return review
