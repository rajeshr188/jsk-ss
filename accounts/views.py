from functools import wraps

from allauth.account.decorators import reauthentication_required
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
    CustomerDeletionCompletionForm,
    CustomerDeletionRetentionFormSet,
    CustomerAccountDeletionAuthenticatedForm,
    CustomerAccountDeletionHoldForm,
    CustomerAccountDeletionPublicForm,
    CustomerInvitationPasswordForm,
    CustomerRegistrationApprovalForm,
    CustomerRegistrationForm,
    CustomerRegistrationRejectionForm,
)
from .models import (
    CustomerAccountDeletionNotice,
    CustomerAccountDeletionRequest,
    CustomerInvitation,
    CustomerRegistration,
)
from .deletion import (
    RETENTION_CATEGORIES,
    complete_customer_account_deletion,
    send_completion_notice,
    review_customer_account_retention,
)
from .selectors import (
    customer_account_deletion_detail,
    customer_account_deletion_disposition,
    customer_account_deletion_queue,
)
from .services import (
    InvalidCustomerAccountDeletion,
    InvalidCustomerRegistration,
    InvalidCustomerInvitation,
    accept_customer_invitation,
    approve_customer_registration,
    issue_registration_verification,
    invitation_is_available,
    registration_is_verifiable,
    reject_customer_registration,
    record_customer_account_deletion_hold,
    request_authenticated_customer_account_deletion,
    send_customer_account_deletion_notice,
    send_customer_account_deletion_verification,
    send_customer_invitation,
    send_customer_registration_verification,
    submit_customer_registration,
    submit_customer_account_deletion,
    deletion_request_is_verifiable,
    verify_and_contain_customer_account,
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
        if not user.is_active or not (user.is_superuser or user.role == user.Role.OWNER):
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


def _customer_account_deletion_enabled():
    return settings.CUSTOMER_ACCOUNT_DELETION_ENABLED


def _deletion_verification_url(request, deletion_request, raw_token):
    return request.build_absolute_uri(
        reverse(
            "customer_account_deletion_verify",
            kwargs={"request_id": deletion_request.pk, "token": raw_token},
        )
    )


@never_cache
def customer_account_deletion(request):
    if not _customer_account_deletion_enabled():
        raise Http404
    if request.user.is_authenticated:
        return redirect("customer_account_deletion_authenticated")

    form = CustomerAccountDeletionPublicForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if not form.cleaned_data["website"]:
            submission = submit_customer_account_deletion(
                email=form.cleaned_data["email"],
                source_ip=_source_ip(request),
            )
            if submission.deletion_request is not None:
                verification_url = _deletion_verification_url(
                    request,
                    submission.deletion_request,
                    submission.raw_token,
                )
                send_customer_account_deletion_verification(
                    deletion_request=submission.deletion_request,
                    raw_token=submission.raw_token,
                    verification_url=verification_url,
                )
        return redirect("customer_account_deletion_submitted")
    return render(
        request,
        "account/customer_deletion_request.html",
        {"form": form},
    )


@never_cache
def customer_account_deletion_submitted(request):
    if not _customer_account_deletion_enabled():
        raise Http404
    return render(request, "account/customer_deletion_submitted.html")


@never_cache
def customer_account_deletion_verify(request, request_id, token):
    if not _customer_account_deletion_enabled():
        raise Http404
    deletion_request = CustomerAccountDeletionRequest.objects.filter(
        pk=request_id
    ).first()
    if deletion_request is None or not deletion_request_is_verifiable(
        deletion_request, token
    ):
        return render(
            request,
            "account/customer_deletion_verification_invalid.html",
            status=200,
        )
    if request.method == "POST":
        try:
            deletion_request = verify_and_contain_customer_account(
                deletion_request_id=deletion_request.pk,
                raw_token=token,
            )
        except (InvalidCustomerAccountDeletion, ObjectDoesNotExist):
            return render(
                request,
                "account/customer_deletion_verification_invalid.html",
                status=200,
            )
        send_customer_account_deletion_notice(
            deletion_request=deletion_request,
            notice_kind="contained",
        )
        return redirect("customer_account_deletion_verified")
    return render(request, "account/customer_deletion_verify.html")


@never_cache
def customer_account_deletion_verified(request):
    if not _customer_account_deletion_enabled():
        raise Http404
    return render(request, "account/customer_deletion_verified.html")


@login_required
@reauthentication_required(allow_get=True)
@never_cache
def customer_account_deletion_authenticated(request):
    if not _customer_account_deletion_enabled():
        raise Http404
    user = request.user
    if (
        user.role != user.Role.CUSTOMER
        or user.is_staff
        or user.is_superuser
        or not hasattr(user, "customer_profile")
    ):
        raise PermissionDenied
    form = CustomerAccountDeletionAuthenticatedForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            deletion_request = request_authenticated_customer_account_deletion(
                user=user,
                source_ip=_source_ip(request),
            )
        except InvalidCustomerAccountDeletion as error:
            _add_validation_errors(form, error)
        else:
            send_customer_account_deletion_notice(
                deletion_request=deletion_request,
                notice_kind="contained",
            )
            return redirect("customer_account_deletion_verified")
    return render(
        request,
        "account/customer_deletion_authenticated.html",
        {
            "form": form,
            "completion_target_days": (
                settings.CUSTOMER_ACCOUNT_DELETION_COMPLETION_TARGET_DAYS
            ),
        },
    )


@owner_required
@never_cache
def customer_account_deletion_list(request):
    if not _customer_account_deletion_enabled():
        raise Http404
    return render(
        request,
        "account/customer_deletion_list.html",
        {"deletion_requests": customer_account_deletion_queue()},
    )


@owner_required
@never_cache
def customer_account_deletion_detail_view(request, request_id):
    if not _customer_account_deletion_enabled():
        raise Http404
    deletion_request = get_object_or_404(
        CustomerAccountDeletionRequest,
        pk=request_id,
    )
    deletion_request = customer_account_deletion_detail(deletion_request.pk)
    return render(
        request,
        "account/customer_deletion_detail.html",
        {
            "deletion_request": deletion_request,
            "hold_form": CustomerAccountDeletionHoldForm(),
            "disposition": customer_account_deletion_disposition(deletion_request),
        },
    )


@owner_required
@never_cache
@reauthentication_required()
@require_POST
def customer_account_deletion_hold(request, request_id):
    if not _customer_account_deletion_enabled():
        raise Http404
    deletion_request = get_object_or_404(
        CustomerAccountDeletionRequest,
        pk=request_id,
    )
    hold_form = CustomerAccountDeletionHoldForm(request.POST)
    if hold_form.is_valid():
        try:
            deletion_request, _ = record_customer_account_deletion_hold(
                deletion_request=deletion_request,
                actor=request.user,
                reason=hold_form.cleaned_data["reason"],
                retained_categories=hold_form.cleaned_data["retained_categories"],
                review_due_at=hold_form.cleaned_data["review_due_at"],
            )
        except (InvalidCustomerAccountDeletion, ValidationError) as error:
            _add_validation_errors(hold_form, error)
        else:
            send_customer_account_deletion_notice(
                deletion_request=deletion_request,
                notice_kind="awaiting_settlement",
            )
            messages.success(request, "The reviewed hold and next review date were recorded.")
            return redirect(
                "customer_account_deletion_detail",
                request_id=deletion_request.pk,
            )
    deletion_request = customer_account_deletion_detail(deletion_request.pk)
    return render(
        request,
        "account/customer_deletion_detail.html",
        {
            "deletion_request": deletion_request,
            "hold_form": hold_form,
            "disposition": customer_account_deletion_disposition(deletion_request),
        },
        status=400,
    )


@owner_required
@never_cache
@reauthentication_required()
def customer_account_deletion_complete(request, request_id, review=False):
    if not _customer_account_deletion_enabled():
        raise Http404
    deletion_request = get_object_or_404(CustomerAccountDeletionRequest, pk=request_id)
    if review and deletion_request.status != deletion_request.Status.COMPLETED_WITH_RETENTION:
        raise Http404
    if not review and deletion_request.status == deletion_request.Status.COMPLETED_WITH_RETENTION:
        return redirect("customer_account_deletion_detail", request_id=request_id)
    form = CustomerDeletionCompletionForm(request.POST if request.method == "POST" else None)
    formset = CustomerDeletionRetentionFormSet(
        request.POST if request.method == "POST" else None,
        initial=[{"category": key} for key, label in RETENTION_CATEGORIES],
        prefix="retention",
    )
    if request.method == "POST":
        valid_form, valid_rows = form.is_valid(), formset.is_valid()
        if valid_form and valid_rows:
            rows = [{**row, "review_on": row["review_on"].isoformat()} for row in formset.cleaned_data]
            try:
                service = review_customer_account_retention if review else complete_customer_account_deletion
                locked, decision = service(
                    request_id=request_id, actor=request.user, retention_plan=rows,
                    **{k: v for k, v in form.cleaned_data.items() if k != "reviewed"},
                )
            except ValidationError as error:
                form.add_error(None, error)
            else:
                # The account mutation has committed. SMTP failure cannot undo it.
                if not hasattr(decision, "notice"):
                    messages.success(request, "Retention review recorded. No contact address remains; no notice was sent. Do not recover erased contact data.")
                    return redirect("customer_account_deletion_detail", request_id=locked.pk)
                accepted = send_completion_notice(notice_id=decision.notice.pk, actor=request.user)
                if accepted:
                    messages.success(request, "Eligible account data removed; the email provider accepted the outcome notice.")
                else:
                    messages.warning(request, "Account data removed. The outcome email needs retry from this request's notice queue.")
                return redirect("customer_account_deletion_detail", request_id=locked.pk)
    return render(request, "account/customer_deletion_complete.html", {
        "deletion_request": deletion_request,
        "disposition": customer_account_deletion_disposition(deletion_request),
        "completion_form": form, "retention_forms": formset, "is_review": review,
    }, status=400 if request.method == "POST" else 200)


@owner_required
@never_cache
@reauthentication_required()
@require_POST
def customer_account_deletion_retry_notice(request, request_id, notice_id):
    if not _customer_account_deletion_enabled():
        raise Http404
    notice = get_object_or_404(CustomerAccountDeletionNotice, pk=notice_id, decision__request_id=request_id)
    accepted = send_completion_notice(notice_id=notice.pk, actor=request.user)
    if accepted:
        messages.success(request, "The email provider accepted the notice; the delivery address has been cleared from the queue.")
    else:
        messages.warning(request, "Notice delivery is still unconfirmed. Review SMTP and retry; no account removal was repeated.")
    return redirect("customer_account_deletion_detail", request_id=request_id)
