"""Explicit owner-operated account minimization, not financial erasure."""

import secrets
from datetime import date, datetime, time, timedelta

from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.db.models import Q
from django.template.loader import render_to_string
from django.utils import timezone

from .models import (
    CustomerAccountDeletionAction as Action,
    CustomerAccountDeletionDecision as Decision,
    CustomerAccountDeletionNotice as Notice,
    CustomerAccountDeletionRequest as Request,
    CustomerInvitation,
    CustomerRegistration,
)
from .services import _append_deletion_action, _revoke_user_sessions


RETENTION_CATEGORIES = (
    ("financial", "Scheme, payment, settlement and financial audit history"),
    ("profile", "Necessary showroom identity/contact fields"),
    ("privacy", "Consent, privacy decisions and temporary notice delivery address"),
    ("providers", "Postmark, Google, Razorpay and support mailbox copies"),
    ("logs", "Application, Caddy and Cloudflare logs"),
    ("exports", "Downloaded, exported and paper showroom records"),
    ("backups", "Database backups and restore suppression"),
)
PROFILE_FIELDS = ("full_name", "email", "mobile_number", "address")


def _owner(actor):
    current = get_user_model().objects.get(pk=actor.pk)
    if not current.is_active or not (current.is_superuser or current.role == "OWNER"):
        raise PermissionError("Only an active owner may complete or review deletion.")
    if not current.has_usable_password():
        raise ValidationError("The reviewing owner needs a usable password for recent local reauthentication.")
    if not settings.CUSTOMER_ACCOUNT_DELETION_ENABLED:
        raise ValidationError("Account deletion is disabled.")
    return current


def validate_retention_plan(rows):
    """Validate shape only: these owner statements are not legal certification."""
    if not isinstance(rows, list) or len(rows) != len(RETENTION_CATEGORIES):
        raise ValidationError("Review every retention category exactly once.")
    cleaned = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValidationError("Invalid retention category.")
        item = {}
        for key in ("category", "treatment", "purpose", "fields", "period_start", "period_or_condition", "review_on"):
            value = row.get(key)
            if not isinstance(value, str) or not value.strip() or len(value) > 1500:
                raise ValidationError("Every category needs a purpose, fields, start event, period/condition and review date.")
            item[key] = value.strip()
        if item["treatment"] not in {"RETAIN", "NOT_APPLICABLE"}:
            raise ValidationError("Choose retain or not applicable, with an explanation.")
        try:
            review_date = date.fromisoformat(item["review_on"])
        except ValueError:
            raise ValidationError("Use an ISO review date (YYYY-MM-DD).") from None
        if not timezone.localdate() < review_date <= timezone.localdate() + timedelta(days=365):
            raise ValidationError("Schedule the next review tomorrow or within 365 days; this is a review limit, not a legal retention period.")
        cleaned.append(item)
    if {r["category"] for r in cleaned} != {key for key, label in RETENTION_CATEGORIES}:
        raise ValidationError("Review every retention category exactly once.")
    if next(r for r in cleaned if r["category"] == "privacy")["treatment"] != "RETAIN":
        raise ValidationError("Minimum privacy/consent evidence and temporary notice delivery must be disclosed as retained.")
    return cleaned


def _review_due(rows):
    earliest = min(date.fromisoformat(r["review_on"]) for r in rows)
    return timezone.make_aware(datetime.combine(earliest, time(9)))


def _text(value, label):
    if not isinstance(value, str) or not value.strip() or len(value) > 3000:
        raise ValidationError(f"Enter {label}, without unnecessary personal information.")
    return value.strip()


