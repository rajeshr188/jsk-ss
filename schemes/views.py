import csv
import hashlib
import json
import logging
import math
import uuid

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import (
    ImproperlyConfigured,
    PermissionDenied,
    ValidationError,
)
from django.core.paginator import Paginator
from django.db import transaction
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt

from accounts.models import CustomUser
from accounts.services import issue_customer_invitation, send_customer_invitation

from .enrolment_notifications import (
    send_enrolment_request_decision,
    send_enrolment_request_received,
)
from .forms import (
    AuditReasonForm,
    ContributionForm,
    CustomerCreateForm,
    EnrolmentForm,
    EnrolmentRequestConversionForm,
    EnrolmentRequestDecisionForm,
    InStoreCashContributionForm,
    InStoreCashContributionReversalForm,
    PaymentOperationsForm,
    OwnerPaymentFilterForm,
    RedemptionForm,
    RedemptionReversalForm,
    SchemeRatePublishForm,
    SchemeEnrolmentRequestForm,
    SchemePlanChangeForm,
    SchemePlanForm,
    WebhookRecoveryForm,
)
from .models import (
    Contribution,
    Customer,
    MetalGrade,
    PaymentOperationsControl,
    PaymentWebhookEvent,
    WebhookProcessingAttempt,
    Redemption,
    SchemeAccount,
    SchemeEnrolmentRequest,
    SchemePlan,
    SchemeRate,
)
from .operations import get_payment_availability
from .payments import (
    PaymentGatewayAuthenticationError,
    PaymentGatewayError,
    get_payment_gateway,
    mock_payment_is_enabled,
    payment_gateway_is_configured,
    razorpay_payment_is_enabled,
)
from .permissions import owner_required
from .navigation import fragment_session, private_read_template, application_inbox_url, review_destination
from .selectors import (
    get_cash_balance,
    get_cash_bonus_summary,
    get_contribution_history,
    get_contribution_receipt_summary,
    get_customer_scheme_account,
    get_customer_scheme_summary,
    get_customer_enrolment_request,
    get_customer_enrolment_requests,
    get_latest_customer_invitation,
    get_current_scheme_rate,
    get_current_scheme_rates,
    get_metal_balance,
    get_owner_activity_summary,
    get_owner_audit_events,
    get_owner_contribution_daily_summary,
    get_owner_contributions,
    get_filtered_owner_payments,
    get_payment_scope_summary,
    get_cash_entry_blocker,
    get_owner_readiness,
    get_owner_customers,
    get_owner_application_keys,
    get_owner_application_items,
    get_owner_exception_keys,
    get_financial_exception_counts,
    get_owner_enrolment_requests,
    get_owner_liability_summary,
    get_owner_exception_queue,
    get_pending_payment_exposure,
    get_owner_redemptions,
    get_owner_scheme_reminders,
    get_owner_settlement_review_count,
    get_pending_enrolment_request_count,
    get_redemption_eligibility_summary,
    get_redemption_history,
    get_scheme_statement,
    get_scheme_rate_history,
    get_outstanding_entitlement,
)
from .services import (
    cash_scheme_activity_is_enabled,
    create_invited_customer,
    complete_redemption,
    decide_scheme_enrolment_request,
    enroll_customer,
    enroll_customer_from_request,
    confirm_razorpay_contribution,
    enrolment_request_offer_is_current,
    initiate_razorpay_contribution,
    in_store_cash_contributions_are_enabled,
    preview_in_store_cash_contribution,
    process_razorpay_webhook,
    process_mock_contribution,
    publish_scheme_rate,
    record_in_store_cash_contribution,
    submit_scheme_enrolment_request,
    reverse_redemption,
    reverse_in_store_cash_contribution,
    retry_metal_allocation,
    reconcile_razorpay_webhook,
    update_payment_operations_control,
    withdraw_scheme_enrolment_request,
    WebhookTransientProcessingError,
)


logger = logging.getLogger(__name__)


@login_required
def post_login(request):
    if request.user.is_superuser or request.user.role == CustomUser.Role.OWNER:
        return redirect("schemes:owner_today")
    return redirect("schemes:my_schemes")


def _is_owner(user):
    return user.is_superuser or user.role == CustomUser.Role.OWNER


def _can_view_scheme_account(user, scheme_account):
    return _is_owner(user) or scheme_account.customer.user_id == user.pk


def _safe_csv_cell(value):
    if value is None:
        return ""
    text = str(value)
    if text.lstrip().startswith(("=", "+", "-", "@")):
        return f"'{text}"
    return text


def _local_iso(value):
    return timezone.localtime(value).isoformat() if value else ""


@owner_required
def owner_dashboard(request):
    activity = get_owner_activity_summary()
    payment_availability = {
        grade.code: {
            "grade": grade,
            "availability": get_payment_availability(metal_grade=grade),
        }
        for grade in MetalGrade.objects.all()
    }
    context = {
        "activity": activity,
        "exception_count": get_financial_exception_counts().total,
        "eligibility": get_redemption_eligibility_summary(),
        "liabilities": get_owner_liability_summary(),
        "payment_availability": payment_availability,
        "payments_restricted": any(
            not item["availability"].allowed
            for item in payment_availability.values()
        ),
        "pending_enrolment_request_count": get_pending_enrolment_request_count(),
    }
    return render(request, "schemes/owner_dashboard.html", context)


@owner_required
@require_GET
@never_cache
def owner_today(request):
    from accounts.selectors import get_activation_attention
    from accounts.selectors import customer_account_deletion_queue
    application_keys = get_owner_application_keys()
    exception_keys = get_owner_exception_keys(oldest_first=True)
    activations = get_activation_attention()
    return render(request, "schemes/owner_today.html", {
        "application_count": application_keys.count(),
        "applications": get_owner_application_items(application_keys[:8]),
        "exception_count": exception_keys.count(),
        "exceptions": get_owner_exception_queue(keys=exception_keys[:8]),
        "activation_count": activations.count(), "activations": activations[:8],
        "readiness": get_owner_readiness(),
        "privacy_due_count": customer_account_deletion_queue().filter(owner_review_due_at__lte=timezone.now()).count() if settings.CUSTOMER_ACCOUNT_DELETION_ENABLED else 0,
        "settlement_due_count": get_owner_settlement_review_count(),
    })


@owner_required
@require_GET
@never_cache
def owner_activation_queue(request):
    from accounts.selectors import get_activation_attention
    page = Paginator(get_activation_attention(), 25).get_page(request.GET.get("page"))
    return render(request, "schemes/owner_activation_queue.html", {"activations": page.object_list, "page_obj": page})


def _owner_customer_filter(request):
    value = request.GET.get("customer", "")
    if not value:
        return None
    if not value.isascii() or not value.isdecimal() or len(value) > 10:
        raise Http404
    return get_object_or_404(Customer.objects.select_related("user"), pk=int(value))


@fragment_session
@owner_required
@require_GET
@never_cache
def owner_applications(request):
    focus = request.GET.get("focus", "attention")
    if focus not in {"attention", "waiting", "closed", "all"}:
        focus = "attention"
    kind = request.GET.get("kind", "all")
    if kind not in {"all", "registration", "plan"}:
        kind = "all"
    customer = _owner_customer_filter(request)
    search = request.GET.get("q", "").strip()[:100]
    keys = get_owner_application_keys(focus=focus, kind=kind, customer=customer, search=search)
    page = Paginator(keys, 25).get_page(request.GET.get("page"))
    from .selectors import get_owner_application_stage_counts
    counts = get_owner_application_stage_counts(kind=kind, customer=customer, search=search)
    return render(request, private_read_template(request, "schemes/owner_applications.html", "schemes/includes/application_workspace.html"), {
        "applications": get_owner_application_items(page.object_list),
        "page_obj": page, "focus": focus, "kind": kind, "customer": customer, "search": search,
        "stage_tabs": [{"key": key, "label": label, "count": counts[key]} for key, label in (("attention", "Needs attention"), ("waiting", "Waiting for customer"), ("closed", "Recorded decisions"), ("all", "All records"))],
    })


@owner_required
def payment_operations(request):
    control = PaymentOperationsControl.objects.prefetch_related(
        "schedule_windows", "updated_by"
    ).get(pk=PaymentOperationsControl.SINGLETON_PK)
    form = PaymentOperationsForm(request.POST or None, control=control)
    if request.method == "POST" and form.is_valid():
        try:
            update_payment_operations_control(
                actor=request.user,
                reason=form.cleaned_data["audit_reason"],
                schedule_enabled=form.cleaned_data["schedule_enabled"],
                require_current_day_rate=form.cleaned_data[
                    "require_current_day_rate"
                ],
                global_pause=form.cleaned_data["global_pause"],
                gold_pause=form.cleaned_data["gold_pause"],
                silver_pause=form.cleaned_data["silver_pause"],
                customer_message=form.cleaned_data["customer_message"],
                schedule=form.schedule_values(),
            )
        except ValidationError as error:
            for message in error.messages:
                form.add_error(None, message)
        else:
            messages.success(request, "Payment operations policy updated.")
            return redirect("schemes:payment_operations")
    grade_availability = {
        grade.code: get_payment_availability(metal_grade=grade)
        for grade in MetalGrade.objects.all()
    }
    pending_exposure = get_pending_payment_exposure()
    return render(
        request,
        "schemes/payment_operations.html",
        {
            "control": control,
            "form": form,
            "operations_rows": [
                {
                    "grade": grade,
                    "availability": grade_availability[grade.code],
                    "exposure": pending_exposure[grade.code],
                }
                for grade in MetalGrade.objects.all()
            ],
            "environment_kill_switch": (
                get_payment_availability(
                    metal_grade=MetalGrade.objects.get(code=MetalGrade.GOLD_22K_916)
                ).code
                == "ENVIRONMENT_KILL_SWITCH"
            ),
        },
    )


