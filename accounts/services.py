import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import timedelta

from allauth.account.models import EmailAddress
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.mail import EmailMultiAlternatives
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.crypto import constant_time_compare

from .models import (
    CustomerInvitation,
    CustomerRegistration,
    CustomerRegistrationAttempt,
)


class InvalidCustomerInvitation(ValidationError):
    pass


class InvalidCustomerRegistration(ValidationError):
    pass


@dataclass(frozen=True)
class CustomerRegistrationSubmission:
    application: CustomerRegistration | None
    raw_token: str | None


def _actor_label(actor):
    return actor.email or actor.username or f"User {actor.pk}"


def _token_digest(raw_token):
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _identity_digest(value):
    return hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        value.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def normalize_indian_mobile(value):
    digits = "".join(character for character in value if character.isdigit())
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    if len(digits) != 10 or digits[0] not in "6789":
        raise ValidationError(
            "Enter a valid 10-digit Indian mobile number beginning with 6, 7, 8, or 9."
        )
    return f"+91{digits}"


def _customer_mobile_exists(normalized_mobile):
    from schemes.models import Customer

    for mobile_number in Customer.objects.values_list("mobile_number", flat=True):
        try:
            if normalize_indian_mobile(mobile_number) == normalized_mobile:
                return True
        except ValidationError:
            continue
    return False


def _registration_token_matches(application, raw_token):
    if not raw_token:
        return False
    return constant_time_compare(
        application.email_token_digest,
        _token_digest(raw_token),
    )


def registration_is_verifiable(application, raw_token):
    return (
        _registration_token_matches(application, raw_token)
        and application.status
        == CustomerRegistration.Status.PENDING_EMAIL_VERIFICATION
        and application.email_verification_expires_at > timezone.now()
    )


@transaction.atomic
def submit_customer_registration(
    *,
    full_name,
    email,
    mobile_number,
    address,
    source_ip,
):
    user_model = get_user_model()
    normalized_email = user_model.objects.normalize_email(email).strip().lower()
    normalized_mobile = normalize_indian_mobile(mobile_number)
    normalized_source = (source_ip or "unknown").strip().lower()
    email_digest = _identity_digest(normalized_email)
    mobile_digest = _identity_digest(normalized_mobile)
    source_ip_digest = _identity_digest(normalized_source)
    now = timezone.now()
    cutoff = now - timedelta(hours=1)
    attempt_limit = settings.PUBLIC_REGISTRATION_ATTEMPTS_PER_HOUR

    CustomerRegistrationAttempt.objects.filter(
        attempted_at__lt=now
        - timedelta(hours=settings.PUBLIC_REGISTRATION_ATTEMPT_RETENTION_HOURS)
    ).delete()

    attempts = CustomerRegistrationAttempt.objects.filter(attempted_at__gte=cutoff)
    if (
        attempts.filter(source_ip_digest=source_ip_digest).count() >= attempt_limit
        or attempts.filter(email_digest=email_digest).count() >= attempt_limit
        or attempts.filter(mobile_digest=mobile_digest).count() >= attempt_limit
    ):
        return CustomerRegistrationSubmission(None, None)

    CustomerRegistration.objects.filter(
        status=CustomerRegistration.Status.PENDING_EMAIL_VERIFICATION,
        email_verification_expires_at__lte=now,
    ).filter(Q(email__iexact=normalized_email) | Q(mobile_number=normalized_mobile)).update(
        status=CustomerRegistration.Status.EXPIRED
    )

    existing_identity = (
        user_model.objects.filter(email__iexact=normalized_email).exists()
        or _customer_mobile_exists(normalized_mobile)
        or CustomerRegistration.objects.filter(
            status__in=[
                CustomerRegistration.Status.PENDING_EMAIL_VERIFICATION,
                CustomerRegistration.Status.AWAITING_OWNER_APPROVAL,
            ]
        )
        .filter(Q(email__iexact=normalized_email) | Q(mobile_number=normalized_mobile))
        .exists()
    )
    if existing_identity:
        CustomerRegistrationAttempt.objects.create(
            email_digest=email_digest,
            mobile_digest=mobile_digest,
            source_ip_digest=source_ip_digest,
            outcome=CustomerRegistrationAttempt.Outcome.IGNORED,
        )
        return CustomerRegistrationSubmission(None, None)

    raw_token = secrets.token_urlsafe(32)
    try:
        with transaction.atomic():
            application = CustomerRegistration.objects.create(
                full_name=full_name.strip(),
                email=normalized_email,
                mobile_number=normalized_mobile,
                address=address.strip(),
                email_token_digest=_token_digest(raw_token),
                email_verification_expires_at=now
                + timedelta(
                    hours=settings.PUBLIC_REGISTRATION_EMAIL_EXPIRY_HOURS
                ),
                terms_version=settings.PUBLIC_REGISTRATION_TERMS_VERSION,
                privacy_version=settings.PUBLIC_REGISTRATION_PRIVACY_VERSION,
                consent_accepted_at=now,
                source_ip_digest=source_ip_digest,
            )
    except IntegrityError:
        CustomerRegistrationAttempt.objects.create(
            email_digest=email_digest,
            mobile_digest=mobile_digest,
            source_ip_digest=source_ip_digest,
            outcome=CustomerRegistrationAttempt.Outcome.IGNORED,
        )
        return CustomerRegistrationSubmission(None, None)

    CustomerRegistrationAttempt.objects.create(
        email_digest=email_digest,
        mobile_digest=mobile_digest,
        source_ip_digest=source_ip_digest,
        outcome=CustomerRegistrationAttempt.Outcome.CREATED,
    )
    return CustomerRegistrationSubmission(application, raw_token)


