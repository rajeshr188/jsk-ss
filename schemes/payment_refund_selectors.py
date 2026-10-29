"""One interpretation of retained exact-payment resolutions, never a blanket clear."""
from django.core.exceptions import ValidationError
from django.db.models import Exists, OuterRef, Q
from django.db.models.fields.json import KeyTextTransform

from .models import PaymentErrorRefundResolution, RefundedPaymentOrderClosure
from .payment_refund_observations import _has_entitlement
from .payment_refund_resolutions import validate_resolution


def valid_resolution_ids(resolutions):
    ids = []
    for resolution in resolutions.select_related("reviewed_observation", "applied_observation", "contribution"):
        try:
            validate_resolution(resolution)
            c = resolution.contribution
            original = resolution.applied_observation.local_snapshot
            if (c.payment_gateway != "razorpay" or c.gateway_mode != "live"
                or c.gateway_order_id != resolution.order_id or c.scheme_account_id != original["account_id"]
                or c.amount * 100 != original["amount_subunits"] or _has_entitlement(resolution.payment_id)):
                continue
        except (ValidationError, KeyError, TypeError, ValueError):
            continue
        ids.append(resolution.pk)
    return ids


def exclude_resolved_capture_events(events):
    """Preserve caller scope/status policy; omit only validated exact signed evidence.

    A new payment, changed payload, mode/order/link, or malformed retained proof stays
    held. Original rows/statuses and processing attempts are never rewritten here.
    """
    # Callers also use correlated event subqueries; never evaluate their OuterRef
    # outside its parent query. Only the immutable resolution set is materialized.
    candidates = PaymentErrorRefundResolution.objects.all()
    ids = valid_resolution_ids(candidates)
    if not ids:
        return events
    matches = PaymentErrorRefundResolution.objects.filter(pk__in=ids,
        gateway_mode=OuterRef("gateway_mode"), payment_id=OuterRef("gateway_reference"),
        order_id=OuterRef("gateway_order_id")).annotate(
            retained_hash=KeyTextTransform("payload_sha256", "applied_observation__local_snapshot"))
    # Two Exists expressions handle both orphaned but exactly order-bound events
    # and events already linked to the expected local contribution.
    matches = matches.filter(retained_hash=OuterRef("payload_sha256"))
    return events.alias(_refund_exact=Exists(matches),
        _refund_linked=Exists(matches.filter(contribution_id=OuterRef("contribution_id")))).exclude(
            Q(gateway="razorpay", gateway_mode="live", event_type="payment.captured", _refund_exact=True)
            & (Q(contribution__isnull=True) | Q(_refund_linked=True)))


def unresolved_payment_events(events):
    return exclude_resolved_capture_events(events.exclude(status__in=["PROCESSED", "IGNORED"]))


def refund_resolution_evidence(account):
    rows = PaymentErrorRefundResolution.objects.filter(contribution__scheme_account=account).order_by("pk")
    ids = valid_resolution_ids(rows)
    if len(ids) != rows.count():
        raise ValidationError("Payment refund resolution evidence requires investigation.")
    return [dict(id=r.pk, contribution=r.contribution_id, payment=r.payment_id,
        order=r.order_id, observation=r.applied_observation_id,
        digest=r.applied_observation.evidence_sha256) for r in rows.select_related("applied_observation")]


def refund_disposition_evidence(account):
    """Additive proof only when present: older retained snapshot hashes stay valid."""
    resolutions, orders = refund_resolution_evidence(account), refunded_order_evidence(account)
    return {**({"payment_refund_resolutions": resolutions} if resolutions else {}),
            **({"refunded_orders": orders} if orders else {})}


def is_resolved_capture_event(event):
    from .models import PaymentWebhookEvent
    rows = PaymentWebhookEvent.objects.filter(pk=event.pk)
    return rows.exists() and not exclude_resolved_capture_events(rows).exists()


def validate_retained_refund_disposition(evidence, account):
    """Check only retained references; later evidence must not rewrite old proofs."""
    if not {"payment_refund_resolutions", "refunded_orders"}.intersection(evidence):
        return
    current = refund_disposition_evidence(account)
    for key in ("payment_refund_resolutions", "refunded_orders"):
        if key not in evidence:
            continue
        rows = evidence[key]
        if (not isinstance(rows, list) or not rows or any(not isinstance(r, dict) or type(r.get("id")) is not int for r in rows)
            or len({r["id"] for r in rows}) != len(rows)
            or any(r not in current.get(key, []) for r in rows)):
            raise ValidationError("Retained payment refund references require investigation.")


def refund_disposition_integrity_errors():
    from .models import RefundedPaymentOrderClosure
    from .refunded_orders import validate_refunded_order_closure
    rows = PaymentErrorRefundResolution.objects.all()
    errors = rows.count() - len(valid_resolution_ids(rows))
    for row in RefundedPaymentOrderClosure.objects.select_related("contribution"):
        try:
            validate_refunded_order_closure(row)
        except ValidationError:
            errors += 1
    return errors


def is_refunded_order_retired(contribution):
    from .refunded_orders import validate_refunded_order_closure
    record = RefundedPaymentOrderClosure.objects.filter(contribution=contribution).select_related("contribution").first()
    if record is None:
        return False
    validate_refunded_order_closure(record)
    return True


def refunded_order_evidence(account):
    from .refunded_orders import validate_refunded_order_closure
    rows = RefundedPaymentOrderClosure.objects.filter(contribution__scheme_account=account).select_related("contribution").order_by("pk")
    result = []
    for row in rows:
        validate_refunded_order_closure(row)
        result.append(dict(id=row.pk, contribution=row.contribution_id, digest=row.evidence_sha256))
    return result