@owner_required
def scheme_rates(request):
    current_rates = get_current_scheme_rates()
    metal_grades = list(MetalGrade.objects.all())
    if request.method == "POST":
        selected_grade = MetalGrade.objects.filter(
            pk=request.POST.get("metal_grade")
        ).first()
    else:
        selected_grade = MetalGrade.objects.filter(
            code=request.GET.get("grade", MetalGrade.GOLD_22K_916)
        ).first()
    if selected_grade is None:
        selected_grade = MetalGrade.objects.get(code=MetalGrade.GOLD_22K_916)
    form = SchemeRatePublishForm(
        request.POST or None,
        current_rates=current_rates,
        initial={"metal_grade": selected_grade},
    )
    if request.method == "POST" and form.is_valid():
        scheme_rate = publish_scheme_rate(
            metal_grade=form.cleaned_data["metal_grade"],
            rate_per_gram=form.cleaned_data["rate_per_gram"],
            notes=form.cleaned_data["notes"],
            published_by=request.user,
        )
        messages.success(
            request,
            f"Published {scheme_rate.metal_grade.display_name} Scheme Rate at "
            f"₹{scheme_rate.rate_per_gram:.4f}/g.",
        )
        return redirect("schemes:scheme_rates")
    return render(
        request,
        "schemes/scheme_rates.html",
        {
            "current_rates": current_rates,
            "rate_history": get_scheme_rate_history(),
            "form": form,
            "grade_rates": [
                {"grade": grade, "current_rate": current_rates.get(grade.code)}
                for grade in metal_grades
            ],
            "current_rate_values": {
                str(rate.metal_grade_id): str(rate.rate_per_gram)
                for rate in current_rates.values()
                if rate is not None
            },
            "selected_grade": selected_grade,
        },
    )


@owner_required
def redemption_eligibility(request):
    eligibility = get_redemption_eligibility_summary()
    for account in eligibility.eligible_now:
        account.outstanding_entitlement = get_outstanding_entitlement(account)
    return render(
        request,
        "schemes/redemption_eligibility.html",
        {
            "eligibility": eligibility,
            "eligibility_groups": (
                (
                    "Eligible now",
                    "Agreement duration complete; the account remains open until redemption.",
                    eligibility.eligible_now,
                ),
                (
                    "Next 30 days",
                    "Becomes eligible 1–30 days from today.",
                    eligibility.next_30_days,
                ),
                (
                    "Days 31–60",
                    "Becomes eligible 31–60 days from today.",
                    eligibility.next_60_days,
                ),
                (
                    "Days 61–90",
                    "Becomes eligible 61–90 days from today.",
                    eligibility.next_90_days,
                ),
                (
                    "Later",
                    "Active agreements more than 90 days from eligibility.",
                    eligibility.later,
                ),
                (
                    "Redeemed",
                    "Accounts already completed through redemption.",
                    eligibility.redeemed,
                ),
            ),
        },
    )


@owner_required
def redemption_list(request):
    return render(
        request,
        "schemes/redemption_list.html",
        {"redemptions": get_owner_redemptions()},
    )


@owner_required
def audit_log(request):
    return render(
        request,
        "schemes/audit_log.html",
        {"audit_events": get_owner_audit_events()},
    )


@owner_required
def reminder_delivery_log(request):
    return render(
        request,
        "schemes/reminder_delivery_log.html",
        {
            "reminders": get_owner_scheme_reminders()[:200],
            "reminders_enabled": settings.SCHEME_REMINDERS_ENABLED,
            "eligibility_days": settings.SCHEME_REMINDER_ELIGIBILITY_DAYS,
        },
    )


@fragment_session
@owner_required
@require_GET
def exception_queue(request):
    category = request.GET.get("category", "all")
    if category not in {"all", "allocation", "webhook", "checkout", "optional_order"}:
        category = "all"
    oldest = request.GET.get("order") == "oldest"
    page = Paginator(get_owner_exception_keys(category=category, oldest_first=oldest), 25).get_page(request.GET.get("page"))
    return render(request, private_read_template(request, "schemes/exception_queue.html", "schemes/includes/exception_workspace.html"), {
        "exceptions": get_owner_exception_queue(keys=page.object_list), "page_obj": page,
        "category": category, "oldest_first": oldest,
    })


@owner_required
def webhook_recovery(request, event_id):
    event = get_object_or_404(
        PaymentWebhookEvent.objects.select_related(
            "contribution",
            "contribution__scheme_account",
            "contribution__scheme_account__customer",
        ).prefetch_related("processing_attempts"),
        pk=event_id,
        gateway="razorpay",
        event_type="payment.captured",
    )
    form = WebhookRecoveryForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        apply = form.cleaned_data["action"] == WebhookRecoveryForm.Action.APPLY
        try:
            result = reconcile_razorpay_webhook(
                webhook_event_id=event.pk,
                apply=apply,
                performed_by=request.user,
                reason=form.cleaned_data["reason"],
            )
        except (ImproperlyConfigured, PaymentGatewayError, ValidationError) as error:
            form.add_error(None, str(error))
        else:
            if result.applied and result.outcome == "ELIGIBLE_FOR_RECOVERY":
                messages.success(
                    request,
                    "The captured payment was recovered and entitlement was applied "
                    "idempotently.",
                )
            elif result.applied:
                messages.success(
                    request,
                    "The already-confirmed contribution was reconciled without "
                    "creating another entitlement.",
                )
            elif result.outcome == "ELIGIBLE_FOR_RECOVERY":
                messages.success(
                    request,
                    "Provider check passed. Review the evidence, then use Apply "
                    "verified recovery.",
                )
            elif result.outcome == "ALREADY_PROCESSED":
                messages.info(
                    request,
                    "The provider payment already matches the confirmed contribution.",
                )
            else:
                messages.warning(
                    request,
                    "Automatic recovery remains blocked. Follow the manual "
                    "reconciliation/refund runbook.",
                )
            return redirect("schemes:webhook_recovery", event_id=event.pk)
    return render(
        request,
        "schemes/webhook_recovery.html",
        {
            "event": event,
            "form": form,
            "can_apply_recovery": event.processing_attempts.filter(
                source=WebhookProcessingAttempt.Source.OWNER_RECOVERY,
                outcome__in=[
                    WebhookProcessingAttempt.Outcome.ELIGIBLE_FOR_RECOVERY,
                    WebhookProcessingAttempt.Outcome.ALREADY_PROCESSED,
                ],
            ).exists(),
        },
    )


@never_cache
@login_required
def contribution_receipt(request, contribution_id):
    contribution = get_object_or_404(
        Contribution.objects.select_related(
            "scheme_account",
            "scheme_account__customer",
            "scheme_account__customer__user",
            "metal_allocation",
            "metal_allocation__scheme_rate",
            "cash_receipt",
            "cash_receipt__received_by",
            "cash_reversal",
            "cash_reversal__processed_by",
        ),
        pk=contribution_id,
        status__in=[
            Contribution.Status.PAID,
            Contribution.Status.PAID_UNALLOCATED,
            Contribution.Status.REVERSED,
        ],
    )
    if not _can_view_scheme_account(request.user, contribution.scheme_account):
        raise Http404
    try:
        receipt = get_contribution_receipt_summary(contribution)
    except ValidationError:
        return render(request, "schemes/document_review_required.html", status=409)
    return render(
        request,
        "schemes/contribution_receipt.html",
        {"receipt": receipt},
    )


@never_cache
@login_required
def scheme_statement(request, scheme_number):
    account = get_object_or_404(
        SchemeAccount.objects.select_related("customer", "customer__user", "plan"),
        scheme_number=scheme_number,
    )
    if not _can_view_scheme_account(request.user, account):
        raise Http404
    try:
        statement = get_scheme_statement(account)
    except ValidationError:
        return render(request, "schemes/document_review_required.html", status=409)
    return render(
        request,
        "schemes/scheme_statement.html",
        {"statement": statement},
    )


