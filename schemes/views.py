from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.models import CustomUser

from .forms import CustomerCreateForm, EnrolmentForm, SchemePlanForm
from .models import Customer, SchemeAccount, SchemePlan
from .permissions import owner_required
from .selectors import get_customer_scheme_summary, get_owner_customers
from .services import create_customer, enroll_customer


@login_required
def post_login(request):
    if request.user.is_superuser or request.user.role == CustomUser.Role.OWNER:
        return redirect("schemes:owner_dashboard")
    return redirect("schemes:my_schemes")


@owner_required
def owner_dashboard(request):
    context = {
        "customer_count": Customer.objects.count(),
        "active_account_count": SchemeAccount.objects.exclude(
            status=SchemeAccount.Status.REDEEMED
        ).count(),
        "active_plan_count": SchemePlan.objects.filter(active=True).count(),
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
        get_owner_customers().prefetch_related("scheme_accounts__plan"), pk=customer_id
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
    return render(request, "schemes/my_schemes.html", {"scheme_accounts": accounts})

