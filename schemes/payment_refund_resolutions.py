"""Exact-payment resolution and replay rejection; no generic hold-clear override."""
from datetime import timedelta

from django.core import signing
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import Contribution, PaymentErrorRefundResolution, PaymentRefundObservation, PaymentWebhookEvent, SchemeAccount
from .payment_refund_observations import (_binding, _has_entitlement, _local_snapshot, _owner,
    inspect_payment_error_refund, validate_observation)


REVIEW_SECONDS = 600
REVIEW_SALT = "schemes.payment-error-refund.v1"


def validate_resolution(resolution):
    review, applied = resolution.reviewed_observation, resolution.applied_observation
    for observation in (review, applied):
        validate_observation(observation)
        if (not observation.fully_refunded or not observation.no_entitlement
            or observation.gateway_mode != resolution.gateway_mode
            or observation.payment_id != resolution.payment_id or observation.order_id != resolution.order_id
            or observation.contribution_id != resolution.contribution_id or observation.webhook_event_id != resolution.webhook_event_id
            or observation.actor_id != resolution.actor_id):
            raise ValidationError("Resolution must bind exact uncredited full-refund evidence and its owner.")
    if (review.pk == applied.pk or review.provider_snapshot != applied.provider_snapshot
        or review.local_snapshot != applied.local_snapshot
        or not review.observed_at <= applied.observed_at <= resolution.resolved_at
        or resolution.resolved_at - review.observed_at > timedelta(seconds=REVIEW_SECONDS)
        or not resolution.reason.strip() or not resolution.actor_label.strip()):
        raise ValidationError("Resolution requires fresh unchanged provider/local evidence and an audit reason.")


def require_payment_not_refund_resolved(*, gateway_mode, payment_id):
    # Presence is deliberately fail-closed even if evidence later needs investigation.
    if PaymentErrorRefundResolution.objects.filter(gateway_mode=gateway_mode, payment_id=payment_id).exists():
        raise ValidationError("This exact payment was refunded without entitlement; retain any later capture for investigation. Do not credit it.")


def _review(observation, actor):
    validate_observation(observation)
    now = timezone.now()
    if (observation.actor_id != actor.pk or not observation.fully_refunded or not observation.no_entitlement
        or not timedelta(0) <= now - observation.observed_at <= timedelta(seconds=REVIEW_SECONDS)
        or PaymentRefundObservation.objects.filter(webhook_event_id=observation.webhook_event_id,
            pk__gt=observation.pk).exists()):
        raise ValidationError("Inspect and review the latest full refund before resolution.")
    event = PaymentWebhookEvent.objects.get(pk=observation.webhook_event_id)
    contribution = _binding(event)
    if (_local_snapshot(event, contribution) != observation.local_snapshot
        or _has_entitlement(observation.payment_id)):
        raise ValidationError("Payment history changed or contains entitlement; this refund requires separate reconciliation.")
    return contribution


def payment_refund_review_token(*, observation_id, performed_by):
    actor = _owner(performed_by)
    observation = PaymentRefundObservation.objects.get(pk=observation_id)
    _review(observation, actor)
    return signing.dumps(dict(observation=observation.pk, actor=actor.pk,
        evidence=observation.evidence_sha256), salt=REVIEW_SALT)


def resolve_payment_error_refund(*, review_token, confirmed, performed_by, reason, gateway=None):
    actor = _owner(performed_by)
    if confirmed is not True or not isinstance(reason, str) or not reason.strip():
        raise ValidationError("Explicitly confirm the reviewed refund and supply an audit reason.")
    try:
        reviewed = signing.loads(review_token, salt=REVIEW_SALT, max_age=REVIEW_SECONDS)
    except (signing.BadSignature, TypeError, ValueError):
        raise ValidationError("The refund review is invalid or expired; inspect again.") from None
    if not isinstance(reviewed, dict) or set(reviewed) != {"observation", "actor", "evidence"} or reviewed["actor"] != actor.pk:
        raise ValidationError("The refund review belongs to another owner or inspection.")
    try:
        review = PaymentRefundObservation.objects.get(pk=reviewed["observation"], actor=actor)
    except (PaymentRefundObservation.DoesNotExist, ValueError, TypeError):
        raise ValidationError("The retained refund review is unavailable.") from None
    if review.evidence_sha256 != reviewed["evidence"]:
        raise ValidationError("The retained refund review has changed.")
    existing = PaymentErrorRefundResolution.objects.filter(gateway_mode="live", payment_id=review.payment_id).first()
    if existing:
        validate_resolution(existing)
        if existing.reviewed_observation_id != review.pk or existing.actor_id != actor.pk:
            raise ValidationError("This payment has a different retained resolution; inspect its history.")
        return existing
    contribution = _review(review, actor)
    # Fresh I/O happens without locks; an unsafe fresh observation remains visible.
    fresh = inspect_payment_error_refund(webhook_event_id=review.webhook_event_id, performed_by=actor,
        reason=reason, gateway=gateway)
    with transaction.atomic():
        SchemeAccount.objects.select_for_update().get(pk=contribution.scheme_account_id)
        event = PaymentWebhookEvent.objects.select_for_update().get(pk=review.webhook_event_id)
        contribution = Contribution.objects.select_for_update().get(pk=contribution.pk)
        actor = _owner(actor)
        existing = PaymentErrorRefundResolution.objects.filter(gateway_mode="live", payment_id=review.payment_id).first()
        if existing:
            validate_resolution(existing)
            if existing.reviewed_observation_id != review.pk or existing.actor_id != actor.pk:
                raise ValidationError("A different resolution was recorded; inspect retained history.")
            return existing
        _review(fresh, actor)
        if (_binding(event).pk != contribution.pk or _local_snapshot(event, contribution) != review.local_snapshot
            or _has_entitlement(review.payment_id)):
            raise ValidationError("The local payment changed during resolution; no refund clearance was recorded.")
        return PaymentErrorRefundResolution.objects.create(reviewed_observation=review, applied_observation=fresh,
            contribution=contribution, webhook_event=event, gateway_mode="live", payment_id=review.payment_id,
            order_id=review.order_id, actor=actor, actor_label=actor.email or actor.username or str(actor.pk),
            reason=reason.strip(), resolved_at=timezone.now())
