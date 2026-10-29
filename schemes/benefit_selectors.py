"""Current unawarded benefit qualification, never an earned-benefit ledger.

Previously awarded/fulfilled benefits will require their retained lifecycle records;
this projection must not be used to erase them after a source correction or plan edit.
"""
from dataclasses import dataclass
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.utils import timezone

from .agreement_contracts import validate_independent_account_terms
from .agreement_eligibility import get_independent_eligibility
from .benefits import BenefitCalculation, calculate_purchase_bonus
from .instalments import AGREEMENT_TIMEZONE
from .models import InstalmentReservation, SchemeAccount


@dataclass(frozen=True, kw_only=True)
class BenefitQualification:
    state: str
    message: str
    kind: str = "NONE"
    configuration_id: int | None = None
    revision_id: int | None = None
    qualified_payments: int = 0
    required_payments: int | None = None
    missed_period_numbers: tuple = ()
    qualifying_principal: Decimal | None = None
    source_receipt_ids: tuple = ()
    calculation: BenefitCalculation | None = None

    @property
    def qualification_met(self):
        return self.state == "QUALIFICATION_MET"


def _original_schedule_progress(account, required_count, today):
    """Ordinary replacements cannot undo a disclosed loss-of-unearned-benefit rule.

    A separately acknowledged compensation replaces only its affected window and
    still needs a real qualifying payment. Chained outage amendments are followed
    through their bounded, validated source links; no automatic grace/free credit.
    """
    from .instalment_selectors import validated_instalment_periods
    periods = validated_instalment_periods(account)
    by_id = {p.pk: p for p in periods}
    qualified = set(InstalmentReservation.objects.filter(
        period__scheme_account=account, state="QUALIFIED").values_list("period_id", flat=True))
    amendments = list(account.outage_resolutions.filter(outcome="COMPENSATE"))
    replacements = {r.period_id: r.compensation_period_id for r in amendments}
    if any(r.created_at > timezone.now() or r.customer_acknowledged_at > timezone.now() for r in amendments):
        raise ValidationError("Outage acknowledgement cannot be from the future.")
    missed, incomplete = [], []
    for original in periods[:required_count]:
        period, seen = original, set()
        while period.pk not in qualified and period.pk in replacements:
            if period.pk in seen or replacements[period.pk] not in by_id:
                raise ValidationError("Outage replacement evidence requires review.")
            seen.add(period.pk)
            period = by_id[replacements[period.pk]]
        if period.pk not in qualified:
            incomplete.append(original.number)
            if period.ends_before <= today:
                missed.append(original.number)
    return tuple(missed), tuple(incomplete)


def get_benefit_qualification(account):
    """Current preparation-stage read. No status, award or financial mutation.

    Always use the accepted immutable configuration/revision, never the plan's latest
    offer. Normal principal eligibility and required schedule completion are distinct.
    Financial uncertainty takes priority over a missed-payment verdict.
    Future mutations must recompute source proof under the agreement lock, never
    accept this non-locking projection or a caller-supplied calculation as authority.
    """
    return _benefit_qualification(account)


def get_closure_benefit_qualification(closure):
    return _benefit_qualification(closure.scheme_account, closure=closure)


def _benefit_qualification(account, *, closure=None):
    account = SchemeAccount.objects.select_related("configuration_snapshot", "plan_revision").get(pk=account.pk)
    if account.agreement_schema_version != 2:
        raise ValidationError("Configured purchase benefits do not reinterpret legacy cash bonuses.")
    values = dict(configuration_id=account.configuration_snapshot_id, revision_id=account.plan_revision_id)

    def result(state, message):
        return BenefitQualification(state=state, message=message, **values)

    try:
        terms = validate_independent_account_terms(account)
        policy = terms.policy
        values.update(kind=policy.benefit_kind, required_payments=policy.required_count)
        if policy.benefit_kind == "NONE":
            return result("NONE", "No bonus or discount is included in this recorded agreement.")
        if closure is not None:
            from .agreement_eligibility import get_closure_eligibility
            progress = get_closure_eligibility(closure)
        else:
            progress = get_independent_eligibility(account)
        values["qualified_payments"] = progress.qualified_payments
        if progress.state in ("CANCELLED", "CLOSED", "CLOSURE_PENDING"):
            return result("HISTORY_REVIEW", "Review retained closure and benefit history; do not infer a new award or erase an earlier benefit.")
        if progress.state in ("REVIEW", "PAYMENT_PENDING") or (closure is None and progress.state == "DISCONTINUATION_REVIEW"):
            return result("REVIEW", "Resolve payment, source and outage evidence before deciding benefit qualification. Principal is retained.")
        if policy.obligation == "REQUIRED_MONTHLY":
            if policy.benefit_on_miss == "DISQUALIFY_UNEARNED":
                missed, incomplete = _original_schedule_progress(account, policy.required_count,
                    timezone.localdate(timezone=AGREEMENT_TIMEZONE))
                values["missed_period_numbers"] = missed
                if missed:
                    return result("UNQUALIFIED_MISS", "The recorded missed-payment rule prevents this unearned benefit. It does not reduce principal, move its duration floor or reverse an already recorded award.")
                if incomplete:
                    if progress.qualified_payments >= policy.required_count:
                        return result("REVIEW", "The overall count is complete but an original or acknowledged compensating benefit window is unfulfilled. Review the recorded terms; do not request an extra payment or grant free benefit credit.")
                    return result("WAITING_SCHEDULE", "An original or explicitly compensating window still lacks its qualifying payment. An acknowledged extra window is not free benefit credit.")
            if progress.qualified_payments < policy.required_count:
                return result("WAITING_SCHEDULE", "Required qualifying payments are incomplete. Date-based principal eligibility alone does not earn the scheduled benefit.")
        if not progress.policy_eligible:
            return result("WAITING_ELIGIBILITY", "Normal principal eligibility and positive verified entitlement are required. Early closure does not automatically award a completion benefit.")
        if policy.benefit_kind == "INR_PURCHASE_BONUS":
            from .inr_selectors import get_inr_principal_summary
            summary = get_inr_principal_summary(account)
            if summary.needs_review:
                raise ValidationError("Principal sources require reconciliation.")
            receipts = account.inr_principal_receipts.filter(correction__isnull=True).order_by("pk")
            if policy.obligation == "REQUIRED_MONTHLY":
                receipts = receipts.filter(contribution__instalment_reservation__state="QUALIFIED")
            sources = list(receipts)
            principal = sum((r.amount for r in sources), Decimal("0.00"))
            if principal <= 0 or principal > summary.principal_recorded:
                raise ValidationError("A positive reconciled qualifying principal base is required.")
            values.update(qualifying_principal=principal, source_receipt_ids=tuple(r.pk for r in sources),
                calculation=calculate_purchase_bonus(qualifying_principal=principal,
                    percentage=policy.benefit_percentage, cap=policy.benefit_cap_inr))
        return result("QUALIFICATION_MET", "The recorded qualification rules are met. This is not an award or fulfilment: the purchase bonus needs a retained award, and a VA discount needs evidenced eligible invoice charges. Neither is a cash payout or extra metal.")
    except ValidationError:
        return result("REVIEW", "Frozen benefit terms or source evidence require review; no benefit is awarded or removed.")
