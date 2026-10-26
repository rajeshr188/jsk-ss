"""Current independent-policy progress, not payment or settlement authorization.

Reads never update the agreement date/status, award benefits or release a hold.
Financial mutation callers still need their own locked source/disposition proof.
"""
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils import timezone

from .agreement_contracts import validate_independent_account_terms
from .instalments import AGREEMENT_TIMEZONE, validate_real_instalment_channel
from .models import InstalmentReservation, PaymentWebhookEvent, SchemeAccount


@dataclass(frozen=True, kw_only=True)
class IndependentEligibility:
    state: str
    message: str
    eligibility_policy: str = ""
    original_date: date | None = None
    required_payments: int | None = None
    qualified_payments: int = 0
    completion_date: date | None = None
    count_verified_at: datetime | None = None
    rule_satisfied: bool = False
    positive_entitlement: bool = False
    benefit_review_required: bool = False

    @property
    def policy_eligible(self):
        return self.state == "ELIGIBLE"


def _verified_principal(account, payments, now):
    """Validate real source credit only; no benefit or settlement balance inference."""
    from .inr_selectors import get_inr_principal_summary

    quantity = Decimal(0)
    for c in payments:
        validate_real_instalment_channel(c)
        c.full_clean()
        if c.status not in ("PAID", "REVERSED"):
            raise ValidationError("Payment history requires reconciliation.")
        if c.paid_at is None or c.paid_at > now or c.paid_at < c.created_at:
            raise ValidationError("Payment verification time requires review.")
        if account.savings_mode == "INR_CREDIT":
            continue  # The source-linked INR ledger validates receipt/correction evidence below.
        allocation = getattr(c, "metal_allocation", None)
        if (allocation is None or not c.scheme_rate_id or c.rate_locked_at is None
                or allocation.created_at > now or c.rate_locked_at > c.paid_at
                or allocation.metal_grade_id != account.metal_grade_id
                or allocation.metal != account.savings_mode
                or allocation.scheme_rate_id != c.scheme_rate_id
                or c.scheme_rate.metal_grade_id != account.metal_grade_id
                or c.scheme_rate.rate_per_gram <= 0
                or allocation.quantity != (c.amount / c.scheme_rate.rate_per_gram).quantize(
                    Decimal("0.000001"), rounding=ROUND_HALF_UP)):
            raise ValidationError("Exact-grade source allocation requires review.")
        if c.payment_channel == "IN_STORE_CASH":
            receipt, correction = getattr(c, "cash_receipt", None), getattr(c, "cash_reversal", None)
            if (receipt is None or receipt.receipt_reference != c.gateway_reference
                    or receipt.received_at != c.paid_at or not receipt.received_by_label.strip()
                    or (c.status == "REVERSED") != (correction is not None)):
                raise ValidationError("Showroom source/correction evidence requires review.")
            if correction and (not correction.reason.strip() or not correction.processed_by_label.strip()
                    or not c.paid_at <= correction.reversed_at <= now):
                raise ValidationError("Cash correction evidence requires review.")
        else:
            if not c.gateway_order_id or not c.gateway_reference:
                raise ValidationError("Verified live payment identity is required.")
            # A callback signature is retained only after the existing authenticated
            # capture path confirms payment; webhook-only captures retain the event.
            captures = PaymentWebhookEvent.objects.filter(contribution=c, gateway="razorpay",
                gateway_mode="live", event_type="payment.captured", status="PROCESSED",
                gateway_order_id=c.gateway_order_id, gateway_reference=c.gateway_reference,
                processed_at__lte=now)
            callback = (len(c.gateway_signature) == 64 and all(
                char in "0123456789abcdefABCDEF" for char in c.gateway_signature))
            if not callback and not captures.exists():
                raise ValidationError("Retained live capture verification is required.")
        if c.status == "PAID":
            quantity += allocation.quantity
    if account.savings_mode == "INR_CREDIT":
        summary = get_inr_principal_summary(account)
        if summary.needs_review:
            raise ValidationError("INR source evidence requires review.")
        return summary.principal_recorded > 0
    return quantity > 0


