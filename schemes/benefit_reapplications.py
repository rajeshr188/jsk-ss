"""Gated append-only review decisions. No principal or benefit is spent here."""
from django.core import signing
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .benefit_awards import _locked
from .benefit_reapplication_selectors import decision_evidence, decision_history
from .closures import _key, _matching, _text
from .models import BenefitInvoiceReversal, BenefitReapplicationDecision
from .settlement_selectors import proof_digest

SALT = "benefit-reapplication-review-v1"


def _reversal(account, reversal_id):
    try:
        return BenefitInvoiceReversal.objects.select_for_update(of=("self",)).select_related(
            "fulfilment__award__scheme_account").get(pk=reversal_id, fulfilment__award__scheme_account=account)
    except BenefitInvoiceReversal.DoesNotExist:
        raise ValidationError("Choose a completed benefit return for this agreement.") from None


@transaction.atomic
def preview_benefit_reapplication(*, account_id, reversal_id, actor, outcome, authorization_reference=""):
    account, actor = _locked(account_id, actor)
    reversal = _reversal(account, reversal_id)
    authorization = _text(authorization_reference, 254, "customer authorization", required=outcome == "APPROVE")
    evidence = decision_evidence(reversal, outcome, authorization)
    return signing.dumps(dict(actor=actor.pk, account=account.pk, evidence=evidence), salt=SALT)


@transaction.atomic
def record_benefit_reapplication(*, account_id, actor, preview_token, reason, idempotency_key):
    from .services import _actor_label
    account, actor = _locked(account_id, actor)
    key, reason = _key(idempotency_key), _text(reason, 2000, "reapplication review reason")
    try:
        payload = signing.loads(preview_token, salt=SALT)
        evidence = payload["evidence"]
        if payload["actor"] != actor.pk or payload["account"] != account.pk:
            raise ValueError
        reversal = _reversal(account, evidence["basis"]["reversal"])
    except (signing.BadSignature, KeyError, TypeError, ValueError):
        raise ValidationError("Reload the owner-bound benefit reapplication preview.") from None
    facts = dict(reversal_id=reversal.pk, recorded_by_id=actor.pk, reason=reason, evidence_digest=proof_digest(evidence))
    existing = BenefitReapplicationDecision.objects.filter(idempotency_key=key).first()
    if existing:
        _matching(existing, facts)
        decision_history(reversal)
        return existing  # Historical retry is not permission to reuse a superseded approval.
    try:
        signing.loads(preview_token, salt=SALT, max_age=600)
    except signing.BadSignature:
        raise ValidationError("The reapplication preview expired; reload it.") from None
    current = decision_evidence(reversal, evidence["outcome"], evidence["authorization_reference"])
    if current != evidence:
        raise ValidationError("Return, closure or decision history changed; reload the review.")
    return BenefitReapplicationDecision.objects.create(**facts,
        previous_id=evidence["previous"], sequence=evidence["sequence"], outcome=evidence["outcome"],
        authorization_reference=evidence["authorization_reference"], evidence=evidence,
        actor_label=_actor_label(actor), idempotency_key=key, recorded_at=timezone.now())
