"""Retained full-return evidence; never infer a physical return from a balance."""
from datetime import UTC
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.utils import timezone

from .inr_settlement_selectors import (inr_source_evidence, validate_inr_proposal,
    validate_inr_fulfilment, validate_inr_completion, proposal_fulfilment_totals)
from .settlement_selectors import proof_digest


def require_original_refund_capacity(sources, refunds, previous_proposals):
    """A customer's return does not reset the provider's original capture/refund cap."""
    from .models import InrSettlementFulfilment
    amounts = {r["id"]: Decimal(r["amount"]) for r in sources["receipts"]}
    used = {}
    for receipt_id, amount in InrSettlementFulfilment.objects.filter(
            proposal__in=previous_proposals, method="PROVIDER_DASHBOARD", kind="REFUND").values_list("receipt_id", "amount"):
        used[receipt_id] = used.get(receipt_id, Decimal(0)) + amount
    for leg in refunds:
        if leg["method"] == "PROVIDER_DASHBOARD" and used.get(leg["receipt"], Decimal(0)) + Decimal(leg["amount"]) > amounts[leg["receipt"]]:
            raise ValidationError("Prior online refunds exhausted this original payment's refund capacity. Reconcile an approved refund route separately; customer returns do not reset the provider limit.")


def disposition_snapshot(proposal):
    completion = getattr(proposal, "completion", None)
    return dict(proposal=proposal.pk, digest=proposal.evidence_digest,
        completion=completion.pk if completion else None,
        fulfilments=[dict(id=f.pk, kind=f.kind, receipt=f.receipt_id, amount=str(f.amount),
            method=f.method, reference=f.external_reference, customer=f.customer_receipt_reference,
            top_up=f.top_up_reference, at=f.fulfilled_at.isoformat())
            for f in proposal.fulfilments.order_by("pk")])


def return_facts(row):
    return dict(fulfilment_id=row.fulfilment_id, method=row.method,
        external_reference=row.external_reference, customer_confirmation=row.customer_confirmation,
        invoice_correction_reference=row.invoice_correction_reference,
        top_up_refund_reference=row.top_up_refund_reference, returned_at=row.returned_at.astimezone(UTC).isoformat())


def validate_inr_return(row):
    f, resolution = row.fulfilment, row.resolution
    validate_inr_fulfilment(f)
    if (resolution.kind != "FULL_RETURN" or f.proposal_id != resolution.proposal_id
            or not row.amount.is_finite() or row.amount != f.amount
            or row.returned_at is None or timezone.is_naive(row.returned_at)
            or row.returned_at < f.fulfilled_at or row.returned_at > timezone.now()
            or not row.external_reference.strip() or not row.customer_confirmation.strip()):
        raise ValidationError("Return evidence must match the actual complete fulfilled portion.")
    if f.kind == "JEWELLERY":
        if (row.method != "GOODS_RETURN" or not row.invoice_correction_reference.strip()
                or bool(row.top_up_refund_reference.strip()) != bool(f.proposal.separate_top_up)):
            raise ValidationError("Retain jewellery return, corrected invoice and any external top-up refund evidence.")
    elif (row.method not in ("CASH_RECEIPT", "BANK_CREDIT")
            or row.invoice_correction_reference or row.top_up_refund_reference):
        raise ValidationError("A refunded principal leg needs actual money received back, not a promised refund cancellation.")


def validate_inr_resolution(resolution):
    p, event, evidence = resolution.proposal, resolution.event, resolution.evidence
    validate_inr_proposal(p)
    completion = getattr(p, "completion", None)
    returns = list(resolution.returns.select_related("fulfilment").order_by("fulfilment_id"))
    fulfilment_ids = set(p.fulfilments.values_list("pk", flat=True))
    try:
        if (evidence["version"] != 1 or proof_digest(evidence) != resolution.evidence_digest
                or evidence["snapshot"] != disposition_snapshot(p)
                or evidence["kind"] != resolution.kind
                or evidence["returns"] != [return_facts(r) for r in returns]
                or type(evidence["sequence"]) is not int
                or event.sequence != evidence["sequence"] + 1
                or event.sequence <= p.evidence["sequence"]
                or event.request_id != p.closure_id or event.resulting_status != "ACCEPTED"
                or event.action != ("REVERSE" if completion else "NOTE")
                or not event.authorization_reference.strip() or not event.reason.strip()
                or not event.actor_label.strip() or event.created_at < p.recorded_at):
            raise ValueError
        if completion and (resolution.kind != "FULL_RETURN" or event.sequence != completion.event.sequence + 1):
            raise ValueError
        if resolution.kind == "VOID":
            if fulfilment_ids or returns or completion:
                raise ValueError
        elif resolution.kind == "FULL_RETURN":
            if not fulfilment_ids or {r.fulfilment_id for r in returns} != fulfilment_ids:
                raise ValueError
        else:
            raise ValueError
    except (KeyError, TypeError, ValueError):
        raise ValidationError("INR disposition correction proof requires review.") from None
    for row in returns:
        validate_inr_return(row)
        if row.returned_at > event.created_at:
            raise ValidationError("Return evidence cannot postdate its recorded resolution.")


def validate_inr_history(account):
    """Validate a single retained generation chain, including every retired proposal."""
    proposals = list(account.inr_settlements.select_related("closure", "completion__event", "resolution__event").order_by("pk"))
    if not proposals:
        return proposals
    sources = inr_source_evidence(account)
    previous = None
    for index, p in enumerate(proposals):
        validate_inr_proposal(p)
        proposal_fulfilment_totals(p)
        resolution = getattr(p, "resolution", None)
        if (p.evidence["sources"] != sources or p.retired != bool(resolution)
                or p.previous_id != (previous.pk if previous else None)
                or (previous and (not previous.retired or p.closure_id != previous.closure_id
                    or p.evidence["sequence"] < previous.resolution.event.sequence
                    or p.recorded_at < previous.resolution.event.created_at))):
            raise ValidationError("INR disposition chain or original-source evidence requires review.")
        require_original_refund_capacity(sources, p.evidence["refunds"], proposals[:index])
        completion = getattr(p, "completion", None)
        if completion:
            validate_inr_completion(completion)
        if resolution:
            validate_inr_resolution(resolution)
        elif p.fulfilments.filter(physical_return__isnull=False).exists():
            raise ValidationError("Physical return is detached from the disposition resolution.")
        previous = p
    return proposals


def validate_inr_disposition_state(account):
    from .closure_selectors import validate_closure_history
    history = validate_inr_history(account)
    if not history:
        if account.status in ("REDEEMED", "CLOSURE_PENDING"):
            raise ValidationError("INR closure is missing disposition evidence.")
        return
    latest = history[-1]
    validate_closure_history(latest.closure)
    completed = not latest.retired and hasattr(latest, "completion")
    if (account.status != ("REDEEMED" if completed else "CLOSURE_PENDING")
            or latest.closure.status != ("SETTLED" if completed else "ACCEPTED")):
        raise ValidationError("INR disposition does not match its contained agreement state.")
