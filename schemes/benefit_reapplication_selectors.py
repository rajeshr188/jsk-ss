"""Review evidence for a returned benefit. Approval is not invoice fulfilment."""
from django.core.exceptions import ValidationError
from django.utils import timezone

from .benefit_fulfilment_selectors import require_unchanged_award_sources, validate_benefit_reversal
from .closure_selectors import validate_closure_history
from .replacement_settlement_selectors import (disposition_history, history_entry,
    require_fresh_replacement_references, validate_replacement_links)
from .settlement_selectors import proof_digest


class _OwnerHistoryRead:
    """Validated historical decisions for one read-only workspace invocation.

    Never returned to callers or used by mutation services. Current source/state
    checks still run; only repeated traversal of the same decision prefix is reused.
    """
    def __init__(self, account):
        self.account_id = account.pk
        self.database = account._state.db
        self.completed = {}
        self.visiting = set()

    def decisions(self, reversal):
        if (reversal._state.db != self.database
                or reversal.fulfilment.award.scheme_account_id != self.account_id):
            raise ValidationError("Benefit review history belongs to another agreement.")
        key = reversal.pk
        if key in self.visiting:
            raise ValidationError("Benefit review history contains a circular predecessor.")
        if key not in self.completed:
            self.visiting.add(key)
            try:
                rows = _decision_history(reversal, history_read=self)
                self.completed[key] = rows
            finally:
                self.visiting.remove(key)
        return self.completed[key]


def return_basis(reversal, *, closure_sequence=None, disposition_count=None, current=True,
                 _history_read=None):
    """Require complete original principal/benefit return, not a balance inference."""
    validate_benefit_reversal(reversal, _history_read=_history_read)
    f, award = reversal.fulfilment, reversal.fulfilment.award
    account = award.scheme_account
    account.refresh_from_db()
    history = disposition_history(account)
    validate_replacement_links(history)
    if disposition_count is not None:
        if type(disposition_count) is not int or not 1 <= disposition_count <= len(history):
            raise ValidationError("The retained disposition prefix is invalid.")
        history = history[:disposition_count]
    elif (account.savings_mode == "INR_CREDIT" and history and not history[-1].retired
            and history[-1].evidence.get("independent", {}).get("reapplication", {}).get("previous") == f.pk):
        # An unconsumed proposal does not use up a review. A later HOLD must still
        # be possible; its existing proposal must be voided before fresh approval.
        history = history[:-1]
    if not history or any("independent" not in row.evidence for row in history):
        raise ValidationError("Reapplication review requires a retained independent full disposition.")
    closure = history[0].closure
    sequence = validate_closure_history(closure)
    if current and (account.status != "CLOSURE_PENDING" or closure.status != "ACCEPTED"):
        raise ValidationError("Retain the accepted closure and block contributions during return review.")
    root = history[0].evidence["independent"]
    if (history[0].basis != "NORMAL" or root["award_evidence"] != award.evidence
            or root["progress"]["state"] != "ELIGIBLE"):
        raise ValidationError("Retain the originally qualified award; correction cannot earn a new benefit.")
    if account.savings_mode == "INR_CREDIT":
        from .inr_correction_selectors import validate_inr_history
        validate_inr_history(account)
        if not f.inr_fulfilment_id or f.inr_fulfilment.proposal_id not in [p.pk for p in history]:
            raise ValidationError("Review the latest fully returned invoice, not an unrelated predecessor.")
    else:
        from .settlement_selectors import validate_configured_settlement
        for row in history:
            validate_configured_settlement(row)
        if f.metal_settlement_id not in [p.pk for p in history]:
            raise ValidationError("Review the latest fully returned exact-grade invoice.")
    entries = [history_entry(row) for row in history]
    if current:
        from .benefit_award_selectors import benefit_source_snapshot
        require_unchanged_award_sources(award)
        if award.invoice_fulfilments.order_by("-pk").first().pk != f.pk:
            raise ValidationError("Review the latest returned benefit, not an already replaced invoice.")
        if root["sources"] != benefit_source_snapshot(account):
            raise ValidationError("Reconcile changed original payment, schedule or review sources first.")
    if closure_sequence is None:
        closure_sequence = sequence
    if type(closure_sequence) is not int or not 1 <= closure_sequence <= sequence:
        raise ValidationError("The retained closure sequence is invalid.")
    events = list(closure.events.filter(sequence__lte=closure_sequence).order_by("sequence").values(
        "id", "sequence", "action", "resulting_status", "authorization_reference", "reason", "actor_label"))
    correction = reversal.inr_return.resolution if reversal.inr_return_id else reversal.metal_reversal
    if closure_sequence < correction.event.sequence:
        raise ValidationError("The review must follow the completed principal return.")
    return dict(account=account.pk, award=award.pk, award_digest=award.evidence_digest,
        original_qualification=proof_digest(root), sources=proof_digest(root["sources"]),
        closure=str(closure.pk), closure_sequence=closure_sequence, closure_events=events,
        dispositions=entries, fulfilment=f.pk, fulfilment_digest=f.evidence_digest,
        reversal=reversal.pk, returned_amount=str(reversal.amount),
        inr_return=reversal.inr_return_id, metal_reversal=reversal.metal_reversal_id,
        invoice_correction=reversal.invoice_correction_reference,
        customer_confirmation=reversal.customer_confirmation,
        returned_at=reversal.returned_at.isoformat(), reversal_recorded_at=reversal.recorded_at.isoformat())


