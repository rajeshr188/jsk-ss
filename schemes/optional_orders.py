"""Durable optional checkout and exact identity recovery; no payment verification.

The request commits before provider I/O. An uncertain response is never retried.
Recovery binds an authenticated identity for reconciliation, never renewed checkout.
"""
import uuid

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .independent_payment_selectors import optional_order_request, resumable_optional_contribution
from .models import Contribution, OptionalPaymentOrderRequest, OptionalPaymentOrderBinding, SchemeAccount
from .payments import PaymentGatewayError, RAZORPAY_ID_PATTERN, get_payment_gateway


def _locked(contribution_id):
    account_id = Contribution.objects.values_list("scheme_account_id", flat=True).get(pk=contribution_id)
    account = SchemeAccount.objects.select_for_update().get(pk=account_id)
    contribution = Contribution.objects.select_for_update().get(pk=contribution_id)
    if contribution.scheme_account_id != account.pk:
        raise ValidationError("The contribution agreement changed; inspect it again.")
    contribution.scheme_account = account
    return account, contribution


def _admit(account, contribution):
    from .services import ensure_payment_initiation_allowed, validate_contribution_allowed
    candidate = resumable_optional_contribution(account)
    if candidate is None or candidate.pk != contribution.pk:
        raise ValidationError("This optional checkout cannot be resumed.")
    validate_contribution_allowed(account, contribution.amount, exclude_contribution_id=contribution.pk)
    ensure_payment_initiation_allowed(metal_grade=account.metal_grade, savings_mode=account.savings_mode, lock=True)


@transaction.atomic(durable=True)
def begin_optional_order_request(*, contribution_id):
    account, contribution = _locked(contribution_id)
    _admit(account, contribution)
    if contribution.gateway_order_id:
        return optional_order_request(contribution), False
    intent = OptionalPaymentOrderRequest.objects.create(contribution=contribution,
        amount_subunits=int(contribution.amount * 100), checkout_expires_at=contribution.checkout_expires_at,
        scheme_rate_id=contribution.scheme_rate_id)
    return intent, True


@transaction.atomic
def _bind_response(*, contribution_id, order):
    _, contribution = _locked(contribution_id)
    intent = optional_order_request(contribution)
    if (contribution.status != "PENDING" or contribution.gateway_order_id or contribution.gateway_reference
            or hasattr(intent, "binding")):
        raise ValidationError("The original order request changed; retain provider evidence for review.")
    if (not isinstance(order.order_id, str) or not order.order_id.startswith("order_")
            or len(order.order_id) > 120 or not RAZORPAY_ID_PATTERN.fullmatch(order.order_id)
            or type(order.amount_subunits) is not int or order.amount_subunits != intent.amount_subunits
            or order.currency != "INR"):
        raise PaymentGatewayError("Razorpay returned an invalid order response; reconcile the original request.")
    if Contribution.objects.filter(payment_gateway="razorpay", gateway_mode="live", gateway_order_id=order.order_id).exists():
        raise ValidationError("This provider order is already linked; reconciliation is required.")
    contribution.gateway_order_id = order.order_id
    contribution.full_clean()
    contribution.save(update_fields=["gateway_order_id"])
    intent.contribution = contribution
    OptionalPaymentOrderBinding.objects.create(request=intent, gateway_order_id=order.order_id,
        observed_at=timezone.now(), actor_label="system:razorpay-order", reason="Authenticated create-order response.")
    return contribution


def create_optional_order(*, contribution, gateway):
    if gateway.name != "razorpay" or gateway.mode != "live":
        raise ValidationError("Independent optional checkout requires Live Razorpay.")
    intent, started = begin_optional_order_request(contribution_id=contribution.pk)
    if started:
        # No network under a database lock. Any exception leaves the durable intent
        # unresolved, including authentication errors, malformed responses and crashes.
        order = gateway.create_order(intent.contribution)
        _bind_response(contribution_id=contribution.pk, order=order)
    with transaction.atomic():
        account, contribution = _locked(contribution.pk)
        # A pause, expiry or containment during I/O must not return payable checkout.
        # The binding above is retained even when this revalidation refuses access.
        _admit(account, contribution)
        return contribution