def send_customer_registration_verification(
    *, application, raw_token, verification_url
):
    application = CustomerRegistration.objects.get(pk=application.pk)
    if not registration_is_verifiable(application, raw_token):
        raise InvalidCustomerRegistration(
            "This email verification request is no longer available."
        )
    if application.email_sent_at:
        raise ValidationError("This verification email was already sent.")

    context = {
        "customer_name": application.full_name,
        "verification_url": verification_url,
        "expires_at": application.email_verification_expires_at,
    }
    subject = " ".join(
        render_to_string(
            "account/email/customer_registration_verification_subject.txt",
            context,
        ).splitlines()
    ).strip()
    text_body = render_to_string(
        "account/email/customer_registration_verification_message.txt",
        context,
    ).strip()
    html_body = render_to_string(
        "account/email/customer_registration_verification_message.html",
        context,
    ).strip()
    message = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[application.email],
        headers={
            "X-PM-TrackLinks": "None",
            "X-PM-TrackOpens": "false",
            "X-PM-Tag": "customer-registration-verification",
        },
    )
    message.attach_alternative(html_body, "text/html")
    try:
        accepted_count = message.send(fail_silently=False)
        if accepted_count != 1:
            raise RuntimeError("The email backend did not accept the verification email.")
    except Exception as error:
        CustomerRegistration.objects.filter(pk=application.pk).update(
            delivery_failed_at=timezone.now(),
            delivery_error=type(error).__name__[:100],
        )
        return False

    CustomerRegistration.objects.filter(pk=application.pk).update(
        email_sent_at=timezone.now(),
        delivery_failed_at=None,
        delivery_error="",
    )
    return True


@transaction.atomic
def verify_customer_registration_email(*, application_id, raw_token):
    application = CustomerRegistration.objects.select_for_update().get(
        pk=application_id
    )
    if not registration_is_verifiable(application, raw_token):
        raise InvalidCustomerRegistration(
            "This email verification request is no longer available."
        )
    application.status = CustomerRegistration.Status.AWAITING_OWNER_APPROVAL
    application.email_verified_at = timezone.now()
    application.save(update_fields=["status", "email_verified_at"])
    return application


@transaction.atomic
def issue_registration_verification(*, application, actor):
    _validate_registration_owner(actor)
    application = CustomerRegistration.objects.select_for_update().get(
        pk=application.pk
    )
    if application.status != CustomerRegistration.Status.PENDING_EMAIL_VERIFICATION:
        raise InvalidCustomerRegistration(
            "Only an application awaiting email verification can be resent."
        )
    raw_token = secrets.token_urlsafe(32)
    application.email_token_digest = _token_digest(raw_token)
    application.email_verification_expires_at = timezone.now() + timedelta(
        hours=settings.PUBLIC_REGISTRATION_EMAIL_EXPIRY_HOURS
    )
    application.email_sent_at = None
    application.delivery_failed_at = None
    application.delivery_error = ""
    application.save(
        update_fields=[
            "email_token_digest",
            "email_verification_expires_at",
            "email_sent_at",
            "delivery_failed_at",
            "delivery_error",
        ]
    )
    return application, raw_token