@owner_required
@never_cache
def contribution_export(request):
    customer, contributions, filter_form = _owner_payment_scope(request)
    if not filter_form.is_valid():
        return HttpResponse("Invalid payment filters. Review the selected dates and filters.", status=400)
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = (
        'attachment; filename="jsk-contributions.csv"'
    )
    writer = csv.writer(response)
    writer.writerow(
        [
            "receipt_number",
            "paid_at",
            "customer_number",
            "customer",
            "scheme_number",
            "savings_mode",
            "amount_inr",
            "payment_gateway",
            "gateway_mode",
            "payment_reference",
            "payment_status",
            "metal",
            "scheme_rate_inr_per_g",
            "quantity_g",
            "payment_channel",
            "cash_received_by",
            "paper_receipt_number",
            "cash_reversal_number",
            "cash_reversed_at",
            "cash_reversal_reason_code",
        ]
    )
    contributions = contributions.filter(
        status__in=[
            Contribution.Status.PAID,
            Contribution.Status.PAID_UNALLOCATED,
            Contribution.Status.REVERSED,
        ]
    )
    for contribution in contributions:
        receipt = get_contribution_receipt_summary(contribution)
        allocation = receipt.allocation
        cash_receipt = (
            contribution.cash_receipt if hasattr(contribution, "cash_receipt") else None
        )
        cash_reversal = (
            contribution.cash_reversal
            if hasattr(contribution, "cash_reversal")
            else None
        )
        writer.writerow(
            [
                receipt.receipt_number,
                _local_iso(contribution.paid_at),
                _safe_csv_cell(contribution.scheme_account.customer.customer_number),
                _safe_csv_cell(contribution.scheme_account.customer.full_name),
                _safe_csv_cell(contribution.scheme_account.scheme_number),
                contribution.scheme_account.savings_mode,
                f"{contribution.amount:.2f}",
                _safe_csv_cell(contribution.payment_gateway),
                contribution.gateway_mode,
                _safe_csv_cell(contribution.gateway_reference),
                contribution.status,
                allocation.metal if allocation else "",
                f"{allocation.scheme_rate.rate_per_gram:.4f}" if allocation else "",
                f"{allocation.quantity:.6f}" if allocation else "",
                contribution.payment_channel,
                _safe_csv_cell(cash_receipt.received_by_label) if cash_receipt else "",
                _safe_csv_cell(cash_receipt.paper_receipt_number) if cash_receipt else "",
                cash_reversal.reversal_number if cash_reversal else "",
                _local_iso(cash_reversal.reversed_at) if cash_reversal else "",
                cash_reversal.reason_code if cash_reversal else "",
            ]
        )
    return response


@owner_required
def redemption_export(request):
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="jsk-redemptions.csv"'
    writer = csv.writer(response)
    writer.writerow(
        [
            "redemption_number",
            "completed_at",
            "status",
            "reversal_number",
            "reversed_at",
            "customer_number",
            "customer",
            "scheme_number",
            "savings_mode",
            "settlement_type",
            "cash_amount_inr",
            "cash_principal_inr",
            "cash_bonus_inr",
            "gold_quantity_g",
            "silver_quantity_g",
            "external_reference",
            "processed_by",
        ]
    )
    for redemption in get_owner_redemptions():
        reversal = redemption.reversal if hasattr(redemption, "reversal") else None
        writer.writerow(
            [
                redemption.redemption_number,
                _local_iso(redemption.completed_at),
                "REVERSED" if reversal else redemption.status,
                reversal.reversal_number if reversal else "",
                _local_iso(reversal.reversed_at) if reversal else "",
                _safe_csv_cell(redemption.scheme_account.customer.customer_number),
                _safe_csv_cell(redemption.scheme_account.customer.full_name),
                _safe_csv_cell(redemption.scheme_account.scheme_number),
                redemption.scheme_account.savings_mode,
                redemption.settlement_type,
                f"{redemption.cash_amount:.2f}" if redemption.cash_amount is not None else "",
                f"{redemption.cash_principal_amount:.2f}" if redemption.cash_principal_amount is not None else "",
                f"{redemption.cash_bonus_amount:.2f}" if redemption.cash_bonus_amount is not None else "",
                f"{redemption.gold_quantity:.6f}" if redemption.gold_quantity is not None else "",
                f"{redemption.silver_quantity:.6f}" if redemption.silver_quantity is not None else "",
                _safe_csv_cell(redemption.external_reference),
                _safe_csv_cell(redemption.processed_by.email),
            ]
        )
    return response


@owner_required
def redemption_create(request, scheme_number):
    account = get_object_or_404(
        SchemeAccount.objects.select_related("customer", "plan"),
        scheme_number=scheme_number,
    )
    # Do not present the legacy partial-redemption form for a configured contract.
    # Its independent service-level full-only settlement gate remains authoritative.
    if account.configuration_snapshot_id:
        raise Http404
    outstanding = get_outstanding_entitlement(account)
    cash_bonus = (
        get_cash_bonus_summary(account)
        if account.savings_mode == SchemeAccount.SavingsMode.CASH
        else None
    )
    if (
        account.effective_status != SchemeAccount.Status.REDEMPTION_ELIGIBLE
        or outstanding <= 0
    ):
        raise Http404
    form = RedemptionForm(
        request.POST or None,
        scheme_account=account,
        outstanding=outstanding,
    )
    if request.method == "POST" and form.is_valid():
        try:
            redemption = complete_redemption(
                scheme_account=account,
                settlement_type=form.cleaned_data["settlement_type"],
                amount=form.cleaned_data["amount"],
                external_reference=form.cleaned_data["external_reference"],
                notes=form.cleaned_data["notes"],
                idempotency_key=form.cleaned_data["idempotency_key"],
                processed_by=request.user,
                audit_reason=form.cleaned_data["audit_reason"],
            )
        except ValidationError as error:
            if hasattr(error, "message_dict"):
                for field, field_errors in error.message_dict.items():
                    for field_error in field_errors:
                        form.add_error(field if field in form.fields else None, field_error)
            else:
                for field_error in error.messages:
                    form.add_error(None, field_error)
        else:
            messages.success(
                request,
                f"Redemption {redemption.redemption_number} completed.",
            )
            return redirect("schemes:redemption_list")
    return render(
        request,
        "schemes/redemption_form.html",
        {
            "scheme_account": account,
            "outstanding": outstanding,
            "cash_bonus": cash_bonus,
            "form": form,
        },
    )


@owner_required
def redemption_reverse(request, redemption_number):
    redemption = get_object_or_404(
        Redemption.objects.select_related(
            "scheme_account",
            "scheme_account__customer",
            "processed_by",
        ),
        redemption_number=redemption_number,
        reversal__isnull=True,
    )
    if redemption.scheme_account.configuration_snapshot_id:
        settlement = get_object_or_404(redemption.scheme_account.closure_requests.filter(settlements__redemption=redemption))
        return redirect("schemes:configured_settlement", request_id=settlement.pk)
    form = RedemptionReversalForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            reversal = reverse_redemption(
                redemption=redemption,
                processed_by=request.user,
                reason=form.cleaned_data["reason"],
            )
        except ValidationError as error:
            for message in error.messages:
                form.add_error(None, message)
        else:
            messages.success(
                request,
                f"Reversal {reversal.reversal_number} recorded; the original redemption remains in the audit trail.",
            )
            return redirect("schemes:redemption_list")
    return render(
        request,
        "schemes/redemption_reversal_form.html",
        {"redemption": redemption, "form": form},
    )


@fragment_session
@owner_required
@require_GET
def customer_list(request):
    search = request.GET.get("q", "").strip()[:100]
    page = Paginator(get_owner_customers(search=search), 25).get_page(request.GET.get("page"))
    return render(
        request,
        private_read_template(request, "schemes/customer_list.html", "schemes/includes/customer_results.html"),
        {"customers": page.object_list, "page_obj": page, "search": search},
    )


@owner_required
def customer_add(request):
    form = CustomerCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            customer, invitation, raw_token = create_invited_customer(
                full_name=form.cleaned_data["full_name"],
                email=form.cleaned_data["email"],
                mobile_number=form.cleaned_data["mobile_number"],
                address=form.cleaned_data["address"],
                invited_by=request.user,
            )
        except ValidationError as error:
            if hasattr(error, "message_dict"):
                for field, field_errors in error.message_dict.items():
                    for field_error in field_errors:
                        form.add_error(
                            field if field in form.fields else None,
                            field_error,
                        )
            else:
                for field_error in error.messages:
                    form.add_error(None, field_error)
        else:
            setup_url = request.build_absolute_uri(
                reverse(
                    "customer_invitation_accept",
                    kwargs={"invitation_id": invitation.pk, "token": raw_token},
                )
            )
            if send_customer_invitation(
                invitation=invitation,
                raw_token=raw_token,
                setup_url=setup_url,
            ):
                messages.success(
                    request,
                    f"Customer {customer.full_name} created. The login setup email was accepted by the email provider.",
                )
            else:
                messages.warning(
                    request,
                    f"Customer {customer.full_name} was created, but the login setup email could not be sent. Use Resend invitation below.",
                )
            return redirect("schemes:customer_detail", customer_id=customer.pk)
    return render(request, "schemes/customer_form.html", {"form": form})


