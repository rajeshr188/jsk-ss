"""Authenticated API capture consumers. No network calls or provider timing inference."""
from django.core.exceptions import ValidationError
from django.db import transaction

from .inr_principal import _source, _source_key, _require_new_principal
from .inr_selectors import validate_principal_receipt, validate_api_capture
from .models import InrPaymentCaptureEvidence, InrPrincipalReceipt
from .payments import PaymentInspection


def validate_inspection(contribution, inspection):
    if (not isinstance(inspection, PaymentInspection) or type(inspection.amount_subunits) is not int
            or inspection.amount_subunits != contribution.amount * 100
            or inspection.order_id != contribution.gateway_order_id
            or inspection.currency != "INR" or inspection.status != "captured" or inspection.captured is not True
            or contribution.gateway_mode != "live" or contribution.payment_gateway != "razorpay"
            or contribution.payment_channel != "RAZORPAY"):
        raise ValidationError("Authenticated API capture must exactly match the live contribution.")


@transaction.atomic
def confirm_api_principal(*, contribution_id, inspection, observed_at, signature="", actor=None, event=None, reason=""):
    """Internal consumer after callback HMAC/API or owner-authenticated API inspection.

    Confirmation, immutable source evidence, principal and timing-pending projection
    commit together. API evidence is never a substitute for signed capture timing.
    """
    from .services import confirm_contribution, _actor_label, _validate_owner
    from .plan_policies import require_current_payment_workflow
    account, c = _source(contribution_id)
    require_current_payment_workflow(account)
    validate_inspection(c, inspection)
    if event is not None:
        _validate_owner(actor)
        if not reason.strip():
            raise ValidationError("Owner recovery requires an audit reason.")
    elif actor is not None or not signature:
        raise ValidationError("A verified callback signature is required.")
    c = confirm_contribution(contribution_id=c.pk, payment_gateway="razorpay",
        gateway_reference=inspection.payment_id, gateway_signature=signature, verified=True)
    existing = InrPrincipalReceipt.objects.filter(contribution=c).first()
    if existing:
        validate_principal_receipt(existing)
        return c
    _require_new_principal(account, c)
    evidence = InrPaymentCaptureEvidence.objects.filter(contribution=c).first()
    if evidence:
        validate_api_capture(evidence)
    else:
        evidence = InrPaymentCaptureEvidence.objects.create(contribution=c,
            payment_id=inspection.payment_id, order_id=inspection.order_id,
            amount_subunits=inspection.amount_subunits, currency=inspection.currency,
            status=inspection.status, captured=inspection.captured, observed_at=observed_at,
            source="OWNER_RECOVERY" if event else "CALLBACK", recovery_event=event, actor=actor,
            actor_label=_actor_label(actor) if actor else "system:razorpay-callback",
            reason=reason.strip() if event else "Callback signature and authenticated live API capture verified.")
    InrPrincipalReceipt.objects.create(scheme_account=account,
        configuration_id=account.configuration_snapshot_id, contribution=c,
        amount=c.amount, source_reference=c.gateway_reference, verified_at=c.paid_at,
        api_capture=evidence, recorded_by=evidence.actor, actor_label=evidence.actor_label,
        reason=evidence.reason, idempotency_key=_source_key("principal", c.pk))
    return c
