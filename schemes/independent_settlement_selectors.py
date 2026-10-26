"""Shared closure qualification and exact-grade proof; never activation."""
import json
from dataclasses import asdict
from decimal import Decimal
from types import SimpleNamespace

from django.core.exceptions import ValidationError
from django.core.serializers.json import DjangoJSONEncoder

from .agreement_eligibility import get_closure_eligibility
from .benefit_award_selectors import benefit_award_evidence, benefit_source_snapshot
from .benefit_fulfilment_selectors import invoice_benefit_amount, require_unchanged_award_sources
from .benefit_selectors import get_closure_benefit_qualification
from .closures import _text
from .models import SchemeBenefitAward
from .settlement_selectors import proof_digest


def independent_closure_proof(account, closure, benefit_invoice):
    result = closure_qualification_proof(account, closure)
    evidence = result["award_evidence"]
    if evidence:
        if evidence["kind"] != "VA_DISCOUNT":
            raise ValidationError("Exact-grade settlement supports only the contracted VA discount, not INR bonus conversion.")
        result["invoice"] = normalize_invoice(benefit_invoice, evidence)
    elif benefit_invoice is not None:
        raise ValidationError("No benefit is qualified for invoice consumption on this closure.")
    return result


def closure_qualification_proof(account, closure):
    """All current evidence must be re-read under the agreement lock on apply."""
    from .replacement_settlement_selectors import replacement_qualification_proof
    replacement = replacement_qualification_proof(account, closure)
    if replacement is not None:
        return replacement
    progress = get_closure_eligibility(closure)
    if progress.state not in ("ELIGIBLE", "COLLECTING", "WAITING_DURATION", "WAITING_PERIOD_END", "DISCONTINUATION_REVIEW"):
        raise ValidationError("Resolve principal, payment and outage evidence before full closure.")
    qualification = get_closure_benefit_qualification(closure)
    if qualification.state in ("REVIEW", "HISTORY_REVIEW"):
        raise ValidationError("Benefit history requires review; do not discard an earned right.")
    award = SchemeBenefitAward.objects.filter(scheme_account=account).first()
    evidence = None
    if award:
        require_unchanged_award_sources(award)
        if not qualification.qualification_met or award.invoice_fulfilments.exists():
            raise ValidationError("Retain and review the existing award; it cannot be silently omitted or re-spent.")
        evidence = award.evidence
    elif qualification.qualification_met:
        evidence = benefit_award_evidence(account, closure=closure)
    result = dict(version=1, progress=asdict(progress), qualification=asdict(qualification),
        sources=benefit_source_snapshot(account), award_id=award.pk if award else None,
        award_evidence=evidence, invoice=None)
    return json.loads(json.dumps(result, cls=DjangoJSONEncoder))


def normalize_invoice(invoice, award_evidence, *, require_receipt=True):
    fields = {"invoice_before_benefit", "eligible_charges", "invoice_evidence_reference",
              "eligible_charge_reference", "customer_receipt_reference"}
    if not require_receipt:
        fields.remove("customer_receipt_reference")
    if not isinstance(invoice, dict) or set(invoice) != fields:
        message = "Supply the complete invoice and eligible-charge evidence."
        if require_receipt:
            message += " Actual customer receipt evidence is also required."
        raise ValidationError(message)
    award = SimpleNamespace(kind=award_evidence["kind"], percentage=Decimal(award_evidence["percentage"]),
        cap_inr=Decimal(award_evidence["cap_inr"]),
        amount=Decimal(award_evidence["amount"]) if award_evidence["amount"] is not None else None)
    if award.kind != "VA_DISCOUNT" and invoice["eligible_charge_reference"] != "":
        raise ValidationError("Purchase bonuses do not have eligible-charge evidence.")
    amount = invoice_benefit_amount(award, invoice["invoice_before_benefit"], invoice["eligible_charges"])
    return dict(invoice_before_benefit=format(invoice["invoice_before_benefit"], ".2f"),
        eligible_charges=format(invoice["eligible_charges"], ".2f") if invoice["eligible_charges"] is not None else None,
        benefit_amount=str(amount),
        **{field: _text(invoice[field], 254, field,
            required=field != "eligible_charge_reference" or award.kind == "VA_DISCOUNT")
            for field in fields - {"invoice_before_benefit", "eligible_charges"}})


def invoice_inputs(proof):
    """Decode only retained/signed canonical money, not arbitrary client coercion."""
    if proof is None:
        return None
    return dict(invoice_before_benefit=Decimal(proof["invoice_before_benefit"]),
        eligible_charges=Decimal(proof["eligible_charges"]) if proof["eligible_charges"] is not None else None,
        **{name: proof[name] for name in ("invoice_evidence_reference", "eligible_charge_reference", "customer_receipt_reference") if name in proof})


def validate_independent_settlement_benefit(settlement):
    """Final lifecycle check after the atomic write, not a source-row constructor.

    Principal-only historical validation stays usable while the transaction builds
    the linked rows. Consumers checking completed lifecycle must also call this.
    """
    from .benefit_fulfilment_selectors import validate_benefit_fulfilment, validate_benefit_reversal
    proof = settlement.evidence.get("independent")
    if proof is None:
        return
    try:
        from .replacement_settlement_selectors import disposition_history, validate_replacement_links
        validate_replacement_links(disposition_history(settlement.redemption.scheme_account))
        expected = proof["award_evidence"]
        award = SchemeBenefitAward.objects.filter(scheme_account=settlement.redemption.scheme_account).first()
        if expected is None:
            if award is not None or proof["invoice"] is not None:
                raise ValueError
            return
        if award is None or award.evidence_digest != proof_digest(expected) or award.evidence != expected:
            raise ValueError
        f = award.invoice_fulfilments.filter(metal_settlement=settlement).first()
        if f is None:
            raise ValueError
        validate_benefit_fulfilment(f)
        invoice = proof["invoice"]
        if any(str(getattr(f, name)) != value for name, value in invoice.items()):
            raise ValueError
        reversed_principal = hasattr(settlement, "correction")
        if hasattr(f, "reversal") != reversed_principal:
            raise ValueError
        if reversed_principal:
            validate_benefit_reversal(f.reversal)
    except (KeyError, TypeError, ValueError, AttributeError):
        raise ValidationError("Independent principal settlement and benefit lifecycle do not match; retain all evidence.") from None
