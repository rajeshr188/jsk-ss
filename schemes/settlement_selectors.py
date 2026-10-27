"""Configured full-settlement proof. Call under the agreement lock when mutating."""
import hashlib
import json
from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils import timezone

from schemes.payment_refund_selectors import unresolved_payment_events

from .models import ConfiguredSettlement, InstalmentReservation, PaymentWebhookEvent


def proof_digest(evidence):
    return hashlib.sha256(json.dumps(evidence, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def full_settlement_evidence(account, closure, *, benefit_invoice=None):
    from .closure_selectors import validate_closure_history
    from .instalments import AGREEMENT_TIMEZONE, has_monthly_instalments
    from .instalment_selectors import instalment_payment_ledger_summary, validated_instalment_periods
    from .selectors import get_metal_balance

    sequence = validate_closure_history(closure)
    if (not account.configuration_snapshot_id or closure.scheme_account_id != account.pk
        or closure.status != "ACCEPTED" or account.status not in ("ACTIVE", "REDEMPTION_ELIGIBLE", "CLOSURE_PENDING")):
        raise ValidationError("Full settlement requires an accepted configured closure on an open agreement.")
    account.full_clean()
    config = account.configuration_snapshot
    independent = None
    if account.agreement_schema_version == 2:
        from .plan_policies import require_operational_configuration
        from .independent_settlement_selectors import independent_closure_proof
        require_operational_configuration(config)
        independent = independent_closure_proof(account, closure, benefit_invoice)
    elif benefit_invoice is not None:
        raise ValidationError("Legacy settlement does not accept independent benefit invoices.")
    if config.accumulation != "EXACT_METAL" or (independent is None and config.benefit_policy != "NONE") or config.settlement_policy != "FULL_ONLY":
        raise ValidationError("Use a supported exact-metal full-only contract; legacy benefit settlement is not enabled.")
    payments = list(account.contributions.select_related("scheme_rate", "metal_allocation", "cash_receipt", "cash_reversal").order_by("pk"))
    orders = [p.gateway_order_id for p in payments if p.gateway_order_id]
    events = PaymentWebhookEvent.objects.filter(Q(contribution__in=payments) | Q(gateway_order_id__in=orders)).order_by("pk")
    if unresolved_payment_events(events).exists():
        raise ValidationError("Reconcile all linked provider events before full settlement.")
    facts = []
    from .payment_refund_selectors import is_refunded_order_retired
    for payment in payments:
        if payment.status == "ABANDONED" and is_refunded_order_retired(payment):
            continue  # Zero entitlement; retained separately in refunded_orders proof.
        # Local FAILED/ABANDONED/expiry is not provider cancellation. V1 deliberately
        # keeps these histories held; no owner checkbox can assert zero exposure.
        cash = payment.payment_channel == "IN_STORE_CASH" and payment.payment_gateway == "in_store_cash" and not payment.gateway_mode
        live = payment.payment_channel == "RAZORPAY" and payment.payment_gateway == "razorpay" and payment.gateway_mode == "live"
        if not (cash or live) or payment.status not in (("PAID", "REVERSED") if cash else ("PAID",)):
            raise ValidationError("Payment history needs resolution: pending, unallocated, test/practice, failed or abandoned attempts cannot enter full settlement.")
        payment.full_clean()
        allocation = getattr(payment, "metal_allocation", None)
        if (allocation is None or payment.scheme_rate_id is None or payment.rate_locked_at is None
            or allocation.metal_grade_id != account.metal_grade_id or allocation.metal != account.savings_mode
            or allocation.scheme_rate_id != payment.scheme_rate_id
            or payment.scheme_rate.metal_grade_id != account.metal_grade_id
            or payment.scheme_rate.rate_per_gram <= 0
            or allocation.quantity != (payment.amount / payment.scheme_rate.rate_per_gram).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)):
            raise ValidationError("Exact-grade allocation and locked-rate evidence require review.")
        if cash:
            if not hasattr(payment, "cash_receipt") or (payment.status == "REVERSED") != hasattr(payment, "cash_reversal"):
                raise ValidationError("Showroom receipt/correction evidence requires review.")
        elif not payment.gateway_order_id or not payment.gateway_reference:
            raise ValidationError("A verified Live order and payment identity are required.")
        facts.append(dict(id=payment.pk, status=payment.status, amount=str(payment.amount),
            allocation=allocation.pk, grams=str(allocation.quantity), grade=allocation.metal_grade_id,
            rate=allocation.scheme_rate_id, rate_value=str(payment.scheme_rate.rate_per_gram),
            order=payment.gateway_order_id, payment=payment.gateway_reference,
            reversal=payment.cash_reversal.pk if hasattr(payment, "cash_reversal") else None))
    redemptions = list(account.redemptions.select_related("reversal").order_by("pk"))
    for redemption in redemptions:
        if not hasattr(redemption, "configured_settlement") or not hasattr(redemption, "reversal"):
            raise ValidationError("Existing settlement history requires explicit review; no partial or legacy cutover is supplied.")
        validate_configured_settlement(redemption.configured_settlement)
    today = timezone.localdate(timezone=AGREEMENT_TIMEZONE)
    normal = independent["progress"]["state"] == "ELIGIBLE" if independent else today >= account.eligible_from
    monthly_proof = None
    if independent is None and has_monthly_instalments(account):
        periods = validated_instalment_periods(account)
        ledger = instalment_payment_ledger_summary(account_id=account.pk)
        if any(ledger[key] for key in ("integrity_errors", "review_required", "awaiting_timing", "order_requests_pending", "paid_unallocated", "unresolved_capture_events", "outage_held_accounts")):
            raise ValidationError("Instalment payment/outage evidence requires resolution before settlement.")
        claims = list(InstalmentReservation.objects.filter(period__scheme_account=account).order_by("pk").values("pk", "period_id", "state"))
        qualified_ids = {p["period_id"] for p in claims if p["state"] == "QUALIFIED"}
        qualified = [p for p in periods if p.pk in qualified_ids]
        normal = normal and len(qualified) == account.agreed_months and today >= max((p.ends_before for p in qualified), default=account.eligible_from)
        monthly_proof = dict(claims=claims, ledger=ledger, periods=[(p.pk, str(p.ends_before)) for p in periods])
    quantity = get_metal_balance(account)
    if quantity <= 0:
        raise ValidationError("A positive recorded entitlement is required; zero balance is not a settlement.")
    from .payment_refund_selectors import refund_disposition_evidence
    evidence = dict(version=1, account=account.pk, closure=str(closure.pk), sequence=sequence,
        **refund_disposition_evidence(account),
        configuration=account.configuration_snapshot_id, grade=account.metal_grade_id,
        quantity=format(quantity, ".6f"), basis="NORMAL" if normal else "EARLY", as_of=str(today),
        payments=facts, redemptions=[dict(id=r.pk, reversal=r.reversal.pk) for r in redemptions],
        webhooks=list(events.values("pk", "status", "event_type", "gateway_reference")), monthly=monthly_proof)
    if independent is not None:
        evidence["independent"] = independent
    return evidence


def validate_configured_settlement(settlement):
    """Validate retained source links, not a fresh permission to settle again."""
    r, event, evidence = settlement.redemption, settlement.event, settlement.evidence
    from .payment_refund_selectors import validate_retained_refund_disposition
    if isinstance(evidence, dict):
        validate_retained_refund_disposition(evidence, r.scheme_account)
    try:
        if not isinstance(evidence, dict) or type(evidence.get("sequence")) is not int:
            raise ValueError
        payments = evidence["payments"]
        if not isinstance(payments, list) or not payments:
            raise ValueError
        paid_quantity = sum((Decimal(p["grams"]) for p in payments if p["status"] == "PAID"), Decimal(0))
        if not paid_quantity.is_finite() or paid_quantity != r.entitlement_amount:
            raise ValueError
        if any(p["status"] not in ("PAID", "REVERSED") or p["grade"] != r.metal_grade_id for p in payments):
            raise ValueError
    except (KeyError, TypeError, ValueError, ArithmeticError):
        raise ValidationError("Configured settlement quantity evidence requires review.") from None
    if (not isinstance(evidence, dict) or proof_digest(evidence) != settlement.evidence_digest
        or settlement.closure.scheme_account_id != r.scheme_account_id
        or event.request_id != settlement.closure_id or event.action != "SETTLE"
        or event.resulting_status != "SETTLED" or event.actor_id != r.processed_by_id
        or event.authorization_reference != settlement.authorization_reference
        or event.reason != r.notes or event.idempotency_key != r.idempotency_key
        or event.sequence != evidence.get("sequence", -2) + 1
        or not settlement.authorization_reference.strip()
        or r.settlement_type != "JEWELLERY_PURCHASE" or not r.external_reference.strip()
        or evidence.get("version") != 1 or evidence.get("account") != r.scheme_account_id
        or evidence.get("closure") != str(settlement.closure_id) or evidence.get("grade") != r.metal_grade_id
        or evidence.get("configuration") != r.scheme_account.configuration_snapshot_id
        or r.metal_grade_id != r.scheme_account.metal_grade_id
        or evidence.get("quantity") != format(r.entitlement_amount, ".6f")
        or evidence.get("basis") != settlement.basis):
        raise ValidationError("Configured settlement evidence is inconsistent.")
    correction = getattr(settlement, "correction", None)
    if hasattr(r, "reversal") != (correction is not None):
        raise ValidationError("Configured reversal evidence is incomplete.")
    if correction and (correction.reversal.redemption_id != r.pk
        or correction.event.request_id != settlement.closure_id or correction.event.action != "REVERSE"
        or correction.event.resulting_status != "ACCEPTED" or correction.event.sequence != event.sequence + 1
        or correction.event.actor_id != correction.reversal.processed_by_id
        or correction.event.reason != correction.reversal.reason
        or not correction.event.authorization_reference.strip()):
        raise ValidationError("Configured reversal source links require review.")
