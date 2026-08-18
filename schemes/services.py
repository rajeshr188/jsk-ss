import calendar
import secrets
from datetime import date

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import Customer, SchemeAccount, SchemePlan


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
