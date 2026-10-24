"""Gated monthly payment ledger, called explicitly by financial services.

These functions neither collect money nor allocate metal nor grant eligibility.
Payment creation and verified-payment/correction services call these explicitly.
Provider order intent uses a separate durable boundary before network I/O.
All writers serialize on the agreement before contribution/reservation locks.
"""
import hashlib
import json
import uuid
from datetime import datetime, time, timedelta, timezone as datetime_timezone

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .instalments import AGREEMENT_TIMEZONE, validate_real_instalment_channel, window_for_instant
from .instalment_selectors import validated_instalment_periods, require_no_outage_hold, require_no_capture_exception
from .models import (
    AuditEvent, Contribution, InStoreCashContributionReversal, InStoreCashReceipt,
    InstalmentPaymentDecision, InstalmentReservation, PaymentWebhookEvent, SchemeAccount,
)


def _lock_contribution(contribution_id):
    account_id = Contribution.objects.values_list('scheme_account_id', flat=True).get(pk=contribution_id)
    account = SchemeAccount.objects.select_for_update().get(pk=account_id)
    contribution = Contribution.objects.select_for_update().get(pk=contribution_id)
    return account, contribution


def _append(reservation, state, code, *, actor_label='system:instalment-evidence', **proof):
    previous = reservation.decisions.order_by("-sequence").first()
    if previous and previous.state != reservation.state:
        raise ValidationError('Instalment decision history and projection disagree; review required.')
    decision = InstalmentPaymentDecision.objects.create(
        reservation=reservation, sequence=previous.sequence + 1 if previous else 1,
        state=state, reason_code=code, actor_label=actor_label, **proof,
    )
    InstalmentReservation.objects.filter(pk=reservation.pk).update(state=state)
    reservation.state = state
    return decision


@transaction.atomic
def reserve_instalment(*, contribution_id):
    """Claim the current agreed monthly window across both channels, never backfill.

    A deadline does not cancel a provider order, so expiration alone cannot release
    this claim. No generic release/override is offered by this foundation.
    """
    account, contribution = _lock_contribution(contribution_id)
    periods = validated_instalment_periods(account)
    validate_real_instalment_channel(contribution)
    existing = InstalmentReservation.objects.filter(contribution=contribution).first()
    if existing:
        last = existing.decisions.order_by("-sequence").first()
        if last is None or last.state != existing.state:
            raise ValidationError('The existing reservation needs integrity review.')
        return existing
    require_no_outage_hold(account)
    require_no_capture_exception(account)
    if contribution.payment_gateway == 'razorpay' and (
        contribution.status != "PENDING" or contribution.gateway_order_id
    ):
        raise ValidationError('Reserve before creating the Razorpay order; historical attribution is not allowed.')
    now = timezone.now()
    period = window_for_instant(periods, now)
    if (
        account.status != "ACTIVE" or period is None
        or window_for_instant(periods, contribution.created_at) != period
        or contribution.amount != period.amount
        or contribution.status not in ("PENDING", "PAID", "PAID_UNALLOCATED")
    ):
        raise ValidationError('A current active agreement payment for the exact period amount is required.')
    claims = InstalmentReservation.objects.filter(period__scheme_account=account)
    if claims.filter(state__in=["RESERVED", "ORDERING", "AWAITING", "REVIEW", "RELEASED_REVIEW"]).exists():
        raise ValidationError('Resolve the existing reservation or timing review before another payment.')
    if claims.filter(state="QUALIFIED").count() >= account.agreed_months:
        raise ValidationError('The required payment count is already complete.')
    if claims.filter(period=period).exclude(state__in=["REVERSED", "RELEASED"]).exists():
        raise ValidationError("This monthly period already has a payment claim.")
    end = datetime.combine(period.ends_before, time.min, tzinfo=AGREEMENT_TIMEZONE)
    if contribution.payment_gateway == 'razorpay':
        if contribution.checkout_expires_at is None:
            raise ValidationError('Razorpay checkout must have an explicit deadline.')
        end = min(end, contribution.checkout_expires_at)
    if now >= end:
        raise ValidationError('An expired checkout cannot acquire a new reservation.')
    reservation = InstalmentReservation.objects.create(
        contribution=contribution, period=period, reserved_at=now, expires_at=end,
    )
    _append(reservation, "RESERVED", "CURRENT_PERIOD_RESERVED")
    return reservation


def _evidence_target(contribution_id):
    account, contribution = _lock_contribution(contribution_id)
    validated_instalment_periods(account)
    validate_real_instalment_channel(contribution)
    reservation = InstalmentReservation.objects.select_for_update().get(contribution=contribution)
    if reservation.period.scheme_account_id != account.pk or reservation.period.amount != contribution.amount:
        raise ValidationError('Reservation contract mismatch; review required.')
    last = reservation.decisions.order_by("-sequence").first()
    if last is None or last.state != reservation.state:
        raise ValidationError('Reservation projection needs integrity review.')
    return contribution, reservation


