import calendar
import hashlib
import secrets
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from accounts.services import issue_customer_invitation

from .bonuses import CASH_BONUS_POLICY_VERSION
from .models import (
    AuditEvent,
    Contribution,
    Customer,
    GatewayMode,
    MetalAllocation,
    PaymentOperationsControl,
    PaymentScheduleWindow,
    PaymentWebhookEvent,
    WebhookProcessingAttempt,
    SchemeRate,
    Redemption,
    RedemptionReversal,
    SchemeAccount,
    SchemePlan,
)
from .operations import get_payment_availability, payment_operations_snapshot
from .payments import (
    PaymentGatewayError,
    PaymentInspection,
    PaymentOrderInspection,
    get_payment_gateway,
)
from .selectors import (
    get_cash_bonus_summary,
    get_current_scheme_rate,
    get_outstanding_entitlement,
)


MONEY_QUANTUM = Decimal("0.01")
METAL_QUANTUM = Decimal("0.000001")
SUCCESSFUL_PAYMENT_STATUSES = (
    Contribution.Status.PAID,
    Contribution.Status.PAID_UNALLOCATED,
)
EXPECTED_ALLOCATION_ERRORS = (ValidationError,)
SCHEME_RATE_PURITY = {
    SchemeRate.Metal.GOLD: Decimal("0.9999"),
    SchemeRate.Metal.SILVER: Decimal("0.9990"),
}
CASH_SCHEME_ACTIVITY_UNAVAILABLE = (
    "Cash savings are closed to new activity. Choose a gold or silver savings mode."
)


@dataclass(frozen=True)
class RazorpayOrderReconciliationResult:
    contribution: Contribution
    inspection: PaymentOrderInspection
    outcome: str
    applied: bool


@dataclass(frozen=True)
class RazorpayWebhookRecoveryResult:
    webhook_event: PaymentWebhookEvent
    contribution: Contribution | None
    inspection: PaymentInspection | None
    outcome: str
    applied: bool


class WebhookTransientProcessingError(Exception):
    """A signed delivery could not be durably consumed and should be retried."""


class _WebhookReviewRequired(Exception):
    def __init__(self, code, detail):
        self.code = code
        self.detail = detail
        super().__init__(detail)


def cash_scheme_activity_is_enabled():
    """Retain CASH workflows only for local historical regression coverage."""
    return settings.DEBUG


def _actor_label(actor):
    if actor is None:
        return "System service"
    return actor.email or actor.username or f"User {actor.pk}"


def _validate_owner(actor):
    user_model = get_user_model()
    if actor is None or not actor.is_active or not (
        actor.is_superuser or actor.role == user_model.Role.OWNER
    ):
        raise ValidationError("Only an active owner can perform this action.")


def record_audit_event(*, action, reason, actor=None, **targets):
    normalized_reason = reason.strip()
    if not normalized_reason:
        raise ValidationError({"reason": "Enter a reason for this action."})
    event = AuditEvent(
        action=action,
        actor=actor,
        actor_label=_actor_label(actor),
        reason=normalized_reason,
        **targets,
    )
    event.full_clean()
    event.save()
    return event


def ensure_payment_initiation_allowed(*, metal, at=None, lock=False):
    if metal not in {SchemeRate.Metal.GOLD, SchemeRate.Metal.SILVER}:
        return
    availability = get_payment_availability(metal=metal, at=at, lock=lock)
    if not availability.allowed:
        raise ValidationError(availability.message)


@transaction.atomic
def update_payment_operations_control(
    *,
    actor,
    reason,
    schedule_enabled,
    require_current_day_rate,
    global_pause,
    gold_pause,
    silver_pause,
    customer_message,
    schedule,
):
    _validate_owner(actor)
    normalized_reason = reason.strip()
    if not normalized_reason:
        raise ValidationError({"reason": "Enter a reason for this change."})
    expected_weekdays = set(PaymentScheduleWindow.Weekday.values)
    if set(schedule) != expected_weekdays:
        raise ValidationError("Provide exactly one payment window for each weekday.")

    control = (
        PaymentOperationsControl.objects.select_for_update()
        .prefetch_related("schedule_windows")
        .get(pk=PaymentOperationsControl.SINGLETON_PK)
    )
    before = payment_operations_snapshot(control)
    control.schedule_enabled = schedule_enabled
    control.require_current_day_rate = require_current_day_rate
    control.global_pause = global_pause
    control.gold_pause = gold_pause
    control.silver_pause = silver_pause
    control.customer_message = customer_message.strip()
    control.updated_by = actor
    control.full_clean()
    control.save()

    existing = {
        window.weekday: window
        for window in PaymentScheduleWindow.objects.select_for_update().filter(
            control=control
        )
    }
    if set(existing) != expected_weekdays:
        raise ValidationError(
            "The stored payment schedule must contain exactly one window for each "
            "weekday."
        )
    for weekday, values in schedule.items():
        window = existing[weekday]
        window.enabled = values["enabled"]
        window.opens_at = values["opens_at"]
        window.closes_at = values["closes_at"]
        window.full_clean()
        window.save(update_fields=["enabled", "opens_at", "closes_at"])

    control = PaymentOperationsControl.objects.prefetch_related(
        "schedule_windows"
    ).get(pk=control.pk)
    after = payment_operations_snapshot(control)
    if before == after:
        raise ValidationError("Change at least one payment operations setting.")
    record_audit_event(
        action=AuditEvent.Action.PAYMENT_OPERATIONS_CHANGE,
        actor=actor,
        reason=normalized_reason,
        details={"before": before, "after": after},
    )
    return control


@transaction.atomic
def publish_scheme_rate(
    *, metal, rate_per_gram, published_by, notes="", effective_from=None
):
    _validate_owner(published_by)
    if metal not in SCHEME_RATE_PURITY:
        raise ValidationError({"metal": "Select gold or silver."})
    try:
        normalized_rate = Decimal(str(rate_per_gram))
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError({"rate_per_gram": "Enter a valid scheme rate."}) from None
    if not normalized_rate.is_finite() or normalized_rate <= 0:
        raise ValidationError(
            {"rate_per_gram": "Scheme rate must be greater than zero."}
        )

    effective_from = effective_from or timezone.now()
    if timezone.is_naive(effective_from):
        effective_from = timezone.make_aware(
            effective_from, timezone.get_current_timezone()
        )
    scheme_rate = SchemeRate(
        metal=metal,
        rate_per_gram=normalized_rate,
        purity=SCHEME_RATE_PURITY[metal],
        effective_from=effective_from,
        published_by=published_by,
        notes=notes.strip(),
    )
    scheme_rate.full_clean()
    scheme_rate.save()
    record_audit_event(
        action=AuditEvent.Action.SCHEME_RATE_PUBLICATION,
        actor=published_by,
        reason=f"Published a new {metal.lower()} Scheme Rate.",
        scheme_rate=scheme_rate,
        details={
            "metal": metal,
            "rate_per_gram": str(scheme_rate.rate_per_gram),
            "purity": str(scheme_rate.purity),
            "effective_from": scheme_rate.effective_from.isoformat(),
            "notes": scheme_rate.notes,
        },
    )
    return scheme_rate


