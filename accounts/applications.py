"""Explicit orchestration of a plan-first application; no payment mutations."""
import hashlib
import json
import secrets
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.urls import reverse
from django.utils import timezone
from django.utils.crypto import constant_time_compare

from .models import CustomerInvitation, CustomerRegistration, PlanApplication, PlanApplicationConfirmation
from .services import (
    _approve_registration_identity, _token_digest, _validate_registration_owner,
    send_customer_invitation, send_customer_registration_verification,
    submit_customer_registration, verify_customer_registration_email,
)
from schemes.models import MetalGrade, SchemePlan, SchemePlanOffering
from schemes.services import _normalize_requested_contribution, enroll_customer


def application_enabled():
    return settings.PUBLIC_CUSTOMER_REGISTRATION_ENABLED and settings.CUSTOMER_ENROLMENT_REQUESTS_ENABLED


def offer_snapshot(plan, grade):
    """Money is serialized as decimal strings, never JSON floats."""
    if plan.configuration_id and plan.configuration.policy_schema_version == 2:
        from .application_contracts import independent_offer_fields
        from schemes.enrolment_contracts import policy_description
        from schemes.plan_governance import plan_edit_digest
        return dict(independent_offer_fields(plan.configuration, grade),
            plan_id=plan.pk, name=plan.name, code=plan.code,
            publication_revision_id=plan.publication_revision_id, plan_digest=plan_edit_digest(plan),
            independent_terms=[list(row) for row in policy_description(plan.configuration)],
            disclosure_version=settings.CUSTOMER_ENROLMENT_REQUEST_DISCLOSURE_VERSION,
            terms_version=settings.PUBLIC_REGISTRATION_TERMS_VERSION,
            privacy_version=settings.PUBLIC_REGISTRATION_PRIVACY_VERSION)
    offer = {
        "plan_id": plan.pk, "name": plan.name, "code": plan.code,
        "amount_rule": plan.amount_rule, "frequency_rule": plan.frequency_rule,
        "fixed_amount": format(plan.fixed_contribution_amount, ".2f") if plan.fixed_contribution_amount is not None else None,
        "minimum_amount": format(plan.minimum_contribution, ".2f"),
        "maximum_amount": format(plan.maximum_contribution, ".2f") if plan.maximum_contribution is not None else None,
        "minimum_months": plan.minimum_months, "default_months": plan.default_months,
        "post_eligibility": plan.allow_contributions_after_eligibility,
        "grade_id": grade.pk, "grade_code": grade.code, "grade_name": grade.display_name,
        "metal": grade.metal, "fineness": format(grade.fineness, ".6f"),
        "disclosure_version": settings.CUSTOMER_ENROLMENT_REQUEST_DISCLOSURE_VERSION,
        "terms_version": settings.PUBLIC_REGISTRATION_TERMS_VERSION,
        "privacy_version": settings.PUBLIC_REGISTRATION_PRIVACY_VERSION,
    }
    if plan.configuration_id:
        from schemes.plan_configuration import configuration_evidence
        offer["configuration"] = configuration_evidence(plan.configuration)
        offer["publication_revision_id"] = plan.publication_revision_id
    return offer


def offer_form_digest(plan):
    """Bind confirmation to every displayed grade and current public terms."""
    if plan.configuration_id and plan.configuration.policy_schema_version == 2 and plan.configuration.accumulation == "INR_PURCHASE_CREDIT":
        offers = [offer_snapshot(plan, None)]
    else:
        offers = [offer_snapshot(plan, grade) for grade in MetalGrade.objects.filter(
            plan_offerings__plan=plan, plan_offerings__active=True,
        ).order_by("pk")]
    return hashlib.sha256(json.dumps(offers, sort_keys=True).encode()).hexdigest()


def _locked_offer(plan_id, grade_id):
    plan = SchemePlan.objects.select_for_update().get(pk=plan_id)
    from schemes.plan_publication import require_configured_offer
    require_configured_offer(plan)
    independent = bool(plan.configuration_id and plan.configuration.policy_schema_version == 2)
    if independent and plan.configuration.accumulation == "INR_PURCHASE_CREDIT":
        if grade_id is not None or not plan.active or not plan.publicly_listed:
            raise ValidationError("Select the available INR purchase-credit offer without a metal grade.")
        return plan, None
    if not independent:
        plan.full_clean()
    grade = MetalGrade.objects.get(pk=grade_id)
    offering = SchemePlanOffering.objects.select_for_update().filter(
        plan=plan, metal_grade=grade, active=True,
    ).first()
    if not plan.active or not plan.publicly_listed or offering is None:
        raise ValidationError("This offer is no longer available. Contact the showroom or choose another plan.")
    return plan, grade


