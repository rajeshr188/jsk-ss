"""Full INR disposition evidence and remaining liability; no provider mutations."""
from dataclasses import dataclass
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils import timezone

from schemes.payment_refund_selectors import unresolved_payment_events

from .inr_principal import calculate_inr_final_settlement
from .inr_selectors import get_inr_principal_summary, validate_inr_contract
from .models import InrSettlementProposal, PaymentWebhookEvent
from .settlement_selectors import proof_digest


def inr_source_evidence(account):
    """Conservative payment-history proof, evaluated under the account lock on writes."""
    validate_inr_contract(account)
    config = account.configuration_snapshot
    if (config.benefit_policy != "NONE" or config.instalment_policy != "NONE"
            or config.eligibility_policy != "CALENDAR" or config.settlement_policy != "FULL_ONLY"):
        raise ValidationError("This foundation supports only optional, calendar, no-benefit INR contracts.")
    from .eligibility import calculate_eligibility_date
    # The account's legacy-shaped date fields are not permission to shorten a frozen policy.
    if (account.agreed_months != config.duration_months
            or account.eligible_from != calculate_eligibility_date(start_date=account.start_date, agreed_months=config.duration_months)):
        raise ValidationError("Frozen INR duration/date evidence requires review.")
    return inr_payment_source_evidence(account)


def inr_payment_source_evidence(account):
    """Source proof shared with gated benefit fulfilment, never settlement permission.

    The existing disposition entry point above retains its family/benefit gate.
    """
    validate_inr_contract(account)
    config = account.configuration_snapshot
    summary = get_inr_principal_summary(account)
    if summary.needs_review or account.redemptions.exists():
        raise ValidationError("Reconcile principal and legacy settlement history first.")
    payments = list(account.contributions.order_by("pk"))
    from .payment_refund_selectors import is_refunded_order_retired
    for payment in payments:
        if payment.status == "ABANDONED" and is_refunded_order_retired(payment):
            continue
        cash = payment.payment_channel == "IN_STORE_CASH" and payment.payment_gateway == "in_store_cash" and not payment.gateway_mode
        live = payment.payment_channel == "RAZORPAY" and payment.payment_gateway == "razorpay" and payment.gateway_mode == "live"
        if not (cash or live) or payment.status not in (("PAID", "REVERSED") if cash else ("PAID",)):
            raise ValidationError("Pending, unallocated, failed, abandoned or practice payments require disposition before settlement.")
    orders = [p.gateway_order_id for p in payments if p.gateway_order_id]
    events = PaymentWebhookEvent.objects.filter(Q(contribution__in=payments) | Q(gateway_order_id__in=orders)).order_by("pk")
    if unresolved_payment_events(events).exists():
        raise ValidationError("Unresolved provider events prevent INR settlement.")
    receipts = account.inr_principal_receipts.select_related("correction").order_by("verified_at", "pk")
    from .payment_refund_selectors import refund_disposition_evidence
    return dict(version=1, account=account.pk, configuration=config.pk, revision=account.plan_revision_id,
        **refund_disposition_evidence(account),
        principal=str(summary.principal_recorded),
        receipts=[dict(id=r.pk, amount=str(r.amount), source=r.source_reference,
            cash=r.cash_receipt_id, webhook=r.webhook_event_id,
            **({"api_capture": r.api_capture_id} if r.api_capture_id else {}),
            correction=getattr(getattr(r, "correction", None), "pk", None)) for r in receipts],
        payments=[dict(id=p.pk, status=p.status, amount=str(p.amount), order=p.gateway_order_id,
            payment=p.gateway_reference, paid_at=p.paid_at.isoformat() if p.paid_at else None) for p in payments],
        webhooks=list(events.values("pk", "status", "event_type", "gateway_reference")))


def refund_legs(evidence, invoice_application):
    """Use earliest verified receipts for invoice first; retain source-specific remainder."""
    remaining = invoice_application
    legs = []
    for row in evidence["receipts"]:
        if row["correction"] is not None:
            continue
        amount = Decimal(row["amount"])
        used = min(remaining, amount)
        remaining -= used
        if amount > used:
            legs.append(dict(receipt=row["id"], amount=str(amount - used),
                method="CASH_RETURN" if row["cash"] else "PROVIDER_DASHBOARD"))
    if remaining:
        raise ValidationError("Invoice allocation exceeds recorded principal.")
    return legs