def _reference(prefix, model, field_name):
    for _ in range(10):
        value = f"{prefix}-{secrets.token_hex(4).upper()}"
        if not model.objects.filter(**{field_name: value}).exists():
            return value
    raise RuntimeError(f"Could not generate a unique {field_name}")


def add_calendar_months(value, months):
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


@transaction.atomic
def create_customer(*, full_name, email, mobile_number, address="", password=None):
    user_model = get_user_model()
    normalized_email = user_model.objects.normalize_email(email).strip().lower()
    if user_model.objects.filter(email__iexact=normalized_email).exists():
        raise ValidationError({"email": "A user with this email already exists."})

    name_parts = full_name.strip().split(maxsplit=1)
    user = user_model(
        username=normalized_email,
        email=normalized_email,
        first_name=name_parts[0],
        last_name=name_parts[1] if len(name_parts) > 1 else "",
        role=user_model.Role.CUSTOMER,
    )
    if password is None:
        user.set_unusable_password()
    else:
        user.set_password(password)
    user.full_clean()
    user.save()

    customer = Customer(
        user=user,
        customer_number=_reference("CUS", Customer, "customer_number"),
        full_name=full_name.strip(),
        mobile_number=mobile_number.strip(),
        email=normalized_email,
        address=address.strip(),
    )
    customer.full_clean()
    customer.save()
    return customer


@transaction.atomic
def create_invited_customer(
    *, full_name, email, mobile_number, invited_by, address=""
):
    customer = create_customer(
        full_name=full_name,
        email=email,
        mobile_number=mobile_number,
        address=address,
        password=None,
    )
    invitation, raw_token = issue_customer_invitation(
        user=customer.user,
        created_by=invited_by,
    )
    return customer, invitation, raw_token


@transaction.atomic
def enroll_customer(
    *,
    customer,
    plan,
    savings_mode,
    start_date=None,
    agreed_months=None,
    performed_by=None,
    reason="Customer enrolled through service.",
):
    if (
        savings_mode == SchemeAccount.SavingsMode.CASH
        and not cash_scheme_activity_is_enabled()
    ):
        raise ValidationError({"savings_mode": CASH_SCHEME_ACTIVITY_UNAVAILABLE})
    plan.full_clean()
    if not plan.active:
        raise ValidationError({"plan": "Only active plans can accept new enrolments."})
    start_date = start_date or timezone.localdate()
    agreed_months = agreed_months or plan.default_months
    if agreed_months < plan.minimum_months:
        raise ValidationError(
            {"agreed_months": "Agreed duration cannot be below the plan minimum."}
        )

    account = SchemeAccount(
        scheme_number=_reference("JSK", SchemeAccount, "scheme_number"),
        customer=customer,
        plan=plan,
        start_date=start_date,
        agreed_months=agreed_months,
        eligible_from=add_calendar_months(start_date, agreed_months),
        savings_mode=savings_mode,
        amount_rule_snapshot=plan.amount_rule,
        frequency_rule_snapshot=plan.frequency_rule,
        fixed_amount_snapshot=plan.fixed_contribution_amount,
        minimum_amount_snapshot=plan.minimum_contribution,
        maximum_amount_snapshot=plan.maximum_contribution,
        allow_post_eligibility_contributions_snapshot=(
            plan.allow_contributions_after_eligibility
        ),
        cash_bonus_policy_version_snapshot=CASH_BONUS_POLICY_VERSION,
        cash_bonus_percentage_snapshot=plan.cash_bonus_percentage,
        cash_bonus_minimum_months_snapshot=plan.cash_bonus_minimum_months,
    )
    account.full_clean()
    account.save()
    record_audit_event(
        action=AuditEvent.Action.CUSTOMER_ENROLMENT,
        actor=performed_by,
        reason=reason,
        scheme_plan=plan,
        scheme_account=account,
        details={
            "scheme_number": account.scheme_number,
            "savings_mode": account.savings_mode,
            "agreed_months": account.agreed_months,
            "eligible_from": account.eligible_from.isoformat(),
        },
    )
    return account


def contribution_period_for(value):
    return date(value.year, value.month, 1)


def validate_contribution_amount(scheme_account, amount):
    try:
        amount = Decimal(str(amount))
        normalized_amount = amount.quantize(MONEY_QUANTUM)
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError({"amount": "Enter a valid contribution amount."}) from None

    if amount != normalized_amount:
        raise ValidationError({"amount": "Contribution amounts support at most 2 decimal places."})
    if normalized_amount <= 0:
        raise ValidationError({"amount": "Contribution amount must be greater than zero."})

    if scheme_account.amount_rule_snapshot == SchemePlan.AmountRule.FIXED:
        if normalized_amount != scheme_account.fixed_amount_snapshot:
            raise ValidationError(
                {"amount": f"This scheme requires exactly ₹{scheme_account.fixed_amount_snapshot}."}
            )
    else:
        if normalized_amount < scheme_account.minimum_amount_snapshot:
            raise ValidationError(
                {"amount": f"Minimum contribution is ₹{scheme_account.minimum_amount_snapshot}."}
            )
        if (
            scheme_account.maximum_amount_snapshot is not None
            and normalized_amount > scheme_account.maximum_amount_snapshot
        ):
            raise ValidationError(
                {"amount": f"Maximum contribution is ₹{scheme_account.maximum_amount_snapshot}."}
            )
    return normalized_amount


def validate_redemption_amount(scheme_account, amount):
    quantum = (
        MONEY_QUANTUM
        if scheme_account.savings_mode == SchemeAccount.SavingsMode.CASH
        else METAL_QUANTUM
    )
    try:
        amount = Decimal(str(amount))
        normalized_amount = amount.quantize(quantum)
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError({"amount": "Enter a valid redemption amount."}) from None
    if amount != normalized_amount:
        decimal_places = 2 if quantum == MONEY_QUANTUM else 6
        raise ValidationError(
            {"amount": f"Redemption supports at most {decimal_places} decimal places."}
        )
    if normalized_amount <= 0:
        raise ValidationError({"amount": "Redemption amount must be greater than zero."})
    return normalized_amount


def validate_contribution_allowed(
    scheme_account,
    amount,
    contribution_date=None,
    *,
    contribution_period=None,
    exclude_contribution_id=None,
):
    if (
        scheme_account.savings_mode == SchemeAccount.SavingsMode.CASH
        and not cash_scheme_activity_is_enabled()
    ):
        raise ValidationError(CASH_SCHEME_ACTIVITY_UNAVAILABLE)
    contribution_date = contribution_date or timezone.localdate()
    if scheme_account.status == SchemeAccount.Status.REDEEMED:
        raise ValidationError("A redeemed scheme cannot receive contributions.")
    if contribution_date < scheme_account.start_date:
        raise ValidationError("Contributions cannot be made before the scheme start date.")
    if (
        contribution_date >= scheme_account.eligible_from
        and not scheme_account.allow_post_eligibility_contributions_snapshot
    ):
        raise ValidationError("This scheme does not allow contributions after eligibility.")

    normalized_amount = validate_contribution_amount(scheme_account, amount)
    period = contribution_period or contribution_period_for(contribution_date)
    if scheme_account.frequency_rule_snapshot == SchemePlan.FrequencyRule.ONCE_PER_MONTH:
        successful = Contribution.objects.filter(
            scheme_account=scheme_account,
            contribution_period=period,
            status__in=SUCCESSFUL_PAYMENT_STATUSES,
        )
        if exclude_contribution_id is not None:
            successful = successful.exclude(pk=exclude_contribution_id)
        if successful.exists():
            raise ValidationError(
                "A successful contribution has already been made for this calendar month."
            )
    return normalized_amount, period


