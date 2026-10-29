"""Explicit closure-intent lifecycle. No settlement, refund or account deletion."""
import uuid

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction

from .closure_selectors import require_unused_agreement, validate_closure_history
from .models import SchemeAccount, SchemeClosureEvent, SchemeClosureRequest


def _key(value):
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        raise ValidationError("A valid submission identifier is required.") from None


def _text(value, limit, label, *, required=True):
    if not isinstance(value, str):
        raise ValidationError(f"Enter {label}.")
    value = value.strip()
    if (required and not value) or len(value) > limit:
        raise ValidationError(f"Enter {label} (at most {limit} characters).")
    return value


def _actor(actor, account):
    # Do not trust stale role/activity flags from the caller.
    if actor is None or not actor.pk:
        raise ValidationError("An active authenticated actor is required.")
    user = get_user_model().objects.get(pk=actor.pk)
    if not user.is_active or user.privacy_erased_at is not None:
        raise ValidationError("An active authenticated actor is required.")
    owner = user.is_superuser or user.role == "OWNER"
    customer = user.role == "CUSTOMER" and user.pk == account.customer.user_id
    if not (owner or customer):
        raise ValidationError("Only this customer or an active owner may review this closure.")
    return user, owner


def _account(account_id):
    account = SchemeAccount.objects.select_for_update().get(pk=account_id)
    from .plan_policies import require_current_payment_workflow
    require_current_payment_workflow(account)
    if not account.configuration_snapshot_id:
        raise ValidationError("Closure preparation supports configured agreements only; legacy cutover requires separate acceptance.")
    return account


def _matching(existing, facts):
    if any(getattr(existing, field) != value for field, value in facts.items()):
        raise ValidationError("This submission identifier was used for different closure evidence.")


@transaction.atomic
def request_scheme_closure(*, account_id, actor, reason, idempotency_key, authorization_reference=""):
    from .services import _actor_label
    account = _account(account_id)
    actor, owner = _actor(actor, account)
    reason = _text(reason, 2000, "a closure reason")
    reference = _text(authorization_reference, 254, "the customer's authorization reference", required=owner)
    if not owner and reference:
        raise ValidationError("A direct customer request does not use owner-assisted authorization.")
    facts = dict(scheme_account_id=account.pk, requested_by_id=actor.pk,
        source="OWNER_ASSISTED" if owner else "CUSTOMER", reason=reason, authorization_reference=reference)
    key = _key(idempotency_key)
    existing = SchemeClosureRequest.objects.filter(idempotency_key=key).first()
    if existing:
        _matching(existing, facts)
        validate_closure_history(existing)
        return existing
    if account.status in ("REDEEMED", "CANCELLED"):
        raise ValidationError("This agreement is already closed.")
    if account.closure_requests.filter(status__in=["PENDING", "ACCEPTED"]).exists():
        raise ValidationError("An open closure request already exists; review it instead.")
    request = SchemeClosureRequest(**facts, idempotency_key=key, actor_label=_actor_label(actor))
    request.full_clean()
    request.save()
    event = SchemeClosureEvent(request=request, sequence=1, action="REQUESTED", resulting_status="PENDING",
        actor=actor, actor_label=request.actor_label, reason=reason, authorization_reference=reference,
        idempotency_key=key)
    event.full_clean()
    event.save()
    return request


@transaction.atomic
def review_scheme_closure(*, request_id, actor, action, reason, idempotency_key,
                         expected_sequence, authorization_reference=""):
    from .services import _actor_label
    target = SchemeClosureRequest.objects.get(pk=request_id)
    account = _account(target.scheme_account_id)
    request = SchemeClosureRequest.objects.select_for_update().get(pk=request_id)
    actor, owner = _actor(actor, account)
    if action not in ("NOTE", "ACCEPT", "WITHDRAW", "REJECT") or (not owner and action != "WITHDRAW"):
        raise ValidationError("Only the owner may review or accept a closure request.")
    reason = _text(reason, 2000, "a review reason")
    reference = _text(authorization_reference, 254, "the customer's withdrawal authorization reference",
        required=owner and action == "WITHDRAW")
    if reference and not (owner and action == "WITHDRAW"):
        raise ValidationError("Only an owner-assisted withdrawal uses this authorization field.")
    facts = dict(request_id=request.pk, actor_id=actor.pk, action=action, reason=reason, authorization_reference=reference)
    key = _key(idempotency_key)
    sequence = validate_closure_history(request)
    existing = SchemeClosureEvent.objects.filter(idempotency_key=key).first()
    if existing:
        _matching(existing, facts)
        return request
    if type(expected_sequence) is not int or expected_sequence != sequence:
        raise ValidationError("Closure evidence changed. Reload before deciding.")
    if request.status not in ("PENDING", "ACCEPTED") or (request.status == "ACCEPTED" and action != "NOTE"):
        raise ValidationError("Only pending requests can be accepted, rejected or withdrawn. An accepted closure cannot silently reopen payments.")
    if account.status in ("REDEEMED", "CANCELLED"):
        raise ValidationError("The agreement is already closed; investigate its history.")
    state = request.status if action == "NOTE" else {"ACCEPT": "ACCEPTED", "REJECT": "REJECTED", "WITHDRAW": "WITHDRAWN"}[action]
    event = SchemeClosureEvent(**facts, idempotency_key=key, sequence=sequence + 1,
        resulting_status=state, actor_label=_actor_label(actor))
    event.full_clean()
    event.save()
    # Checked projection only; immutable request facts and all financial rows survive.
    SchemeClosureRequest.objects.filter(pk=request.pk).update(status=state)
    request.status = state
    return request


@transaction.atomic
def cancel_unused_agreement(*, request_id, actor, reason, idempotency_key, expected_sequence):
    """Complete an accepted, genuinely unused configured agreement. No settlement.

    CANCEL is an append-only, typed proof of the V1 no-history predicate. It is
    written atomically with both lifecycle projections under the payment lock.
    A different saving cycle needs a new agreement; this operation has no undo.
    """
    from django.utils import timezone
    from .services import _actor_label

    target = SchemeClosureRequest.objects.get(pk=request_id)
    account = _account(target.scheme_account_id)
    request = SchemeClosureRequest.objects.select_for_update().get(pk=request_id)
    actor, owner = _actor(actor, account)
    if not owner:
        raise ValidationError("Only an active owner may cancel an unused agreement.")
    reason = _text(reason, 2000, "a cancellation reason")
    facts = dict(request_id=request.pk, actor_id=actor.pk, action="CANCEL", reason=reason,
                 authorization_reference="")
    key = _key(idempotency_key)
    sequence = validate_closure_history(request)
    existing = SchemeClosureEvent.objects.filter(idempotency_key=key).first()
    if existing:
        _matching(existing, facts)
        return request
    if type(expected_sequence) is not int or expected_sequence != sequence:
        raise ValidationError("Closure evidence changed. Reload before deciding.")
    if request.status != "ACCEPTED" or account.status not in ("ACTIVE", "REDEMPTION_ELIGIBLE"):
        raise ValidationError("Cancellation requires an accepted closure on an open agreement.")
    account.full_clean()
    require_unused_agreement(account)
    event = SchemeClosureEvent(**facts, sequence=sequence + 1, resulting_status="CANCELLED",
        idempotency_key=key, actor_label=_actor_label(actor))
    event.full_clean()
    event.save()
    SchemeAccount.objects.filter(pk=account.pk).update(status="CANCELLED", updated_at=timezone.now())
    SchemeClosureRequest.objects.filter(pk=request.pk).update(status="CANCELLED")
    request.status = "CANCELLED"
    return request
