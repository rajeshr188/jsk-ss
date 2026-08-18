from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.core.exceptions import ImproperlyConfigured
from django.db.models import Case, Count, DecimalField, F, OuterRef, Q, Subquery, Sum, Value, When
from django.db.models.functions import Coalesce
from django.utils import timezone

from .bonuses import cash_bonus_policy_for_account
from .models import (
    AuditEvent,
    Contribution,
    Customer,
    MetalAllocation,
    PaymentWebhookEvent,
    RateSnapshot,
    Redemption,
    SchemeAccount,
)
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
    cash_earned_bonus: Decimal
    cash_projected_bonus: Decimal
    gold: MetalLiability
    silver: MetalLiability

    @property
    def cash_redeemable_amount(self):
        return self.cash_principal + self.cash_earned_bonus


@dataclass(frozen=True)
class CashBonusSummary:
    principal_paid: Decimal
    principal_outstanding: Decimal
    earned_bonus: Decimal
    projected_bonus: Decimal
    redeemable_amount: Decimal
    policy_version: str
    percentage: Decimal
    minimum_qualifying_months: int
    contract_qualifies: bool


@dataclass(frozen=True)
class OwnerActivitySummary:
    customer_count: int
    active_account_count: int
    contribution_count_today: int
    contribution_count_month: int
    unallocated_payment_count: int


@dataclass(frozen=True)
class RedemptionEligibilitySummary:
    as_of: date
    eligible_now: tuple
    next_30_days: tuple
    next_60_days: tuple
    next_90_days: tuple
    later: tuple
    redeemed: tuple

    @property
    def eligible_now_count(self):
        return len(self.eligible_now)

    @property
    def next_30_days_count(self):
        return len(self.next_30_days)

    @property
    def next_60_days_count(self):
        return len(self.next_60_days)

    @property
    def next_90_days_count(self):
        return len(self.next_90_days)


@dataclass(frozen=True)
class OwnerExceptionItem:
    category: str
    detected_at: datetime
    detail: str
    contribution: Contribution | None = None
    webhook_event: PaymentWebhookEvent | None = None

    @property
    def scheme_account(self):
        if self.contribution is not None:
            return self.contribution.scheme_account
        if self.webhook_event and self.webhook_event.contribution_id:
            return self.webhook_event.contribution.scheme_account
        return None