def _check_preferences(plan, amount, months):
    amount = _normalize_requested_contribution(plan=plan, amount=amount)
    if plan.configuration_id and plan.configuration.policy_schema_version == 2:
        if months != plan.configuration.duration_months or (months is not None and type(months) is not int):
            raise ValidationError("Use the published duration; required payment count is a separate condition.")
        return amount
    if not isinstance(months, int) or not plan.minimum_months <= months <= 32767:
        raise ValidationError("Choose a valid duration at or above the plan minimum.")
    return amount


def _confirmation(application, *, final, plan, grade):
    previous = application.confirmations.order_by("-sequence").first()
    return PlanApplicationConfirmation.objects.create(
        application=application, sequence=previous.sequence + 1 if previous else 1,
        final=final, offer=offer_snapshot(plan, grade),
        terms_schema_version=application.terms_schema_version,
        plan_revision_id=plan.publication_revision_id if application.terms_schema_version == 2 else None,
        requested_amount=application.requested_amount, requested_months=application.requested_months,
        start_date=application.start_date,
    )


def _absolute(base_url, name, **kwargs):
    return base_url.rstrip("/") + reverse(name, kwargs=kwargs)


@transaction.atomic
def submit_plan_application(*, plan, metal_grade, amount, months, message, full_name,
                            email, mobile_number, source_ip, offer_digest, base_url):
    if not application_enabled():
        raise ValidationError("Online plan applications are currently unavailable.")
    plan, grade = _locked_offer(plan.pk, metal_grade.pk if metal_grade else None)
    if not constant_time_compare(offer_digest, offer_form_digest(plan)):
        raise ValidationError("The offer changed while this page was open. Review the refreshed terms and confirm again.")
    amount = _check_preferences(plan, amount, months)
    if len(message) > 1000:
        raise ValidationError("Keep the showroom message within 1000 characters.")
    submission = submit_customer_registration(
        full_name=full_name, email=email, mobile_number=mobile_number, address="", source_ip=source_ip,
    )
    if submission.application is None:
        return submission
    application = PlanApplication.objects.create(
        registration=submission.application, plan=plan, metal_grade=grade,
        terms_schema_version=2 if plan.configuration_id and plan.configuration.policy_schema_version == 2 else 1,
        requested_amount=amount, requested_months=months, customer_message=message.strip(),
        expires_at=timezone.now() + timedelta(days=settings.CUSTOMER_ENROLMENT_REQUEST_EXPIRY_DAYS),
    )
    _confirmation(application, final=False, plan=plan, grade=grade)
    url = _absolute(base_url, "customer_registration_verify", application_id=submission.application.pk, token=submission.raw_token)
    transaction.on_commit(lambda: _send_verification(submission.application, submission.raw_token, url))
    return submission


def _send_verification(registration, raw_token, url):
    try:
        send_customer_registration_verification(application=registration, raw_token=raw_token, verification_url=url)
    except Exception as error:
        CustomerRegistration.objects.filter(
            pk=registration.pk, email_token_digest=_token_digest(raw_token), email_sent_at__isnull=True,
        ).update(delivery_failed_at=timezone.now(), delivery_error=type(error).__name__[:100])


