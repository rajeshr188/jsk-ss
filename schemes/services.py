import calendar
import secrets
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db import transaction
from django.utils import timezone

from .models import (
    Contribution,
    Customer,
    MetalAllocation,
    RateSnapshot,
    SchemeAccount,
    SchemePlan,
)
from .payments import get_payment_gateway
from .rates import MetalRateProviderError, get_metal_rate_provider


MONEY_QUANTUM = Decimal("0.01")
METAL_QUANTUM = Decimal("0.000001")
SUCCESSFUL_PAYMENT_STATUSES = (
    Contribution.Status.PAID,
    Contribution.Status.PAID_UNALLOCATED,
)
EXPECTED_ALLOCATION_ERRORS = (
    ImproperlyConfigured,
    MetalRateProviderError,
    ValidationError,
)


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
def create_customer(*, full_name, email, mobile_number, address="", password):
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
def enroll_customer(*, customer, plan, savings_mode, start_date=None, agreed_months=None):
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
    )
    account.full_clean()
    account.save()
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


def validate_contribution_allowed(
    scheme_account,
    amount,
    contribution_date=None,
    *,
    contribution_period=None,
    exclude_contribution_id=None,
):
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


@transaction.atomic
def initiate_contribution(
    *, scheme_account, amount, payment_gateway, contribution_date=None
):
    locked_account = SchemeAccount.objects.select_for_update().get(pk=scheme_account.pk)
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
    )
    contribution.full_clean()
    contribution.save()
    return contribution


@transaction.atomic
def confirm_contribution(
    *, contribution_id, payment_gateway, gateway_reference, verified
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
    if not verified:
        raise ValidationError("Payment success was not verified server-side.")
    if contribution.payment_gateway != payment_gateway:
        raise ValidationError("Payment gateway does not match the initiated contribution.")
    if not gateway_reference:
        raise ValidationError("A verified gateway reference is required.")

    validate_contribution_allowed(
        contribution.scheme_account,
        contribution.amount,
        timezone.localdate(),
        contribution_period=contribution.contribution_period,
        exclude_contribution_id=contribution.pk,
    )
    contribution.status = Contribution.Status.PAID
    contribution.gateway_reference = gateway_reference
    contribution.paid_at = timezone.now()
    contribution.full_clean()
    contribution.save(update_fields=["status", "gateway_reference", "paid_at"])
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


@transaction.atomic
def allocate_metal(*, contribution, rate_provider=None):
    locked_contribution = (
        Contribution.objects.select_for_update()
        .select_related("scheme_account")
        .get(pk=contribution.pk)
    )
    existing = MetalAllocation.objects.filter(contribution=locked_contribution).select_related(
        "rate_snapshot"
    ).first()
    if existing is not None:
        if locked_contribution.status == Contribution.Status.PAID_UNALLOCATED:
            locked_contribution.status = Contribution.Status.PAID
            locked_contribution.allocation_error = ""
            locked_contribution.save(update_fields=["status", "allocation_error"])
        return existing
    if locked_contribution.status not in SUCCESSFUL_PAYMENT_STATUSES:
        raise ValidationError("Only a paid contribution can receive a metal allocation.")

    metal = locked_contribution.scheme_account.savings_mode
    if metal not in {RateSnapshot.Metal.GOLD, RateSnapshot.Metal.SILVER}:
        raise ValidationError("Cash contributions do not receive a metal allocation.")
    provider = rate_provider or get_metal_rate_provider()
    quote = provider.get_rate(metal)
    if quote.metal != metal:
        raise ValidationError("The rate quote metal does not match the scheme.")
    if quote.applied_rate <= 0 or quote.provider_rate <= 0:
        raise ValidationError("Metal rates must be greater than zero.")

    snapshot = RateSnapshot(
        metal=quote.metal,
        provider=quote.provider,
        provider_timestamp=quote.provider_timestamp,
        provider_rate=quote.provider_rate,
        applied_rate=quote.applied_rate,
        purity=quote.purity,
    )
    snapshot.full_clean()
    snapshot.save()

    quantity = (locked_contribution.amount / snapshot.applied_rate).quantize(
        METAL_QUANTUM, rounding=ROUND_HALF_UP
    )
    if quantity <= 0:
        raise ValidationError("The contribution is too small to allocate at 6 decimal places.")
    allocation = MetalAllocation(
        contribution=locked_contribution,
        rate_snapshot=snapshot,
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


def retry_metal_allocation(*, contribution, rate_provider=None):
    try:
        return allocate_metal(contribution=contribution, rate_provider=rate_provider)
    except Exception as error:
        mark_contribution_paid_unallocated(
            contribution_id=contribution.pk,
            error=error,
        )
        raise


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
    if contribution.scheme_account.savings_mode in {
        SchemeAccount.SavingsMode.GOLD,
        SchemeAccount.SavingsMode.SILVER,
    }:
        try:
            retry_metal_allocation(contribution=contribution)
        except EXPECTED_ALLOCATION_ERRORS:
            return Contribution.objects.select_related("scheme_account").get(
                pk=contribution.pk
            )
    return contribution
