"""Validated owner presentation of retained INR settlement and exact fulfilment legs."""
from .inr_settlement_selectors import inr_settlement_snapshot


def fulfilment_legs(proposal):
    legs = {}
    if proposal.principal_to_invoice:
        legs["JEWELLERY"] = dict(kind="JEWELLERY", method="SHOWROOM", receipt_id=None,
            amount=proposal.principal_to_invoice)
    for row in proposal.evidence["refunds"]:
        legs[f"REFUND:{row['receipt']}"] = dict(kind="REFUND", method=row["method"],
            receipt_id=row["receipt"], amount=row["amount"])
    return legs


def inr_owner_workspace(closure):
    history, balance = inr_settlement_snapshot(closure.scheme_account)
    current = next((p for p in history if not p.retired and p.closure_id == closure.pk), None)
    remaining = []
    if current:
        fulfilled = {(f.kind, f.receipt_id) for f in current.fulfilments.all()}
        remaining = [leg for leg in fulfilment_legs(current).values()
            if (leg["kind"], leg["receipt_id"]) not in fulfilled]
    return dict(history=history, current=current, remaining=remaining,
        balance=balance)