def send_progress_access(*, application_id, raw_token, base_url):
    application = PlanApplication.objects.select_related("registration").get(pk=application_id)
    if not progress_token_available(application, raw_token):
        return False
    url = _absolute(base_url, "plan_application_access", application_id=application.registration_id, token=raw_token)
    confirmed = application.confirmed_offer
    terms_summary = ""
    if application.terms_schema_version == 2:
        terms_summary = (f"\nRecorded request: {confirmed.get('name', '')}; {confirmed.get('grade_name', '')}; "
            f"requested amount INR {application.requested_amount:.2f}.\n" +
            "\n".join(f"{label}: {value}" for label, value in confirmed.get("independent_terms", ())) + "\n")
    message = EmailMultiAlternatives(
        subject="Continue your Jai Sri Krishna Jewellery plan application",
        body=("Your email is verified. Use this private link to complete your details or check "
              f"your plan application progress:\n\n{url}\n\n"
              f"This access expires on {timezone.localtime(application.expires_at):%d %b %Y, %H:%M %Z}. "
              "The request does not enable payments before showroom approval and login setup." + terms_summary),
        from_email=settings.DEFAULT_FROM_EMAIL, to=[application.registration.email],
        headers={"X-PM-TrackLinks": "None", "X-PM-TrackOpens": "false", "X-PM-Tag": "plan-application-progress"},
    )
    try:
        if message.send(fail_silently=False) != 1:
            raise RuntimeError("Email backend did not accept progress access.")
    except Exception as error:
        PlanApplication.objects.filter(pk=application.pk).update(
            progress_delivery_failed_at=timezone.now(), progress_delivery_error=type(error).__name__[:100],
        )
        return False
    PlanApplication.objects.filter(pk=application.pk).update(
        progress_sent_at=timezone.now(), progress_delivery_failed_at=None, progress_delivery_error="",
    )
    return True


def progress_identity_available(application):
    user = application.registration.approved_user
    return user is None or (user.is_active and user.role == "CUSTOMER" and user.privacy_erased_at is None)


def progress_token_available(application, raw_token):
    return bool(raw_token and application.registration.email_verified_at
                and application.expires_at > timezone.now() and application.progress_token_digest
                and progress_identity_available(application)
                and constant_time_compare(application.progress_token_digest, _token_digest(raw_token)))


def _issue_progress(application, base_url):
    raw_token = secrets.token_urlsafe(32)
    application.progress_token_digest = _token_digest(raw_token)
    application.progress_sent_at = None
    application.progress_delivery_failed_at = None
    application.progress_delivery_error = ""
    application.save(update_fields=["progress_token_digest", "progress_sent_at", "progress_delivery_failed_at", "progress_delivery_error"])
    transaction.on_commit(lambda: send_progress_access(application_id=application.pk, raw_token=raw_token, base_url=base_url))
    return application


@transaction.atomic
def verify_plan_application(*, registration_id, raw_token, base_url):
    # All application mutations lock identity, then application, then offer rows.
    registration = verify_customer_registration_email(application_id=registration_id, raw_token=raw_token)
    application = PlanApplication.objects.select_for_update().select_related("registration").get(registration=registration)
    if application.expires_at <= timezone.now():
        raise ValidationError("This application has expired. Contact the showroom for help.")
    return _issue_progress(application, base_url)


@transaction.atomic
def reissue_progress_access(*, registration_id, actor, base_url):
    _validate_registration_owner(actor)
    registration = CustomerRegistration.objects.select_for_update().get(pk=registration_id)
    application = PlanApplication.objects.select_for_update().get(registration=registration)
    application.registration = registration
    if not registration.email_verified_at or application.expires_at <= timezone.now() or not progress_identity_available(application):
        raise ValidationError("Verified, unexpired application access is required.")
    return _issue_progress(application, base_url)


@transaction.atomic
def complete_plan_application(*, registration_id, access_digest, address, metal_grade, amount,
                              months, message, start_date, offer_digest):
    if not application_enabled():
        raise ValidationError("Online plan application updates are currently unavailable.")
    registration = CustomerRegistration.objects.select_for_update().get(pk=registration_id)
    application = PlanApplication.objects.select_for_update().get(registration=registration)
    if (registration.status != CustomerRegistration.Status.AWAITING_OWNER_APPROVAL
            or application.expires_at <= timezone.now()
            or not access_digest or not constant_time_compare(application.progress_token_digest or "", access_digest)):
        raise ValidationError("This application can no longer be updated with this access. Contact the showroom.")
    if len(address.strip()) < 8 or len(address) > 1000:
        raise ValidationError("Enter your complete address.")
    if start_date < timezone.localdate():
        raise ValidationError("Confirm a start date today or later.")
    plan, grade = _locked_offer(application.plan_id, metal_grade.pk if metal_grade else None)
    if not constant_time_compare(offer_digest, offer_form_digest(plan)):
        raise ValidationError("The offer changed while this page was open. Review the refreshed terms and confirm again.")
    amount = _check_preferences(plan, amount, months)
    if len(message) > 1000:
        raise ValidationError("Keep the showroom message within 1000 characters.")
    registration.address = address.strip()
    registration.save(update_fields=["address"])
    application.metal_grade = grade
    application.terms_schema_version = 2 if plan.configuration_id and plan.configuration.policy_schema_version == 2 else 1
    application.requested_amount = amount
    application.requested_months = months
    application.customer_message = message.strip()
    application.start_date = start_date
    application.completed_at = timezone.now()
    application.save()
    _confirmation(application, final=True, plan=plan, grade=grade)
    return application