@never_cache
@owner_required
@require_GET
def customer_detail(request, customer_id):
    customer = get_object_or_404(
        get_owner_customers(),
        pk=customer_id,
    )
    from .selectors import get_customer_document_payments, get_customer_privacy_requests
    privacy_page = Paginator(get_customer_privacy_requests(customer), 25).get_page(request.GET.get("privacy_page")) if request.GET.get("section") == "access" and settings.CUSTOMER_ACCOUNT_DELETION_ENABLED else None
    document_receipts = Paginator(get_customer_document_payments(customer.user), 25).get_page(request.GET.get("receipt_page")) if request.GET.get("section") == "documents" else None
    plans_page = Paginator(customer.scheme_accounts.select_related("plan", "metal_grade").order_by("-start_date", "-pk"), 12).get_page(request.GET.get("page"))
    return render(
        request,
        "schemes/customer_detail.html",
        {
            "customer": customer,
            "latest_invitation": get_latest_customer_invitation(customer),
            "page_obj": plans_page, "document_receipts": document_receipts, "privacy_page": privacy_page,
            "section": request.GET.get("section") if request.GET.get("section") in {"plans", "documents", "access"} else "summary",
            "cash_scheme_activity_enabled": cash_scheme_activity_is_enabled(),
            "in_store_cash_enabled": in_store_cash_contributions_are_enabled(),
        },
    )


@owner_required
@require_POST
def customer_invitation_resend(request, customer_id):
    customer = get_object_or_404(Customer.objects.select_related("user"), pk=customer_id)
    try:
        invitation, raw_token = issue_customer_invitation(
            user=customer.user,
            created_by=request.user,
        )
    except ValidationError as error:
        messages.error(request, " ".join(error.messages))
    else:
        setup_url = request.build_absolute_uri(
            reverse(
                "customer_invitation_accept",
                kwargs={"invitation_id": invitation.pk, "token": raw_token},
            )
        )
        if send_customer_invitation(
            invitation=invitation,
            raw_token=raw_token,
            setup_url=setup_url,
        ):
            messages.success(
                request,
                "A new login setup email was accepted by the email provider. The previous invitation is no longer valid.",
            )
        else:
            messages.warning(
                request,
                "The new invitation was created, but its email could not be sent. You can try again safely.",
            )
    return redirect("schemes:customer_detail", customer_id=customer.pk)


@owner_required
def customer_enroll(request, customer_id):
    customer = get_object_or_404(Customer, pk=customer_id)
    form = EnrolmentForm(
        request.POST or None,
        initial={"start_date": timezone.localdate(), "agreed_months": 12},
    )
    if request.method == "POST" and form.is_valid():
        try:
            account = enroll_customer(
                customer=customer,
                plan=form.cleaned_data["plan"],
                metal_grade=form.cleaned_data["metal_grade"],
                start_date=form.cleaned_data["start_date"],
                agreed_months=form.cleaned_data["agreed_months"],
                selected_contribution_amount=form.cleaned_data.get("selected_contribution_amount"),
                selected_amount_confirmed=form.cleaned_data.get("selected_amount_confirmed", False),
                expected_configuration_id=form.cleaned_data.get("expected_configuration_id"),
                expected_plan_digest=form.cleaned_data.get("expected_plan_digest"),
                performed_by=request.user,
                reason=form.cleaned_data["audit_reason"],
            )
        except ValidationError as error:
            for field, field_errors in error.message_dict.items():
                for field_error in field_errors:
                    form.add_error(field if field in form.fields else None, field_error)
        else:
            messages.success(request, f"Scheme {account.scheme_number} created.")
            return redirect("schemes:customer_detail", customer_id=customer.pk)
    return render(
        request,
        "schemes/enrolment_form.html",
        {"customer": customer, "form": form},
    )


def _customer_for_request_user(user):
    if user.role != CustomUser.Role.CUSTOMER or not user.is_active:
        raise PermissionDenied
    try:
        return user.customer_profile
    except Customer.DoesNotExist as error:
        raise PermissionDenied from error


def _add_service_errors(form, error):
    if hasattr(error, "message_dict"):
        for field, field_errors in error.message_dict.items():
            for field_error in field_errors:
                form.add_error(field if field in form.fields else None, field_error)
    else:
        for field_error in error.messages:
            form.add_error(None, field_error)


@login_required
def scheme_enrolment_request_create(request, plan_id):
    if not settings.CUSTOMER_ENROLMENT_REQUESTS_ENABLED:
        raise Http404
    customer = _customer_for_request_user(request.user)
    from .selectors import get_public_scheme_plans
    plan = get_object_or_404(
        get_public_scheme_plans(),
        pk=plan_id,
        active=True,
        publicly_listed=True,
    )
    form = SchemeEnrolmentRequestForm(request.POST or None, plan=plan)
    if request.method == "POST" and form.is_valid():
        try:
            submission = submit_scheme_enrolment_request(
                customer=customer,
                plan=plan,
                metal_grade=form.cleaned_data["metal_grade"],
                requested_contribution_amount=form.cleaned_data[
                    "requested_contribution_amount"
                ],
                requested_months=form.cleaned_data["requested_months"],
                customer_message=form.cleaned_data["customer_message"],
                actor=request.user,
                expected_plan_digest=form.cleaned_data.get("expected_plan_digest"),
            )
        except ValidationError as error:
            _add_service_errors(form, error)
        else:
            if submission.created:
                delivery = send_enrolment_request_received(
                    enrolment_request=submission.enrolment_request,
                    base_url=request.build_absolute_uri("/").rstrip("/"),
                )
                if delivery.customer_accepted:
                    messages.success(
                        request,
                        "Your request was recorded. The email provider accepted your acknowledgement.",
                    )
                else:
                    messages.warning(
                        request,
                        "Your request was recorded, but its acknowledgement email could not be sent.",
                    )
                if not delivery.owner_recipient_count:
                    messages.warning(
                        request,
                        "The request is safely recorded, but no active owner email recipient is configured.",
                    )
                elif not delivery.owner_accepted_count:
                    messages.warning(
                        request,
                        "The request is safely recorded, but owner email notification failed.",
                    )
            else:
                messages.info(
                    request,
                    "A pending request already exists for this plan and metal grade.",
                )
            return redirect(
                "schemes:my_enrolment_request_detail",
                request_id=submission.enrolment_request.pk,
            )
    return render(
        request,
        "schemes/enrolment_request_form.html",
        {"plan": plan, "form": form},
    )


@login_required
@never_cache
def my_enrolment_requests(request):
    _customer_for_request_user(request.user)
    return render(
        request,
        "schemes/my_enrolment_requests.html",
        {
            "enrolment_requests": get_customer_enrolment_requests(request.user),
            "requests_enabled": settings.CUSTOMER_ENROLMENT_REQUESTS_ENABLED,
        },
    )


@login_required
@never_cache
def my_enrolment_request_detail(request, request_id):
    _customer_for_request_user(request.user)
    enrolment_request = get_customer_enrolment_request(request.user, request_id)
    if enrolment_request is None:
        raise Http404
    return render(
        request,
        "schemes/my_enrolment_request_detail.html",
        {
            "enrolment_request": enrolment_request,
            "offer_is_current": enrolment_request_offer_is_current(
                enrolment_request
            ),
        },
    )


@login_required
@require_POST
def my_enrolment_request_withdraw(request, request_id):
    _customer_for_request_user(request.user)
    enrolment_request = get_customer_enrolment_request(request.user, request_id)
    if enrolment_request is None:
        raise Http404
    try:
        enrolment_request = withdraw_scheme_enrolment_request(
            enrolment_request=enrolment_request,
            actor=request.user,
        )
    except ValidationError as error:
        messages.error(request, " ".join(error.messages))
    else:
        if enrolment_request.status == SchemeEnrolmentRequest.Status.WITHDRAWN:
            messages.success(request, "Your enrolment request was withdrawn.")
        else:
            messages.info(request, "The request had already reached its expiry date.")
    return redirect("schemes:my_enrolment_request_detail", request_id=request_id)


@owner_required
def owner_enrolment_request_list(request):
    page = Paginator(get_owner_enrolment_requests(), 25).get_page(request.GET.get("page"))
    return render(
        request,
        "schemes/owner_enrolment_request_list.html",
        {"enrolment_requests": page.object_list, "page_obj": page},
    )


@owner_required
def owner_enrolment_request_detail(request, request_id):
    enrolment_request = get_object_or_404(
        get_owner_enrolment_requests(),
        pk=request_id,
    )
    return render(
        request,
        "schemes/owner_enrolment_request_detail.html",
        {
            "enrolment_request": enrolment_request,
            "offer_is_current": enrolment_request_offer_is_current(enrolment_request),
            "decision_form": EnrolmentRequestDecisionForm(),
            "form": EnrolmentRequestConversionForm(enrolment_request=enrolment_request),
        },
    )


