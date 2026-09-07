import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import timedelta

from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth import SESSION_KEY
from django.contrib.auth.password_validation import validate_password
from django.contrib.sessions.models import Session
from django.core.exceptions import ValidationError
from django.core.mail import EmailMultiAlternatives
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.crypto import constant_time_compare

from .models import (
    CustomerAccountDeletionAction,
    CustomerAccountDeletionAttempt,
    CustomerAccountDeletionDecision,
    CustomerAccountDeletionRequest,
    CustomerInvitation,
    CustomerRegistration,
    CustomerRegistrationAttempt,
)


class InvalidCustomerInvitation(ValidationError):
    pass


class InvalidCustomerRegistration(ValidationError):
    pass


class InvalidCustomerAccountDeletion(ValidationError):
    pass


@dataclass(frozen=True)
class CustomerRegistrationSubmission:
    application: CustomerRegistration | None
    raw_token: str | None


@dataclass(frozen=True)
class CustomerAccountDeletionSubmission:
    deletion_request: CustomerAccountDeletionRequest | None
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


def _deletion_actor_label(actor, fallback):
    return _actor_label(actor) if actor is not None else fallback


def _append_deletion_action(
    *, deletion_request, action, actor=None, actor_label="System", details=None
):
    return CustomerAccountDeletionAction.objects.create(
        request=deletion_request,
        action=action,
        actor=actor,
        actor_label=_deletion_actor_label(actor, actor_label),
        details=details or {},
    )


def deletion_request_is_verifiable(deletion_request, raw_token):
    return bool(
        raw_token
        and deletion_request.status
        == CustomerAccountDeletionRequest.Status.PENDING_VERIFICATION
        and deletion_request.verification_expires_at > timezone.now()
        and constant_time_compare(
            deletion_request.verification_token_digest,
            _token_digest(raw_token),
        )
    )


def _record_deletion_attempt(*, email_digest, source_ip_digest, outcome):
    CustomerAccountDeletionAttempt.objects.create(
        email_digest=email_digest,
        source_ip_digest=source_ip_digest,
        outcome=outcome,
    )


