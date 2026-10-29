"""Read-only principal and benefit documents; never grant financial permission."""
from dataclasses import dataclass
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import SchemeBenefitAward


def validate_metal_document_history(account):
    if not account.configuration_snapshot_id or account.configuration_snapshot.policy_schema_version != 2:
        return
    from .models import ConfiguredSettlement
    from .settlement_selectors import validate_configured_settlement
    from .independent_settlement_selectors import validate_independent_settlement_benefit
    for row in ConfiguredSettlement.objects.filter(redemption__scheme_account=account):
        validate_configured_settlement(row)
        validate_independent_settlement_benefit(row)


@dataclass(frozen=True)
class BenefitDocument:
    kind: str
    amount: Decimal | None
    percentage: Decimal
    cap: Decimal
    entries: tuple
    pending_right: bool
    needs_review: bool


def benefit_document(account):
    """Expose invoice facts, not private review reasons or authority references."""
    from .selectors import StatementEntry
    from .benefit_application_selectors import application_history
    from .benefit_fulfilment_selectors import require_unchanged_award_sources, get_benefit_invoice_status
    from .benefit_reapplication_selectors import reapplication_review_status
    award = SchemeBenefitAward.objects.filter(scheme_account=account).first()
    if award is None:
        return None
    rows = list(award.invoice_fulfilments.order_by("pk"))
    entries = [StatementEntry(award.recorded_at, "Purchase benefit recorded", f"BEN-{award.pk}",
        "Retained right; separate from principal", benefit_amount=award.amount)]
    review = False
    try:
        require_unchanged_award_sources(award)
        if rows and not hasattr(rows[-1], "reversal"):
            review = get_benefit_invoice_status(award).needs_review
        elif rows:
            application_history(award)
            review = reapplication_review_status(rows[-1].reversal) == "STALE"
    except ValidationError:
        review = True
    for row in rows:
        entries.append(StatementEntry(row.fulfilled_at, "Benefit applied to invoice", f"BEN-INV-{row.pk}",
            "Returned in full" if hasattr(row, "reversal") else "Applied",
            invoice_reference=row.invoice_reference, benefit_amount=row.benefit_amount,
            detail=(f"Invoice before benefit INR {row.invoice_before_benefit:.2f}; after benefit INR {row.invoice_after_benefit:.2f}. "
                + (f"Eligible charges INR {row.eligible_charges:.2f}. " if row.eligible_charges is not None else "")
                + (f"Replaces BEN-INV-{row.previous_id}; approved review BEN-REV-{row.reapplication_decision_id}."
                   if row.previous_id else "Original benefit invoice."))))
        reversal = getattr(row, "reversal", None)
        if reversal:
            entries.append(StatementEntry(reversal.returned_at, "Benefit invoice fully reversed", f"BEN-RET-{reversal.pk}",
                "Retained right requires review before reuse", benefit_amount=reversal.amount,
                invoice_reference=row.invoice_reference))
            for decision in reversal.reapplication_decisions.order_by("sequence"):
                entries.append(StatementEntry(decision.recorded_at, "Returned benefit review", f"BEN-REV-{decision.pk}",
                    "Approved for replacement review; no handover" if decision.outcome == "APPROVE" else "Held for review"))
    return BenefitDocument(award.get_kind_display(), award.amount, award.percentage, award.cap_inr,
        tuple(sorted(entries, key=lambda e: e.occurred_at)), not rows or hasattr(rows[-1], "reversal"), review)


def inr_statement(account):
    from .selectors import SchemeStatement, StatementEntry
    from .inr_settlement_selectors import inr_settlement_balance
    from .inr_correction_selectors import validate_inr_disposition_state
    from .independent_inr_settlement_selectors import validate_independent_inr_benefit
    balance = inr_settlement_balance(account)  # Reject missing/invalid principal sources.
    proposals = list(account.inr_settlements.order_by("pk"))
    if proposals:
        account.refresh_from_db()
        validate_inr_disposition_state(account)
    entries = []
    for receipt in account.inr_principal_receipts.select_related("contribution", "correction"):
        c = receipt.contribution
        entries.append(StatementEntry(receipt.verified_at, "INR purchase-credit contribution", receipt.source_reference,
            c.get_status_display(), amount_inr=receipt.amount, principal_credit=receipt.amount,
            entitlement_unit="INR", contribution_id=c.pk, payment_label=c.payment_method_display))
        if hasattr(receipt, "correction"):
            correction = receipt.correction
            entries.append(StatementEntry(correction.recorded_at, "INR contribution correction", f"INR-COR-{correction.pk}",
                "Principal removed", principal_debit=receipt.amount, entitlement_unit="INR"))
    for p in proposals:
        validate_independent_inr_benefit(p, current=True)
        details = dict(invoice_reference=p.invoice_reference, settlement_basis=p.get_basis_display())
        entries.append(StatementEntry(p.recorded_at, "Full INR settlement proposed", f"INR-PROP-{p.pk}",
            "Proposal only; no principal discharged", detail="Replaces proposal INR-PROP-" + str(p.previous_id) if p.previous_id else "Original proposal", **details))
        for f in p.fulfilments.order_by("pk"):
            entries.append(StatementEntry(f.fulfilled_at,
                "Jewellery handed over" if f.kind == "JEWELLERY" else "Principal refund recorded",
                f.external_reference, "Showroom-recorded fulfilment", principal_debit=f.amount,
                entitlement_unit="INR", **details))
            returned = getattr(f, "physical_return", None)
            if returned:
                entries.append(StatementEntry(returned.returned_at, "Full principal fulfilment returned", f"INR-RET-{returned.pk}",
                    "Principal restored", principal_credit=f.amount, entitlement_unit="INR", **details))
        if hasattr(p, "completion"):
            entries.append(StatementEntry(p.completion.event.created_at, "Full settlement completed", f"INR-DONE-{p.completion.pk}",
                "All principal legs recorded; historical closure", **details))
        if hasattr(p, "resolution"):
            entries.append(StatementEntry(p.resolution.event.created_at, p.resolution.get_kind_display(), f"INR-RES-{p.resolution.pk}",
                "Agreement contained for review/replacement", **details))
    return SchemeStatement(account, timezone.now(), tuple(sorted(entries, key=lambda e: e.occurred_at)),
        balance.outstanding, "INR", inr_balance=balance, benefit=benefit_document(account))
