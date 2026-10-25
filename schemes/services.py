import hashlib
import secrets
from contextlib import nullcontext
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from accounts.services import issue_customer_invitation

from .bonuses import CASH_BONUS_POLICY_VERSION
from .instalments import AGREEMENT_TIMEZONE, has_monthly_instalments
from .instalment_selectors import current_instalment_period, resumable_instalment_contribution
from .instalment_payments import (
    reserve_instalment, attribute_cash_instalment, attribute_razorpay_instalment,
    note_verified_instalment, reverse_cash_instalment, release_reconciled_instalment,
    note_late_instalment_capture,
    begin_instalment_order_request, complete_instalment_order_request,
)
from .eligibility import (
    add_calendar_months,
    calculate_eligibility_date,
    is_redemption_eligible,
)
from .models import (
    AuditEvent,
    Contribution,
    Customer,
    GatewayMode,
    InStoreCashContributionReversal,
    InStoreCashReceipt,
    InstalmentReservation,
    MetalAllocation,
    MetalGrade,
    PaymentChannel,
    PaymentOperationsControl,
    PaymentScheduleWindow,
    PaymentWebhookEvent,
    WebhookProcessingAttempt,
    SchemeRate,
    Redemption,
    RedemptionReversal,
    SchemeAccount,
    SchemeEnrolmentRequest,
    SchemePlan,
    SchemePlanOffering,
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
    get_metal_balance,
    get_outstanding_entitlement,
)


MONEY_QUANTUM = Decimal("0.01")
METAL_QUANTUM = Decimal("0.000001")
SUCCESSFUL_PAYMENT_STATUSES = (
    Contribution.Status.PAID,
    Contribution.Status.PAID_UNALLOCATED,
)
EXPECTED_ALLOCATION_ERRORS = (ValidationError,)
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


@dataclass(frozen=True)
class InStoreCashContributionPreview:
    scheme_account: SchemeAccount
    amount: Decimal
    contribution_period: date
    scheme_rate: SchemeRate | None
    quantity: Decimal | None


@dataclass(frozen=True)
class EnrolmentRequestSubmission:
    enrolment_request: SchemeEnrolmentRequest
    created: bool


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


def in_store_cash_contributions_are_enabled():
    return settings.IN_STORE_CASH_CONTRIBUTIONS_ENABLED


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


