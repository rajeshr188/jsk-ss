from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from django.core.exceptions import ValidationError


CASH_BONUS_POLICY_VERSION = "CASH-BONUS-V1"
MONEY_QUANTUM = Decimal("0.01")
PERCENT_DIVISOR = Decimal("100")


@dataclass(frozen=True)
class CashBonusPolicy:
    version: str
    percentage: Decimal
    minimum_qualifying_months: int

    def __post_init__(self):
        if self.version != CASH_BONUS_POLICY_VERSION:
            raise ValidationError(
                f"Unsupported cash bonus policy version: {self.version}."
            )
        if self.percentage < 0 or self.percentage > 100:
            raise ValidationError("Cash bonus percentage must be between 0 and 100.")
        if self.minimum_qualifying_months < 12:
            raise ValidationError(
                "Cash bonus qualifying duration must be at least 12 months."
            )

    def contract_qualifies(self, agreed_months):
        return self.percentage > 0 and agreed_months >= self.minimum_qualifying_months

    def calculate(self, principal):
        if principal <= 0 or self.percentage <= 0:
            return Decimal("0.00")
        return (principal * self.percentage / PERCENT_DIVISOR).quantize(
            MONEY_QUANTUM,
            rounding=ROUND_HALF_UP,
        )


def cash_bonus_policy_for_account(scheme_account):
    return CashBonusPolicy(
        version=scheme_account.cash_bonus_policy_version_snapshot,
        percentage=scheme_account.cash_bonus_percentage_snapshot,
        minimum_qualifying_months=scheme_account.cash_bonus_minimum_months_snapshot,
    )
