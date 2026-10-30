from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .inr_settlement_selectors import InrSettlementBalance
    from .statement_selectors import BenefitDocument

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Case, Count, DecimalField, Exists, F, OuterRef, Q, Subquery, Sum, Value, When
from django.db.models.functions import Coalesce
from django.utils import timezone

from accounts.models import CustomerInvitation, CustomerRegistration

from .bonuses import cash_bonus_policy_for_account
from .eligibility import eligibility_days_until, is_redemption_eligible
from .models import (
    AuditEvent,
    Contribution,
    Customer,
    GatewayMode,
    InStoreCashContributionReversal,
    InStoreCashReceipt,
    MetalAllocation,
    MetalGrade,
    PaymentChannel,
    PaymentWebhookEvent,
    SchemeRate,
    Redemption,
    SchemeAccount,
    SchemeEnrolmentRequest,
    SchemePlan,
    SchemeReminder,
)


MONEY_QUANTUM = Decimal("0.01")


def get_owner_plan_configuration(*, closed=False):
    return SchemePlan.objects.filter(catalogue_closure__isnull=not closed).annotate(
        agreement_count=Count("scheme_accounts", distinct=True),
        offered_grade_count=Count("metal_offerings", filter=Q(metal_offerings__active=True), distinct=True),
    ).select_related("configuration", "catalogue_closure").prefetch_related("metal_offerings__metal_grade")


def get_plan_configurations(*, closed=False):
    from .models import SchemePlanConfiguration
    return (SchemePlanConfiguration.objects.filter(catalogue_closure__isnull=not closed).annotate(plan_count=Count("plans"))
            .select_related("created_by", "catalogue_closure").order_by("name", "family_id", "-version", "pk"))


def get_plan_edit_impact(plan):
    return {
        "agreements": plan.scheme_accounts.count(),
        "latest_revision": plan.revisions.first(),
        "recent_revisions": plan.revisions.all()[:5],
    }


SUCCESSFUL_PAYMENT_STATUSES = (
    Contribution.Status.PAID,
    Contribution.Status.PAID_UNALLOCATED,
)
RECEIPT_PAYMENT_STATUSES = (*SUCCESSFUL_PAYMENT_STATUSES, Contribution.Status.REVERSED)


@dataclass(frozen=True)
class MetalLiability:
    metal_grade: MetalGrade
    quantity: Decimal
    scheme_rate: Decimal | None = None
    indicative_exposure: Decimal | None = None
    rate_published_at: datetime | None = None


@dataclass(frozen=True)
class OwnerLiabilitySummary:
    cash_principal: Decimal
    cash_earned_bonus: Decimal
    cash_projected_bonus: Decimal
    metal_grades: tuple[MetalLiability, ...]
    inr_purchase_principal: Decimal = Decimal("0.00")

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
class InStoreCashDailySummary:
    as_of: date
    receipts_count: int
    received_amount: Decimal
    reversals_count: int
    reversed_amount: Decimal

    @property
    def net_amount(self):
        return self.received_amount - self.reversed_amount


@dataclass(frozen=True)
class OwnerContributionDailySummary:
    cash: InStoreCashDailySummary
    razorpay_count: int
    razorpay_amount: Decimal
    verified_count: int
    verified_amount: Decimal

    @property
    def as_of(self):
        return self.cash.as_of


@dataclass(frozen=True)
class RedemptionEligibilitySummary:
    as_of: date
    eligible_now: tuple
    next_30_days: tuple
    next_60_days: tuple
    next_90_days: tuple
    later: tuple
    redeemed: tuple
    configured: tuple = ()

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
    queue_kind: str = "allocation"

    @property
    def scheme_account(self):
        if self.contribution is not None:
            return self.contribution.scheme_account
        if self.webhook_event and self.webhook_event.contribution_id:
            return self.webhook_event.contribution.scheme_account
        return None

    @property
    def recovery_available(self):
        return bool(
            self.webhook_event and self.webhook_event.gateway == "razorpay"
            and self.webhook_event.event_type == "payment.captured"
        )


@dataclass(frozen=True)
class FinancialExceptionCounts:
    paid_unallocated: int
    failed_webhooks: int
    mismatched_webhooks: int
    expired_checkouts: int = 0
    unresolved_optional_orders: int = 0
    refund_disposition_errors: int = 0

    @property
    def total(self):
        return self.paid_unallocated + self.failed_webhooks + self.expired_checkouts + self.unresolved_optional_orders + self.refund_disposition_errors


@dataclass(frozen=True)
class ContributionReceiptSummary:
    receipt_number: str
    contribution: Contribution
    allocation: MetalAllocation | None
    principal_amount: Decimal | None = None


@dataclass(frozen=True)
class MetalAcquisitionSummary:
    paid_amount: Decimal
    allocated_grams: Decimal
    average_cost_per_gram: Decimal | None


@dataclass(frozen=True)
class StatementEntry:
    occurred_at: datetime
    description: str
    reference: str
    status: str
    amount_inr: Decimal | None = None
    scheme_rate: Decimal | None = None
    metal_allocation: Decimal | None = None
    metal_reversal: Decimal | None = None
    redemption: Decimal | None = None
    restoration: Decimal | None = None
    entitlement_unit: str = ""
    contribution_id: int | None = None
    payment_label: str = ""
    practice_record: bool = False
    invoice_reference: str = ""
    settlement_basis: str = ""
    principal_credit: Decimal | None = None
    principal_debit: Decimal | None = None
    benefit_amount: Decimal | None = None
    detail: str = ""


@dataclass(frozen=True)
class SchemeStatement:
    scheme_account: SchemeAccount
    generated_at: datetime
    entries: tuple[StatementEntry, ...]
    remaining_entitlement: Decimal
    entitlement_unit: str
    cash_bonus: CashBonusSummary | None = None
    inr_balance: "InrSettlementBalance | None" = None
    benefit: "BenefitDocument | None" = None

    @property
    def includes_practice_activity(self):
        return any(entry.practice_record for entry in self.entries)


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
        .select_related("plan", "customer", "metal_grade")
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


def get_owner_customers(*, search=""):
    customers = Customer.objects.select_related("user").annotate(
        scheme_account_count=Count("scheme_accounts", distinct=True)
    )
    if search:
        customers = customers.filter(
            Q(full_name__icontains=search) | Q(email__icontains=search)
            | Q(mobile_number__icontains=search) | Q(customer_number__icontains=search)
            | Q(scheme_accounts__scheme_number__icontains=search)
        ).distinct()
    return customers.order_by("full_name", "pk")


def get_filtered_owner_payments(*, customer=None, contribution_id=None, filters=None):
    """One read scope shared by on-screen records and the recorded-payment export."""
    rows = get_owner_contributions()
    if customer is not None:
        rows = rows.filter(scheme_account__customer=customer)
    if contribution_id is not None:
        rows = rows.filter(pk=contribution_id)
    values = filters or {}
    if values.get("q"):
        value = values["q"]
        rows = rows.filter(
            Q(scheme_account__customer__full_name__icontains=value)
            | Q(scheme_account__customer__email__icontains=value)
            | Q(scheme_account__customer__customer_number__icontains=value)
            | Q(scheme_account__scheme_number__icontains=value)
            | Q(scheme_account__plan__name__icontains=value)
            | Q(scheme_account__plan_name_snapshot__icontains=value)
            | Q(scheme_account__plan__code__icontains=value)
            | Q(scheme_account__plan_code_snapshot__icontains=value)
            | Q(gateway_reference__icontains=value) | Q(gateway_order_id__icontains=value)
            | Q(cash_receipt__paper_receipt_number__icontains=value)
        )
    for field, key in (("status", "status"), ("payment_gateway", "method"), ("gateway_mode", "mode")):
        if values.get(key):
            rows = rows.filter(**{field: values[key]})
    if values.get("start"):
        rows = rows.filter(created_at__date__gte=values["start"])
    if values.get("end"):
        rows = rows.filter(created_at__date__lte=values["end"])
    return rows.order_by("-created_at", "-pk")


