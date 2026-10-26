"""Gated invoice evidence; never mutate principal, issue refunds or reopen awards."""
from decimal import Decimal

from django.core import signing
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .benefit_awards import _locked
from .benefit_fulfilment_selectors import (benefit_fulfilment_evidence, fulfilment_source,
    invoice_benefit_amount, validate_benefit_fulfilment, validate_benefit_reversal)
from .closures import _key, _matching, _text
from .models import (SchemeBenefitAward, BenefitInvoiceFulfilment, BenefitInvoiceReversal,
    InrSettlementFulfilment, ConfiguredSettlement, InrFulfilmentReturn, ConfiguredSettlementReversal)
from .settlement_selectors import proof_digest

SALT = "benefit-invoice-fulfilment-v1"


def _award(account, award_id):
    return SchemeBenefitAward.objects.select_for_update().get(pk=award_id, scheme_account=account)


def _invoice_row(award, *, invoice_before_benefit, eligible_charges=None, inr_fulfilment_id=None,
                 metal_settlement_id=None, invoice_evidence_reference, eligible_charge_reference="",
                 customer_receipt_reference):
    if bool(inr_fulfilment_id) == bool(metal_settlement_id):
        raise ValidationError("Choose exactly one actual principal handover.")
    amount = invoice_benefit_amount(award, invoice_before_benefit, eligible_charges)
    # Canonical paise representations make preview proof stable across a DB reload.
    row = BenefitInvoiceFulfilment(award=award,
        invoice_before_benefit=invoice_before_benefit.quantize(Decimal(".01")),
        eligible_charges=eligible_charges.quantize(Decimal(".01")) if eligible_charges is not None else None,
        benefit_amount=amount, invoice_after_benefit=(invoice_before_benefit - amount).quantize(Decimal(".01")),
        invoice_evidence_reference=_text(invoice_evidence_reference, 254, "invoice evidence"),
        eligible_charge_reference=_text(eligible_charge_reference, 254, "eligible charge evidence") if award.kind == "VA_DISCOUNT" else "",
        customer_receipt_reference=_text(customer_receipt_reference, 254, "customer receipt"), recorded_at=timezone.now())
    if award.kind != "VA_DISCOUNT" and eligible_charge_reference:
        raise ValidationError("Purchase bonus has no eligible-charge evidence.")
    try:
        if inr_fulfilment_id:
            row.inr_fulfilment = InrSettlementFulfilment.objects.select_for_update(of=("self",)).get(
                pk=inr_fulfilment_id, proposal__scheme_account_id=award.scheme_account_id)
        else:
            row.metal_settlement = ConfiguredSettlement.objects.select_for_update(of=("self",)).get(
                pk=metal_settlement_id, redemption__scheme_account_id=award.scheme_account_id)
    except (InrSettlementFulfilment.DoesNotExist, ConfiguredSettlement.DoesNotExist):
        raise ValidationError("Select a recorded jewellery handover for this agreement.") from None
    _, row.invoice_reference, row.fulfilled_at, _ = fulfilment_source(row)
    previous = award.invoice_fulfilments.order_by("-pk").first()
    if previous:
        from .benefit_application_selectors import validate_bound_review
        disposition = row.inr_fulfilment.proposal if row.inr_fulfilment_id else row.metal_settlement
        decision = validate_bound_review(disposition, current=True)
        row.previous, row.reapplication_decision = previous, decision
    row.evidence = benefit_fulfilment_evidence(row)
    row.evidence_digest = proof_digest(row.evidence)
    validate_benefit_fulfilment(row, current=True)
    return row


@transaction.atomic
def preview_benefit_fulfilment(*, account_id, award_id, actor, **invoice):
    account, actor = _locked(account_id, actor)
    award = _award(account, award_id)
    row = _invoice_row(award, **invoice)
    return signing.dumps(dict(actor=actor.pk, account=account.pk, evidence=row.evidence), salt=SALT)