def validate_contribution_confirmation_allowed(contribution):
    if contribution.frequency_rule_snapshot != SchemePlan.FrequencyRule.ONCE_PER_MONTH:
        return
    if Contribution.objects.filter(
        scheme_account=contribution.scheme_account,
        contribution_period=contribution.contribution_period,
        status__in=SUCCESSFUL_PAYMENT_STATUSES,
    ).exclude(pk=contribution.pk).exists():
        raise ValidationError(
            "A successful contribution has already been made for this calendar month."
        )


def _lock_current_scheme_rate(contribution):
    metal = contribution.scheme_account.savings_mode
    if metal not in {SchemeRate.Metal.GOLD, SchemeRate.Metal.SILVER}:
        return contribution
    if contribution.scheme_rate_id:
        return contribution
    scheme_rate = get_current_scheme_rate(metal)
    if scheme_rate is None:
        metal_name = contribution.scheme_account.get_savings_mode_display().split()[0]
        raise ValidationError(
            f"{metal_name} contributions are temporarily unavailable because the "
            "current Scheme Rate has not been published."
        )
    contribution.scheme_rate = scheme_rate
    contribution.rate_locked_at = timezone.now()
    return contribution


@transaction.atomic
def initiate_contribution(
    *,
    scheme_account,
    amount,
    payment_gateway,
    gateway_mode="",
    contribution_date=None,
):
    locked_account = SchemeAccount.objects.select_for_update().get(pk=scheme_account.pk)
    ensure_payment_initiation_allowed(
        metal=locked_account.savings_mode,
        lock=True,
    )
    normalized_amount, period = validate_contribution_allowed(
        locked_account, amount, contribution_date
    )
    contribution = Contribution(
        scheme_account=locked_account,
        amount=normalized_amount,
        contribution_period=period,
        frequency_rule_snapshot=locked_account.frequency_rule_snapshot,
        status=Contribution.Status.PENDING,
        payment_gateway=payment_gateway,
        gateway_mode=gateway_mode,
    )
    _lock_current_scheme_rate(contribution)
    contribution.full_clean()
    contribution.save()
    return contribution


@transaction.atomic
def confirm_contribution(
    *,
    contribution_id,
    payment_gateway,
    gateway_reference,
    verified,
    gateway_signature="",
):
    account_id = Contribution.objects.only("scheme_account_id").get(
        pk=contribution_id
    ).scheme_account_id
    SchemeAccount.objects.select_for_update().get(pk=account_id)
    contribution = (
        Contribution.objects.select_for_update()
        .select_related("scheme_account")
        .get(pk=contribution_id)
    )

    if contribution.status in SUCCESSFUL_PAYMENT_STATUSES:
        if (
            contribution.payment_gateway == payment_gateway
            and contribution.gateway_reference == gateway_reference
        ):
            return contribution
        raise ValidationError("This contribution has already been confirmed.")
    if contribution.status == Contribution.Status.FAILED:
        raise ValidationError("A failed contribution cannot be confirmed.")
    if contribution.status == Contribution.Status.ABANDONED:
        raise ValidationError(
            "An abandoned contribution cannot be confirmed automatically; "
            "reconcile and refund any late provider payment."
        )
    if not verified:
        raise ValidationError("Payment success was not verified server-side.")
    if contribution.payment_gateway != payment_gateway:
        raise ValidationError("Payment gateway does not match the initiated contribution.")
    if not gateway_reference:
        raise ValidationError("A verified gateway reference is required.")

    validate_contribution_confirmation_allowed(contribution)
    is_metal_contribution = contribution.scheme_account.savings_mode in {
        SchemeAccount.SavingsMode.GOLD,
        SchemeAccount.SavingsMode.SILVER,
    }
    contribution.status = (
        Contribution.Status.PAID_UNALLOCATED
        if is_metal_contribution
        else Contribution.Status.PAID
    )
    contribution.gateway_reference = gateway_reference
    contribution.gateway_signature = gateway_signature
    contribution.paid_at = timezone.now()
    contribution.full_clean()
    contribution.save(
        update_fields=[
            "status",
            "gateway_reference",
            "gateway_signature",
            "paid_at",
        ]
    )
    return contribution


@transaction.atomic
def fail_contribution(*, contribution_id, gateway_reference=None):
    contribution = Contribution.objects.select_for_update().get(pk=contribution_id)
    if contribution.status in SUCCESSFUL_PAYMENT_STATUSES:
        raise ValidationError("A paid contribution cannot be marked as failed.")
    contribution.status = Contribution.Status.FAILED
    contribution.gateway_reference = gateway_reference
    contribution.paid_at = None
    contribution.full_clean()
    contribution.save(update_fields=["status", "gateway_reference", "paid_at"])
    return contribution


