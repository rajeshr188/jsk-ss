"""Bounded, acknowledged outage amendments. Never resolves uncertain provider funds."""
import uuid
from datetime import datetime, time

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .instalments import AGREEMENT_TIMEZONE, compensation_window
from .instalment_selectors import require_reconciled_outage_payments, validated_instalment_periods
from .models import (
    InstalmentOutageResolution, InstalmentReservation, InstalmentReview,
    SchemeAccount, SchemeInstalmentPeriod,
)


@transaction.atomic
def resolve_instalment_outage(*, hold_id, actor, outcome, reason, evidence_reference,
    incident_started_at, service_restored_at, customer_acknowledged_at,
    acknowledgement_reference, idempotency_key, expected_review_sequence, expected_period_count):
    from .services import _validate_owner, _actor_label

    _validate_owner(actor)
    text = dict(reason=reason, evidence_reference=evidence_reference,
        acknowledgement_reference=acknowledgement_reference)
    for name, value in text.items():
        if not isinstance(value, str) or not value.strip() or len(value.strip()) > (2000 if name == "reason" else 254):
            raise ValidationError("Incident reason, evidence and customer acknowledgement references are required.")
        text[name] = value.strip()
    try:
        key = uuid.UUID(str(idempotency_key))
    except (ValueError, TypeError, AttributeError):
        raise ValidationError("A valid resolution submission identifier is required.") from None
    hold = InstalmentReview.objects.select_related("period").get(pk=hold_id)
    account = SchemeAccount.objects.select_for_update().get(pk=hold.period.scheme_account_id)
    if account.status == "CANCELLED":
        raise ValidationError("A cancelled unused agreement cannot receive outage amendments.")
    facts = dict(hold_id=hold.pk, scheme_account_id=account.pk, period_id=hold.period_id,
        actor_id=actor.pk, outcome=outcome, incident_started_at=incident_started_at,
        service_restored_at=service_restored_at, customer_acknowledged_at=customer_acknowledged_at, **text)
    existing = InstalmentOutageResolution.objects.filter(idempotency_key=key).first()
    if existing:
        if any(getattr(existing, name) != value for name, value in facts.items()):
            raise ValidationError("This submission identifier already records a different outage resolution.")
        return existing
    if hold.action != "OUTAGE_HOLD" or hasattr(hold, "outage_resolution"):
        raise ValidationError("Select an unresolved outage hold.")
    periods = validated_instalment_periods(account)
    sequence = hold.period.reviews.order_by("-sequence").first().sequence
    if (type(expected_review_sequence) is not int or expected_review_sequence != sequence
        or type(expected_period_count) is not int or expected_period_count != len(periods)):
        raise ValidationError("The review or schedule changed. Reload and obtain acknowledgement of the current proposal.")
    now = timezone.now()
    timestamps = (incident_started_at, service_restored_at, customer_acknowledged_at)
    if any(not isinstance(value, datetime) or timezone.is_naive(value) for value in timestamps):
        raise ValidationError("Use timezone-aware incident and customer acknowledgement timestamps.")
    if not incident_started_at < service_restored_at <= customer_acknowledged_at <= now or customer_acknowledged_at < hold.created_at:
        raise ValidationError("Record a restored incident and genuine subsequent acknowledgement, not future or pre-review consent.")
    start = datetime.combine(hold.period.starts_on, time.min, AGREEMENT_TIMEZONE)
    end = datetime.combine(hold.period.ends_before, time.min, AGREEMENT_TIMEZONE)
    if incident_started_at >= end or service_restored_at <= start:
        raise ValidationError("The evidenced incident must overlap the affected monthly window.")
    if account.status != "ACTIVE":
        raise ValidationError("Only an active monthly agreement can receive an outage resolution.")

    # The lock serializes financial mutations. A note/acknowledgement cannot stand
    # in for provider reconciliation or free an ORDERING / late-capture claim.
    require_reconciled_outage_payments(account)
    claims = InstalmentReservation.objects.filter(period__scheme_account=account)
    qualified = claims.filter(period=hold.period, state="QUALIFIED").first()
    number = extra = None
    if outcome == "COMPENSATE":
        if now < end or qualified or claims.filter(state="QUALIFIED").count() >= account.agreed_months:
            raise ValidationError("Compensation requires an ended unpaid outage-affected window and an incomplete payment count.")
        if account.outage_resolutions.filter(period=hold.period, outcome="COMPENSATE").exists():
            raise ValidationError("This affected period has already received compensation.")
        number = account.outage_resolutions.filter(outcome="COMPENSATE").count() + 1
        window = compensation_window(account, number)
        if timezone.localdate(now, AGREEMENT_TIMEZONE) >= window.starts_on:
            raise ValidationError("The proposed compensating month has already begun; retain the hold for separate agreement review.")
        # Dates come only from the original agreed period basis. Bulk insertion is
        # restricted to this atomic pair: period + immutable acknowledged amendment.
        extra = SchemeInstalmentPeriod.objects.bulk_create([SchemeInstalmentPeriod(
            scheme_account=account, number=window.number, starts_on=window.starts_on,
            ends_before=window.ends_before, amount=window.amount, created_by=actor,
            actor_label=_actor_label(actor), reason=text["reason"],
        )])[0]
    elif outcome == "RESTORED":
        if not start <= now < end or service_restored_at >= end or qualified:
            raise ValidationError("Resume without compensation only while the original unpaid window remains open.")
    elif outcome == "QUALIFIED":
        if not qualified:
            raise ValidationError("Existing verified qualification for this period is required.")
    else:
        raise ValidationError("Unsupported outage resolution; there is no waive or forfeit action.")
    result = InstalmentOutageResolution.objects.create(**facts, compensation_number=number,
        compensation_period=extra, actor_label=_actor_label(actor), idempotency_key=key,
        qualification_decision=qualified.decisions.order_by("-sequence").first() if outcome == "QUALIFIED" else None)
    validated_instalment_periods(account)
    return result
