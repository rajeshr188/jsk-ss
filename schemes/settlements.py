"""Owner-authorized full exact-grade settlement; legacy paths remain separate."""
from decimal import Decimal

from django.core import signing
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .closures import _account, _actor, _key, _matching, _text
from .closure_selectors import validate_closure_history
from .models import (AuditEvent, ConfiguredSettlement, ConfiguredSettlementReversal,
    Redemption, RedemptionReversal, SchemeAccount, SchemeClosureEvent, SchemeClosureRequest)
from .settlement_selectors import full_settlement_evidence, proof_digest, validate_configured_settlement

SALT = "configured-full-settlement-v1"


@transaction.atomic
def preview_full_settlement(*, request_id, actor):
    target = SchemeClosureRequest.objects.get(pk=request_id)
    account = _account(target.scheme_account_id)
    actor, owner = _actor(actor, account)
    if not owner:
        raise ValidationError("Only an active owner may prepare a full settlement.")
    request = SchemeClosureRequest.objects.select_for_update().get(pk=request_id)
    evidence = full_settlement_evidence(account, request)
    token = signing.dumps(dict(request=str(request.pk), actor=actor.pk, digest=proof_digest(evidence)), salt=SALT)
    return evidence, token


@transaction.atomic
def settle_configured_agreement(*, request_id, actor, preview_token, invoice_reference,
    authorization_reference, reason, idempotency_key):
    from .services import _actor_label, _reference, record_audit_event
    target = SchemeClosureRequest.objects.get(pk=request_id)
    account = _account(target.scheme_account_id)
    actor, owner = _actor(actor, account)
    if not owner:
        raise ValidationError("Only an active owner may complete a full settlement.")
    request = SchemeClosureRequest.objects.select_for_update().get(pk=request_id)
    invoice = _text(invoice_reference, 120, "the jewellery invoice reference")
    authorization = _text(authorization_reference, 254, "customer confirmation of this exact settlement")
    reason = _text(reason, 2000, "the settlement reason")
    key = _key(idempotency_key)
    try:
        # Authenticity is checked even for a replay; expiry only applies to new mutation.
        preview = signing.loads(preview_token, salt=SALT)
    except (signing.BadSignature, TypeError, ValueError):
        raise ValidationError("Reload the full settlement preview.") from None
    if not isinstance(preview, dict) or preview.get("request") != str(request.pk) or preview.get("actor") != actor.pk:
        raise ValidationError("This preview belongs to another owner or agreement.")
    existing = ConfiguredSettlement.objects.filter(redemption__idempotency_key=key).first()
    if existing:
        validate_closure_history(request)
        validate_configured_settlement(existing)
        _matching(existing, dict(closure_id=request.pk, authorization_reference=authorization, evidence_digest=preview.get("digest")))
        _matching(existing.redemption, dict(processed_by_id=actor.pk, external_reference=invoice, notes=reason))
        return existing.redemption
    try:
        signing.loads(preview_token, salt=SALT, max_age=600)
    except signing.SignatureExpired:
        raise ValidationError("The preview expired. Reload and reconfirm the exact settlement.") from None
    evidence = full_settlement_evidence(account, request)
    if proof_digest(evidence) != preview.get("digest"):
        raise ValidationError("Agreement, payment or review evidence changed. Reload and reconfirm before settling.")
    quantity = Decimal(evidence["quantity"])
    redemption = Redemption(redemption_number=_reference("RED", Redemption, "redemption_number"),
        idempotency_key=key, scheme_account=account, metal_grade=account.metal_grade,
        settlement_type="JEWELLERY_PURCHASE", external_reference=invoice, notes=reason, processed_by=actor,
        **{"gold_quantity" if account.savings_mode == "GOLD" else "silver_quantity": quantity})
    redemption.full_clean()
    redemption.save()
    event = SchemeClosureEvent(request=request, sequence=evidence["sequence"] + 1, action="SETTLE",
        resulting_status="SETTLED", actor=actor, actor_label=_actor_label(actor), reason=reason,
        authorization_reference=authorization, idempotency_key=key)
    event.full_clean()
    event.save()
    settlement = ConfiguredSettlement(closure=request, event=event, redemption=redemption,
        basis=evidence["basis"], authorization_reference=authorization, evidence=evidence, evidence_digest=proof_digest(evidence))
    settlement.full_clean()
    settlement.save()
    record_audit_event(action=AuditEvent.Action.REDEMPTION, actor=actor, reason=reason,
        scheme_account=account, redemption=redemption, details=dict(basis=evidence["basis"],
            full_only=True, quantity=str(quantity), grade=account.metal_grade.code, closure=str(request.pk)))
    SchemeAccount.objects.filter(pk=account.pk).update(status="REDEEMED", updated_at=timezone.now())
    SchemeClosureRequest.objects.filter(pk=request.pk).update(status="SETTLED")
    return redemption


@transaction.atomic
def reverse_configured_settlement(*, settlement_id, actor, reason, authorization_reference,
    idempotency_key, expected_sequence):
    from .services import _actor_label, _reference, record_audit_event
    target = ConfiguredSettlement.objects.get(pk=settlement_id)
    account = _account(target.closure.scheme_account_id)
    actor, owner = _actor(actor, account)
    if not owner:
        raise ValidationError("Only an active owner may reverse a configured settlement.")
    request = SchemeClosureRequest.objects.select_for_update().get(pk=target.closure_id)
    settlement = ConfiguredSettlement.objects.select_for_update().get(pk=settlement_id)
    reason = _text(reason, 2000, "a correction reason")
    reference = _text(authorization_reference, 254, "the invoice-correction and entitlement-restoration evidence reference")
    key = _key(idempotency_key)
    sequence = validate_closure_history(request)
    validate_configured_settlement(settlement)
    existing = ConfiguredSettlementReversal.objects.filter(event__idempotency_key=key).first()
    if existing:
        _matching(existing, dict(settlement_id=settlement.pk))
        _matching(existing.event, dict(actor_id=actor.pk, reason=reason, authorization_reference=reference))
        return existing.reversal
    if (type(expected_sequence) is not int or sequence != expected_sequence or request.status != "SETTLED"
        or account.status != "REDEEMED" or hasattr(settlement, "correction")
        or request.events.order_by("-sequence").first().pk != settlement.event_id):
        raise ValidationError("Settlement state changed or was already reversed. Reload its evidence.")
    reversal = RedemptionReversal(redemption=settlement.redemption, processed_by=actor, reason=reason,
        reversal_number=_reference("REV", RedemptionReversal, "reversal_number"))
    reversal.full_clean()
    reversal.save()
    event = SchemeClosureEvent(request=request, sequence=sequence + 1, action="REVERSE", resulting_status="ACCEPTED",
        actor=actor, actor_label=_actor_label(actor), reason=reason, authorization_reference=reference, idempotency_key=key)
    event.full_clean()
    event.save()
    ConfiguredSettlementReversal.objects.create(settlement=settlement, reversal=reversal, event=event)
    record_audit_event(action=AuditEvent.Action.REVERSAL, actor=actor, reason=reason, scheme_account=account,
        redemption=settlement.redemption, details=dict(reversal_number=reversal.reversal_number, closure=str(request.pk), full_only=True))
    SchemeAccount.objects.filter(pk=account.pk).update(status="CLOSURE_PENDING", updated_at=timezone.now())
    SchemeClosureRequest.objects.filter(pk=request.pk).update(status="ACCEPTED")
    return reversal