def reconcile_abandoned_razorpay_contribution(
    *,
    contribution_id,
    cutoff,
    apply=False,
    gateway=None,
    performed_by=None,
    reason="Reconciled an aged Razorpay order against the provider.",
):
    """Inspect and optionally close a clearly untouched Razorpay order.

    Razorpay Orders cannot be cancelled through the Orders API. ABANDONED is
    therefore an application-side state: the provider reference is retained and a
    later captured webhook is deliberately rejected into the exception workflow.
    """
    gateway = gateway or get_payment_gateway()
    if (
        gateway.name != "razorpay"
        or getattr(gateway, "mode", None) not in GatewayMode.values
    ):
        raise ImproperlyConfigured("A mode-specific Razorpay gateway is required.")
    if performed_by is not None:
        _validate_owner(performed_by)
    normalized_reason = reason.strip()
    if not normalized_reason:
        raise ValidationError({"reason": "Enter a reconciliation reason."})
    if timezone.is_naive(cutoff):
        cutoff = timezone.make_aware(cutoff, timezone.get_current_timezone())

    contribution = Contribution.objects.select_related("scheme_account").get(
        pk=contribution_id
    )
    if contribution.status != Contribution.Status.PENDING:
        raise ValidationError(
            "Only a pending contribution can be reconciled as abandoned."
        )
    if contribution.payment_gateway != "razorpay" or not contribution.gateway_order_id:
        raise ValidationError("The contribution has no Razorpay order to reconcile.")
    if contribution.gateway_mode != gateway.mode:
        raise ValidationError(
            "The Razorpay payment mode does not match the initiated contribution."
        )
    if contribution.created_at > cutoff:
        raise ValidationError(
            "The Razorpay order is not old enough for abandonment review."
        )

    inspection = gateway.inspect_order(order_id=contribution.gateway_order_id)
    expected_amount = int(contribution.amount * 100)
    untouched = (
        inspection.order_id == contribution.gateway_order_id
        and inspection.status == "created"
        and inspection.amount_subunits == expected_amount
        and inspection.amount_paid_subunits == 0
        and inspection.amount_due_subunits == expected_amount
        and inspection.currency == "INR"
        and inspection.attempts == 0
        and inspection.payment_count == 0
        and not inspection.payment_statuses
    )
    outcome = "ELIGIBLE_FOR_ABANDONMENT" if untouched else "REVIEW_REQUIRED"
    if not apply:
        return RazorpayOrderReconciliationResult(
            contribution=contribution,
            inspection=inspection,
            outcome=outcome,
            applied=False,
        )

    with transaction.atomic():
        locked = (
            Contribution.objects.select_for_update()
            .select_related("scheme_account")
            .get(pk=contribution.pk)
        )
        if (
            locked.status != Contribution.Status.PENDING
            or locked.gateway_order_id != contribution.gateway_order_id
            or locked.gateway_mode != gateway.mode
        ):
            raise ValidationError(
                "The contribution changed during reconciliation; inspect it again."
            )
        if untouched:
            locked.status = Contribution.Status.ABANDONED
            locked.full_clean()
            locked.save(update_fields=["status"])

        record_audit_event(
            action=AuditEvent.Action.PAYMENT_ORDER_RECONCILIATION,
            actor=performed_by,
            reason=normalized_reason,
            scheme_account=locked.scheme_account,
            contribution=locked,
            details={
                "outcome": outcome,
                "applied": untouched,
                "gateway": "razorpay",
                "gateway_mode": locked.gateway_mode,
                "gateway_order_id": locked.gateway_order_id,
                "provider_order_status": inspection.status,
                "provider_attempts": inspection.attempts,
                "provider_amount_subunits": inspection.amount_subunits,
                "provider_amount_paid_subunits": inspection.amount_paid_subunits,
                "provider_amount_due_subunits": inspection.amount_due_subunits,
                "provider_payment_count": inspection.payment_count,
                "provider_payment_statuses": list(inspection.payment_statuses),
            },
        )
    return RazorpayOrderReconciliationResult(
        contribution=locked,
        inspection=inspection,
        outcome=outcome,
        applied=untouched,
    )


@transaction.atomic
def allocate_metal(*, contribution):
    locked_contribution = (
        Contribution.objects.select_for_update()
        .select_related("scheme_account")
        .get(pk=contribution.pk)
    )
    existing = (
        MetalAllocation.objects.filter(contribution=locked_contribution)
        .select_related("scheme_rate")
        .first()
    )
    if existing is not None:
        if locked_contribution.status == Contribution.Status.PAID_UNALLOCATED:
            locked_contribution.status = Contribution.Status.PAID
            locked_contribution.allocation_error = ""
            locked_contribution.save(update_fields=["status", "allocation_error"])
        return existing
    if locked_contribution.status not in SUCCESSFUL_PAYMENT_STATUSES:
        raise ValidationError("Only a paid contribution can receive a metal allocation.")

    metal = locked_contribution.scheme_account.savings_mode
    if metal not in {SchemeRate.Metal.GOLD, SchemeRate.Metal.SILVER}:
        raise ValidationError("Cash contributions do not receive a metal allocation.")
    scheme_rate = locked_contribution.scheme_rate
    if scheme_rate is None:
        raise ValidationError("This paid contribution has no locked Scheme Rate.")
    if scheme_rate.metal != metal:
        raise ValidationError("The locked Scheme Rate metal does not match the scheme.")
    if scheme_rate.rate_per_gram <= 0:
        raise ValidationError("The locked Scheme Rate must be greater than zero.")

    quantity = (locked_contribution.amount / scheme_rate.rate_per_gram).quantize(
        METAL_QUANTUM, rounding=ROUND_HALF_UP
    )
    if quantity <= 0:
        raise ValidationError("The contribution is too small to allocate at 6 decimal places.")
    allocation = MetalAllocation(
        contribution=locked_contribution,
        scheme_rate=scheme_rate,
        metal=metal,
        quantity=quantity,
    )
    allocation.full_clean()
    allocation.save()
    locked_contribution.status = Contribution.Status.PAID
    locked_contribution.allocation_error = ""
    locked_contribution.allocation_attempted_at = timezone.now()
    locked_contribution.full_clean()
    locked_contribution.save(
        update_fields=["status", "allocation_error", "allocation_attempted_at"]
    )
    return allocation


@transaction.atomic
def mark_contribution_paid_unallocated(*, contribution_id, error):
    contribution = (
        Contribution.objects.select_for_update()
        .select_related("scheme_account")
        .get(pk=contribution_id)
    )
    if contribution.scheme_account.savings_mode not in {
        SchemeAccount.SavingsMode.GOLD,
        SchemeAccount.SavingsMode.SILVER,
    }:
        raise ValidationError("Only metal contributions can await allocation.")
    if contribution.status not in SUCCESSFUL_PAYMENT_STATUSES:
        raise ValidationError("Only a successful payment can await allocation.")
    if MetalAllocation.objects.filter(contribution=contribution).exists():
        contribution.status = Contribution.Status.PAID
        contribution.allocation_error = ""
    else:
        contribution.status = Contribution.Status.PAID_UNALLOCATED
        if isinstance(error, EXPECTED_ALLOCATION_ERRORS):
            contribution.allocation_error = str(error).strip()[:1000]
        else:
            contribution.allocation_error = (
                "Unexpected allocation error. Owner investigation is required."
            )
    contribution.allocation_attempted_at = timezone.now()
    contribution.full_clean()
    contribution.save(
        update_fields=["status", "allocation_error", "allocation_attempted_at"]
    )
    return contribution


def retry_metal_allocation(*, contribution, performed_by=None, reason=""):
    if performed_by is not None:
        _validate_owner(performed_by)
        if not reason.strip():
            raise ValidationError({"reason": "Enter a reason for retrying allocation."})
    try:
        allocation = allocate_metal(contribution=contribution)
    except Exception as error:
        mark_contribution_paid_unallocated(
            contribution_id=contribution.pk,
            error=error,
        )
        if performed_by is not None:
            record_audit_event(
                action=AuditEvent.Action.ALLOCATION_RETRY,
                actor=performed_by,
                reason=reason,
                scheme_account=contribution.scheme_account,
                contribution=contribution,
                details={"outcome": "FAILED", "error": str(error).strip()[:1000]},
            )
        raise
    if performed_by is not None:
        record_audit_event(
            action=AuditEvent.Action.ALLOCATION_RETRY,
            actor=performed_by,
            reason=reason,
            scheme_account=contribution.scheme_account,
            contribution=contribution,
            scheme_rate=allocation.scheme_rate,
            details={
                "outcome": "SUCCEEDED",
                "quantity": str(allocation.quantity),
                "scheme_rate": str(allocation.scheme_rate.rate_per_gram),
            },
        )
    return allocation


def _apply_contribution_entitlement(contribution):
    if contribution.scheme_account.savings_mode in {
        SchemeAccount.SavingsMode.GOLD,
        SchemeAccount.SavingsMode.SILVER,
    }:
        try:
            retry_metal_allocation(contribution=contribution)
        except EXPECTED_ALLOCATION_ERRORS:
            pass
        return Contribution.objects.select_related("scheme_account").get(
            pk=contribution.pk
        )
    return contribution


