from dataclasses import dataclass
from datetime import datetime, timedelta

from django.conf import settings
from django.utils import timezone

from .models import MetalGrade, PaymentOperationsControl, PaymentScheduleWindow
from .selectors import get_current_scheme_rate


@dataclass(frozen=True)
class PaymentAvailability:
    allowed: bool
    code: str
    message: str
    next_opening: datetime | None = None


OPEN = PaymentAvailability(
    allowed=True,
    code="OPEN",
    message="Online contributions are available.",
)


def _blocked(*, code, default_message, control=None, next_opening=None):
    message = (
        control.customer_message.strip()
        if control is not None and control.customer_message.strip()
        else default_message
    )
    return PaymentAvailability(
        allowed=False,
        code=code,
        message=message,
        next_opening=next_opening,
    )


def _next_scheduled_opening(*, windows, local_now):
    by_weekday = {window.weekday: window for window in windows if window.enabled}
    current_time = local_now.time().replace(tzinfo=None)
    for days_ahead in range(8):
        candidate_date = local_now.date() + timedelta(days=days_ahead)
        window = by_weekday.get(candidate_date.weekday())
        if window is None:
            continue
        if days_ahead == 0 and current_time < window.opens_at:
            candidate_time = window.opens_at
        elif days_ahead == 0:
            continue
        else:
            candidate_time = window.opens_at
        naive = datetime.combine(candidate_date, candidate_time)
        return timezone.make_aware(naive, timezone.get_current_timezone())
    return None


def get_payment_availability(*, metal_grade, at=None, lock=False):
    if metal_grade is None or metal_grade.metal not in MetalGrade.Metal.values:
        return _blocked(
            code="UNSUPPORTED_SAVINGS_MODE",
            default_message="Online contributions are unavailable for this savings mode.",
        )
    if settings.PAYMENT_INITIATION_KILL_SWITCH:
        return _blocked(
            code="ENVIRONMENT_KILL_SWITCH",
            default_message=(
                "Online contributions are temporarily paused. Please contact the "
                "showroom if you need assistance."
            ),
        )

    controls = PaymentOperationsControl.objects.prefetch_related("schedule_windows")
    if lock:
        controls = controls.select_for_update()
    try:
        control = controls.get(pk=PaymentOperationsControl.SINGLETON_PK)
    except PaymentOperationsControl.DoesNotExist:
        return _blocked(
            code="CONTROL_UNAVAILABLE",
            default_message="Online contributions are temporarily unavailable.",
        )

    if control.global_pause:
        return _blocked(
            code="MANUAL_GLOBAL_PAUSE",
            default_message="Online contributions are temporarily paused.",
            control=control,
        )
    metal = metal_grade.metal
    if metal == MetalGrade.Metal.GOLD and control.gold_pause:
        return _blocked(
            code="MANUAL_METAL_PAUSE",
            default_message="Gold contributions are temporarily paused.",
            control=control,
        )
    if metal == MetalGrade.Metal.SILVER and control.silver_pause:
        return _blocked(
            code="MANUAL_METAL_PAUSE",
            default_message="Silver contributions are temporarily paused.",
            control=control,
        )

    current_time = at or timezone.now()
    if timezone.is_naive(current_time):
        current_time = timezone.make_aware(
            current_time,
            timezone.get_current_timezone(),
        )
    local_now = timezone.localtime(current_time)
    windows = list(control.schedule_windows.all())
    if control.schedule_enabled:
        window = next(
            (item for item in windows if item.weekday == local_now.weekday()),
            None,
        )
        local_clock = local_now.time().replace(tzinfo=None)
        if (
            window is None
            or not window.enabled
            or not (window.opens_at <= local_clock < window.closes_at)
        ):
            return _blocked(
                code="OUTSIDE_BUSINESS_HOURS",
                default_message="Online contributions are closed outside business hours.",
                control=control,
                next_opening=_next_scheduled_opening(
                    windows=windows,
                    local_now=local_now,
                ),
            )

    scheme_rate = get_current_scheme_rate(metal_grade, at=current_time)
    if scheme_rate is None:
        return _blocked(
            code="RATE_UNAVAILABLE",
            default_message=(
                "Online contributions are unavailable because the current Scheme "
                "Rate has not been published."
            ),
            control=control,
        )
    if (
        control.schedule_enabled
        and control.require_current_day_rate
        and timezone.localdate(scheme_rate.published_at) != local_now.date()
    ):
        return _blocked(
            code="RATE_REVIEW_REQUIRED",
            default_message=(
                "Online contributions will reopen after today's Scheme Rate is "
                "reviewed and published."
            ),
            control=control,
        )
    return OPEN


def payment_operations_snapshot(control):
    windows = control.schedule_windows.all().order_by("weekday")
    return {
        "schedule_enabled": control.schedule_enabled,
        "require_current_day_rate": control.require_current_day_rate,
        "global_pause": control.global_pause,
        "gold_pause": control.gold_pause,
        "silver_pause": control.silver_pause,
        "customer_message": control.customer_message,
        "schedule": [
            {
                "weekday": window.weekday,
                "enabled": window.enabled,
                "opens_at": window.opens_at.isoformat(timespec="minutes"),
                "closes_at": window.closes_at.isoformat(timespec="minutes"),
            }
            for window in windows
        ],
    }