def get_payment_scope_summary(rows):
    return rows.aggregate(
        record_count=Count("pk"),
        received_amount=Coalesce(Sum("amount", filter=Q(status__in=SUCCESSFUL_PAYMENT_STATUSES) & (Q(payment_gateway="in_store_cash") | Q(payment_gateway="razorpay", gateway_mode="live"))), Decimal("0.00")),
        test_amount=Coalesce(Sum("amount", filter=Q(status__in=SUCCESSFUL_PAYMENT_STATUSES) & (Q(payment_gateway="mock") | Q(payment_gateway="razorpay", gateway_mode="test"))), Decimal("0.00")),
        reversed_amount=Coalesce(Sum("amount", filter=Q(status="REVERSED")), Decimal("0.00")),
    )


def get_cash_entry_blocker(account):
    """Read-only early guidance. The existing preview/commit services remain authority."""
    from django.core.exceptions import ValidationError
    from .services import preview_in_store_cash_contribution
    pending = Contribution.objects.filter(scheme_account=account, status="PENDING", payment_gateway="razorpay").order_by("created_at", "pk").first()
    if pending:
        return {"message": "An online payment is awaiting reconciliation. Resolve that recorded attempt before accepting cash for this plan.", "contribution": pending}
    try:
        preview_in_store_cash_contribution(
            scheme_account=account,
            amount=account.fixed_amount_snapshot if account.amount_rule_snapshot == "FIXED" else account.minimum_amount_snapshot,
        )
    except ValidationError as error:
        return {"message": " ".join(error.messages), "contribution": None}
    return None


def get_owner_readiness():
    from .operations import get_payment_availability
    grades = MetalGrade.objects.filter(
        Q(plan_offerings__active=True, plan_offerings__plan__active=True, plan_offerings__plan__publicly_listed=True)
        | Q(scheme_accounts__status="ACTIVE")
    ).distinct()
    return [{"grade": grade, "availability": get_payment_availability(metal_grade=grade)} for grade in grades]


def get_owner_application_keys(*, focus="attention", kind="all", customer=None, at=None, search=""):
    """Paginate both historical record types in SQL before loading review evidence."""
    at = at or timezone.now()
    registrations = CustomerRegistration.objects.all()
    plans = SchemeEnrolmentRequest.objects.all()
    if search:
        search = search.strip()[:100]
        registrations = registrations.filter(Q(full_name__icontains=search) | Q(email__icontains=search) | Q(mobile_number__icontains=search))
        plans = plans.filter(Q(customer__full_name__icontains=search) | Q(customer__email__icontains=search) | Q(customer__mobile_number__icontains=search) | Q(customer__customer_number__icontains=search))
    awaiting_details = Q(status="AWAITING_OWNER_APPROVAL", plan_application__completed_at__isnull=True,
                         plan_application__isnull=False, plan_application__expires_at__gt=at,
                         plan_application__progress_delivery_failed_at__isnull=True,
                         plan_application__progress_sent_at__isnull=False)
    registration_attention = (Q(status=CustomerRegistration.Status.AWAITING_OWNER_APPROVAL) & ~awaiting_details) | (
        Q(status=CustomerRegistration.Status.PENDING_EMAIL_VERIFICATION)
        & (Q(delivery_failed_at__isnull=False) | Q(email_verification_expires_at__lte=at))
    )
    if focus == "attention":
        registrations = registrations.filter(registration_attention)
        plans = plans.filter(status=SchemeEnrolmentRequest.Status.PENDING_OWNER_REVIEW)
    elif focus == "waiting":
        registrations = registrations.filter(awaiting_details | Q(
            status=CustomerRegistration.Status.PENDING_EMAIL_VERIFICATION,
            email_verification_expires_at__gt=at, delivery_failed_at__isnull=True,
        ))
        plans = plans.none()
    elif focus == "closed":
        registrations = registrations.filter(status__in=["APPROVED", "REJECTED", "EXPIRED"])
        plans = plans.exclude(status=SchemeEnrolmentRequest.Status.PENDING_OWNER_REVIEW)
    if customer:
        # Only the explicit approval link identifies an applicant as this customer.
        registrations = registrations.filter(approved_user_id=customer.user_id)
        plans = plans.filter(customer=customer)
    if kind == "registration":
        plans = plans.none()
    elif kind == "plan":
        registrations = registrations.filter(plan_application__isnull=False)
    registrations = registrations.order_by().annotate(
        queue_kind=Value("registration"), queue_date=F("submitted_at"),
        queue_priority=Case(
            When(status="AWAITING_OWNER_APPROVAL", then=Value(0)),
            When(registration_attention, then=Value(2)),
            When(status="PENDING_EMAIL_VERIFICATION", then=Value(3)), default=Value(4),
        ),
    ).values("pk", "queue_kind", "queue_date", "queue_priority")
    plans = plans.order_by().annotate(
        queue_kind=Value("plan"), queue_date=F("created_at"),
        queue_priority=Case(When(status="PENDING_OWNER_REVIEW", then=Value(1)), default=Value(4)),
    ).values("pk", "queue_kind", "queue_date", "queue_priority")
    return registrations.union(plans, all=True).order_by(
        "queue_priority", "queue_date", "queue_kind", "pk"
    )


def get_owner_application_stage_counts(*, kind="all", customer=None, search="", at=None):
    # Reuse the exact union/scope rules: a plan application is one queue record,
    # not its linked registration plus a second synthetic agreement application.
    at = at or timezone.now()
    return {focus: get_owner_application_keys(focus=focus, kind=kind, customer=customer,
                                             search=search, at=at).count()
            for focus in ("attention", "waiting", "closed", "all")}


def get_customer_privacy_requests(customer):
    return customer.account_deletion_requests.only(
        "id", "customer_id", "status", "requested_at", "verified_at",
        "owner_review_due_at", "closed_at",
    ).order_by("-requested_at", "-pk")


def get_recorded_first_payment(account):
    """Read-only milestone: never infer receipt from checkout or a URL hint."""
    received = account.contributions.filter(status__in=SUCCESSFUL_PAYMENT_STATUSES)
    real = received.filter(Q(payment_gateway="in_store_cash") |
                           Q(payment_gateway="razorpay", gateway_mode=GatewayMode.LIVE)).exists()
    practice = received.filter(Q(payment_gateway="mock") |
                               Q(payment_gateway="razorpay", gateway_mode=GatewayMode.TEST)).exists()
    return {"complete": real, "practice_recorded": practice}


@dataclass(frozen=True)
class OwnerApplicationItem:
    kind: str
    record: CustomerRegistration | SchemeEnrolmentRequest
    submitted_at: datetime
    next_action: str