def _timing_state(reservation, earliest, latest, received_at, *, provider_seconds=False):
    if earliest is None or latest is None:
        return "REVIEW", "MISSING_PROVIDER_TIMING"
    if latest < earliest or latest > received_at or (
        provider_seconds and earliest < reservation.contribution.created_at.replace(microsecond=0)
    ):
        return "REVIEW", "INCONSISTENT_PAYMENT_TIMING"
    # Unix-second evidence is not subsecond precision. Review the final second at
    # a boundary rather than accepting an event that might have crossed it.
    upper = latest + timedelta(seconds=1) if provider_seconds else latest
    period = reservation.period
    if window_for_instant([period], earliest) is None or window_for_instant([period], upper) is None:
        return "REVIEW", "PERIOD_BOUNDARY_REVIEW"
    # A previously opened checkout may still capture after its local timeout. Do not
    # silently apply an expired locked rate/period decision; keep the money evidence.
    if upper >= reservation.expires_at:
        return "REVIEW", "CHECKOUT_DEADLINE_REVIEW"
    return "QUALIFIED", "VERIFIED_WITHIN_PERIOD"


@transaction.atomic
def attribute_cash_instalment(*, contribution_id):
    contribution, reservation = _evidence_target(contribution_id)
    if contribution.payment_channel != "IN_STORE_CASH" or contribution.status not in ("PAID", "PAID_UNALLOCATED"):
        raise ValidationError('A verified, unreversed showroom cash receipt is required.')
    receipt = InStoreCashReceipt.objects.get(contribution=contribution)
    existing = reservation.decisions.filter(cash_receipt=receipt).first()
    if existing:
        return existing
    if reservation.state not in ("RESERVED", "REVIEW"):
        raise ValidationError('This payment has already reached a terminal attribution state.')
    state, code = _timing_state(reservation, receipt.received_at, receipt.received_at, timezone.now())
    return _append(reservation, state, code, cash_receipt=receipt,
        earliest_at=receipt.received_at, latest_at=receipt.received_at, actor_label=receipt.received_by_label)


def _provider_instant(value):
    # Reject bool, float, strings and milliseconds rather than guessing units.
    if type(value) is not int or value <= 0:
        return None
    try:
        return datetime.fromtimestamp(value, datetime_timezone.utc)
    except (ValueError, OverflowError, OSError):
        return None


@transaction.atomic
def attribute_razorpay_instalment(*, event_id, body):
    """Use a processed captured event's exact, previously signature-verified body.

    This is an internal consumer, NOT a webhook authentication endpoint. The caller
    must already have verified the signature and processed the payment. Match the
    stored hash and safe identity/amount facts again. Never persist the raw payload.
    Payment creation and event creation bound timing conservatively; neither local
    confirmation nor webhook arrival is substituted for a provider timestamp.
    """
    event = PaymentWebhookEvent.objects.get(pk=event_id)
    if (event.status != "PROCESSED" or event.event_type != 'payment.captured'
        or event.gateway != 'razorpay' or event.gateway_mode != "live" or event.contribution_id is None
        or not isinstance(body, bytes) or hashlib.sha256(body).hexdigest() != event.payload_sha256):
        raise ValidationError('Processed live capture evidence with its original body is required.')
    contribution, reservation = _evidence_target(event.contribution_id)
    if contribution.payment_channel != "RAZORPAY" or contribution.status not in ("PAID", "PAID_UNALLOCATED"):
        raise ValidationError('The payment must already be independently verified.')
    try:
        payload = json.loads(body)
        payment = payload['payload']['payment']["entity"]
        valid = (payload["event"] == 'payment.captured'
            and isinstance(payment["id"], str) and bool(payment["id"])
            and isinstance(payment["order_id"], str) and bool(payment["order_id"])
            and payment["id"] == contribution.gateway_reference == event.gateway_reference
            and payment["order_id"] == contribution.gateway_order_id == event.gateway_order_id
            and payment['status'] == 'captured' and payment['captured'] is True
            and payment["currency"] == "INR" and type(payment['amount']) is int
            and payment['amount'] == contribution.amount * 100)
    except (KeyError, TypeError, ValueError):
        valid = False
    if not valid:
        raise ValidationError('Capture payload and verified contribution do not match.')
    existing = reservation.decisions.filter(webhook_event=event).first()
    if existing:
        return existing
    if reservation.state not in ("RESERVED", "AWAITING", "REVIEW", "QUALIFIED"):
        raise ValidationError('A reversed payment cannot qualify again.')
    earliest = _provider_instant(payment.get('created_at'))
    latest = _provider_instant(payload.get('created_at'))
    state, code = _timing_state(reservation, earliest, latest, event.received_at, provider_seconds=True)
    if reservation.state == "REVIEW" and state == "QUALIFIED":
        state, code = "REVIEW", "PRIOR_REVIEW_UNRESOLVED"
    # Conflicting evidence must remain visible. A second event never adds a second
    # credit, and can place the existing claim into review rather than hide conflict.
    return _append(reservation, state, code, webhook_event=event, earliest_at=earliest, latest_at=latest)


