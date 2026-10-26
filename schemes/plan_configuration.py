"""Owner-only preparation of immutable policies, without creating financial rights."""

from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import transaction

from .models import MetalGrade, SchemePlanConfiguration
from .plan_policies import policy_from_configuration, require_operational_configuration, validate_plan_policy


CONFIGURATION_FIELDS = (
    "name", "amount_policy", "minimum_amount", "maximum_amount", "fixed_amount",
    "amount_step", "frequency_rule", "minimum_months", "default_months",
    "allow_contributions_after_eligibility", "accumulation", "instalment_policy",
    "eligibility_policy", "missed_payment_policy", "benefit_policy", "settlement_policy",
)
EDITABLE_CONFIGURATION_FIELDS = CONFIGURATION_FIELDS[:10]
SCHEDULE_CONFIGURATION_FIELDS = ("period_basis", "grace_days", "catch_up_policy", "max_extension_months")
CONFIGURATION_FIELDS += SCHEDULE_CONFIGURATION_FIELDS
INDEPENDENT_CONFIGURATION_FIELDS = (
    "policy_schema_version", "duration_months", "required_count", "benefit_percentage",
    "benefit_cap_inr", "benefit_qualification", "benefit_on_miss", "eligible_charge_definition",
)

# An approved preparation preset, not a default applied to existing configurations.
MONTHLY_COMPLETION_POLICY = {
    "instalment_policy": "MONTHLY_COMPLETION", "eligibility_policy": "CALENDAR_AND_COUNT",
    "missed_payment_policy": "EXTEND_THEN_REVIEW", "period_basis": "ANNIVERSARY",
    "grace_days": 0, "catch_up_policy": "NONE", "max_extension_months": 3,
}
AGREEMENT_CONFIGURATION_FIELDS = (
    "agreement_schema_version", "eligibility_policy_snapshot", "required_count_snapshot",
    "configuration_snapshot_id", "amount_rule_snapshot", "fixed_amount_snapshot",
    "minimum_amount_snapshot", "maximum_amount_snapshot", "contribution_step_snapshot",
    "frequency_rule_snapshot", "allow_post_eligibility_contributions_snapshot",
    "cash_bonus_percentage_snapshot", "cash_bonus_minimum_months_snapshot",
)


def configuration_evidence(configuration):
    """Serializable evidence, not an executable rules payload."""
    result = {}
    fields = CONFIGURATION_FIELDS
    if configuration.policy_schema_version == 2:
        fields += INDEPENDENT_CONFIGURATION_FIELDS
    elif configuration.policy_schema_version != 1:
        raise ValidationError("Unsupported configuration evidence schema.")
    for name in fields:
        # Preserve the exact historical evidence/digests of the calendar-only family.
        if (configuration.policy_schema_version == 1 and name in SCHEDULE_CONFIGURATION_FIELDS
                and configuration.instalment_policy == "NONE"):
            continue
        value = getattr(configuration, name)
        result[name] = format(value, ".2f") if isinstance(value, Decimal) else value
    return {"id": configuration.pk, "family_id": str(configuration.family_id),
            "version": configuration.version, **result}


def configuration_plan_values(configuration):
    """Compatibility columns; the immutable configuration remains authoritative."""
    require_operational_configuration(configuration)
    return {
        "amount_rule": "FIXED" if configuration.amount_policy == "PLAN_FIXED" else "VARIABLE",
        "fixed_contribution_amount": configuration.fixed_amount,
        "minimum_contribution": configuration.minimum_amount,
        "maximum_contribution": configuration.maximum_amount,
        # Instalment ceilings belong to period reservations, not the old calendar-month index.
        # The explicit instalment ledger enforces this family's contribution limit.
        "frequency_rule": "FLEXIBLE" if configuration.instalment_policy == "MONTHLY_COMPLETION" else configuration.frequency_rule,
        "minimum_months": configuration.minimum_months,
        "default_months": configuration.default_months,
        "allow_contributions_after_eligibility": configuration.allow_contributions_after_eligibility,
        "cash_bonus_percentage": Decimal("0.00"),
        "cash_bonus_minimum_months": 12,
    }


def configuration_draft_values(configuration):
    """Exact storage projection for preparation; never operational permission."""
    if configuration.policy_schema_version != 2:
        return configuration_plan_values(configuration)
    configuration.full_clean()
    return {
        "amount_rule": "FIXED" if configuration.amount_policy == "PLAN_FIXED" else "VARIABLE",
        "fixed_contribution_amount": configuration.fixed_amount,
        "minimum_contribution": configuration.minimum_amount,
        "maximum_contribution": configuration.maximum_amount,
        "frequency_rule": configuration.frequency_rule,
        "minimum_months": configuration.duration_months,
        "default_months": configuration.duration_months,
        "allow_contributions_after_eligibility": configuration.allow_contributions_after_eligibility,
        "cash_bonus_percentage": Decimal("0.00"),
        "cash_bonus_minimum_months": 12,
    }


