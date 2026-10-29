"""Explicit all-attempt retirement. No refund execution, principal or qualification."""
from datetime import datetime, timedelta
import hashlib
import json

from django.core import signing
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import (Contribution, InstalmentReservation, PaymentErrorRefundResolution,
    PaymentWebhookEvent, RefundedPaymentOrderClosure, SchemeAccount)
from .payment_refund_observations import _owner, _has_entitlement
from .payment_refund_selectors import valid_resolution_ids, unresolved_payment_events
from .payments import PaymentGatewayError, get_payment_gateway
from .refunded_order_evidence import inspect_refunded_order, validate_order_snapshot


SALT = "schemes.refunded-order-review.v1"
REVIEW_SECONDS = 600


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _source(c):
    if (c.payment_channel != "RAZORPAY" or c.payment_gateway != "razorpay" or c.gateway_mode != "live"
        or c.status not in {"PENDING", "FAILED", "ABANDONED"} or not c.gateway_order_id
        or c.gateway_reference or c.paid_at or hasattr(c, "metal_allocation")
        or hasattr(c, "inr_principal_receipt")):
        raise ValidationError("Only a never-credited Live order can be retired through refund reconciliation.")
    claim = getattr(c, "instalment_reservation", None)
    if claim and claim.state not in {"RESERVED", "RELEASED", "RELEASED_REVIEW"}:
        raise ValidationError("The instalment has payment or timing evidence requiring separate review.")
    return dict(contribution=c.pk, account=c.scheme_account_id, amount=int(c.amount * 100),
        order=c.gateway_order_id, status=c.status, rate=c.scheme_rate_id,
        rate_locked_at=c.rate_locked_at.isoformat() if c.rate_locked_at else None,
        expiry=c.checkout_expires_at.isoformat() if c.checkout_expires_at else None,
        reservation=claim.pk if claim else None, period=claim.period_id if claim else None,
        reservation_state=claim.state if claim else None)


def _resolutions(c, provider):
    if provider["order"]["id"] != c.gateway_order_id or provider["order"]["amount"] != int(c.amount * 100):
        raise ValidationError("The refunded provider order differs from the local contribution.")
    if any(_has_entitlement(p["payment_id"]) for p in provider["payments"]):
        raise ValidationError("An order attempt has historical entitlement; use separate financial reconciliation.")
    payment_ids = [p["payment_id"] for p in provider["payments"] if p["status"] == "refunded"]
    rows = PaymentErrorRefundResolution.objects.filter(contribution=c, gateway_mode="live",
        order_id=c.gateway_order_id, payment_id__in=payment_ids).order_by("pk")
    ids = valid_resolution_ids(rows)
    if len(ids) != len(payment_ids):
        raise ValidationError("Every refunded payment requires its exact validated no-entitlement resolution.")
    return [dict(id=r.pk, payment=r.payment_id, digest=r.applied_observation.evidence_sha256)
        for r in rows.select_related("applied_observation")]


def _events(c):
    return PaymentWebhookEvent.objects.filter(Q(contribution=c) | Q(gateway_order_id=c.gateway_order_id))


def _require_no_event_hold(c):
    if unresolved_payment_events(_events(c)).exists():
        raise ValidationError("Another or contradictory provider event still needs investigation.")


def validate_refunded_order_closure(record, *, creating=False):
    e, c = record.evidence, record.contribution
    try:
        if (not isinstance(e, dict) or set(e) != {"version", "source", "provider", "resolutions"}
                or type(e["version"]) is not int or e["version"] != 1):
            raise ValueError
        validate_order_snapshot(e["provider"])
        source = _source(c)
        original = e["source"]
        if not isinstance(original, dict) or set(source) != set(original):
            raise ValueError
        if not creating:
            if c.status != "ABANDONED" or original["status"] not in {"PENDING", "FAILED", "ABANDONED"}:
                raise ValueError
            source["status"] = original["status"]
            if source["reservation"]:
                if source["reservation_state"] not in {"RELEASED", "RELEASED_REVIEW"}:
                    raise ValueError
                if original["reservation_state"] not in {"RESERVED", "RELEASED", "RELEASED_REVIEW"}:
                    raise ValueError
                source["reservation_state"] = original["reservation_state"]
                decision = getattr(record, "release_decision", None)
                previous = (decision.reservation.decisions.filter(sequence=decision.sequence - 1).first()
                    if decision else None)
                if (decision is None or decision.reservation_id != source["reservation"]
                    or decision.state != "RELEASED" or decision.reason_code != "FULL_REFUND_ORDER_RECONCILED"
                    or decision.actor_label != record.actor_label or decision.created_at < record.closed_at
                    or previous is None or previous.state != original["reservation_state"]):
                    raise ValueError
        if (source != original or _resolutions(c, e["provider"]) != e["resolutions"]
            or record.evidence_sha256 != _digest(e) or not record.reason.strip() or not record.actor_label.strip()
            or not timedelta(0) <= record.closed_at - record.reviewed_at <= timedelta(seconds=REVIEW_SECONDS)):
            raise ValueError
    except (KeyError, TypeError, ValueError, PaymentGatewayError):
        raise ValidationError("Retained refunded-order evidence requires investigation.") from None


