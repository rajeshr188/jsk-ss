import hashlib
from dataclasses import dataclass
from datetime import date

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from .models import (
    Contribution,
    Redemption,
    SchemeAccount,
    SchemeReminder,
    SchemeReminderDeliveryAttempt,
)
from .selectors import (
    get_allocation_exception_contributions,
    get_completed_redemptions_for_date,
    get_scheme_reminder_owner_emails,
    get_upcoming_eligibility_accounts,
)


@dataclass(frozen=True)
class SchemeReminderCandidate:
    kind: str
    audience: str
    recipient_email: str
    scheme_account: SchemeAccount
    event_date: date
    contribution: Contribution | None = None
    redemption: Redemption | None = None
    eligibility_lead_days: int | None = None

    @property
    def idempotency_key(self):
        identity = "|".join(
            [
                "scheme-reminder-v1",
                self.kind,
                self.audience,
                self.recipient_email.strip().lower(),
                str(self.scheme_account.pk),
                str(self.contribution.pk if self.contribution else ""),
                str(self.redemption.pk if self.redemption else ""),
                str(self.eligibility_lead_days or ""),
                self.event_date.isoformat(),
            ]
        )
        return hashlib.sha256(identity.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class SchemeReminderPlan:
    candidates: tuple[SchemeReminderCandidate, ...]
    owner_recipient_count: int
    invalid_customer_recipient_count: int


@dataclass(frozen=True)
class SchemeReminderDeliveryResult:
    reminder: SchemeReminder
    outcome: str


def _customer_recipient(scheme_account):
    customer = scheme_account.customer
    user = customer.user
    customer_email = customer.email.strip().lower()
    user_email = user.email.strip().lower()
    if not user.is_active or not customer_email or customer_email != user_email:
        return None
    return customer_email


def _candidate(
    *,
    kind,
    audience,
    recipient_email,
    scheme_account,
    event_date,
    contribution=None,
    redemption=None,
    eligibility_lead_days=None,
):
    return SchemeReminderCandidate(
        kind=kind,
        audience=audience,
        recipient_email=recipient_email,
        scheme_account=scheme_account,
        event_date=event_date,
        contribution=contribution,
        redemption=redemption,
        eligibility_lead_days=eligibility_lead_days,
    )


def build_scheme_reminder_plan(*, as_of):
    owner_emails = get_scheme_reminder_owner_emails()
    candidates = []
    invalid_customer_recipients = 0

    if (
        settings.SCHEME_REMINDER_CUSTOMER_ELIGIBILITY
        or settings.SCHEME_REMINDER_OWNER_ELIGIBILITY
    ):
        accounts = get_upcoming_eligibility_accounts(
            as_of=as_of,
            lead_days=settings.SCHEME_REMINDER_ELIGIBILITY_DAYS,
        )
        for account in accounts:
            lead_days = (account.eligible_from - as_of).days
            if settings.SCHEME_REMINDER_CUSTOMER_ELIGIBILITY:
                recipient = _customer_recipient(account)
                if recipient:
                    candidates.append(
                        _candidate(
                            kind=SchemeReminder.Kind.UPCOMING_ELIGIBILITY,
                            audience=SchemeReminder.Audience.CUSTOMER,
                            recipient_email=recipient,
                            scheme_account=account,
                            event_date=account.eligible_from,
                            eligibility_lead_days=lead_days,
                        )
                    )
                else:
                    invalid_customer_recipients += 1
            if settings.SCHEME_REMINDER_OWNER_ELIGIBILITY:
                for recipient in owner_emails:
                    candidates.append(
                        _candidate(
                            kind=SchemeReminder.Kind.UPCOMING_ELIGIBILITY,
                            audience=SchemeReminder.Audience.OWNER,
                            recipient_email=recipient,
                            scheme_account=account,
                            event_date=account.eligible_from,
                            eligibility_lead_days=lead_days,
                        )
                    )

    if settings.SCHEME_REMINDER_OWNER_ALLOCATION_EXCEPTIONS:
        for contribution in get_allocation_exception_contributions():
            detected_at = (
                contribution.allocation_attempted_at
                or contribution.paid_at
                or contribution.created_at
            )
            for recipient in owner_emails:
                candidates.append(
                    _candidate(
                        kind=SchemeReminder.Kind.ALLOCATION_EXCEPTION,
                        audience=SchemeReminder.Audience.OWNER,
                        recipient_email=recipient,
                        scheme_account=contribution.scheme_account,
                        contribution=contribution,
                        event_date=timezone.localdate(detected_at),
                    )
                )

    if (
        settings.SCHEME_REMINDER_CUSTOMER_REDEMPTIONS
        or settings.SCHEME_REMINDER_OWNER_REDEMPTIONS
    ):
        for redemption in get_completed_redemptions_for_date(as_of=as_of):
            account = redemption.scheme_account
            event_date = timezone.localdate(redemption.completed_at)
            if settings.SCHEME_REMINDER_CUSTOMER_REDEMPTIONS:
                recipient = _customer_recipient(account)
                if recipient:
                    candidates.append(
                        _candidate(
                            kind=SchemeReminder.Kind.COMPLETED_REDEMPTION,
                            audience=SchemeReminder.Audience.CUSTOMER,
                            recipient_email=recipient,
                            scheme_account=account,
                            redemption=redemption,
                            event_date=event_date,
                        )
                    )
                else:
                    invalid_customer_recipients += 1
            if settings.SCHEME_REMINDER_OWNER_REDEMPTIONS:
                for recipient in owner_emails:
                    candidates.append(
                        _candidate(
                            kind=SchemeReminder.Kind.COMPLETED_REDEMPTION,
                            audience=SchemeReminder.Audience.OWNER,
                            recipient_email=recipient,
                            scheme_account=account,
                            redemption=redemption,
                            event_date=event_date,
                        )
                    )

    return SchemeReminderPlan(
        candidates=tuple(candidates),
        owner_recipient_count=len(owner_emails),
        invalid_customer_recipient_count=invalid_customer_recipients,
    )


def _action_url(candidate):
    if candidate.audience == SchemeReminder.Audience.CUSTOMER:
        path = reverse(
            "schemes:my_scheme_detail",
            args=[candidate.scheme_account.scheme_number],
        )
    elif candidate.kind == SchemeReminder.Kind.UPCOMING_ELIGIBILITY:
        path = reverse("schemes:redemption_eligibility")
    elif candidate.kind == SchemeReminder.Kind.ALLOCATION_EXCEPTION:
        path = reverse("schemes:exception_queue")
    else:
        path = reverse("schemes:redemption_list")
    return f"{settings.SCHEME_REMINDER_BASE_URL}{path}"


def _build_message(candidate):
    context = {
        "audience": candidate.audience,
        "kind": candidate.kind,
        "customer_name": candidate.scheme_account.customer.full_name,
        "scheme_number": candidate.scheme_account.scheme_number,
        "eligible_from": candidate.scheme_account.eligible_from,
        "eligibility_lead_days": candidate.eligibility_lead_days,
        "contribution_id": candidate.contribution.pk if candidate.contribution else None,
        "redemption_number": (
            candidate.redemption.redemption_number if candidate.redemption else None
        ),
        "redemption_completed_at": (
            candidate.redemption.completed_at if candidate.redemption else None
        ),
        "action_url": _action_url(candidate),
    }
    subject = render_to_string(
        "schemes/email/scheme_reminder_subject.txt",
        context,
    )
    subject = " ".join(subject.splitlines()).strip()
    text_body = render_to_string(
        "schemes/email/scheme_reminder_message.txt",
        context,
    ).strip()
    html_body = render_to_string(
        "schemes/email/scheme_reminder_message.html",
        context,
    ).strip()
    message = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[candidate.recipient_email],
        headers={
            "X-PM-TrackLinks": "None",
            "X-PM-TrackOpens": "false",
            "X-PM-Tag": "scheme-reminder",
        },
    )
    message.attach_alternative(html_body, "text/html")
    return message


