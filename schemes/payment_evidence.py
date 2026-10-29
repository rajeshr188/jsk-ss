"""Read-only checks for previously authenticated, processed capture evidence."""
import hashlib
import json

from django.core.exceptions import ValidationError


def validated_capture_payload(*, event, contribution, body):
    """Internal consumer only: this does NOT authenticate a webhook signature."""
    if (event.status != "PROCESSED" or event.event_type != "payment.captured"
            or event.gateway != "razorpay" or event.gateway_mode != "live"
            or event.contribution_id != contribution.pk
            or contribution.payment_channel != "RAZORPAY" or contribution.payment_gateway != "razorpay"
            or contribution.gateway_mode != "live" or contribution.status not in ("PAID", "PAID_UNALLOCATED")
            or not isinstance(body, bytes) or hashlib.sha256(body).hexdigest() != event.payload_sha256):
        raise ValidationError("Processed live capture evidence with its original body is required.")
    try:
        payload = json.loads(body)
        payment = payload["payload"]["payment"]["entity"]
        valid = (payload["event"] == "payment.captured"
            and isinstance(payment["id"], str) and bool(payment["id"])
            and isinstance(payment["order_id"], str) and bool(payment["order_id"])
            and payment["id"] == contribution.gateway_reference == event.gateway_reference
            and payment["order_id"] == contribution.gateway_order_id == event.gateway_order_id
            and payment["status"] == "captured" and payment["captured"] is True
            and payment["currency"] == "INR" and type(payment["amount"]) is int
            and payment["amount"] == contribution.amount * 100)
    except (KeyError, TypeError, ValueError):
        valid = False
    if not valid:
        raise ValidationError("Capture payload and verified contribution do not match.")
    return payload, payment