def _owner_request_decision(request, request_id, status):
    enrolment_request = get_object_or_404(
        get_owner_enrolment_requests(),
        pk=request_id,
    )
    form = EnrolmentRequestDecisionForm(request.POST)
    if form.is_valid():
        try:
            enrolment_request = decide_scheme_enrolment_request(
                enrolment_request=enrolment_request,
                status=status,
                actor=request.user,
                reason=form.cleaned_data["reason"],
            )
        except ValidationError as error:
            _add_service_errors(form, error)
        else:
            delivery = send_enrolment_request_decision(
                enrolment_request=enrolment_request,
                base_url=request.build_absolute_uri("/").rstrip("/"),
            )
            message = f"Request marked {enrolment_request.get_status_display().lower()}."
            if delivery.customer_accepted:
                messages.success(
                    request,
                    f"{message} The email provider accepted the customer notice.",
                )
            else:
                messages.warning(
                    request,
                    f"{message} The customer notice could not be sent.",
                )
            return redirect(application_inbox_url(request)) if request.POST.get("return_to") else redirect("schemes:owner_enrolment_request_list")
    return render(
        request,
        "schemes/owner_enrolment_request_detail.html",
        {
            "enrolment_request": enrolment_request,
            "offer_is_current": enrolment_request_offer_is_current(enrolment_request),
            "decision_form": form,
            "form": EnrolmentRequestConversionForm(enrolment_request=enrolment_request),
        },
        status=400,
    )


@owner_required
@require_POST
def owner_enrolment_request_decline(request, request_id):
    return _owner_request_decision(
        request,
        request_id,
        SchemeEnrolmentRequest.Status.DECLINED,
    )


@owner_required
@require_POST
def owner_enrolment_request_expire(request, request_id):
    return _owner_request_decision(
        request,
        request_id,
        SchemeEnrolmentRequest.Status.EXPIRED,
    )


@owner_required
def owner_enrolment_request_enroll(request, request_id):
    enrolment_request = get_object_or_404(
        get_owner_enrolment_requests(),
        pk=request_id,
    )
    form = EnrolmentRequestConversionForm(
        request.POST or None,
        enrolment_request=enrolment_request,
    )
    if request.method == "POST" and form.is_valid():
        try:
            account, created = enroll_customer_from_request(
                enrolment_request=enrolment_request,
                actor=request.user,
                current_terms_confirmed=form.cleaned_data["current_terms_confirmed"],
                start_date=form.cleaned_data["start_date"],
                agreed_months=form.cleaned_data["agreed_months"],
                reason=form.cleaned_data["audit_reason"],
            )
        except ValidationError as error:
            _add_service_errors(form, error)
        else:
            if created:
                enrolment_request.refresh_from_db()
                delivery = send_enrolment_request_decision(
                    enrolment_request=enrolment_request,
                    base_url=request.build_absolute_uri("/").rstrip("/"),
                )
                if delivery.customer_accepted:
                    messages.success(
                        request,
                        f"Scheme {account.scheme_number} created; the email provider accepted the customer notice.",
                    )
                else:
                    messages.warning(
                        request,
                        f"Scheme {account.scheme_number} was created, but the customer notice could not be sent.",
                    )
            else:
                messages.info(request, f"Scheme {account.scheme_number} already exists.")
            return redirect(review_destination(request, "schemes:owner_enrolment_request_detail", request_id=request_id))
    return render(
        request,
        "schemes/enrolment_request_conversion.html",
        {
            "enrolment_request": enrolment_request,
            "offer_is_current": enrolment_request_offer_is_current(enrolment_request),
            "form": form,
            "decision_form": EnrolmentRequestDecisionForm(),
        },
    )


@owner_required
def plan_configuration_list(request):
    from .selectors import get_plan_configurations
    page = Paginator(get_plan_configurations(), 20).get_page(request.GET.get("page"))
    return render(request, "schemes/configuration_list.html", {"page": page})


@owner_required
@require_http_methods(["GET", "POST"])
@never_cache
def plan_configuration_create(request, previous_id=None, independent=False):
    from .forms import PlanConfigurationForm
    from .models import SchemePlanConfiguration
    from .plan_configuration import EDITABLE_CONFIGURATION_FIELDS, create_configuration_version

    previous = get_object_or_404(SchemePlanConfiguration, pk=previous_id) if previous_id else None
    if independent or (previous and previous.policy_schema_version == 2):
        from .configuration_forms import IndependentConfigurationForm
        form = IndependentConfigurationForm(request.POST if request.method == "POST" else None, previous=previous)
        preview = None
        if request.method == "POST" and form.is_valid():
            action = request.POST.get("action")
            if action == "preview":
                preview = form.configuration
            elif action == "save":
                try:
                    configuration = create_configuration_version(values=form.configuration_values(),
                        actor=request.user, reason=form.cleaned_data["reason"], previous_id=previous_id)
                except ValidationError as error:
                    _add_service_errors(form, error)
                else:
                    messages.success(request, "Preparation version recorded. Publication, enrolment and payments remain gated.")
                    return redirect("schemes:plan_configuration_detail", configuration_id=configuration.pk)
            else:
                form.add_error(None, "Choose Review configuration or Save immutable version.")
        return render(request, "schemes/independent_configuration_form.html",
            {"form": form, "previous": previous, "preview": preview})
    initial = {field: getattr(previous, field) for field in EDITABLE_CONFIGURATION_FIELDS} if previous else None
    if previous:
        initial["schedule_family"] = "MONTHLY_COMPLETION" if previous.instalment_policy == "MONTHLY_COMPLETION" else "CALENDAR"
        initial["schedule_period"] = previous.period_basis or ""
        initial["completion_rule"] = previous.eligibility_policy
        initial["missed_outcome"] = previous.missed_payment_policy
    form = PlanConfigurationForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        try:
            configuration = create_configuration_version(
                values=form.configuration_values(),
                actor=request.user, reason=form.cleaned_data["reason"], previous_id=previous_id,
            )
        except ValidationError as error:
            _add_service_errors(form, error)
        else:
            messages.success(request, "Configuration version recorded. It is not a published offer.")
            return redirect("schemes:plan_configuration_detail", configuration_id=configuration.pk)
    return render(request, "schemes/configuration_form.html", {"form": form, "previous": previous})


@owner_required
def plan_configuration_detail(request, configuration_id):
    from .forms import ConfigurationPreviewForm
    from .models import SchemePlanConfiguration
    from .plan_configuration import preview_configuration_agreement

    configuration = get_object_or_404(SchemePlanConfiguration, pk=configuration_id)
    if configuration.policy_schema_version == 2:
        return render(request, "schemes/configuration_detail.html", {"configuration": configuration})
    form = ConfigurationPreviewForm(request.POST or None, initial={
        "amount": configuration.fixed_amount or configuration.minimum_amount,
        "months": configuration.default_months,
    })
    preview = None
    if request.method == "POST" and form.is_valid():
        try:
            preview = preview_configuration_agreement(configuration=configuration, **form.cleaned_data)
        except ValidationError as error:
            _add_service_errors(form, error)
    return render(request, "schemes/configuration_detail.html", {
        "configuration": configuration, "form": form, "preview": preview,
    })


@owner_required
@require_http_methods(["GET", "POST"])
@never_cache
def configured_plan_create(request, configuration_id):
    from .forms import ConfiguredPlanDraftForm
    from .models import SchemePlanConfiguration
    from .plan_configuration import create_configured_plan_draft

    configuration = get_object_or_404(SchemePlanConfiguration, pk=configuration_id)
    if configuration.policy_schema_version == 2:
        from .configuration_forms import IndependentPlanDraftForm
        form = IndependentPlanDraftForm(request.POST if request.method == "POST" else None, configuration=configuration)
    else:
        form = ConfiguredPlanDraftForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        try:
            create_configured_plan_draft(configuration_id=configuration.pk, actor=request.user, **form.cleaned_data)
        except ValidationError as error:
            _add_service_errors(form, error)
        else:
            messages.success(request, "Preparation-only plan created and audited. Publication review and the configured-plan release gate are required before enrolment.")
            return redirect("schemes:plan_list")
    return render(request, "schemes/configured_plan_form.html", {"form": form, "configuration": configuration})


@owner_required
def configured_plan_publication(request, plan_id):
    from .forms import ConfiguredPlanPublicationForm
    from .plan_governance import plan_edit_digest
    from .plan_publication import set_configured_plan_publication

    plan = get_object_or_404(SchemePlan.objects.select_related("configuration", "publication_revision"),
                             pk=plan_id, configuration__isnull=False)
    publish = not (plan.active or plan.publicly_listed)
    form = ConfiguredPlanPublicationForm(request.POST or None, initial={"expected_digest": plan_edit_digest(plan)})
    if request.method == "POST" and form.is_valid():
        try:
            set_configured_plan_publication(plan_id=plan.pk, publish=publish, actor=request.user,
                **form.cleaned_data)
        except ValidationError as error:
            _add_service_errors(form, error)
        else:
            messages.success(request, "Offer published for new applications." if publish else
                             "Offer withdrawn. Existing agreements and their rights are unchanged.")
            return redirect("schemes:plan_list")
    return render(request, "schemes/plan_publication.html", {"plan": plan, "form": form,
        "publish": publish, "release_enabled": settings.CONFIGURED_PLANS_ENABLED})


