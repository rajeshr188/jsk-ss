"""Audited, one-way archive/retirement services. No financial mutations."""
from django.core.exceptions import ValidationError
from django.db import transaction

from .catalogue_selectors import catalogue_closure_preview
from .models import PlanCatalogueClosure, SchemePlan, SchemePlanConfiguration


def require_open_catalogue_item(*, plan=None, configuration=None):
    lookup = {"plan_id": plan.pk} if plan is not None else {"configuration_id": configuration.pk}
    if PlanCatalogueClosure.objects.filter(**lookup).exists():
        raise ValidationError("This catalogue item is archived or retired. Its history remains available; create a separate offer for future use.")


@transaction.atomic
def close_catalogue_item(*, actor, reason, confirmed, expected_digest, plan_id=None, configuration_id=None):
    from .services import _validate_owner, _actor_label, record_scheme_plan_change
    from .plan_governance import PLAN_FIELDS, ensure_plan_revision

    _validate_owner(actor)
    if (plan_id is None) == (configuration_id is None):
        raise ValidationError("Choose one catalogue item.")
    if confirmed is not True or not reason or not reason.strip():
        raise ValidationError("Confirmation and an audit reason are required.")
    plan = SchemePlan.objects.select_for_update().get(pk=plan_id) if plan_id is not None else None
    configuration = (SchemePlanConfiguration.objects.select_for_update().get(pk=configuration_id)
        if configuration_id is not None else None)
    preview = catalogue_closure_preview(plan=plan, configuration=configuration)
    if preview["record"]:
        record = preview["record"]
        if record.actor_id == actor.pk and record.reason == reason.strip():
            return record, False
        raise ValidationError("This item is already archived or retired; its recorded reason cannot be changed.")
    if expected_digest != preview["expected_digest"]:
        raise ValidationError("This item or its usage changed. Reload and review before confirming.")
    if preview["blocked"]:
        raise ValidationError(preview["blocked"])
    if plan is not None:
        # Observe legacy terms before retiring; the agreement snapshot is never updated.
        ensure_plan_revision(plan=plan, actor=actor, reason="Terms observed before catalogue closure.")
        before = {field: getattr(plan, field) for field in PLAN_FIELDS}
        plan.active = plan.publicly_listed = False
        plan.full_clean()
        plan.save()
        ensure_plan_revision(plan=plan, actor=actor, reason=reason)
        record_scheme_plan_change(plan=plan, actor=actor, reason=reason, before=before)
    record = PlanCatalogueClosure.objects.create(plan=plan, configuration=configuration,
        action=preview["action"], actor=actor, actor_label=_actor_label(actor), reason=reason.strip())
    return record, True
