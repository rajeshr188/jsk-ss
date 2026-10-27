"""Strict, minimal provider evidence. No financial resolution authority lives here."""
from dataclasses import asdict, dataclass

from .payments import PaymentGatewayError, PaymentGatewayValidationError, RAZORPAY_ID_PATTERN


REFUND_PAGE_SIZE = 25
REFUND_MAX_PAGES = 10
PAYMENT_STATES = frozenset({"created", "authorized", "captured", "refunded", "failed"})
REFUND_STATES = frozenset({"pending", "processed", "failed"})


def _invalid():
    raise PaymentGatewayError("Razorpay refund evidence is incomplete or inconsistent; retain the payment for review.")


def _identifier(value, prefix):
    return (isinstance(value, str) and len(value) <= 120 and value.startswith(prefix)
            and len(value) > len(prefix) and RAZORPAY_ID_PATTERN.fullmatch(value))


def _integer(value, minimum=0):
    return type(value) is int and minimum <= value <= 99999999999999


@dataclass(frozen=True)
class RefundEvidence:
    refund_id: str
    payment_id: str
    amount_subunits: int
    currency: str
    status: str
    created_at: int


@dataclass(frozen=True)
class PaymentRefundInspection:
    payment_id: str
    order_id: str
    amount_subunits: int
    currency: str
    status: str
    captured: bool
    amount_refunded_subunits: int
    refund_status: str | None
    refunds: tuple[RefundEvidence, ...]

    @property
    def fully_refunded(self):
        # Provider completion, not independent confirmation of bank credit.
        return (self.status == "refunded" and self.captured is True
                and self.refund_status == "full"
                and self.amount_refunded_subunits == self.amount_subunits
                and bool(self.refunds)
                and all(r.status == "processed" for r in self.refunds)
                and sum(r.amount_subunits for r in self.refunds) == self.amount_subunits)

    def snapshot(self):
        snapshot = asdict(self)
        snapshot["refunds"] = [asdict(refund) for refund in self.refunds]
        return snapshot


def _payment(raw, payment_id):
    if not isinstance(raw, dict):
        _invalid()
    fields = dict(payment_id=raw.get("id"), order_id=raw.get("order_id"),
        amount_subunits=raw.get("amount"), currency=raw.get("currency"),
        status=raw.get("status"), captured=raw.get("captured"),
        amount_refunded_subunits=raw.get("amount_refunded"), refund_status=raw.get("refund_status"))
    if (raw.get("entity") != "payment" or fields["payment_id"] != payment_id
        or not _identifier(fields["order_id"], "order_")
        or not _integer(fields["amount_subunits"], 100)
        or fields["currency"] != "INR"
        or not isinstance(fields["status"], str) or fields["status"] not in PAYMENT_STATES
        or type(fields["captured"]) is not bool
        or not _integer(fields["amount_refunded_subunits"])
        or fields["amount_refunded_subunits"] > fields["amount_subunits"]
        or (fields["refund_status"] is not None and
            (not isinstance(fields["refund_status"], str) or fields["refund_status"] not in {"partial", "full"}))):
        _invalid()
    amount, refunded = fields["amount_subunits"], fields["amount_refunded_subunits"]
    expected_refund_status = "full" if refunded == amount else "partial" if refunded else None
    if (fields["refund_status"] != expected_refund_status
        or fields["captured"] != (fields["status"] in {"captured", "refunded"})
        or (refunded and not fields["captured"])
        or (fields["status"] == "refunded") != (refunded == amount)):
        _invalid()
    return fields


def _refund(raw, payment_id):
    if not isinstance(raw, dict):
        _invalid()
    if (raw.get("entity") != "refund" or not _identifier(raw.get("id"), "rfnd_")
        or raw.get("payment_id") != payment_id or raw.get("currency") != "INR"
        or not _integer(raw.get("amount"), 1)
        or not isinstance(raw.get("status"), str) or raw["status"] not in REFUND_STATES
        or not _integer(raw.get("created_at"), 1)):
        _invalid()
    return RefundEvidence(raw["id"], payment_id, raw["amount"], "INR", raw["status"], raw["created_at"])


def validate_snapshot(snapshot):
    """Round-trip stored evidence through exactly the provider validation boundary."""
    if not isinstance(snapshot, dict) or set(snapshot) != {
        "payment_id", "order_id", "amount_subunits", "currency", "status", "captured",
        "amount_refunded_subunits", "refund_status", "refunds",
    } or not _identifier(snapshot.get("payment_id"), "pay_"):
        _invalid()
    fields = _payment(dict(entity="payment", id=snapshot["payment_id"],
        order_id=snapshot["order_id"], amount=snapshot["amount_subunits"],
        currency=snapshot["currency"], status=snapshot["status"], captured=snapshot["captured"],
        amount_refunded=snapshot["amount_refunded_subunits"], refund_status=snapshot["refund_status"]),
        snapshot["payment_id"])
    if not isinstance(snapshot["refunds"], list) or len(snapshot["refunds"]) >= REFUND_PAGE_SIZE * REFUND_MAX_PAGES:
        _invalid()
    refunds = []
    for raw in snapshot["refunds"]:
        if not isinstance(raw, dict) or set(raw) != {"refund_id", "payment_id", "amount_subunits", "currency", "status", "created_at"}:
            _invalid()
        refunds.append(_refund(dict(entity="refund", id=raw["refund_id"], payment_id=raw["payment_id"],
            amount=raw["amount_subunits"], currency=raw["currency"], status=raw["status"], created_at=raw["created_at"]), fields["payment_id"]))
    if (len({r.refund_id for r in refunds}) != len(refunds)
        or sum(r.amount_subunits for r in refunds if r.status == "processed") != fields["amount_refunded_subunits"]
        or sum(r.amount_subunits for r in refunds if r.status != "failed") > fields["amount_subunits"]):
        _invalid()
    return PaymentRefundInspection(**fields, refunds=tuple(sorted(refunds, key=lambda r: r.refund_id)))


def inspect_payment_refunds(*, gateway, payment_id):
    if not _identifier(payment_id, "pay_"):
        raise PaymentGatewayValidationError("The Razorpay payment ID is invalid.")
    if gateway.name != "razorpay" or gateway.mode != "live":
        raise PaymentGatewayValidationError("Payment-error refund inspection requires the Live Razorpay gateway.")
    initial = _payment(gateway._request_json("GET", f"/payments/{payment_id}"), payment_id)
    refunds, seen = [], set()
    for page_number in range(REFUND_MAX_PAGES):
        page = gateway._request_json("GET", f"/payments/{payment_id}/refunds?count={REFUND_PAGE_SIZE}&skip={page_number * REFUND_PAGE_SIZE}")
        if (not isinstance(page, dict) or page.get("entity") != "collection"
            or type(page.get("count")) is not int or not isinstance(page.get("items"), list)
            or page["count"] != len(page["items"]) or not 0 <= page["count"] <= REFUND_PAGE_SIZE):
            _invalid()
        for item in page["items"]:
            refund = _refund(item, payment_id)
            if refund.refund_id in seen:
                _invalid()
            seen.add(refund.refund_id)
            refunds.append(refund)
        if page["count"] < REFUND_PAGE_SIZE:
            break
    else:
        _invalid()  # A full final page does not prove pagination exhaustion.
    final = _payment(gateway._request_json("GET", f"/payments/{payment_id}"), payment_id)
    if initial != final:
        _invalid()  # No mixed pre-/post-refund snapshot across a changing collection.
    return validate_snapshot(PaymentRefundInspection(**final, refunds=tuple(refunds)).snapshot())