@transaction.atomic
def submit_customer_account_deletion(*, email, source_ip):
    """Accept a public request without disclosing whether the identity exists."""

    from schemes.models import Customer

    user_model = get_user_model()
    normalized_email = user_model.objects.normalize_email(email).strip().lower()
    normalized_source = (source_ip or "unknown").strip().lower()
    email_digest = _identity_digest(normalized_email)
    source_ip_digest = _identity_digest(normalized_source)
    now = timezone.now()
    attempt_cutoff = now - timedelta(hours=1)
    retention_cutoff = now - timedelta(
        hours=settings.CUSTOMER_ACCOUNT_DELETION_ATTEMPT_RETENTION_HOURS
    )
    CustomerAccountDeletionAttempt.objects.filter(
        attempted_at__lt=retention_cutoff
    ).delete()

    recent_attempts = CustomerAccountDeletionAttempt.objects.filter(
        attempted_at__gte=attempt_cutoff
    )
    if (
        recent_attempts.filter(email_digest=email_digest).count()
        >= settings.CUSTOMER_ACCOUNT_DELETION_ATTEMPTS_PER_HOUR
        or recent_attempts.filter(source_ip_digest=source_ip_digest).count()
        >= settings.CUSTOMER_ACCOUNT_DELETION_ATTEMPTS_PER_HOUR
    ):
        return CustomerAccountDeletionSubmission(None, None)

    CustomerAccountDeletionRequest.objects.filter(
        status=CustomerAccountDeletionRequest.Status.PENDING_VERIFICATION,
        verification_expires_at__lte=now,
    ).update(
        status=CustomerAccountDeletionRequest.Status.EXPIRED,
        closed_at=now,
    )

    customer = (
        Customer.objects.select_related("user")
        .filter(
            email__iexact=normalized_email,
            user__email__iexact=normalized_email,
            user__role=user_model.Role.CUSTOMER,
            user__is_active=True,
            user__is_staff=False,
            user__is_superuser=False,
        )
        .first()
    )
    if customer is None:
        _record_deletion_attempt(
            email_digest=email_digest,
            source_ip_digest=source_ip_digest,
            outcome=CustomerAccountDeletionAttempt.Outcome.IGNORED,
        )
        return CustomerAccountDeletionSubmission(None, None)

    existing = (
        CustomerAccountDeletionRequest.objects.select_for_update()
        .filter(
            customer=customer,
            status__in=CustomerAccountDeletionRequest.OPEN_STATUSES,
        )
        .first()
    )
    if existing is not None and existing.status != existing.Status.PENDING_VERIFICATION:
        _record_deletion_attempt(
            email_digest=email_digest,
            source_ip_digest=source_ip_digest,
            outcome=CustomerAccountDeletionAttempt.Outcome.IGNORED,
        )
        return CustomerAccountDeletionSubmission(None, None)
    if (
        existing is not None
        and existing.verification_email_sent_at is not None
        and existing.verification_delivery_failed_at is None
    ):
        _record_deletion_attempt(
            email_digest=email_digest,
            source_ip_digest=source_ip_digest,
            outcome=CustomerAccountDeletionAttempt.Outcome.IGNORED,
        )
        return CustomerAccountDeletionSubmission(None, None)

    raw_token = secrets.token_urlsafe(32)
    expires_at = now + timedelta(
        hours=settings.CUSTOMER_ACCOUNT_DELETION_EMAIL_EXPIRY_HOURS
    )
    if existing is None:
        try:
            deletion_request = CustomerAccountDeletionRequest.objects.create(
                customer=customer,
                requested_email=normalized_email,
                email_digest=email_digest,
                source_ip_digest=source_ip_digest,
                verification_token_digest=_token_digest(raw_token),
                source=CustomerAccountDeletionRequest.Source.PUBLIC,
                policy_version=settings.CUSTOMER_ACCOUNT_DELETION_POLICY_VERSION,
                verification_expires_at=expires_at,
            )
        except IntegrityError:
            _record_deletion_attempt(
                email_digest=email_digest,
                source_ip_digest=source_ip_digest,
                outcome=CustomerAccountDeletionAttempt.Outcome.IGNORED,
            )
            return CustomerAccountDeletionSubmission(None, None)
        replacement = False
    else:
        deletion_request = existing
        deletion_request.verification_token_digest = _token_digest(raw_token)
        deletion_request.verification_expires_at = expires_at
        deletion_request.verification_email_sent_at = None
        deletion_request.verification_delivery_failed_at = None
        deletion_request.verification_delivery_error = ""
        deletion_request.source_ip_digest = source_ip_digest
        deletion_request.save(
            update_fields=[
                "verification_token_digest",
                "verification_expires_at",
                "verification_email_sent_at",
                "verification_delivery_failed_at",
                "verification_delivery_error",
                "source_ip_digest",
            ]
        )
        replacement = True

    _append_deletion_action(
        deletion_request=deletion_request,
        action=CustomerAccountDeletionAction.Action.REQUESTED,
        actor_label="Public deletion request",
        details={"source": "PUBLIC", "replacement": replacement},
    )
    _record_deletion_attempt(
        email_digest=email_digest,
        source_ip_digest=source_ip_digest,
        outcome=CustomerAccountDeletionAttempt.Outcome.CREATED,
    )
    return CustomerAccountDeletionSubmission(deletion_request, raw_token)


def send_customer_account_deletion_verification(
    *, deletion_request, raw_token, verification_url
):
    deletion_request = CustomerAccountDeletionRequest.objects.get(
        pk=deletion_request.pk
    )
    if not deletion_request_is_verifiable(deletion_request, raw_token):
        raise InvalidCustomerAccountDeletion(
            "This account-deletion verification is no longer available."
        )

    context = {
        "verification_url": verification_url,
        "expires_at": deletion_request.verification_expires_at,
    }
    subject = " ".join(
        render_to_string(
            "account/email/customer_deletion_verification_subject.txt", context
        ).splitlines()
    ).strip()
    text_body = render_to_string(
        "account/email/customer_deletion_verification_message.txt", context
    ).strip()
    html_body = render_to_string(
        "account/email/customer_deletion_verification_message.html", context
    ).strip()
    message = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[deletion_request.requested_email],
        headers={
            "X-PM-TrackLinks": "None",
            "X-PM-TrackOpens": "false",
            "X-PM-Tag": "customer-account-deletion-verification",
        },
    )
    message.attach_alternative(html_body, "text/html")
    try:
        accepted_count = message.send(fail_silently=False)
        if accepted_count != 1:
            raise RuntimeError("The email backend did not accept the verification email.")
    except Exception as error:
        CustomerAccountDeletionRequest.objects.filter(pk=deletion_request.pk).update(
            verification_delivery_failed_at=timezone.now(),
            verification_delivery_error=type(error).__name__[:100],
        )
        _append_deletion_action(
            deletion_request=deletion_request,
            action=CustomerAccountDeletionAction.Action.VERIFICATION_EMAIL_FAILED,
            actor_label="Email backend",
            details={"error_type": type(error).__name__[:100]},
        )
        return False

    CustomerAccountDeletionRequest.objects.filter(pk=deletion_request.pk).update(
        verification_email_sent_at=timezone.now(),
        verification_delivery_failed_at=None,
        verification_delivery_error="",
    )
    _append_deletion_action(
        deletion_request=deletion_request,
        action=CustomerAccountDeletionAction.Action.VERIFICATION_EMAIL_ACCEPTED,
        actor_label="Email backend",
        details={"accepted_count": 1},
    )
    return True


