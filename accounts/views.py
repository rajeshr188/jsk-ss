from functools import wraps

from django.contrib import messages
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.exceptions import ObjectDoesNotExist
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from .forms import (
    CustomerInvitationPasswordForm,
    CustomerRegistrationApprovalForm,
    CustomerRegistrationForm,
    CustomerRegistrationRejectionForm,
)
from .models import CustomerInvitation, CustomerRegistration
from .services import (
    InvalidCustomerRegistration,
    InvalidCustomerInvitation,
    accept_customer_invitation,
    approve_customer_registration,
    issue_registration_verification,
    invitation_is_available,
    registration_is_verifiable,
    reject_customer_registration,
    send_customer_invitation,
    send_customer_registration_verification,
    submit_customer_registration,
    verify_customer_registration_email,
)


def _invitation_or_none(invitation_id):
    return (
        CustomerInvitation.objects.select_related("user")
        .filter(pk=invitation_id)
        .first()
    )


@never_cache
def customer_invitation_accept(request, invitation_id, token):
    invitation = _invitation_or_none(invitation_id)
    if invitation is None or not invitation_is_available(invitation, token):
        return render(
            request,
            "account/customer_invitation_invalid.html",
            status=200,
        )

    form = CustomerInvitationPasswordForm(invitation.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            accept_customer_invitation(
                invitation_id=invitation.pk,
                raw_token=token,
                new_password=form.cleaned_data["new_password1"],
            )
        except (InvalidCustomerInvitation, ObjectDoesNotExist):
            return render(
                request,
                "account/customer_invitation_invalid.html",
                status=200,
            )
        messages.success(
            request,
            "Your password is set. You can now sign in with your email address.",
        )
        return redirect("account_login")

    return render(
        request,
        "account/customer_invitation_accept.html",
        {"form": form, "invitation": invitation},
    )


def _public_registration_enabled():
    return settings.PUBLIC_CUSTOMER_REGISTRATION_ENABLED


def _source_ip(request):
    if getattr(settings, "SECURE_PROXY_SSL_HEADER", None):
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if forwarded:
            return forwarded.split(",", maxsplit=1)[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def _registration_verification_url(request, application, raw_token):
    return request.build_absolute_uri(
        reverse(
            "customer_registration_verify",
            kwargs={"application_id": application.pk, "token": raw_token},
        )
    )


@never_cache
def customer_registration(request):
    if not _public_registration_enabled():
        raise Http404

    form = CustomerRegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if not form.cleaned_data["website"]:
            submission = submit_customer_registration(
                full_name=form.cleaned_data["full_name"],
                email=form.cleaned_data["email"],
                mobile_number=form.cleaned_data["mobile_number"],
                address=form.cleaned_data["address"],
                source_ip=_source_ip(request),
            )
            if submission.application is not None:
                verification_url = _registration_verification_url(
                    request,
                    submission.application,
                    submission.raw_token,
                )
                send_customer_registration_verification(
                    application=submission.application,
                    raw_token=submission.raw_token,
                    verification_url=verification_url,
                )
        return redirect("customer_registration_submitted")

    return render(
        request,
        "account/customer_registration.html",
        {"form": form},
    )


@never_cache
def customer_registration_submitted(request):
    if not _public_registration_enabled():
        raise Http404
    return render(request, "account/customer_registration_submitted.html")


@never_cache
def customer_registration_verify(request, application_id, token):
    if not _public_registration_enabled():
        raise Http404
    application = CustomerRegistration.objects.filter(pk=application_id).first()
    if application is None or not registration_is_verifiable(application, token):
        return render(
            request,
            "account/customer_registration_verification_invalid.html",
            status=200,
        )

    if request.method == "POST":
        try:
            verify_customer_registration_email(
                application_id=application.pk,
                raw_token=token,
            )
        except (InvalidCustomerRegistration, ObjectDoesNotExist):
            return render(
                request,
                "account/customer_registration_verification_invalid.html",
                status=200,
            )
        return redirect("customer_registration_verified")

    return render(request, "account/customer_registration_verify.html")


@never_cache
def customer_registration_verified(request):
    if not _public_registration_enabled():
        raise Http404
    return render(request, "account/customer_registration_verified.html")


def owner_required(view_func):
    @login_required
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        user = request.user
        if not (user.is_superuser or user.role == user.Role.OWNER):
            raise PermissionDenied
        return view_func(request, *args, **kwargs)

    return wrapped


@owner_required
def customer_registration_list(request):
    applications = CustomerRegistration.objects.select_related(
        "reviewed_by", "approved_user__customer_profile"
    )
    return render(
        request,
        "account/customer_registration_list.html",
        {"applications": applications},
    )


@owner_required
def customer_registration_detail(request, application_id):
    application = get_object_or_404(
        CustomerRegistration.objects.select_related(
            "reviewed_by", "approved_user__customer_profile"
        ),
        pk=application_id,
    )
    return render(
        request,
        "account/customer_registration_detail.html",
        {
            "application": application,
            "approval_form": CustomerRegistrationApprovalForm(),
            "rejection_form": CustomerRegistrationRejectionForm(),
        },
    )


def _add_validation_errors(form, error):
    if hasattr(error, "message_dict"):
        for field, field_errors in error.message_dict.items():
            for field_error in field_errors:
                form.add_error(field if field in form.fields else None, field_error)
    else:
        for field_error in error.messages:
            form.add_error(None, field_error)


@owner_required
@require_POST
def customer_registration_approve(request, application_id):
    application = get_object_or_404(CustomerRegistration, pk=application_id)
    approval_form = CustomerRegistrationApprovalForm(request.POST)
    if approval_form.is_valid():
        try:
            customer, invitation, raw_token = approve_customer_registration(
                application=application,
                reviewed_by=request.user,
                reason=approval_form.cleaned_data["reason"],
            )
        except (InvalidCustomerRegistration, ValidationError) as error:
            _add_validation_errors(approval_form, error)
        else:
            setup_url = request.build_absolute_uri(
                reverse(
                    "customer_invitation_accept",
                    kwargs={
                        "invitation_id": invitation.pk,
                        "token": raw_token,
                    },
                )
            )
            if send_customer_invitation(
                invitation=invitation,
                raw_token=raw_token,
                setup_url=setup_url,
            ):
                messages.success(
                    request,
                    "Registration approved. The password-setup email was accepted by the email provider.",
                )
            else:
                messages.warning(
                    request,
                    "Registration approved, but the password-setup email could not be sent. Resend it from the customer record.",
                )
            return redirect("schemes:customer_detail", customer_id=customer.pk)

    return render(
        request,
        "account/customer_registration_detail.html",
        {
            "application": application,
            "approval_form": approval_form,
            "rejection_form": CustomerRegistrationRejectionForm(),
        },
        status=400,
    )


@owner_required
@require_POST
def customer_registration_reject(request, application_id):
    application = get_object_or_404(CustomerRegistration, pk=application_id)
    rejection_form = CustomerRegistrationRejectionForm(request.POST)
    if rejection_form.is_valid():
        try:
            reject_customer_registration(
                application=application,
                reviewed_by=request.user,
                reason=rejection_form.cleaned_data["reason"],
            )
        except (InvalidCustomerRegistration, ValidationError) as error:
            _add_validation_errors(rejection_form, error)
        else:
            messages.success(request, "Registration rejected and retained for audit.")
            return redirect("customer_registration_list")

    return render(
        request,
        "account/customer_registration_detail.html",
        {
            "application": application,
            "approval_form": CustomerRegistrationApprovalForm(),
            "rejection_form": rejection_form,
        },
        status=400,
    )


@owner_required
@require_POST
def customer_registration_resend_verification(request, application_id):
    application = get_object_or_404(CustomerRegistration, pk=application_id)
    try:
        application, raw_token = issue_registration_verification(
            application=application,
            actor=request.user,
        )
    except (InvalidCustomerRegistration, ValidationError) as error:
        messages.error(request, " ".join(error.messages))
    else:
        verification_url = _registration_verification_url(
            request,
            application,
            raw_token,
        )
        if send_customer_registration_verification(
            application=application,
            raw_token=raw_token,
            verification_url=verification_url,
        ):
            messages.success(
                request,
                "A replacement verification email was accepted by the email provider.",
            )
        else:
            messages.warning(
                request,
                "The replacement verification email could not be sent.",
            )
    return redirect("customer_registration_detail", application_id=application.pk)
