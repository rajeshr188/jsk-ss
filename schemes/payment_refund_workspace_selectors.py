"""Owner-facing evidence reads. GET must never inspect the provider or mutate records."""
from datetime import datetime, timedelta
from decimal import Decimal

from django.core import signing
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils import timezone

from .models import PaymentErrorRefundResolution, PaymentWebhookEvent, RefundedPaymentOrderClosure
from .payment_refund_observations import _binding, validate_observation
from .payment_refund_resolutions import payment_refund_review_token
from .payment_refund_selectors import is_resolved_capture_event, valid_resolution_ids
from .refunded_order_evidence import validate_order_snapshot
from .refunded_orders import SALT, REVIEW_SECONDS, validate_refunded_order_closure
from .payments import PaymentGatewayError


def refund_review_history():
    return PaymentWebhookEvent.objects.filter(gateway="razorpay", gateway_mode="live",
        event_type="payment.captured", refund_observations__isnull=False).select_related(
            "contribution__scheme_account").distinct().order_by("-received_at", "-pk")


def payment_refund_workspace(event, actor):
    result = dict(compared_contribution=None, binding_error="", observation=None, comparison=None,
        review_token="", resolution=None, resolution_valid=False, exact_event_resolved=False,
        review_error="", can_resolve=False)
    try:
        result["compared_contribution"] = _binding(event)
    except ValidationError as error:
        result["binding_error"] = " ".join(error.messages)
    observation = event.refund_observations.order_by("-pk").first()
    result["observation"] = observation
    if observation:
        try:
            validate_observation(observation)
            p = observation.provider_snapshot
            result["comparison"] = p | dict(amount=Decimal(p["amount_subunits"]) / 100,
                refunded=Decimal(p["amount_refunded_subunits"]) / 100,
                refunds=[r | dict(amount=Decimal(r["amount_subunits"]) / 100) for r in p["refunds"]])
            if not observation.no_entitlement:
                raise ValidationError("This payment has historical local entitlement. Use separate reconciliation; this screen cannot reverse or refund credited principal.")
            result["review_token"] = payment_refund_review_token(observation_id=observation.pk, performed_by=actor)
        except ValidationError as error:
            result["review_error"] = " ".join(error.messages)
    resolution = PaymentErrorRefundResolution.objects.filter(gateway_mode="live", payment_id=event.gateway_reference).first()
    if resolution:
        result["resolution"] = resolution
        result["resolution_valid"] = bool(valid_resolution_ids(PaymentErrorRefundResolution.objects.filter(pk=resolution.pk)))
        result["exact_event_resolved"] = is_resolved_capture_event(event)
        result["review_token"] = ""
    result["can_resolve"] = bool(result["review_token"] and not result["binding_error"] and not resolution)
    return result


def refunded_order_workspace(contribution):
    record = RefundedPaymentOrderClosure.objects.filter(contribution=contribution).select_related("contribution").first()
    error = ""
    if record:
        try:
            validate_refunded_order_closure(record)
        except ValidationError as exc:
            error = " ".join(exc.messages)
    events = PaymentWebhookEvent.objects.filter(gateway="razorpay", gateway_mode="live", event_type="payment.captured").filter(
        Q(contribution=contribution) | Q(gateway_order_id=contribution.gateway_order_id)).order_by("-received_at", "-pk")
    return dict(retirement=record, retirement_error=error, capture_events=events[:20], capture_count=events.count(),
        can_inspect_order=not record and contribution.status in {"PENDING", "FAILED", "ABANDONED"}
            and bool(contribution.gateway_order_id))


def order_review_comparison(token, actor, contribution):
    """Only display server-signed, actor/route-bound evidence; Apply independently checks again."""
    try:
        review = signing.loads(token, salt=SALT, max_age=REVIEW_SECONDS)
        if (not isinstance(review, dict) or set(review) != {"actor", "contribution", "evidence", "reviewed_at"}
            or review["actor"] != actor.pk or review["contribution"] != contribution.pk):
            raise ValueError
        at = datetime.fromisoformat(review["reviewed_at"])
        if timezone.is_naive(at) or not timedelta(0) <= timezone.now() - at <= timedelta(seconds=REVIEW_SECONDS):
            raise ValueError
        provider = validate_order_snapshot(review["evidence"]["provider"])
        return dict(reviewed_at=at, order=provider["order"] | dict(amount=Decimal(provider["order"]["amount"]) / 100),
            payments=[p | dict(amount=Decimal(p["amount_subunits"]) / 100,
                refunded=Decimal(p["amount_refunded_subunits"]) / 100) for p in provider["payments"]])
    except (signing.BadSignature, KeyError, TypeError, ValueError, PaymentGatewayError):
        raise ValidationError("This order comparison is invalid, belongs to another owner/order or has expired. Inspect again.") from None
