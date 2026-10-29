"""Typed builder-v1 compatibility rules, not an executable or financial rules engine.

Design validity is deliberately separate from operational support. No policy here
creates an entitlement, qualifies a payment, or authorises publication by itself.
Existing persisted configuration evidence remains unchanged.
"""

from dataclasses import dataclass
from decimal import Decimal

from django.core.exceptions import ValidationError


@dataclass(frozen=True, kw_only=True)
class PlanPolicy:
    accumulation: str
    amount_policy: str
    obligation: str
    payment_limit: str
    eligibility: str
    period_basis: str | None = None
    duration_months: int | None = None
    required_count: int | None = None
    missed_outcome: str = "NONE"
    extension_periods: int | None = None
    benefit_kind: str = "NONE"
    benefit_percentage: Decimal | None = None
    benefit_cap_inr: Decimal | None = None
    benefit_qualification: str = "NONE"
    benefit_on_miss: str = "NONE"
    eligible_charge_definition: str = ""
    allow_post_eligibility: bool = False
    settlement: str = "FULL_ONLY"
    grace_days: int = 0
    catch_up: str = "NONE"
    # Version of this typed vocabulary, distinct from the persisted row's encoding.
    schema_version: int = 1


CHOICES = {
    "accumulation": {"EXACT_METAL", "INR_PURCHASE_CREDIT"},
    "amount_policy": {"PLAN_FIXED", "CUSTOMER_FIXED", "VARIABLE"},
    "obligation": {"OPTIONAL", "REQUIRED_MONTHLY"},
    "payment_limit": {"FLEXIBLE", "ONCE_PER_PERIOD"},
    "eligibility": {"DURATION", "COUNT", "DURATION_AND_COUNT", "ANYTIME"},
    "period_basis": {None, "CALENDAR_MONTH", "ANNIVERSARY"},
    "missed_outcome": {"NONE", "EXTEND_THEN_REVIEW", "LOSE_UNEARNED_BENEFIT"},
    "benefit_kind": {"NONE", "INR_PURCHASE_BONUS", "VA_DISCOUNT"},
    "benefit_qualification": {"NONE", "NORMAL_ELIGIBILITY", "REQUIRED_SCHEDULE"},
    "benefit_on_miss": {"NONE", "PRESERVE_ON_COMPLETION", "DISQUALIFY_UNEARNED"},
    "settlement": {"FULL_ONLY"},
    "catch_up": {"NONE"},
}