def validate_inr_proposal(proposal):
    evidence = proposal.evidence
    try:
        split = calculate_inr_final_settlement(principal=proposal.principal, invoice_payable=proposal.invoice_payable)
        sources = evidence["sources"]
        from .payment_refund_selectors import validate_retained_refund_disposition
        validate_retained_refund_disposition(sources, proposal.scheme_account)
        receipts = sources["receipts"]
        net = sum((Decimal(r["amount"]) for r in receipts if r["correction"] is None), Decimal(0))
        if (evidence["version"] != 1 or proof_digest(evidence) != proposal.evidence_digest
                or not net.is_finite() or net != proposal.principal
                or len({r["id"] for r in receipts}) != len(receipts)
                or Decimal(evidence["invoice_payable"]) != proposal.invoice_payable
                or sources["account"] != proposal.scheme_account_id
                or sources["configuration"] != proposal.scheme_account.configuration_snapshot_id
                or Decimal(sources["principal"]) != proposal.principal
                or proposal.closure.scheme_account_id != proposal.scheme_account_id
                or evidence["closure"] != str(proposal.closure_id)
                or evidence.get("previous") != proposal.previous_id
                or type(evidence["sequence"]) is not int or evidence["sequence"] < 2
                or evidence["basis"] != proposal.basis
                or evidence["refunds"] != refund_legs(sources, split.principal_to_invoice)
                or any(getattr(proposal, name) != getattr(split, name) for name in
                    ("principal_to_invoice", "principal_refund", "separate_top_up"))):
            raise ValueError
    except (KeyError, TypeError, ValueError, ArithmeticError):
        raise ValidationError("INR disposition proof requires review.") from None


def validate_inr_fulfilment(fulfilment):
    p = fulfilment.proposal
    validate_inr_proposal(p)
    if (fulfilment.fulfilled_at is None or timezone.is_naive(fulfilment.fulfilled_at) or fulfilment.fulfilled_at < p.recorded_at
            or fulfilment.fulfilled_at > timezone.now()):
        raise ValidationError("Record actual fulfilment after the agreed proposal, not a future promise.")
    if fulfilment.kind == "JEWELLERY":
        if (fulfilment.receipt_id is not None or fulfilment.amount != p.principal_to_invoice
                or fulfilment.method != "SHOWROOM" or fulfilment.external_reference != p.invoice_reference
                or bool(fulfilment.top_up_reference) != bool(p.separate_top_up)):
            raise ValidationError("Jewellery fulfilment must match the full invoice leg and evidenced external top-up.")
    elif fulfilment.kind == "REFUND":
        leg = next((r for r in p.evidence["refunds"] if r["receipt"] == fulfilment.receipt_id), None)
        if (not leg or fulfilment.receipt.scheme_account_id != p.scheme_account_id
                or fulfilment.amount != Decimal(leg["amount"]) or fulfilment.method != leg["method"]
                or fulfilment.top_up_reference):
            raise ValidationError("Refund must match its complete original-source leg; no cash substitution for online payments.")
    else:
        raise ValidationError("Unknown INR fulfilment leg.")
    if fulfilment.amount <= 0:
        raise ValidationError("Zero-value fulfilment is not evidence.")


@dataclass(frozen=True)
class InrSettlementBalance:
    principal_recorded: Decimal
    fulfilled: Decimal
    outstanding: Decimal
    refund_pending: Decimal
    jewellery_pending: Decimal


def inr_settlement_balance(account):
    return inr_settlement_snapshot(account)[1]


def inr_settlement_snapshot(account):
    """Validate fresh history once and return its paired balance for this read.

    No caller-supplied proof or cross-request cache is accepted. Mutation services
    continue to call the balance selector afresh under their existing locks.
    """
    summary = get_inr_principal_summary(account)
    if summary.needs_review:
        raise ValidationError("INR principal sources require reconciliation.")
    from .inr_correction_selectors import validate_inr_history
    proposals = validate_inr_history(account)
    proposal = next((p for p in proposals if not p.retired), None)
    if proposal is None:
        return proposals, InrSettlementBalance(summary.principal_recorded, Decimal(0), summary.principal_recorded, Decimal(0), Decimal(0))
    jewellery, refund = proposal_fulfilment_totals(proposal)
    return proposals, InrSettlementBalance(summary.principal_recorded, jewellery + refund,
        summary.principal_recorded - jewellery - refund,
        proposal.principal_refund - refund, proposal.principal_to_invoice - jewellery)


def proposal_fulfilment_totals(proposal):
    """Historical gross discharge: physical returns never rewrite original completion."""
    validate_inr_proposal(proposal)
    jewellery = refund = Decimal("0.00")
    for fulfilment in proposal.fulfilments.select_related("receipt"):
        validate_inr_fulfilment(fulfilment)
        if fulfilment.kind == "JEWELLERY":
            jewellery += fulfilment.amount
        else:
            refund += fulfilment.amount
    if jewellery > proposal.principal_to_invoice or refund > proposal.principal_refund:
        raise ValidationError("INR fulfilment exceeds its agreed disposition.")
    return jewellery, refund


def validate_inr_completion(completion):
    p, event = completion.proposal, completion.event
    validate_inr_proposal(p)
    jewellery, refund = proposal_fulfilment_totals(p)
    if (jewellery + refund != p.principal or event.request_id != p.closure_id or event.action != "SETTLE"
            or event.resulting_status != "SETTLED" or event.sequence != p.evidence["sequence"] + 1
            or event.authorization_reference != p.authorization_reference
            or event.created_at < p.recorded_at):
        raise ValidationError("All INR principal must be fulfilled before full closure.")
