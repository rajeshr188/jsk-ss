"""Retained benefit evidence and drift detection; never a spendable balance."""
import json
from dataclasses import dataclass
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Q
from django.utils import timezone

from .agreement_contracts import validate_independent_account_terms
from .benefit_selectors import get_benefit_qualification
from .benefits import BENEFIT_CALCULATION_VERSION, BENEFIT_ROUNDING_RULE, calculate_purchase_bonus
from .models import PaymentWebhookEvent, SchemeAccount, SchemeBenefitAward
from .settlement_selectors import proof_digest


def _rows(queryset, *fields):
    return list(queryset.order_by("pk").values(*fields))


def benefit_award_evidence(account, *, closure=None):
    """Current proof. Mutation callers must hold the agreement lock throughout."""
    account = SchemeAccount.objects.select_related("configuration_snapshot", "plan_revision").get(pk=account.pk)
    if account.agreement_schema_version != 2 or not account.configuration_snapshot_id or not account.plan_revision_id:
        raise ValidationError("A benefit award requires its retained independent contract and revision.")
    terms = validate_independent_account_terms(account)
    if closure is not None:
        from .benefit_selectors import get_closure_benefit_qualification
        if closure.scheme_account_id != account.pk:
            raise ValidationError("The award's closure must belong to this agreement.")
        qualification = get_closure_benefit_qualification(closure)
    else:
        qualification = get_benefit_qualification(account)
    if not qualification.qualification_met:
        raise ValidationError("Benefit qualification is not met; resolve the recorded review or schedule first.")
    policy = terms.policy
    evidence = dict(version=1, account=account.pk, configuration=terms.configuration_id,
        revision=account.plan_revision_id, revision_digest=proof_digest(account.plan_revision.terms),
        contract=terms.account_snapshots(), kind=policy.benefit_kind,
        percentage=policy.benefit_percentage, cap_inr=policy.benefit_cap_inr,
        eligible_charge_definition=policy.eligible_charge_definition,
        calculation_version=BENEFIT_CALCULATION_VERSION, rounding_rule=BENEFIT_ROUNDING_RULE,
        qualifying_principal=qualification.qualifying_principal,
        amount=qualification.calculation.amount if qualification.calculation else None,
        source_receipt_ids=list(qualification.source_receipt_ids),
        qualified_payments=qualification.qualified_payments, required_payments=qualification.required_payments,
        **benefit_source_snapshot(account))
    if closure is not None:
        evidence["closure"] = str(closure.pk)
    return json.loads(json.dumps(evidence, cls=DjangoJSONEncoder))


def benefit_source_snapshot(account):
    """Financial source facts only, not eligibility or permission to spend an award.

    Kept identical to the source portion of v1 award evidence so closing an agreement
    never requires pretending that it is still active or rewriting a retained award.
    """
    payments = account.contributions.all()
    events = PaymentWebhookEvent.objects.filter(Q(contribution__in=payments) | Q(
        gateway_order_id__in=payments.exclude(gateway_order_id="").values("gateway_order_id")))
    periods = account.instalment_periods.all()
    from .models import InstalmentReservation, InstalmentPaymentDecision, InstalmentReview
    claims = InstalmentReservation.objects.filter(period__in=periods)
    evidence = dict(
        payments=_rows(payments, "pk", "amount", "status", "paid_at", "payment_channel", "payment_gateway",
            "gateway_mode", "gateway_order_id", "gateway_reference", "scheme_rate_id", "rate_locked_at",
            "cash_receipt__pk", "cash_reversal__pk", "metal_allocation__pk", "metal_allocation__quantity"),
        receipts=_rows(account.inr_principal_receipts.all(), "pk", "contribution_id", "amount", "verified_at",
            "cash_receipt_id", "webhook_event_id", "api_capture_id", "correction__pk"),
        periods=_rows(periods, "pk", "number", "starts_on", "ends_before"),
        claims=_rows(claims, "pk", "period_id", "contribution_id", "state"),
        decisions=_rows(InstalmentPaymentDecision.objects.filter(reservation__in=claims),
            "pk", "reservation_id", "sequence", "state", "earliest_at", "latest_at", "created_at"),
        reviews=_rows(InstalmentReview.objects.filter(period__in=periods), "pk", "period_id", "sequence", "action"),
        outages=_rows(account.outage_resolutions.all(), "pk", "period_id", "outcome", "compensation_period_id",
            "customer_acknowledged_at", "created_at"),
        webhooks=_rows(events, "pk", "status", "event_type", "gateway_mode", "gateway_order_id",
            "gateway_reference", "payload_sha256", "processed_at"))
    from .payment_refund_selectors import refund_disposition_evidence
    evidence.update(refund_disposition_evidence(account))
    return json.loads(json.dumps(evidence, cls=DjangoJSONEncoder))


