"""Approved monthly schedule foundation. No payment or eligibility mutation.

Periods are denomination-independent. Structural schedule/attribution support does
not activate schema-2 enrolment or payments. Outage mutations use separate services.
Do not treat paid_at (local confirmation time) as proof of provider capture time.
"""
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.core.exceptions import ValidationError
from django.db import transaction

from .eligibility import add_calendar_months

AGREEMENT_TIMEZONE = ZoneInfo("Asia/Kolkata")


def has_monthly_instalments(account):
    return bool(account.configuration_snapshot_id and
        account.configuration_snapshot.instalment_policy == "MONTHLY_COMPLETION")


@dataclass(frozen=True)
class InstalmentWindow:
    number: int
    starts_on: date
    ends_before: date
    amount: Decimal
    extension: bool


def period_boundary(configuration, start_date, index):
    """Immutable policy boundary; calendar period zero starts on enrolment day."""
    if configuration.period_basis == "CALENDAR_MONTH":
        return start_date if index == 0 else add_calendar_months(start_date.replace(day=1), index)
    if configuration.period_basis == "ANNIVERSARY":
        return add_calendar_months(start_date, index)
    raise ValidationError("Unsupported monthly period basis.")


def build_instalment_windows(*, configuration, start_date, agreed_months, amount):
    """Half-open India-local windows; no change to the minimum-duration date."""
    from .plan_configuration import validate_configuration_amount
    from .plan_policies import require_operational_configuration

    configuration.full_clean()
    require_operational_configuration(configuration)
    if configuration.instalment_policy != "MONTHLY_COMPLETION":
        raise ValidationError("This configuration has no required monthly schedule.")
    if type(start_date) is not date or type(agreed_months) is not int:
        raise ValidationError("Use a calendar start date and whole-month duration.")
    if not configuration.minimum_months <= agreed_months <= 32767:
        raise ValidationError("The duration is outside the configuration's permitted range.")
    selected = validate_configuration_amount(configuration, amount)
    count = agreed_months + configuration.max_extension_months
    try:
        # Validate the end before allocating a potentially long schedule.
        period_boundary(configuration, start_date, count)
        return tuple(InstalmentWindow(
            number=index + 1, starts_on=period_boundary(configuration, start_date, index),
            ends_before=period_boundary(configuration, start_date, index + 1), amount=selected,
            extension=index >= agreed_months,
        ) for index in range(count))
    except (ValueError, OverflowError):
        raise ValidationError("The proposed schedule exceeds supported calendar dates.") from None


def window_for_instant(windows, occurred_at):
    """Map an aware instant, without claiming that it is verified payment evidence."""
    if not isinstance(occurred_at, datetime) or occurred_at.utcoffset() is None:
        raise ValidationError("An aware, evidenced payment timestamp is required.")
    local_day = occurred_at.astimezone(AGREEMENT_TIMEZONE).date()
    return next((window for window in windows if window.starts_on <= local_day < window.ends_before), None)


def preview_monthly_completion(*, configuration, start_date, agreed_months, amount, missed_periods=()):
    """Owner scenario only: assume one payment in each non-missed period.

    This neither reads actual payments nor grants eligibility. No outage is inferred,
    no obligation is marked missed, and no money/rates/grams are created or changed.
    """
    windows = build_instalment_windows(configuration=configuration, start_date=start_date,
        agreed_months=agreed_months, amount=amount)
    if not isinstance(missed_periods, (tuple, list, set, frozenset)) or any(
        type(number) is not int or number < 1 or number > len(windows) for number in missed_periods
    ):
        raise ValidationError("Missed periods must be whole period numbers within this schedule.")
    missed = set(missed_periods)
    paid = 0
    completion = None
    rows = []
    for window in windows:
        needed = paid < agreed_months
        assumed_paid = needed and window.number not in missed
        if assumed_paid:
            paid += 1
        if paid == agreed_months and completion is None:
            completion = max(add_calendar_months(start_date, agreed_months), window.ends_before)
        rows.append({"window": window, "outcome": (
            "Not needed" if not needed else "Assumed missed" if not assumed_paid else "Assumed paid"
        )})
    return {
        "rows": rows[:60], "omitted_rows": max(0, len(rows) - 60),
        "required_payments": agreed_months, "assumed_payments": paid,
        "original_date": add_calendar_months(start_date, agreed_months),
        "projected_completion": completion, "review_after": windows[-1].ends_before,
        "review_required": completion is None, "preview_only": True,
    }