def _revoke_user_sessions(user):
    session_keys = []
    for session in Session.objects.filter(expire_date__gt=timezone.now()).iterator():
        try:
            authenticated_user_id = session.get_decoded().get(SESSION_KEY)
        except Exception:
            continue
        if str(authenticated_user_id) == str(user.pk):
            session_keys.append(session.session_key)
    if session_keys:
        Session.objects.filter(session_key__in=session_keys).delete()
    return len(session_keys)


@transaction.atomic
def _verify_and_contain_customer_account(
    *, deletion_request_id, raw_token=None, authenticated_user=None
):
    deletion_request = (
        CustomerAccountDeletionRequest.objects.select_for_update()
        .select_related("customer__user")
        .get(pk=deletion_request_id)
    )
    user = deletion_request.customer.user
    if authenticated_user is None:
        if not deletion_request_is_verifiable(deletion_request, raw_token):
            raise InvalidCustomerAccountDeletion(
                "This account-deletion verification is no longer available."
            )
        actor = None
        actor_label = "Verified customer email"
    else:
        if authenticated_user.pk != user.pk or not authenticated_user.is_active:
            raise InvalidCustomerAccountDeletion(
                "This account is not eligible for authenticated deletion."
            )
        if deletion_request.source != deletion_request.Source.AUTHENTICATED:
            raise InvalidCustomerAccountDeletion("The deletion-request source changed.")
        actor = authenticated_user
        actor_label = "Authenticated customer"

    now = timezone.now()
    deletion_request.status = deletion_request.Status.VERIFIED
    deletion_request.verified_at = now
    deletion_request.save(update_fields=["status", "verified_at"])
    _append_deletion_action(
        deletion_request=deletion_request,
        action=CustomerAccountDeletionAction.Action.VERIFIED,
        actor=actor,
        actor_label=actor_label,
        details={"source": deletion_request.source},
    )

    revoked_sessions = _revoke_user_sessions(user)
    _append_deletion_action(
        deletion_request=deletion_request,
        action=CustomerAccountDeletionAction.Action.SESSIONS_REVOKED,
        actor=actor,
        actor_label=actor_label,
        details={"count": revoked_sessions},
    )

    removed_google_links, _ = SocialAccount.objects.filter(
        user=user,
        provider="google",
    ).delete()
    _append_deletion_action(
        deletion_request=deletion_request,
        action=CustomerAccountDeletionAction.Action.GOOGLE_LINK_REMOVED,
        actor=actor,
        actor_label=actor_label,
        details={"count": removed_google_links},
    )

    CustomerInvitation.objects.filter(
        user=user,
        accepted_at__isnull=True,
        revoked_at__isnull=True,
    ).update(revoked_at=now)
    user.is_active = False
    user.save(update_fields=["is_active"])

    deletion_request.status = deletion_request.Status.CONTAINED
    deletion_request.contained_at = now
    deletion_request.owner_review_due_at = now + timedelta(
        days=settings.CUSTOMER_ACCOUNT_DELETION_OWNER_REVIEW_DAYS
    )
    deletion_request.save(
        update_fields=["status", "contained_at", "owner_review_due_at"]
    )
    _append_deletion_action(
        deletion_request=deletion_request,
        action=CustomerAccountDeletionAction.Action.CONTAINED,
        actor=actor,
        actor_label=actor_label,
        details={"login_disabled": True},
    )
    return deletion_request