def validate_plan_policy(policy):
    """Reject incomplete/contradictory contracts, including forged non-form input."""
    if not isinstance(policy, PlanPolicy):
        raise ValidationError("A typed plan policy is required.")
    errors = {}
    for name, choices in CHOICES.items():
        value = getattr(policy, name)
        if (value is not None and not isinstance(value, str)) or value not in choices:
            errors[name] = "Unsupported policy choice."
    if type(policy.schema_version) is not int or policy.schema_version != 1:
        errors["schema_version"] = "Unsupported policy schema."
    if type(policy.allow_post_eligibility) is not bool:
        errors["allow_post_eligibility"] = "Choose an explicit boolean."
    if type(policy.grace_days) is not int or policy.grace_days != 0:
        errors["grace_days"] = "This contract supports zero extra grace days."
    for name in ("duration_months", "required_count", "extension_periods"):
        value = getattr(policy, name)
        if value is not None and (type(value) is not int or not 1 <= value <= 32767):
            errors[name] = "Use a positive whole number within the supported range."
    if not isinstance(policy.eligible_charge_definition, str):
        errors["eligible_charge_definition"] = "Use a charge definition, not executable rules."
    if errors:
        raise ValidationError(errors)

    needs_duration = policy.eligibility in {"DURATION", "DURATION_AND_COUNT"}
    if needs_duration != (policy.duration_months is not None):
        errors["duration_months"] = "Duration is required only for duration-based eligibility."
    required = policy.obligation == "REQUIRED_MONTHLY"
    count_based = policy.eligibility in {"COUNT", "DURATION_AND_COUNT"}
    if (policy.payment_limit == "ONCE_PER_PERIOD") != (policy.period_basis is not None):
        errors["period_basis"] = "A period ceiling needs a basis; flexible payments have none."
    if not required:
        if count_based or policy.required_count is not None:
            errors["required_count"] = "Optional payments cannot create an instalment obligation."
        if policy.missed_outcome != "NONE" or policy.extension_periods is not None:
            errors["missed_outcome"] = "An unused optional window is not a missed instalment."
        if policy.benefit_on_miss != "NONE":
            errors["benefit_on_miss"] = "Optional contributions have no missed-payment penalty."
    else:
        if policy.amount_policy == "VARIABLE":
            errors["amount_policy"] = "Required instalments need a fixed agreed amount."
        if policy.payment_limit != "ONCE_PER_PERIOD" or policy.period_basis is None:
            errors["payment_limit"] = "Required monthly payments need one qualifying payment per period."
        if policy.required_count is None:
            errors["required_count"] = "Specify the scheduled qualifying count independently."
        if policy.eligibility == "ANYTIME":
            errors["eligibility"] = "The approved anytime family has no mandatory instalments."
        if count_based:
            if policy.missed_outcome != "EXTEND_THEN_REVIEW" or policy.extension_periods != 3:
                errors["missed_outcome"] = "Count completion uses three ordinary replacements, then review."
            if policy.allow_post_eligibility:
                errors["allow_post_eligibility"] = "Stop contributions after the required count is complete."
        elif policy.eligibility == "DURATION":
            if (policy.missed_outcome != "LOSE_UNEARNED_BENEFIT"
                    or policy.extension_periods is not None or policy.benefit_kind == "NONE"
                    or policy.benefit_on_miss != "DISQUALIFY_UNEARNED"):
                errors["missed_outcome"] = "Duration-only obligations must govern a named unearned benefit."

    if policy.benefit_kind == "NONE":
        if (policy.benefit_percentage is not None or policy.benefit_cap_inr is not None
                or policy.benefit_qualification != "NONE" or policy.benefit_on_miss != "NONE"
                or policy.eligible_charge_definition):
            errors["benefit_kind"] = "A no-benefit policy cannot contain hidden benefit terms."
    else:
        for name, maximum in (("benefit_percentage", Decimal("100")),
                              ("benefit_cap_inr", Decimal("999999999999.99"))):
            value = getattr(policy, name)
            if (not isinstance(value, Decimal) or not value.is_finite()
                    or not Decimal("0") < value <= maximum
                    or value.as_tuple().exponent < -2):
                errors[name] = "Specify a positive finite Decimal with at most two decimal places."
        expected = "REQUIRED_SCHEDULE" if required else "NORMAL_ELIGIBILITY"
        if policy.benefit_qualification != expected:
            errors["benefit_qualification"] = "Explicit qualification must match the obligation."
        if required and policy.benefit_on_miss == "NONE":
            errors["benefit_on_miss"] = "Choose whether extended completion preserves the unearned benefit."
        if policy.benefit_kind == "INR_PURCHASE_BONUS":
            if policy.accumulation != "INR_PURCHASE_CREDIT":
                errors["benefit_kind"] = "An INR principal bonus cannot imply a metal valuation."
            if policy.eligible_charge_definition:
                errors["eligible_charge_definition"] = "The purchase bonus uses qualifying INR principal."
        elif not policy.eligible_charge_definition.strip():
            errors["eligible_charge_definition"] = "Define the eligible VA/making charges before publication."
    if errors:
        raise ValidationError(errors)


def operational_policy_blockers(policy):
    """The approved builder-v1 matrix has implemented workflows.

    Validate every call: publication permission, immutable agreement validation and
    financial source/fulfilment authority remain separate checks. This is not a
    switch that can disable existing agreement rights when intake is paused.
    """
    validate_plan_policy(policy)
    return ()


def _legacy_policy_blockers(policy):
    """Keep schema-1 interpretations unchanged; new dimensions require schema 2."""
    supported = (policy.accumulation == "EXACT_METAL" and policy.benefit_kind == "NONE"
        and policy.eligibility in {"DURATION", "DURATION_AND_COUNT"}
        and policy.duration_months is not None and policy.duration_months >= 12)
    if policy.obligation == "REQUIRED_MONTHLY":
        supported = supported and (policy.amount_policy == "CUSTOMER_FIXED"
            and policy.eligibility == "DURATION_AND_COUNT"
            and policy.required_count == policy.duration_months)
    else:
        supported = supported and policy.period_basis != "ANNIVERSARY"
    return () if supported else ("Use an independent configuration for these policy dimensions.",)


def require_operational_policy(policy):
    blockers = operational_policy_blockers(policy)
    if blockers:
        raise ValidationError({"policy": list(blockers)})


