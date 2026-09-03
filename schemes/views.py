import csv
import hashlib
import json
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.http import Http404, HttpResponse, JsonResponse
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt

from accounts.models import CustomUser
from accounts.services import issue_customer_invitation, send_customer_invitation

from .forms import (
    AuditReasonForm,
    ContributionForm,
    CustomerCreateForm,
    EnrolmentForm,
    PaymentOperationsForm,
    RedemptionForm,
    RedemptionReversalForm,
    SchemeRatePublishForm,
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
from .selectors import (
    get_cash_balance,
    get_cash_bonus_summary,
    get_contribution_history,
    get_contribution_receipt_summary,
    get_customer_scheme_account,
    get_customer_scheme_summary,
    get_latest_customer_invitation,
    get_current_scheme_rate,
    get_current_scheme_rates,
    get_metal_balance,
    get_owner_activity_summary,
    get_owner_audit_events,
    get_owner_contributions,
    get_owner_customers,
    get_owner_liability_summary,
    get_owner_exception_queue,
    get_pending_payment_exposure,
    get_owner_redemptions,
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
    enroll_customer,
    confirm_razorpay_contribution,
    initiate_razorpay_contribution,
    process_razorpay_webhook,
    process_mock_contribution,
    publish_scheme_rate,
    record_scheme_plan_change,
    reverse_redemption,
    retry_metal_allocation,
    reconcile_razorpay_webhook,
    update_payment_operations_control,
    WebhookTransientProcessingError,
)


logger = logging.getLogger(__name__)


@login_required
def post_login(request):
    if request.user.is_superuser or request.user.role == CustomUser.Role.OWNER:
        return redirect("schemes:owner_dashboard")
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
    exceptions = get_owner_exception_queue()
    payment_availability = {
        grade.code: {
            "grade": grade,
            "availability": get_payment_availability(metal_grade=grade),
        }
        for grade in MetalGrade.objects.all()
    }
    context = {
        "activity": activity,
        "exception_count": len(exceptions),
        "eligibility": get_redemption_eligibility_summary(),
        "liabilities": get_owner_liability_summary(),
        "payment_availability": payment_availability,
        "payments_restricted": any(
            not item["availability"].allowed
            for item in payment_availability.values()
        ),
    }
    return render(request, "schemes/owner_dashboard.html", context)


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
def exception_queue(request):
    return render(
        request,
        "schemes/exception_queue.html",
        {"exceptions": get_owner_exception_queue()},
    )


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


@login_required
def contribution_receipt(request, contribution_id):
    contribution = get_object_or_404(
        Contribution.objects.select_related(
            "scheme_account",
            "scheme_account__customer",
            "scheme_account__customer__user",
            "metal_allocation",
            "metal_allocation__scheme_rate",
        ),
        pk=contribution_id,
        status__in=[
            Contribution.Status.PAID,
            Contribution.Status.PAID_UNALLOCATED,
        ],
    )
    if not _can_view_scheme_account(request.user, contribution.scheme_account):
        raise Http404
    return render(
        request,
        "schemes/contribution_receipt.html",
        {"receipt": get_contribution_receipt_summary(contribution)},
    )


@login_required
def scheme_statement(request, scheme_number):
    account = get_object_or_404(
        SchemeAccount.objects.select_related("customer", "customer__user", "plan"),
        scheme_number=scheme_number,
    )
    if not _can_view_scheme_account(request.user, account):
        raise Http404
    return render(
        request,
        "schemes/scheme_statement.html",
        {"statement": get_scheme_statement(account)},
    )


@owner_required
def contribution_export(request):
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
        ]
    )
    contributions = get_owner_contributions().filter(
        status__in=[
            Contribution.Status.PAID,
            Contribution.Status.PAID_UNALLOCATED,
        ]
    )
    for contribution in contributions:
        receipt = get_contribution_receipt_summary(contribution)
        allocation = receipt.allocation
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