def recover_optional_order(*, contribution_id, order_id, actor, reason, evidence_reference,
                           idempotency_key, gateway=None):
    from .services import _validate_owner, _actor_label
    from .instalment_payments import _provider_instant
    # Recheck persisted authority before provider I/O, and again before binding.
    actor = get_user_model().objects.filter(pk=getattr(actor, "pk", None)).first()
    _validate_owner(actor)
    if any(not isinstance(value, str) or not value.strip() or len(value.strip()) > limit
           for value, limit in ((order_id, 120), (reason, 2000), (evidence_reference, 254))):
        raise ValidationError("Candidate order, reason and investigation evidence are required.")
    order_id, reason, evidence_reference = order_id.strip(), reason.strip(), evidence_reference.strip()
    try:
        key = uuid.UUID(str(idempotency_key))
    except (ValueError, TypeError, AttributeError):
        raise ValidationError("A valid recovery submission identifier is required.") from None
    facts = dict(gateway_order_id=order_id, actor_id=actor.pk, reason=reason, evidence_reference=evidence_reference)

    def replay():
        existing = OptionalPaymentOrderBinding.objects.select_related("request__contribution").filter(idempotency_key=key).first()
        if existing:
            if (not existing.recovered or existing.request.contribution_id != contribution_id
                    or any(getattr(existing, field) != value for field, value in facts.items())):
                raise ValidationError("This submission already records a different recovery.")
            existing.full_clean()
        return existing

    existing = replay()
    if existing:
        return existing
    gateway = gateway or get_payment_gateway()
    if gateway.name != "razorpay" or gateway.mode != "live":
        raise ValidationError("Exact recovery requires the configured Live Razorpay account.")
    contribution = Contribution.objects.get(pk=contribution_id)
    intent = optional_order_request(contribution)
    identity = gateway.inspect_order_identity(order_id=order_id)
    observed_at = timezone.now()
    provider_created_at = _provider_instant(identity.created_at)
    if (identity.order_id != order_id or identity.receipt != f"opt_{intent.request_token.hex}"
            or identity.request_token != str(intent.request_token) or identity.contribution_id != str(contribution.pk)
            or type(identity.amount_subunits) is not int or identity.amount_subunits != intent.amount_subunits
            or identity.currency != "INR" or identity.status not in {"created", "attempted", "paid"}
            or provider_created_at is None or not intent.created_at.replace(microsecond=0) <= provider_created_at <= observed_at):
        raise ValidationError("Authenticated provider identity does not match the original optional request.")
    with transaction.atomic():
        _, locked = _locked(contribution_id)
        actor = get_user_model().objects.filter(pk=actor.pk).first()
        _validate_owner(actor)
        existing = replay()
        if existing:
            return existing
        current = optional_order_request(locked)
        if (current.pk != intent.pk or current.request_token != intent.request_token
                or hasattr(current, "binding") or locked.status not in ("PENDING", "FAILED")
                or locked.gateway_order_id or locked.gateway_reference):
            raise ValidationError("Order evidence changed; reload before recovery.")
        if Contribution.objects.filter(payment_gateway="razorpay", gateway_mode="live", gateway_order_id=order_id).exists():
            raise ValidationError("This provider order is already attached to another contribution.")
        locked.gateway_order_id, locked.status = order_id, "PENDING"
        locked.full_clean()
        locked.save(update_fields=["gateway_order_id", "status"])
        current.contribution = locked
        return OptionalPaymentOrderBinding.objects.create(request=current, **facts, recovered=True,
            provider_created_at=provider_created_at, provider_status=identity.status, observed_at=observed_at,
            actor_label=_actor_label(actor), idempotency_key=key)