@transaction.atomic
def complete_customer_account_deletion(
    *, request_id, actor, retention_plan, retain_profile_fields,
    reason, external_review, confirmation,
):
    from schemes.models import Customer, Contribution, SchemeAccount, SchemeEnrolmentRequest
    from .selectors import customer_account_deletion_disposition

    actor = _owner(actor)
    # Serialize against owner enrolment and all financial operations on agreements.
    customer_id = Request.objects.values_list("customer_id", flat=True).get(pk=request_id)
    customer = Customer.objects.select_for_update().get(pk=customer_id)
    user = get_user_model().objects.select_for_update().get(pk=customer.user_id)
    locked = Request.objects.select_for_update().get(pk=request_id)
    if locked.status == Request.Status.COMPLETED_WITH_RETENTION:
        return locked, Decision.objects.get(request=locked, outcome="COMPLETED_WITH_RETENTION")
    if locked.status not in {Request.Status.CONTAINED, Request.Status.AWAITING_SETTLEMENT}:
        raise ValidationError("Only a verified, contained request can be completed.")
    if confirmation != str(locked.pk):
        raise ValidationError("Confirm the exact request identifier before removing data.")
    if user.is_active or user.is_staff or user.is_superuser or user.role != "CUSTOMER" or user.privacy_erased_at:
        raise ValidationError("Customer containment/role integrity needs review.")
    rows = validate_retention_plan(retention_plan)
    reason = _text(reason, "the completion reason")
    external_review = _text(external_review, "the external review evidence and remaining follow-ups")
    if not isinstance(retain_profile_fields, (list, tuple)) or not set(retain_profile_fields) <= set(PROFILE_FIELDS):
        raise ValidationError("Select only supported profile fields for retention.")
    retained = sorted(set(retain_profile_fields))
    accounts = list(SchemeAccount.objects.select_for_update().filter(customer=customer).order_by("pk"))
    contributions = Contribution.objects.filter(scheme_account__in=accounts)
    list(contributions.select_for_update().order_by("pk"))
    enrolments = SchemeEnrolmentRequest.objects.select_for_update().filter(customer=customer)
    if enrolments.filter(status="PENDING_OWNER_REVIEW").exists():
        raise ValidationError("Close or review the pending enrolment request before completion.")
    if contributions.filter(status__in=["PENDING", "PAID_UNALLOCATED"]).exists():
        raise ValidationError("Reconcile pending payments and unallocated entitlements before completion.")
    preview = customer_account_deletion_disposition(locked)
    if preview.allocation_exceptions or preview.unresolved_webhooks:
        raise ValidationError("Financial exceptions need review before completion.")
    has_history = preview.has_financial_history
    by_category = {r["category"]: r for r in rows}
    if has_history and by_category["financial"]["treatment"] != "RETAIN":
        raise ValidationError("Financial/agreement history must be retained in this release.")
    if bool(retained) != (by_category["profile"]["treatment"] == "RETAIN"):
        raise ValidationError("The profile retention category must match the selected fields.")
    outstanding = any(
        b.cash_principal != 0 or b.cash_earned_bonus != 0 or b.metal_quantity != 0
        for b in preview.account_balances
    )
    open_agreements = any(a.status != "REDEEMED" for a in accounts)
    if (outstanding or open_agreements) and not {"full_name", "email"} <= set(retained):
        raise ValidationError("Keep the showroom name and email for open agreements/entitlements, with a documented settlement purpose.")
    original_email = locked.requested_email
    # Do not guess that an email match authorizes changing another application.
    ambiguous = CustomerRegistration.objects.filter(
        Q(email__iexact=original_email) | Q(email__iexact=customer.email),
    ).exclude(approved_user=user)
    if ambiguous.exists():
        raise ValidationError("Other email-matched applications need separate identity/disposition review.")
    tombstone = f"deleted-{secrets.token_hex(16)}"
    tombstone_email = f"{tombstone}@deleted.invalid"
    disposition = {
        "version": 1, "retention_plan": rows, "retain_profile_fields": retained,
        "external_review": external_review,
        "removed": ["login credentials and email bindings", "social links/tokens", "invitations", "sessions", "unneeded profile and linked registration identity"],
        "financial_history_unchanged": True,
    }
    decision = Decision.objects.create(
        request=locked, outcome="COMPLETED_WITH_RETENTION", reason=reason,
        retained_categories="; ".join(dict(RETENTION_CATEGORIES)[r["category"]] for r in rows if r["treatment"] == "RETAIN"),
        disposition=disposition, review_due_at=_review_due(rows),
        policy_version=locked.policy_version, decided_by=actor,
        decided_by_label=actor.email or actor.username,
    )
    _revoke_user_sessions(user)
    SocialAccount.objects.filter(user=user).delete()
    EmailAddress.objects.filter(user=user).delete()
    CustomerInvitation.objects.filter(user=user).delete()
    user.groups.clear()
    user.user_permissions.clear()
    user.email = tombstone_email
    user.username = tombstone
    user.first_name = user.last_name = ""
    user.last_login = None
    user.set_unusable_password()
    user.privacy_erased_at = timezone.now()
    user.save()
    for field in PROFILE_FIELDS:
        if field not in retained:
            setattr(customer, field, tombstone_email if field == "email" else "Removed customer" if field == "full_name" else "")
    Customer.objects.filter(pk=customer.pk).update(
        **{field: getattr(customer, field) for field in PROFILE_FIELDS},
        updated_at=timezone.now(),
    )
    CustomerRegistration.objects.filter(approved_user=user).update(
        full_name="Removed customer", email=tombstone_email, mobile_number="", address="",
        source_ip_digest="", review_reason="Identity minimized under verified account deletion.",
        delivery_error="",
    )
    # Explicit identity minimization, not a change to historical outcomes/times.
    Request.objects.filter(customer=customer).update(
        requested_email=tombstone_email, email_digest="", source_ip_digest="",
        verification_delivery_error="",
    )
    Action.objects.filter(request__customer=customer, actor=user).update(actor_label="Removed customer")
    locked.requested_email = tombstone_email
    locked.status = Request.Status.COMPLETED_WITH_RETENTION
    locked.closed_at = timezone.now()
    locked.owner_review_due_at = decision.review_due_at
    locked.save(update_fields=["status", "closed_at", "owner_review_due_at"])
    for action in [Action.Action.DATA_MINIMIZED, Action.Action.COMPLETED_WITH_RETENTION]:
        _append_deletion_action(deletion_request=locked, action=action, actor=actor, details={"decision_id": decision.pk})
    Notice.objects.create(decision=decision, recipient_email=original_email)
    return locked, decision