def get_owner_application_items(keys):
    keys = tuple(keys)
    registrations = CustomerRegistration.objects.select_related(
        "approved_user__customer_profile", "reviewed_by", "plan_application__plan", "plan_application__metal_grade"
    ).in_bulk(key["pk"] for key in keys if key["queue_kind"] == "registration")
    plans = get_owner_enrolment_requests().in_bulk(
        key["pk"] for key in keys if key["queue_kind"] == "plan"
    )
    items = []
    for key in keys:
        kind = key["queue_kind"]
        record = (registrations if kind == "registration" else plans).get(key["pk"])
        if record is None:  # A concurrent retention operation may remove an unverified record.
            continue
        if kind == "registration":
            if record.status == record.Status.AWAITING_OWNER_APPROVAL:
                journey = getattr(record, "plan_application", None)
                if journey:
                    if journey.expires_at <= timezone.now():
                        action = "Review expired application; no approval available"
                    elif journey.progress_delivery_failed_at or not journey.progress_sent_at:
                        action = "Recover application progress email delivery"
                    elif not journey.completed_at:
                        action = "Await customer details and plan confirmation"
                    else:
                        action = "Review identity and customer-confirmed plan together"
                else:
                    action = "Verify showroom contact and review identity"
            elif record.status == record.Status.PENDING_EMAIL_VERIFICATION:
                journey = getattr(record, "plan_application", None)
                action = "Ask the applicant to start a new plan application" if journey and journey.expires_at <= timezone.now() else "Review verification delivery" if record.delivery_failed_at else (
                    "Review expired verification" if record.email_verification_expires_at <= timezone.now()
                    else "Await customer email verification"
                )
            else:
                action = "View decision and customer record"
        else:
            action = "Review plan and confirm terms" if record.status == record.Status.PENDING_OWNER_REVIEW else "View recorded decision"
            if record.status == record.Status.PENDING_OWNER_REVIEW and record.effective_status == record.Status.EXPIRED:
                action = "Review and record expiry"
            elif record.status == record.Status.PENDING_OWNER_REVIEW and (
                not record.customer.user.is_active or record.customer.user.role != "CUSTOMER"
            ):
                action = "Review customer login eligibility"
        items.append(OwnerApplicationItem(kind, record, key["queue_date"], action))
    return tuple(items)


def get_expired_pending_checkouts(*, at=None):
    """All modes remain visible, including orders without a provider identity."""
    return Contribution.objects.filter(
        status=Contribution.Status.PENDING, payment_gateway="razorpay",
        checkout_expires_at__lte=at or timezone.now(),
    )


def get_owner_exception_keys(*, oldest_first=False, category="all"):
    from .payment_refund_selectors import exclude_resolved_capture_events
    from .independent_payment_selectors import unbound_optional_order_contributions
    allocations = Contribution.objects.filter(status=Contribution.Status.PAID_UNALLOCATED).order_by().annotate(
        queue_kind=Value("allocation"),
        queue_date=Coalesce("allocation_attempted_at", "paid_at", "created_at"),
    ).values("pk", "queue_kind", "queue_date")
    webhooks = exclude_resolved_capture_events(PaymentWebhookEvent.objects.filter(status__in=["FAILED", "REVIEW_REQUIRED"])).order_by().annotate(
        queue_kind=Value("webhook"), queue_date=Coalesce("processed_at", "received_at"),
    ).values("pk", "queue_kind", "queue_date")
    optional_orders = unbound_optional_order_contributions().order_by().annotate(
        queue_kind=Value("optional_order"), queue_date=F("optional_order_request__created_at"),
    ).values("pk", "queue_kind", "queue_date")
    checkouts = get_expired_pending_checkouts().exclude(pk__in=unbound_optional_order_contributions()).order_by().annotate(
        queue_kind=Value("checkout"), queue_date=F("checkout_expires_at"),
    ).values("pk", "queue_kind", "queue_date")
    groups = {"allocation": allocations, "webhook": webhooks,
        "checkout": checkouts, "optional_order": optional_orders}
    selected = groups.get(category)
    combined = selected if selected is not None else allocations.union(webhooks, checkouts, optional_orders, all=True)
    return combined.order_by(
        "queue_date" if oldest_first else "-queue_date", "queue_kind", "pk"
    )


def get_enrollable_scheme_plans():
    """Release switch only affects new offers, never existing agreement rights."""
    from django.conf import settings
    plans = SchemePlan.objects.filter(active=True, catalogue_closure__isnull=True)
    if not settings.CONFIGURED_PLANS_ENABLED:
        return plans.filter(configuration__isnull=True)
    return plans.filter(Q(configuration__isnull=True) | Q(publication_revision__isnull=False))


def get_public_scheme_plans(*, limit=None):
    plans = (
        get_enrollable_scheme_plans().filter(
            active=True,
            publicly_listed=True,
        ).filter(Q(metal_offerings__active=True) | Q(
            configuration__policy_schema_version=2,
            configuration__accumulation="INR_PURCHASE_CREDIT",
        ))
        .prefetch_related("metal_offerings__metal_grade")
        .distinct()
        .order_by("name", "code")
    )
    if limit is not None:
        return plans[:limit]
    return plans


def get_owner_customer(customer_id):
    return Customer.objects.select_related("user").prefetch_related(
        "scheme_accounts__plan",
        "scheme_accounts__metal_grade",
    ).get(pk=customer_id)


def get_latest_customer_invitation(customer):
    return (
        CustomerInvitation.objects.filter(user=customer.user)
        .select_related("created_by")
        .order_by("-created_at", "-pk")
        .first()
    )


def get_customer_scheme_account(user, scheme_number):
    return get_customer_scheme_summary(user).filter(scheme_number=scheme_number).first()


def get_customer_enrolment_requests(user):
    return SchemeEnrolmentRequest.objects.filter(
        customer__user=user,
    ).select_related(
        "customer",
        "plan",
        "metal_grade",
        "scheme_account",
    ).order_by(
        "-created_at",
        "-pk",
    )


def get_customer_enrolment_request(user, request_id):
    return get_customer_enrolment_requests(user).filter(pk=request_id).first()


def get_owner_enrolment_requests():
    return SchemeEnrolmentRequest.objects.select_related(
        "customer__user",
        "plan",
        "metal_grade",
        "scheme_account",
        "decided_by",
    ).order_by(
        Case(
            When(
                status=SchemeEnrolmentRequest.Status.PENDING_OWNER_REVIEW,
                then=Value(0),
            ),
            default=Value(1),
        ),
        "-created_at",
        "-pk",
    )


def get_pending_enrolment_request_count():
    return SchemeEnrolmentRequest.objects.filter(
        status=SchemeEnrolmentRequest.Status.PENDING_OWNER_REVIEW,
        expires_at__gt=timezone.now(),
    ).count()


def get_current_scheme_rate(metal_grade, at=None):
    at = at or timezone.now()
    grade_id = getattr(metal_grade, "pk", None)
    if grade_id is None:
        grade_id = MetalGrade.objects.only("pk").get(code=metal_grade).pk
    return (
        SchemeRate.objects.filter(metal_grade_id=grade_id, effective_from__lte=at)
        .select_related("published_by", "metal_grade")
        .order_by("-effective_from", "-published_at", "-pk")
        .first()
    )


def get_current_scheme_rates(at=None):
    return {
        grade.code: get_current_scheme_rate(grade, at=at)
        for grade in MetalGrade.objects.all()
    }


def get_scheme_rate_history(limit=50):
    return SchemeRate.objects.select_related("published_by", "metal_grade").order_by(
        "-effective_from", "-published_at", "-pk"
    )[:limit]


