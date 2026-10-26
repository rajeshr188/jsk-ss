"""Internal manual fulfilment foundation; no UI, activation or refund-provider API."""
from decimal import Decimal
from uuid import uuid5

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
from .independent_inr_settlement_selectors import (independent_inr_proof,
    require_independent_inr_gate, validate_independent_inr_benefit)
from .independent_settlement_selectors import invoice_inputs

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


def _proposal_evidence(account, request, invoice_payable, *, independent=False, benefit_invoice=None):
    sequence = validate_closure_history(request)
    if request.status != "ACCEPTED" or account.status not in ("ACTIVE", "REDEMPTION_ELIGIBLE", "CLOSURE_PENDING"):
        raise ValidationError("An accepted customer-authorized closure is required.")
    if request.source == "OWNER_ASSISTED" and not request.authorization_reference.strip():
        raise ValidationError("Retain the customer's closure authorization.")
    from .inr_correction_selectors import validate_inr_history, require_original_refund_capacity
    history = validate_inr_history(account)
    if history and not independent and any("independent" in p.evidence for p in history):
        raise ValidationError("Use the gated independent replacement preview; do not bypass its retained evidence.")
    if any(not p.retired for p in history):
        raise ValidationError("A full disposition already exists; inspect its pending fulfilment instead.")
    proof = independent_inr_proof(account, request, invoice_payable, benefit_invoice) if independent else None
    if proof is not None:
        from .inr_settlement_selectors import inr_payment_source_evidence
        sources = inr_payment_source_evidence(account)
    else:
        sources = inr_source_evidence(account)
    split = calculate_inr_final_settlement(principal=Decimal(sources["principal"]), invoice_payable=invoice_payable)
    eligible = (proof["progress"]["state"] == "ELIGIBLE" if proof is not None
        else timezone.localdate(timezone=AGREEMENT_TIMEZONE) >= account.eligible_from)
    basis = "NORMAL" if eligible else "EARLY"
    evidence = dict(version=1, closure=str(request.pk), sequence=sequence, sources=sources, basis=basis,
        invoice_payable=str(invoice_payable), refunds=refund_legs(sources, split.principal_to_invoice))
    require_original_refund_capacity(sources, evidence["refunds"], history)
    if history:
        evidence["previous"] = history[-1].pk
    if proof is not None:
        evidence["independent"] = proof
    return evidence, split


@transaction.atomic
def preview_inr_settlement(*, request_id, actor, invoice_payable):
    """Original optional/calendar/no-benefit foundation; retained proof compatibility."""
    account, request, actor = _locked_closure(request_id, actor)
    if InrSettlementProposal.objects.filter(scheme_account=account, retired=False).exists():
        raise ValidationError("A full disposition already exists; inspect its pending fulfilment instead.")
    evidence, split = _proposal_evidence(account, request, invoice_payable)
    token = signing.dumps(dict(request=str(request.pk), actor=actor.pk, evidence=evidence), salt=SALT)
    return split, token


@transaction.atomic
def preview_independent_inr_settlement(*, request_id, actor, invoice_payable, benefit_invoice=None):
    """New independent-family entry; net invoice is checked against the actual benefit.

    No receipt of goods or money is claimed by a preview or disposition proposal.
    Existing v1 foundation records/entry remain separate and cannot replace this path.
    """
    account, request, actor = _locked_closure(request_id, actor)
    evidence, split = _proposal_evidence(account, request, invoice_payable,
        independent=True, benefit_invoice=benefit_invoice)
    return split, signing.dumps(dict(request=str(request.pk), actor=actor.pk, evidence=evidence), salt=SALT)


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
    independent = evidence.get("independent")
    if independent is not None:
        from .plan_policies import require_operational_configuration
        require_operational_configuration(account.configuration_snapshot)
    existing = InrSettlementProposal.objects.filter(idempotency_key=key).first()
    if existing:
        _matching(existing, facts)
        validate_inr_proposal(existing)
        validate_independent_inr_benefit(existing)
        return existing
    try:
        signing.loads(preview_token, salt=SALT, max_age=600)
    except signing.BadSignature:
        raise ValidationError("The INR preview expired; reload it.") from None
    current, split = _proposal_evidence(account, request, invoice_payable,
        independent=independent is not None,
        benefit_invoice=invoice_inputs(independent["invoice"]) if independent is not None else None)
    if current != evidence:
        raise ValidationError("Financial or closure evidence changed; reload the INR preview.")
    if independent is not None:
        from .replacement_settlement_selectors import require_fresh_replacement_references
        require_fresh_replacement_references(account, authorization, reference)
    if InrSettlementProposal.objects.filter(scheme_account=account, retired=False).exists():
        raise ValidationError("Only one full INR disposition is permitted; corrections require review.")
    if independent and independent["award_evidence"]:
        from .benefit_awards import _retain_closure_award
        _retain_closure_award(account=account, closure=request, actor=actor,
            evidence=independent["award_evidence"], reason=reason, idempotency_key=uuid5(key, "benefit-award"))
    proposal = InrSettlementProposal.objects.create(**facts, principal=split.principal,
        invoice_payable=split.invoice_payable, principal_to_invoice=split.principal_to_invoice,
        principal_refund=split.principal_refund, separate_top_up=split.separate_top_up,
        basis=current["basis"], evidence=current, previous_id=current.get("previous"), actor_label=_actor_label(actor),
        idempotency_key=key, recorded_at=timezone.now())
    SchemeAccount.objects.filter(pk=account.pk).update(status="CLOSURE_PENDING", updated_at=timezone.now())
    validate_independent_inr_benefit(proposal, current=True)
    return proposal