def reminder_candidate_state(candidate):
    reminder = SchemeReminder.objects.filter(
        idempotency_key=candidate.idempotency_key,
    ).prefetch_related(
        "delivery_attempts",
    ).first()
    if reminder is None:
        return "PENDING"
    attempts = list(reminder.delivery_attempts.all())
    if any(
        attempt.outcome == SchemeReminderDeliveryAttempt.Outcome.ACCEPTED
        for attempt in attempts
    ):
        return "ALREADY_SENT"
    if len(attempts) >= settings.SCHEME_REMINDER_RETRY_LIMIT:
        return "RETRY_EXHAUSTED"
    return "PENDING"


@transaction.atomic
def deliver_scheme_reminder(candidate):
    reminder, created = SchemeReminder.objects.get_or_create(
        idempotency_key=candidate.idempotency_key,
        defaults={
            "kind": candidate.kind,
            "audience": candidate.audience,
            "recipient_email": candidate.recipient_email,
            "scheme_account": candidate.scheme_account,
            "contribution": candidate.contribution,
            "redemption": candidate.redemption,
            "event_date": candidate.event_date,
            "eligibility_lead_days": candidate.eligibility_lead_days,
        },
    )
    reminder = SchemeReminder.objects.select_for_update().get(pk=reminder.pk)
    expected = (
        reminder.kind == candidate.kind
        and reminder.audience == candidate.audience
        and reminder.recipient_email.lower() == candidate.recipient_email.lower()
        and reminder.scheme_account_id == candidate.scheme_account.pk
        and reminder.contribution_id
        == (candidate.contribution.pk if candidate.contribution else None)
        and reminder.redemption_id
        == (candidate.redemption.pk if candidate.redemption else None)
        and reminder.event_date == candidate.event_date
        and reminder.eligibility_lead_days == candidate.eligibility_lead_days
    )
    if not expected:
        raise ValidationError("The reminder idempotency identity is inconsistent.")
    if created:
        reminder.full_clean()

    attempts = list(reminder.delivery_attempts.all())
    if any(
        attempt.outcome == SchemeReminderDeliveryAttempt.Outcome.ACCEPTED
        for attempt in attempts
    ):
        return SchemeReminderDeliveryResult(reminder=reminder, outcome="ALREADY_SENT")
    if len(attempts) >= settings.SCHEME_REMINDER_RETRY_LIMIT:
        return SchemeReminderDeliveryResult(
            reminder=reminder,
            outcome="RETRY_EXHAUSTED",
        )

    message = _build_message(candidate)
    try:
        accepted_count = message.send(fail_silently=False)
        if accepted_count != 1:
            raise RuntimeError("The email backend did not accept the reminder.")
    except Exception as error:
        attempt = SchemeReminderDeliveryAttempt(
            reminder=reminder,
            outcome=SchemeReminderDeliveryAttempt.Outcome.FAILED,
            backend=settings.EMAIL_BACKEND,
            accepted_count=0,
            error_code=type(error).__name__[:100],
        )
        attempt.full_clean()
        attempt.save()
        return SchemeReminderDeliveryResult(reminder=reminder, outcome="FAILED")

    attempt = SchemeReminderDeliveryAttempt(
        reminder=reminder,
        outcome=SchemeReminderDeliveryAttempt.Outcome.ACCEPTED,
        backend=settings.EMAIL_BACKEND,
        accepted_count=accepted_count,
        error_code="",
    )
    attempt.full_clean()
    attempt.save()
    return SchemeReminderDeliveryResult(reminder=reminder, outcome="SENT")
