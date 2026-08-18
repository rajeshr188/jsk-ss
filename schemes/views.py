import hashlib
import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt

from accounts.models import CustomUser

from .forms import ContributionForm, CustomerCreateForm, EnrolmentForm, SchemePlanForm
from .models import Contribution, Customer, SchemeAccount, SchemePlan
from .payments import (
    PaymentGatewayError,
    get_payment_gateway,
    mock_payment_is_enabled,
    payment_gateway_is_configured,
    razorpay_payment_is_enabled,
)
from .permissions import owner_required
from .rates import MetalRateProviderError, metal_rate_provider_is_configured
from .selectors import (
    get_cash_balance,
    get_contribution_history,
    get_customer_scheme_account,
    get_customer_scheme_summary,
    get_metal_balance,
    get_owner_activity_summary,
    get_owner_contributions,
    get_owner_customers,
    get_owner_liability_summary,
)
from .services import (
    create_customer,
    enroll_customer,
    confirm_razorpay_contribution,
    initiate_razorpay_contribution,
    process_razorpay_webhook,
    process_mock_contribution,
    retry_metal_allocation,
)


@login_required
def post_login(request):
    if request.user.is_superuser or request.user.role == CustomUser.Role.OWNER:
        return redirect("schemes:owner_dashboard")
    return redirect("schemes:my_schemes")


@owner_required
def owner_dashboard(request):
    activity = get_owner_activity_summary()
    context = {
        "activity": activity,
        "liabilities": get_owner_liability_summary(),
    }
    return render(request, "schemes/owner_dashboard.html", context)


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
            customer = create_customer(
                full_name=form.cleaned_data["full_name"],
                email=form.cleaned_data["email"],
                mobile_number=form.cleaned_data["mobile_number"],
                address=form.cleaned_data["address"],
                password=form.cleaned_data["password1"],
            )
        except ValidationError as error:
            for field, field_errors in error.message_dict.items():
                for field_error in field_errors:
                    form.add_error(field if field in form.fields else None, field_error)
        else:
            messages.success(request, f"Customer {customer.full_name} created.")
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
    return render(request, "schemes/customer_detail.html", {"customer": customer})


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
                savings_mode=form.cleaned_data["savings_mode"],
                start_date=form.cleaned_data["start_date"],
                agreed_months=form.cleaned_data["agreed_months"],
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
        plan = form.save()
        messages.success(request, f"Plan {plan.name} created.")
        return redirect("schemes:plan_list")
    return render(request, "schemes/plan_form.html", {"form": form})


@login_required
def my_schemes(request):
    accounts = get_customer_scheme_summary(request.user)
    return render(
        request,
        "schemes/my_schemes.html",
        {
            "scheme_accounts": accounts,
            "mock_payment_enabled": mock_payment_is_enabled(),
            "payment_gateway_enabled": payment_gateway_is_configured(),
            "metal_rate_provider_enabled": metal_rate_provider_is_configured(),
        },
    )


@login_required
def my_scheme_detail(request, scheme_number):
    account = get_customer_scheme_account(request.user, scheme_number)
    if account is None:
        raise Http404
    return render(
        request,
        "schemes/my_scheme_detail.html",
        {
            "scheme_account": account,
            "cash_balance": get_cash_balance(account),
            "metal_balance": get_metal_balance(account),
            "contributions": get_contribution_history(account),
            "mock_payment_enabled": mock_payment_is_enabled(),
            "payment_gateway_enabled": payment_gateway_is_configured(),
            "metal_rate_provider_enabled": metal_rate_provider_is_configured(),
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
        account.savings_mode in {
            SchemeAccount.SavingsMode.GOLD,
            SchemeAccount.SavingsMode.SILVER,
        }
        and not metal_rate_provider_is_configured()
    ):
        raise Http404

    form = ContributionForm(request.POST or None, scheme_account=account)
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
        else:
            if razorpay_payment_is_enabled():
                return redirect("schemes:razorpay_checkout", contribution_id=contribution.pk)
            if contribution.status == Contribution.Status.PAID:
                if contribution.scheme_account.savings_mode == SchemeAccount.SavingsMode.CASH:
                    message = f"Mock payment successful. ₹{contribution.amount} was added."
                else:
                    allocation = contribution.metal_allocation
                    message = (
                        f"Mock payment successful. {allocation.quantity} g "
                        f"{allocation.get_metal_display()} was allocated."
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
        },
    )


@login_required
def razorpay_checkout(request, contribution_id):
    if not razorpay_payment_is_enabled():
        raise Http404
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
    return render(
        request,
        "schemes/razorpay_checkout.html",
        {
            "contribution": contribution,
            "razorpay_key_id": get_payment_gateway().key_id,
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
    try:
        contribution = confirm_razorpay_contribution(
            contribution_id=contribution.pk,
            callback_order_id=request.POST.get("razorpay_order_id", ""),
            payment_id=request.POST.get("razorpay_payment_id", ""),
            signature=request.POST.get("razorpay_signature", ""),
        )
    except (ImproperlyConfigured, PaymentGatewayError, ValidationError) as error:
        messages.error(request, f"Payment verification failed: {error}")
    else:
        if contribution.status == Contribution.Status.PAID_UNALLOCATED:
            messages.warning(
                request,
                "Payment verified, but metal allocation is pending owner retry.",
            )
        else:
            messages.success(request, "Razorpay test payment verified successfully.")
    return redirect(
        "schemes:my_scheme_detail",
        scheme_number=contribution.scheme_account.scheme_number,
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
            event_id=event_id[:120],
            body=body,
            payload=payload,
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
    try:
        allocation = retry_metal_allocation(contribution=contribution)
    except (ImproperlyConfigured, MetalRateProviderError, ValidationError) as error:
        messages.error(request, f"Allocation retry failed: {error}")
    else:
        messages.success(
            request,
            f"Allocated {allocation.quantity} g {allocation.get_metal_display()} "
            f"for {contribution.scheme_account.customer.full_name}.",
        )
    return redirect("schemes:contribution_list")