def _pending_proposal(proposal):
    require_independent_inr_gate(proposal)
    validate_independent_inr_benefit(proposal, current=True)
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
    require_independent_inr_gate(proposal)
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
        validate_independent_inr_benefit(proposal)
        return existing
    _pending_proposal(proposal)
    fulfilment = InrSettlementFulfilment.objects.create(**facts, actor_label=_actor_label(actor),
        idempotency_key=key, recorded_at=timezone.now())
    independent = proposal.evidence.get("independent")
    if kind == "JEWELLERY" and independent and independent["award_evidence"]:
        from .models import SchemeBenefitAward
        from .benefit_fulfilments import preview_benefit_fulfilment, record_benefit_fulfilment
        award = SchemeBenefitAward.objects.get(scheme_account=account)
        token = preview_benefit_fulfilment(account_id=account.pk, award_id=award.pk, actor=actor,
            inr_fulfilment_id=fulfilment.pk, customer_receipt_reference=facts["customer_receipt_reference"],
            **invoice_inputs(independent["invoice"]))
        record_benefit_fulfilment(account_id=account.pk, actor=actor, preview_token=token,
            reason=facts["reason"], idempotency_key=uuid5(key, "benefit-invoice"))
    inr_settlement_balance(account)
    validate_independent_inr_benefit(InrSettlementProposal.objects.get(pk=proposal.pk), current=True)
    return fulfilment


@transaction.atomic
def complete_inr_settlement(*, proposal_id, actor, reason, idempotency_key):
    from .services import _actor_label
    target = InrSettlementProposal.objects.get(pk=proposal_id)
    account, request, actor = _locked_closure(target.closure_id, actor)
    proposal = InrSettlementProposal.objects.select_for_update().get(pk=proposal_id)
    require_independent_inr_gate(proposal)
    key = _key(idempotency_key)
    reason = _text(reason, 2000, "the reconciled full-closure reason")
    existing = InrSettlementCompletion.objects.filter(event__idempotency_key=key).first()
    if existing:
        _matching(existing, dict(proposal_id=proposal.pk))
        _matching(existing.event, dict(actor_id=actor.pk, reason=reason))
        validate_inr_completion(existing)
        validate_closure_history(request)
        validate_independent_inr_benefit(proposal)
        return existing
    _pending_proposal(proposal)
    if inr_settlement_balance(account).outstanding != 0:
        raise ValidationError("Jewellery/refunds remain outstanding; do not close the agreement.")
    event = SchemeClosureEvent(request=request, sequence=proposal.evidence["sequence"] + 1,
        action="SETTLE", resulting_status="SETTLED", actor=actor, actor_label=_actor_label(actor),
        reason=reason, authorization_reference=proposal.authorization_reference, idempotency_key=key, created_at=timezone.now())
    event.full_clean()
    event.save()
    completion = InrSettlementCompletion.objects.create(proposal=proposal, event=event)
    SchemeAccount.objects.filter(pk=account.pk).update(status="REDEEMED", updated_at=timezone.now())
    SchemeClosureRequest.objects.filter(pk=request.pk).update(status="SETTLED")
    validate_independent_inr_benefit(InrSettlementProposal.objects.get(pk=proposal.pk), current=True)
    return completion
