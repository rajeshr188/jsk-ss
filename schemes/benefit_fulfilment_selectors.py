"""Invoice-linked benefit evidence, not a second principal/settlement ledger."""
from dataclasses import dataclass
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.utils import timezone

from .benefit_award_selectors import benefit_source_snapshot, validate_benefit_award
from .benefits import _decimal, calculate_va_discount
from .closure_selectors import validate_closure_history
from .models import BenefitInvoiceFulfilment, InrSettlementProposal, Redemption
from .settlement_selectors import proof_digest, validate_configured_settlement


def invoice_benefit_amount(award, invoice_before_benefit, eligible_charges):
    _decimal(invoice_before_benefit, "Invoice before this scheme benefit", positive=True)
    if award.kind == "INR_PURCHASE_BONUS":
        if eligible_charges is not None:
            raise ValidationError("A purchase bonus does not discount a VA charge base.")
        amount = award.amount
    else:
        amount = calculate_va_discount(eligible_charges=eligible_charges, invoice_payable=invoice_before_benefit,
            percentage=award.percentage, cap=award.cap_inr).amount
    if amount is None or amount >= invoice_before_benefit:
        raise ValidationError("This invoice cannot evidence the full benefit plus principal handover. Review it; do not forfeit a remainder or cash out a benefit.")
    return amount


def fulfilment_source(row):
    """Validate immutable original handover facts, including after a full return."""
    award = row.award
    if bool(row.inr_fulfilment_id) == bool(row.metal_settlement_id):
        raise ValidationError("Link exactly one recorded principal jewellery handover.")
    if row.inr_fulfilment_id:
        from .inr_settlement_selectors import validate_inr_fulfilment
        f = row.inr_fulfilment
        p = f.proposal
        validate_inr_fulfilment(f)
        if (award.scheme_account.savings_mode != "INR_CREDIT" or p.scheme_account_id != award.scheme_account_id
                or f.kind != "JEWELLERY" or f.method != "SHOWROOM" or p.basis != "NORMAL"
                or p.invoice_payable != row.invoice_after_benefit
                or row.customer_receipt_reference != f.customer_receipt_reference):
            raise ValidationError("Benefit invoice must match this agreement's normal full INR jewellery disposition and receipt.")
        return p.closure, p.invoice_reference, f.fulfilled_at, dict(kind="INR", id=f.pk,
            proposal=p.pk, digest=p.evidence_digest, amount=str(f.amount), top_up=f.top_up_reference)
    s = row.metal_settlement
    validate_configured_settlement(s)
    if (award.scheme_account.savings_mode not in ("GOLD", "SILVER")
            or s.redemption.scheme_account_id != award.scheme_account_id or s.basis != "NORMAL"):
        raise ValidationError("Benefit invoice must match this agreement's full exact-grade settlement.")
    expected = [dict(id=p["pk"], status=p["status"], amount=p["amount"],
        allocation=p["metal_allocation__pk"], grams=p["metal_allocation__quantity"],
        grade=award.scheme_account.metal_grade_id, rate=p["scheme_rate_id"],
        order=p["gateway_order_id"], payment=p["gateway_reference"], reversal=p["cash_reversal__pk"])
        for p in award.evidence["payments"]]
    actual = [{k: p.get(k) for k in expected[0]} for p in s.evidence["payments"]] if expected else []
    if not expected or actual != expected:
        raise ValidationError("The full metal handover must retain the award's exact payment/allocation sources.")
    return s.closure, s.redemption.external_reference, s.redemption.completed_at, dict(kind="METAL",
        id=s.pk, redemption=s.redemption_id, digest=s.evidence_digest, grams=str(s.redemption.entitlement_amount))


def benefit_fulfilment_evidence(row):
    closure, reference, at, source = fulfilment_source(row)
    evidence = dict(version=1, award=row.award_id, award_digest=row.award.evidence_digest,
        closure=str(closure.pk), source=source, invoice_reference=reference,
        invoice_before_benefit=str(row.invoice_before_benefit), eligible_charges=str(row.eligible_charges) if row.eligible_charges is not None else None,
        benefit_amount=str(row.benefit_amount), invoice_after_benefit=str(row.invoice_after_benefit),
        invoice_evidence_reference=row.invoice_evidence_reference, eligible_charge_reference=row.eligible_charge_reference,
        customer_receipt_reference=row.customer_receipt_reference, fulfilled_at=at.isoformat(),
        calculation_version=row.award.calculation_version, rounding_rule=row.award.rounding_rule)
    if row.previous_id:
        from .benefit_application_selectors import decision_reference
        evidence.update(version=2, reapplication=decision_reference(row.reapplication_decision))
    return evidence