@transaction.atomic
def send_completion_notice(*, notice_id, actor):
    """Manual serialized retries; SMTP acceptance is not exactly-once delivery.

    Sending occurs only after the separate minimization transaction has committed.
    A crash after SMTP acceptance may require a duplicate retry; never re-erase.
    """
    _owner(actor)
    notice = Notice.objects.select_for_update(of=("self",)).select_related("decision__request").get(pk=notice_id)
    if notice.accepted_at:
        return True
    decision = notice.decision
    context = {"decision": decision, "retention_plan": decision.disposition["retention_plan"]}
    message = EmailMultiAlternatives(
        subject=("Your retained-record review" if decision.outcome == "RETENTION_REVIEW" else "Your account deletion outcome") + " — Jai Sri Krishna Jewellery",
        body=render_to_string("account/email/customer_deletion_completion.txt", context),
        from_email=settings.DEFAULT_FROM_EMAIL, to=[notice.recipient_email],
        headers={"X-PM-TrackLinks": "None", "X-PM-TrackOpens": "false", "X-PM-Tag": "customer-deletion-completion"},
    )
    notice.attempts += 1
    notice.last_attempt_at = timezone.now()
    try:
        if message.send(fail_silently=False) != 1:
            raise RuntimeError("Backend did not accept notice")
    except Exception:
        notice.last_error = "Email delivery not confirmed; review and retry."
        action = Action.Action.NOTICE_FAILED
    else:
        notice.accepted_at = timezone.now()
        notice.recipient_email = ""
        notice.last_error = ""
        action = Action.Action.NOTICE_ACCEPTED
    notice.save()
    _append_deletion_action(
        deletion_request=decision.request, action=action, actor=actor,
        details={"kind": "completion", "notice_id": notice.pk, "attempt": notice.attempts},
    )
    return notice.accepted_at is not None