def ensure_payment_initiation_allowed(*, metal_grade, at=None, lock=False, savings_mode=None):
    if metal_grade is None and savings_mode != SchemeAccount.SavingsMode.INR_CREDIT:
        return
    availability = get_payment_availability(
        metal_grade=metal_grade,
        at=at,
        lock=lock,
        savings_mode=savings_mode,
    )
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
    *, metal_grade, rate_per_gram, published_by, notes="", effective_from=None
):
    _validate_owner(published_by)
    if metal_grade is None or not metal_grade.pk:
        raise ValidationError({"metal_grade": "Select a metal grade."})
    metal_grade = MetalGrade.objects.select_for_update().get(pk=metal_grade.pk)
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
        metal=metal_grade.metal,
        metal_grade=metal_grade,
        rate_per_gram=normalized_rate,
        purity=metal_grade.fineness,
        effective_from=effective_from,
        published_by=published_by,
        notes=notes.strip(),
    )
    scheme_rate.full_clean()
    scheme_rate.save()
    record_audit_event(
        action=AuditEvent.Action.SCHEME_RATE_PUBLICATION,
        actor=published_by,
        reason=f"Published a new {metal_grade.display_name} Scheme Rate.",
        scheme_rate=scheme_rate,
        details={
            "metal": metal_grade.metal,
            "metal_grade": metal_grade.code,
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
    metal_grade=None,
    savings_mode=None,
    start_date=None,
    agreed_months=None,
    selected_contribution_amount=None,
    selected_amount_confirmed=False,
    expected_configuration_id=None,
    expected_plan_digest=None,
    performed_by=None,
    reason="Customer enrolled through service.",
):
    customer = Customer.objects.select_for_update().get(pk=customer.pk)
    if get_user_model().objects.filter(pk=customer.user_id, privacy_erased_at__isnull=False).exists():
        raise ValidationError("A removed customer login cannot receive new enrolments.")
    # Resolve denomination from the locked offer, not caller-cached configuration.
    from .models import SchemePlan
    from .plan_governance import ensure_plan_revision

    plan = SchemePlan.objects.select_for_update().get(pk=plan.pk)
    independent = bool(plan.configuration_id and plan.configuration.policy_schema_version == 2)
    inr_credit = independent and plan.configuration.accumulation == "INR_PURCHASE_CREDIT"
    if inr_credit:
        if metal_grade is not None or savings_mode not in (None, SchemeAccount.SavingsMode.INR_CREDIT):
            raise ValidationError("INR purchase credit cannot carry a metal grade or another denomination.")
        savings_mode = SchemeAccount.SavingsMode.INR_CREDIT
    if metal_grade is not None:
        metal_grade = MetalGrade.objects.get(pk=metal_grade.pk)
        savings_mode = metal_grade.metal
    elif savings_mode != SchemeAccount.SavingsMode.CASH and not inr_credit:
        raise ValidationError(
            {"metal_grade": "Select the exact metal grade for this enrolment."}
        )
    if (
        savings_mode == SchemeAccount.SavingsMode.CASH
        and not cash_scheme_activity_is_enabled()
    ):
        raise ValidationError({"savings_mode": CASH_SCHEME_ACTIVITY_UNAVAILABLE})
    # Serialize enrolment with audited offer edits; never use a stale caller instance.
    if plan.configuration_id:
        from .plan_publication import require_configured_offer
        from .plan_governance import plan_edit_digest
        require_configured_offer(plan)
        if expected_plan_digest != plan_edit_digest(plan):
            raise ValidationError('The configured offer changed; review it with the customer again.')
    if not independent:
        plan.full_clean()
    # Independent policy is authoritative: the legacy plan duration/frequency
    # columns cannot represent COUNT/ANYTIME. require_configured_offer above still
    # checks publication, exact revision evidence and operational readiness.
    if not plan.active:
        raise ValidationError({"plan": "Only active plans can accept new enrolments."})
    if metal_grade is not None and not SchemePlanOffering.objects.filter(
        plan=plan,
        metal_grade=metal_grade,
        active=True,
    ).exists():
        raise ValidationError(
            {"metal_grade": "This metal grade is not offered by the selected plan."}
        )
    start_date = start_date or timezone.localdate()
    from .plan_configuration import agreement_snapshot_values
    if plan.configuration_id:
        _validate_owner(performed_by)
        if expected_configuration_id != plan.configuration_id or selected_amount_confirmed is not True:
            raise ValidationError({"plan": 'Confirm the current configuration and individual amount with the customer.'})
    if independent:
        from .agreement_contracts import resolve_independent_agreement_terms
        terms = resolve_independent_agreement_terms(configuration_id=plan.configuration_id,
            start_date=start_date, selected_amount=selected_contribution_amount,
            metal_grade_id=metal_grade.pk if metal_grade else None)
        if agreed_months is not None and (type(agreed_months) is not int or agreed_months != terms.policy.duration_months):
            raise ValidationError("The selected duration must match the accepted independent policy; count is not duration.")
        snapshots = terms.account_snapshots()
        revision = plan.publication_revision
    else:
        agreed_months = agreed_months or plan.default_months
        if agreed_months < plan.minimum_months:
            raise ValidationError(
                {"agreed_months": "Agreed duration cannot be below the plan minimum."}
            )
        snapshots = agreement_snapshot_values(plan=plan, selected_amount=selected_contribution_amount)
        snapshots.update(start_date=start_date, agreed_months=agreed_months,
            eligible_from=calculate_eligibility_date(start_date=start_date, agreed_months=agreed_months),
            savings_mode=savings_mode, metal_grade_id=metal_grade.pk if metal_grade else None)
        revision = ensure_plan_revision(
            plan=plan, actor=performed_by,
            reason='Current offer recorded at enrolment; individual agreement terms are snapshotted separately.',
        )
    account = SchemeAccount(
        scheme_number=_reference("JSK", SchemeAccount, "scheme_number"),
        customer=customer,
        plan=plan,
        plan_name_snapshot=plan.name,
        plan_code_snapshot=plan.code,
        plan_revision=revision,
        **snapshots,
        cash_bonus_policy_version_snapshot=CASH_BONUS_POLICY_VERSION,
    )
    account.full_clean()
    account.save()
    if account.configuration_snapshot_id and account.configuration_snapshot.instalment_policy == "MONTHLY_COMPLETION":
        from .instalments import prepare_instalment_periods
        prepare_instalment_periods(account_id=account.pk, actor=performed_by,
            reason='Schedule recorded atomically with the accepted configured agreement.')
    record_audit_event(
        action=AuditEvent.Action.CUSTOMER_ENROLMENT,
        actor=performed_by,
        reason=reason,
        scheme_plan=plan,
        scheme_account=account,
        details={
            "scheme_number": account.scheme_number,
            'plan_revision_id': revision.pk,
            'configuration_id': account.configuration_snapshot_id,
            'fixed_contribution_amount': str(account.fixed_amount_snapshot) if account.fixed_amount_snapshot is not None else None,
            "savings_mode": account.savings_mode,
            "metal_grade": account.metal_grade.code if account.metal_grade_id else None,
            "agreed_months": account.agreed_months,
            "eligible_from": account.eligible_from.isoformat() if account.eligible_from else None,
            **({"agreement_schema_version": account.agreement_schema_version,
                "eligibility_policy": account.eligibility_policy_snapshot,
                "required_count": account.required_count_snapshot} if independent else {}),
        },
    )
    return account


def _validate_customer_actor(*, customer, actor):
    user_model = get_user_model()
    if (
        actor is None
        or not actor.is_active
        or actor.role != user_model.Role.CUSTOMER
        or customer.user_id != actor.pk
    ):
        raise ValidationError("Only the active customer may perform this action.")


def _normalize_requested_contribution(*, plan, amount):
    if plan.configuration_id:
        from .plan_configuration import validate_configuration_amount
        return validate_configuration_amount(plan.configuration, amount)
    try:
        normalized = Decimal(str(amount)).quantize(MONEY_QUANTUM)
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError(
            {"requested_contribution_amount": "Enter a valid contribution amount."}
        ) from None
    if not normalized.is_finite() or normalized <= 0:
        raise ValidationError(
            {"requested_contribution_amount": "Enter a positive contribution amount."}
        )
    if Decimal(str(amount)) != normalized:
        raise ValidationError(
            {
                "requested_contribution_amount": (
                    "Contribution amounts support at most 2 decimal places."
                )
            }
        )
    if plan.amount_rule == SchemePlan.AmountRule.FIXED:
        if normalized != plan.fixed_contribution_amount:
            raise ValidationError(
                {
                    "requested_contribution_amount": (
                        "This plan uses the displayed fixed contribution amount."
                    )
                }
            )
    elif normalized < plan.minimum_contribution or (
        plan.maximum_contribution is not None
        and normalized > plan.maximum_contribution
    ):
        raise ValidationError(
            {
                "requested_contribution_amount": (
                    "Choose an amount within the plan's displayed range."
                )
            }
        )
    return normalized


def enrolment_request_offer_is_current(enrolment_request):
    plan = enrolment_request.plan
    from .plan_publication import require_configured_offer
    try:
        require_configured_offer(plan)
    except ValidationError:
        return False
    if not plan.active or not plan.publicly_listed:
        return False
    if not SchemePlanOffering.objects.filter(
        plan=plan,
        metal_grade=enrolment_request.metal_grade,
        active=True,
    ).exists():
        return False
    return all(
        [
            enrolment_request.configuration_snapshot_id == plan.configuration_id,
            enrolment_request.amount_rule_snapshot == plan.amount_rule,
            enrolment_request.plan_name_snapshot == plan.name,
            enrolment_request.plan_code_snapshot == plan.code,
            enrolment_request.frequency_rule_snapshot == plan.frequency_rule,
            enrolment_request.fixed_contribution_amount_snapshot
            == plan.fixed_contribution_amount,
            enrolment_request.minimum_contribution_snapshot
            == plan.minimum_contribution,
            enrolment_request.maximum_contribution_snapshot
            == plan.maximum_contribution,
            enrolment_request.minimum_months_snapshot == plan.minimum_months,
            enrolment_request.default_months_snapshot == plan.default_months,
            enrolment_request.allow_post_eligibility_contributions_snapshot
            == plan.allow_contributions_after_eligibility,
            enrolment_request.disclosure_version == settings.CUSTOMER_ENROLMENT_REQUEST_DISCLOSURE_VERSION,
        ]
    )


def _request_audit_details(enrolment_request):
    return {
        "enrolment_request_id": str(enrolment_request.pk),
        "customer_number": enrolment_request.customer.customer_number,
        "plan_code": enrolment_request.plan_code_snapshot,
        "metal_grade": enrolment_request.metal_grade.code,
        "requested_contribution_amount": str(
            enrolment_request.requested_contribution_amount
        ),
        "requested_months": enrolment_request.requested_months,
        "disclosure_version": enrolment_request.disclosure_version,
    }


def _decide_enrolment_request(*, enrolment_request, status, actor, reason):
    normalized_reason = reason.strip()
    if not normalized_reason:
        raise ValidationError({"reason": "Enter a reason for this action."})
    enrolment_request.status = status
    enrolment_request.decided_by = actor
    enrolment_request.decided_by_label = _actor_label(actor)
    enrolment_request.decision_reason = normalized_reason
    enrolment_request.decided_at = timezone.now()
    enrolment_request.save()
    return enrolment_request


@transaction.atomic
def submit_scheme_enrolment_request(
    *,
    customer,
    plan,
    metal_grade,
    requested_contribution_amount,
    requested_months,
    customer_message,
    actor,
):
    if not settings.CUSTOMER_ENROLMENT_REQUESTS_ENABLED:
        raise ValidationError("Online enrolment requests are currently unavailable.")
    customer = Customer.objects.select_for_update().select_related("user").get(
        pk=customer.pk
    )
    _validate_customer_actor(customer=customer, actor=actor)
    plan = SchemePlan.objects.select_for_update().get(pk=plan.pk)
    metal_grade = MetalGrade.objects.get(pk=metal_grade.pk)
    from .plan_publication import require_configured_offer
    require_configured_offer(plan)
    plan.full_clean()
    if not plan.active or not plan.publicly_listed:
        raise ValidationError({"plan": "This plan is not open for online requests."})
    if not SchemePlanOffering.objects.filter(
        plan=plan,
        metal_grade=metal_grade,
        active=True,
    ).exists():
        raise ValidationError(
            {"metal_grade": "This metal grade is not currently offered by the plan."}
        )

    now = timezone.now()
    expired_requests = SchemeEnrolmentRequest.objects.select_for_update().filter(
        customer=customer,
        plan=plan,
        metal_grade=metal_grade,
        status=SchemeEnrolmentRequest.Status.PENDING_OWNER_REVIEW,
        expires_at__lte=now,
    )
    for expired_request in expired_requests:
        _decide_enrolment_request(
            enrolment_request=expired_request,
            status=SchemeEnrolmentRequest.Status.EXPIRED,
            actor=None,
            reason="The request validity period ended before a replacement submission.",
        )
        record_audit_event(
            action=AuditEvent.Action.ENROLMENT_REQUEST_EXPIRED,
            actor=None,
            reason=expired_request.decision_reason,
            scheme_plan=expired_request.plan,
            details=_request_audit_details(expired_request),
        )

    existing = SchemeEnrolmentRequest.objects.filter(
        customer=customer,
        plan=plan,
        metal_grade=metal_grade,
        status=SchemeEnrolmentRequest.Status.PENDING_OWNER_REVIEW,
    ).first()
    if existing is not None:
        return EnrolmentRequestSubmission(existing, False)

    try:
        requested_months = int(requested_months)
    except (TypeError, ValueError):
        raise ValidationError(
            {"requested_months": "Enter a valid preferred duration."}
        ) from None
    if requested_months < plan.minimum_months:
        raise ValidationError(
            {
                "requested_months": (
                    f"This plan requires at least {plan.minimum_months} months."
                )
            }
        )
    normalized_amount = _normalize_requested_contribution(
        plan=plan,
        amount=requested_contribution_amount,
    )
    normalized_message = str(customer_message or "").strip()
    if len(normalized_message) > 1000:
        raise ValidationError(
            {"customer_message": "Keep the showroom message within 1000 characters."}
        )
    enrolment_request = SchemeEnrolmentRequest(
        customer=customer,
        plan=plan,
        metal_grade=metal_grade,
        plan_name_snapshot=plan.name,
        plan_code_snapshot=plan.code,
        configuration_snapshot_id=plan.configuration_id,
        requested_contribution_amount=normalized_amount,
        requested_months=requested_months,
        customer_message=normalized_message,
        amount_rule_snapshot=plan.amount_rule,
        frequency_rule_snapshot=plan.frequency_rule,
        fixed_contribution_amount_snapshot=plan.fixed_contribution_amount,
        minimum_contribution_snapshot=plan.minimum_contribution,
        maximum_contribution_snapshot=plan.maximum_contribution,
        minimum_months_snapshot=plan.minimum_months,
        default_months_snapshot=plan.default_months,
        allow_post_eligibility_contributions_snapshot=(
            plan.allow_contributions_after_eligibility
        ),
        disclosure_version=settings.CUSTOMER_ENROLMENT_REQUEST_DISCLOSURE_VERSION,
        disclosure_accepted_at=now,
        expires_at=now
        + timedelta(days=settings.CUSTOMER_ENROLMENT_REQUEST_EXPIRY_DAYS),
    )
    enrolment_request.save()
    record_audit_event(
        action=AuditEvent.Action.ENROLMENT_REQUEST_SUBMITTED,
        actor=actor,
        reason="Customer submitted a non-binding enrolment interest request.",
        scheme_plan=plan,
        details=_request_audit_details(enrolment_request),
    )
    return EnrolmentRequestSubmission(enrolment_request, True)


@transaction.atomic
def withdraw_scheme_enrolment_request(*, enrolment_request, actor):
    enrolment_request = (
        SchemeEnrolmentRequest.objects.select_for_update()
        .select_related("customer__user", "plan", "metal_grade")
        .get(pk=enrolment_request.pk)
    )
    _validate_customer_actor(customer=enrolment_request.customer, actor=actor)
    if enrolment_request.status != SchemeEnrolmentRequest.Status.PENDING_OWNER_REVIEW:
        raise ValidationError("Only a pending request can be withdrawn.")
    status = SchemeEnrolmentRequest.Status.WITHDRAWN
    reason = "Customer withdrew the enrolment interest request."
    action = AuditEvent.Action.ENROLMENT_REQUEST_WITHDRAWN
    if enrolment_request.expires_at <= timezone.now():
        status = SchemeEnrolmentRequest.Status.EXPIRED
        reason = "The request validity period ended before withdrawal."
        action = AuditEvent.Action.ENROLMENT_REQUEST_EXPIRED
    _decide_enrolment_request(
        enrolment_request=enrolment_request,
        status=status,
        actor=actor if status == SchemeEnrolmentRequest.Status.WITHDRAWN else None,
        reason=reason,
    )
    record_audit_event(
        action=action,
        actor=actor if status == SchemeEnrolmentRequest.Status.WITHDRAWN else None,
        reason=reason,
        scheme_plan=enrolment_request.plan,
        details=_request_audit_details(enrolment_request),
    )
    return enrolment_request


@transaction.atomic
def decide_scheme_enrolment_request(*, enrolment_request, status, actor, reason):
    _validate_owner(actor)
    if status not in {
        SchemeEnrolmentRequest.Status.DECLINED,
        SchemeEnrolmentRequest.Status.EXPIRED,
    }:
        raise ValidationError("Select a supported enrolment request decision.")
    enrolment_request = (
        SchemeEnrolmentRequest.objects.select_for_update()
        .select_related("customer__user", "plan", "metal_grade")
        .get(pk=enrolment_request.pk)
    )
    if enrolment_request.status != SchemeEnrolmentRequest.Status.PENDING_OWNER_REVIEW:
        raise ValidationError("Only a pending request can be reviewed.")
    if (
        enrolment_request.expires_at <= timezone.now()
        and status != SchemeEnrolmentRequest.Status.EXPIRED
    ):
        raise ValidationError("This request has expired; record it as expired.")
    _decide_enrolment_request(
        enrolment_request=enrolment_request,
        status=status,
        actor=actor,
        reason=reason,
    )
    action = (
        AuditEvent.Action.ENROLMENT_REQUEST_DECLINED
        if status == SchemeEnrolmentRequest.Status.DECLINED
        else AuditEvent.Action.ENROLMENT_REQUEST_EXPIRED
    )
    record_audit_event(
        action=action,
        actor=actor,
        reason=enrolment_request.decision_reason,
        scheme_plan=enrolment_request.plan,
        details=_request_audit_details(enrolment_request),
    )
    return enrolment_request


@transaction.atomic
def enroll_customer_from_request(
    *,
    enrolment_request,
    actor,
    current_terms_confirmed,
    start_date,
    agreed_months,
    reason,
):
    _validate_owner(actor)
    enrolment_request = (
        SchemeEnrolmentRequest.objects.select_for_update()
        .select_related("customer__user", "metal_grade")
        .get(pk=enrolment_request.pk)
    )
    if enrolment_request.status == SchemeEnrolmentRequest.Status.ENROLLED:
        return enrolment_request.scheme_account, False
    if enrolment_request.status != SchemeEnrolmentRequest.Status.PENDING_OWNER_REVIEW:
        raise ValidationError("Only a pending request can become an agreement.")
    current_plan = SchemePlan.objects.select_for_update().get(
        pk=enrolment_request.plan_id
    )
    SchemePlanOffering.objects.select_for_update().filter(
        plan=current_plan,
        metal_grade=enrolment_request.metal_grade,
    ).first()
    enrolment_request.plan = current_plan
    user_model = get_user_model()
    if (
        not enrolment_request.customer.user.is_active
        or enrolment_request.customer.user.role != user_model.Role.CUSTOMER
    ):
        raise ValidationError(
            "The customer login is no longer active and eligible for conversion."
        )
    if enrolment_request.expires_at <= timezone.now():
        raise ValidationError(
            "This request has expired. Record expiry and ask the customer to submit again."
        )
    if not current_terms_confirmed:
        raise ValidationError(
            "Confirm that the current terms were reviewed with the customer."
        )
    if not enrolment_request_offer_is_current(enrolment_request):
        raise ValidationError(
            "The public offer changed or closed. Do not silently substitute terms; "
            "ask the customer to review the current offer and submit again."
        )
    if agreed_months != enrolment_request.requested_months:
        raise ValidationError("The duration differs from the customer's request. Ask the customer to withdraw and confirm a new request; do not substitute a duration.")
    from .plan_governance import plan_edit_digest
    account = enroll_customer(
        customer=enrolment_request.customer,
        plan=enrolment_request.plan,
        metal_grade=enrolment_request.metal_grade,
        start_date=start_date,
        agreed_months=agreed_months,
        selected_contribution_amount=enrolment_request.requested_contribution_amount,
        selected_amount_confirmed=current_terms_confirmed,
        expected_configuration_id=enrolment_request.configuration_snapshot_id,
        expected_plan_digest=plan_edit_digest(current_plan),
        performed_by=actor,
        reason=reason,
    )
    enrolment_request.scheme_account = account
    _decide_enrolment_request(
        enrolment_request=enrolment_request,
        status=SchemeEnrolmentRequest.Status.ENROLLED,
        actor=actor,
        reason=reason,
    )
    details = _request_audit_details(enrolment_request)
    details["scheme_number"] = account.scheme_number
    record_audit_event(
        action=AuditEvent.Action.ENROLMENT_REQUEST_ENROLLED,
        actor=actor,
        reason=enrolment_request.decision_reason,
        scheme_plan=enrolment_request.plan,
        scheme_account=account,
        details=details,
    )
    return account, True


def contribution_period_for(value):
    return date(value.year, value.month, 1)


def validate_contribution_amount(scheme_account, amount):
    if isinstance(amount, (float, bool)):
        raise ValidationError({'amount': 'Use a decimal INR amount.'})
    from .plan_configuration import validate_agreement_configuration
    validate_agreement_configuration(scheme_account)
    try:
        amount = Decimal(str(amount))
        normalized_amount = amount.quantize(MONEY_QUANTUM)
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError({"amount": "Enter a valid contribution amount."}) from None

    if not normalized_amount.is_finite():
        raise ValidationError({'amount': 'Enter a finite contribution amount.'})
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
    if (scheme_account.contribution_step_snapshot is not None
            and (normalized_amount - scheme_account.minimum_amount_snapshot) % scheme_account.contribution_step_snapshot):
        raise ValidationError({'amount': 'Use an allowed contribution increment from the agreement minimum.'})
    return normalized_amount


def validate_redemption_amount(scheme_account, amount):
    if scheme_account.configuration_snapshot_id:
        raise ValidationError('Full-only settlement for configured agreements has not been released.')
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
    _server_instant=None,
):
    from .plan_policies import require_current_payment_workflow
    require_current_payment_workflow(scheme_account)
    from .closure_selectors import require_no_accepted_closure
    require_no_accepted_closure(scheme_account)
    monthly = has_monthly_instalments(scheme_account)
    if Customer.objects.filter(
        pk=scheme_account.customer_id, user__privacy_erased_at__isnull=False,
    ).exists():
        raise ValidationError("A removed customer login cannot initiate new contributions.")
    if (
        scheme_account.savings_mode == SchemeAccount.SavingsMode.CASH
        and not cash_scheme_activity_is_enabled()
    ):
        raise ValidationError(CASH_SCHEME_ACTIVITY_UNAVAILABLE)
    if scheme_account.agreement_schema_version == 2:
        from .independent_payment_selectors import validate_independent_payment_window
        period = validate_independent_payment_window(scheme_account,
            contribution_date=contribution_date, contribution_period=contribution_period,
            exclude_contribution_id=exclude_contribution_id, at=_server_instant)
        return validate_contribution_amount(scheme_account, amount), period
    if monthly:
        today = timezone.now().astimezone(AGREEMENT_TIMEZONE).date()
        if contribution_date is not None and contribution_date != today:
            raise ValidationError('Monthly instalments cannot be backdated or paid in advance.')
        if contribution_period is not None and contribution_period != contribution_period_for(today):
            raise ValidationError("The accounting month cannot override an agreed instalment period.")
        current_instalment_period(scheme_account, exclude_contribution_id=exclude_contribution_id)
        contribution_date = today
    contribution_date = contribution_date or timezone.localdate()
    if scheme_account.status == SchemeAccount.Status.REDEEMED:
        raise ValidationError("A redeemed scheme cannot receive contributions.")
    if contribution_date < scheme_account.start_date:
        raise ValidationError("Contributions cannot be made before the scheme start date.")
    if not monthly and is_redemption_eligible(
        eligible_from=scheme_account.eligible_from,
        as_of=contribution_date,
    ) and not scheme_account.allow_post_eligibility_contributions_snapshot:
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
    metal_grade = contribution.scheme_account.metal_grade
    if metal_grade is None:
        return contribution
    if contribution.scheme_rate_id:
        return contribution
    scheme_rate = get_current_scheme_rate(metal_grade)
    if scheme_rate is None:
        metal_name = metal_grade.display_name
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
    if locked_account.agreement_schema_version == 2:
        if payment_gateway != "razorpay" or gateway_mode != GatewayMode.LIVE:
            raise ValidationError("Independent online contributions require live Razorpay.")
        if not has_monthly_instalments(locked_account):
            raise ValidationError("Optional independent online order recovery is not integrated yet.")
    ensure_payment_initiation_allowed(
        metal_grade=locked_account.metal_grade,
        lock=True,
        savings_mode=locked_account.savings_mode,
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
        payment_channel=(
            PaymentChannel.RAZORPAY
            if payment_gateway == "razorpay"
            else PaymentChannel.MOCK
        ),
        gateway_mode=gateway_mode,
        checkout_expires_at=(
            timezone.now()
            + timedelta(minutes=settings.RAZORPAY_CHECKOUT_EXPIRY_MINUTES)
            if payment_gateway == "razorpay"
            else None
        ),
    )
    _lock_current_scheme_rate(contribution)
    contribution.full_clean()
    contribution.save()
    if has_monthly_instalments(locked_account):
        reservation = reserve_instalment(contribution_id=contribution.pk)
        contribution.checkout_expires_at = reservation.expires_at
        contribution.save(update_fields=['checkout_expires_at'])
    return contribution


