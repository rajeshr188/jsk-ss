"""Fresh owner review evidence; never cached authority to credit a payment."""
from datetime import timedelta
from decimal import Decimal

from django.core import signing
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import Contribution

REVIEW_SALT = "schemes.captured-payment-review.v1"
REVIEW_SECONDS = 600


def webhook_review_context(event, actor):
    latest = event.processing_attempts.order_by("-created_at", "-pk").first()
    contribution = Contribution.objects.select_related("scheme_account").filter(
        payment_gateway="razorpay", gateway_mode=event.gateway_mode,
        gateway_order_id=event.gateway_order_id).first() if event.gateway_order_id else None
    snapshot = latest.provider_snapshot if latest and isinstance(latest.provider_snapshot, dict) else {}
    amount = snapshot.get("amount_subunits")
    comparison = {key: snapshot.get(key) for key in ("payment_id", "order_id", "currency", "status", "captured")}
    comparison["amount"] = Decimal(amount) / Decimal("100") if type(amount) is int and amount >= 0 else None
    now = timezone.now()
    can_apply = bool(latest and contribution and latest.source == "OWNER_RECOVERY"
        and contribution.status in {"PENDING", "PAID", "PAID_UNALLOCATED"}
        and contribution.scheme_account.status in {"ACTIVE", "REDEMPTION_ELIGIBLE", "CLOSURE_PENDING"}
        and (contribution.status == "PENDING" or contribution.gateway_reference == event.gateway_reference)
        and latest.actor_id == actor.pk and latest.outcome in {"ELIGIBLE_FOR_RECOVERY", "ALREADY_PROCESSED"}
        and latest.created_at <= now <= latest.created_at + timedelta(seconds=REVIEW_SECONDS)
        and event.contribution_id in (None, contribution.pk)
        and snapshot.get("payment_id") == event.gateway_reference
        and snapshot.get("order_id") == event.gateway_order_id
        and type(amount) is int and amount == int(contribution.amount * 100)
        and snapshot.get("currency") == "INR" and snapshot.get("status") == "captured"
        and snapshot.get("captured") is True)
    identity = dict(owner=actor.pk, event=event.pk, attempt=latest.pk if latest else None,
        event_status=event.status, event_mode=event.gateway_mode, event_hash=event.payload_sha256,
        event_order=event.gateway_order_id, event_payment=event.gateway_reference,
        event_contribution=event.contribution_id, failure_code=event.failure_code, provider=snapshot)
    if contribution:
        identity["local"] = dict(contribution=contribution.pk, amount=str(contribution.amount),
            status=contribution.status, payment=contribution.gateway_reference,
            rate=contribution.scheme_rate_id, account=contribution.scheme_account_id,
            account_status=contribution.scheme_account.status,
            deadline=contribution.checkout_expires_at.isoformat() if contribution.checkout_expires_at else None)
    return dict(latest=latest, compared_contribution=contribution, comparison=comparison,
        can_apply_recovery=can_apply, review_identity=identity,
        review_token=signing.dumps(identity, salt=REVIEW_SALT) if can_apply else "")


def require_webhook_review(event, actor, token):
    context = webhook_review_context(event, actor)
    try:
        reviewed = signing.loads(token, salt=REVIEW_SALT, max_age=REVIEW_SECONDS)
    except signing.BadSignature:
        raise ValidationError("Check provider again; this review is missing, invalid or expired.") from None
    if not context["can_apply_recovery"] or reviewed != context["review_identity"]:
        raise ValidationError("The owner, payment or latest inspection changed. Check provider again.")
