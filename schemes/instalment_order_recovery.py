"""Bind a conclusively identified lost order response; never create or release one."""
import uuid

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .instalment_payments import _append, _evidence_target, _provider_instant
from .instalment_selectors import durable_order_request
from .models import Contribution, InstalmentOrderRecovery
from .payments import get_payment_gateway


def recover_instalment_order(*, contribution_id, order_id, actor, reason, evidence_reference,
    idempotency_key, expected_payment_sequence, gateway=None):
    from .services import _actor_label, _validate_owner

    _validate_owner(actor)
    if any(not isinstance(v, str) or not v.strip() or len(v.strip()) > limit
        for v, limit in ((reason, 2000), (evidence_reference, 254), (order_id, 120))):
        raise ValidationError("A candidate order ID, investigation reason and evidence reference are required.")
    order_id, reason, evidence_reference = order_id.strip(), reason.strip(), evidence_reference.strip()
    try:
        key = uuid.UUID(str(idempotency_key))
    except (ValueError, TypeError, AttributeError):
        raise ValidationError("A valid recovery submission identifier is required.") from None
    facts = dict(gateway_order_id=order_id, actor_id=actor.pk, reason=reason, evidence_reference=evidence_reference)

    def replay():
        existing = InstalmentOrderRecovery.objects.select_related("request_decision__reservation").filter(idempotency_key=key).first()
        if existing and (existing.request_decision.reservation.contribution_id != contribution_id
            or any(getattr(existing, name) != value for name, value in facts.items())):
            raise ValidationError("This submission identifier already records a different order recovery.")
        return existing

    existing = replay()
    if existing:
        return existing
    gateway = gateway or get_payment_gateway()
    if gateway.name != "razorpay" or gateway.mode != "live":
        raise ValidationError("Use the configured Live Razorpay account to recover a real instalment order.")
    # No network under a database lock. Both snapshots are checked again afterwards.
    contribution = Contribution.objects.get(pk=contribution_id)
    intent = durable_order_request(contribution)
    if contribution.gateway_mode != gateway.mode:
        raise ValidationError("The contribution belongs to a different provider mode.")
    identity = gateway.inspect_order_identity(order_id=order_id)
    observed_at = timezone.now()
    provider_created_at = _provider_instant(identity.created_at)
    if (identity.order_id != order_id or identity.receipt != f"inst_{intent.request_token.hex}"
        or identity.request_token != str(intent.request_token) or identity.contribution_id != str(contribution.pk)
        or type(identity.amount_subunits) is not int or identity.amount_subunits != contribution.amount * 100
        or identity.currency != "INR" or identity.status not in {"created", "attempted", "paid"}
        or provider_created_at is None or not intent.created_at.replace(microsecond=0) <= provider_created_at <= observed_at):
        raise ValidationError("The authenticated provider order does not match the original durable request. No link or payment was changed.")
    with transaction.atomic():
        locked, claim = _evidence_target(contribution_id)
        existing = replay()
        if existing:
            return existing
        last = claim.decisions.order_by("-sequence").first()
        if (claim.state != "ORDERING" or locked.status not in ("PENDING", "FAILED")
            or locked.gateway_order_id or locked.gateway_reference
            or type(expected_payment_sequence) is not int or last.sequence != expected_payment_sequence
            or last.pk != intent.pk or last.request_token != intent.request_token
            or locked.amount != contribution.amount or locked.gateway_mode != gateway.mode):
            raise ValidationError("Payment evidence changed or is not an unresolved request. Reload before recovery.")
        if Contribution.objects.filter(payment_gateway="razorpay", gateway_mode="live", gateway_order_id=order_id).exists():
            raise ValidationError("This provider order is already attached to another contribution.")
        locked.gateway_order_id = order_id
        locked.status = Contribution.Status.PENDING
        locked.full_clean()
        locked.save(update_fields=["gateway_order_id", "status"])
        decision = _append(claim, "RESERVED", "PROVIDER_ORDER_RECOVERED", actor_label=_actor_label(actor))
        return InstalmentOrderRecovery.objects.create(**facts, request_decision=intent, decision=decision,
            receipt=identity.receipt, provider_status=identity.status, provider_created_at=provider_created_at,
            amount_subunits=identity.amount_subunits, currency=identity.currency, observed_at=observed_at,
            actor_label=_actor_label(actor), idempotency_key=key)