def initiate_razorpay_contribution(
    *, scheme_account, amount, contribution_date=None, gateway=None
):
    gateway = gateway or get_payment_gateway()
    if gateway.name != "razorpay":
        raise ImproperlyConfigured("The Razorpay payment gateway is not configured.")
    if getattr(gateway, "mode", None) not in GatewayMode.values:
        raise ImproperlyConfigured("The Razorpay payment mode is not configured.")

    ensure_payment_initiation_allowed(metal=scheme_account.savings_mode)

    normalized_amount, period = validate_contribution_allowed(
        scheme_account, amount, contribution_date
    )
    contribution = Contribution.objects.filter(
        scheme_account=scheme_account,
        contribution_period=period,
        frequency_rule_snapshot=SchemePlan.FrequencyRule.ONCE_PER_MONTH,
        status=Contribution.Status.PENDING,
        payment_gateway=gateway.name,
    ).first()
    if contribution is not None and contribution.amount != normalized_amount:
        raise ValidationError(
            "A Razorpay payment is already pending for this contribution month."
        )
    if contribution is not None and contribution.gateway_mode != gateway.mode:
        raise ValidationError(
            "A Razorpay payment from a different provider mode is already pending "
            "for this contribution month. Reconcile it before starting another payment."
        )
    if contribution is None:
        try:
            contribution = initiate_contribution(
                scheme_account=scheme_account,
                amount=normalized_amount,
                payment_gateway=gateway.name,
                gateway_mode=gateway.mode,
                contribution_date=contribution_date,
            )
        except IntegrityError:
            contribution = Contribution.objects.get(
                scheme_account=scheme_account,
                contribution_period=period,
                frequency_rule_snapshot=SchemePlan.FrequencyRule.ONCE_PER_MONTH,
                status=Contribution.Status.PENDING,
                payment_gateway=gateway.name,
            )
            if contribution.amount != normalized_amount:
                raise ValidationError(
                    "A Razorpay payment is already pending for this contribution month."
                ) from None
            if contribution.gateway_mode != gateway.mode:
                raise ValidationError(
                    "A Razorpay payment from a different provider mode is already "
                    "pending for this contribution month. Reconcile it before "
                    "starting another payment."
                ) from None

    order_error = None
    with transaction.atomic():
        contribution = (
            Contribution.objects.select_for_update()
            .select_related("scheme_account")
            .get(pk=contribution.pk)
        )
        ensure_payment_initiation_allowed(
            metal=contribution.scheme_account.savings_mode,
            lock=True,
        )
        if not contribution.scheme_rate_id:
            _lock_current_scheme_rate(contribution)
            contribution.full_clean()
            contribution.save(update_fields=["scheme_rate", "rate_locked_at"])
        if contribution.gateway_order_id:
            return contribution
        try:
            order = gateway.create_order(contribution)
        except PaymentGatewayError as error:
            contribution.status = Contribution.Status.FAILED
            contribution.full_clean()
            contribution.save(update_fields=["status"])
            order_error = error
        else:
            contribution.gateway_order_id = order.order_id
            contribution.full_clean()
            contribution.save(update_fields=["gateway_order_id"])
    if order_error is not None:
        raise order_error
    return contribution


def confirm_razorpay_contribution(
    *,
    contribution_id,
    callback_order_id,
    payment_id,
    signature,
    gateway=None,
):
    gateway = gateway or get_payment_gateway()
    if gateway.name != "razorpay":
        raise ImproperlyConfigured("The Razorpay payment gateway is not configured.")
    contribution = Contribution.objects.select_related("scheme_account").get(
        pk=contribution_id
    )
    if contribution.gateway_mode != getattr(gateway, "mode", None):
        raise ValidationError(
            "The Razorpay payment mode does not match the initiated contribution."
        )
    if not contribution.gateway_order_id or callback_order_id != contribution.gateway_order_id:
        raise ValidationError("The Razorpay order does not match this contribution.")
    if contribution.status in SUCCESSFUL_PAYMENT_STATUSES:
        if contribution.gateway_reference != payment_id:
            raise ValidationError("This contribution has already been confirmed.")
        return _apply_contribution_entitlement(contribution)
    if contribution.status == Contribution.Status.ABANDONED:
        raise ValidationError(
            "An abandoned contribution cannot be confirmed automatically; "
            "reconcile and refund any late provider payment."
        )

    verified = gateway.verify_payment(
        order_id=contribution.gateway_order_id,
        payment_id=payment_id,
        signature=signature,
        expected_amount=contribution.amount,
    )
    contribution = confirm_contribution(
        contribution_id=contribution.pk,
        payment_gateway=gateway.name,
        gateway_reference=payment_id,
        gateway_signature=signature,
        verified=verified,
    )
    return _apply_contribution_entitlement(contribution)


def _record_webhook_attempt(
    *,
    event,
    source,
    outcome,
    reason,
    actor=None,
    error_code="",
    detail="",
    provider_snapshot=None,
):
    normalized_reason = reason.strip()
    if not normalized_reason:
        raise ValidationError({"reason": "Enter a webhook processing reason."})
    actor_label = (
        _actor_label(actor)
        if actor is not None
        else f"Razorpay {event.gateway_mode} webhook"
    )
    attempt = WebhookProcessingAttempt(
        webhook_event=event,
        source=source,
        outcome=outcome,
        actor=actor,
        actor_label=actor_label,
        reason=normalized_reason,
        error_code=error_code,
        detail=detail.strip()[:1000],
        provider_snapshot=provider_snapshot or {},
    )
    attempt.full_clean()
    attempt.save()
    return attempt


def _payment_inspection_snapshot(inspection):
    if inspection is None:
        return {}
    return {
        "payment_id": inspection.payment_id,
        "order_id": inspection.order_id,
        "amount_subunits": inspection.amount_subunits,
        "currency": inspection.currency,
        "status": inspection.status,
        "captured": inspection.captured,
    }


def _extract_webhook_payment(payload):
    payment = payload.get("payload", {}).get("payment", {}).get("entity", {})
    if not isinstance(payment, dict):
        raise _WebhookReviewRequired(
            "PAYMENT_ENTITY_MISSING",
            "Razorpay webhook payment details are missing.",
        )
    payment_id = payment.get("id")
    order_id = payment.get("order_id")
    if (
        not isinstance(payment_id, str)
        or not payment_id.startswith("pay_")
        or len(payment_id) > 120
        or not isinstance(order_id, str)
        or not order_id.startswith("order_")
        or len(order_id) > 120
    ):
        raise _WebhookReviewRequired(
            "PAYMENT_IDENTIFIERS_MISSING",
            "Razorpay webhook payment identifiers are missing or invalid.",
        )
    return payment, payment_id, order_id