def get_contribution_history(scheme_account):
    from .models import InstalmentOrderRecovery

    return scheme_account.contributions.select_related(
        "scheme_rate__metal_grade",
        "metal_allocation__scheme_rate",
        "metal_allocation__metal_grade",
        "cash_receipt",
        "cash_receipt__received_by",
        "cash_reversal",
        "cash_reversal__processed_by",
    ).annotate(order_identity_recovered=Exists(InstalmentOrderRecovery.objects.filter(
        request_decision__reservation__contribution_id=OuterRef("pk"))))


def get_customer_document_payments(user):
    return get_owner_contributions().filter(scheme_account__customer__user=user, status__in=RECEIPT_PAYMENT_STATUSES).order_by("-created_at", "-pk")


def get_customer_attention_accounts(user):
    rows = Contribution.objects.filter(scheme_account=OuterRef("pk"))
    return get_customer_scheme_summary(user).annotate(
        workspace_received=Exists(rows.filter(status__in=SUCCESSFUL_PAYMENT_STATUSES)),
        workspace_unresolved=Exists(rows.filter(Q(status="PAID_UNALLOCATED") | Q(status="PENDING", payment_gateway="razorpay"))),
    ).filter(Q(workspace_received=False) | Q(workspace_unresolved=True)).exclude(status__in=["REDEEMED", "CANCELLED"]).order_by("-workspace_unresolved", "start_date", "pk")[:6]


def get_customer_payment_availability(scheme_account):
    """Read-only presentation of initiation rules; services still enforce them."""
    from .closure_selectors import accepted_closure
    # Local import avoids operations -> selectors -> operations at module load.
    from .operations import OPEN, PaymentAvailability, get_payment_availability
    from .payments import payment_gateway_is_configured
    from .services import cash_scheme_activity_is_enabled

    def blocked(code, message):
        return PaymentAvailability(False, code, message)

    if scheme_account.agreement_schema_version == 2:
        from .independent_payment_selectors import get_independent_payment_availability
        return get_independent_payment_availability(scheme_account)
    if scheme_account.status == "CANCELLED":
        return blocked("CANCELLED", "This unused agreement has been cancelled. Your login and other agreements are unchanged.")
    if scheme_account.status == "REDEEMED":
        return blocked("REDEEMED", "This agreement has been fully redeemed. Your login and other agreements are unchanged.")
    if accepted_closure(scheme_account):
        return blocked("CLOSURE_PENDING", "Closure has been accepted. Do not pay again. Existing payments and entitlement remain for reconciliation and full settlement; the agreement is not closed yet.")
    if not payment_gateway_is_configured():
        return blocked("UNCONFIGURED", "Online payments are currently unavailable. Contact the showroom for assistance.")
    from .instalments import AGREEMENT_TIMEZONE, has_monthly_instalments
    monthly = has_monthly_instalments(scheme_account)
    if monthly:
        from django.core.exceptions import ValidationError
        from .instalment_selectors import get_monthly_eligibility, current_instalment_period, resumable_instalment_contribution, unresolved_instalment_captures
        if unresolved_instalment_captures(account_id=scheme_account.pk).exists():
            return blocked("CAPTURE_REVIEW", "A payment requires showroom reconciliation. Do not make another payment while this review is open.")
        if settings.PAYMENT_GATEWAY != "razorpay" or settings.RAZORPAY_MODE != "live":
            return blocked("INSTALMENT_REAL_PAYMENT_REQUIRED", "Only live payments can qualify for this monthly agreement. Contact the showroom.")
        evaluation = get_monthly_eligibility(scheme_account)
        if evaluation.state not in ("COLLECTING", "PAYMENT_PENDING"):
            return blocked("INSTALMENT_" + evaluation.state, evaluation.message)
        if evaluation.allocation_pending:
            return blocked("ALLOCATION_PENDING", "A recorded payment is awaiting metal allocation. Contact the showroom before paying again.")
        try:
            resumable = resumable_instalment_contribution(scheme_account)
            if resumable is None:
                current_instalment_period(scheme_account)
            elif resumable.gateway_mode != settings.RAZORPAY_MODE:
                return blocked("MODE_MISMATCH", "The showroom must review an earlier payment attempt before you can continue.")
        except ValidationError as exc:
            return blocked("INSTALMENT_UNAVAILABLE", " ".join(exc.messages))
    today = timezone.localdate(timezone=AGREEMENT_TIMEZONE) if monthly else timezone.localdate()
    if scheme_account.status == SchemeAccount.Status.REDEEMED:
        return blocked("REDEEMED", "This agreement has been redeemed.")
    if today < scheme_account.start_date:
        return blocked("NOT_STARTED", "Contributions become available on the agreement start date.")
    if not monthly and is_redemption_eligible(eligible_from=scheme_account.eligible_from, as_of=today) and not scheme_account.allow_post_eligibility_contributions_snapshot:
        if scheme_account.configuration_snapshot_id:
            return blocked("CONFIGURED_SETTLEMENT_UNAVAILABLE", "The recorded calendar date has been reached. Full jewellery settlement requires showroom review and customer confirmation; contact the showroom.")
        return blocked("ELIGIBLE", "Contributions are complete. Contact the showroom to arrange redemption.")
    if scheme_account.savings_mode == SchemeAccount.SavingsMode.CASH:
        if not cash_scheme_activity_is_enabled():
            return blocked("LEGACY_CASH", "This legacy cash agreement is retained for reference. New contributions are unavailable.")
        availability = OPEN
    else:
        availability = get_payment_availability(metal_grade=scheme_account.metal_grade)
        if not availability.allowed:
            return availability
    if scheme_account.frequency_rule_snapshot == SchemePlan.FrequencyRule.ONCE_PER_MONTH:
        period = today.replace(day=1)
        contributions = Contribution.objects.filter(scheme_account=scheme_account, contribution_period=period)
        if contributions.filter(status__in=SUCCESSFUL_PAYMENT_STATUSES).exists():
            return blocked("MONTH_PAID", "Your contribution for this calendar month has been received.")
        pending = contributions.filter(status=Contribution.Status.PENDING, payment_gateway="razorpay").first()
        if pending is not None:
            if pending.gateway_mode != settings.RAZORPAY_MODE:
                return blocked("MODE_MISMATCH", "The showroom must review an earlier payment attempt before you can continue.")
            if pending.razorpay_checkout_expired:
                return blocked("EXPIRED_PENDING", "Checkout expired — awaiting provider reconciliation. Contact the showroom if your account was debited.")
    return availability