@owner_required
def customer_list(request):
    return render(
        request,
        "schemes/customer_list.html",
        {"customers": get_owner_customers()},
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


@owner_required
def customer_detail(request, customer_id):
    customer = get_object_or_404(
        get_owner_customers().prefetch_related(
            "scheme_accounts__plan", "scheme_accounts__contributions"
        ),
        pk=customer_id,
    )
    return render(
        request,
        "schemes/customer_detail.html",
        {
            "customer": customer,
            "latest_invitation": get_latest_customer_invitation(customer),
            "cash_scheme_activity_enabled": cash_scheme_activity_is_enabled(),
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


@owner_required
def plan_list(request):
    return render(request, "schemes/plan_list.html", {"plans": SchemePlan.objects.all()})


@owner_required
def plan_add(request):
    form = SchemePlanForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            plan = form.save()
            form.save_offerings()
        messages.success(request, f"Plan {plan.name} created.")
        return redirect("schemes:plan_list")
    return render(request, "schemes/plan_form.html", {"form": form})


@owner_required
def plan_edit(request, plan_id):
    plan = get_object_or_404(SchemePlan, pk=plan_id)
    form = SchemePlanChangeForm(request.POST or None, instance=plan)
    if request.method == "POST" and form.is_valid():
        tracked_fields = SchemePlanChangeForm.Meta.fields
        stored_plan = SchemePlan.objects.get(pk=plan.pk)
        before = {field: getattr(stored_plan, field) for field in tracked_fields}
        before["metal_grades"] = tuple(
            stored_plan.metal_offerings.filter(active=True)
            .order_by("metal_grade__code")
            .values_list("metal_grade__code", flat=True)
        )
        with transaction.atomic():
            plan = form.save()
            form.save_offerings()
            event = record_scheme_plan_change(
                plan=plan,
                actor=request.user,
                reason=form.cleaned_data["audit_reason"],
                before=before,
                after_overrides={
                    "metal_grades": tuple(
                        plan.metal_offerings.filter(active=True)
                        .order_by("metal_grade__code")
                        .values_list("metal_grade__code", flat=True)
                    )
                },
            )
        if event is None:
            messages.info(request, "No plan values changed.")
        else:
            messages.success(request, f"Plan {plan.name} updated and audited.")
        return redirect("schemes:plan_list")
    return render(
        request,
        "schemes/plan_form.html",
        {"form": form, "plan": plan},
    )


@login_required
def my_schemes(request):
    accounts = list(get_customer_scheme_summary(request.user))
    for account in accounts:
        if account.savings_mode == SchemeAccount.SavingsMode.CASH:
            account.cash_bonus = get_cash_bonus_summary(account)
        else:
            account.current_scheme_rate = get_current_scheme_rate(account.metal_grade)
    return render(
        request,
        "schemes/my_schemes.html",
        {
            "scheme_accounts": accounts,
            "mock_payment_enabled": mock_payment_is_enabled(),
            "payment_gateway_enabled": payment_gateway_is_configured(),
            "cash_scheme_activity_enabled": cash_scheme_activity_is_enabled(),
        },
    )


@login_required
def my_scheme_detail(request, scheme_number):
    account = get_customer_scheme_account(request.user, scheme_number)
    if account is None:
        raise Http404
    current_scheme_rate = (
        get_current_scheme_rate(account.metal_grade)
        if account.savings_mode != SchemeAccount.SavingsMode.CASH
        else None
    )
    payment_availability = (
        get_payment_availability(metal_grade=account.metal_grade)
        if account.savings_mode
        in {SchemeAccount.SavingsMode.GOLD, SchemeAccount.SavingsMode.SILVER}
        else None
    )
    return render(
        request,
        "schemes/my_scheme_detail.html",
        {
            "scheme_account": account,
            "cash_balance": get_cash_balance(account),
            "cash_bonus": get_cash_bonus_summary(account),
            "metal_balance": get_metal_balance(account),
            "contributions": get_contribution_history(account),
            "redemptions": get_redemption_history(account),
            "mock_payment_enabled": mock_payment_is_enabled(),
            "payment_gateway_enabled": payment_gateway_is_configured(),
            "razorpay_mode": (
                get_payment_gateway().mode if razorpay_payment_is_enabled() else ""
            ),
            "current_scheme_rate": current_scheme_rate,
            "cash_scheme_activity_enabled": cash_scheme_activity_is_enabled(),
            "payment_availability": payment_availability,
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
    form = ContributionForm(request.POST or None, scheme_account=account)
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
    availability = get_payment_availability(
        metal_grade=contribution.scheme_account.metal_grade
    )
    if not availability.allowed:
        messages.warning(request, availability.message)
        return redirect(
            "schemes:my_scheme_detail",
            scheme_number=contribution.scheme_account.scheme_number,
        )
    return render(
        request,
        "schemes/razorpay_checkout.html",
        {
            "contribution": contribution,
            "razorpay_key_id": gateway.key_id,
            "razorpay_mode": gateway.mode,
            "amount_subunits": int(contribution.amount * 100),
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


@owner_required
def contribution_list(request):
    return render(
        request,
        "schemes/contribution_list.html",
        {"contributions": get_owner_contributions()},
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
    form = AuditReasonForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Enter a reason for retrying the allocation.")
        return redirect("schemes:contribution_list")
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
    return redirect("schemes:contribution_list")
