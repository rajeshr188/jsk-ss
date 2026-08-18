from dataclasses import dataclass
from datetime import datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.core.exceptions import ImproperlyConfigured
from django.db.models import Count, DecimalField, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from .models import Contribution, Customer, MetalAllocation, RateSnapshot, SchemeAccount
from .rates import MetalRateProviderError, get_metal_rate_provider


MONEY_QUANTUM = Decimal("0.01")
SUCCESSFUL_PAYMENT_STATUSES = (
    Contribution.Status.PAID,
    Contribution.Status.PAID_UNALLOCATED,
)


@dataclass(frozen=True)
class MetalLiability:
    metal: str
    quantity: Decimal
    reference_rate: Decimal | None = None
    indicative_exposure: Decimal | None = None
    rate_provider: str | None = None
    rate_timestamp: datetime | None = None
    rate_error: str | None = None


@dataclass(frozen=True)
class OwnerLiabilitySummary:
    cash_principal: Decimal
    gold: MetalLiability
    silver: MetalLiability


@dataclass(frozen=True)
class OwnerActivitySummary:
    customer_count: int
    active_account_count: int
    contribution_count_today: int
    contribution_count_month: int
    unallocated_payment_count: int


def get_customer_scheme_summary(user):
    return (
        SchemeAccount.objects.filter(customer__user=user)
        .select_related("plan", "customer")
        .annotate(
            cash_balance=Coalesce(
                Sum(
                    "contributions__amount",
                    filter=Q(contributions__status=Contribution.Status.PAID),
                ),
                Value(Decimal("0.00")),
                output_field=DecimalField(max_digits=14, decimal_places=2),
            ),
            metal_balance=Coalesce(
                Sum(
                    "contributions__metal_allocation__quantity",
                    filter=Q(
                        contributions__status=Contribution.Status.PAID,
                        contributions__metal_allocation__isnull=False,
                    ),
                ),
                Value(Decimal("0.000000")),
                output_field=DecimalField(max_digits=18, decimal_places=6),
            ),
        )
    )


def get_owner_customers():
    return Customer.objects.select_related("user").prefetch_related("scheme_accounts")


def get_owner_customer(customer_id):
    return Customer.objects.select_related("user").prefetch_related(
        "scheme_accounts__plan"
    ).get(pk=customer_id)


def get_customer_scheme_account(user, scheme_number):
    return get_customer_scheme_summary(user).filter(scheme_number=scheme_number).first()


def get_contribution_history(scheme_account):
    return scheme_account.contributions.select_related("metal_allocation__rate_snapshot")


def get_owner_contributions():
    return Contribution.objects.select_related(
        "scheme_account",
        "scheme_account__customer",
        "scheme_account__plan",
        "metal_allocation",
        "metal_allocation__rate_snapshot",
    )


def get_cash_balance(scheme_account):
    if scheme_account.savings_mode != SchemeAccount.SavingsMode.CASH:
        return Decimal("0.00")
    return scheme_account.contributions.filter(status=Contribution.Status.PAID).aggregate(
        total=Coalesce(
            Sum("amount"),
            Value(Decimal("0.00")),
            output_field=DecimalField(max_digits=14, decimal_places=2),
        )
    )["total"]


def get_metal_balance(scheme_account):
    if scheme_account.savings_mode not in {
        SchemeAccount.SavingsMode.GOLD,
        SchemeAccount.SavingsMode.SILVER,
    }:
        return Decimal("0.000000")
    return MetalAllocation.objects.filter(
        contribution__scheme_account=scheme_account,
        contribution__status=Contribution.Status.PAID,
        metal=scheme_account.savings_mode,
    ).aggregate(
        total=Coalesce(
            Sum("quantity"),
            Value(Decimal("0.000000")),
            output_field=DecimalField(max_digits=18, decimal_places=6),
        )
    )["total"]