@transaction.atomic
def review_customer_account_retention(
    *, request_id, actor, retention_plan, retain_profile_fields,
    reason, external_review, confirmation,
):
    from schemes.models import Customer, Contribution, SchemeAccount
    from .selectors import customer_account_deletion_disposition

    actor = _owner(actor)
    customer_id = Request.objects.values_list("customer_id", flat=True).get(pk=request_id)
    customer = Customer.objects.select_for_update().get(pk=customer_id)
    user = get_user_model().objects.select_for_update().get(pk=customer.user_id)
    locked = Request.objects.select_for_update().get(pk=request_id)
    if locked.status != "COMPLETED_WITH_RETENTION" or not user.privacy_erased_at:
        raise ValidationError("Only a completed, minimized account can receive a retention review.")
    if confirmation != str(locked.pk):
        raise ValidationError("Confirm the exact request identifier.")
    previous = locked.decisions.exclude(outcome="AWAITING_SETTLEMENT").first()
    if not isinstance(retain_profile_fields, (list, tuple)):
        raise ValidationError("Select supported profile fields for retention.")
    retained = sorted(set(retain_profile_fields))
    if not set(retained) <= set(previous.disposition["retain_profile_fields"]):
        raise ValidationError("A review may remove retained fields, never restore erased identity.")
    rows = validate_retention_plan(retention_plan)
    reason = _text(reason, "the review reason")
    external_review = _text(external_review, "external review evidence and remaining follow-ups")
    accounts = list(SchemeAccount.objects.select_for_update().filter(customer=customer).order_by("pk"))
    contributions = Contribution.objects.filter(scheme_account__in=accounts)
    list(contributions.select_for_update().order_by("pk"))
    preview = customer_account_deletion_disposition(locked)
    by_category = {r["category"]: r for r in rows}
    if preview.has_financial_history and by_category["financial"]["treatment"] != "RETAIN":
        raise ValidationError("Financial history destruction is not supported by this workflow.")
    if bool(retained) != (by_category["profile"]["treatment"] == "RETAIN"):
        raise ValidationError("The profile category must match the selected retained fields.")
    if set(retained) != set(previous.disposition["retain_profile_fields"]):
        if contributions.filter(status__in=["PENDING", "PAID_UNALLOCATED"]).exists() or preview.allocation_exceptions or preview.unresolved_webhooks:
            raise ValidationError("Resolve financial exceptions before further profile removal.")
        outstanding = any(
            b.cash_principal != 0 or b.cash_earned_bonus != 0 or b.metal_quantity != 0
            for b in preview.account_balances
        )
        if (outstanding or any(a.status != "REDEEMED" for a in accounts)) and not {"full_name", "email"} <= set(retained):
            raise ValidationError("Keep the showroom name and email until the open entitlement/agreement is resolved.")
    disposition = {**previous.disposition, "retention_plan": rows, "retain_profile_fields": retained, "external_review": external_review}
    if disposition == previous.disposition and reason == previous.reason:
        return locked, previous
    # Use only an already-lawfully-retained contact route. Never recover one from backups.
    recipient = customer.email if "email" in previous.disposition["retain_profile_fields"] else ""
    decision = Decision.objects.create(
        request=locked, outcome="RETENTION_REVIEW", reason=reason,
        retained_categories="; ".join(dict(RETENTION_CATEGORIES)[r["category"]] for r in rows if r["treatment"] == "RETAIN"),
        disposition=disposition, review_due_at=_review_due(rows),
        policy_version=locked.policy_version, decided_by=actor, decided_by_label=actor.email or actor.username,
    )
    removed = set(previous.disposition["retain_profile_fields"]) - set(retained)
    if removed:
        Customer.objects.filter(pk=customer.pk).update(**{
            field: user.email if field == "email" else "Removed customer" if field == "full_name" else ""
            for field in removed
        }, updated_at=timezone.now())
    locked.owner_review_due_at = decision.review_due_at
    locked.save(update_fields=["owner_review_due_at"])
    _append_deletion_action(
        deletion_request=locked, action=Action.Action.RETENTION_REVIEWED, actor=actor,
        details={"decision_id": decision.pk, "removed_profile_fields": sorted(removed), "notice_queued": bool(recipient)},
    )
    if recipient:
        Notice.objects.create(decision=decision, recipient_email=recipient)
    return locked, decision
