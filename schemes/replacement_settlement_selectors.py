"""Replacement proof reads; never reopen contributions or re-earn a benefit.

Consumed benefits require a complete return and current explicit reapplication review.
"""
from copy import deepcopy

from django.core.exceptions import ValidationError

from .models import ConfiguredSettlement, InrSettlementProposal, SchemeBenefitAward


def disposition_history(account):
    if account.savings_mode == "INR_CREDIT":
        if account.redemptions.exists():
            raise ValidationError("Mixed principal history requires investigation.")
        return list(account.inr_settlements.select_related("scheme_account", "closure", "resolution__event").order_by("pk"))
    if account.inr_settlements.exists():
        raise ValidationError("Mixed principal history requires investigation.")
    history = list(ConfiguredSettlement.objects.filter(redemption__scheme_account=account)
        .select_related("closure", "event", "redemption__scheme_account", "redemption__reversal",
            "correction__event", "correction__reversal").order_by("pk"))
    if len(history) != account.redemptions.count():
        raise ValidationError("Unlinked/legacy redemptions cannot enter independent replacement settlement.")
    return history


def history_entry(row):
    if isinstance(row, InrSettlementProposal):
        resolution = getattr(row, "resolution", None)
        if not row.retired or resolution is None:
            raise ValidationError("Every predecessor must have a completed void/full-return resolution.")
        return dict(id=row.pk, digest=row.evidence_digest, resolution=resolution.pk,
            resolution_digest=resolution.evidence_digest, event=resolution.event_id)
    correction = getattr(row, "correction", None)
    if correction is None:
        raise ValidationError("Every previous metal settlement needs its completed full reversal.")
    return dict(id=row.pk, digest=row.evidence_digest, correction=correction.pk,
        reversal=correction.reversal_id, event=correction.event_id)


def validate_replacement_links(history):
    """Historical chain shape, including after a later replacement has completed.

    Does not infer physical returns: callers also validate each retained disposition
    and its resolution. No current eligibility calculation can improve the first
    disposition's basis/benefit merely because a correction happened later.
    """
    if not history:
        return
    proofs = [r.evidence.get("independent") for r in history]
    if all(p is None for p in proofs):
        return  # Existing narrow foundation history remains separate.
    try:
        root = proofs[0]
        if (not isinstance(root, dict) or root["version"] != 1
                or not isinstance(root["sources"], dict)
                or not isinstance(root["progress"], dict)
                or not isinstance(root["qualification"], dict)
                or (root["award_evidence"] is not None and not isinstance(root["award_evidence"], dict))):
            raise ValueError
        for index, (row, proof) in enumerate(zip(history, proofs)):
            if not isinstance(proof, dict) or not isinstance(root, dict):
                raise ValueError
            if row.closure_id != history[0].closure_id or row.basis != history[0].basis:
                raise ValueError
            if row.basis != ("NORMAL" if root["progress"]["state"] == "ELIGIBLE" else "EARLY"):
                raise ValueError
            if index == 0:
                if "replacement_history" in proof:
                    raise ValueError
                continue
            if proof.get("replacement_history") != [history_entry(p) for p in history[:index]]:
                raise ValueError
            if any(proof[name] != root[name] for name in ("version", "progress", "qualification", "sources", "award_evidence")):
                raise ValueError
            prior = history[index - 1]
            resolution = prior.resolution if isinstance(prior, InrSettlementProposal) else prior.correction
            if row.evidence["sequence"] < resolution.event.sequence:
                raise ValueError
            if isinstance(row, InrSettlementProposal):
                if row.previous_id != prior.pk or row.recorded_at < resolution.event.created_at:
                    raise ValueError
            elif row.redemption.completed_at < resolution.event.created_at:
                raise ValueError
            if not isinstance(row, InrSettlementProposal) and row.evidence.get("redemptions") != [
                    dict(id=p.redemption_id, reversal=p.correction.reversal_id) for p in history[:index]]:
                raise ValueError
    except (KeyError, TypeError, AttributeError, ValueError):
        raise ValidationError("Replacement disposition chain or retained qualification differs; investigate without rewriting history.") from None


def replacement_qualification_proof(account, closure):
    history = disposition_history(account)
    if not history:
        return None
    from .closure_selectors import validate_closure_history
    validate_closure_history(closure)
    closure.refresh_from_db()
    account.refresh_from_db()
    if (closure.scheme_account_id != account.pk or closure.status != "ACCEPTED"
            or account.status != "CLOSURE_PENDING" or any(r.closure_id != closure.pk for r in history)):
        raise ValidationError("Keep the original accepted closure contained for an authorized replacement.")
    validate_replacement_links(history)
    if any("independent" not in r.evidence for r in history):
        raise ValidationError("Do not convert an older foundation disposition into an independent replacement.")
    if account.savings_mode == "INR_CREDIT":
        from .inr_correction_selectors import validate_inr_disposition_state
        from .independent_inr_settlement_selectors import validate_independent_inr_benefit
        validate_inr_disposition_state(account)
        for p in history:
            validate_independent_inr_benefit(p, current=True)
    else:
        from .settlement_selectors import validate_configured_settlement
        from .independent_settlement_selectors import validate_independent_settlement_benefit
        for p in history:
            validate_configured_settlement(p)
            validate_independent_settlement_benefit(p)
    entries = [history_entry(p) for p in history]
    from .benefit_award_selectors import benefit_source_snapshot
    root = history[0].evidence["independent"]
    if root["sources"] != benefit_source_snapshot(account):
        raise ValidationError("Original payment, rate, schedule or review evidence changed; reconcile before replacement.")
    award = SchemeBenefitAward.objects.filter(scheme_account=account).first()
    expected = root["award_evidence"]
    if expected is None:
        if award is not None:
            raise ValidationError("A correction cannot silently add or remove a benefit award.")
    else:
        from .benefit_fulfilment_selectors import require_unchanged_award_sources
        if award is None or award.evidence != expected:
            raise ValidationError("Retain the original unconsumed award and investigate missing evidence.")
        require_unchanged_award_sources(award)
    proof = deepcopy(root)
    proof.update(invoice=None, award_id=award.pk if award else None, replacement_history=entries)
    if award and award.invoice_fulfilments.exists():
        from .benefit_application_selectors import current_reapplication
        proof["reapplication"] = current_reapplication(award)
    return proof


def require_fresh_replacement_references(account, authorization, invoice):
    history = disposition_history(account)
    if not history:
        return
    references = [history[0].closure.authorization_reference]
    for row in history:
        references.append(row.authorization_reference)
        resolution = getattr(row, "resolution" if isinstance(row, InrSettlementProposal) else "correction", None)
        if resolution:
            references.append(resolution.event.authorization_reference)
    if authorization.casefold() in {r.casefold() for r in references}:
        raise ValidationError("Retain fresh customer authorization for this exact replacement, not a previous settlement or return reference.")
    if invoice:
        from .models import Redemption
        if (InrSettlementProposal.objects.filter(invoice_reference__iexact=invoice).exists()
                or Redemption.objects.filter(external_reference__iexact=invoice).exists()):
            raise ValidationError("Use a new invoice reference for the replacement disposition.")