def get_owner_liability_summary(rate_provider=None):
    cash_principal = Contribution.objects.filter(
        status=Contribution.Status.PAID,
        scheme_account__savings_mode=SchemeAccount.SavingsMode.CASH,
    ).aggregate(
        total=Coalesce(
            Sum("amount"),
            Value(Decimal("0.00")),
            output_field=DecimalField(max_digits=14, decimal_places=2),
        )
    )["total"]

    metal_totals = MetalAllocation.objects.filter(
        contribution__status=Contribution.Status.PAID,
    ).aggregate(
        gold=Coalesce(
            Sum("quantity", filter=Q(metal=RateSnapshot.Metal.GOLD)),
            Value(Decimal("0.000000")),
            output_field=DecimalField(max_digits=18, decimal_places=6),
        ),
        silver=Coalesce(
            Sum("quantity", filter=Q(metal=RateSnapshot.Metal.SILVER)),
            Value(Decimal("0.000000")),
            output_field=DecimalField(max_digits=18, decimal_places=6),
        ),
    )

    try:
        provider = rate_provider or get_metal_rate_provider()
    except (ImproperlyConfigured, MetalRateProviderError) as error:
        rate_error = str(error)
        gold = MetalLiability(
            metal=SchemeAccount.SavingsMode.GOLD,
            quantity=metal_totals["gold"],
            rate_error=rate_error,
        )
        silver = MetalLiability(
            metal=SchemeAccount.SavingsMode.SILVER,
            quantity=metal_totals["silver"],
            rate_error=rate_error,
        )
    else:
        gold = _get_current_metal_liability(
            provider, SchemeAccount.SavingsMode.GOLD, metal_totals["gold"]
        )
        silver = _get_current_metal_liability(
            provider, SchemeAccount.SavingsMode.SILVER, metal_totals["silver"]
        )

    return OwnerLiabilitySummary(
        cash_principal=cash_principal,
        gold=gold,
        silver=silver,
    )


def _get_current_metal_liability(provider, metal, quantity):
    try:
        quote = provider.get_rate(metal)
    except (ImproperlyConfigured, MetalRateProviderError) as error:
        return MetalLiability(metal=metal, quantity=quantity, rate_error=str(error))

    return MetalLiability(
        metal=metal,
        quantity=quantity,
        reference_rate=quote.applied_rate,
        indicative_exposure=(quantity * quote.applied_rate).quantize(
            MONEY_QUANTUM, rounding=ROUND_HALF_UP
        ),
        rate_provider=quote.provider,
        rate_timestamp=quote.provider_timestamp,
    )


def get_owner_activity_summary(as_of=None):
    local_date = as_of or timezone.localdate()
    current_timezone = timezone.get_current_timezone()
    day_start = timezone.make_aware(datetime.combine(local_date, time.min), current_timezone)
    day_end = day_start + timedelta(days=1)
    month_start_date = local_date.replace(day=1)
    month_start = timezone.make_aware(
        datetime.combine(month_start_date, time.min), current_timezone
    )
    if local_date.month == 12:
        next_month_date = local_date.replace(
            year=local_date.year + 1, month=1, day=1
        )
    else:
        next_month_date = local_date.replace(month=local_date.month + 1, day=1)
    next_month = timezone.make_aware(
        datetime.combine(next_month_date, time.min), current_timezone
    )

    contribution_counts = Contribution.objects.aggregate(
        today=Count(
            "pk",
            filter=Q(
                status__in=SUCCESSFUL_PAYMENT_STATUSES,
                paid_at__gte=day_start,
                paid_at__lt=day_end,
            ),
        ),
        month=Count(
            "pk",
            filter=Q(
                status__in=SUCCESSFUL_PAYMENT_STATUSES,
                paid_at__gte=month_start,
                paid_at__lt=next_month,
            ),
        ),
        unallocated=Count(
            "pk",
            filter=Q(status=Contribution.Status.PAID_UNALLOCATED),
        ),
    )
    return OwnerActivitySummary(
        customer_count=Customer.objects.count(),
        active_account_count=SchemeAccount.objects.exclude(
            status=SchemeAccount.Status.REDEEMED
        ).count(),
        contribution_count_today=contribution_counts["today"],
        contribution_count_month=contribution_counts["month"],
        unallocated_payment_count=contribution_counts["unallocated"],
    )
