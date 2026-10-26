"""Read-only frozen registration-first terms; never permission to enrol or pay."""
import re

from django.core.exceptions import ValidationError

from schemes.enrolment_contracts import independent_request_values
from schemes.plan_configuration import configuration_evidence
from schemes.plan_policies import policy_from_configuration


def independent_offer_fields(configuration, grade):
    policy = policy_from_configuration(configuration)
    inr = policy.accumulation == "INR_PURCHASE_CREDIT"
    if inr != (grade is None):
        raise ValidationError("Select the offered denomination; INR credit has no metal grade.")
    return dict(
        schema_version=2, accumulation=policy.accumulation,
        amount_rule="VARIABLE" if policy.amount_policy == "VARIABLE" else "FIXED",
        frequency_rule=policy.payment_limit,
        fixed_amount=format(configuration.fixed_amount, ".2f") if configuration.fixed_amount is not None else None,
        minimum_amount=format(configuration.minimum_amount, ".2f"),
        maximum_amount=format(configuration.maximum_amount, ".2f") if configuration.maximum_amount is not None else None,
        minimum_months=policy.duration_months, default_months=policy.duration_months,
        duration_months=policy.duration_months, required_count=policy.required_count,
        eligibility=policy.eligibility, post_eligibility=policy.allow_post_eligibility,
        grade_id=grade.pk if grade else None, grade_code=grade.code if grade else None,
        grade_name=grade.display_name if grade else "INR jewellery purchase credit",
        metal=grade.metal if grade else None, fineness=format(grade.fineness, ".6f") if grade else None,
        configuration=configuration_evidence(configuration),
    )


def validate_independent_confirmation(confirmation):
    from schemes.models import MetalGrade, SchemePlanConfiguration, SchemePlanRevision
    offer = confirmation.offer
    if confirmation.terms_schema_version != 2 or not isinstance(offer, dict):
        raise ValidationError("Independent confirmation requires versioned offer evidence.")
    evidence = offer.get("configuration")
    if not isinstance(evidence, dict):
        raise ValidationError("Configuration evidence is missing.")
    if (type(evidence.get("id")) is not int or evidence["id"] <= 0
            or (offer.get("grade_id") is not None and type(offer["grade_id"]) is not int)):
        raise ValidationError("Use recorded configuration and grade identities.")
    config = SchemePlanConfiguration.objects.filter(pk=evidence.get("id")).first()
    revision = SchemePlanRevision.objects.filter(pk=confirmation.plan_revision_id).first()
    if config is None or config.policy_schema_version != 2 or revision is None:
        raise ValidationError("Independent configuration and publication revision are required.")
    grade = MetalGrade.objects.filter(pk=offer.get("grade_id")).first()
    if offer.get("grade_id") is not None and grade is None:
        raise ValidationError("The recorded grade is unavailable.")
    expected = independent_offer_fields(config, grade)
    if any(offer.get(key) != value for key, value in expected.items() if key != "grade_name"):
        raise ValidationError("Confirmation terms differ from the frozen policy.")
    independent_request_values(configuration_id=config.pk, metal_grade_id=grade.pk if grade else None,
        amount=confirmation.requested_amount, months=confirmation.requested_months)
    terms = revision.terms
    if (revision.plan_id != confirmation.application.plan_id or offer.get("plan_id") != revision.plan_id
            or offer.get("publication_revision_id") != revision.pk or not isinstance(terms, dict)
            or terms.get("configuration") != expected["configuration"]
            or terms.get("name") != offer.get("name") or terms.get("code") != offer.get("code")
            or not re.fullmatch(r"[0-9a-f]{64}", str(offer.get("plan_digest", "")))):
        raise ValidationError("The confirmed publication provenance requires review.")
    grades = terms.get("metal_grades")
    if not isinstance(grades, list) or (grade and grade.code not in grades) or (grade is None and grades != []):
        raise ValidationError("The confirmed grade differs from the published offer.")
    return config


def validate_independent_application(application):
    latest = application.confirmations.order_by("-sequence").first()
    if latest is None or latest.terms_schema_version != application.terms_schema_version:
        raise ValidationError("Application confirmation version is missing or inconsistent.")
    validate_independent_confirmation(latest)
    if (latest.offer.get("grade_id") != application.metal_grade_id
            or latest.requested_amount != application.requested_amount
            or latest.requested_months != application.requested_months
            or latest.start_date != application.start_date
            or bool(application.completed_at) != latest.final):
        raise ValidationError("Application preferences differ from the latest confirmation.")
    if application.scheme_account_id:
        from schemes.agreement_contracts import validate_independent_account_terms
        account = application.scheme_account
        validate_independent_account_terms(account)
        if (not latest.final or account.plan_revision_id != latest.plan_revision_id
                or account.configuration_snapshot_id != latest.offer["configuration"]["id"]
                or account.metal_grade_id != application.metal_grade_id
                or account.agreed_months != application.requested_months
                or account.start_date != application.start_date
                or (account.amount_rule_snapshot == "FIXED" and account.fixed_amount_snapshot != application.requested_amount)):
            raise ValidationError("The agreement differs from the customer's final confirmation.")
    return latest