def require_unchanged_award_sources(award):
    """A closure may progress, but verified payment/qualification facts may not drift."""
    validate_benefit_award(award)
    account = award.scheme_account
    snapshot = benefit_source_snapshot(account)
    if any(award.evidence.get(k) != v for k, v in snapshot.items()):
        raise ValidationError("Award sources changed. Retain the award and reconcile; do not deduct principal.")
    from .agreement_eligibility import _verified_principal
    if not _verified_principal(account, list(account.contributions.select_related(
            "scheme_rate", "metal_allocation", "cash_receipt", "cash_reversal")), timezone.now()):
        raise ValidationError("A verified principal handover is required.")
    from .plan_policies import policy_from_configuration
    if policy_from_configuration(account.configuration_snapshot).obligation == "OPTIONAL":
        from .independent_payment_selectors import require_optional_order_integrity
        require_optional_order_integrity(account)


def validate_benefit_fulfilment(row, *, current=False, _history_read=None):
    award = row.award
    validate_benefit_award(award)
    amount = invoice_benefit_amount(award, row.invoice_before_benefit, row.eligible_charges)
    closure, reference, at, _ = fulfilment_source(row)
    if row.recorded_at is None or timezone.is_naive(row.recorded_at) or at is None or timezone.is_naive(at):
        raise ValidationError("Aware actual handover and recording times are required.")
    if (row.benefit_amount != amount or row.invoice_after_benefit != row.invoice_before_benefit - amount
            or row.invoice_reference != reference or row.fulfilled_at != at
            or at < award.recorded_at or at > timezone.now()
            or row.recorded_at < at or row.recorded_at > timezone.now()
            or not row.invoice_evidence_reference.strip() or not row.customer_receipt_reference.strip()
            or bool(row.eligible_charge_reference.strip()) != (award.kind == "VA_DISCOUNT")
            or row.evidence != benefit_fulfilment_evidence(row) or row.evidence_digest != proof_digest(row.evidence)):
        raise ValidationError("Benefit fulfilment amount, invoice or retained evidence differs.")
    from .benefit_application_selectors import validate_application_link
    validate_application_link(row, current=current, _history_read=None if current else _history_read)
    if not current:
        return
    # The caller may hold the award from before its principal handover completed.
    # Read mutable status from storage, without replacing immutable invoice proof.
    award.scheme_account.refresh_from_db()
    closure.refresh_from_db()
    require_unchanged_award_sources(award)
    validate_closure_history(closure)
    account = award.scheme_account
    if row.inr_fulfilment_id:
        from .inr_settlement_selectors import inr_payment_source_evidence
        p = row.inr_fulfilment.proposal
        if "independent" in p.evidence:
            from .inr_correction_selectors import validate_inr_history
            history = validate_inr_history(account)
        else:
            # Preserve the pre-integration proof's single-proposal boundary.
            history = list(account.inr_settlements.order_by("pk"))
        if (p.retired or hasattr(p, "resolution") or hasattr(row.inr_fulfilment, "physical_return")
                or p.evidence["sources"] != inr_payment_source_evidence(account)
                or not history or history[-1].pk != p.pk
                or any(not prior.retired for prior in history[:-1])
                or ("independent" not in p.evidence and len(history) != 1)):
            raise ValidationError("Reconcile the current full INR disposition before benefit fulfilment.")
        completed = hasattr(p, "completion")
        if completed:
            from .inr_settlement_selectors import validate_inr_completion
            validate_inr_completion(p.completion)
        expected = ("REDEEMED", "SETTLED") if completed else ("CLOSURE_PENDING", "ACCEPTED")
    else:
        s = row.metal_settlement
        from .replacement_settlement_selectors import disposition_history, validate_replacement_links
        history = disposition_history(account)
        validate_replacement_links(history)
        total = sum((Decimal(p["metal_allocation__quantity"]) for p in award.evidence["payments"] if p["status"] == "PAID"), Decimal(0))
        if (hasattr(s, "correction") or total != s.redemption.entitlement_amount
                or not history or history[-1].pk != s.pk
                or any(not hasattr(prior, "correction") for prior in history[:-1])
                or account.inr_settlements.exists()):
            raise ValidationError("Reconcile the exact full metal disposition before benefit fulfilment.")
        expected = ("REDEEMED", "SETTLED")
    if (account.status, closure.status) != expected:
        raise ValidationError("Principal handover and closure state do not match.")
    # One externally issued invoice cannot be borrowed from another disposition.
    if (InrSettlementProposal.objects.filter(invoice_reference__iexact=reference).exclude(
            pk=row.inr_fulfilment.proposal_id if row.inr_fulfilment_id else None).exists()
            or Redemption.objects.filter(external_reference__iexact=reference).exclude(
                pk=row.metal_settlement.redemption_id if row.metal_settlement_id else None).exists()):
        raise ValidationError("The invoice reference is already linked to another principal disposition.")


