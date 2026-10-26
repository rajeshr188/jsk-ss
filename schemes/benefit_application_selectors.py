"""Linear benefit invoice history and explicit consumption of returned-right review."""
from django.core.exceptions import ValidationError

from .models import BenefitReapplicationDecision


def decision_reference(decision):
    return dict(decision=decision.pk, digest=decision.evidence_digest,
        previous=decision.reversal.fulfilment_id, reversal=decision.reversal_id)


def current_reapplication(award):
    from .benefit_reapplication_selectors import decision_history, reapplication_review_status
    history = application_history(award)
    if not history or not hasattr(history[-1], "reversal"):
        raise ValidationError("A reapplication requires a complete retained invoice return.")
    reversal = history[-1].reversal
    rows = decision_history(reversal)
    if not rows or reapplication_review_status(reversal) != "APPROVED_REVIEW":
        raise ValidationError("A reapplication requires the latest current approved customer-authorized review.")
    return decision_reference(rows[-1])


def validate_bound_review(disposition, *, current=False):
    """Proposal binding survives returns; only current approval permits new use."""
    from .benefit_reapplication_selectors import decision_history
    proof = disposition.evidence.get("independent", {}).get("reapplication")
    if not isinstance(proof, dict):
        raise ValidationError("Retain the explicit reapplication approval in this disposition.")
    try:
        decision = BenefitReapplicationDecision.objects.get(pk=proof["decision"])
        rows = decision_history(decision.reversal)
        basis = decision.evidence["basis"]
        account_id = disposition.scheme_account_id if hasattr(disposition, "scheme_account_id") else disposition.redemption.scheme_account_id
        if (decision.outcome != "APPROVE" or proof != decision_reference(decision)
                or basis["account"] != account_id or basis["closure"] != str(disposition.closure_id)
                or basis["closure_sequence"] != disposition.evidence["sequence"]
                or basis["dispositions"] != disposition.evidence["independent"]["replacement_history"]):
            raise ValueError
        if current and (not rows or rows[-1].pk != decision.pk):
            raise ValidationError("The bound reapplication approval was superseded; void/reconcile this proposal first.")
    except (KeyError, TypeError, ValueError, BenefitReapplicationDecision.DoesNotExist):
        raise ValidationError("Benefit reapplication approval does not match this exact replacement.") from None
    return decision


def validate_application_link(row, *, current=False):
    """Historical checks recurse only into earlier returned invoices, never successors."""
    prior = row.award.invoice_fulfilments.order_by("pk")
    if row.pk:
        prior = prior.filter(pk__lt=row.pk)
    last = prior.last()
    if row.previous_id != (last.pk if last else None):
        raise ValidationError("Benefit invoices must form one retained predecessor chain.")
    if row.previous_id is None:
        if row.reapplication_decision_id is not None:
            raise ValidationError("An original invoice cannot consume a return review.")
        return
    previous = row.previous
    reversal = getattr(previous, "reversal", None)
    disposition = row.inr_fulfilment.proposal if row.inr_fulfilment_id else row.metal_settlement
    decision = validate_bound_review(disposition, current=current)
    if (previous.award_id != row.award_id or reversal is None
            or decision.reversal_id != reversal.pk or row.reapplication_decision_id != decision.pk
            or row.fulfilled_at < decision.recorded_at
            or row.recorded_at < reversal.recorded_at):
        raise ValidationError("Only a fully returned prior invoice and its approved review permit reapplication.")
    # validate_bound_review validates decision_history, including this predecessor's
    # complete return. Repeating it here would recursively revalidate every older
    # generation twice at each level of a longer invoice chain.
    if current:
        latest = row.award.invoice_fulfilments.exclude(pk=row.pk).order_by("-pk").first()
        if latest is None or latest.pk != previous.pk:
            raise ValidationError("Another invoice already consumed this returned right.")


def application_history(award):
    from .benefit_fulfilment_selectors import validate_benefit_fulfilment, validate_benefit_reversal
    rows = list(award.invoice_fulfilments.order_by("pk"))
    for index, row in enumerate(rows):
        reversal = getattr(row, "reversal", None)
        if reversal:
            # Reversal validation includes its original fulfilment proof.
            validate_benefit_reversal(reversal)
        else:
            validate_benefit_fulfilment(row)
            if index != len(rows) - 1:
                raise ValidationError("Every replaced benefit invoice requires its full reversal.")
    return rows
