"""Internal manual fulfilment foundation; no UI, activation or refund-provider API."""
from decimal import Decimal

from django.core import signing
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .closures import _actor, _key, _matching, _text
from .closure_selectors import validate_closure_history
from .inr_principal import calculate_inr_final_settlement
from .inr_selectors import validate_inr_contract
from .inr_settlement_selectors import (inr_source_evidence, refund_legs, inr_settlement_balance,
    validate_inr_proposal, validate_inr_fulfilment, validate_inr_completion)
from .instalments import AGREEMENT_TIMEZONE
from .models import (SchemeAccount, SchemeClosureRequest, SchemeClosureEvent,
    InrSettlementProposal, InrSettlementFulfilment, InrSettlementCompletion)
from .settlement_selectors import proof_digest

SALT = "inr-final-disposition-v1"


def _locked_closure(request_id, actor):
    target = SchemeClosureRequest.objects.get(pk=request_id)
    account = SchemeAccount.objects.select_for_update().get(pk=target.scheme_account_id)
    actor, owner = _actor(actor, account)
    if not owner:
        raise ValidationError("Only an active owner may record manual INR settlement evidence.")
    validate_inr_contract(account)
    request = SchemeClosureRequest.objects.select_for_update().get(pk=request_id)
    return account, request, actor


def _proposal_evidence(account, request, invoice_payable):
    sequence = validate_closure_history(request)
    if request.status != "ACCEPTED" or account.status not in ("ACTIVE", "REDEMPTION_ELIGIBLE", "CLOSURE_PENDING"):
        raise ValidationError("An accepted customer-authorized closure is required.")
    if request.source == "OWNER_ASSISTED" and not request.authorization_reference.strip():
        raise ValidationError("Retain the customer's closure authorization.")
    from .inr_correction_selectors import validate_inr_history, require_original_refund_capacity
    history = validate_inr_history(account)
    if any(not p.retired for p in history):
        raise ValidationError("A full disposition already exists; inspect its pending fulfilment instead.")
    sources = inr_source_evidence(account)
    split = calculate_inr_final_settlement(principal=Decimal(sources["principal"]), invoice_payable=invoice_payable)
    basis = "NORMAL" if timezone.localdate(timezone=AGREEMENT_TIMEZONE) >= account.eligible_from else "EARLY"
    evidence = dict(version=1, closure=str(request.pk), sequence=sequence, sources=sources, basis=basis,
        invoice_payable=str(invoice_payable), refunds=refund_legs(sources, split.principal_to_invoice))
    require_original_refund_capacity(sources, evidence["refunds"], history)
    if history:
        evidence["previous"] = history[-1].pk
    return evidence, split


@transaction.atomic
def preview_inr_settlement(*, request_id, actor, invoice_payable):
    account, request, actor = _locked_closure(request_id, actor)
    if InrSettlementProposal.objects.filter(scheme_account=account, retired=False).exists():
        raise ValidationError("A full disposition already exists; inspect its pending fulfilment instead.")
    evidence, split = _proposal_evidence(account, request, invoice_payable)
    token = signing.dumps(dict(request=str(request.pk), actor=actor.pk, evidence=evidence), salt=SALT)
    return split, token


@transaction.atomic
def propose_inr_settlement(*, request_id, actor, preview_token, invoice_reference,
                           authorization_reference, reason, idempotency_key):
    from .services import _actor_label
    account, request, actor = _locked_closure(request_id, actor)
    key = _key(idempotency_key)
    reference = _text(invoice_reference, 120, "the invoice reference", required=False) or None
    authorization = _text(authorization_reference, 254, "customer agreement to this exact invoice/refund split")
    reason = _text(reason, 2000, "the disposition reason")
    try:
        payload = signing.loads(preview_token, salt=SALT)
        if payload["request"] != str(request.pk) or payload["actor"] != actor.pk:
            raise ValueError
        evidence = payload["evidence"]
        invoice_payable = Decimal(evidence["invoice_payable"])
    except (signing.BadSignature, KeyError, TypeError, ValueError, ArithmeticError):
        raise ValidationError("Reload the owner-bound INR disposition preview.") from None
    facts = dict(scheme_account_id=account.pk, closure_id=request.pk, invoice_reference=reference,
        authorization_reference=authorization, reason=reason, recorded_by_id=actor.pk,
        evidence_digest=proof_digest(evidence))
    existing = InrSettlementProposal.objects.filter(idempotency_key=key).first()
    if existing:
        _matching(existing, facts)
        validate_inr_proposal(existing)
        return existing
    try:
        signing.loads(preview_token, salt=SALT, max_age=600)
    except signing.BadSignature:
        raise ValidationError("The INR preview expired; reload it.") from None
    current, split = _proposal_evidence(account, request, invoice_payable)
    if current != evidence:
        raise ValidationError("Financial or closure evidence changed; reload the INR preview.")
    if InrSettlementProposal.objects.filter(scheme_account=account, retired=False).exists():
        raise ValidationError("Only one full INR disposition is permitted; corrections require review.")
    proposal = InrSettlementProposal.objects.create(**facts, principal=split.principal,
        invoice_payable=split.invoice_payable, principal_to_invoice=split.principal_to_invoice,
        principal_refund=split.principal_refund, separate_top_up=split.separate_top_up,
        basis=current["basis"], evidence=current, previous_id=current.get("previous"), actor_label=_actor_label(actor), idempotency_key=key)
    SchemeAccount.objects.filter(pk=account.pk).update(status="CLOSURE_PENDING", updated_at=timezone.now())
    return proposal