def get_customer_scheme_summary(user):
    money_field = DecimalField(max_digits=14, decimal_places=2)
    metal_field = DecimalField(max_digits=18, decimal_places=6)
    cash_contributions = (
        Contribution.objects.filter(
            scheme_account=OuterRef("pk"),
            status=Contribution.Status.PAID,
        )
        .values("scheme_account")
        .annotate(total=Sum("amount"))
        .values("total")
    )
    metal_allocations = (
        MetalAllocation.objects.filter(
            contribution__scheme_account=OuterRef("pk"),
            contribution__status=Contribution.Status.PAID,
        )
        .values("contribution__scheme_account")
        .annotate(total=Sum("quantity"))
        .values("total")
    )
    cash_redemptions = (
        Redemption.objects.filter(
            scheme_account=OuterRef("pk"),
            status=Redemption.Status.COMPLETED,
            reversal__isnull=True,
        )
        .values("scheme_account")
        .annotate(total=Sum("cash_principal_amount"))
        .values("total")
    )
    gold_redemptions = (
        Redemption.objects.filter(
            scheme_account=OuterRef("pk"),
            status=Redemption.Status.COMPLETED,
            reversal__isnull=True,
        )
        .values("scheme_account")
        .annotate(total=Sum("gold_quantity"))
        .values("total")
    )
    silver_redemptions = (
        Redemption.objects.filter(
            scheme_account=OuterRef("pk"),
            status=Redemption.Status.COMPLETED,
            reversal__isnull=True,
        )
        .values("scheme_account")
        .annotate(total=Sum("silver_quantity"))
        .values("total")
    )
    return (
        SchemeAccount.objects.filter(customer__user=user)
        .select_related("plan", "customer")
        .annotate(
            cash_contributed=Coalesce(
                Subquery(cash_contributions, output_field=money_field),
                Value(Decimal("0.00")),
                output_field=money_field,
            ),
            metal_allocated=Coalesce(
                Subquery(metal_allocations, output_field=metal_field),
                Value(Decimal("0.000000")),
                output_field=metal_field,
            ),
            cash_redeemed=Coalesce(
                Subquery(cash_redemptions, output_field=money_field),
                Value(Decimal("0.00")),
                output_field=money_field,
            ),
            gold_redeemed=Coalesce(
                Subquery(gold_redemptions, output_field=metal_field),
                Value(Decimal("0.000000")),
                output_field=metal_field,
            ),
            silver_redeemed=Coalesce(
                Subquery(silver_redemptions, output_field=metal_field),
                Value(Decimal("0.000000")),
                output_field=metal_field,
            ),
        )
        .annotate(
            cash_balance=F("cash_contributed") - F("cash_redeemed"),
            metal_balance=Case(
                When(
                    savings_mode=SchemeAccount.SavingsMode.GOLD,
                    then=F("metal_allocated") - F("gold_redeemed"),
                ),
                When(
                    savings_mode=SchemeAccount.SavingsMode.SILVER,
                    then=F("metal_allocated") - F("silver_redeemed"),
                ),
                default=Value(Decimal("0.000000")),
                output_field=metal_field,
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


def get_redemption_history(scheme_account):
    return scheme_account.redemptions.select_related(
        "processed_by", "reversal", "reversal__processed_by"
    )


def get_owner_contributions():
    return Contribution.objects.select_related(
        "scheme_account",
        "scheme_account__customer",
        "scheme_account__plan",
        "metal_allocation",
        "metal_allocation__rate_snapshot",
    )


def get_owner_redemptions():
    return Redemption.objects.select_related(
        "scheme_account",
        "scheme_account__customer",
        "scheme_account__plan",
        "processed_by",
        "reversal",
        "reversal__processed_by",
    )


def get_owner_audit_events():
    return AuditEvent.objects.select_related(
        "actor",
        "scheme_plan",
        "scheme_account",
        "scheme_account__customer",
        "contribution",
        "rate_snapshot",
        "redemption",
    )


def get_owner_exception_queue():
    items = []
    unallocated = Contribution.objects.filter(
        status=Contribution.Status.PAID_UNALLOCATED
    ).select_related("scheme_account", "scheme_account__customer")
    for contribution in unallocated:
        items.append(
            OwnerExceptionItem(
                category="PAID_UNALLOCATED / failed allocation",
                detected_at=(
                    contribution.allocation_attempted_at or contribution.paid_at
                    or contribution.created_at
                ),
                detail=(
                    contribution.allocation_error
                    or "Verified payment is awaiting a metal allocation."
                ),
                contribution=contribution,
            )
        )

    failed_webhooks = PaymentWebhookEvent.objects.filter(
        status=PaymentWebhookEvent.Status.FAILED
    ).select_related(
        "contribution",
        "contribution__scheme_account",
        "contribution__scheme_account__customer",
    )
    for event in failed_webhooks:
        is_mismatch = "match" in event.error.lower()
        items.append(
            OwnerExceptionItem(
                category=(
                    "Payment mismatch / manual correction required"
                    if is_mismatch
                    else "Failed webhook reconciliation"
                ),
                detected_at=event.processed_at or event.received_at,
                detail=event.error or "Webhook processing failed.",
                webhook_event=event,
            )
        )
    return tuple(sorted(items, key=lambda item: item.detected_at, reverse=True))


def get_cash_balance(scheme_account):
    if scheme_account.savings_mode != SchemeAccount.SavingsMode.CASH:
        return Decimal("0.00")
    return get_cash_bonus_summary(scheme_account).principal_outstanding


def get_cash_bonus_summary(scheme_account, as_of=None):
    if scheme_account.savings_mode != SchemeAccount.SavingsMode.CASH:
        return CashBonusSummary(
            principal_paid=Decimal("0.00"),
            principal_outstanding=Decimal("0.00"),
            earned_bonus=Decimal("0.00"),
            projected_bonus=Decimal("0.00"),
            redeemable_amount=Decimal("0.00"),
            policy_version=scheme_account.cash_bonus_policy_version_snapshot,
            percentage=scheme_account.cash_bonus_percentage_snapshot,
            minimum_qualifying_months=(
                scheme_account.cash_bonus_minimum_months_snapshot
            ),
            contract_qualifies=False,
        )

    policy = cash_bonus_policy_for_account(scheme_account)
    paid_contributions = scheme_account.contributions.filter(
        status=Contribution.Status.PAID
    )
    principal_paid = paid_contributions.aggregate(
        total=Coalesce(
            Sum("amount"),
            Value(Decimal("0.00")),
            output_field=DecimalField(max_digits=14, decimal_places=2),
        )
    )["total"]
    redeemed = scheme_account.redemptions.filter(
        status=Redemption.Status.COMPLETED,
        reversal__isnull=True,
    ).aggregate(
        principal=Coalesce(
            Sum("cash_principal_amount"),
            Value(Decimal("0.00")),
            output_field=DecimalField(max_digits=14, decimal_places=2),
        ),
        bonus=Coalesce(
            Sum("cash_bonus_amount"),
            Value(Decimal("0.00")),
            output_field=DecimalField(max_digits=14, decimal_places=2),
        ),
    )
    principal_outstanding = max(
        principal_paid - redeemed["principal"],
        Decimal("0.00"),
    )
    as_of = as_of or timezone.localdate()
    contract_qualifies = policy.contract_qualifies(scheme_account.agreed_months)
    earned_bonus = Decimal("0.00")
    projected_bonus = Decimal("0.00")
    if contract_qualifies and as_of >= scheme_account.eligible_from:
        local_timezone = timezone.get_current_timezone()
        cutoff = timezone.make_aware(
            datetime.combine(
                scheme_account.eligible_from + timedelta(days=1),
                time.min,
            ),
            local_timezone,
        )
        qualifying_principal = paid_contributions.filter(
            paid_at__lt=cutoff
        ).aggregate(
            total=Coalesce(
                Sum("amount"),
                Value(Decimal("0.00")),
                output_field=DecimalField(max_digits=14, decimal_places=2),
            )
        )["total"]
        earned_bonus = max(
            policy.calculate(qualifying_principal) - redeemed["bonus"],
            Decimal("0.00"),
        )
    elif contract_qualifies:
        projected_bonus = policy.calculate(principal_paid)

    return CashBonusSummary(
        principal_paid=principal_paid,
        principal_outstanding=principal_outstanding,
        earned_bonus=earned_bonus,
        projected_bonus=projected_bonus,
        redeemable_amount=principal_outstanding + earned_bonus,
        policy_version=policy.version,
        percentage=policy.percentage,
        minimum_qualifying_months=policy.minimum_qualifying_months,
        contract_qualifies=contract_qualifies,
    )


def get_metal_balance(scheme_account):
    if scheme_account.savings_mode not in {
        SchemeAccount.SavingsMode.GOLD,
        SchemeAccount.SavingsMode.SILVER,
    }:
        return Decimal("0.000000")
    allocated = MetalAllocation.objects.filter(
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
    field_name = (
        "gold_quantity"
        if scheme_account.savings_mode == SchemeAccount.SavingsMode.GOLD
        else "silver_quantity"
    )
    redeemed = scheme_account.redemptions.filter(
        status=Redemption.Status.COMPLETED,
        reversal__isnull=True,
    ).aggregate(
        total=Coalesce(
            Sum(field_name),
            Value(Decimal("0.000000")),
            output_field=DecimalField(max_digits=18, decimal_places=6),
        )
    )["total"]
    return allocated - redeemed


def get_outstanding_entitlement(scheme_account):
    if scheme_account.savings_mode == SchemeAccount.SavingsMode.CASH:
        return get_cash_bonus_summary(scheme_account).redeemable_amount
    return get_metal_balance(scheme_account)


def get_owner_liability_summary(rate_provider=None):
    cash_summaries = (
        get_cash_bonus_summary(account)
        for account in SchemeAccount.objects.filter(
            savings_mode=SchemeAccount.SavingsMode.CASH
        )
    )
    cash_principal = Decimal("0.00")
    cash_earned_bonus = Decimal("0.00")
    cash_projected_bonus = Decimal("0.00")
    for summary in cash_summaries:
        cash_principal += summary.principal_outstanding
        cash_earned_bonus += summary.earned_bonus
        cash_projected_bonus += summary.projected_bonus

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
    metal_redeemed = Redemption.objects.filter(
        status=Redemption.Status.COMPLETED,
        reversal__isnull=True,
    ).aggregate(
        gold=Coalesce(
            Sum("gold_quantity"),
            Value(Decimal("0.000000")),
            output_field=DecimalField(max_digits=18, decimal_places=6),
        ),
        silver=Coalesce(
            Sum("silver_quantity"),
            Value(Decimal("0.000000")),
            output_field=DecimalField(max_digits=18, decimal_places=6),
        ),
    )
    metal_totals["gold"] -= metal_redeemed["gold"]
    metal_totals["silver"] -= metal_redeemed["silver"]

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
        cash_earned_bonus=cash_earned_bonus,
        cash_projected_bonus=cash_projected_bonus,
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


def get_redemption_eligibility_summary(as_of=None):
    as_of = as_of or timezone.localdate()
    day_30 = as_of + timedelta(days=30)
    day_60 = as_of + timedelta(days=60)
    day_90 = as_of + timedelta(days=90)
    open_accounts = list(
        SchemeAccount.objects.exclude(status=SchemeAccount.Status.REDEEMED)
        .select_related("customer", "plan")
        .order_by("eligible_from", "scheme_number")
    )
    redeemed = tuple(
        SchemeAccount.objects.filter(status=SchemeAccount.Status.REDEEMED)
        .select_related("customer", "plan")
        .order_by("-eligible_from", "scheme_number")
    )
    return RedemptionEligibilitySummary(
        as_of=as_of,
        eligible_now=tuple(
            account for account in open_accounts if account.eligible_from <= as_of
        ),
        next_30_days=tuple(
            account
            for account in open_accounts
            if as_of < account.eligible_from <= day_30
        ),
        next_60_days=tuple(
            account
            for account in open_accounts
            if day_30 < account.eligible_from <= day_60
        ),
        next_90_days=tuple(
            account
            for account in open_accounts
            if day_60 < account.eligible_from <= day_90
        ),
        later=tuple(
            account for account in open_accounts if account.eligible_from > day_90
        ),
        redeemed=redeemed,
    )