def get_customer_plan_next_action(scheme_account, availability=None):
    """Derive continuation from recorded agreement/payment state, never URL hints."""
    from django.urls import reverse
    availability = availability or get_customer_payment_availability(scheme_account)
    history_url = reverse("schemes:my_scheme_detail", args=[scheme_account.scheme_number])
    if scheme_account.status == "CANCELLED":
        return dict(stage="Unused agreement cancelled", message=availability.message,
            label="View closure history", url=reverse("schemes:closure_workspace", args=[scheme_account.scheme_number]), can_pay=False)
    if scheme_account.configuration_snapshot_id and scheme_account.status == "REDEEMED":
        return dict(stage="Full settlement recorded", message="This agreement is closed to new payments. Its financial and closure history remain available.",
            label="View closure history", url=reverse("schemes:closure_workspace", args=[scheme_account.scheme_number]), can_pay=False)
    contributions = Contribution.objects.filter(scheme_account=scheme_account)
    unresolved = contributions.filter(
        Q(status=Contribution.Status.PAID_UNALLOCATED)
        | Q(status=Contribution.Status.PENDING, payment_gateway="razorpay"),
    ).order_by(
        Case(When(status=Contribution.Status.PAID_UNALLOCATED, then=Value(0)), default=Value(1)),
        "created_at", "pk",
    ).first()
    if unresolved is not None:
        from .checkout_selectors import checkout_can_resume
        if ((not scheme_account.configuration_snapshot_id or scheme_account.agreement_schema_version == 2)
                and availability.allowed and checkout_can_resume(unresolved)):
            return dict(stage="Payment checkout ready", message="Continue your existing checkout to complete this contribution.",
                label="Continue payment", url=reverse("schemes:razorpay_checkout", args=[unresolved.pk]), can_pay=True)
        mode = "Test payment" if unresolved.gateway_mode == GatewayMode.TEST else (
            "Practice payment" if unresolved.payment_gateway == "mock" else "Payment"
        )
        if unresolved.status == Contribution.Status.PAID_UNALLOCATED:
            stage = f"{mode} recorded — metal credit pending"
            message = "Do not pay again for this contribution. View its recorded status or contact the showroom."
        elif unresolved.razorpay_checkout_expired:
            stage = f"{mode} checkout expired — confirmation pending"
            message = "Checkout expired — awaiting provider reconciliation. If your account was debited, do not pay again; contact the showroom."
        else:
            stage = f"{mode} confirmation pending"
            message = "Check the recorded status before starting another payment. If debited, do not pay again while confirmation is pending."
        return dict(stage=stage, message=message, label="View payment status",
                    url=(reverse("schemes:payment_status", args=[unresolved.pk]) if unresolved.payment_gateway == "razorpay" else history_url), can_pay=False)
    received = contributions.filter(status__in=SUCCESSFUL_PAYMENT_STATUSES).exists()
    if availability.code == "CLOSURE_PENDING":
        return dict(stage="Closure accepted — settlement pending", message=availability.message,
            label="View closure history", url=reverse("schemes:closure_workspace", args=[scheme_account.scheme_number]), can_pay=False)
    real_received = contributions.filter(status__in=SUCCESSFUL_PAYMENT_STATUSES).filter(
        Q(payment_gateway="in_store_cash") | Q(payment_gateway="razorpay", gateway_mode=GatewayMode.LIVE),
    ).exists()
    if not availability.allowed:
        message = availability.message
        if availability.code == "NOT_STARTED":
            message += f" Start date: {scheme_account.start_date:%d %b %Y}."
        return dict(stage=("First payment recorded" if real_received else (
                    "Test or practice payment recorded" if received else "Approved plan")),
                    message=message, label="Contact the showroom", url=reverse("contact"), can_pay=False)
    from .payments import get_payment_gateway
    gateway = get_payment_gateway()
    test_checkout = gateway.name == "razorpay" and gateway.mode == "test"
    practice_checkout = gateway.name == "mock"
    label = "Make a contribution" if real_received else "Make first payment"
    if test_checkout:
        label = "Open test checkout"
    elif practice_checkout:
        label = "Open practice payment"
    return dict(stage=("First payment recorded" if real_received else (
                    "Test or practice payment recorded" if received else "Ready for first payment")),
                message=("Your agreement is approved. Online payments use Razorpay Test Mode; this is not a live payment."
                         if test_checkout else "Practice payments do not collect money." if practice_checkout
                         else "Continue with your approved agreement. Payment is recorded only after server confirmation."),
                label=label, url=reverse("schemes:pay_contribution", args=[scheme_account.scheme_number]), can_pay=True)


def get_customer_request_progress(user, limit=3, attention_only=False):
    from django.urls import reverse
    from .services import enrolment_request_offer_is_current
    requests = get_customer_enrolment_requests(user)
    if attention_only:
        requests = requests.filter(status=SchemeEnrolmentRequest.Status.PENDING_OWNER_REVIEW)
    requests = requests.annotate(
        priority=Case(When(status=SchemeEnrolmentRequest.Status.PENDING_OWNER_REVIEW, then=Value(0)), default=Value(1)),
    ).order_by("priority", "-created_at", "-pk")[:limit]
    result = []
    for item in requests:
        stage = item.effective_status_label
        if item.status == SchemeEnrolmentRequest.Status.ENROLLED and item.scheme_account_id:
            action = get_customer_plan_next_action(item.scheme_account)
        else:
            message = "Contact the showroom to discuss the recorded decision."
            if item.effective_status == SchemeEnrolmentRequest.Status.PENDING_OWNER_REVIEW:
                message = "The showroom must review your application. No payment is due before an agreement is created."
                if not enrolment_request_offer_is_current(item):
                    stage = "Confirm current terms"
                    message = "The offer changed. Open your application to withdraw it and submit a fresh confirmation."
            elif item.effective_status == SchemeEnrolmentRequest.Status.EXPIRED:
                message = "Contact the showroom before applying again."
            action = dict(stage=stage, message=message, label="View application",
                          url=reverse("schemes:my_enrolment_request_detail", args=[item.pk]), can_pay=False)
        result.append(dict(name=item.plan_name_snapshot, grade=item.metal_grade, action=action))
    return result


def get_redemption_history(scheme_account):
    return scheme_account.redemptions.select_related(
        "processed_by", "reversal", "reversal__processed_by", "configured_settlement"
    )


def get_owner_contributions():
    return Contribution.objects.select_related(
        "scheme_account",
        "scheme_account__customer",
        "scheme_account__plan",
        "scheme_account__metal_grade",
        "metal_allocation",
        "scheme_rate__metal_grade",
        "metal_allocation__scheme_rate",
        "metal_allocation__metal_grade",
        "cash_receipt",
        "cash_receipt__received_by",
        "cash_reversal",
        "cash_reversal__processed_by",
    )


def get_in_store_cash_daily_summary(as_of=None):
    local_date = as_of or timezone.localdate()
    current_timezone = timezone.get_current_timezone()
    day_start = timezone.make_aware(
        datetime.combine(local_date, time.min),
        current_timezone,
    )
    day_end = day_start + timedelta(days=1)
    money_field = DecimalField(max_digits=14, decimal_places=2)
    receipts = InStoreCashReceipt.objects.filter(
        received_at__gte=day_start,
        received_at__lt=day_end,
    ).aggregate(
        count=Count("pk"),
        amount=Coalesce(
            Sum("contribution__amount"),
            Value(Decimal("0.00")),
            output_field=money_field,
        ),
    )
    reversals = InStoreCashContributionReversal.objects.filter(
        reversed_at__gte=day_start,
        reversed_at__lt=day_end,
    ).aggregate(
        count=Count("pk"),
        amount=Coalesce(
            Sum("contribution__amount"),
            Value(Decimal("0.00")),
            output_field=money_field,
        ),
    )
    return InStoreCashDailySummary(
        as_of=local_date,
        receipts_count=receipts["count"],
        received_amount=receipts["amount"],
        reversals_count=reversals["count"],
        reversed_amount=reversals["amount"],
    )