def _validate_registration_owner(actor):
    user_model = get_user_model()
    if actor is None or not actor.is_active or not (
        actor.is_superuser or actor.role == user_model.Role.OWNER
    ):
        raise ValidationError("Only an active owner can review registrations.")


@transaction.atomic
def approve_customer_registration(*, application, reviewed_by, reason):
    _validate_registration_owner(reviewed_by)
    application = CustomerRegistration.objects.select_for_update().get(
        pk=application.pk
    )
    if application.status != CustomerRegistration.Status.AWAITING_OWNER_APPROVAL:
        raise InvalidCustomerRegistration(
            "Only a verified application awaiting approval can be approved."
        )
    normalized_reason = reason.strip()
    if not normalized_reason:
        raise ValidationError({"reason": "Enter a reason for this decision."})

    user_model = get_user_model()
    if user_model.objects.filter(email__iexact=application.email).exists():
        raise ValidationError(
            {"email": "A login with this email now exists; review it manually."}
        )
    if _customer_mobile_exists(application.mobile_number):
        raise ValidationError(
            {"mobile_number": "A customer with this mobile number now exists."}
        )

    from schemes.services import create_invited_customer

    try:
        customer, invitation, raw_token = create_invited_customer(
            full_name=application.full_name,
            email=application.email,
            mobile_number=application.mobile_number,
            address=application.address,
            invited_by=reviewed_by,
        )
    except IntegrityError as error:
        raise ValidationError(
            "A conflicting customer identity was created during approval; review it manually."
        ) from error
    now = timezone.now()
    application.status = CustomerRegistration.Status.APPROVED
    application.reviewed_at = now
    application.reviewed_by = reviewed_by
    application.reviewed_by_label = _actor_label(reviewed_by)
    application.review_reason = normalized_reason
    application.mobile_verified_at = now
    application.approved_user = customer.user
    application.save(
        update_fields=[
            "status",
            "reviewed_at",
            "reviewed_by",
            "reviewed_by_label",
            "review_reason",
            "mobile_verified_at",
            "approved_user",
        ]
    )
    return customer, invitation, raw_token


@transaction.atomic
def reject_customer_registration(*, application, reviewed_by, reason):
    _validate_registration_owner(reviewed_by)
    application = CustomerRegistration.objects.select_for_update().get(
        pk=application.pk
    )
    if application.status != CustomerRegistration.Status.AWAITING_OWNER_APPROVAL:
        raise InvalidCustomerRegistration(
            "Only a verified application awaiting approval can be rejected."
        )
    normalized_reason = reason.strip()
    if not normalized_reason:
        raise ValidationError({"reason": "Enter a reason for this decision."})
    application.status = CustomerRegistration.Status.REJECTED
    application.reviewed_at = timezone.now()
    application.reviewed_by = reviewed_by
    application.reviewed_by_label = _actor_label(reviewed_by)
    application.review_reason = normalized_reason
    application.save(
        update_fields=[
            "status",
            "reviewed_at",
            "reviewed_by",
            "reviewed_by_label",
            "review_reason",
        ]
    )
    return application


def invitation_token_matches(invitation, raw_token):
    if not raw_token:
        return False
    return constant_time_compare(
        invitation.token_digest,
        _token_digest(raw_token),
    )


def invitation_is_available(invitation, raw_token):
    user = invitation.user
    return (
        invitation_token_matches(invitation, raw_token)
        and invitation.accepted_at is None
        and invitation.revoked_at is None
        and invitation.expires_at > timezone.now()
        and user.is_active
        and user.role == user.Role.CUSTOMER
        and not user.has_usable_password()
        and user.email.lower() == invitation.email.lower()
    )