def _inspect(c, gateway):
    if transaction.get_connection().in_atomic_block:
        raise ValidationError("Provider order inspection must run outside a database transaction.")
    source = _source(c)
    _require_no_event_hold(c)
    provider = inspect_refunded_order(gateway=gateway, order_id=c.gateway_order_id)
    c.refresh_from_db()
    if source != _source(c):
        raise ValidationError("Order facts changed during inspection; review again.")
    _require_no_event_hold(c)
    return dict(version=1, source=source, provider=provider, resolutions=_resolutions(c, provider))


def refunded_order_review_token(*, contribution_id, performed_by, gateway=None):
    actor = _owner(performed_by)
    c = Contribution.objects.get(pk=contribution_id)
    evidence = _inspect(c, gateway or get_payment_gateway())
    _owner(actor)
    return signing.dumps(dict(contribution=c.pk, actor=actor.pk, evidence=evidence,
        reviewed_at=timezone.now().isoformat()), salt=SALT, compress=True)


def retire_refunded_order(*, review_token, confirmed, performed_by, reason, gateway=None, expected_contribution_id=None):
    actor = _owner(performed_by)
    if confirmed is not True or not isinstance(reason, str) or not reason.strip():
        raise ValidationError("Confirm the all-attempt order review and enter an audit reason.")
    try:
        review = signing.loads(review_token, salt=SALT, max_age=REVIEW_SECONDS)
        if not isinstance(review, dict) or set(review) != {"contribution", "actor", "evidence", "reviewed_at"} or review["actor"] != actor.pk:
            raise ValueError
        reviewed_at = datetime.fromisoformat(review["reviewed_at"])
        if timezone.is_naive(reviewed_at):
            raise ValueError
    except (signing.BadSignature, TypeError, ValueError):
        raise ValidationError("The order review is invalid or expired; inspect again.") from None
    if expected_contribution_id is not None and review["contribution"] != expected_contribution_id:
        raise ValidationError("The order review belongs to a different contribution. Inspect this order separately.")
    c = Contribution.objects.get(pk=review["contribution"])
    existing = RefundedPaymentOrderClosure.objects.filter(contribution=c).first()
    if existing:
        validate_refunded_order_closure(existing)
        if existing.actor_id != actor.pk or existing.evidence != review["evidence"]:
            raise ValidationError("A different order review was applied; inspect retained history.")
        return existing
    evidence = _inspect(c, gateway or get_payment_gateway())
    if evidence != review["evidence"]:
        raise ValidationError("Provider or local facts changed; inspect and review again.")
    with transaction.atomic():
        SchemeAccount.objects.select_for_update().get(pk=c.scheme_account_id)
        c = Contribution.objects.select_for_update().get(pk=c.pk)
        actor = _owner(actor)
        existing = RefundedPaymentOrderClosure.objects.filter(contribution=c).first()
        if existing:
            validate_refunded_order_closure(existing)
            if existing.actor_id != actor.pk or existing.evidence != evidence:
                raise ValidationError("A different order review was applied.")
            return existing
        _require_no_event_hold(c)
        if _source(c) != evidence["source"] or _resolutions(c, evidence["provider"]) != evidence["resolutions"]:
            raise ValidationError("Local payment history changed; no order was retired.")
        record = RefundedPaymentOrderClosure.objects.create(contribution=c, evidence=evidence,
            evidence_sha256=_digest(evidence), actor=actor, actor_label=actor.email or actor.username or str(actor.pk),
            reason=reason.strip(), reviewed_at=reviewed_at, closed_at=timezone.now())
        Contribution.objects.filter(pk=c.pk).update(status="ABANDONED")
        claim = InstalmentReservation.objects.select_for_update().filter(contribution=c).first()
        if claim:
            from .instalment_payments import _append
            _append(claim, "RELEASED", "FULL_REFUND_ORDER_RECONCILED", actor_label=record.actor_label,
                refund_order_closure=record)
        c.refresh_from_db()
        return record