def expected_account_windows(account):
    from .plan_configuration import validate_agreement_configuration

    validate_agreement_configuration(account)
    if not account.configuration_snapshot_id:
        raise ValidationError("Existing agreements must not acquire new instalment obligations.")
    if account.agreement_schema_version == 2:
        from .agreement_contracts import resolve_independent_agreement_schedule
        if not has_monthly_instalments(account):
            raise ValidationError("Optional payment ceilings must not create required instalment periods.")
        return resolve_independent_agreement_schedule(
            configuration_id=account.configuration_snapshot_id, start_date=account.start_date,
            selected_amount=account.fixed_amount_snapshot, metal_grade_id=account.metal_grade_id).windows
    return build_instalment_windows(configuration=account.configuration_snapshot,
        start_date=account.start_date, agreed_months=account.agreed_months, amount=account.fixed_amount_snapshot)


def compensation_window(account, number):
    """V1 amendment allowance: three months, SEPARATE from ordinary extensions."""
    if account.agreement_schema_version == 2:
        raise ValidationError("Independent agreement outage compensation is not yet integrated.")
    base = expected_account_windows(account)
    if type(number) is not int or not 1 <= number <= 3:
        raise ValidationError("An agreement permits at most three outage-compensation months.")
    index = len(base) + number - 1
    try:
        return InstalmentWindow(number=index + 1,
            starts_on=period_boundary(account.configuration_snapshot, account.start_date, index),
            ends_before=period_boundary(account.configuration_snapshot, account.start_date, index + 1),
            amount=base[0].amount, extension=True)
    except (ValueError, OverflowError):
        raise ValidationError("The compensation exceeds supported calendar dates.") from None


def effective_account_windows(account):
    """Original schedule plus individually acknowledged, append-only amendments."""
    base = expected_account_windows(account)
    if account.agreement_schema_version == 2:
        if account.outage_resolutions.exists():
            raise ValidationError("Independent agreement outage resolutions require review.")
        return base
    amendments = list(account.outage_resolutions.filter(outcome="COMPENSATE").select_related(
        "hold", "period", "compensation_period").order_by("compensation_number"))
    for number, amendment in enumerate(amendments, 1):
        if amendment.compensation_number != number:
            raise ValidationError("Outage compensation sequence requires review.")
        amendment.full_clean()
    return base + tuple(compensation_window(account, amendment.compensation_number) for amendment in amendments)


def required_instalment_count(account):
    """Read the validated frozen count, never infer schema-2 count from duration."""
    from .plan_configuration import validate_agreement_configuration
    validate_agreement_configuration(account)
    if not has_monthly_instalments(account):
        raise ValidationError("This agreement has no required instalment count.")
    return account.required_count_snapshot if account.agreement_schema_version == 2 else account.agreed_months


def validate_real_instalment_channel(contribution):
    if not (
        (contribution.payment_gateway == "razorpay" and contribution.payment_channel == "RAZORPAY" and contribution.gateway_mode == "live")
        or (contribution.payment_gateway == "in_store_cash" and contribution.payment_channel == "IN_STORE_CASH" and not contribution.gateway_mode)
    ):
        raise ValidationError("Only live Razorpay or recorded showroom cash can qualify real instalments.")


@transaction.atomic
def prepare_instalment_periods(*, account_id, actor, reason):
    """Create the accepted schedule atomically at enrolment, not a public bypass.

    Lock the agreement for idempotency. Never repair partial/corrupt schedules by
    overwriting history. Existing-style agreements are explicitly rejected.
    """
    from .models import SchemeAccount, SchemeInstalmentPeriod
    from .services import _actor_label, _validate_owner

    _validate_owner(actor)
    if not isinstance(reason, str) or not reason.strip():
        raise ValidationError("A schedule preparation reason is required.")
    account = SchemeAccount.objects.select_for_update().get(pk=account_id)
    expected = effective_account_windows(account)
    existing = list(account.instalment_periods.order_by("number"))
    if existing:
        if len(existing) != len(expected) or any(
            (row.number, row.starts_on, row.ends_before, row.amount)
            != (window.number, window.starts_on, window.ends_before, window.amount)
            for row, window in zip(existing, expected)
        ):
            raise ValidationError("The recorded schedule requires review; no periods were changed.")
        return existing
    if account.agreement_schema_version == 2 and (
        account.status != "ACTIVE" or account.contributions.exists()
    ):
        raise ValidationError("Record the independent schedule at enrolment, before any contributions; no backfill is allowed.")
    # Validated complete snapshot; insertion is atomic and bounded by the frozen policy.
    return SchemeInstalmentPeriod.objects.bulk_create([
        SchemeInstalmentPeriod(scheme_account=account, number=window.number,
            starts_on=window.starts_on, ends_before=window.ends_before, amount=window.amount,
            created_by=actor, actor_label=_actor_label(actor), reason=reason.strip())
        for window in expected
    ])