def validate_benefit_award(award):
    """Validate retained facts without re-earning or silently revoking the award.

    Current source changes are separately flagged by get_benefit_award_status.
    The digest detects inconsistency, not a substitute for DB permissions/backups.
    """
    account = SchemeAccount.objects.select_related("configuration_snapshot", "plan_revision").get(pk=award.scheme_account_id)
    if account.agreement_schema_version != 2 or not account.configuration_snapshot_id or not account.plan_revision_id:
        raise ValidationError("The award's independent contract or revision needs review; retain its history.")
    terms = validate_independent_account_terms(account)
    policy = terms.policy
    e = award.evidence
    from .payment_refund_selectors import validate_retained_refund_disposition
    if isinstance(e, dict):
        validate_retained_refund_disposition(e, account)
    try:
        if "closure" in e:
            from .models import SchemeClosureRequest
            if not SchemeClosureRequest.objects.filter(pk=e["closure"], scheme_account=account).exists():
                raise ValueError
        expected = dict(version=1, account=account.pk, configuration=terms.configuration_id,
            revision=account.plan_revision_id, revision_digest=proof_digest(account.plan_revision.terms),
            contract=json.loads(json.dumps(terms.account_snapshots(), cls=DjangoJSONEncoder)),
            kind=award.kind, percentage=str(award.percentage), cap_inr=str(award.cap_inr),
            eligible_charge_definition=award.eligible_charge_definition,
            calculation_version=award.calculation_version, rounding_rule=award.rounding_rule,
            qualifying_principal=str(award.qualifying_principal) if award.qualifying_principal is not None else None,
            amount=str(award.amount) if award.amount is not None else None,
            required_payments=policy.required_count)
        if (not isinstance(e, dict) or any(e.get(k) != v for k, v in expected.items())
                or proof_digest(e) != award.evidence_digest
                or award.configuration_id != terms.configuration_id or award.revision_id != account.plan_revision_id
                or award.kind != policy.benefit_kind or award.percentage != policy.benefit_percentage
                or award.cap_inr != policy.benefit_cap_inr or award.eligible_charge_definition != policy.eligible_charge_definition
                or award.calculation_version != BENEFIT_CALCULATION_VERSION or award.rounding_rule != BENEFIT_ROUNDING_RULE
                or not award.recorded_at or timezone.is_naive(award.recorded_at) or award.recorded_at > timezone.now()
                or not award.actor_label.strip() or not award.reason.strip()):
            raise ValueError
        if type(e.get("qualified_payments")) is not int or e["qualified_payments"] < 0:
            raise ValueError
        if policy.required_count is not None and e["qualified_payments"] != policy.required_count:
            raise ValueError
        for name in ("payments", "receipts", "periods", "claims", "decisions", "reviews", "outages", "webhooks"):
            rows = e[name]
            if not isinstance(rows, list) or len({r["pk"] for r in rows}) != len(rows):
                raise ValueError
        ids = e["source_receipt_ids"]
        if not isinstance(ids, list) or any(type(pk) is not int for pk in ids) or len(set(ids)) != len(ids):
            raise ValueError
        if award.kind == "INR_PURCHASE_BONUS":
            source_rows = [r for r in e["receipts"] if r["pk"] in ids and r["correction__pk"] is None]
            principal = sum((Decimal(r["amount"]) for r in source_rows), Decimal("0.00"))
            if len(source_rows) != len(ids) or not ids or principal != award.qualifying_principal:
                raise ValueError
            calculation = calculate_purchase_bonus(qualifying_principal=principal,
                percentage=award.percentage, cap=award.cap_inr)
            if award.amount != calculation.amount or principal <= 0:
                raise ValueError
        elif award.kind != "VA_DISCOUNT" or ids or award.amount is not None or award.qualifying_principal is not None:
            raise ValueError
    except (KeyError, TypeError, ValueError, ArithmeticError):
        raise ValidationError("Retained benefit award evidence requires review; do not discard the award.") from None


@dataclass(frozen=True)
class BenefitAwardStatus:
    award_id: int | None
    kind: str | None
    recorded_amount: Decimal | None
    needs_review: bool
    message: str


def get_benefit_award_status(account):
    award = SchemeBenefitAward.objects.filter(scheme_account_id=account.pk).first()
    if award is None:
        return BenefitAwardStatus(None, None, None, False, "No benefit award is recorded.")
    review = False
    try:
        validate_benefit_award(award)
        review = benefit_award_evidence(account) != award.evidence
    except ValidationError:
        review = True
    return BenefitAwardStatus(award.pk, award.kind, award.amount, review,
        "Retain the award and review changed source/closure evidence; no principal deduction or automatic revocation."
        if review else "Recorded purchase benefit/right; not an invoice fulfilment, cash balance or settlement authorization.")