@transaction.atomic
def create_configuration_version(*, values, actor, reason, previous_id=None):
    from .services import _actor_label, _validate_owner

    _validate_owner(actor)
    if not reason or not reason.strip():
        raise ValidationError("A reason is required for the configuration record.")
    if set(values) - set(CONFIGURATION_FIELDS + INDEPENDENT_CONFIGURATION_FIELDS):
        raise ValidationError("Unsupported configuration fields.")
    if any(isinstance(values.get(name), (float, bool)) for name in ("minimum_amount", "maximum_amount", "fixed_amount", "amount_step", "benefit_percentage", "benefit_cap_inr")):
        raise ValidationError("Money must use decimal input, not floating-point values.")
    provenance = {}
    if previous_id:
        previous = SchemePlanConfiguration.objects.select_for_update().get(pk=previous_id)
        if SchemePlanConfiguration.objects.filter(previous=previous).exists():
            raise ValidationError("This configuration already has a newer version. Open the latest version first.")
        provenance = {"previous": previous, "family_id": previous.family_id, "version": previous.version + 1}
    configuration = SchemePlanConfiguration(
        **values, **provenance, created_by=actor, actor_label=_actor_label(actor), reason=reason.strip(),
    )
    if configuration.policy_schema_version == 2:
        validate_plan_policy(policy_from_configuration(configuration))
    else:
        require_operational_configuration(configuration)
    configuration.save()
    return configuration


def validate_configuration_amount(configuration, amount):
    """Validate an exact amount without rounding or substituting a preference."""
    if isinstance(amount, (float, bool)):
        raise ValidationError("Use a decimal INR amount, not floating-point input.")
    try:
        selected = Decimal(amount)
        if not selected.is_finite() or selected <= 0 or selected >= Decimal("1000000000000"):
            raise ValidationError("Enter a positive INR amount within the supported range.")
        if selected != selected.quantize(Decimal("0.01")):
            raise ValidationError("INR amounts support at most two decimal places.")
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError("Enter a valid decimal INR amount.") from None
    if selected < configuration.minimum_amount or (
        configuration.maximum_amount is not None and selected > configuration.maximum_amount
    ):
        raise ValidationError("The selected amount is outside this configuration's limits.")
    if configuration.amount_policy == "PLAN_FIXED" and selected != configuration.fixed_amount:
        raise ValidationError("Use the amount fixed by the showroom.")
    if configuration.amount_step and (selected - configuration.minimum_amount) % configuration.amount_step:
        raise ValidationError("The selected amount must follow the configured increment from the minimum.")
    return selected


def agreement_snapshot_values(*, plan, selected_amount=None):
    """Resolve operational terms; caller records consent and retains activation gates."""
    result = {
        "configuration_snapshot_id": plan.configuration_id,
        "amount_rule_snapshot": plan.amount_rule,
        "fixed_amount_snapshot": plan.fixed_contribution_amount,
        "minimum_amount_snapshot": plan.minimum_contribution,
        "maximum_amount_snapshot": plan.maximum_contribution,
        "contribution_step_snapshot": None,
        "frequency_rule_snapshot": plan.frequency_rule,
        "allow_post_eligibility_contributions_snapshot": plan.allow_contributions_after_eligibility,
        "cash_bonus_percentage_snapshot": plan.cash_bonus_percentage,
        "cash_bonus_minimum_months_snapshot": plan.cash_bonus_minimum_months,
    }
    if not plan.configuration_id:
        # A legacy variable preference must never become a fixed contract silently.
        return result
    configuration = SchemePlanConfiguration.objects.get(pk=plan.configuration_id)
    configuration.full_clean()
    for field, value in configuration_plan_values(configuration).items():
        if getattr(plan, field) != value:
            raise ValidationError("Plan terms do not match the pinned configuration.")
    if configuration.amount_policy == "CUSTOMER_FIXED" and selected_amount is None:
        raise ValidationError("The customer's confirmed fixed contribution amount is required.")
    if selected_amount is not None:
        selected = validate_configuration_amount(configuration, selected_amount)
    else:
        selected = configuration.fixed_amount
    if configuration.amount_policy in {"PLAN_FIXED", "CUSTOMER_FIXED"}:
        result.update(amount_rule_snapshot="FIXED", fixed_amount_snapshot=selected,
                      minimum_amount_snapshot=selected, maximum_amount_snapshot=selected)
    else:
        result["contribution_step_snapshot"] = configuration.amount_step
    return result


