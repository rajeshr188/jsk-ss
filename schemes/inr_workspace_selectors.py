"""Validated owner presentation of retained INR settlement and exact fulfilment legs."""
from .inr_settlement_selectors import inr_settlement_snapshot
from .models import InrSettlementFulfilment


def fulfilment_legs(proposal):
    legs = {}
    if proposal.principal_to_invoice:
        legs["JEWELLERY"] = dict(kind="JEWELLERY", method="SHOWROOM", receipt_id=None,
            amount=proposal.principal_to_invoice)
    for row in proposal.evidence["refunds"]:
        legs[f"REFUND:{row['receipt']}"] = dict(kind="REFUND", method=row["method"],
            receipt_id=row["receipt"], amount=row["amount"])
    methods = dict(InrSettlementFulfilment._meta.get_field("method").choices)
    for leg in legs.values():
        leg["kind_label"] = "Jewellery delivery" if leg["kind"] == "JEWELLERY" else "Principal refund"
        leg["method_label"] = methods[leg["method"]]
    return legs


def pending_fulfilment_legs(proposal):
    """Presentation only; the mutation service rechecks fulfilment under lock."""
    fulfilled = set(proposal.fulfilments.values_list("kind", "receipt_id"))
    return {key: leg for key, leg in fulfilment_legs(proposal).items()
        if (leg["kind"], leg["receipt_id"]) not in fulfilled}


def inr_owner_workspace(closure):
    history, balance = inr_settlement_snapshot(closure.scheme_account)
    current = next((p for p in history if not p.retired and p.closure_id == closure.pk), None)
    remaining = []
    if current:
        remaining = list(pending_fulfilment_legs(current).values())
    return dict(history=history, current=current, remaining=remaining,
        balance=balance)
