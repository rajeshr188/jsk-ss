"""Independent INR disposition proof and complete benefit lifecycle reads."""
from decimal import Decimal

from django.core.exceptions import ValidationError

from .benefit_award_selectors import benefit_source_snapshot
from .benefit_fulfilment_selectors import (require_unchanged_award_sources,
    validate_benefit_fulfilment, validate_benefit_reversal)
from .independent_settlement_selectors import closure_qualification_proof, normalize_invoice
from .inr_selectors import validate_inr_contract
from .models import SchemeBenefitAward
from .settlement_selectors import proof_digest


def independent_inr_proof(account, closure, invoice_payable, benefit_invoice):
    validate_inr_contract(account)
    from .plan_policies import require_operational_configuration
    require_operational_configuration(account.configuration_snapshot)
    proof = closure_qualification_proof(account, closure)
    if proof["award_evidence"]:
        invoice = normalize_invoice(benefit_invoice, proof["award_evidence"], require_receipt=False)
        if Decimal(invoice["invoice_before_benefit"]) - Decimal(invoice["benefit_amount"]) != invoice_payable:
            raise ValidationError("The principal split must use the invoice after its exact contracted benefit.")
        proof["invoice"] = invoice
    elif benefit_invoice is not None:
        raise ValidationError("No benefit is qualified; do not invent an invoice discount.")
    return proof


def require_independent_inr_gate(proposal):
    if "independent" in proposal.evidence:
        from .plan_policies import require_operational_configuration
        require_operational_configuration(proposal.scheme_account.configuration_snapshot)


def validate_independent_inr_benefit(proposal, *, current=False):
    """Validate after atomic orchestration, not between construction of linked rows.

    Old foundation proofs remain readable. This is not permission to replace a
    returned disposition, award a second benefit or authorize payment initiation.
    """
    proof = proposal.evidence.get("independent")
    if proof is None:
        return
    try:
        account = proposal.scheme_account
        if current and proof["sources"] != benefit_source_snapshot(account):
            raise ValueError
        award = SchemeBenefitAward.objects.filter(scheme_account=account).first()
        expected = proof["award_evidence"]
        if expected is None:
            if award or proof["invoice"] is not None:
                raise ValueError
            return
        if not award or award.evidence != expected or award.evidence_digest != proof_digest(expected):
            raise ValueError
        if current:
            require_unchanged_award_sources(award)
        invoice = proof["invoice"]
        if (proposal.basis != "NORMAL" or proposal.principal_to_invoice <= 0
                or Decimal(invoice["invoice_before_benefit"]) - Decimal(invoice["benefit_amount"]) != proposal.invoice_payable):
            raise ValueError
        handover = proposal.fulfilments.filter(kind="JEWELLERY").first()
        f = getattr(award, "invoice_fulfilment", None)
        if handover is None:
            if f is not None:
                raise ValueError
            return
        if f is None or f.inr_fulfilment_id != handover.pk:
            raise ValueError
        validate_benefit_fulfilment(f)
        if any((str(getattr(f, name)) if getattr(f, name) is not None else None) != value
               for name, value in invoice.items()):
            raise ValueError
        returned = getattr(handover, "physical_return", None)
        reversal = getattr(f, "reversal", None)
        if bool(returned) != bool(reversal):
            raise ValueError
        if reversal:
            if reversal.inr_return_id != returned.pk:
                raise ValueError
            validate_benefit_reversal(reversal)
    except (KeyError, TypeError, ValueError, AttributeError, ArithmeticError):
        raise ValidationError("Independent INR principal and benefit evidence requires review; retain all records.") from None