def validate_agreement_configuration(account):
    """Validate frozen contract facts without consulting the plan's current offer."""
    independent = bool(account.configuration_snapshot_id and account.configuration_snapshot.policy_schema_version == 2)
    if (account.agreement_schema_version != (2 if independent else 1)
            or (not independent and (account.eligibility_policy_snapshot or account.required_count_snapshot is not None))):
        raise ValidationError("The agreement storage version must match its pinned policy.")
    if not account.configuration_snapshot_id:
        if account.contribution_step_snapshot is not None:
            raise ValidationError("An amount increment requires a recorded configuration.")
        if account.plan_revision_id and isinstance(account.plan_revision.terms, dict) and "configuration" in account.plan_revision.terms:
            raise ValidationError("The agreement is missing its recorded configuration.")
        return
    configuration = account.configuration_snapshot
    if configuration.policy_schema_version == 2:
        from .agreement_contracts import validate_independent_account_terms
        validate_independent_account_terms(account)
        return
    configuration.full_clean()
    require_operational_configuration(configuration)
    revision = account.plan_revision
    if (not revision or revision.plan_id != account.plan_id or not isinstance(revision.terms, dict)
            or revision.terms.get("configuration") != configuration_evidence(configuration)
            or not account.metal_grade_id or account.savings_mode != account.metal_grade.metal
            or account.metal_grade.code not in revision.terms.get("metal_grades", [])):
        raise ValidationError("The recorded configuration, revision and grade must agree.")
    from .eligibility import calculate_eligibility_date
    if (account.plan_name_snapshot != revision.terms.get("name")
            or account.plan_code_snapshot != revision.terms.get("code")
            or account.eligible_from != calculate_eligibility_date(start_date=account.start_date, agreed_months=account.agreed_months)):
        raise ValidationError("Agreement identity and calendar eligibility must match its recorded terms.")
    from .models import SchemePlan
    # Reconstruct only the immutable policy projection; never load current plan terms.
    projected = SchemePlan(configuration=configuration, **configuration_plan_values(configuration))
    expected = agreement_snapshot_values(plan=projected, selected_amount=account.fixed_amount_snapshot)
    if (account.agreed_months < configuration.minimum_months
            or any(getattr(account, field) != value for field, value in expected.items())):
        raise ValidationError("Agreement amounts or operational terms differ from the recorded configuration.")


def preview_configuration_agreement(*, configuration, amount, months, metal_grade, start_date=None, missed_periods=()):
    """Read-only selected terms. This is NOT customer consent or an enrolment API."""
    configuration = SchemePlanConfiguration.objects.get(pk=configuration.pk)
    configuration.full_clean()
    require_operational_configuration(configuration)
    selected = validate_configuration_amount(configuration, amount)
    if type(months) is not int or not configuration.minimum_months <= months <= 32767:
        raise ValidationError("Choose a whole-month duration at or above the configured minimum.")
    if not metal_grade or not MetalGrade.objects.filter(pk=metal_grade.pk, metal__in=["GOLD", "SILVER"]).exists():
        raise ValidationError("Select an existing exact metal grade.")
    # Reload the grade so an altered caller object cannot change preview identity.
    grade = MetalGrade.objects.get(pk=metal_grade.pk)
    fixed = configuration.amount_policy in {"PLAN_FIXED", "CUSTOMER_FIXED"}
    result = {
        "configuration": configuration_evidence(configuration),
        "amount_rule_snapshot": "FIXED" if fixed else "VARIABLE",
        "fixed_amount_snapshot": format(selected, ".2f") if fixed else None,
        "minimum_amount_snapshot": format(selected if fixed else configuration.minimum_amount, ".2f"),
        "maximum_amount_snapshot": format(selected, ".2f") if fixed else (
            format(configuration.maximum_amount, ".2f") if configuration.maximum_amount is not None else None
        ),
        "amount_step": format(configuration.amount_step, ".2f") if configuration.amount_step else None,
        "metal_grade": grade.code, "agreed_months": months,
        "settlement_policy": "FULL_ONLY", "publishable": False,
    }
    if configuration.instalment_policy == "MONTHLY_COMPLETION":
        from .instalments import AGREEMENT_TIMEZONE, preview_monthly_completion
        from django.utils import timezone
        result["schedule"] = preview_monthly_completion(
            configuration=configuration, start_date=start_date or timezone.localdate(timezone=AGREEMENT_TIMEZONE),
            agreed_months=months, amount=selected, missed_periods=missed_periods,
        )
    elif missed_periods:
        raise ValidationError("A calendar-only plan has no missed-instalment scenario.")
    return result


@transaction.atomic
def create_configured_plan_draft(*, configuration_id, name, code, metal_grades, actor, reason, description=""):
    from .plan_governance import save_scheme_plan

    configuration = SchemePlanConfiguration.objects.get(pk=configuration_id)
    # The shared service handles owner permission, plan/offer validation and audit atomically.
    return save_scheme_plan(
        values={"name": name, "code": code, "description": description, "active": False, "publicly_listed": False},
        configuration_id=configuration.pk, metal_grades=metal_grades, actor=actor, reason=reason,
    )[0]
