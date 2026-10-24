"""Purchase-credit principal reads. No legacy cash bonus, grams or settlement inference."""
from dataclasses import dataclass
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import Contribution, InrPrincipalReceipt, MetalAllocation, SchemeAccount
from .agreement_contracts import validate_independent_account_terms


def validate_inr_contract(account):
    if (account.savings_mode != "INR_CREDIT" or account.metal_grade_id is not None
            or not account.configuration_snapshot_id):
        raise ValidationError("A separate schema-2 INR purchase-credit contract is required.")
    validate_independent_account_terms(account)


def validate_principal_receipt(receipt):
    account = receipt.scheme_account
    contribution = receipt.contribution
    validate_inr_contract(account)
    if (receipt.configuration_id != account.configuration_snapshot_id
            or contribution.scheme_account_id != account.pk
            or receipt.amount != contribution.amount
            or receipt.source_reference != contribution.gateway_reference
            or receipt.verified_at != contribution.paid_at or not contribution.paid_at
            or contribution.paid_at > timezone.now()
            or contribution.scheme_rate_id is not None or contribution.rate_locked_at is not None
            or MetalAllocation.objects.filter(contribution=contribution).exists()):
        raise ValidationError("Principal/source/contract evidence differs or contains metal accounting.")
    if receipt.cash_receipt_id and not receipt.webhook_event_id:
        cash = receipt.cash_receipt
        if (contribution.payment_channel != "IN_STORE_CASH" or contribution.payment_gateway != "in_store_cash"
                or contribution.gateway_mode or contribution.gateway_order_id
                or contribution.status not in ("PAID", "REVERSED")
                or cash.contribution_id != contribution.pk or cash.receipt_reference != receipt.source_reference
                or cash.received_at != receipt.verified_at or not cash.received_by_label.strip()):
            raise ValidationError("A matching actual in-store cash receipt is required.")
    elif receipt.webhook_event_id and not receipt.cash_receipt_id:
        event = receipt.webhook_event
        if (contribution.payment_channel != "RAZORPAY" or contribution.payment_gateway != "razorpay"
                or contribution.gateway_mode != "live" or contribution.status != "PAID"
                or not contribution.gateway_order_id
                or event.contribution_id != contribution.pk or event.gateway != "razorpay"
                or event.gateway_mode != "live" or event.status != "PROCESSED"
                or event.event_type != "payment.captured" or not event.processed_at
                or event.gateway_order_id != contribution.gateway_order_id
                or event.gateway_reference != contribution.gateway_reference
                or len(event.payload_sha256) != 64
                or any(char not in "0123456789abcdefABCDEF" for char in event.payload_sha256)):
            raise ValidationError("A processed matching live capture is required; test/mock payments do not create principal.")
    else:
        raise ValidationError("Exactly one verified principal source is required.")


def validate_principal_correction(correction):
    receipt = correction.receipt
    validate_principal_receipt(receipt)
    reversal = correction.cash_reversal
    if (not receipt.cash_receipt_id or reversal.contribution_id != receipt.contribution_id
            or receipt.contribution.status != "REVERSED"
            or reversal.reversed_at < receipt.verified_at or reversal.reversed_at > timezone.now()
            or not reversal.reason.strip() or not reversal.processed_by_label.strip()):
        raise ValidationError("A matching completed cash-entry reversal is required, not a refund promise.")


@dataclass(frozen=True)
class InrPrincipalSummary:
    received: Decimal
    corrected: Decimal
    principal_recorded: Decimal
    unrecorded_sources: int
    source_errors: int

    @property
    def needs_review(self):
        return bool(self.unrecorded_sources or self.source_errors)


def get_inr_principal_summary(account):
    """Retain ledger liability despite source drift; flag it, never silently erase it.

    This is gross source accounting, not spendable balance. Manual final-settlement
    discharges and pending refunds are projected by inr_settlement_balance separately.
    """
    validate_inr_contract(account)
    received = corrected = Decimal("0.00")
    errors = 0
    receipts = InrPrincipalReceipt.objects.filter(scheme_account=account).select_related(
        "scheme_account__configuration_snapshot", "scheme_account__plan_revision", "configuration",
        "contribution", "cash_receipt", "webhook_event", "correction__cash_reversal")
    for receipt in receipts:
        received += receipt.amount
        correction = getattr(receipt, "correction", None)
        if correction:
            corrected += receipt.amount
        try:
            validate_principal_receipt(receipt)
            if correction:
                validate_principal_correction(correction)
            elif receipt.contribution.status == "REVERSED":
                errors += 1
        except ValidationError:
            errors += 1
    sources = account.contributions.filter(status__in=["PAID", "PAID_UNALLOCATED", "REVERSED"])
    # A receipt attached to another agreement is not proof this agreement was credited.
    missing = sources.filter(payment_channel="IN_STORE_CASH").exclude(
        pk__in=receipts.values("contribution_id")).count()
    missing += sources.filter(payment_channel="RAZORPAY", gateway_mode="live").exclude(
        pk__in=receipts.values("contribution_id")).count()
    return InrPrincipalSummary(received, corrected, received - corrected, missing, errors)


def get_inr_recorded_principal_total():
    if InrPrincipalReceipt.objects.exclude(scheme_account__savings_mode="INR_CREDIT").exists():
        raise ValidationError("INR receipt denomination requires reconciliation.")
    total = Decimal("0.00")
    for account in SchemeAccount.objects.filter(savings_mode="INR_CREDIT").select_related(
            "configuration_snapshot", "plan_revision"):
        summary = get_inr_principal_summary(account)
        if summary.needs_review:
            raise ValidationError("INR principal requires reconciliation; do not report an incomplete liability.")
        from .inr_settlement_selectors import inr_settlement_balance
        total += inr_settlement_balance(account).outstanding
    return total