def get_owner_contribution_daily_summary(as_of=None):
    cash = get_in_store_cash_daily_summary(as_of=as_of)
    current_timezone = timezone.get_current_timezone()
    day_start = timezone.make_aware(
        datetime.combine(cash.as_of, time.min),
        current_timezone,
    )
    day_end = day_start + timedelta(days=1)
    money_field = DecimalField(max_digits=14, decimal_places=2)
    successful_today = Contribution.objects.filter(
        status__in=SUCCESSFUL_PAYMENT_STATUSES,
        paid_at__gte=day_start,
        paid_at__lt=day_end,
    )
    live_razorpay = Q(
        payment_channel=PaymentChannel.RAZORPAY,
        gateway_mode=GatewayMode.LIVE,
    )
    real_payment = live_razorpay | Q(
        payment_channel=PaymentChannel.IN_STORE_CASH,
    )
    totals = successful_today.aggregate(
        razorpay_count=Count("pk", filter=live_razorpay),
        razorpay_amount=Coalesce(
            Sum("amount", filter=live_razorpay),
            Value(Decimal("0.00")),
            output_field=money_field,
        ),
        verified_count=Count("pk", filter=real_payment),
        verified_amount=Coalesce(
            Sum("amount", filter=real_payment),
            Value(Decimal("0.00")),
            output_field=money_field,
        ),
    )
    return OwnerContributionDailySummary(
        cash=cash,
        razorpay_count=totals["razorpay_count"],
        razorpay_amount=totals["razorpay_amount"],
        verified_count=totals["verified_count"],
        verified_amount=totals["verified_amount"],
    )


def get_pending_payment_exposure():
    rows = (
        Contribution.objects.filter(
            status=Contribution.Status.PENDING,
            payment_gateway="razorpay",
            gateway_order_id__isnull=False,
            scheme_account__savings_mode__in=[
                SchemeAccount.SavingsMode.GOLD,
                SchemeAccount.SavingsMode.SILVER,
            ],
        )
        .values(
            "scheme_account__metal_grade__code",
            "scheme_account__metal_grade__display_name",
        )
        .annotate(count=Count("pk"), amount=Sum("amount"))
    )
    exposure = {
        grade.code: {
            "count": 0,
            "amount": Decimal("0.00"),
            "display_name": grade.display_name,
        }
        for grade in MetalGrade.objects.all()
    }
    for row in rows:
        code = row["scheme_account__metal_grade__code"]
        exposure[code] = {
            "count": row["count"],
            "amount": row["amount"] or Decimal("0.00"),
            "display_name": row["scheme_account__metal_grade__display_name"],
        }
    return exposure


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
        "scheme_rate",
        "redemption",
    )


def get_owner_exception_queue(*, keys=None):
    from .independent_payment_selectors import unbound_optional_order_contributions
    items = []
    unallocated = Contribution.objects.filter(
        status=Contribution.Status.PAID_UNALLOCATED
    ).select_related("scheme_account", "scheme_account__customer")
    if keys is not None:
        keys = tuple(keys)
        unallocated = unallocated.filter(pk__in=[key["pk"] for key in keys if key["queue_kind"] == "allocation"])
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
        status__in=[
            PaymentWebhookEvent.Status.FAILED,
            PaymentWebhookEvent.Status.REVIEW_REQUIRED,
        ]
    ).select_related(
        "contribution",
        "contribution__scheme_account",
        "contribution__scheme_account__customer",
    )
    from .payment_refund_selectors import exclude_resolved_capture_events
    failed_webhooks = exclude_resolved_capture_events(failed_webhooks)
    if keys is not None:
        failed_webhooks = failed_webhooks.filter(pk__in=[key["pk"] for key in keys if key["queue_kind"] == "webhook"])
    for event in failed_webhooks:
        is_mismatch = (
            "MISMATCH" in event.failure_code.upper()
            or "match" in event.error.lower()
        )
        items.append(
            OwnerExceptionItem(
                category=(
                    "Payment mismatch / manual correction required"
                    if is_mismatch
                    else (
                        "Webhook review required"
                        if event.status == PaymentWebhookEvent.Status.REVIEW_REQUIRED
                        else "Failed webhook reconciliation"
                    )
                ),
                detected_at=event.processed_at or event.received_at,
                detail=event.error or "Webhook processing failed.",
                webhook_event=event,
                queue_kind="webhook",
            )
        )
    optional_orders = unbound_optional_order_contributions().select_related(
        "scheme_account__customer", "optional_order_request")
    if keys is not None:
        optional_orders = optional_orders.filter(pk__in=[key["pk"] for key in keys if key["queue_kind"] == "optional_order"])
    for contribution in optional_orders:
        items.append(OwnerExceptionItem(
            category="Optional order identity unresolved",
            detected_at=contribution.optional_order_request.created_at,
            detail="An original order request has no retained provider identity. Investigate that request before any replacement payment; elapsed time does not prove non-payment.",
            contribution=contribution, queue_kind="optional_order",
        ))
    checkouts = get_expired_pending_checkouts().exclude(pk__in=unbound_optional_order_contributions()).select_related("scheme_account", "scheme_account__customer")
    if keys is not None:
        checkouts = checkouts.filter(pk__in=[key["pk"] for key in keys if key["queue_kind"] == "checkout"])
    for contribution in checkouts:
        items.append(OwnerExceptionItem(
            category="Checkout expired — provider reconciliation required",
            detected_at=contribution.checkout_expires_at,
            detail="The payment remains unconfirmed. Inspect the provider order and payments before closing this attempt; expiry alone does not prove non-payment.",
            contribution=contribution, queue_kind="checkout",
        ))
    if keys is not None:
        by_key = {
            (item.queue_kind, item.contribution.pk if item.contribution else item.webhook_event.pk): item
            for item in items
        }
        return tuple(by_key[(key["queue_kind"], key["pk"])] for key in keys if (key["queue_kind"], key["pk"]) in by_key)
    return tuple(sorted(items, key=lambda item: item.detected_at, reverse=True))


def get_financial_exception_counts():
    from .independent_payment_selectors import unbound_optional_order_contributions
    from .payment_refund_selectors import exclude_resolved_capture_events, refund_disposition_integrity_errors
    webhook_counts = exclude_resolved_capture_events(PaymentWebhookEvent.objects.filter(
        status__in=[
            PaymentWebhookEvent.Status.FAILED,
            PaymentWebhookEvent.Status.REVIEW_REQUIRED,
        ]
    )).aggregate(
        failed=Count("pk"),
        mismatched=Count(
            "pk",
            filter=(
                Q(failure_code__icontains="MISMATCH")
                | Q(error__icontains="match")
            ),
        ),
    )
    return FinancialExceptionCounts(
        paid_unallocated=Contribution.objects.filter(
            status=Contribution.Status.PAID_UNALLOCATED
        ).count(),
        failed_webhooks=webhook_counts["failed"],
        mismatched_webhooks=webhook_counts["mismatched"],
        expired_checkouts=get_expired_pending_checkouts().exclude(pk__in=unbound_optional_order_contributions()).count(),
        unresolved_optional_orders=unbound_optional_order_contributions().count(),
        refund_disposition_errors=refund_disposition_integrity_errors(),
    )


def contribution_receipt_number(contribution):
    paid_date = timezone.localtime(contribution.paid_at).date()
    return f"JSK-RCT-{paid_date.year}-{contribution.pk:08d}"


def get_contribution_receipt_summary(contribution):
    if contribution.status not in RECEIPT_PAYMENT_STATUSES:
        raise ValueError("Only verified payments have contribution receipts.")
    try:
        allocation = contribution.metal_allocation
    except MetalAllocation.DoesNotExist:
        allocation = None
    principal = None
    if contribution.scheme_account.savings_mode == "INR_CREDIT":
        from .inr_selectors import get_inr_principal_summary
        from django.core.exceptions import ValidationError
        if get_inr_principal_summary(contribution.scheme_account).needs_review:
            raise ValidationError("Purchase-credit receipt evidence requires reconciliation.")
        recorded_principal = getattr(contribution, "inr_principal_receipt", None)
        if recorded_principal is None:
            raise ValidationError("A verified purchase-credit principal receipt is required.")
        principal = recorded_principal.amount
    return ContributionReceiptSummary(
        receipt_number=contribution_receipt_number(contribution),
        contribution=contribution,
        allocation=allocation,
        principal_amount=principal,
    )


