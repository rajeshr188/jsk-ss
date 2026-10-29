from django.contrib import messages
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST, require_http_methods
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.crypto import constant_time_compare

from schemes.permissions import owner_required
from schemes.navigation import review_destination
from schemes.selectors import get_public_scheme_plans
from .application_forms import PlanApplicationContactForm, PlanApplicationCompletionForm, PlanApplicationApprovalForm
from .application_selectors import get_plan_application, application_progress, application_timeline
from .applications import (
    application_enabled, application_terms_current, complete_plan_application,
    offer_form_digest, progress_token_available, progress_identity_available, reissue_progress_access,
    submit_plan_application, approve_plan_application,
)
from .forms import CustomerRegistrationRejectionForm
from .models import CustomerRegistration


def grant_application_access(request, application):
    request.session.cycle_key()
    request.session["plan_application_access"] = {
        "registration": str(application.registration_id), "digest": application.progress_token_digest,
    }


def _errors(form, error):
    for message in error.messages:
        form.add_error(None, message)


@never_cache
@require_http_methods(["GET", "POST"])
def application_start(request, plan_id):
    if not application_enabled():
        raise Http404
    plan = get_object_or_404(get_public_scheme_plans(), pk=plan_id)
    if request.user.is_authenticated:
        if request.user.is_active and request.user.role == "CUSTOMER":
            return redirect("schemes:scheme_enrolment_request_create", plan_id=plan.pk)
        raise Http404
    form = PlanApplicationContactForm(request.POST or None, plan=plan, initial={"offer_digest": offer_form_digest(plan)})
    if request.method == "POST" and form.is_valid():
        if form.cleaned_data["website"]:
            return redirect("customer_registration_submitted")
        try:
            submit_plan_application(
                plan=plan, metal_grade=form.cleaned_data["metal_grade"],
                amount=form.cleaned_data["requested_contribution_amount"], months=form.cleaned_data["requested_months"],
                message=form.cleaned_data["customer_message"], full_name=form.cleaned_data["full_name"],
                email=form.cleaned_data["email"], mobile_number=form.cleaned_data["mobile_number"],
                offer_digest=form.cleaned_data["offer_digest"],
                source_ip=_application_source_ip(request),
                base_url=request.build_absolute_uri("/"),
            )
        except ValidationError as error:
            _errors(form, error)
        else:
            return redirect("customer_registration_submitted")
    return render(request, "account/plan_application_start.html", {"form": form, "selected_plan": plan})


@never_cache
@require_http_methods(["GET", "POST"])
def application_access(request, application_id, token):
    application = get_plan_application(application_id)
    if application is None or not progress_token_available(application, token):
        return render(request, "account/plan_application_access_invalid.html")
    if request.method == "POST":
        grant_application_access(request, application)
        return redirect("plan_application_progress", application_id=application_id)
    return render(request, "account/plan_application_access.html")