def process_razorpay_webhook(*, gateway_mode, event_id, body, payload):
    if gateway_mode not in GatewayMode.values:
        raise ValidationError("The Razorpay webhook mode is invalid.")
    payload_hash = hashlib.sha256(body).hexdigest()
    event_type = payload.get("event") if isinstance(payload, dict) else None
    if not isinstance(event_type, str) or not event_type:
        raise ValidationError("Razorpay webhook event type is missing.")
    event, _ = PaymentWebhookEvent.objects.get_or_create(
        gateway="razorpay",
        gateway_mode=gateway_mode,
        event_id=event_id,
        defaults={
            "event_type": event_type,
            "payload_sha256": payload_hash,
        },
    )
    if event.payload_sha256 != payload_hash:
        raise ValidationError("Razorpay reused an event ID with different content.")
    if event.status in {
        PaymentWebhookEvent.Status.PROCESSED,
        PaymentWebhookEvent.Status.IGNORED,
        PaymentWebhookEvent.Status.REVIEW_REQUIRED,
    }:
        _record_webhook_attempt(
            event=event,
            source=WebhookProcessingAttempt.Source.PROVIDER_DELIVERY,
            outcome=WebhookProcessingAttempt.Outcome.ALREADY_FINAL,
            reason="Received a duplicate delivery for a final webhook event.",
        )
        return event

    try:
        if event_type != "payment.captured":
            with transaction.atomic():
                event.status = PaymentWebhookEvent.Status.IGNORED
                event.processed_at = timezone.now()
                event.failure_code = ""
                event.error = ""
                event.save(
                    update_fields=[
                        "status",
                        "processed_at",
                        "failure_code",
                        "error",
                    ]
                )
                _record_webhook_attempt(
                    event=event,
                    source=WebhookProcessingAttempt.Source.PROVIDER_DELIVERY,
                    outcome=WebhookProcessingAttempt.Outcome.IGNORED,
                    reason=f"Ignored unsupported Razorpay event type {event_type}.",
                )
            return event

        payment, payment_id, order_id = _extract_webhook_payment(payload)
        event.gateway_order_id = order_id
        event.gateway_reference = payment_id
        event.save(update_fields=["gateway_order_id", "gateway_reference"])
        try:
            contribution = Contribution.objects.select_related("scheme_account").get(
                payment_gateway="razorpay",
                gateway_mode=gateway_mode,
                gateway_order_id=order_id,
            )
        except Contribution.DoesNotExist:
            raise _WebhookReviewRequired(
                "CONTRIBUTION_NOT_FOUND_OR_MODE_MISMATCH",
                "No mode-matched local contribution exists for this Razorpay order.",
            ) from None
        event.contribution = contribution
        event.save(update_fields=["contribution"])
        if (
            payment.get("status") != "captured"
            or payment.get("captured") is not True
            or payment.get("currency") != "INR"
            or payment.get("amount") != int(contribution.amount * 100)
        ):
            raise _WebhookReviewRequired(
                "PAYMENT_DETAILS_MISMATCH",
                "Razorpay webhook payment details do not match the local contribution.",
            )
        if contribution.status == Contribution.Status.ABANDONED:
            raise _WebhookReviewRequired(
                "LATE_CAPTURE_ABANDONED",
                "An abandoned contribution received a late captured payment; "
                "reconcile and refund it manually.",
            )

        try:
            contribution = confirm_contribution(
                contribution_id=contribution.pk,
                payment_gateway="razorpay",
                gateway_reference=payment_id,
                verified=True,
            )
            contribution = _apply_contribution_entitlement(contribution)
        except ValidationError as error:
            raise _WebhookReviewRequired(
                "CONTRIBUTION_CONFIRMATION_REJECTED",
                str(error).strip(),
            ) from None

        with transaction.atomic():
            event.status = PaymentWebhookEvent.Status.PROCESSED
            event.contribution = contribution
            event.failure_code = ""
            event.error = ""
            event.processed_at = timezone.now()
            event.save(
                update_fields=[
                    "status",
                    "contribution",
                    "failure_code",
                    "error",
                    "processed_at",
                ]
            )
            _record_webhook_attempt(
                event=event,
                source=WebhookProcessingAttempt.Source.PROVIDER_DELIVERY,
                outcome=WebhookProcessingAttempt.Outcome.PROCESSED,
                reason="Processed a signed captured-payment webhook.",
            )
        return event
    except _WebhookReviewRequired as error:
        with transaction.atomic():
            event.status = PaymentWebhookEvent.Status.REVIEW_REQUIRED
            event.failure_code = error.code
            event.error = error.detail[:1000]
            event.processed_at = timezone.now()
            event.save(
                update_fields=[
                    "status",
                    "contribution",
                    "gateway_order_id",
                    "gateway_reference",
                    "failure_code",
                    "error",
                    "processed_at",
                ]
            )
            _record_webhook_attempt(
                event=event,
                source=WebhookProcessingAttempt.Source.PROVIDER_DELIVERY,
                outcome=WebhookProcessingAttempt.Outcome.REVIEW_REQUIRED,
                reason="Accepted a signed webhook into owner reconciliation.",
                error_code=error.code,
                detail=error.detail,
            )
        return event
    except Exception as error:
        safe_detail = "A transient application failure interrupted webhook processing."
        try:
            with transaction.atomic():
                event.status = PaymentWebhookEvent.Status.RECEIVED
                event.failure_code = "TRANSIENT_PROCESSING_FAILURE"
                event.error = safe_detail
                event.processed_at = None
                event.save(
                    update_fields=[
                        "status",
                        "contribution",
                        "gateway_order_id",
                        "gateway_reference",
                        "failure_code",
                        "error",
                        "processed_at",
                    ]
                )
                _record_webhook_attempt(
                    event=event,
                    source=WebhookProcessingAttempt.Source.PROVIDER_DELIVERY,
                    outcome=WebhookProcessingAttempt.Outcome.TRANSIENT_FAILURE,
                    reason="Deferred a signed webhook for provider retry.",
                    error_code="TRANSIENT_PROCESSING_FAILURE",
                    detail=safe_detail,
                )
        except Exception:
            pass
        raise WebhookTransientProcessingError(safe_detail) from error


def _classify_webhook_recovery(*, event, contribution, inspection):
    if contribution is None:
        return (
            "MANUAL_REVIEW_REQUIRED",
            "No mode-matched local contribution exists for this Razorpay order.",
        )
    expected_amount = int(contribution.amount * 100)
    if (
        inspection.payment_id != event.gateway_reference
        or inspection.order_id != event.gateway_order_id
        or inspection.amount_subunits != expected_amount
        or inspection.currency != "INR"
        or inspection.status != "captured"
        or inspection.captured is not True
    ):
        return (
            "MANUAL_REVIEW_REQUIRED",
            "The provider payment does not exactly match a captured local contribution.",
        )
    if contribution.status == Contribution.Status.ABANDONED:
        return (
            "MANUAL_REVIEW_REQUIRED",
            "The provider captured an abandoned contribution; use the manual refund workflow.",
        )
    if contribution.status == Contribution.Status.FAILED:
        return (
            "MANUAL_REVIEW_REQUIRED",
            "A failed local contribution cannot receive automatic entitlement.",
        )
    if contribution.status == Contribution.Status.PENDING:
        return ("ELIGIBLE_FOR_RECOVERY", "The captured payment is eligible for recovery.")
    if contribution.status in SUCCESSFUL_PAYMENT_STATUSES:
        if contribution.gateway_reference == inspection.payment_id:
            return ("ALREADY_PROCESSED", "The contribution is already confirmed.")
        return (
            "MANUAL_REVIEW_REQUIRED",
            "The contribution was confirmed with a different provider payment.",
        )
    return ("MANUAL_REVIEW_REQUIRED", "The contribution status requires manual review.")