@transaction.atomic
def reverse_cash_instalment(*, contribution_id):
    'Mirror an already-authorized financial reversal; never reverse money here.'
    contribution, reservation = _evidence_target(contribution_id)
    if contribution.payment_channel != "IN_STORE_CASH" or contribution.status != "REVERSED":
        raise ValidationError('Complete the authorized cash correction before reversing qualification.')
    reversal = InStoreCashContributionReversal.objects.get(contribution=contribution)
    existing = reservation.decisions.filter(cash_reversal=reversal).first()
    if existing:
        return existing
    return _append(reservation, "REVERSED", "CASH_ENTRY_REVERSED", cash_reversal=reversal,
        actor_label=reversal.processed_by_label)


@transaction.atomic
def note_verified_instalment(*, contribution_id):
    """Callback/API verification proves funds, not which monthly period counts."""
    contribution, reservation = _evidence_target(contribution_id)
    if contribution.status not in ("PAID", "PAID_UNALLOCATED"):
        raise ValidationError('Only an independently verified payment may await timing evidence.')
    if reservation.state == "RESERVED":
        return _append(reservation, "AWAITING", "VERIFIED_TIMING_PENDING")
    if reservation.state not in ("AWAITING", "QUALIFIED", "REVIEW"):
        raise ValidationError('A released/reversed claim cannot be automatically confirmed.')
    return reservation.decisions.order_by("-sequence").first()


@transaction.atomic(durable=True)
def begin_instalment_order_request(*, contribution_id):
    'Persist intent before provider I/O; uncertain attempts cannot be retried blindly.'
    contribution, reservation = _evidence_target(contribution_id)
    from .closure_selectors import require_no_accepted_closure
    require_no_accepted_closure(contribution.scheme_account)
    if contribution.gateway_order_id:
        return False
    if contribution.status != "PENDING" or reservation.state != "RESERVED" or timezone.now() >= reservation.expires_at:
        raise ValidationError('An order request is already underway or requires reconciliation; do not create another.')
    _append(reservation, "ORDERING", "PROVIDER_ORDER_REQUEST_STARTED", request_token=uuid.uuid4())
    return True


@transaction.atomic
def complete_instalment_order_request(*, contribution_id):
    contribution, reservation = _evidence_target(contribution_id)
    if not contribution.gateway_order_id or contribution.status != "PENDING" or reservation.state != "ORDERING":
        raise ValidationError('The reserved provider order was not recorded consistently.')
    return _append(reservation, "RESERVED", "PROVIDER_ORDER_RECORDED")


@transaction.atomic
def release_reconciled_instalment(*, contribution_id, audit_id):
    contribution, reservation = _evidence_target(contribution_id)
    audit = AuditEvent.objects.get(pk=audit_id, contribution=contribution,
        action=AuditEvent.Action.PAYMENT_ORDER_RECONCILIATION)
    facts = audit.details
    amount = int(contribution.amount * 100)
    expected = {'applied': True, 'outcome': "ELIGIBLE_FOR_ABANDONMENT",
        'gateway': 'razorpay', 'gateway_mode': "live", 'gateway_order_id': contribution.gateway_order_id,
        'provider_order_status': 'created', 'provider_attempts': 0,
        'provider_amount_subunits': amount, 'provider_amount_paid_subunits': 0,
        'provider_amount_due_subunits': amount, 'provider_payment_count': 0, 'provider_payment_statuses': []}
    if (contribution.status != "ABANDONED" or contribution.payment_gateway != 'razorpay'
        or timezone.now() < reservation.expires_at or any(facts.get(k) != v for k, v in expected.items())):
        raise ValidationError('Release requires an expired, provider-reconciled untouched order and its audit.')
    existing = reservation.decisions.filter(reconciliation_audit=audit).first()
    if existing:
        return existing
    if reservation.state != "RESERVED":
        raise ValidationError('Only an unpaid reserved claim may be released.')
    return _append(reservation, "RELEASED", "UNTOUCHED_ORDER_RECONCILED",
        reconciliation_audit=audit, actor_label=audit.actor_label)


@transaction.atomic
def note_late_instalment_capture(*, event_id):
    event = PaymentWebhookEvent.objects.get(pk=event_id, status="REVIEW_REQUIRED",
        failure_code="LATE_CAPTURE_ABANDONED", gateway_mode="live", event_type='payment.captured')
    contribution, reservation = _evidence_target(event.contribution_id)
    if reservation.state not in ("RELEASED", "RELEASED_REVIEW") or contribution.status != "ABANDONED":
        raise ValidationError('Late-capture review requires a reconciled released claim.')
    existing = reservation.decisions.filter(webhook_event=event).first()
    if existing:
        return existing
    # Non-occupying review preserves any replacement claim, while the account-level
    # guard prevents further initiation. Existing provider exception handling owns funds.
    return _append(reservation, "RELEASED_REVIEW", "LATE_CAPTURE_AFTER_RELEASE", webhook_event=event)
