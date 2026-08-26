import hashlib
import secrets
from datetime import timedelta

from allauth.account.models import EmailAddress
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.crypto import constant_time_compare

from .models import CustomerInvitation


class InvalidCustomerInvitation(ValidationError):
    pass


def _actor_label(actor):
    return actor.email or actor.username or f"User {actor.pk}"


def _token_digest(raw_token):
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


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
