"""Explicit plan mutations; agreement economic snapshots remain authoritative."""

import hashlib
import json
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from .models import MetalGrade, SchemePlan, SchemePlanOffering, SchemePlanRevision


PLAN_FIELDS = (
    "name", "code", "description", "minimum_months", "default_months",
    "amount_rule", "frequency_rule", "fixed_contribution_amount",
    "minimum_contribution", "maximum_contribution",
    "allow_contributions_after_eligibility", "cash_bonus_percentage",
    "cash_bonus_minimum_months", "active", "publicly_listed",
)


def plan_terms(plan):
    terms = {field: getattr(plan, field) for field in PLAN_FIELDS}
    # Match database precision, so 100 and 100.00 do not create different revisions.
    terms = {
        key: format(value, f".{plan._meta.get_field(key).decimal_places}f")
        if isinstance(value, Decimal) else value
        for key, value in terms.items()
    }
    terms["metal_grades"] = list(plan.metal_offerings.filter(active=True)
                                .order_by("metal_grade__code").values_list("metal_grade__code", flat=True))
    terms["eligibility_basis"] = "CALENDAR_MONTHS"
    if plan.configuration_id:
        from .plan_configuration import configuration_evidence
        terms["configuration"] = configuration_evidence(plan.configuration)
        if plan.configuration.policy_schema_version == 2:
            from .plan_policies import policy_from_configuration
            terms["eligibility_basis"] = policy_from_configuration(plan.configuration).eligibility
    return terms


def plan_edit_digest(plan):
    payload = {"terms": plan_terms(plan), "updated_at": plan.updated_at.isoformat()}
    if plan.configuration_id:
        payload["publication_revision_id"] = plan.publication_revision_id
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def ensure_plan_revision(*, plan, actor, reason):
    """Caller must hold the plan row lock (or have just inserted the plan)."""
    from .services import _actor_label

    terms = plan_terms(plan)
    previous = plan.revisions.first()
    if previous and previous.terms == terms:
        return previous
    revision = SchemePlanRevision(
        plan=plan, number=previous.number + 1 if previous else 1, terms=terms,
        actor=actor, actor_label=_actor_label(actor), reason=reason.strip(),
    )
    revision.full_clean()
    revision.save()
    return revision


@transaction.atomic
def save_scheme_plan(*, values, metal_grades, actor, reason, plan_id=None, expected_digest=None, configuration_id=None):
    from .services import _validate_owner, cash_scheme_activity_is_enabled, record_scheme_plan_change

    _validate_owner(actor)
    if not reason or not reason.strip():
        raise ValidationError("A reason is required for the plan audit record.")
    if set(values) - set(PLAN_FIELDS):
        raise ValidationError("Unsupported plan fields.")
    if not cash_scheme_activity_is_enabled() and any(
        field in values for field in ("cash_bonus_percentage", "cash_bonus_minimum_months")
    ):
        raise ValidationError("Legacy cash bonus terms cannot be edited in production.")
    plan = SchemePlan.objects.select_for_update().get(pk=plan_id) if plan_id else SchemePlan()
    if plan_id and plan.configuration_id:
        if plan.active or plan.publicly_listed:
            raise ValidationError("Withdraw the configured offer before editing it; existing agreements stay unchanged.")
        if values.get("active") or values.get("publicly_listed"):
            raise ValidationError("Use the audited publication review to open a configured offer.")
    if configuration_id is not None:
        if plan_id:
            raise ValidationError("Create a separate draft to use another configuration version.")
        from .models import SchemePlanConfiguration
        from .plan_configuration import configuration_plan_values
        plan.configuration = SchemePlanConfiguration.objects.get(pk=configuration_id)
        for field, value in configuration_plan_values(plan.configuration).items():
            setattr(plan, field, value)
    if plan_id and expected_digest != plan_edit_digest(plan):
        raise ValidationError("This plan changed since you opened it. Reload and review the latest terms before saving.")
    before = {field: getattr(plan, field) for field in PLAN_FIELDS}
    before["metal_grades"] = tuple(plan_terms(plan)["metal_grades"]) if plan_id else ()
    selected_ids = {grade.pk for grade in metal_grades}
    if not selected_ids or MetalGrade.objects.filter(pk__in=selected_ids).count() != len(selected_ids):
        raise ValidationError("Select at least one valid metal grade.")
    for field, value in values.items():
        setattr(plan, field, value)
    if not plan_id:
        plan.publicly_listed = False
    plan.full_clean()
    changed = not plan_id or any(before[field] != getattr(plan, field) for field in PLAN_FIELDS)
    changed = changed or set(plan.metal_offerings.filter(active=True).values_list("metal_grade_id", flat=True)) != selected_ids
    if plan_id and not changed:
        return plan, False
    # Capture the previous observed terms before the first edit of a legacy plan.
    if plan_id and not plan.revisions.exists():
        stored = SchemePlan.objects.get(pk=plan_id)
        ensure_plan_revision(plan=stored, actor=actor, reason="Legacy plan terms observed before audited edit; not historical acceptance evidence.")
    plan.save()
    for grade in MetalGrade.objects.all():
        SchemePlanOffering.objects.update_or_create(
            plan=plan, metal_grade=grade, defaults={"active": grade.pk in selected_ids},
        )
    revision = ensure_plan_revision(plan=plan, actor=actor, reason=reason)
    record_scheme_plan_change(
        plan=plan, actor=actor, reason=reason, before=before,
        after_overrides={"metal_grades": tuple(revision.terms["metal_grades"])},
    )
    return plan, True
