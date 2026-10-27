"""Source-linked INR principal bookkeeping, not payment verification or a refund API.

Verified-source hooks exist; collection/activation stays gated until the complete
schema-2 payment, eligibility and settlement workflows are accepted.
Every mutation locks the agreement before its source, matching the payment lock order.
"""
from dataclasses import dataclass
from decimal import Decimal
import uuid

from django.core.exceptions import ValidationError
from django.db import transaction

from .closures import _actor, _key, _matching, _text
from .inr_selectors import validate_inr_contract, validate_principal_receipt, validate_principal_correction
from .models import (Contribution, InrPrincipalReceipt, InrPrincipalCorrection,
                     InStoreCashContributionReversal, InStoreCashReceipt, PaymentWebhookEvent, SchemeAccount)


def _source(contribution_id):
    account_id = Contribution.objects.values_list("scheme_account_id", flat=True).get(pk=contribution_id)
    account = SchemeAccount.objects.select_for_update().get(pk=account_id)
    validate_inr_contract(account)
    source = Contribution.objects.select_for_update().get(pk=contribution_id)
    if source.scheme_account_id != account.pk:
        raise ValidationError("The source agreement changed; inspect it again.")
    return account, source


def _locked_source(contribution_id, actor):
    account, source = _source(contribution_id)
    actor, owner = _actor(actor, account)
    if not owner:
        raise ValidationError("Only an active owner may record INR principal evidence.")
    return account, source, actor


def _require_new_principal(account, source):
    if source.payment_gateway == "razorpay":
        from .payment_refund_resolutions import require_payment_not_refund_resolved
        require_payment_not_refund_resolved(gateway_mode=source.gateway_mode, payment_id=source.gateway_reference)
    if source.status != "PAID":
        raise ValidationError("Record principal only after verified payment, not pending or reversed payment.")
    if account.inr_settlements.exists():
        raise ValidationError("Late funds after an agreed disposition require separate reconciliation; retain their source evidence.")
    if account.status not in ("ACTIVE", "REDEMPTION_ELIGIBLE", "CLOSURE_PENDING"):
        raise ValidationError("Late funds on a closed agreement require explicit settlement review.")


def _source_key(kind, pk):
    return uuid.uuid5(uuid.NAMESPACE_URL, f"jsk:inr:{kind}:{pk}")


@transaction.atomic
def record_inr_principal(*, contribution_id, actor, reason, idempotency_key,
                         cash_receipt_id=None, webhook_event_id=None):
    from .services import _actor_label
    account, source, actor = _locked_source(contribution_id, actor)
    key = _key(idempotency_key)
    facts = dict(scheme_account_id=account.pk, configuration_id=account.configuration_snapshot_id,
                 contribution_id=source.pk, amount=source.amount, source_reference=source.gateway_reference,
                 verified_at=source.paid_at, cash_receipt_id=cash_receipt_id, webhook_event_id=webhook_event_id,
                 recorded_by_id=actor.pk, reason=_text(reason, 2000, "the principal recording reason"))
    existing = InrPrincipalReceipt.objects.filter(idempotency_key=key).first()
    if existing:
        _matching(existing, facts)
        validate_principal_receipt(existing)
        return existing
    if InrPrincipalReceipt.objects.filter(contribution=source).exists():
        raise ValidationError("This contribution already has principal evidence; use its original submission identifier.")
    _require_new_principal(account, source)
    receipt = InrPrincipalReceipt(**facts, actor_label=_actor_label(actor), idempotency_key=key)
    receipt.save()
    return receipt


@transaction.atomic
def record_captured_inr_principal(*, event_id, body):
    """Internal post-verification consumer; never authenticate or collect funds here."""
    from .payment_evidence import validated_capture_payload
    from .instalments import has_monthly_instalments
    from .instalment_payments import attribute_razorpay_instalment
    target = PaymentWebhookEvent.objects.get(pk=event_id)
    if target.contribution_id is None:
        raise ValidationError("A captured contribution is required.")
    account, source = _source(target.contribution_id)
    event = PaymentWebhookEvent.objects.select_for_update().get(pk=event_id)
    validated_capture_payload(event=event, contribution=source, body=body)
    receipt = InrPrincipalReceipt.objects.filter(contribution=source).first()
    if receipt:
        # A duplicate event can add timing evidence, never another principal credit.
        validate_principal_receipt(receipt)
    else:
        _require_new_principal(account, source)
        receipt = InrPrincipalReceipt.objects.create(scheme_account=account,
            configuration_id=account.configuration_snapshot_id, contribution=source,
            amount=source.amount, source_reference=source.gateway_reference,
            verified_at=source.paid_at, webhook_event=event, recorded_by=None,
            actor_label="system:razorpay-capture", reason="Verified live captured-payment principal.",
            idempotency_key=_source_key("principal", source.pk))
    if has_monthly_instalments(account):
        attribute_razorpay_instalment(event_id=event.pk, body=body)
    return receipt


