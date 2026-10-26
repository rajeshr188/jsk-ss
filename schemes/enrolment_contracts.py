"""Read-only request terms and presentation; never publication or payment authority."""
import re

from django.core.exceptions import ValidationError
from django.utils import timezone

from .agreement_contracts import resolve_independent_agreement_terms, validate_independent_account_terms
from .instalments import AGREEMENT_TIMEZONE
from .plan_configuration import configuration_evidence
from .plan_policies import policy_from_configuration


def independent_request_values(*, configuration_id, metal_grade_id, amount, months):
    terms = resolve_independent_agreement_terms(configuration_id=configuration_id,
        start_date=timezone.localdate(timezone=AGREEMENT_TIMEZONE),
        selected_amount=amount, metal_grade_id=metal_grade_id)
    if months != terms.policy.duration_months or (months is not None and type(months) is not int):
        raise ValidationError("Use the plan's exact duration; required count is not a duration.")
    return dict(request_schema_version=2, savings_mode_snapshot=terms.savings_mode,
        eligibility_policy_snapshot=terms.policy.eligibility, required_count_snapshot=terms.policy.required_count,
        requested_months=terms.policy.duration_months, amount_rule_snapshot=terms.amount_rule,
        frequency_rule_snapshot=terms.policy.payment_limit, fixed_contribution_amount_snapshot=terms.fixed_amount,
        minimum_contribution_snapshot=terms.minimum_amount, maximum_contribution_snapshot=terms.maximum_amount,
        minimum_months_snapshot=terms.policy.duration_months, default_months_snapshot=terms.policy.duration_months,
        allow_post_eligibility_contributions_snapshot=terms.policy.allow_post_eligibility)


def validate_request_terms(request):
    from .models import SchemePlanRevision
    if not request.configuration_snapshot_id or not request.plan_revision_snapshot_id:
        raise ValidationError("Independent requests require their configuration and publication revision.")
    expected = independent_request_values(configuration_id=request.configuration_snapshot_id,
        metal_grade_id=request.metal_grade_id, amount=request.requested_contribution_amount, months=request.requested_months)
    if any(getattr(request, field) != value for field, value in expected.items()):
        raise ValidationError("Request terms differ from the pinned independent policy.")
    revision = SchemePlanRevision.objects.get(pk=request.plan_revision_snapshot_id)
    evidence = revision.terms
    if (revision.plan_id != request.plan_id or not isinstance(evidence, dict)
            or evidence.get("configuration") != configuration_evidence(request.configuration_snapshot)
            or evidence.get("name") != request.plan_name_snapshot or evidence.get("code") != request.plan_code_snapshot
            or not re.fullmatch(r"[0-9a-f]{64}", request.offer_digest)):
        raise ValidationError("Request publication provenance requires review.")
    grades = evidence.get("metal_grades")
    if not isinstance(grades, list) or (request.metal_grade_id and request.metal_grade.code not in grades) or (
            request.savings_mode_snapshot == "INR_CREDIT" and grades != []):
        raise ValidationError("Request denomination differs from the pinned offer.")
    if request.scheme_account_id:
        account = request.scheme_account
        terms = validate_independent_account_terms(account)
        if (account.configuration_snapshot_id != request.configuration_snapshot_id
                or account.plan_revision_id != request.plan_revision_snapshot_id
                or terms.savings_mode != request.savings_mode_snapshot
                or account.agreed_months != request.requested_months
                or account.fixed_amount_snapshot != expected["fixed_contribution_amount_snapshot"]):
            raise ValidationError("Linked agreement differs from the customer's confirmed request.")
    return expected


def policy_description(configuration):
    """Plain, escaped template/email facts from the immutable policy, not the live plan."""
    policy = policy_from_configuration(configuration)
    rows = [("Accumulation", "INR jewellery purchase credit; no metal rate or grams" if policy.accumulation == "INR_PURCHASE_CREDIT"
             else "One agreed exact metal grade; no conversion between grades")]
    rows.append(("Amount rule", {"PLAN_FIXED": "Plan-fixed contribution amount", "CUSTOMER_FIXED": "Customer-selected amount, fixed at enrolment",
                               "VARIABLE": "Variable contributions within the recorded bounds; the requested amount is a preference"}[policy.amount_policy]))
    rows.append(("Amount bounds", f"Minimum INR {configuration.minimum_amount:.2f}; " +
        (f"maximum INR {configuration.maximum_amount:.2f}" if configuration.maximum_amount is not None else "no configured maximum") +
        (f"; increments of INR {configuration.amount_step:.2f} from the minimum" if configuration.amount_step else "")))
    rows.append(("Duration", f"{policy.duration_months} months" if policy.duration_months else "No minimum-duration condition"))
    rows.append(("Required schedule", f"{policy.required_count} qualifying monthly payments" if policy.required_count else "No mandatory instalments"))
    rows.append(("Payment limit", "Flexible contributions" if policy.payment_limit == "FLEXIBLE" else
        "At most one qualifying contribution per " + ("calendar month (India time; enrolment month counts)" if policy.period_basis == "CALENDAR_MONTH" else "agreement-anniversary month")))
    rows.append(("Normal eligibility", {"DURATION": "Agreed duration; schedule compliance for benefits is separate",
        "COUNT": "Final required payment verified and conclusively attributed; no wait for its month to end",
        "DURATION_AND_COUNT": "Required count complete and both duration and final qualifying period ended",
        "ANYTIME": "Positive verified entitlement; no maturity wait"}[policy.eligibility] + "; full settlement still needs review and customer authorization"))
    rows.append(("Missed payments", {"NONE": "Unused optional windows create no debt", "EXTEND_THEN_REVIEW": "Three ordinary replacement periods, then review; paid entitlement is retained",
        "LOSE_UNEARNED_BENEFIT": "Loss of the named unearned benefit, not principal; no silent maturity extension"}[policy.missed_outcome]))
    if policy.benefit_kind == "NONE":
        rows.append(("Benefit", "No bonus or discount"))
    else:
        base = "verified net qualifying INR principal" if policy.benefit_kind == "INR_PURCHASE_BONUS" else policy.eligible_charge_definition
        rows.append(("Conditional benefit", f"{configuration.get_benefit_policy_display()}: {policy.benefit_percentage}% of {base}, capped at INR {policy.benefit_cap_inr:.2f}; invoice-fulfilled, not cash"))
        rows.append(("Benefit qualification", "Required schedule" if policy.benefit_qualification == "REQUIRED_SCHEDULE" else "Normal eligibility"))
        if policy.benefit_on_miss != "NONE":
            rows.append(("Benefit on missed payments", "Preserved on approved extended completion" if policy.benefit_on_miss == "PRESERVE_ON_COMPLETION" else "Disqualify the unearned benefit; unresolved outages require review"))
    rows.append(("Settlement", "One final full settlement; no partial withdrawals. Request submission creates no entitlement."))
    if policy.accumulation == "INR_PURCHASE_CREDIT":
        rows.append(("Unused paid principal", "Recorded showroom invoice application and any agreed manual refund together close the full agreement; no replacement-credit voucher or automatic gateway refund. Benefits are separate and not refunded as cash."))
    return tuple(rows)
