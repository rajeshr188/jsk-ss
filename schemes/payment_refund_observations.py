"""Owner-initiated provider observations. No refund, credit or hold-clear mutation."""
import hashlib
import json

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import (Contribution, InrPaymentCaptureEvidence, InrPrincipalReceipt,
    PaymentRefundObservation, PaymentWebhookEvent, SchemeAccount)
from .payment_refund_evidence import PaymentRefundInspection, validate_snapshot
from .payments import PaymentGatewayError, get_payment_gateway


def _owner(actor):
    from .services import _validate_owner
    actor = get_user_model().objects.filter(pk=getattr(actor, "pk", None)).first()
    _validate_owner(actor)
    return actor


def _binding(event):
    if (event.gateway != "razorpay" or event.gateway_mode != "live"
        or event.event_type != "payment.captured" or not event.gateway_reference or not event.gateway_order_id):
        raise ValidationError("An exact Live captured-payment event is required for refund inspection.")
    try:
        contribution = Contribution.objects.get(payment_gateway="razorpay", gateway_mode="live",
            gateway_order_id=event.gateway_order_id)
    except (Contribution.DoesNotExist, Contribution.MultipleObjectsReturned):
        raise ValidationError("Recover the exact local order identity before refund inspection.") from None
    if event.contribution_id not in (None, contribution.pk):
        raise ValidationError("The capture event is linked to a different contribution.")
    return contribution


def _local_snapshot(event, contribution):
    """Retain only binding facts, never credentials, raw payload or personal details."""
    return dict(event_id=event.pk, event_type=event.event_type,
        payload_sha256=event.payload_sha256, event_status=event.status,
        event_contribution_id=event.contribution_id, contribution_id=contribution.pk,
        account_id=contribution.scheme_account_id, gateway_mode=event.gateway_mode,
        payment_id=event.gateway_reference, order_id=event.gateway_order_id,
        amount_subunits=int(contribution.amount * 100), contribution_status=contribution.status,
        confirmed_payment_id=contribution.gateway_reference or "",
        paid_at=contribution.paid_at.isoformat() if contribution.paid_at else None)


def _has_entitlement(payment_id):
    # Historical source records survive reversals/settlement. Never infer this from
    # an outstanding balance. Do not confuse a different first payment on the order.
    sources = Contribution.objects.filter(payment_gateway="razorpay", gateway_mode="live", gateway_reference=payment_id)
    return (sources.filter(Q(paid_at__isnull=False) | Q(status__in=["PAID", "PAID_UNALLOCATED", "REVERSED"])
                | Q(metal_allocation__isnull=False) | Q(inr_principal_receipt__isnull=False)).exists()
        or InrPaymentCaptureEvidence.objects.filter(gateway_mode="live", payment_id=payment_id).exists()
        or InrPrincipalReceipt.objects.filter(source_reference=payment_id).exists()
        or PaymentWebhookEvent.objects.filter(gateway="razorpay", gateway_mode="live", gateway_reference=payment_id,
            event_type="payment.captured", status="PROCESSED").exists())


def observation_digest(provider, local, no_entitlement):
    return hashlib.sha256(json.dumps(dict(provider=provider, local=local, no_entitlement=no_entitlement),
        sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()


def validate_observation(observation):
    try:
        inspection = validate_snapshot(observation.provider_snapshot)
    except PaymentGatewayError:
        raise ValidationError("Invalid retained refund provider evidence.") from None
    local = observation.local_snapshot
    required_keys = {"event_id", "event_type", "payload_sha256", "event_status", "event_contribution_id",
        "contribution_id", "account_id", "gateway_mode", "payment_id", "order_id", "amount_subunits",
        "contribution_status", "confirmed_payment_id", "paid_at"}
    if (not isinstance(local, dict) or set(local) != required_keys
        or local["event_id"] != observation.webhook_event_id or local["contribution_id"] != observation.contribution_id
        or local["gateway_mode"] != "live" or local["event_type"] != "payment.captured"
        or local["payment_id"] != observation.payment_id or local["order_id"] != observation.order_id
        or type(local["amount_subunits"]) is not int or local["amount_subunits"] != observation.amount_subunits
        or inspection.payment_id != observation.payment_id or inspection.order_id != observation.order_id
        or inspection.amount_subunits != observation.amount_subunits or inspection.currency != observation.currency
        or type(observation.no_entitlement) is not bool or type(observation.fully_refunded) is not bool
        or observation.fully_refunded != inspection.fully_refunded
        or observation.evidence_sha256 != observation_digest(observation.provider_snapshot, local, observation.no_entitlement)
        or not observation.reason.strip() or not observation.actor_label.strip()):
        raise ValidationError("Refund observation does not match its retained binding.")


def inspect_payment_error_refund(*, webhook_event_id, performed_by, reason, gateway=None):
    """Record a fresh inspection, even if partial/credited. Never clear any hold."""
    actor = _owner(performed_by)
    if not isinstance(reason, str) or not reason.strip():
        raise ValidationError("Enter a refund investigation reason.")
    gateway = gateway or get_payment_gateway()
    if gateway.name != "razorpay" or getattr(gateway, "mode", None) != "live":
        raise ValidationError("Use the Live Razorpay gateway for payment-error refund inspection.")
    event = PaymentWebhookEvent.objects.get(pk=webhook_event_id)
    contribution = _binding(event)
    original = _local_snapshot(event, contribution)
    # Intentionally outside transaction/locks: provider timeouts cannot hold an agreement.
    if transaction.get_connection().in_atomic_block:
        raise ValidationError("Refund provider inspection must run outside a database transaction.")
    inspection = gateway.inspect_payment_refunds(payment_id=event.gateway_reference)
    if not isinstance(inspection, PaymentRefundInspection):
        raise ValidationError("The gateway did not return typed refund evidence.")
    inspection = validate_snapshot(inspection.snapshot())
    if (inspection.payment_id != event.gateway_reference or inspection.order_id != event.gateway_order_id
        or inspection.amount_subunits != int(contribution.amount * 100)):
        raise ValidationError("The provider refund does not match the exact local payment.")
    observed_at = timezone.now()
    with transaction.atomic():
        SchemeAccount.objects.select_for_update().get(pk=contribution.scheme_account_id)
        event = PaymentWebhookEvent.objects.select_for_update().get(pk=event.pk)
        contribution = Contribution.objects.select_for_update().get(pk=contribution.pk)
        actor = _owner(actor)
        if _binding(event).pk != contribution.pk or _local_snapshot(event, contribution) != original:
            raise ValidationError("Local payment evidence changed during inspection; inspect again.")
        no_entitlement = not _has_entitlement(event.gateway_reference)
        provider = inspection.snapshot()
        return PaymentRefundObservation.objects.create(contribution=contribution, webhook_event=event,
            gateway_mode="live", payment_id=inspection.payment_id, order_id=inspection.order_id,
            amount_subunits=inspection.amount_subunits, currency=inspection.currency,
            provider_snapshot=provider, local_snapshot=original,
            evidence_sha256=observation_digest(provider, original, no_entitlement),
            fully_refunded=inspection.fully_refunded, no_entitlement=no_entitlement,
            actor=actor, actor_label=actor.email or actor.username or str(actor.pk),
            reason=reason.strip(), observed_at=observed_at)
