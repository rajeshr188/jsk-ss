"""Controlled publication of supported offers; never rewrite accepted agreements."""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction

from .models import SchemePlan
from .plan_governance import PLAN_FIELDS, ensure_plan_revision, plan_edit_digest, plan_terms
from .plan_policies import require_operational_configuration


def validate_publication_evidence(plan):
    """Storage integrity, independent of the operational new-enrolment switch."""
    revision = plan.publication_revision
    if not revision or revision.plan_id != plan.pk or revision.terms != plan_terms(plan):
        raise ValidationError("The configured offer needs a matching audited publication revision.")
    if not plan.active:
        raise ValidationError("A listed configured offer must be active.")
    plan.configuration.full_clean()
    require_operational_configuration(plan.configuration)


def require_configured_offer(plan):
    from .catalogue_lifecycle import require_open_catalogue_item
    require_open_catalogue_item(plan=plan)
    if not plan.configuration_id:
        return
    if not settings.CONFIGURED_PLANS_ENABLED:
        raise ValidationError("Configured plans are preparation-only while their release gate is disabled.")
    if not plan.active:
        raise ValidationError("This configured offer is not published for enrolment.")
    validate_publication_evidence(plan)


@transaction.atomic
def set_configured_plan_publication(*, plan_id, publish, actor, reason, expected_digest, confirmed):
    from .services import _validate_owner, record_scheme_plan_change

    _validate_owner(actor)
    if type(publish) is not bool or confirmed is not True or not reason or not reason.strip():
        raise ValidationError("Review confirmation and an audit reason are required.")
    plan = SchemePlan.objects.select_for_update().get(pk=plan_id)
    from .catalogue_lifecycle import require_open_catalogue_item
    require_open_catalogue_item(plan=plan)
    if not plan.configuration_id:
        raise ValidationError("Use the existing plan workflow for legacy offers.")
    if expected_digest != plan_edit_digest(plan):
        raise ValidationError("This plan changed. Reload and review the current offer.")
    # Withdrawal is always available, including when the release gate is disabled.
    if publish and not settings.CONFIGURED_PLANS_ENABLED:
        raise ValidationError("Configured publication is disabled by the release gate.")
    if plan.active == publish and plan.publicly_listed == publish:
        if publish:
            validate_publication_evidence(plan)
        return plan, False
    plan.configuration.full_clean()
    if publish:
        require_operational_configuration(plan.configuration)
    if publish and not plan.metal_offerings.filter(active=True).exists():
        raise ValidationError("Select at least one exact metal grade before publishing.")
    before = {field: getattr(plan, field) for field in PLAN_FIELDS}
    before["publication_revision_id"] = plan.publication_revision_id
    # A revision is appended inside this transaction before the guarded plan update.
    # Any validation/audit failure rolls both back; no intermediate offer is visible.
    plan.active = plan.publicly_listed = publish
    revision = ensure_plan_revision(plan=plan, actor=actor, reason=reason)
    if publish:
        plan.publication_revision = revision
    plan.full_clean()
    plan.save()
    record_scheme_plan_change(plan=plan, actor=actor, reason=reason, before=before,
        after_overrides={"publication_revision_id": plan.publication_revision_id})
    return plan, True
