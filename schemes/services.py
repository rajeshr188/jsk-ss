import calendar
import hashlib
import secrets
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import (
    Contribution,
    Customer,
    MetalAllocation,
    PaymentWebhookEvent,
    RateSnapshot,
    Redemption,
    SchemeAccount,
    SchemePlan,
)
from .payments import PaymentGatewayError, get_payment_gateway
from .rates import MetalRateProviderError, get_metal_rate_provider
from .selectors import get_outstanding_entitlement


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
    if not verified:
        raise ValidationError("Payment success was not verified server-side.")
    if contribution.payment_gateway != payment_gateway:
        raise ValidationError("Payment gateway does not match the initiated contribution.")
    if not gateway_reference:
        raise ValidationError("A verified gateway reference is required.")

    validate_contribution_confirmation_allowed(contribution)
    contribution.status = Contribution.Status.PAID
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


def _apply_contribution_entitlement(contribution):
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


def initiate_razorpay_contribution(
    *, scheme_account, amount, contribution_date=None, gateway=None
):
    gateway = gateway or get_payment_gateway()
    if gateway.name != "razorpay":
        raise ImproperlyConfigured("The Razorpay payment gateway is not configured.")

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
    if contribution is None:
        try:
            contribution = initiate_contribution(
                scheme_account=scheme_account,
                amount=normalized_amount,
                payment_gateway=gateway.name,
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

    order_error = None
    with transaction.atomic():
        contribution = Contribution.objects.select_for_update().get(pk=contribution.pk)
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
    if not contribution.gateway_order_id or callback_order_id != contribution.gateway_order_id:
        raise ValidationError("The Razorpay order does not match this contribution.")
    if contribution.status in SUCCESSFUL_PAYMENT_STATUSES:
        if contribution.gateway_reference != payment_id:
            raise ValidationError("This contribution has already been confirmed.")
        return _apply_contribution_entitlement(contribution)

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


def process_razorpay_webhook(*, event_id, body, payload):
    payload_hash = hashlib.sha256(body).hexdigest()
    event_type = payload.get("event") if isinstance(payload, dict) else None
    if not isinstance(event_type, str) or not event_type:
        raise ValidationError("Razorpay webhook event type is missing.")
    event, _ = PaymentWebhookEvent.objects.get_or_create(
        gateway="razorpay",
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
    }:
        return event

    try:
        if event_type != "payment.captured":
            event.status = PaymentWebhookEvent.Status.IGNORED
            event.processed_at = timezone.now()
            event.error = ""
            event.save(update_fields=["status", "processed_at", "error"])
            return event

        payment = payload.get("payload", {}).get("payment", {}).get("entity", {})
        payment_id = payment.get("id")
        order_id = payment.get("order_id")
        if not isinstance(payment_id, str) or not isinstance(order_id, str):
            raise ValidationError("Razorpay payment identifiers are missing.")
        contribution = Contribution.objects.select_related("scheme_account").get(
            payment_gateway="razorpay",
            gateway_order_id=order_id,
        )
        if (
            payment.get("status") != "captured"
            or payment.get("captured") is not True
            or payment.get("currency") != "INR"
            or payment.get("amount") != int(contribution.amount * 100)
        ):
            raise ValidationError("Razorpay webhook payment details do not match.")

        contribution = confirm_contribution(
            contribution_id=contribution.pk,
            payment_gateway="razorpay",
            gateway_reference=payment_id,
            verified=True,
        )
        contribution = _apply_contribution_entitlement(contribution)
        event.status = PaymentWebhookEvent.Status.PROCESSED
        event.contribution = contribution
        event.gateway_order_id = order_id
        event.gateway_reference = payment_id
        event.error = ""
        event.processed_at = timezone.now()
        event.save(
            update_fields=[
                "status",
                "contribution",
                "gateway_order_id",
                "gateway_reference",
                "error",
                "processed_at",
            ]
        )
        return event
    except (Contribution.DoesNotExist, ValidationError) as error:
        event.status = PaymentWebhookEvent.Status.FAILED
        event.error = str(error).strip()[:1000]
        event.processed_at = timezone.now()
        event.save(update_fields=["status", "error", "processed_at"])
        raise ValidationError(event.error) from None


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
    if normalized_amount == outstanding:
        account.status = SchemeAccount.Status.REDEEMED
        account.save(update_fields=["status", "updated_at"])
    return redemption