@never_cache
@require_http_methods(["GET", "POST"])
def application_progress_view(request, application_id):
    application = get_plan_application(application_id)
    grant = request.session.get("plan_application_access", {})
    if (application is None or grant.get("registration") != str(application_id)
            or application.expires_at <= timezone.now() or not application.progress_token_digest or not progress_identity_available(application)
            or not constant_time_compare(application.progress_token_digest, grant.get("digest", ""))):
        return render(request, "account/plan_application_access_invalid.html")
    stage, next_action = application_progress(application)
    editable = application_enabled() and application.registration.status == CustomerRegistration.Status.AWAITING_OWNER_APPROVAL
    if not application_enabled() and application.registration.status == CustomerRegistration.Status.AWAITING_OWNER_APPROVAL:
        stage, next_action = "Online updates unavailable", "Your saved application is retained. Contact the showroom to continue."
    form = None
    if editable:
        initial = {
            "address": application.registration.address, "metal_grade": application.metal_grade_id,
            "requested_contribution_amount": (application.plan.fixed_contribution_amount
                if application.plan.amount_rule == "FIXED" else application.requested_amount),
            "requested_months": application.requested_months, "customer_message": application.customer_message,
            "start_date": application.start_date or timezone.localdate(), "offer_digest": offer_form_digest(application.plan),
        }
        if application.plan.configuration_id and application.plan.configuration.policy_schema_version == 2:
            configuration = application.plan.configuration
            initial["requested_months"] = configuration.duration_months
            initial["requested_contribution_amount"] = application.requested_amount
            if configuration.amount_policy == "PLAN_FIXED":
                initial["requested_contribution_amount"] = configuration.fixed_amount
        form = PlanApplicationCompletionForm(request.POST or None, plan=application.plan, initial=initial)
        if request.method == "POST" and form.is_valid():
            try:
                complete_plan_application(
                    registration_id=application_id, access_digest=grant["digest"],
                    address=form.cleaned_data["address"], metal_grade=form.cleaned_data["metal_grade"],
                    amount=form.cleaned_data["requested_contribution_amount"], months=form.cleaned_data["requested_months"],
                    message=form.cleaned_data["customer_message"], start_date=form.cleaned_data["start_date"],
                    offer_digest=form.cleaned_data["offer_digest"],
                )
            except ValidationError as error:
                _errors(form, error)
            else:
                messages.success(request, "Your details and plan confirmation are saved for showroom review.")
                return redirect("plan_application_progress", application_id=application_id)
    elif request.method == "POST":
        raise Http404
    timeline = application_timeline(application)
    if application.scheme_account_id and application.scheme_account.customer.user.has_usable_password():
        from schemes.selectors import get_customer_plan_next_action
        action = get_customer_plan_next_action(application.scheme_account)
        stage = action["stage"]
        next_action = action["message"] + " Sign in to continue with your approved plan."
    continuation_url = None
    if application.scheme_account_id:
        from urllib.parse import urlencode
        continuation_url = reverse("account_login") + "?" + urlencode({
            "next": reverse("schemes:my_scheme_detail", args=[application.scheme_account.scheme_number]),
        })
    return render(request, "account/plan_application_progress.html", {
        "journey": application, "stage": stage, "next_action": next_action, "form": form,
        "needs_confirmation": editable and not application_terms_current(application),
        "continuation_url": continuation_url, "timeline": timeline,
    })


def owner_application_context(application, approval_form=None):
    terms_current = application_terms_current(application)
    return {
        "application": application.registration, "journey": application,
        "approval_form": approval_form or PlanApplicationApprovalForm(),
        "rejection_form": CustomerRegistrationRejectionForm(),
        "offer_is_current": terms_current,
        "can_approve": (application.registration.status == CustomerRegistration.Status.AWAITING_OWNER_APPROVAL
                        and application.expires_at > timezone.now() and terms_current),
        "stage": application_progress(application)[0],
    }


@owner_required
@require_POST
def application_approve(request, application_id):
    application = get_plan_application(application_id)
    if application is None:
        raise Http404
    form = PlanApplicationApprovalForm(request.POST)
    if form.is_valid():
        try:
            account, created = approve_plan_application(
                registration_id=application_id, actor=request.user,
                mobile_verified=form.cleaned_data["mobile_verified"], terms_reviewed=form.cleaned_data["terms_reviewed"],
                reason=form.cleaned_data["reason"], base_url=request.build_absolute_uri("/"),
            )
        except ValidationError as error:
            _errors(form, error)
        else:
            messages.success(request, "Identity and plan approved." if created else "This application was already approved; the same agreement is retained.")
            return redirect(review_destination(request, "customer_registration_detail", application_id=application_id))
    return render(request, "account/plan_application_review.html", owner_application_context(application, form), status=400)


@owner_required
@require_POST
def application_resend_progress(request, application_id):
    if get_plan_application(application_id) is None:
        raise Http404
    try:
        reissue_progress_access(registration_id=application_id, actor=request.user, base_url=request.build_absolute_uri("/"))
    except (ValidationError, CustomerRegistration.DoesNotExist) as error:
        messages.error(request, "Unable to replace progress access. Review verification and application expiry.")
    else:
        messages.info(request, "Replacement progress access issued. Check its delivery status below; earlier access is invalidated.")
    return redirect(review_destination(request, "customer_registration_detail", application_id=application_id))


def _application_source_ip(request):
    from .views import _source_ip
    return _source_ip(request)