def policy_from_configuration(configuration):
    """Project either persisted encoding into the typed compatibility vocabulary.

    The old format derives count from chosen duration. Its template projection uses
    default duration only; runtime agreement dates/counts still use frozen terms.
    Schema 2 stores the approved independent dimensions without deriving count from duration.
    """
    schema = configuration.policy_schema_version
    if type(schema) is not int or schema not in (1, 2):
        raise ValidationError("Unsupported persisted policy schema.")
    required = configuration.instalment_policy == "MONTHLY_COMPLETION"
    if configuration.instalment_policy not in {"NONE", "MONTHLY_COMPLETION"}:
        raise ValidationError("Unsupported persisted obligation.")
    eligibility = {"CALENDAR": "DURATION", "CALENDAR_AND_COUNT": "DURATION_AND_COUNT"}
    if schema == 2:
        eligibility.update(COUNT="COUNT", ANYTIME="ANYTIME")
    limits = {"FLEXIBLE": "FLEXIBLE", "ONCE_PER_MONTH": "ONCE_PER_PERIOD",
              "ONCE_PER_PERIOD": "ONCE_PER_PERIOD"}
    if configuration.eligibility_policy not in eligibility or configuration.frequency_rule not in limits:
        raise ValidationError("Unsupported persisted eligibility or payment limit.")
    if schema == 2:
        return PlanPolicy(
            accumulation=configuration.accumulation, amount_policy=configuration.amount_policy,
            obligation="REQUIRED_MONTHLY" if required else "OPTIONAL",
            payment_limit=limits[configuration.frequency_rule], period_basis=configuration.period_basis,
            eligibility=eligibility[configuration.eligibility_policy], duration_months=configuration.duration_months,
            required_count=configuration.required_count, missed_outcome=configuration.missed_payment_policy,
            extension_periods=configuration.max_extension_months, benefit_kind=configuration.benefit_policy,
            benefit_percentage=configuration.benefit_percentage, benefit_cap_inr=configuration.benefit_cap_inr,
            benefit_qualification=configuration.benefit_qualification, benefit_on_miss=configuration.benefit_on_miss,
            eligible_charge_definition=configuration.eligible_charge_definition,
            settlement=configuration.settlement_policy, allow_post_eligibility=configuration.allow_contributions_after_eligibility,
            grace_days=configuration.grace_days, catch_up=configuration.catch_up_policy,
        )
    return PlanPolicy(
        accumulation=configuration.accumulation, amount_policy=configuration.amount_policy,
        obligation="REQUIRED_MONTHLY" if required else "OPTIONAL",
        payment_limit=limits[configuration.frequency_rule],
        period_basis=(configuration.period_basis if required else
                      ("CALENDAR_MONTH" if configuration.frequency_rule == "ONCE_PER_MONTH" else None)),
        eligibility=eligibility[configuration.eligibility_policy],
        duration_months=configuration.default_months,
        required_count=configuration.default_months if required else None,
        missed_outcome=configuration.missed_payment_policy,
        extension_periods=configuration.max_extension_months if required else None,
        benefit_kind=configuration.benefit_policy,
        settlement=configuration.settlement_policy,
        allow_post_eligibility=configuration.allow_contributions_after_eligibility,
        grace_days=configuration.grace_days if required else 0,
        catch_up=configuration.catch_up_policy if required else "NONE",
    )


def require_operational_configuration(configuration):
    """Require an implemented encoding and validated compatible financial policy."""
    policy = policy_from_configuration(configuration)
    require_operational_policy(policy)
    if configuration.policy_schema_version == 1:
        blockers = _legacy_policy_blockers(policy)
        if blockers:
            raise ValidationError({"policy": list(blockers)})


def require_current_payment_workflow(account):
    """Validate denomination/encoding without tying existing rights to intake."""
    configuration = account.configuration_snapshot if account.configuration_snapshot_id else None
    if configuration:
        if account.agreement_schema_version != configuration.policy_schema_version:
            raise ValidationError("The agreement encoding must match its recorded configuration.")
        require_operational_configuration(configuration)
        expected_inr = configuration.accumulation == "INR_PURCHASE_CREDIT"
        if expected_inr != (account.savings_mode == "INR_CREDIT"):
            raise ValidationError("The agreement denomination must match its recorded configuration.")
        if not expected_inr and account.savings_mode not in {"GOLD", "SILVER"}:
            raise ValidationError("An exact-metal configuration requires a metal agreement.")
    elif account.agreement_schema_version == 2 or account.savings_mode == "INR_CREDIT":
        raise ValidationError("Independent and INR agreements require their recorded configuration.")