def get_independent_eligibility(account, *, as_of=None):
    """Read CURRENT server-time evidence for all five approved schema-2 families.

    An arbitrary as-of date cannot backdate verification or grant future rights.
    Tests can control the server clock; historical replay is deliberately unsupported.
    Reload the account and frozen contract to avoid stale/caller-modified snapshots.
    Operational readiness remains separate, even when this projection says ELIGIBLE.
    """
    now = timezone.now()
    today = now.astimezone(AGREEMENT_TIMEZONE).date()
    if as_of is not None and (type(as_of) is not date or as_of != today):
        raise ValidationError("Independent eligibility uses today's server date, not historical replay or a future forecast.")
    account = SchemeAccount.objects.select_related("configuration_snapshot", "plan_revision", "metal_grade").get(pk=account.pk)
    if account.agreement_schema_version != 2:
        raise ValidationError("Use the existing eligibility rules for legacy agreements.")
    values = {}

    def result(state, message):
        return IndependentEligibility(state=state, message=message, **values)

    try:
        terms = validate_independent_account_terms(account)
    except ValidationError:
        return result("REVIEW", "The frozen agreement requires review; no eligibility is confirmed.")
    policy = terms.policy
    values.update(eligibility_policy=policy.eligibility, original_date=terms.duration_not_before,
        required_payments=policy.required_count, benefit_review_required=policy.benefit_kind != "NONE")
    if account.status == "CANCELLED":
        return result("CANCELLED", "This unused agreement is cancelled; retained terms do not permit payment or settlement.")
    if account.status == "REDEEMED":
        return result("CLOSED", "This agreement is closed; retained payment history is not a new entitlement.")
    from .closure_selectors import accepted_closure
    if (account.status == "CLOSURE_PENDING" or accepted_closure(account)
            or account.redemptions.exists() or account.inr_settlements.exists()):
        return result("CLOSURE_PENDING", "Inspect the full closure/disposition history. This progress view cannot authorize another settlement.")

    periods, qualified = [], []
    review = pending = False
    try:
        if policy.obligation == "REQUIRED_MONTHLY":
            from .instalment_selectors import validated_instalment_periods, instalment_payment_ledger_summary
            periods = validated_instalment_periods(account)
            ledger = instalment_payment_ledger_summary(account_id=account.pk)
            claims = list(InstalmentReservation.objects.filter(period__scheme_account=account).select_related(
                "period", "contribution").prefetch_related("decisions"))
            qualified = [c for c in claims if c.state == "QUALIFIED"]
            if ledger["integrity_errors"] or len(qualified) != ledger["qualified_payments"] or len(qualified) > policy.required_count:
                raise ValidationError("Qualification history requires review.")
            verified = []
            for claim in qualified:
                decision = max(claim.decisions.all(), key=lambda d: d.sequence)
                if (decision.state != "QUALIFIED" or decision.created_at > now
                        or decision.latest_at is None or decision.latest_at > now
                        or claim.contribution.paid_at is None or claim.contribution.paid_at > now
                        or claim.period.starts_on > today):
                    raise ValidationError("Qualification has not been verified at the current instant.")
                verified.append(max(decision.created_at, claim.contribution.paid_at))
            values["qualified_payments"] = len(qualified)
            if len(qualified) == policy.required_count:
                values["count_verified_at"] = max(verified)
            review = any(ledger[k] for k in ("outage_held_accounts", "unresolved_capture_events",
                "review_required", "awaiting_timing", "order_requests_pending", "paid_unallocated"))
            pending = any(c.state == "RESERVED" for c in claims)
        elif account.instalment_periods.exists():
            raise ValidationError("An optional agreement cannot have required instalment periods.")

        # Rule progress is independent of benefit awards and financial holds.
        count_complete = values.get("count_verified_at") is not None
        if policy.eligibility == "COUNT":
            values["rule_satisfied"] = count_complete
            if count_complete:
                values["completion_date"] = values["count_verified_at"].astimezone(AGREEMENT_TIMEZONE).date()
        elif policy.eligibility == "DURATION_AND_COUNT":
            if count_complete:
                completion = max(terms.duration_not_before, max(c.period.ends_before for c in qualified))
                values.update(completion_date=completion, rule_satisfied=today >= completion)
        elif policy.eligibility == "DURATION":
            values.update(completion_date=terms.duration_not_before, rule_satisfied=today >= terms.duration_not_before)

        payments = list(account.contributions.select_related("scheme_rate", "metal_allocation", "cash_receipt", "cash_reversal").order_by("pk"))
        sources = account.contributions.all()
        orders = sources.exclude(gateway_order_id="").filter(gateway_order_id__isnull=False)
        if PaymentWebhookEvent.objects.filter(Q(contribution__in=sources) | Q(
                gateway_order_id__in=orders.values("gateway_order_id"))).exclude(status__in=["PROCESSED", "IGNORED"]).exists():
            review = True
        # Local failure/abandonment is not provider cancellation. Never present it
        # as settled exposure, even if a separate qualified count is complete.
        if any(c.status in ("FAILED", "ABANDONED", "PAID_UNALLOCATED") for c in payments):
            review = True
        pending |= any(c.status == "PENDING" for c in payments)
        if policy.obligation == "OPTIONAL":
            from .independent_payment_selectors import require_optional_order_integrity
            require_optional_order_integrity(account)
        values["positive_entitlement"] = _verified_principal(
            account, [c for c in payments if c.status in ("PAID", "REVERSED")], now)
        if policy.eligibility == "ANYTIME":
            values["rule_satisfied"] = values["positive_entitlement"]
    except ValidationError:
        return result("REVIEW", "Payment, source or schedule evidence requires review. Recorded principal is retained; no eligibility is confirmed.")

    if review:
        return result("REVIEW", "Resolve the payment or outage hold. Rule progress does not release funds or award a benefit.")
    if pending:
        return result("PAYMENT_PENDING", "Verify or reconcile the existing payment before full-settlement review.")
    if today < terms.start_date:
        return result("NOT_STARTED", "The agreement has not started.")
    if not values["positive_entitlement"]:
        return result("NO_ENTITLEMENT", "No positive verified principal is recorded. Reaching a date alone does not create money or metal.")
    if values.get("rule_satisfied"):
        return result("ELIGIBLE", "Principal eligibility rules are met. Full settlement still needs separate showroom review and customer authorization; this is not a bonus or discount award.")
    if policy.eligibility == "DURATION" or (policy.eligibility == "DURATION_AND_COUNT" and count_complete):
        return result("WAITING_DURATION" if policy.eligibility == "DURATION" else "WAITING_PERIOD_END",
            "Verified principal is retained. Normal eligibility waits for the recorded duration and, where required, final qualifying period end.")
    if periods and today >= periods[-1].ends_before:
        return result("DISCONTINUATION_REVIEW", "Available payment windows ended without the required count. Review early full closure; paid principal is not forfeited.")
    return result("COLLECTING", "Required verified payments remain. Attempts, future windows and benefit promises do not count as completed instalments.")
