"""Configured purchase-benefit arithmetic, separate from legacy cash bonuses.

These pure calculations create no award, invoice discount, refund or liability.
The calculation version/inputs must be retained by the future award/fulfilment record.
"""
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP, localcontext

from django.core.exceptions import ValidationError


BENEFIT_CALCULATION_VERSION = "PURCHASE_BENEFIT_V1"
BENEFIT_ROUNDING_RULE = "PAISE_HALF_UP_ONCE"
MAX_MONEY = Decimal("999999999999.99")


def _decimal(value, name, *, maximum=MAX_MONEY, positive=False):
    if (not isinstance(value, Decimal) or not value.is_finite()
            or value < 0 or (positive and value == 0) or value > maximum
            or value.as_tuple().exponent < -2):
        raise ValidationError(f"{name} must be a finite {'positive' if positive else 'non-negative'} Decimal within range, with at most two decimal places.")
    return value


@dataclass(frozen=True, kw_only=True)
class BenefitCalculation:
    kind: str
    base: Decimal
    percentage: Decimal
    cap: Decimal
    amount: Decimal
    version: str = BENEFIT_CALCULATION_VERSION
    rounding_rule: str = BENEFIT_ROUNDING_RULE


def _calculate(kind, base, percentage, cap):
    _decimal(base, "Qualifying base")
    _decimal(percentage, "Benefit percentage", maximum=Decimal("100"), positive=True)
    _decimal(cap, "Benefit cap", positive=True)
    # Independent of a caller's ambient Decimal precision/rounding. All accepted
    # inputs fit this context; round once, after applying the explicit INR cap.
    with localcontext() as context:
        context.prec = 38
        amount = min(base * percentage / Decimal("100"), cap).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP)
    return BenefitCalculation(kind=kind, base=base, percentage=percentage, cap=cap, amount=amount)


def calculate_purchase_bonus(*, qualifying_principal, percentage, cap):
    """INR purchase-only bonus, never legacy cash interest or extra metal."""
    return _calculate("INR_PURCHASE_BONUS", qualifying_principal, percentage, cap)


def calculate_va_discount(*, eligible_charges, invoice_payable, percentage, cap):
    """Only evidenced eligible charges, not principal/metal or the whole invoice.

    The caller must separately retain invoice identity, eligible-charge evidence and
    one-time consumption. A pure calculation cannot establish that evidence.
    """
    _decimal(invoice_payable, "Invoice payable")
    _decimal(eligible_charges, "Eligible charges")
    if eligible_charges > invoice_payable:
        raise ValidationError("Eligible charges cannot exceed the evidenced invoice payable.")
    return _calculate("VA_DISCOUNT", eligible_charges, percentage, cap)