def preview_in_store_cash_contribution(*, scheme_account, amount):
    if not in_store_cash_contributions_are_enabled():
        raise ValidationError("In-store cash contribution recording is disabled.")
    scheme_account = SchemeAccount.objects.get(pk=scheme_account.pk)
    if scheme_account.savings_mode not in {
        SchemeAccount.SavingsMode.GOLD,
        SchemeAccount.SavingsMode.SILVER,
        SchemeAccount.SavingsMode.INR_CREDIT,
    }:
        raise ValidationError(
            "In-store cash can be recorded only against a gold or silver scheme."
        )
    ensure_payment_initiation_allowed(metal_grade=scheme_account.metal_grade, savings_mode=scheme_account.savings_mode)
    normalized_amount, period = validate_contribution_allowed(scheme_account, amount)
    if scheme_account.savings_mode == SchemeAccount.SavingsMode.INR_CREDIT:
        return InStoreCashContributionPreview(scheme_account, normalized_amount, period, None, None)
    scheme_rate = get_current_scheme_rate(scheme_account.metal_grade)
    if scheme_rate is None:
        raise ValidationError(
            f"{scheme_account.entitlement_name} contributions are temporarily "
            "unavailable because the current Scheme Rate has not been published."
        )
    quantity = (normalized_amount / scheme_rate.rate_per_gram).quantize(
        METAL_QUANTUM,
        rounding=ROUND_HALF_UP,
    )
    if quantity <= 0:
        raise ValidationError("The contribution is too small to allocate.")
    return InStoreCashContributionPreview(
        scheme_account=scheme_account,
        amount=normalized_amount,
        contribution_period=period,
        scheme_rate=scheme_rate,
        quantity=quantity,
    )


