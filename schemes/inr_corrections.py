"""Owner-attested full physical returns, not automatic refunds or partial redemption."""
from datetime import datetime, UTC

from django.core import signing
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .closures import _key, _matching, _text
from .closure_selectors import validate_closure_history
from .inr_correction_selectors import (disposition_snapshot, validate_inr_history,
    validate_inr_resolution, validate_inr_disposition_state)
from .inr_settlements import _locked_closure
from .models import (InrSettlementProposal, InrSettlementResolution, InrFulfilmentReturn,
    SchemeClosureEvent, SchemeClosureRequest, SchemeAccount)
from .settlement_selectors import proof_digest

SALT = "inr-full-disposition-resolution-v1"


def _locked(proposal_id, actor):
    target = InrSettlementProposal.objects.get(pk=proposal_id)
    account, request, actor = _locked_closure(target.closure_id, actor)
    proposal = InrSettlementProposal.objects.select_for_update().get(pk=proposal_id)
    return account, request, actor, proposal


def _evidence(account, request, proposal, kind, returns):
    validate_inr_disposition_state(account)
    sequence = validate_closure_history(request)
    history = validate_inr_history(account)
    if not history or history[-1].pk != proposal.pk or proposal.retired:
        raise ValidationError("Only the current unresolved disposition may be corrected.")
    fulfilments = {f.pk: f for f in proposal.fulfilments.select_for_update().order_by("pk")}
    if kind == "VOID":
        if fulfilments or returns or hasattr(proposal, "completion"):
            raise ValidationError("Only an entirely unfulfilled proposal can be voided.")
    elif kind != "FULL_RETURN" or not fulfilments or {r["fulfilment_id"] for r in returns} != set(fulfilments):
        raise ValidationError("Record every fulfilled portion returned in full; partial or promised returns cannot restore principal.")
    resolution = InrSettlementResolution(proposal=proposal, kind=kind)
    for facts in returns:
        row = InrFulfilmentReturn(resolution=resolution, fulfilment=fulfilments[facts["fulfilment_id"]],
            amount=fulfilments[facts["fulfilment_id"]].amount, **{k: v for k, v in facts.items() if k != "fulfilment_id"})
        from .inr_correction_selectors import validate_inr_return
        validate_inr_return(row)
    return dict(version=1, snapshot=disposition_snapshot(proposal), sequence=sequence, kind=kind,
        returns=[dict(r, returned_at=r["returned_at"].isoformat()) for r in returns])


def _returns(rows):
    if not isinstance(rows, (list, tuple)):
        raise ValidationError("Provide the complete list of actual return evidence.")
    result = []
    fields = {"fulfilment_id", "method", "external_reference", "customer_confirmation",
        "invoice_correction_reference", "top_up_refund_reference", "returned_at"}
    for row in rows:
        if not isinstance(row, dict) or set(row) != fields or type(row["fulfilment_id"]) is not int:
            raise ValidationError("Use exact return evidence fields; amounts are derived from the original fulfilment.")
        when = row["returned_at"]
        if not isinstance(when, datetime) or timezone.is_naive(when):
            raise ValidationError("An aware actual return time is required.")
        result.append(dict(fulfilment_id=row["fulfilment_id"], returned_at=when.astimezone(UTC),
            **{name: _text(row[name], 254 if name == "customer_confirmation" else 120, name,
                required=name not in ("invoice_correction_reference", "top_up_refund_reference"))
                for name in fields - {"fulfilment_id", "returned_at"}}))
    if len({r["fulfilment_id"] for r in result}) != len(result):
        raise ValidationError("A fulfilled portion can only be returned once.")
    return sorted(result, key=lambda r: r["fulfilment_id"])


@transaction.atomic
def preview_inr_resolution(*, proposal_id, actor, kind, return_evidence):
    account, request, actor, p = _locked(proposal_id, actor)
    evidence = _evidence(account, request, p, kind, _returns(return_evidence))
    return signing.dumps(dict(actor=actor.pk, evidence=evidence), salt=SALT)


@transaction.atomic
def resolve_inr_settlement(*, proposal_id, actor, kind, return_evidence, preview_token,
    authorization_reference, reason, idempotency_key):
    from .services import _actor_label
    account, request, actor, p = _locked(proposal_id, actor)
    returns = _returns(return_evidence)
    key = _key(idempotency_key)
    reason = _text(reason, 2000, "the correction reason")
    authorization = _text(authorization_reference, 254, "customer authorization for this correction and retained liability")
    try:
        payload = signing.loads(preview_token, salt=SALT)
        evidence = payload["evidence"]
        if (payload["actor"] != actor.pk or evidence["snapshot"]["proposal"] != p.pk
                or evidence["kind"] != kind
                or evidence["returns"] != [dict(r, returned_at=r["returned_at"].isoformat()) for r in returns]):
            raise ValueError
    except (signing.BadSignature, KeyError, TypeError, ValueError):
        raise ValidationError("Reload the owner-bound full-return/void preview.") from None
    existing = InrSettlementResolution.objects.filter(event__idempotency_key=key).first()
    if existing:
        _matching(existing, dict(proposal_id=p.pk, kind=kind, evidence_digest=proof_digest(evidence)))
        _matching(existing.event, dict(actor_id=actor.pk, reason=reason, authorization_reference=authorization))
        validate_inr_resolution(existing)
        return existing
    try:
        signing.loads(preview_token, salt=SALT, max_age=600)
    except signing.BadSignature:
        raise ValidationError("The correction preview expired; reload it.") from None
    if _evidence(account, request, p, kind, returns) != evidence:
        raise ValidationError("Disposition evidence changed; reload the correction preview.")
    event = SchemeClosureEvent(request=request, sequence=evidence["sequence"] + 1,
        action="REVERSE" if hasattr(p, "completion") else "NOTE", resulting_status="ACCEPTED",
        actor=actor, actor_label=_actor_label(actor), reason=reason, authorization_reference=authorization,
        idempotency_key=key)
    event.full_clean()
    event.save()
    resolution = InrSettlementResolution.objects.create(proposal=p, event=event, kind=kind,
        evidence=evidence, evidence_digest=proof_digest(evidence))
    for facts in returns:
        f = p.fulfilments.get(pk=facts["fulfilment_id"])
        InrFulfilmentReturn.objects.create(resolution=resolution, amount=f.amount, **facts)
    validate_inr_resolution(resolution)
    InrSettlementProposal.objects.filter(pk=p.pk).update(retired=True)
    SchemeAccount.objects.filter(pk=account.pk).update(status="CLOSURE_PENDING", updated_at=timezone.now())
    SchemeClosureRequest.objects.filter(pk=request.pk).update(status="ACCEPTED")
    account.refresh_from_db()
    validate_inr_disposition_state(account)
    return resolution