def get_scheme_statement(scheme_account):
    if scheme_account.savings_mode == "INR_CREDIT":
        from .statement_selectors import inr_statement
        return inr_statement(scheme_account)
    from .statement_selectors import validate_metal_document_history
    validate_metal_document_history(scheme_account)
    entries = []
    contributions = get_contribution_history(scheme_account).filter(
        status__in=RECEIPT_PAYMENT_STATUSES
    )
    for contribution in contributions:
        try:
            allocation = contribution.metal_allocation
        except MetalAllocation.DoesNotExist:
            allocation = None
        if scheme_account.savings_mode == SchemeAccount.SavingsMode.CASH:
            description = "Cash contribution"
            unit = "INR"
        elif allocation is None:
            description = (
                f"{scheme_account.entitlement_name} payment — allocation pending"
            )
            unit = f"g {scheme_account.entitlement_name}"
        else:
            description = f"{allocation.metal_grade.display_name} contribution allocated"
            unit = f"g {allocation.metal_grade.display_name}"
        entries.append(
            StatementEntry(
                occurred_at=contribution.paid_at,
                description=description,
                reference=contribution.gateway_reference or "",
                status=contribution.get_status_display(),
                amount_inr=contribution.amount,
                scheme_rate=(
                    allocation.scheme_rate.rate_per_gram if allocation else None
                ),
                metal_allocation=allocation.quantity if allocation else None,
                entitlement_unit=unit,
                contribution_id=contribution.pk,
                payment_label=("Test payment - no live payment" if contribution.gateway_mode == GatewayMode.TEST else
                               "Practice payment - no money collected" if contribution.payment_gateway == "mock" else contribution.payment_method_display),
                practice_record=(contribution.gateway_mode == GatewayMode.TEST or contribution.payment_gateway == "mock"),
            )
        )
        if contribution.status == Contribution.Status.REVERSED:
            reversal = contribution.cash_reversal
            entries.append(
                StatementEntry(
                    occurred_at=reversal.reversed_at,
                    description="In-store cash contribution correction",
                    reference=reversal.reversal_number,
                    status="Entitlement removed",
                    metal_reversal=allocation.quantity if allocation else None,
                    entitlement_unit=unit,
                    contribution_id=contribution.pk,
                )
            )

    for redemption in get_redemption_history(scheme_account):
        configured = getattr(redemption, "configured_settlement", None)
        settlement_details = dict(
            invoice_reference=redemption.external_reference if configured else "",
            settlement_basis=configured.get_basis_display() if configured else "",
        )
        entries.append(
            StatementEntry(
                occurred_at=redemption.completed_at,
                description=f"{redemption.get_settlement_type_display()} redemption",
                reference=redemption.redemption_number,
                status="Reversed" if hasattr(redemption, "reversal") else "Completed",
                redemption=redemption.entitlement_amount,
                entitlement_unit=redemption.entitlement_unit,
                **settlement_details,
            )
        )
        if hasattr(redemption, "reversal"):
            entries.append(
                StatementEntry(
                    occurred_at=redemption.reversal.reversed_at,
                    description="Redemption reversal",
                    reference=redemption.reversal.reversal_number,
                    status="Restored",
                    restoration=redemption.entitlement_amount,
                    entitlement_unit=redemption.entitlement_unit,
                    **settlement_details,
                )
            )

    cash_bonus = None
    if scheme_account.savings_mode == SchemeAccount.SavingsMode.CASH:
        cash_bonus = get_cash_bonus_summary(scheme_account)
        remaining_entitlement = cash_bonus.redeemable_amount
        entitlement_unit = "INR"
    else:
        remaining_entitlement = get_metal_balance(scheme_account)
        entitlement_unit = f"g {scheme_account.entitlement_name}"
    from .statement_selectors import benefit_document
    return SchemeStatement(
        scheme_account=scheme_account,
        generated_at=timezone.now(),
        entries=tuple(sorted(entries, key=lambda entry: entry.occurred_at)),
        remaining_entitlement=remaining_entitlement,
        entitlement_unit=entitlement_unit,
        cash_bonus=cash_bonus,
        benefit=benefit_document(scheme_account),
    )


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
        metal_grade=scheme_account.metal_grade,
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
    if contract_qualifies and is_redemption_eligible(
        eligible_from=scheme_account.eligible_from,
        as_of=as_of,
    ):
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
        metal_grade=scheme_account.metal_grade,
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


def get_metal_acquisition_summary(scheme_account):
    """Historical paid INR per recorded gram, separate from remaining entitlement.

    Use the same PAID, exact-grade allocation basis as the metal balance. A cash
    correction leaves its original allocation as evidence but marks its payment
    reversed, so it contributes neither amount nor grams here. Redemptions and
    their returns do not rewrite acquisition history. Divide six-decimal stored
    quantities before rounding the final INR/g display, never average quoted rates.
    """
    if scheme_account.savings_mode not in {"GOLD", "SILVER"} or not scheme_account.metal_grade_id:
        return None
    totals = MetalAllocation.objects.filter(
        contribution__scheme_account=scheme_account,
        contribution__status=Contribution.Status.PAID,
        metal_grade_id=scheme_account.metal_grade_id,
    ).aggregate(paid=Sum("contribution__amount"), grams=Sum("quantity"))
    paid = totals["paid"] or Decimal("0.00")
    grams = totals["grams"] or Decimal("0.000000")
    average = (paid / grams).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP) if grams > 0 else None
    return MetalAcquisitionSummary(paid, grams, average)


def get_outstanding_entitlement(scheme_account):
    if scheme_account.savings_mode == "INR_CREDIT":
        from .inr_settlement_selectors import inr_settlement_balance
        return inr_settlement_balance(scheme_account).outstanding
    if scheme_account.savings_mode == SchemeAccount.SavingsMode.CASH:
        return get_cash_bonus_summary(scheme_account).redeemable_amount
    return get_metal_balance(scheme_account)


def get_owner_liability_summary():
    from .inr_selectors import get_inr_recorded_principal_total
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

    allocated = {
        row["metal_grade_id"]: row["quantity"]
        for row in MetalAllocation.objects.filter(
            contribution__status=Contribution.Status.PAID,
        )
        .values("metal_grade_id")
        .annotate(quantity=Sum("quantity"))
    }
    redeemed = {
        row["metal_grade_id"]: row["quantity"]
        for row in Redemption.objects.filter(
            status=Redemption.Status.COMPLETED,
            reversal__isnull=True,
            metal_grade__isnull=False,
        )
        .values("metal_grade_id")
        .annotate(
            quantity=Sum(
                Case(
                    When(gold_quantity__isnull=False, then=F("gold_quantity")),
                    default=F("silver_quantity"),
                    output_field=DecimalField(max_digits=18, decimal_places=6),
                )
            )
        )
    }
    grade_liabilities = tuple(
        _get_current_metal_liability(
            grade,
            allocated.get(grade.pk, Decimal("0.000000"))
            - redeemed.get(grade.pk, Decimal("0.000000")),
        )
        for grade in MetalGrade.objects.all()
    )

    return OwnerLiabilitySummary(
        cash_principal=cash_principal,
        cash_earned_bonus=cash_earned_bonus,
        cash_projected_bonus=cash_projected_bonus,
        metal_grades=grade_liabilities,
        inr_purchase_principal=get_inr_recorded_principal_total(),
    )