def record_in_store_cash_contribution(
    *,
    scheme_account,
    amount,
    expected_scheme_rate_id,
    received_by,
    idempotency_key,
    paper_receipt_number="",
    notes="",
    audit_reason="Cash received at the showroom.",
):
    if not in_store_cash_contributions_are_enabled():
        raise ValidationError("In-store cash contribution recording is disabled.")
    _validate_owner(received_by)
    paper_receipt_number = paper_receipt_number.strip() or None
    notes = notes.strip()
    normalized_reason = audit_reason.strip()
    if not normalized_reason:
        raise ValidationError({"audit_reason": "Enter a reason for recording the cash."})

    with transaction.atomic():
        SchemeAccount.objects.select_for_update().get(pk=scheme_account.pk)
        existing = (
            InStoreCashReceipt.objects.select_related(
                "contribution",
                "contribution__scheme_account",
            )
            .filter(idempotency_key=idempotency_key)
            .first()
        )
        if existing is not None:
            contribution = existing.contribution
            submitted_amount = validate_contribution_amount(
                contribution.scheme_account,
                amount,
            )
            if (
                contribution.scheme_account_id == scheme_account.pk
                and contribution.amount == submitted_amount
                and existing.paper_receipt_number == paper_receipt_number
                and existing.notes == notes
                and contribution.scheme_rate_id == expected_scheme_rate_id
            ):
                return _apply_contribution_entitlement(contribution)
            raise ValidationError("The cash receipt submission token was already used.")

        account = (
            SchemeAccount.objects.select_for_update(of=("self",))
            .select_related("customer", "metal_grade")
            .get(pk=scheme_account.pk)
        )
        from .closure_selectors import require_no_accepted_closure
        require_no_accepted_closure(account)
        if account.savings_mode not in {
            SchemeAccount.SavingsMode.GOLD,
            SchemeAccount.SavingsMode.SILVER,
            SchemeAccount.SavingsMode.INR_CREDIT,
        }:
            raise ValidationError(
                "In-store cash can be recorded only against a gold or silver scheme."
            )
        if account.metal_grade_id:
            MetalGrade.objects.select_for_update().get(pk=account.metal_grade_id)
        ensure_payment_initiation_allowed(metal_grade=account.metal_grade, lock=True, savings_mode=account.savings_mode)
        if Contribution.objects.filter(
            scheme_account=account,
            status=Contribution.Status.PENDING,
            payment_gateway="razorpay",
        ).exists():
            raise ValidationError(
                "This scheme has a pending Razorpay order. Reconcile or complete it "
                "before recording in-store cash."
            )
        now = timezone.now()
        normalized_amount, period = validate_contribution_allowed(account, amount, _server_instant=now)
        inr_credit = account.savings_mode == SchemeAccount.SavingsMode.INR_CREDIT
        scheme_rate = None if inr_credit else (
            SchemeRate.objects.select_for_update()
            .filter(
                metal_grade=account.metal_grade,
                effective_from__lte=now,
            )
            .order_by("-effective_from", "-published_at", "-pk")
            .first()
        )
        if not inr_credit and scheme_rate is None:
            raise ValidationError("The current Scheme Rate has not been published.")
        if (scheme_rate.pk if scheme_rate else None) != expected_scheme_rate_id:
            raise ValidationError(
                "The Scheme Rate changed after preview. Review the updated rate "
                "before confirming cash receipt."
            )

        receipt_reference = _reference(
            "CASH",
            InStoreCashReceipt,
            "receipt_reference",
        )
        contribution = Contribution(
            scheme_account=account,
            amount=normalized_amount,
            contribution_period=period,
            frequency_rule_snapshot=account.frequency_rule_snapshot,
            status=Contribution.Status.PAID if inr_credit else Contribution.Status.PAID_UNALLOCATED,
            payment_gateway="in_store_cash",
            payment_channel=PaymentChannel.IN_STORE_CASH,
            gateway_reference=receipt_reference,
            scheme_rate=scheme_rate,
            rate_locked_at=None if inr_credit else now,
            paid_at=now,
        )
        contribution.full_clean()
        contribution.save()
        receipt = InStoreCashReceipt(
            contribution=contribution,
            receipt_reference=receipt_reference,
            idempotency_key=idempotency_key,
            paper_receipt_number=paper_receipt_number,
            received_by=received_by,
            received_by_label=_actor_label(received_by),
            received_at=now,
            notes=notes,
        )
        receipt.full_clean()
        receipt.save()
        if has_monthly_instalments(account):
            reserve_instalment(contribution_id=contribution.pk)
            attribute_cash_instalment(contribution_id=contribution.pk)
        if account.savings_mode == SchemeAccount.SavingsMode.INR_CREDIT:
            from .inr_principal import record_cash_inr_principal
            record_cash_inr_principal(cash_receipt_id=receipt.pk)
        record_audit_event(
            action=AuditEvent.Action.IN_STORE_CASH_RECEIPT,
            actor=received_by,
            reason=normalized_reason,
            scheme_account=account,
            contribution=contribution,
            scheme_rate=scheme_rate,
            details={
                "receipt_reference": receipt_reference,
                "paper_receipt_number": paper_receipt_number,
                "amount_inr": str(normalized_amount),
                "metal_grade": account.metal_grade.code if account.metal_grade_id else None,
                "rate_per_gram": str(scheme_rate.rate_per_gram) if scheme_rate else None,
            },
        )

    return _apply_contribution_entitlement(contribution)


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

    from .plan_policies import require_current_payment_workflow
    require_current_payment_workflow(contribution.scheme_account)

    if contribution.status in SUCCESSFUL_PAYMENT_STATUSES:
        if (
            contribution.payment_gateway == payment_gateway
            and contribution.gateway_reference == gateway_reference
        ):
            if has_monthly_instalments(contribution.scheme_account):
                note_verified_instalment(contribution_id=contribution.pk)
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
    if has_monthly_instalments(contribution.scheme_account):
        note_verified_instalment(contribution_id=contribution.pk)
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
    if not contribution.razorpay_checkout_expired:
        raise ValidationError('Checkout must expire before abandonment reconciliation.')

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
        SchemeAccount.objects.select_for_update().get(pk=contribution.scheme_account_id)
        locked = (
            Contribution.objects.select_for_update()
            .select_related("scheme_account")
            .get(pk=contribution.pk)
        )
        if (
            locked.status != Contribution.Status.PENDING
            or locked.gateway_order_id != contribution.gateway_order_id
            or locked.gateway_mode != gateway.mode
            or locked.amount != contribution.amount
            or locked.scheme_rate_id != contribution.scheme_rate_id
            or locked.checkout_expires_at != contribution.checkout_expires_at
        ):
            raise ValidationError(
                "The contribution changed during reconciliation; inspect it again."
            )
        if untouched:
            locked.status = Contribution.Status.ABANDONED
            locked.full_clean()
            locked.save(update_fields=["status"])

        reconciliation_audit = record_audit_event(
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
        if untouched and has_monthly_instalments(locked.scheme_account):
            release_reconciled_instalment(contribution_id=locked.pk, audit_id=reconciliation_audit.pk)
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

    metal_grade = locked_contribution.scheme_account.metal_grade
    if metal_grade is None:
        raise ValidationError("Cash contributions do not receive a metal allocation.")
    scheme_rate = locked_contribution.scheme_rate
    if scheme_rate is None:
        raise ValidationError("This paid contribution has no locked Scheme Rate.")
    if scheme_rate.metal_grade_id != metal_grade.pk:
        raise ValidationError("The locked Scheme Rate grade does not match the scheme.")
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
        metal=metal_grade.metal,
        metal_grade=metal_grade,
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
    from .plan_policies import require_current_payment_workflow
    require_current_payment_workflow(contribution.scheme_account)
    if (contribution.scheme_account.savings_mode == SchemeAccount.SavingsMode.INR_CREDIT
        and contribution.payment_channel == PaymentChannel.IN_STORE_CASH):
        from .inr_principal import record_cash_inr_principal
        receipt = InStoreCashReceipt.objects.get(contribution=contribution)
        record_cash_inr_principal(cash_receipt_id=receipt.pk)
        return contribution
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

    # Always reload immutable contract evidence rather than trusting a caller's cached object.
    scheme_account = SchemeAccount.objects.get(pk=scheme_account.pk)
    if has_monthly_instalments(scheme_account):
        if gateway.mode != GatewayMode.LIVE:
            raise ValidationError('Monthly real instalments require the live payment mode.')
        with transaction.atomic():
            account = SchemeAccount.objects.select_for_update().get(pk=scheme_account.pk)
            ensure_payment_initiation_allowed(metal_grade=account.metal_grade, lock=True, savings_mode=account.savings_mode)
            contribution = resumable_instalment_contribution(account)
            normalized_amount, _ = validate_contribution_allowed(account, amount, contribution_date,
                exclude_contribution_id=contribution.pk if contribution else None)
            if contribution is not None:
                if contribution.amount != normalized_amount or contribution.gateway_mode != gateway.mode:
                    raise ValidationError('The reserved checkout does not match the agreed amount/payment mode.')
            else:
                contribution = initiate_contribution(scheme_account=account, amount=normalized_amount,
                    payment_gateway=gateway.name, gateway_mode=gateway.mode, contribution_date=contribution_date)
        return _create_razorpay_order(contribution=contribution, gateway=gateway)

    ensure_payment_initiation_allowed(metal_grade=scheme_account.metal_grade)

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

    return _create_razorpay_order(contribution=contribution, gateway=gateway)


def _create_razorpay_order(*, contribution, gateway):
    from .closure_selectors import require_no_accepted_closure
    from .plan_policies import require_current_payment_workflow
    require_current_payment_workflow(contribution.scheme_account)
    order_error = None
    monthly = has_monthly_instalments(contribution.scheme_account)
    if contribution.scheme_account.agreement_schema_version == 2 and not monthly:
        raise ValidationError("Optional independent online order recovery is not integrated yet.")
    order_started = begin_instalment_order_request(contribution_id=contribution.pk) if monthly else False
    with transaction.atomic():
        SchemeAccount.objects.select_for_update().get(pk=contribution.scheme_account_id)
        contribution = (
            Contribution.objects.select_for_update()
            .select_related("scheme_account")
            .get(pk=contribution.pk)
        )
        require_no_accepted_closure(contribution.scheme_account)
        require_current_payment_workflow(contribution.scheme_account)
        if monthly:
            if order_started:
                current_instalment_period(contribution.scheme_account, exclude_contribution_id=contribution.pk)
                if contribution.razorpay_checkout_expired or not InstalmentReservation.objects.filter(
                    contribution=contribution, state="ORDERING",
                ).exists():
                    raise ValidationError('The reserved order needs review before proceeding.')
            else:
                resumable = resumable_instalment_contribution(contribution.scheme_account)
                if resumable is None or resumable.pk != contribution.pk:
                    raise ValidationError('This checkout no longer holds a payable period reservation.')
        ensure_payment_initiation_allowed(
            metal_grade=contribution.scheme_account.metal_grade,
            lock=True,
            savings_mode=contribution.scheme_account.savings_mode,
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
            if monthly:
                complete_instalment_order_request(contribution_id=contribution.pk)
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
        if has_monthly_instalments(contribution.scheme_account):
            note_verified_instalment(contribution_id=contribution.pk)
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


def _complete_captured_webhook(*, contribution, event, payment_id, body):
    monthly = has_monthly_instalments(contribution.scheme_account)
    inr_credit = contribution.scheme_account.savings_mode == SchemeAccount.SavingsMode.INR_CREDIT
    # Preserve legacy confirmation/retry transaction boundaries. Monthly funds and
    # qualification evidence must commit together under the agreement lock.
    with transaction.atomic() if monthly or inr_credit else nullcontext():
        if monthly or inr_credit:
            SchemeAccount.objects.select_for_update().get(pk=contribution.scheme_account_id)
        contribution = confirm_contribution(contribution_id=contribution.pk,
            payment_gateway='razorpay', gateway_reference=payment_id, verified=True)
        contribution = _apply_contribution_entitlement(contribution)
        with transaction.atomic():
            event.status = PaymentWebhookEvent.Status.PROCESSED
            event.contribution = contribution
            event.failure_code = ""
            event.error = ""
            event.processed_at = timezone.now()
            event.save(update_fields=["status", 'contribution', 'failure_code', 'error', 'processed_at'])
            if inr_credit:
                from .inr_principal import record_captured_inr_principal
                record_captured_inr_principal(event_id=event.pk, body=body)
            elif monthly:
                attribute_razorpay_instalment(event_id=event.pk, body=body)
            _record_webhook_attempt(event=event, source=WebhookProcessingAttempt.Source.PROVIDER_DELIVERY,
                outcome=WebhookProcessingAttempt.Outcome.PROCESSED,
                reason='Processed a signed captured-payment webhook.')
    return event


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
        if (event.status == PaymentWebhookEvent.Status.PROCESSED and event.contribution_id
            and event.contribution.scheme_account.savings_mode == SchemeAccount.SavingsMode.INR_CREDIT):
            from .plan_policies import require_current_payment_workflow
            from .inr_principal import record_captured_inr_principal
            require_current_payment_workflow(event.contribution.scheme_account)
            record_captured_inr_principal(event_id=event.pk, body=body)
        elif (event.status == PaymentWebhookEvent.Status.PROCESSED and event.contribution_id
            and has_monthly_instalments(event.contribution.scheme_account)):
            # A provider retry after API recovery can supply the original signed timing.
            attribute_razorpay_instalment(event_id=event.pk, body=body)
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
            return _complete_captured_webhook(contribution=contribution, event=event,
                payment_id=payment_id, body=body)
        except ValidationError as error:
            if Contribution.objects.filter(pk=contribution.pk, status=Contribution.Status.ABANDONED).exists():
                raise _WebhookReviewRequired("LATE_CAPTURE_ABANDONED",
                    'An abandoned contribution received a late capture; owner reconciliation is required.') from None
            if (has_monthly_instalments(contribution.scheme_account)
                and Contribution.objects.filter(pk=contribution.pk, status__in=SUCCESSFUL_PAYMENT_STATUSES)
                    .exclude(gateway_reference=payment_id).exists()):
                raise _WebhookReviewRequired("DUPLICATE_CAPTURE_REVIEW",
                    'A different captured payment was reported for an already-confirmed instalment. Preserve the original credit and reconcile the additional payment separately.') from None
            raise _WebhookReviewRequired(
                "CONTRIBUTION_CONFIRMATION_REJECTED",
                str(error).strip(),
            ) from None

    except _WebhookReviewRequired as error:
        with transaction.atomic():
            if event.contribution_id:
                SchemeAccount.objects.select_for_update().get(pk=event.contribution.scheme_account_id)
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
            if (error.code == "LATE_CAPTURE_ABANDONED" and event.contribution_id
                and has_monthly_instalments(event.contribution.scheme_account)):
                note_late_instalment_capture(event_id=event.pk)
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
    if contribution.scheme_account.savings_mode == SchemeAccount.SavingsMode.INR_CREDIT:
        return ("MANUAL_REVIEW_REQUIRED",
            "INR API-recovery principal evidence is not integrated; retain the source for reconciliation.")
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
        SchemeAccount.objects.select_for_update().get(pk=contribution.scheme_account_id)
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
        "metal_grade": account.metal_grade,
    }
    if account.savings_mode == SchemeAccount.SavingsMode.CASH:
        values["cash_amount"] = normalized_amount
        values["metal_grade"] = None
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
            and existing.metal_grade_id == (
                values["metal_grade"].pk if values["metal_grade"] else None
            )
            and existing.external_reference == external_reference
            and existing.notes == notes
        ):
            return existing
        raise ValidationError("The redemption submission token was already used.")

    if account.status == SchemeAccount.Status.REDEEMED:
        raise ValidationError("This scheme has already been fully redeemed.")
    if not is_redemption_eligible(
        eligible_from=account.eligible_from,
        as_of=timezone.localdate(),
    ):
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
    if Redemption.objects.filter(pk=redemption.pk, scheme_account__configuration_snapshot__isnull=False).exists():
        raise ValidationError('Use the configured full-settlement correction workflow; payments must remain blocked.')
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
def reverse_in_store_cash_contribution(
    *,
    contribution,
    processed_by,
    reason_code,
    reason,
):
    _validate_owner(processed_by)
    normalized_reason = reason.strip()
    if not normalized_reason:
        raise ValidationError({"reason": "Enter the bookkeeping error details."})
    if reason_code not in InStoreCashContributionReversal.ReasonCode.values:
        raise ValidationError({"reason_code": "Select a valid correction reason."})

    account_id = Contribution.objects.only("scheme_account_id").get(
        pk=contribution.pk
    ).scheme_account_id
    account = SchemeAccount.objects.select_for_update().get(pk=account_id)
    locked = (
        Contribution.objects.select_for_update(of=("self",))
        .select_related("scheme_account", "metal_allocation")
        .get(pk=contribution.pk)
    )
    from .plan_policies import require_current_payment_workflow
    require_current_payment_workflow(account)
    if locked.payment_channel != PaymentChannel.IN_STORE_CASH:
        raise ValidationError("Only an in-store cash contribution can be corrected.")
    if locked.status == Contribution.Status.REVERSED:
        raise ValidationError("This in-store cash contribution is already reversed.")
    if locked.status not in SUCCESSFUL_PAYMENT_STATUSES:
        raise ValidationError("Only a recorded in-store cash receipt can be corrected.")
    if InStoreCashContributionReversal.objects.filter(contribution=locked).exists():
        raise ValidationError("This in-store cash contribution is already reversed.")

    reversal_deadline = locked.paid_at + timedelta(
        hours=settings.IN_STORE_CASH_REVERSAL_HOURS
    )
    if timezone.now() > reversal_deadline:
        raise ValidationError(
            "The routine correction window has closed. Escalate this record for "
            "manual financial review."
        )
    if account.status == SchemeAccount.Status.REDEEMED or Redemption.objects.filter(
        scheme_account=account,
        completed_at__gte=locked.paid_at,
        reversal__isnull=True,
    ).exists():
        raise ValidationError(
            "This contribution cannot be reversed after a downstream redemption."
        )
    try:
        allocation = locked.metal_allocation
    except MetalAllocation.DoesNotExist:
        allocation = None
    if allocation is not None and get_metal_balance(account) < allocation.quantity:
        raise ValidationError(
            "The allocated metal is no longer fully available for this correction."
        )

    reversal = InStoreCashContributionReversal(
        contribution=locked,
        reversal_number=_reference(
            "CRV",
            InStoreCashContributionReversal,
            "reversal_number",
        ),
        reason_code=reason_code,
        reason=normalized_reason,
        processed_by=processed_by,
        processed_by_label=_actor_label(processed_by),
    )
    reversal.full_clean()
    reversal.save()
    locked.status = Contribution.Status.REVERSED
    locked.full_clean()
    locked.save(update_fields=["status"])
    if has_monthly_instalments(account):
        reverse_cash_instalment(contribution_id=locked.pk)
    if account.savings_mode == SchemeAccount.SavingsMode.INR_CREDIT:
        from .inr_principal import record_cash_inr_correction
        record_cash_inr_correction(cash_reversal_id=reversal.pk, actor=processed_by)
    record_audit_event(
        action=AuditEvent.Action.IN_STORE_CASH_REVERSAL,
        actor=processed_by,
        reason=normalized_reason,
        scheme_account=account,
        contribution=locked,
        scheme_rate=locked.scheme_rate,
        details={
            "reversal_number": reversal.reversal_number,
            "receipt_reference": locked.gateway_reference,
            "reason_code": reason_code,
            "amount_inr": str(locked.amount),
            "allocation_quantity": str(allocation.quantity) if allocation else None,
        },
    )
    return reversal


@transaction.atomic
def record_scheme_plan_change(*, plan, actor, reason, before, after_overrides=None):
    _validate_owner(actor)
    after_overrides = after_overrides or {}
    after = {
        key: str(after_overrides[key] if key in after_overrides else getattr(plan, key))
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
