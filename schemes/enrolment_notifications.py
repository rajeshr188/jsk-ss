import logging
from dataclasses import dataclass

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse

from .models import SchemeEnrolmentRequest
from .selectors import get_owner_notification_emails


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EnrolmentRequestNotificationResult:
    customer_accepted: bool
    owner_accepted_count: int = 0
    owner_recipient_count: int = 0


def _absolute_url(base_url, path):
    return f"{base_url.rstrip('/')}{path}"


def _send(*, enrolment_request, event, audience, recipient, action_url):
    context = {
        "enrolment_request": enrolment_request,
        "event": event,
        "audience": audience,
        "action_url": action_url,
    }
    subject = " ".join(
        render_to_string(
            "schemes/email/enrolment_request_subject.txt",
            context,
        ).splitlines()
    ).strip()
    text_body = render_to_string(
        "schemes/email/enrolment_request_message.txt",
        context,
    )
    html_body = render_to_string(
        "schemes/email/enrolment_request_message.html",
        context,
    )
    message = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[recipient],
        headers={
            "X-PM-TrackLinks": "None",
            "X-PM-TrackOpens": "false",
            "X-PM-Tag": "scheme-enrolment-request",
        },
    )
    message.attach_alternative(html_body, "text/html")
    try:
        return message.send(fail_silently=False) == 1
    except Exception:
        logger.exception(
            "Scheme enrolment request notification failed request_id=%s event=%s audience=%s",
            enrolment_request.pk,
            event,
            audience,
        )
        return False


def send_enrolment_request_received(*, enrolment_request, base_url):
    customer_url = _absolute_url(
        base_url,
        reverse(
            "schemes:my_enrolment_request_detail",
            args=[enrolment_request.pk],
        ),
    )
    customer_accepted = _send(
        enrolment_request=enrolment_request,
        event="received",
        audience="customer",
        recipient=enrolment_request.customer.email,
        action_url=customer_url,
    )
    owner_url = _absolute_url(
        base_url,
        reverse(
            "schemes:owner_enrolment_request_detail",
            args=[enrolment_request.pk],
        ),
    )
    owner_recipients = get_owner_notification_emails()
    accepted = sum(
        _send(
            enrolment_request=enrolment_request,
            event="received",
            audience="owner",
            recipient=recipient,
            action_url=owner_url,
        )
        for recipient in owner_recipients
    )
    return EnrolmentRequestNotificationResult(
        customer_accepted=customer_accepted,
        owner_accepted_count=accepted,
        owner_recipient_count=len(owner_recipients),
    )


def send_enrolment_request_decision(*, enrolment_request, base_url):
    customer_url = _absolute_url(
        base_url,
        reverse(
            "schemes:my_enrolment_request_detail",
            args=[enrolment_request.pk],
        ),
    )
    return EnrolmentRequestNotificationResult(
        customer_accepted=_send(
            enrolment_request=enrolment_request,
            event=enrolment_request.status.lower(),
            audience="customer",
            recipient=enrolment_request.customer.email,
            action_url=customer_url,
        )
    )