def reconcile_razorpay_webhook(
    *,
    webhook_event_id,
    apply=False,
    gateway=None,
    performed_by,
    reason,
):
    _validate_owner(performed_by)
    normalized_reason = reason.strip()
    if not normalized_reason:
        raise ValidationError({"reason": "Enter a webhook recovery reason."})
    gateway = gateway or get_payment_gateway()
    if (
        gateway.name != "razorpay"
        or getattr(gateway, "mode", None) not in GatewayMode.values
    ):
        raise ImproperlyConfigured("A mode-specific Razorpay gateway is required.")

    event = PaymentWebhookEvent.objects.select_related(
        "contribution",
        "contribution__scheme_account",
    ).get(pk=webhook_event_id, gateway="razorpay")
    if event.gateway_mode != gateway.mode:
        raise ValidationError(
            "The Razorpay gateway mode does not match this webhook event."
        )
    if event.event_type != "payment.captured":
        raise ValidationError("Only captured-payment webhooks can be reconciled.")
    if apply and not event.processing_attempts.filter(
        source=WebhookProcessingAttempt.Source.OWNER_RECOVERY,
        outcome__in=[
            WebhookProcessingAttempt.Outcome.ELIGIBLE_FOR_RECOVERY,
            WebhookProcessingAttempt.Outcome.ALREADY_PROCESSED,
        ],
    ).exists():
        raise ValidationError(
            "Check provider state and review a safe result before applying recovery."
        )
    if not event.gateway_order_id or not event.gateway_reference:
        _record_webhook_attempt(
            event=event,
            source=WebhookProcessingAttempt.Source.OWNER_RECOVERY,
            outcome=WebhookProcessingAttempt.Outcome.REVIEW_REQUIRED,
            actor=performed_by,
            reason=normalized_reason,
            error_code="PROVIDER_IDENTIFIERS_UNAVAILABLE",
            detail="The webhook does not retain both provider identifiers.",
        )
        return RazorpayWebhookRecoveryResult(
            webhook_event=event,
            contribution=event.contribution,
            inspection=None,
            outcome="MANUAL_REVIEW_REQUIRED",
            applied=False,
        )

    try:
        inspection = gateway.inspect_payment(payment_id=event.gateway_reference)
    except PaymentGatewayError as error:
        _record_webhook_attempt(
            event=event,
            source=WebhookProcessingAttempt.Source.OWNER_RECOVERY,
            outcome=WebhookProcessingAttempt.Outcome.TRANSIENT_FAILURE,
            actor=performed_by,
            reason=normalized_reason,
            error_code="PROVIDER_INSPECTION_FAILED",
            detail=str(error),
        )
        raise

    contribution = (
        Contribution.objects.select_related("scheme_account")
        .filter(
            payment_gateway="razorpay",
            gateway_mode=event.gateway_mode,
            gateway_order_id=event.gateway_order_id,
        )
        .first()
    )
    outcome, detail = _classify_webhook_recovery(
        event=event,
        contribution=contribution,
        inspection=inspection,
    )
    snapshot = _payment_inspection_snapshot(inspection)
    attempt_outcome = {
        "ELIGIBLE_FOR_RECOVERY": WebhookProcessingAttempt.Outcome.ELIGIBLE_FOR_RECOVERY,
        "ALREADY_PROCESSED": WebhookProcessingAttempt.Outcome.ALREADY_PROCESSED,
        "MANUAL_REVIEW_REQUIRED": WebhookProcessingAttempt.Outcome.REVIEW_REQUIRED,
    }[outcome]
    if not apply or outcome == "MANUAL_REVIEW_REQUIRED":
        _record_webhook_attempt(
            event=event,
            source=WebhookProcessingAttempt.Source.OWNER_RECOVERY,
            outcome=attempt_outcome,
            actor=performed_by,
            reason=normalized_reason,
            error_code=("" if outcome != "MANUAL_REVIEW_REQUIRED" else event.failure_code),
            detail=detail,
            provider_snapshot=snapshot,
        )
        return RazorpayWebhookRecoveryResult(
            webhook_event=event,
            contribution=contribution,
            inspection=inspection,
            outcome=outcome,
            applied=False,
        )

    with transaction.atomic():
        locked_event = PaymentWebhookEvent.objects.select_for_update().get(pk=event.pk)
        locked_contribution = (
            Contribution.objects.select_for_update()
            .select_related("scheme_account")
            .get(pk=contribution.pk)
        )
        locked_outcome, locked_detail = _classify_webhook_recovery(
            event=locked_event,
            contribution=locked_contribution,
            inspection=inspection,
        )
        if locked_outcome not in {"ELIGIBLE_FOR_RECOVERY", "ALREADY_PROCESSED"}:
            raise ValidationError(
                "The webhook or contribution changed during recovery; inspect it again."
            )
        if locked_outcome == "ELIGIBLE_FOR_RECOVERY":
            locked_contribution = confirm_contribution(
                contribution_id=locked_contribution.pk,
                payment_gateway="razorpay",
                gateway_reference=inspection.payment_id,
                verified=True,
            )
            locked_contribution = _apply_contribution_entitlement(locked_contribution)
        elif locked_contribution.status == Contribution.Status.PAID_UNALLOCATED:
            locked_contribution = _apply_contribution_entitlement(locked_contribution)

        locked_event.status = PaymentWebhookEvent.Status.PROCESSED
        locked_event.contribution = locked_contribution
        locked_event.failure_code = ""
        locked_event.error = ""
        locked_event.processed_at = timezone.now()
        locked_event.save(
            update_fields=[
                "status",
                "contribution",
                "failure_code",
                "error",
                "processed_at",
            ]
        )
        _record_webhook_attempt(
            event=locked_event,
            source=WebhookProcessingAttempt.Source.OWNER_RECOVERY,
            outcome=(
                WebhookProcessingAttempt.Outcome.PROCESSED
                if locked_outcome == "ELIGIBLE_FOR_RECOVERY"
                else WebhookProcessingAttempt.Outcome.ALREADY_PROCESSED
            ),
            actor=performed_by,
            reason=normalized_reason,
            detail=locked_detail,
            provider_snapshot=snapshot,
        )
        record_audit_event(
            action=AuditEvent.Action.WEBHOOK_RECOVERY,
            actor=performed_by,
            reason=normalized_reason,
            scheme_account=locked_contribution.scheme_account,
            contribution=locked_contribution,
            details={
                "webhook_event_id": locked_event.pk,
                "gateway": locked_event.gateway,
                "gateway_mode": locked_event.gateway_mode,
                "gateway_event_id": locked_event.event_id,
                "gateway_order_id": locked_event.gateway_order_id,
                "gateway_reference": locked_event.gateway_reference,
                "outcome": locked_outcome,
                "provider": snapshot,
            },
        )
    return RazorpayWebhookRecoveryResult(
        webhook_event=locked_event,
        contribution=locked_contribution,
        inspection=inspection,
        outcome=locked_outcome,
        applied=True,
    )