def _get_current_metal_liability(metal_grade, quantity):
    scheme_rate = get_current_scheme_rate(metal_grade)
    if scheme_rate is None:
        return MetalLiability(metal_grade=metal_grade, quantity=quantity)
    return MetalLiability(
        metal_grade=metal_grade,
        quantity=quantity,
        scheme_rate=scheme_rate.rate_per_gram,
        indicative_exposure=(quantity * scheme_rate.rate_per_gram).quantize(
            MONEY_QUANTUM, rounding=ROUND_HALF_UP
        ),
        rate_published_at=scheme_rate.published_at,
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
            status__in=[SchemeAccount.Status.REDEEMED, SchemeAccount.Status.CANCELLED]
        ).count(),
        contribution_count_today=contribution_counts["today"],
        contribution_count_month=contribution_counts["month"],
        unallocated_payment_count=contribution_counts["unallocated"],
    )


def get_owner_settlement_review_count(*, as_of=None):
    """Calendar-due legacy agreements, not approval of a settlement or benefit.

    Configured agreements have a separate policy projection and their settlement
    service is still gated. Their original dates must not enter this legacy queue.
    """
    return SchemeAccount.objects.filter(
        configuration_snapshot__isnull=True,
        eligible_from__lte=as_of or timezone.localdate(),
    ).exclude(status=SchemeAccount.Status.REDEEMED).count()


def get_redemption_eligibility_summary(as_of=None):
    as_of = as_of or timezone.localdate()
    open_accounts = list(
        SchemeAccount.objects.exclude(status__in=[SchemeAccount.Status.REDEEMED, SchemeAccount.Status.CANCELLED])
        .select_related("customer", "plan", "metal_grade", "configuration_snapshot")
        .order_by("eligible_from", "scheme_number")
    )
    # Configured settlement is not released. Never place its original date into
    # legacy date-only redemption buckets or offer the legacy redemption action.
    configured = tuple(account for account in open_accounts if account.configuration_snapshot_id)
    open_accounts = [account for account in open_accounts if not account.configuration_snapshot_id]
    redeemed = tuple(
        SchemeAccount.objects.filter(status=SchemeAccount.Status.REDEEMED)
        .select_related("customer", "plan", "metal_grade")
        .order_by("-eligible_from", "scheme_number")
    )
    return RedemptionEligibilitySummary(
        as_of=as_of,
        configured=configured,
        eligible_now=tuple(
            account
            for account in open_accounts
            if is_redemption_eligible(
                eligible_from=account.eligible_from,
                as_of=as_of,
            )
        ),
        next_30_days=tuple(
            account
            for account in open_accounts
            if 1
            <= eligibility_days_until(
                eligible_from=account.eligible_from,
                as_of=as_of,
            )
            <= 30
        ),
        next_60_days=tuple(
            account
            for account in open_accounts
            if 31
            <= eligibility_days_until(
                eligible_from=account.eligible_from,
                as_of=as_of,
            )
            <= 60
        ),
        next_90_days=tuple(
            account
            for account in open_accounts
            if 61
            <= eligibility_days_until(
                eligible_from=account.eligible_from,
                as_of=as_of,
            )
            <= 90
        ),
        later=tuple(
            account
            for account in open_accounts
            if eligibility_days_until(
                eligible_from=account.eligible_from,
                as_of=as_of,
            )
            > 90
        ),
        redeemed=redeemed,
    )


def get_upcoming_eligibility_accounts(*, as_of, lead_days):
    target_dates = [as_of + timedelta(days=days) for days in lead_days]
    return SchemeAccount.objects.filter(
        eligible_from__in=target_dates,
        configuration_snapshot__isnull=True,
    ).exclude(
        status=SchemeAccount.Status.REDEEMED,
    ).select_related(
        "customer",
        "customer__user",
        "plan",
        "metal_grade",
    ).order_by(
        "eligible_from",
        "scheme_number",
    )


def get_upcoming_monthly_completion_accounts(*, as_of, lead_days):
    """Bound by either possible date floor; current count/holds still need evaluation."""
    dates = [as_of + timedelta(days=days) for days in lead_days]
    return SchemeAccount.objects.filter(
        agreement_schema_version=1,
        status=SchemeAccount.Status.ACTIVE,
        configuration_snapshot__instalment_policy="MONTHLY_COMPLETION",
    ).filter(Q(instalment_periods__ends_before__in=dates) | Q(eligible_from__in=dates)
    ).select_related("customer__user", "configuration_snapshot", "plan", "metal_grade").distinct().order_by("pk")


def eligibility_reminder_terms(account, *, as_of):
    """Current evidence, not a forecast or historical reconstruction."""
    from .instalments import has_monthly_instalments
    from .instalment_selectors import get_monthly_eligibility
    from .closure_selectors import accepted_closure

    if account.agreement_schema_version == 2:
        from .independent_reminders import independent_reminder_terms
        return independent_reminder_terms(account, as_of=as_of)
    if account.status in (SchemeAccount.Status.REDEEMED, SchemeAccount.Status.CANCELLED) or accepted_closure(account):
        return None
    if has_monthly_instalments(account):
        if account.status != SchemeAccount.Status.ACTIVE:
            return None
        result = get_monthly_eligibility(account, as_of=as_of)
        if result.state == "WAITING_PERIOD_END" and not result.allocation_pending:
            return SchemeReminder.Kind.UPCOMING_MONTHLY_COMPLETION, result.completion_date
        return None
    if account.configuration_snapshot_id:
        # Other configured families remain gated until their settlement path exists.
        return None
    return SchemeReminder.Kind.UPCOMING_ELIGIBILITY, account.eligible_from


def get_allocation_exception_contributions():
    return Contribution.objects.filter(
        status=Contribution.Status.PAID_UNALLOCATED,
    ).select_related(
        "scheme_account",
        "scheme_account__customer",
        "scheme_account__customer__user",
        "scheme_account__metal_grade",
    ).order_by(
        "allocation_attempted_at",
        "pk",
    )


def get_completed_redemptions_for_date(*, as_of):
    return Redemption.objects.filter(
        status=Redemption.Status.COMPLETED,
        completed_at__date=as_of,
        reversal__isnull=True,
    ).select_related(
        "scheme_account",
        "scheme_account__customer",
        "scheme_account__customer__user",
        "scheme_account__metal_grade",
    ).order_by(
        "completed_at",
        "pk",
    )


def get_owner_notification_emails():
    user_model = get_user_model()
    emails = user_model.objects.filter(
        is_active=True,
    ).filter(
        Q(role=user_model.Role.OWNER) | Q(is_superuser=True),
    ).exclude(
        email="",
    ).order_by(
        "pk",
    ).values_list(
        "email",
        flat=True,
    )
    deduplicated = {}
    for email in emails:
        normalized = email.strip().lower()
        if normalized:
            deduplicated.setdefault(normalized, normalized)
    return tuple(deduplicated.values())


def get_scheme_reminder_owner_emails():
    return get_owner_notification_emails()


def get_owner_scheme_reminders():
    return SchemeReminder.objects.select_related(
        "scheme_account",
        "scheme_account__customer",
        "contribution",
        "redemption",
    ).prefetch_related(
        "delivery_attempts",
    )
