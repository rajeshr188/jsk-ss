"""Gated retained awards. No invoice consumption, refund or agreement closure."""
from decimal import Decimal

from django.core import signing
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .benefit_award_selectors import benefit_award_evidence, validate_benefit_award
from .closures import _actor, _key, _matching, _text
from .models import SchemeAccount, SchemeBenefitAward
from .plan_policies import require_operational_configuration
from .settlement_selectors import proof_digest

SALT = "configured-benefit-award-v1"


def _locked(account_id, actor):
    account = SchemeAccount.objects.select_for_update().get(pk=account_id)
    actor, owner = _actor(actor, account)
    if not owner:
        raise ValidationError("Only an active owner may record a benefit award.")
    if not account.configuration_snapshot_id or account.agreement_schema_version != 2:
        raise ValidationError("Benefit awards require a pinned independent agreement.")
    require_operational_configuration(account.configuration_snapshot)
    return account, actor


@transaction.atomic
def preview_benefit_award(*, account_id, actor):
    account, actor = _locked(account_id, actor)
    if SchemeBenefitAward.objects.filter(scheme_account=account).exists():
        raise ValidationError("A benefit award already exists; inspect its retained history.")
    evidence = benefit_award_evidence(account)
    return signing.dumps(dict(actor=actor.pk, evidence=evidence), salt=SALT)


@transaction.atomic
def record_benefit_award(*, account_id, actor, preview_token, reason, idempotency_key):
    account, actor = _locked(account_id, actor)
    key = _key(idempotency_key)
    reason = _text(reason, 2000, "the benefit award reason")
    try:
        payload = signing.loads(preview_token, salt=SALT)
        evidence = payload["evidence"]
        if payload["actor"] != actor.pk or evidence["account"] != account.pk:
            raise ValueError
    except (signing.BadSignature, KeyError, TypeError, ValueError):
        raise ValidationError("Reload the owner-bound benefit award preview.") from None
    facts = dict(scheme_account_id=account.pk, recorded_by_id=actor.pk, reason=reason,
        evidence_digest=proof_digest(evidence))
    existing = SchemeBenefitAward.objects.filter(idempotency_key=key).first()
    if existing:
        _matching(existing, facts)
        validate_benefit_award(existing)
        return existing
    try:
        signing.loads(preview_token, salt=SALT, max_age=600)
    except signing.BadSignature:
        raise ValidationError("The benefit preview expired; reload it.") from None
    if SchemeBenefitAward.objects.filter(scheme_account=account).exists():
        raise ValidationError("A benefit award is already retained; do not stack or replace it.")
    if benefit_award_evidence(account) != evidence:
        raise ValidationError("Benefit sources or qualification changed; reload the preview.")
    return _create_award(facts, evidence, actor, key)


def _create_award(facts, evidence, actor, key):
    from .services import _actor_label
    return SchemeBenefitAward.objects.create(**facts, configuration_id=evidence["configuration"],
        revision_id=evidence["revision"], kind=evidence["kind"],
        qualifying_principal=Decimal(evidence["qualifying_principal"]) if evidence["qualifying_principal"] is not None else None,
        amount=Decimal(evidence["amount"]) if evidence["amount"] is not None else None,
        percentage=Decimal(evidence["percentage"]), cap_inr=Decimal(evidence["cap_inr"]),
        eligible_charge_definition=evidence["eligible_charge_definition"],
        calculation_version=evidence["calculation_version"], rounding_rule=evidence["rounding_rule"],
        evidence=evidence, actor_label=_actor_label(actor), idempotency_key=key, recorded_at=timezone.now())


def _retain_closure_award(*, account, closure, actor, evidence, reason, idempotency_key, reapplication=None):
    """Called inside a signed full-settlement transaction, never as a projection write."""
    account, actor = _locked(account.pk, actor)
    existing = SchemeBenefitAward.objects.select_for_update().filter(scheme_account=account).first()
    if existing:
        from .benefit_fulfilment_selectors import require_unchanged_award_sources
        require_unchanged_award_sources(existing)
        if existing.evidence != evidence:
            raise ValidationError("The retained award changed or was consumed; review it.")
        if existing.invoice_fulfilments.exists():
            from .benefit_application_selectors import current_reapplication
            if not reapplication or current_reapplication(existing) != reapplication:
                raise ValidationError("Retain a current reapplication approval for this returned right.")
        return existing
    if benefit_award_evidence(account, closure=closure) != evidence:
        raise ValidationError("Closure benefit qualification changed; reload the settlement preview.")
    return _create_award(dict(scheme_account_id=account.pk, recorded_by_id=actor.pk,
        reason=_text(reason, 2000, "benefit reason"), evidence_digest=proof_digest(evidence)),
        evidence, actor, _key(idempotency_key))