def process_mock_contribution(*, scheme_account, amount, contribution_date=None):
    gateway = get_payment_gateway()
    contribution = initiate_contribution(
        scheme_account=scheme_account,
        amount=amount,
        payment_gateway=gateway.name,
        contribution_date=contribution_date,
    )
    result = gateway.charge(contribution)
    if not result.successful:
        return fail_contribution(
            contribution_id=contribution.pk,
            gateway_reference=result.gateway_reference,
        )
    contribution = confirm_contribution(
        contribution_id=contribution.pk,
        payment_gateway=gateway.name,
        gateway_reference=result.gateway_reference,
        verified=result.verified,
    )
    return _apply_contribution_entitlement(contribution)


@transaction.atomic
def complete_redemption(
    *,
    scheme_account,
    settlement_type,
    amount,
    processed_by,
    idempotency_key,
    external_reference="",
    notes="",
    audit_reason="Redemption completed through service.",
):
    account = (
        SchemeAccount.objects.select_for_update()
        .select_related("customer")
        .get(pk=scheme_account.pk)
    )
    normalized_amount = validate_redemption_amount(account, amount)
    external_reference = external_reference.strip()
    notes = notes.strip()
    allowed_settlements = {
        SchemeAccount.SavingsMode.CASH: {
            Redemption.SettlementType.CASH,
            Redemption.SettlementType.JEWELLERY_PURCHASE,
        },
        SchemeAccount.SavingsMode.GOLD: {
            Redemption.SettlementType.METAL,
            Redemption.SettlementType.JEWELLERY_PURCHASE,
        },
        SchemeAccount.SavingsMode.SILVER: {
            Redemption.SettlementType.METAL,
            Redemption.SettlementType.JEWELLERY_PURCHASE,
        },
    }
    if settlement_type not in allowed_settlements[account.savings_mode]:
        raise ValidationError(
            "The settlement type is not supported for this savings mode."
        )
    if (
        settlement_type == Redemption.SettlementType.JEWELLERY_PURCHASE
        and not external_reference
    ):
        raise ValidationError(
            {"external_reference": "Enter the jewellery invoice or sales reference."}
        )
    if not processed_by.is_active or not (
        processed_by.is_superuser
        or processed_by.role == get_user_model().Role.OWNER
    ):
        raise ValidationError("Only an active owner can complete a redemption.")

    values = {
        "cash_amount": None,
        "cash_principal_amount": None,
        "cash_bonus_amount": None,
        "gold_quantity": None,
        "silver_quantity": None,
    }
    if account.savings_mode == SchemeAccount.SavingsMode.CASH:
        values["cash_amount"] = normalized_amount
    elif account.savings_mode == SchemeAccount.SavingsMode.GOLD:
        values["gold_quantity"] = normalized_amount
    else:
        values["silver_quantity"] = normalized_amount

    existing = Redemption.objects.filter(idempotency_key=idempotency_key).first()
    if existing is not None:
        if (
            existing.scheme_account_id == account.pk
            and existing.settlement_type == settlement_type
            and existing.cash_amount == values["cash_amount"]
            and existing.gold_quantity == values["gold_quantity"]
            and existing.silver_quantity == values["silver_quantity"]
            and existing.external_reference == external_reference
            and existing.notes == notes
        ):
            return existing
        raise ValidationError("The redemption submission token was already used.")

    if account.status == SchemeAccount.Status.REDEEMED:
        raise ValidationError("This scheme has already been fully redeemed.")
    if timezone.localdate() < account.eligible_from:
        raise ValidationError("This scheme is not yet eligible for redemption.")
    outstanding = get_outstanding_entitlement(account)
    if outstanding <= 0:
        raise ValidationError("This scheme has no outstanding entitlement to redeem.")
    if normalized_amount > outstanding:
        unit = "INR" if account.savings_mode == SchemeAccount.SavingsMode.CASH else "g"
        raise ValidationError(
            {"amount": f"Cannot redeem more than the outstanding {outstanding} {unit}."}
        )

    if account.savings_mode == SchemeAccount.SavingsMode.CASH:
        cash_summary = get_cash_bonus_summary(account)
        principal_amount = min(
            normalized_amount,
            cash_summary.principal_outstanding,
        )
        values["cash_principal_amount"] = principal_amount
        values["cash_bonus_amount"] = normalized_amount - principal_amount

    redemption = Redemption(
        redemption_number=_reference("RED", Redemption, "redemption_number"),
        idempotency_key=idempotency_key,
        scheme_account=account,
        settlement_type=settlement_type,
        external_reference=external_reference,
        notes=notes,
        processed_by=processed_by,
        **values,
    )
    redemption.full_clean()
    redemption.save()
    record_audit_event(
        action=AuditEvent.Action.REDEMPTION,
        actor=processed_by,
        reason=audit_reason,
        scheme_account=account,
        redemption=redemption,
        details={
            "redemption_number": redemption.redemption_number,
            "settlement_type": settlement_type,
            "amount": str(normalized_amount),
            "unit": redemption.entitlement_unit,
        },
    )
    if normalized_amount == outstanding:
        account.status = SchemeAccount.Status.REDEEMED
        account.save(update_fields=["status", "updated_at"])
    return redemption


@transaction.atomic
def reverse_redemption(*, redemption, processed_by, reason):
    _validate_owner(processed_by)
    normalized_reason = reason.strip()
    if not normalized_reason:
        raise ValidationError({"reason": "Enter a reason for the reversal."})

    locked_redemption = (
        Redemption.objects.select_for_update()
        .select_related("scheme_account")
        .get(pk=redemption.pk)
    )
    existing = RedemptionReversal.objects.filter(
        redemption=locked_redemption
    ).first()
    if existing is not None:
        raise ValidationError("This redemption has already been reversed.")

    reversal = RedemptionReversal(
        reversal_number=_reference(
            "REV", RedemptionReversal, "reversal_number"
        ),
        redemption=locked_redemption,
        reason=normalized_reason,
        processed_by=processed_by,
    )
    reversal.full_clean()
    reversal.save()

    account = SchemeAccount.objects.select_for_update().get(
        pk=locked_redemption.scheme_account_id
    )
    if account.status == SchemeAccount.Status.REDEEMED:
        account.status = SchemeAccount.Status.ACTIVE
        account.save(update_fields=["status", "updated_at"])

    record_audit_event(
        action=AuditEvent.Action.REVERSAL,
        actor=processed_by,
        reason=normalized_reason,
        scheme_account=account,
        redemption=locked_redemption,
        details={
            "reversal_number": reversal.reversal_number,
            "redemption_number": locked_redemption.redemption_number,
            "amount": str(locked_redemption.entitlement_amount),
            "unit": locked_redemption.entitlement_unit,
        },
    )
    return reversal


@transaction.atomic
def record_scheme_plan_change(*, plan, actor, reason, before):
    _validate_owner(actor)
    after = {
        key: str(getattr(plan, key))
        for key in before
    }
    changed = {
        key: {"from": str(before[key]), "to": after[key]}
        for key in before
        if str(before[key]) != after[key]
    }
    if not changed:
        return None
    return record_audit_event(
        action=AuditEvent.Action.SCHEME_CHANGE,
        actor=actor,
        reason=reason,
        scheme_plan=plan,
        details={"changes": changed},
    )