@owner_required
def plan_list(request):
    from .selectors import get_owner_plan_configuration
    return render(request, "schemes/plan_list.html", {
        "plans": get_owner_plan_configuration(),
        "configured_plans_enabled": settings.CONFIGURED_PLANS_ENABLED,
        "cash_scheme_activity_enabled": cash_scheme_activity_is_enabled(),
    })


@owner_required
def plan_add(request):
    from .plan_governance import save_scheme_plan
    form = SchemePlanForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            plan, _ = save_scheme_plan(
                values={field: form.cleaned_data[field] for field in form.Meta.fields if field in form.cleaned_data},
                metal_grades=form.cleaned_data["metal_grades"], actor=request.user,
                reason=form.cleaned_data["audit_reason"],
            )
        except ValidationError as error:
            _add_service_errors(form, error)
        else:
            messages.success(request, f"Plan {plan.name} created and audited; not publicly listed.")
            return redirect("schemes:plan_list")
    return render(request, "schemes/plan_form.html", {"form": form})


@owner_required
@require_http_methods(["GET", "POST"])
@never_cache
def plan_edit(request, plan_id):
    from .plan_governance import save_scheme_plan
    from .selectors import get_plan_edit_impact
    plan = get_object_or_404(SchemePlan, pk=plan_id)
    if plan.configuration_id and plan.configuration.policy_schema_version == 2:
        from .configuration_forms import IndependentPlanDraftForm
        form = IndependentPlanDraftForm(request.POST if request.method == "POST" else None,
            configuration=plan.configuration, plan=plan)
        if request.method == "POST" and form.is_valid():
            try:
                save_scheme_plan(plan_id=plan.pk, expected_digest=form.cleaned_data["expected_digest"],
                    values={name: form.cleaned_data[name] for name in ("name", "code", "description")},
                    metal_grades=form.cleaned_data["metal_grades"], actor=request.user, reason=form.cleaned_data["reason"])
            except ValidationError as error:
                _add_service_errors(form, error)
            else:
                messages.success(request, "Draft reviewed and saved. Policy, publication and enrolment remain locked.")
                return redirect("schemes:plan_list")
        return render(request, "schemes/configured_plan_form.html",
            {"form": form, "configuration": plan.configuration, "plan": plan})
    form = SchemePlanChangeForm(request.POST or None, instance=plan)
    if request.method == "POST" and form.is_valid():
        try:
            plan, changed = save_scheme_plan(
                plan_id=plan.pk, expected_digest=form.cleaned_data["expected_digest"],
                values={field: form.cleaned_data[field] for field in form.Meta.fields if field in form.cleaned_data},
                metal_grades=form.cleaned_data["metal_grades"], actor=request.user,
                reason=form.cleaned_data["audit_reason"],
            )
        except ValidationError as error:
            _add_service_errors(form, error)
        else:
            if changed:
                messages.success(request, f"Plan {plan.name} updated and audited.")
            else:
                messages.info(request, "No plan values changed.")
            return redirect("schemes:plan_list")
    return render(
        request,
        "schemes/plan_form.html",
        {"form": form, "plan": plan, "impact": get_plan_edit_impact(plan)},
    )


@login_required
@never_cache
def my_schemes(request, section="home"):
    from .selectors import get_customer_payment_availability, get_customer_plan_next_action, get_customer_request_progress
    from accounts.application_selectors import get_customer_plan_applications

    account_page = Paginator(get_customer_scheme_summary(request.user), 12).get_page(request.GET.get("page"))
    accounts = list(account_page.object_list)
    for account in accounts:
        account.payment_availability = get_customer_payment_availability(account)
        account.next_action = get_customer_plan_next_action(account, account.payment_availability)
        if account.savings_mode == SchemeAccount.SavingsMode.CASH:
            account.cash_bonus = get_cash_bonus_summary(account)
        elif account.metal_grade_id:
            account.current_scheme_rate = get_current_scheme_rate(account.metal_grade)
    applications = list(get_customer_plan_applications(request.user)[:3])
    actions = {account.pk: account.next_action for account in accounts}
    for application in applications:
        application.next_action = actions.get(application.scheme_account_id)
    from .selectors import get_customer_attention_accounts
    attention = list(get_customer_attention_accounts(request.user))
    for account in attention:
        account.next_action = get_customer_plan_next_action(account)
    return render(
        request,
        "schemes/my_schemes.html",
        {
            "scheme_accounts": accounts,
            "page_obj": account_page, "section": section, "attention_accounts": attention,
            "plan_applications": applications,
            "application_updates": get_customer_request_progress(request.user, attention_only=True),
            "mock_payment_enabled": mock_payment_is_enabled(),
            "payment_gateway_enabled": payment_gateway_is_configured(),
            "cash_scheme_activity_enabled": cash_scheme_activity_is_enabled(),
            "enrolment_requests_enabled": (
                settings.CUSTOMER_ENROLMENT_REQUESTS_ENABLED
            ),
        },
    )


@login_required
@require_GET
@never_cache
def customer_applications(request):
    customer = Customer.objects.filter(user=request.user).first()
    keys = get_owner_application_keys(focus="all", kind="plan", customer=customer) if customer else SchemeEnrolmentRequest.objects.none()
    page = Paginator(keys, 25).get_page(request.GET.get("page"))
    return render(request, "schemes/customer_applications.html", {"applications": get_owner_application_items(page.object_list), "page_obj": page, "enrolment_requests_enabled": settings.CUSTOMER_ENROLMENT_REQUESTS_ENABLED})


@login_required
@require_GET
@never_cache
def customer_documents(request):
    from .selectors import get_customer_document_payments
    plans = Paginator(get_customer_scheme_summary(request.user), 12).get_page(request.GET.get("plan_page"))
    receipts = Paginator(get_customer_document_payments(request.user), 25).get_page(request.GET.get("page"))
    return render(request, "schemes/customer_documents.html", {"plans_page": plans, "page_obj": receipts, "receipts": receipts.object_list})


@login_required
@never_cache
def my_scheme_detail(request, scheme_number):
    from .selectors import get_customer_payment_availability, get_customer_plan_next_action

    account = get_customer_scheme_account(request.user, scheme_number)
    if account is None:
        raise Http404
    current_scheme_rate = (
        get_current_scheme_rate(account.metal_grade)
        if account.metal_grade_id
        else None
    )
    payment_availability = get_customer_payment_availability(account)
    payments_page = Paginator(get_contribution_history(account), 25).get_page(request.GET.get("page"))
    redemptions_page = Paginator(get_redemption_history(account), 25).get_page(request.GET.get("redemption_page"))
    return render(
        request,
        "schemes/my_scheme_detail.html",
        {
            "scheme_account": account,
            "cash_balance": get_cash_balance(account),
            "cash_bonus": get_cash_bonus_summary(account),
            "metal_balance": get_metal_balance(account),
            "contributions": payments_page.object_list,
            "page_obj": payments_page,
            "redemptions_page": redemptions_page,
            "redemptions": redemptions_page.object_list,
            "mock_payment_enabled": mock_payment_is_enabled(),
            "payment_gateway_enabled": payment_gateway_is_configured(),
            "razorpay_mode": (
                get_payment_gateway().mode if razorpay_payment_is_enabled() else ""
            ),
            "current_scheme_rate": current_scheme_rate,
            "cash_scheme_activity_enabled": cash_scheme_activity_is_enabled(),
            "payment_availability": payment_availability,
            "next_action": get_customer_plan_next_action(account, payment_availability),
        },
    )