def application_terms_current(application):
    # Never decide currentness from a caller's cached offer. Approval holds this row lock.
    plan = SchemePlan.objects.select_related("configuration", "publication_revision").get(pk=application.plan_id)
    from schemes.plan_publication import require_configured_offer
    try:
        require_configured_offer(plan)
        if application.terms_schema_version == 2:
            from .application_contracts import validate_independent_application
            validate_independent_application(application)
        current_offer = offer_snapshot(plan, application.metal_grade)
    except (ValidationError, ObjectDoesNotExist):
        return False
    latest = application.confirmations.order_by("-sequence").first()
    return bool(latest and latest.final and application.completed_at
                and latest.offer == current_offer
                and latest.requested_amount == application.requested_amount
                and latest.requested_months == application.requested_months
                and latest.start_date == application.start_date
                and application.start_date >= timezone.localdate()
                and plan.active and plan.publicly_listed
                and ((application.terms_schema_version == 2 and plan.configuration_id
                      and plan.configuration.accumulation == "INR_PURCHASE_CREDIT" and application.metal_grade_id is None)
                     or SchemePlanOffering.objects.filter(plan=plan, metal_grade=application.metal_grade, active=True).exists()))


def _send_activation(invitation, raw_token, base_url):
    try:
        send_customer_invitation(
            invitation=invitation, raw_token=raw_token,
            setup_url=_absolute(base_url, "customer_invitation_accept", invitation_id=invitation.pk, token=raw_token),
        )
    except Exception as error:
        # A superseded token or template failure must never roll back an approval.
        CustomerInvitation.objects.filter(pk=invitation.pk, email_sent_at__isnull=True).update(
            delivery_failed_at=timezone.now(), delivery_error=type(error).__name__[:100],
        )


@transaction.atomic
def approve_plan_application(*, registration_id, actor, mobile_verified, terms_reviewed, reason, base_url):
    _validate_registration_owner(actor)
    registration = CustomerRegistration.objects.select_for_update().get(pk=registration_id)
    application = PlanApplication.objects.select_for_update().get(registration=registration)
    if application.scheme_account_id and registration.status == CustomerRegistration.Status.APPROVED:
        return application.scheme_account, False
    if mobile_verified is not True or terms_reviewed is not True:
        raise ValidationError("Verify showroom contact and review the confirmed terms with the customer.")
    if registration.status != CustomerRegistration.Status.AWAITING_OWNER_APPROVAL:
        raise ValidationError("Email verification and a pending identity review are required.")
    if application.expires_at <= timezone.now():
        raise ValidationError("This application has expired. Do not create an agreement.")
    plan, grade = _locked_offer(application.plan_id, application.metal_grade_id)
    application.plan, application.metal_grade = plan, grade
    if not application_terms_current(application):
        raise ValidationError("Customer confirmation is missing or the offer/start date changed. Ask the customer to confirm current terms in application progress.")
    if len(registration.address.strip()) < 8:
        raise ValidationError("The customer's address must be completed before approval.")
    customer, invitation, raw_token = _approve_registration_identity(
        application=registration, reviewed_by=actor, reason=reason,
    )
    from schemes.plan_governance import plan_edit_digest
    account = enroll_customer(
        customer=customer, plan=plan, metal_grade=grade, start_date=application.start_date,
        agreed_months=application.requested_months, performed_by=actor, reason=reason,
        selected_contribution_amount=application.requested_amount,
        selected_amount_confirmed=terms_reviewed,
        expected_configuration_id=application.confirmations.order_by("-sequence").first().offer.get("configuration", {}).get("id"),
        expected_plan_digest=plan_edit_digest(plan),
    )
    application.scheme_account = account
    application.save(update_fields=["scheme_account"])
    if application.terms_schema_version == 2:
        from .application_contracts import validate_independent_application
        validate_independent_application(application)
    transaction.on_commit(lambda: _send_activation(invitation, raw_token, base_url))
    return account, True