def validate_reapplication_decision(row, *, _history_read=None):
    try:
        e = row.evidence
        previous = row.previous
        if (e["version"] != 1 or row.sequence != e["sequence"]
                or e["outcome"] != row.outcome or e["authorization_reference"] != row.authorization_reference
                or row.outcome not in ("APPROVE", "HOLD")
                or bool(row.authorization_reference.strip()) != (row.outcome == "APPROVE")
                or e["previous"] != (previous.pk if previous else None)
                or e["previous_digest"] != (previous.evidence_digest if previous else None)
                or row.sequence != (previous.sequence + 1 if previous else 1)
                or (previous and previous.reversal_id != row.reversal_id)
                or row.evidence_digest != proof_digest(e)
                or not row.reason.strip() or not row.actor_label.strip()
                or row.recorded_at is None or timezone.is_naive(row.recorded_at)
                or not row.reversal.recorded_at <= row.recorded_at <= timezone.now()
                or (previous and row.recorded_at < previous.recorded_at)
                or e["basis"] != return_basis(row.reversal, closure_sequence=e["basis"]["closure_sequence"],
                    disposition_count=len(e["basis"]["dispositions"]), current=False,
                    _history_read=_history_read)):
            raise ValueError
    except (KeyError, TypeError, AttributeError, ValueError):
        raise ValidationError("Retained benefit reapplication decision requires investigation; do not rewrite it.") from None


def decision_history(reversal, *, _history_read=None):
    if _history_read is not None:
        return _history_read.decisions(reversal)
    return _decision_history(reversal)


def _decision_history(reversal, *, history_read=None):
    rows = list(reversal.reapplication_decisions.select_related("previous").order_by("sequence"))
    for number, row in enumerate(rows, 1):
        if row.sequence != number or row.previous_id != (rows[number - 2].pk if number > 1 else None):
            raise ValidationError("Benefit reapplication history is incomplete or forked.")
        validate_reapplication_decision(row, _history_read=history_read)
    return rows


def decision_evidence(reversal, outcome, authorization_reference):
    if outcome not in ("APPROVE", "HOLD") or bool(authorization_reference) != (outcome == "APPROVE"):
        raise ValidationError("Approval needs fresh customer authorization; a hold must not claim approval.")
    rows = decision_history(reversal)
    from .models import BenefitInvoiceFulfilment
    if BenefitInvoiceFulfilment.objects.filter(reapplication_decision__reversal=reversal).exists():
        raise ValidationError("This review was consumed by an invoice; review its own full return instead.")
    basis = return_basis(reversal)
    if outcome == "APPROVE":
        require_fresh_replacement_references(reversal.fulfilment.award.scheme_account, authorization_reference, "")
        used = {r.authorization_reference.casefold() for r in rows if r.authorization_reference}
        used.add(reversal.customer_confirmation.casefold())
        used.add(reversal.fulfilment.customer_receipt_reference.casefold())
        if authorization_reference.casefold() in used:
            raise ValidationError("Retain fresh customer authorization for this reapplication review.")
    previous = rows[-1] if rows else None
    return dict(version=1, basis=basis, sequence=len(rows) + 1,
        previous=previous.pk if previous else None, previous_digest=previous.evidence_digest if previous else None,
        outcome=outcome, authorization_reference=authorization_reference)


def _status_from_validated_history(reversal, rows, *, history_read=None):
    """Reuse this invocation's validated rows; return any current basis we read."""
    if not rows:
        return "UNREVIEWED", None
    from .models import BenefitInvoiceFulfilment
    consumed = BenefitInvoiceFulfilment.objects.filter(reapplication_decision__reversal=reversal).first()
    if consumed:
        from .benefit_fulfilment_selectors import validate_benefit_fulfilment
        validate_benefit_fulfilment(consumed, _history_read=history_read)
        return "CONSUMED", None
    latest = rows[-1]
    basis = return_basis(reversal, _history_read=history_read)
    if latest.evidence["basis"] != basis:
        return "STALE", basis
    return ("APPROVED_REVIEW" if latest.outcome == "APPROVE" else "HELD"), basis


def reapplication_review_status(reversal):
    """Fresh read; none of these states authorizes another invoice."""
    return _status_from_validated_history(reversal, decision_history(reversal))[0]


def owner_reapplication_workspace(account):
    """Private retained history and reviewable returns; never spending permission."""
    from .models import BenefitInvoiceReversal
    reversals = BenefitInvoiceReversal.objects.filter(fulfilment__award__scheme_account=account).select_related(
        "fulfilment__award", "fulfilment__metal_settlement", "fulfilment__inr_fulfilment__proposal").order_by("-pk")
    labels = {"UNREVIEWED": "Not yet reviewed", "APPROVED_REVIEW": "Approved for replacement review",
        "HELD": "On hold", "STALE": "Needs a fresh review", "CONSUMED": "Used by a replacement invoice"}
    rows, reviewable = [], []
    history_read = _OwnerHistoryRead(account)
    for reversal in reversals:
        decisions, blocked, status = [], "", "REVIEW_REQUIRED"
        try:
            decisions = decision_history(reversal, _history_read=history_read)
            status, basis = _status_from_validated_history(reversal, decisions, history_read=history_read)
            if status != "CONSUMED":
                if basis is None:
                    return_basis(reversal, _history_read=history_read)
                reviewable.append(reversal.pk)
        except ValidationError as error:
            blocked = " ".join(error.messages)
            status = "REVIEW_REQUIRED"
        f = reversal.fulfilment
        closure_id = f.inr_fulfilment.proposal.closure_id if f.inr_fulfilment_id else f.metal_settlement.closure_id
        rows.append(dict(reversal=reversal, decisions=decisions, status=status,
            status_label=labels.get(status, "Investigation required"), blocked=blocked, closure_id=closure_id))
    return dict(review_rows=rows, reviewable_returns=reversals.filter(pk__in=reviewable))