@transaction.atomic
def record_cash_inr_principal(*, cash_receipt_id):
    """Link an actual owner receipt and its schedule evidence in one transaction."""
    from .instalments import has_monthly_instalments
    from .instalment_payments import attribute_cash_instalment
    cash = InStoreCashReceipt.objects.get(pk=cash_receipt_id)
    account, source = _source(cash.contribution_id)
    receipt = InrPrincipalReceipt.objects.filter(contribution=source).first()
    if receipt:
        validate_principal_receipt(receipt)
        if receipt.cash_receipt_id != cash.pk:
            raise ValidationError("The original principal source must be retained.")
    else:
        receipt = record_inr_principal(contribution_id=source.pk, actor=cash.received_by,
            reason="Verified showroom cash principal.", idempotency_key=_source_key("principal", source.pk),
            cash_receipt_id=cash.pk)
    if has_monthly_instalments(account):
        attribute_cash_instalment(contribution_id=source.pk)
    return receipt


@transaction.atomic
def record_cash_inr_correction(*, cash_reversal_id, actor):
    """Mirror a completed full cash-entry correction, never a refund instruction."""
    from .instalments import has_monthly_instalments
    from .instalment_payments import reverse_cash_instalment
    reversal = InStoreCashContributionReversal.objects.get(pk=cash_reversal_id)
    account, source, actor = _locked_source(reversal.contribution_id, actor)
    receipt = InrPrincipalReceipt.objects.get(contribution=source)
    correction = record_inr_cash_correction(receipt_id=receipt.pk, cash_reversal_id=reversal.pk,
        actor=actor, reason=reversal.reason, idempotency_key=_source_key("cash-correction", reversal.pk))
    if has_monthly_instalments(account):
        reverse_cash_instalment(contribution_id=source.pk)
    return correction


@transaction.atomic
def record_inr_cash_correction(*, receipt_id, cash_reversal_id, actor, reason, idempotency_key):
    from .services import _actor_label
    target = InrPrincipalReceipt.objects.get(pk=receipt_id)
    account, source, actor = _locked_source(target.contribution_id, actor)
    receipt = InrPrincipalReceipt.objects.select_for_update().get(pk=receipt_id)
    reversal = InStoreCashContributionReversal.objects.select_for_update().get(pk=cash_reversal_id)
    key = _key(idempotency_key)
    facts = dict(receipt_id=receipt.pk, cash_reversal_id=reversal.pk, recorded_by_id=actor.pk,
                 reason=_text(reason, 2000, "the principal correction reason"))
    existing = InrPrincipalCorrection.objects.filter(idempotency_key=key).first()
    if existing:
        _matching(existing, facts)
        validate_principal_correction(existing)
        return existing
    if (account.status not in ("ACTIVE", "REDEMPTION_ELIGIBLE") or account.closure_requests.exists()
            or account.redemptions.exists()):
        raise ValidationError("Closure/fulfilment evidence requires a separate correction review.")
    if InrPrincipalCorrection.objects.filter(receipt=receipt).exists():
        raise ValidationError("This principal receipt is already corrected.")
    correction = InrPrincipalCorrection(**facts, actor_label=_actor_label(actor), idempotency_key=key)
    correction.save()
    return correction


@dataclass(frozen=True)
class InrFinalSettlementAmounts:
    principal: Decimal
    invoice_payable: Decimal
    principal_to_invoice: Decimal
    principal_refund: Decimal
    separate_top_up: Decimal


def calculate_inr_final_settlement(*, principal, invoice_payable):
    """Pure principal split, not eligibility, benefit calculation or fulfilment evidence."""
    for value in (principal, invoice_payable):
        if (not isinstance(value, Decimal) or not value.is_finite()
                or value < 0 or value > Decimal("999999999999.99")
                or value != value.quantize(Decimal("0.01"))):
            raise ValidationError("Use non-negative finite Decimal INR amounts in paise.")
    if principal == 0:
        raise ValidationError("An unused agreement needs cancellation, not financial settlement.")
    applied = min(principal, invoice_payable)
    return InrFinalSettlementAmounts(principal, invoice_payable, applied, principal - applied, invoice_payable - applied)
