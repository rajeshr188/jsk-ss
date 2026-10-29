"""Conservative all-attempt read proof for retiring a fully refunded Live order."""
from .payment_refund_evidence import _identifier, _integer, _payment
from .payments import PaymentGatewayError, PaymentGatewayValidationError


def _invalid():
    raise PaymentGatewayError("The refunded order is not fully reconciled; retain its payment hold.")


def _order(raw, order_id):
    if not isinstance(raw, dict):
        _invalid()
    fields = {k: raw.get(k) for k in ("id", "amount", "amount_paid", "amount_due", "currency", "status", "attempts")}
    if (raw.get("entity") != "order" or fields["id"] != order_id
        or not _identifier(order_id, "order_") or fields["currency"] != "INR"
        or fields["status"] != "paid" or not _integer(fields["amount"], 100)
        or not _integer(fields["amount_paid"], 100) or not _integer(fields["amount_due"])
        or fields["amount_paid"] != fields["amount"] or fields["amount_due"] != 0
        or type(fields["attempts"]) is not int or not 1 <= fields["attempts"] <= 100):
        _invalid()
    return fields


def validate_order_snapshot(snapshot):
    if not isinstance(snapshot, dict) or set(snapshot) != {"order", "payments"}:
        _invalid()
    order, payments = snapshot["order"], snapshot["payments"]
    if not isinstance(order, dict) or set(order) != {"id", "amount", "amount_paid", "amount_due", "currency", "status", "attempts"}:
        _invalid()
    _order(dict(entity="order", **order), order["id"])
    if not isinstance(payments, list) or len(payments) != order["attempts"]:
        _invalid()
    seen, refunded = set(), 0
    for p in payments:
        if not isinstance(p, dict) or set(p) != {"payment_id", "order_id", "amount_subunits", "currency",
                "status", "captured", "amount_refunded_subunits", "refund_status"}:
            _invalid()
        if not _identifier(p["payment_id"], "pay_") or p["payment_id"] in seen:
            _invalid()
        _payment(dict(entity="payment", id=p["payment_id"], order_id=p["order_id"], amount=p["amount_subunits"],
            currency=p["currency"], status=p["status"], captured=p["captured"],
            amount_refunded=p["amount_refunded_subunits"], refund_status=p["refund_status"]), p["payment_id"])
        if p["order_id"] != order["id"] or p["amount_subunits"] != order["amount"] or p["status"] not in {"failed", "refunded"}:
            _invalid()
        seen.add(p["payment_id"])
        refunded += p["amount_refunded_subunits"]
    if refunded != order["amount_paid"]:
        _invalid()
    return snapshot


def inspect_refunded_order(*, gateway, order_id):
    if gateway.name != "razorpay" or gateway.mode != "live" or not _identifier(order_id, "order_"):
        raise PaymentGatewayValidationError("Refunded-order inspection requires an exact Live order.")
    before = _order(gateway._request_json("GET", f"/orders/{order_id}"), order_id)
    collection = gateway._request_json("GET", f"/orders/{order_id}/payments")
    if (not isinstance(collection, dict) or collection.get("entity") != "collection"
        or type(collection.get("count")) is not int or not isinstance(collection.get("items"), list)
        or collection["count"] != len(collection["items"]) or collection["count"] != before["attempts"]):
        _invalid()
    payments = [_payment(p, p.get("id") if isinstance(p, dict) else None) for p in collection["items"]]
    after = _order(gateway._request_json("GET", f"/orders/{order_id}"), order_id)
    if before != after:
        _invalid()
    return validate_order_snapshot(dict(order=after, payments=sorted(payments, key=lambda p: p["payment_id"])))
