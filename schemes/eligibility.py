"""Exact-calendar eligibility policy for scheme agreements.

Eligibility is an entitlement date calculated in the India-local calendar. It is
not shifted for weekends, public holidays, showroom closure, payment schedules, or
payment-operation pauses. There is no early-redemption grace period and an eligible
agreement remains eligible until its entitlement is fully redeemed.
"""

import calendar
from datetime import date


def add_calendar_months(value: date, months: int) -> date:
    """Add calendar months, clamping to the destination month's final day."""

    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def calculate_eligibility_date(*, start_date: date, agreed_months: int) -> date:
    """Return the contractual eligibility date for a snapshotted agreement."""

    return add_calendar_months(start_date, agreed_months)


def is_redemption_eligible(*, eligible_from: date, as_of: date) -> bool:
    """Return whether the entitlement is eligible on the supplied local date."""

    return as_of >= eligible_from


def eligibility_days_until(*, eligible_from: date, as_of: date) -> int:
    """Return signed calendar days until eligibility (zero on the boundary)."""

    return (eligible_from - as_of).days