def validate_benefit_reversal(row, *, current=False, _history_read=None):
    f = row.fulfilment
    validate_benefit_fulfilment(f, _history_read=None if current else _history_read)
    if bool(row.inr_return_id) == bool(row.metal_reversal_id) or row.amount != f.benefit_amount:
        raise ValidationError("Reverse only the complete consumed benefit against one full principal return.")
    if row.inr_return_id:
        from .inr_correction_selectors import validate_inr_resolution
        r = row.inr_return
        validate_inr_resolution(r.resolution)
        if (not f.inr_fulfilment_id or r.fulfilment_id != f.inr_fulfilment_id or r.method != "GOODS_RETURN"
                or r.resolution.kind != "FULL_RETURN" or not r.resolution.proposal.retired
                or row.invoice_correction_reference != r.invoice_correction_reference
                or row.customer_confirmation != r.customer_confirmation or row.returned_at != r.returned_at):
            raise ValidationError("Use the matching actual full INR jewellery return and invoice correction.")
        closure = r.resolution.proposal.closure
        corrected_at = r.resolution.event.created_at
    else:
        r = row.metal_reversal
        validate_configured_settlement(r.settlement)
        if not f.metal_settlement_id or r.settlement_id != f.metal_settlement_id:
            raise ValidationError("Use the matching full exact-grade settlement reversal.")
        closure = r.settlement.closure
        corrected_at = r.event.created_at
    account = f.award.scheme_account
    # These mutable states may have advanced since a caller loaded an old return.
    # Keep the immutable invoice/return evidence intact while reading current state.
    closure.refresh_from_db()
    account.refresh_from_db()
    validate_closure_history(closure)
    if ((current and (account.status != "CLOSURE_PENDING" or closure.status != "ACCEPTED"))
            or not row.invoice_correction_reference.strip() or not row.customer_confirmation.strip()
            or row.returned_at is None or timezone.is_naive(row.returned_at)
            or row.recorded_at is None or timezone.is_naive(row.recorded_at)
            or not f.fulfilled_at <= row.returned_at <= corrected_at <= row.recorded_at <= timezone.now()):
        raise ValidationError("Actual full return and contained closure evidence are required; no promised or partial correction.")


@dataclass(frozen=True)
class BenefitInvoiceStatus:
    fulfilled: Decimal
    reversed: Decimal
    needs_review: bool


def get_benefit_invoice_status(award):
    rows = list(award.invoice_fulfilments.order_by("pk"))
    if not rows:
        return BenefitInvoiceStatus(Decimal("0.00"), Decimal("0.00"), False)
    f = rows[-1]
    r = getattr(f, "reversal", None)
    review = bool(r)  # A returned invoice never automatically reopens an award for spending.
    try:
        from .benefit_application_selectors import application_history
        application_history(award)
        if r:
            validate_benefit_reversal(r, current=True)
        else:
            validate_benefit_fulfilment(f, current=True)
    except ValidationError:
        review = True
    return BenefitInvoiceStatus(sum((f.benefit_amount for f in rows), Decimal("0.00")),
        sum((f.reversal.amount for f in rows if hasattr(f, "reversal")), Decimal("0.00")), review)