@transaction.atomic
def record_benefit_fulfilment(*, account_id, actor, preview_token, reason, idempotency_key):
    from .services import _actor_label
    account, actor = _locked(account_id, actor)
    key, reason = _key(idempotency_key), _text(reason, 2000, "benefit handover reason")
    try:
        payload = signing.loads(preview_token, salt=SALT)
        evidence = payload["evidence"]
        if payload["actor"] != actor.pk or payload["account"] != account.pk:
            raise ValueError
        award = _award(account, evidence["award"])
    except (signing.BadSignature, KeyError, TypeError, ValueError, SchemeBenefitAward.DoesNotExist):
        raise ValidationError("Reload the owner-bound benefit invoice preview.") from None
    facts = dict(award_id=award.pk, recorded_by_id=actor.pk, reason=reason, evidence_digest=proof_digest(evidence))
    existing = BenefitInvoiceFulfilment.objects.filter(idempotency_key=key).first()
    if existing:
        _matching(existing, facts)
        validate_benefit_fulfilment(existing)
        return existing
    try:
        signing.loads(preview_token, salt=SALT, max_age=600)
    except signing.BadSignature:
        raise ValidationError("The invoice preview expired; reload it.") from None
    row = _invoice_row(award, invoice_before_benefit=Decimal(evidence["invoice_before_benefit"]),
        eligible_charges=Decimal(evidence["eligible_charges"]) if evidence["eligible_charges"] is not None else None,
        inr_fulfilment_id=evidence["source"]["id"] if evidence["source"]["kind"] == "INR" else None,
        metal_settlement_id=evidence["source"]["id"] if evidence["source"]["kind"] == "METAL" else None,
        invoice_evidence_reference=evidence["invoice_evidence_reference"],
        eligible_charge_reference=evidence["eligible_charge_reference"],
        customer_receipt_reference=evidence["customer_receipt_reference"])
    if row.evidence != evidence:
        raise ValidationError("Invoice or principal evidence changed; reload the preview.")
    row.recorded_by, row.actor_label, row.reason, row.idempotency_key = actor, _actor_label(actor), reason, key
    row.save()
    return row


@transaction.atomic
def reverse_benefit_fulfilment(*, account_id, fulfilment_id, actor, reason, idempotency_key,
        inr_return_id=None, metal_reversal_id=None, invoice_correction_reference,
        customer_confirmation, returned_at):
    """Attest a completed full return; no partial reversal or promise of a return.

    Amount is derived, never supplied. The underlying principal correction retains
    its own authorized preview; this entry must match that already-recorded evidence.
    """
    from .services import _actor_label
    account, actor = _locked(account_id, actor)
    f = BenefitInvoiceFulfilment.objects.select_for_update().get(pk=fulfilment_id, award__scheme_account=account)
    key = _key(idempotency_key)
    if bool(inr_return_id) == bool(metal_reversal_id):
        raise ValidationError("Choose exactly one full principal return.")
    facts = dict(fulfilment_id=f.pk, inr_return_id=inr_return_id, metal_reversal_id=metal_reversal_id,
        amount=f.benefit_amount, recorded_by_id=actor.pk, reason=_text(reason, 2000, "benefit correction reason"),
        invoice_correction_reference=_text(invoice_correction_reference, 120, "corrected invoice"),
        customer_confirmation=_text(customer_confirmation, 254, "customer confirmation"), returned_at=returned_at)
    existing = BenefitInvoiceReversal.objects.filter(idempotency_key=key).first()
    if existing:
        _matching(existing, facts)
        validate_benefit_reversal(existing)
        return existing
    if BenefitInvoiceReversal.objects.filter(fulfilment=f).exists():
        raise ValidationError("This benefit already has a full retained reversal.")
    if inr_return_id:
        InrFulfilmentReturn.objects.select_for_update().get(pk=inr_return_id)
    else:
        ConfiguredSettlementReversal.objects.select_for_update().get(pk=metal_reversal_id)
    row = BenefitInvoiceReversal(**facts, actor_label=_actor_label(actor), idempotency_key=key, recorded_at=timezone.now())
    validate_benefit_reversal(row, current=True)
    row.save()
    return row