@transaction.atomic
def request_authenticated_customer_account_deletion(*, user, source_ip):
    from schemes.models import Customer

    user_model = get_user_model()
    if (
        not user.is_active
        or user.role != user_model.Role.CUSTOMER
        or user.is_staff
        or user.is_superuser
    ):
        raise InvalidCustomerAccountDeletion(
            "Only an active customer can request account deletion."
        )
    customer = Customer.objects.select_for_update().get(user=user)
    existing = CustomerAccountDeletionRequest.objects.filter(
        customer=customer,
        status__in=CustomerAccountDeletionRequest.OPEN_STATUSES,
    ).first()
    if existing is not None:
        raise InvalidCustomerAccountDeletion(
            "An account-deletion request is already under review."
        )

    now = timezone.now()
    raw_token = secrets.token_urlsafe(32)
    deletion_request = CustomerAccountDeletionRequest.objects.create(
        customer=customer,
        requested_email=user.email.strip().lower(),
        email_digest=_identity_digest(user.email.strip().lower()),
        source_ip_digest=_identity_digest((source_ip or "unknown").strip().lower()),
        verification_token_digest=_token_digest(raw_token),
        source=CustomerAccountDeletionRequest.Source.AUTHENTICATED,
        policy_version=settings.CUSTOMER_ACCOUNT_DELETION_POLICY_VERSION,
        verification_expires_at=now,
    )
    _append_deletion_action(
        deletion_request=deletion_request,
        action=CustomerAccountDeletionAction.Action.REQUESTED,
        actor=user,
        details={"source": "AUTHENTICATED", "replacement": False},
    )
    return _verify_and_contain_customer_account(
        deletion_request_id=deletion_request.pk,
        authenticated_user=user,
    )


def verify_and_contain_customer_account(*, deletion_request_id, raw_token):
    return _verify_and_contain_customer_account(
        deletion_request_id=deletion_request_id,
        raw_token=raw_token,
    )


def send_customer_account_deletion_notice(*, deletion_request, notice_kind):
    allowed_kinds = {"contained", "awaiting_settlement"}
    if notice_kind not in allowed_kinds:
        raise ValidationError("Unknown account-deletion notice kind.")
    context = {
        "notice_kind": notice_kind,
        "review_due_at": deletion_request.owner_review_due_at,
    }
    subject = " ".join(
        render_to_string(
            "account/email/customer_deletion_notice_subject.txt", context
        ).splitlines()
    ).strip()
    text_body = render_to_string(
        "account/email/customer_deletion_notice_message.txt", context
    ).strip()
    html_body = render_to_string(
        "account/email/customer_deletion_notice_message.html", context
    ).strip()
    message = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[deletion_request.requested_email],
        headers={
            "X-PM-TrackLinks": "None",
            "X-PM-TrackOpens": "false",
            "X-PM-Tag": "customer-account-deletion-notice",
        },
    )
    message.attach_alternative(html_body, "text/html")
    try:
        accepted_count = message.send(fail_silently=False)
        if accepted_count != 1:
            raise RuntimeError("The email backend did not accept the deletion notice.")
    except Exception as error:
        _append_deletion_action(
            deletion_request=deletion_request,
            action=CustomerAccountDeletionAction.Action.NOTICE_FAILED,
            actor_label="Email backend",
            details={"kind": notice_kind, "error_type": type(error).__name__[:100]},
        )
        return False
    _append_deletion_action(
        deletion_request=deletion_request,
        action=CustomerAccountDeletionAction.Action.NOTICE_ACCEPTED,
        actor_label="Email backend",
        details={"kind": notice_kind, "accepted_count": 1},
    )
    return True


@transaction.atomic
def record_customer_account_deletion_hold(
    *, deletion_request, actor, reason, retained_categories, review_due_at
):
    user_model = get_user_model()
    if not actor.is_active or not (
        actor.is_superuser or actor.role == user_model.Role.OWNER
    ):
        raise PermissionError("Only an active owner can review deletion requests.")
    locked = CustomerAccountDeletionRequest.objects.select_for_update().get(
        pk=deletion_request.pk
    )
    if locked.status not in {
        locked.Status.CONTAINED,
        locked.Status.AWAITING_SETTLEMENT,
    }:
        raise InvalidCustomerAccountDeletion(
            "Only a contained request can be placed under reviewed retention."
        )
    if review_due_at <= timezone.now():
        raise ValidationError("The next review must be in the future.")

    decision = CustomerAccountDeletionDecision.objects.create(
        request=locked,
        outcome=CustomerAccountDeletionDecision.Outcome.AWAITING_SETTLEMENT,
        reason=reason.strip(),
        retained_categories=retained_categories.strip(),
        review_due_at=review_due_at,
        policy_version=locked.policy_version,
        decided_by=actor,
        decided_by_label=_actor_label(actor),
    )
    locked.status = locked.Status.AWAITING_SETTLEMENT
    locked.owner_review_due_at = review_due_at
    locked.save(update_fields=["status", "owner_review_due_at"])
    _append_deletion_action(
        deletion_request=locked,
        action=CustomerAccountDeletionAction.Action.OWNER_HOLD_RECORDED,
        actor=actor,
        details={"decision_id": decision.pk},
    )
    return locked, decision