@login_required
def pay_contribution(request, scheme_number):
    if not payment_gateway_is_configured():
        raise Http404
    account = get_customer_scheme_account(request.user, scheme_number)
    if account is None:
        raise Http404
    if (
        account.savings_mode == SchemeAccount.SavingsMode.CASH
        and not cash_scheme_activity_is_enabled()
    ):
        return render(
            request,
            "schemes/contribution_form.html",
            {
                "scheme_account": account,
                "cash_activity_unavailable": True,
            },
            status=403,
        )
    current_scheme_rate = (
        get_current_scheme_rate(account.metal_grade)
        if account.savings_mode
        in {SchemeAccount.SavingsMode.GOLD, SchemeAccount.SavingsMode.SILVER}
        else None
    )

    response_status = 200
    from accounts.application_selectors import first_payment_preference
    preference = first_payment_preference(account, request.user)
    initial = {"amount": preference} if preference is not None else {}
    form = ContributionForm(request.POST or None, scheme_account=account, initial=initial)
    payment_availability = (
        get_payment_availability(metal_grade=account.metal_grade)
        if account.savings_mode
        in {SchemeAccount.SavingsMode.GOLD, SchemeAccount.SavingsMode.SILVER}
        else None
    )
    if payment_availability is not None and not payment_availability.allowed:
        return render(
            request,
            "schemes/contribution_form.html",
            {
                "scheme_account": account,
                "form": form,
                "current_scheme_rate": current_scheme_rate,
                "payment_unavailable": payment_availability,
            },
            status=503,
        )
    if current_scheme_rate is None and account.savings_mode != SchemeAccount.SavingsMode.CASH:
        return render(
            request,
            "schemes/contribution_form.html",
            {
                "scheme_account": account,
                "form": form,
                "mock_payment_enabled": mock_payment_is_enabled(),
                "razorpay_mode": (
                    get_payment_gateway().mode if razorpay_payment_is_enabled() else ""
                ),
                "current_scheme_rate": None,
                "rate_unavailable": True,
            },
            status=503,
        )
    if request.method == "POST" and form.is_valid():
        try:
            if mock_payment_is_enabled():
                contribution = process_mock_contribution(
                    scheme_account=account,
                    amount=form.cleaned_data["amount"],
                )
            else:
                contribution = initiate_razorpay_contribution(
                    scheme_account=account,
                    amount=form.cleaned_data["amount"],
                )
        except (ImproperlyConfigured, PaymentGatewayError, ValidationError) as error:
            if isinstance(error, (ImproperlyConfigured, PaymentGatewayError)):
                form.add_error(None, str(error))
            elif hasattr(error, "message_dict") and "amount" in error.message_dict:
                for message in error.message_dict["amount"]:
                    form.add_error("amount", message)
            else:
                for message in error.messages:
                    form.add_error(None, message)
            if isinstance(error, PaymentGatewayError):
                response_status = error.status_code
            elif isinstance(error, ImproperlyConfigured):
                response_status = 503
            else:
                response_status = 400
        else:
            if razorpay_payment_is_enabled():
                return redirect("schemes:razorpay_checkout", contribution_id=contribution.pk)
            if contribution.status == Contribution.Status.PAID:
                if contribution.scheme_account.savings_mode == SchemeAccount.SavingsMode.CASH:
                    message = f"Mock payment successful. ₹{contribution.amount} was added."
                else:
                    allocation = contribution.metal_allocation
                    message = (
                        f"Mock payment successful. {allocation.quantity:.3f} g "
                        f"{allocation.metal_grade.display_name} was allocated."
                    )
                messages.success(request, message)
            elif contribution.status == Contribution.Status.PAID_UNALLOCATED:
                messages.warning(
                    request,
                    "Mock payment was verified, but the metal allocation is pending. "
                    "The store owner has been notified and can retry it safely.",
                )
            else:
                messages.error(request, "The mock payment failed. No balance was added.")
            return redirect("schemes:my_scheme_detail", scheme_number=account.scheme_number)
    return render(
        request,
        "schemes/contribution_form.html",
        {
            "scheme_account": account,
            "form": form,
            "mock_payment_enabled": mock_payment_is_enabled(),
            "razorpay_mode": (
                get_payment_gateway().mode if razorpay_payment_is_enabled() else ""
            ),
            "current_scheme_rate": current_scheme_rate,
        },
        status=response_status,
    )


@login_required
def razorpay_checkout(request, contribution_id):
    if not razorpay_payment_is_enabled():
        raise Http404
    gateway = get_payment_gateway()
    contribution = get_object_or_404(
        Contribution.objects.select_related(
            "scheme_account",
            "scheme_account__customer",
            "scheme_account__customer__user",
        ),
        pk=contribution_id,
        payment_gateway="razorpay",
        scheme_account__customer__user=request.user,
    )
    if not contribution.gateway_order_id:
        raise Http404
    from .closure_selectors import accepted_closure
    if accepted_closure(contribution.scheme_account):
        messages.warning(request, "Closure has been accepted. Checkout cannot resume; contact the showroom to reconcile any existing payment.")
        return redirect("schemes:my_scheme_detail", scheme_number=contribution.scheme_account.scheme_number)
    if contribution.gateway_mode != gateway.mode:
        messages.warning(
            request,
            "This pending payment belongs to a different Razorpay mode and cannot "
            "be resumed. Please contact the showroom.",
        )
        return redirect(
            "schemes:my_scheme_detail",
            scheme_number=contribution.scheme_account.scheme_number,
        )
    if contribution.status in {
        Contribution.Status.PAID,
        Contribution.Status.PAID_UNALLOCATED,
    }:
        messages.info(request, "This Razorpay payment has already been confirmed.")
        return redirect(
            "schemes:my_scheme_detail",
            scheme_number=contribution.scheme_account.scheme_number,
        )
    if contribution.status == Contribution.Status.FAILED:
        messages.error(request, "This payment attempt is no longer active.")
        return redirect(
            "schemes:my_scheme_detail",
            scheme_number=contribution.scheme_account.scheme_number,
        )
    if contribution.status != Contribution.Status.PENDING:
        messages.error(request, "This payment attempt is no longer active.")
        return redirect(
            "schemes:my_scheme_detail",
            scheme_number=contribution.scheme_account.scheme_number,
        )
    if contribution.razorpay_checkout_expired:
        messages.warning(
            request,
            "This Checkout window has expired. Payment status must be checked. The "
            "showroom must reconcile the provider order before another attempt.",
        )
        return redirect(
            "schemes:my_scheme_detail",
            scheme_number=contribution.scheme_account.scheme_number,
        )
    from .instalments import has_monthly_instalments
    from .instalment_selectors import current_instalment_period
    if has_monthly_instalments(contribution.scheme_account):
        try:
            current_instalment_period(contribution.scheme_account, exclude_contribution_id=contribution.pk)
        except ValidationError:
            messages.warning(request, "This monthly payment requires showroom reconciliation and cannot be resumed.")
            return redirect("schemes:my_scheme_detail", scheme_number=contribution.scheme_account.scheme_number)
    availability = get_payment_availability(
        metal_grade=contribution.scheme_account.metal_grade
    )
    if not availability.allowed:
        messages.warning(request, availability.message)
        return redirect(
            "schemes:my_scheme_detail",
            scheme_number=contribution.scheme_account.scheme_number,
        )
    checkout_timeout_seconds = max(
        1,
        math.ceil((contribution.checkout_expires_at - timezone.now()).total_seconds()),
    )
    return render(
        request,
        "schemes/razorpay_checkout.html",
        {
            "contribution": contribution,
            "razorpay_key_id": gateway.key_id,
            "razorpay_mode": gateway.mode,
            "amount_subunits": int(contribution.amount * 100),
            "checkout_timeout_seconds": checkout_timeout_seconds,
            "checkout_expires_at": contribution.checkout_expires_at,
        },
    )


@login_required
@require_POST
def razorpay_confirm(request, contribution_id):
    if not razorpay_payment_is_enabled():
        raise Http404
    contribution = get_object_or_404(
        Contribution.objects.select_related("scheme_account"),
        pk=contribution_id,
        payment_gateway="razorpay",
        scheme_account__customer__user=request.user,
    )
    callback_order_id = request.POST.get("razorpay_order_id", "")
    payment_id = request.POST.get("razorpay_payment_id", "")
    signature = request.POST.get("razorpay_signature", "")
    if not all((callback_order_id, payment_id, signature)):
        return JsonResponse(
            {
                "success": False,
                "detail": "Payment verification fields are missing.",
            },
            status=400,
        )
    try:
        contribution = confirm_razorpay_contribution(
            contribution_id=contribution.pk,
            callback_order_id=callback_order_id,
            payment_id=payment_id,
            signature=signature,
        )
    except (ImproperlyConfigured, PaymentGatewayError, ValidationError) as error:
        if isinstance(error, PaymentGatewayAuthenticationError):
            status_code = 401
        elif isinstance(error, PaymentGatewayError):
            status_code = error.status_code
        elif isinstance(error, ImproperlyConfigured):
            status_code = 503
        else:
            status_code = 400
        return JsonResponse(
            {
                "success": False,
                "detail": f"Payment verification failed: {error}",
            },
            status=status_code,
        )
    else:
        if contribution.status == Contribution.Status.PAID_UNALLOCATED:
            messages.warning(
                request,
                "Payment verified, but metal allocation is pending owner retry.",
            )
        else:
            messages.success(request, "Razorpay payment verified successfully.")
    return JsonResponse(
        {
            "success": True,
            "redirect_url": reverse(
                "schemes:my_scheme_detail",
                args=[contribution.scheme_account.scheme_number],
            ),
        }
    )


@fragment_session
@never_cache
@login_required
@require_GET
def payment_status(request, contribution_id):
    """A customer-scoped, server-rendered outcome; never verify or retry on GET."""
    contribution = get_object_or_404(
        Contribution.objects.select_related("scheme_account__customer", "scheme_account__metal_grade"),
        pk=contribution_id,
        payment_gateway="razorpay",
        scheme_account__customer__user=request.user,
    )
    return render(request, private_read_template(request, "schemes/payment_status.html", "schemes/includes/payment_status_panel.html"), {"contribution": contribution, "checked_at": timezone.now()})