@transaction.atomic
def issue_customer_invitation(*, user, created_by):
    user_model = get_user_model()
    if created_by is None or not created_by.is_active or not (
        created_by.is_superuser or created_by.role == user_model.Role.OWNER
    ):
        raise ValidationError("Only an active owner can invite a customer.")

    locked_user = user_model.objects.select_for_update().get(pk=user.pk)
    if (
        not locked_user.is_active
        or locked_user.role != user_model.Role.CUSTOMER
        or not locked_user.email
    ):
        raise ValidationError("The customer login is not eligible for an invitation.")
    if locked_user.has_usable_password():
        raise ValidationError(
            "This customer already has a password. Use password reset instead."
        )

    now = timezone.now()
    CustomerInvitation.objects.filter(
        user=locked_user,
        accepted_at__isnull=True,
        revoked_at__isnull=True,
    ).update(revoked_at=now)

    raw_token = secrets.token_urlsafe(32)
    invitation = CustomerInvitation(
        user=locked_user,
        email=locked_user.email.strip().lower(),
        token_digest=_token_digest(raw_token),
        created_by=created_by,
        created_by_label=_actor_label(created_by),
        expires_at=now
        + timedelta(hours=settings.CUSTOMER_INVITATION_EXPIRY_HOURS),
    )
    invitation.full_clean()
    invitation.save()
    return invitation, raw_token


def send_customer_invitation(*, invitation, raw_token, setup_url):
    invitation = CustomerInvitation.objects.select_related("user").get(
        pk=invitation.pk
    )
    if not invitation_is_available(invitation, raw_token):
        raise InvalidCustomerInvitation("This invitation is no longer available.")
    if invitation.email_sent_at:
        raise ValidationError("This invitation was already sent.")

    context = {
        "customer_name": invitation.user.get_full_name() or invitation.email,
        "setup_url": setup_url,
        "expires_at": invitation.expires_at,
    }
    subject = render_to_string(
        "account/email/customer_invitation_subject.txt", context
    )
    subject = " ".join(subject.splitlines()).strip()
    text_body = render_to_string(
        "account/email/customer_invitation_message.txt", context
    ).strip()
    html_body = render_to_string(
        "account/email/customer_invitation_message.html", context
    ).strip()
    message = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[invitation.email],
        headers={
            "X-PM-TrackLinks": "None",
            "X-PM-TrackOpens": "false",
            "X-PM-Tag": "customer-invitation",
        },
    )
    message.attach_alternative(html_body, "text/html")

    try:
        accepted_count = message.send(fail_silently=False)
        if accepted_count != 1:
            raise RuntimeError("The email backend did not accept the invitation.")
    except Exception as error:
        CustomerInvitation.objects.filter(pk=invitation.pk).update(
            delivery_failed_at=timezone.now(),
            delivery_error=type(error).__name__[:100],
        )
        return False

    CustomerInvitation.objects.filter(pk=invitation.pk).update(
        email_sent_at=timezone.now(),
        delivery_failed_at=None,
        delivery_error="",
    )
    return True


@transaction.atomic
def accept_customer_invitation(*, invitation_id, raw_token, new_password):
    user_model = get_user_model()
    invitation_user_id = CustomerInvitation.objects.values_list(
        "user_id", flat=True
    ).get(pk=invitation_id)
    # Invitation issue/resend takes locks in this same user-then-invitation order.
    user = user_model.objects.select_for_update().get(pk=invitation_user_id)
    invitation = CustomerInvitation.objects.select_for_update().get(pk=invitation_id)
    invitation.user = user
    if not invitation_is_available(invitation, raw_token):
        raise InvalidCustomerInvitation("This invitation is no longer available.")

    validate_password(new_password, user=user)
    user.set_password(new_password)
    user.save(update_fields=["password"])

    email_address = EmailAddress.objects.filter(
        email__iexact=user.email
    ).select_for_update().first()
    if email_address is not None and email_address.user_id != user.pk:
        raise ValidationError("The invitation email belongs to another login.")
    if email_address is None:
        email_address = EmailAddress.objects.create(
            user=user,
            email=user.email,
            primary=True,
            verified=True,
        )
    else:
        EmailAddress.objects.filter(user=user, primary=True).exclude(
            pk=email_address.pk
        ).update(primary=False)
        email_address.primary = True
        email_address.verified = True
        email_address.save(update_fields=["primary", "verified"])

    invitation.accepted_at = timezone.now()
    invitation.save(update_fields=["accepted_at"])
    CustomerInvitation.objects.filter(
        user=user,
        accepted_at__isnull=True,
        revoked_at__isnull=True,
    ).exclude(pk=invitation.pk).update(revoked_at=timezone.now())
    return user