def _pending_proposal(proposal):
    request = proposal.closure
    if (proposal.retired or hasattr(proposal, "resolution") or hasattr(proposal, "completion") or request.status != "ACCEPTED"
            or proposal.scheme_account.status != "CLOSURE_PENDING"
            or validate_closure_history(request) != proposal.evidence["sequence"]):
        raise ValidationError("INR closure state changed; investigate before recording further fulfilment.")
    inr_settlement_balance(proposal.scheme_account)


@transaction.atomic
def record_inr_fulfilment(*, proposal_id, actor, kind, method, external_reference,
    customer_receipt_reference, fulfilled_at, reason, idempotency_key, receipt_id=None, top_up_reference=""):
    from .services import _actor_label
    target = InrSettlementProposal.objects.get(pk=proposal_id)
    account, request, actor = _locked_closure(target.closure_id, actor)
    proposal = InrSettlementProposal.objects.select_for_update().get(pk=proposal_id)
    # Derive the exact permitted leg amount. Callers cannot specify a partial debit.
    if kind == "JEWELLERY" and receipt_id is None:
        amount = proposal.principal_to_invoice
    elif kind == "REFUND":
        leg = next((leg for leg in proposal.evidence["refunds"] if leg["receipt"] == receipt_id), None)
        if not leg:
            raise ValidationError("Select an original-source refund leg from this proposal.")
        amount = Decimal(leg["amount"])
    else:
        raise ValidationError("Select a complete jewellery or refund leg.")
    facts = dict(proposal_id=proposal.pk, kind=kind, receipt_id=receipt_id, amount=amount, method=method,
        external_reference=_text(external_reference, 120, "the completed transaction/invoice reference"),
        customer_receipt_reference=_text(customer_receipt_reference, 254, "the customer's actual receipt evidence"),
        top_up_reference=_text(top_up_reference, 120, "the external invoice top-up receipt", required=False),
        fulfilled_at=fulfilled_at, recorded_by_id=actor.pk, reason=_text(reason, 2000, "the fulfilment reason"))
    key = _key(idempotency_key)
    existing = InrSettlementFulfilment.objects.filter(idempotency_key=key).first()
    if existing:
        _matching(existing, facts)
        validate_inr_fulfilment(existing)
        return existing
    _pending_proposal(proposal)
    fulfilment = InrSettlementFulfilment.objects.create(**facts, actor_label=_actor_label(actor), idempotency_key=key)
    inr_settlement_balance(account)
    return fulfilment


@transaction.atomic
def complete_inr_settlement(*, proposal_id, actor, reason, idempotency_key):
    from .services import _actor_label
    target = InrSettlementProposal.objects.get(pk=proposal_id)
    account, request, actor = _locked_closure(target.closure_id, actor)
    proposal = InrSettlementProposal.objects.select_for_update().get(pk=proposal_id)
    key = _key(idempotency_key)
    reason = _text(reason, 2000, "the reconciled full-closure reason")
    existing = InrSettlementCompletion.objects.filter(event__idempotency_key=key).first()
    if existing:
        _matching(existing, dict(proposal_id=proposal.pk))
        _matching(existing.event, dict(actor_id=actor.pk, reason=reason))
        validate_inr_completion(existing)
        validate_closure_history(request)
        return existing
    _pending_proposal(proposal)
    if inr_settlement_balance(account).outstanding != 0:
        raise ValidationError("Jewellery/refunds remain outstanding; do not close the agreement.")
    event = SchemeClosureEvent(request=request, sequence=proposal.evidence["sequence"] + 1,
        action="SETTLE", resulting_status="SETTLED", actor=actor, actor_label=_actor_label(actor),
        reason=reason, authorization_reference=proposal.authorization_reference, idempotency_key=key)
    event.full_clean()
    event.save()
    completion = InrSettlementCompletion.objects.create(proposal=proposal, event=event)
    SchemeAccount.objects.filter(pk=account.pk).update(status="REDEEMED", updated_at=timezone.now())
    SchemeClosureRequest.objects.filter(pk=request.pk).update(status="SETTLED")
    return completion