@csrf_exempt
@require_POST
def razorpay_webhook(request):
    if not razorpay_payment_is_enabled():
        return JsonResponse({"detail": "Razorpay is not configured."}, status=503)
    body = request.body
    if len(body) > 256 * 1024:
        return JsonResponse({"detail": "Webhook payload is too large."}, status=413)
    gateway = get_payment_gateway()
    signature = request.headers.get("X-Razorpay-Signature", "")
    if not gateway.verify_webhook(body=body, signature=signature):
        return JsonResponse({"detail": "Invalid webhook signature."}, status=400)
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JsonResponse({"detail": "Invalid JSON payload."}, status=400)
    event_id = request.headers.get("X-Razorpay-Event-Id") or (
        f"sha256:{hashlib.sha256(body).hexdigest()}"
    )
    try:
        event = process_razorpay_webhook(
            gateway_mode=gateway.mode,
            event_id=event_id[:120],
            body=body,
            payload=payload,
        )
    except WebhookTransientProcessingError:
        logger.error(
            "Transient Razorpay webhook processing failure for event_id=%s mode=%s.",
            event_id,
            gateway.mode,
        )
        return JsonResponse(
            {"detail": "Webhook processing is temporarily unavailable."},
            status=503,
        )
    except ValidationError as error:
        return JsonResponse({"detail": str(error)}, status=400)
    return JsonResponse({"status": event.status.lower()})


def _owner_payment_scope(request):
    customer = _owner_customer_filter(request)
    form = OwnerPaymentFilterForm(request.GET)
    rows = get_filtered_owner_payments(customer=customer)
    contribution_id = request.GET.get("contribution", "")
    if contribution_id:
        if not contribution_id.isascii() or not contribution_id.isdecimal() or len(contribution_id) > 10:
            raise Http404
        contribution = get_object_or_404(rows, pk=int(contribution_id))
        customer = contribution.scheme_account.customer
    rows = get_filtered_owner_payments(customer=customer, contribution_id=int(contribution_id) if contribution_id else None, filters=form.cleaned_data if form.is_valid() else None)
    return customer, rows if form.is_valid() else rows.none(), form


@owner_required
@require_GET
@never_cache
def owner_payment_detail(request, contribution_id):
    contribution = get_object_or_404(get_owner_contributions(), pk=contribution_id)
    return render(request, "schemes/owner_payment_detail.html", {"contribution": contribution, "customer": contribution.scheme_account.customer})


@fragment_session
@owner_required
@require_GET
@never_cache
def contribution_list(request):
    customer, contributions, filter_form = _owner_payment_scope(request)
    page = Paginator(contributions, 25).get_page(request.GET.get("page"))
    query = request.GET.copy()
    query.pop("page", None)
    scoped = bool(customer or any(request.GET.get(key) for key in ("q", "status", "method", "mode", "start", "end", "contribution")))
    return render(
        request,
        private_read_template(request, "schemes/contribution_list.html", "schemes/includes/payment_workspace.html"),
        {
            "contributions": page.object_list,
            "page_obj": page,
            "customer": customer,
            "daily_summary": None if scoped else get_owner_contribution_daily_summary(),
            "scope_summary": get_payment_scope_summary(contributions),
            "filter_form": filter_form, "export_query": query.urlencode(),
            "in_store_cash_enabled": in_store_cash_contributions_are_enabled(),
        },
    )


@owner_required
@never_cache
def in_store_cash_contribution(request, scheme_number):
    if not in_store_cash_contributions_are_enabled():
        raise Http404
    account = get_object_or_404(
        SchemeAccount.objects.select_related("customer", "plan", "metal_grade"),
        scheme_number=scheme_number,
        savings_mode__in=[
            SchemeAccount.SavingsMode.GOLD,
            SchemeAccount.SavingsMode.SILVER,
        ],
    )
    form = InStoreCashContributionForm(
        request.POST or None,
        scheme_account=account,
        initial={"idempotency_key": uuid.uuid4()},
    )
    preview = None
    cash_blocker = get_cash_entry_blocker(account)
    if request.method == "POST" and form.is_valid():
        action = request.POST.get("action")
        token = str(form.cleaned_data["idempotency_key"])
        session_key = f"in_store_cash_preview:{token}"
        if action == "preview":
            try:
                preview = preview_in_store_cash_contribution(
                    scheme_account=account,
                    amount=form.cleaned_data["amount"],
                )
            except ValidationError as error:
                form.add_error(None, " ".join(error.messages))
            else:
                request.session[session_key] = {
                    "scheme_account_id": account.pk,
                    "amount": str(form.cleaned_data["amount"]),
                    "scheme_rate_id": preview.scheme_rate.pk,
                    "paper_receipt_number": form.cleaned_data[
                        "paper_receipt_number"
                    ],
                    "notes": form.cleaned_data["notes"].strip(),
                    "audit_reason": form.cleaned_data["audit_reason"].strip(),
                }
        elif action == "confirm":
            snapshot = request.session.get(session_key)
            current_values = {
                "scheme_account_id": account.pk,
                "amount": str(form.cleaned_data["amount"]),
                "scheme_rate_id": form.cleaned_data["expected_scheme_rate_id"],
                "paper_receipt_number": form.cleaned_data[
                    "paper_receipt_number"
                ],
                "notes": form.cleaned_data["notes"].strip(),
                "audit_reason": form.cleaned_data["audit_reason"].strip(),
            }
            if not form.cleaned_data["confirm_cash_received"]:
                form.add_error(
                    "confirm_cash_received",
                    "Confirm that the showroom physically received the cash.",
                )
            elif snapshot is None or snapshot != current_values:
                form.add_error(
                    None,
                    "The preview is missing or the details changed. Review the "
                    "cash receipt again before confirming.",
                )
            else:
                try:
                    contribution = record_in_store_cash_contribution(
                        scheme_account=account,
                        amount=form.cleaned_data["amount"],
                        expected_scheme_rate_id=snapshot["scheme_rate_id"],
                        received_by=request.user,
                        idempotency_key=form.cleaned_data["idempotency_key"],
                        paper_receipt_number=form.cleaned_data[
                            "paper_receipt_number"
                        ],
                        notes=form.cleaned_data["notes"],
                        audit_reason=form.cleaned_data["audit_reason"],
                    )
                except ValidationError as error:
                    request.session.pop(session_key, None)
                    form.add_error(None, " ".join(error.messages))
                else:
                    request.session.pop(session_key, None)
                    if contribution.status == Contribution.Status.PAID:
                        messages.success(
                            request,
                            "In-store cash was recorded and metal was allocated.",
                        )
                    else:
                        messages.warning(
                            request,
                            "Cash receipt was recorded, but metal allocation requires "
                            "owner review.",
                        )
                    return redirect(
                        "schemes:contribution_receipt",
                        contribution_id=contribution.pk,
                    )
        else:
            form.add_error(None, "Choose Review receipt before confirmation.")
    return render(
        request,
        "schemes/in_store_cash_contribution.html",
        {
            "scheme_account": account,
            "form": form,
            "preview": preview,
            "cash_blocker": cash_blocker,
        },
    )


@owner_required
def in_store_cash_contribution_reverse(request, contribution_id):
    contribution = get_object_or_404(
        get_owner_contributions(),
        pk=contribution_id,
        payment_gateway="in_store_cash",
        status__in=[
            Contribution.Status.PAID,
            Contribution.Status.PAID_UNALLOCATED,
        ],
    )
    form = InStoreCashContributionReversalForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            reverse_in_store_cash_contribution(
                contribution=contribution,
                processed_by=request.user,
                reason_code=form.cleaned_data["reason_code"],
                reason=form.cleaned_data["reason"],
            )
        except ValidationError as error:
            form.add_error(None, " ".join(error.messages))
        else:
            messages.success(
                request,
                "The contribution was reversed without deleting its receipt or "
                "financial history.",
            )
            return redirect(
                "schemes:contribution_receipt",
                contribution_id=contribution.pk,
            )
    return render(
        request,
        "schemes/in_store_cash_contribution_reverse.html",
        {"contribution": contribution, "form": form},
    )


@owner_required
@require_POST
def retry_contribution_allocation(request, contribution_id):
    contribution = get_object_or_404(
        Contribution.objects.select_related("scheme_account", "scheme_account__customer"),
        pk=contribution_id,
        status=Contribution.Status.PAID_UNALLOCATED,
        scheme_account__savings_mode__in=[
            SchemeAccount.SavingsMode.GOLD,
            SchemeAccount.SavingsMode.SILVER,
        ],
    )
    review_url = reverse("schemes:contribution_list") + f"?contribution={contribution.pk}"
    form = AuditReasonForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Enter a reason for retrying the allocation.")
        return redirect(review_url)
    try:
        allocation = retry_metal_allocation(
            contribution=contribution,
            performed_by=request.user,
            reason=form.cleaned_data["reason"],
        )
    except (ImproperlyConfigured, ValidationError) as error:
        messages.error(request, f"Allocation retry failed: {error}")
    else:
        messages.success(
            request,
            f"Allocated {allocation.quantity:.6f} g "
            f"{allocation.metal_grade.display_name} "
            f"for {contribution.scheme_account.customer.full_name}.",
        )
    return redirect(review_url)
