"""Read-only qualification and eligibility projections; never settlement authority."""
from dataclasses import dataclass
from datetime import date

from django.core.exceptions import ValidationError
from django.db.models import Exists, OuterRef, Q
from django.utils import timezone

from .instalments import AGREEMENT_TIMEZONE, effective_account_windows, validate_real_instalment_channel, window_for_instant
from .models import Contribution, InstalmentOrderRecovery, InstalmentOutageResolution, InstalmentPaymentDecision, InstalmentReservation, InstalmentReview, PaymentWebhookEvent, SchemeInstalmentPeriod


@dataclass(frozen=True)
class MonthlyEligibility:
    state: str
    message: str
    original_date: date
    required_payments: int
    qualified_payments: int = 0
    completion_date: date | None = None
    forecast_date: date | None = None
    review_after: date | None = None
    allocation_pending: bool = False

    @property
    def policy_eligible(self):
        return self.state == "ELIGIBLE"


def get_monthly_eligibility(account, *, as_of=None):
    """Evaluate CURRENT evidence at a local calendar date, not historical replay.

    Dates are derived, never written back to the agreement. Forecasts assume one
    qualifying payment in every remaining available window and are not promises.
    This presentation selector is not a locking financial authorization boundary.
    Configured settlement requires separate locked full-settlement authorization.
    """
    from .instalments import has_monthly_instalments

    if account.agreement_schema_version == 2:
        raise ValidationError("Independent agreement eligibility workflows are not activated.")
    if not has_monthly_instalments(account):
        raise ValidationError("This agreement has no monthly-completion policy.")
    today = as_of or timezone.localdate(timezone=AGREEMENT_TIMEZONE)
    if type(today) is not date:
        raise ValidationError("Use a local calendar date for eligibility evaluation.")
    values = dict(original_date=account.eligible_from, required_payments=account.agreed_months)

    def result(state, message, **changes):
        return MonthlyEligibility(state=state, message=message, **(values | changes))

    if account.status == "CANCELLED":
        return result("CANCELLED", "This unused agreement has been cancelled. No further contributions or redemption are available; your login and records are retained.")

    try:
        periods = validated_instalment_periods(account)
        ledger = instalment_payment_ledger_summary(account_id=account.pk)
    except ValidationError:
        return result("REVIEW", "The recorded schedule requires showroom review; no eligibility is confirmed.")
    missing_allocation = account.contributions.filter(
        status="PAID", metal_allocation__isnull=True).exists()
    values.update(qualified_payments=ledger["qualified_payments"], review_after=periods[-1].ends_before,
                  allocation_pending=bool(ledger["paid_unallocated"] or missing_allocation))
    qualified_ids = set(InstalmentReservation.objects.filter(
        period__scheme_account=account, state="QUALIFIED").values_list("period_id", flat=True))
    qualified = [p for p in periods if p.pk in qualified_ids]
    if (ledger["integrity_errors"] or len(qualified) != ledger["qualified_payments"]
        or len(qualified) > account.agreed_months or any(p.starts_on > today for p in qualified)):
        return result("REVIEW", "Payment evidence requires showroom review; no eligibility is confirmed.")
    if account.status == "REDEEMED":
        return result("CLOSED", "This agreement has been redeemed.")
    from .closure_selectors import accepted_closure
    if accepted_closure(account):
        return result("CLOSURE_PENDING", "Closure is accepted, not completed. New payments are blocked; recorded entitlement and unresolved payments remain for review and full settlement.")
    if (ledger["outage_held_accounts"] or ledger["unresolved_capture_events"]
        or ledger["review_required"] or ledger["awaiting_timing"] or ledger["order_requests_pending"]):
        return result("REVIEW", "An outage or payment review is open. Do not pay again until the showroom resolves it. Recorded entitlement is retained.")
    if InstalmentReservation.objects.filter(period__scheme_account=account, state="RESERVED").exists():
        return result("PAYMENT_PENDING", "An existing checkout requires confirmation or provider reconciliation before another payment.")
    if len(qualified) == account.agreed_months:
        completion = max(account.eligible_from, qualified[-1].ends_before)
        return result("ELIGIBLE" if today >= completion else "WAITING_PERIOD_END",
                      "Required qualifying payments are complete. Both the agreed minimum duration and the final qualifying period must have ended. Full jewellery settlement requires showroom review and customer confirmation.",
                      completion_date=completion)
    if today >= periods[-1].ends_before:
        return result("DISCONTINUATION_REVIEW", "The available payment windows have ended without the required count. Contact the showroom for discontinuation review; paid entitlement is not forfeited.")
    remaining = [p for p in periods if p.ends_before > today and p.pk not in qualified_ids]
    needed = account.agreed_months - len(qualified)
    forecast = max(account.eligible_from, remaining[needed - 1].ends_before) if len(remaining) >= needed else None
    return result("NOT_STARTED" if today < account.start_date else "COLLECTING",
                  "Continue with one qualifying payment per available agreed monthly period. Any forecast depends on future payments; it is not confirmed eligibility."
                  if forecast else "The remaining windows cannot currently complete the required count. Contact the showroom to review your options; paid entitlement is retained.",
                  forecast_date=forecast)


def durable_order_request(contribution):
    intents = list(InstalmentPaymentDecision.objects.filter(reservation__contribution=contribution,
        state="ORDERING").select_related("reservation").order_by("sequence")[:2])
    if len(intents) != 1 or intents[0].request_token is None:
        raise ValidationError("No durable unique order-request identity exists; retain this case for provider investigation.")
    return intents[0]


def order_was_recovered(contribution_id):
    return InstalmentOrderRecovery.objects.filter(request_decision__reservation__contribution_id=contribution_id).exists()


def unresolved_instalment_captures(*, account_id=None, period_id=None):
    """Retained Live capture exceptions, including an order linked after delivery."""
    contributions = Contribution.objects.filter(
        scheme_account__configuration_snapshot__instalment_policy="MONTHLY_COMPLETION",
        payment_gateway="razorpay", gateway_mode="live")
    if account_id is not None:
        contributions = contributions.filter(scheme_account_id=account_id)
    if period_id is not None:
        contributions = contributions.filter(instalment_reservation__period_id=period_id)
    orders = contributions.exclude(gateway_order_id="").filter(gateway_order_id__isnull=False)
    return PaymentWebhookEvent.objects.filter(gateway="razorpay", gateway_mode="live",
        event_type="payment.captured").filter(
            Q(contribution_id__in=contributions.values("pk"))
            | Q(gateway_order_id__in=orders.values("gateway_order_id"))
        ).exclude(status__in=["PROCESSED", "IGNORED"])


def require_no_capture_exception(account):
    if unresolved_instalment_captures(account_id=account.pk).exists():
        raise ValidationError("A captured-payment exception requires provider reconciliation before another payment or timing acceptance. Do not pay again or manually clear the evidence.")


def open_outage_holds():
    return InstalmentReview.objects.filter(action="OUTAGE_HOLD", outage_resolution__isnull=True)


def require_no_outage_hold(account):
    if open_outage_holds().filter(period__scheme_account=account).exists():
        raise ValidationError("A recorded outage requires agreement review before further payment initiation. No missed-payment verdict or automatic grace is applied.")


def require_reconciled_outage_payments(account):
    """Conservative read guard; mutation caller must already hold the account lock."""
    summary = instalment_payment_ledger_summary(account_id=account.pk)
    claims = InstalmentReservation.objects.filter(period__scheme_account=account)
    contributions = account.contributions.all()
    unresolved_events = PaymentWebhookEvent.objects.filter(
        Q(contribution__in=contributions)
        | Q(gateway_order_id__in=contributions.exclude(gateway_order_id="").values("gateway_order_id"))
    ).exclude(status__in=["PROCESSED", "IGNORED"])
    if (summary["integrity_errors"] or summary["paid_unallocated"]
        or claims.exclude(state__in=["QUALIFIED", "REVERSED", "RELEASED"]).exists()
        or contributions.filter(status__in=["PENDING", "PAID_UNALLOCATED"]).exists()
        or contributions.filter(status="PAID", metal_allocation__isnull=True).exists()
        or unresolved_events.exists()):
        raise ValidationError("Reconcile all pending, uncertain, timing, allocation and webhook evidence before closing this hold.")


def validated_instalment_periods(account):
    expected = effective_account_windows(account)
    periods = list(account.instalment_periods.order_by("number"))
    if len(periods) != len(expected) or any(
        (p.number, p.starts_on, p.ends_before, p.amount) != (w.number, w.starts_on, w.ends_before, w.amount)
        for p, w in zip(periods, expected)
    ):
        raise ValidationError("The complete recorded schedule must pass review before attribution.")
    return periods


def current_instalment_period(account, *, exclude_contribution_id=None):
    """New-payment guard; caller holds the agreement lock when mutating."""
    from .plan_policies import require_current_payment_workflow
    require_current_payment_workflow(account)
    from .instalments import required_instalment_count
    from .closure_selectors import require_no_accepted_closure
    require_no_accepted_closure(account)
    require_no_outage_hold(account)
    require_no_capture_exception(account)
    if exclude_contribution_id is not None and order_was_recovered(exclude_contribution_id):
        raise ValidationError("The recovered provider order is reconciliation-only; its checkout cannot be resumed.")
    period = window_for_instant(validated_instalment_periods(account), timezone.now())
    if account.status != "ACTIVE" or period is None:
        raise ValidationError("No current payable monthly period exists for this active agreement.")
    claims = InstalmentReservation.objects.filter(period__scheme_account=account)
    if claims.filter(state="QUALIFIED").count() >= required_instalment_count(account):
        raise ValidationError("The required instalment count is already complete.")
    if exclude_contribution_id is not None:
        claims = claims.exclude(contribution_id=exclude_contribution_id)
    if claims.filter(state__in=["RESERVED", "ORDERING", "AWAITING", "REVIEW", "RELEASED_REVIEW"]).exists():
        raise ValidationError("Resolve the existing payment reservation or evidence review first.")
    if claims.filter(period=period).exclude(state__in=["REVERSED", "RELEASED"]).exists():
        raise ValidationError("This monthly period already has a qualifying payment.")
    orphan = Contribution.objects.filter(scheme_account=account,
        status__in=["PENDING", "PAID", "PAID_UNALLOCATED"], instalment_reservation__isnull=True)
    if exclude_contribution_id is not None:
        orphan = orphan.exclude(pk=exclude_contribution_id)
    if orphan.exists():
        raise ValidationError("A payment without a period reservation requires review.")
    return period


def resumable_instalment_contribution(account):
    claim = InstalmentReservation.objects.filter(period__scheme_account=account,
        state="RESERVED", contribution__status="PENDING", contribution__payment_gateway="razorpay").select_related("contribution").first()
    if claim is None:
        return None
    period = current_instalment_period(account, exclude_contribution_id=claim.contribution_id)
    if claim.period_id != period.pk or timezone.now() >= claim.expires_at:
        raise ValidationError("The reserved checkout expired; reconcile its provider order before retrying.")
    return claim.contribution


def instalment_payment_ledger_summary(*, account_id=None):
    claims = InstalmentReservation.objects.select_related(
        "contribution", "period__scheme_account",
    ).prefetch_related("decisions__webhook_event", "decisions__cash_receipt", "decisions__cash_reversal", "decisions__reconciliation_audit", "decisions__owner_review__source_decision")
    if account_id is not None:
        claims = claims.filter(period__scheme_account_id=account_id)
    unreserved = Contribution.objects.filter(
        scheme_account__configuration_snapshot__instalment_policy="MONTHLY_COMPLETION",
        instalment_reservation__isnull=True,
    )
    if account_id is not None:
        unreserved = unreserved.filter(scheme_account_id=account_id)
    unreserved_count = unreserved.count()
    result = dict(reservations=0, qualified_payments=0, review_required=0, reversed=0,
        order_requests_pending=0, awaiting_timing=0, released=0, paid_unallocated=0, unreserved_payments=unreserved_count,
        uncorrelated_order_requests=0, integrity_errors=unreserved_count)
    result["unresolved_capture_events"] = unresolved_instalment_captures(account_id=account_id).count()
    reviews = InstalmentReview.objects.all()
    if account_id is not None:
        reviews = reviews.filter(period__scheme_account_id=account_id)
    result["outage_held_accounts"] = reviews.filter(action="OUTAGE_HOLD", outage_resolution__isnull=True).values("period__scheme_account_id").distinct().count()
    result["owner_reviews"] = reviews.count()
    recoveries = InstalmentOrderRecovery.objects.select_related("request_decision__reservation__contribution", "decision")
    if account_id is not None:
        recoveries = recoveries.filter(request_decision__reservation__period__scheme_account_id=account_id)
    result["recovered_orders"] = recoveries.count()
    for recovery in recoveries.iterator(chunk_size=100):
        try:
            recovery.full_clean()
        except ValidationError:
            result["integrity_errors"] += 1
    review_sequences = {}
    for review in reviews.select_related("reservation", "source_decision", "qualification_decision").order_by("period_id", "sequence").iterator(chunk_size=100):
        expected = review_sequences.get(review.period_id, 0) + 1
        review_sequences[review.period_id] = review.sequence
        if review.sequence != expected or not review.reason.strip() or not review.evidence_reference.strip() or not review.actor_label.strip():
            result["integrity_errors"] += 1
        if review.reservation_id and review.reservation.period_id != review.period_id:
            result["integrity_errors"] += 1
        if review.action == "ACCEPT_TIMING":
            qualification = getattr(review, "qualification_decision", None)
            if (review.source_decision is None or review.source_decision.reservation_id != review.reservation_id
                or qualification is None or qualification.reservation_id != review.reservation_id):
                result["integrity_errors"] += 1
    resolutions = InstalmentOutageResolution.objects.select_related("hold", "period", "scheme_account", "compensation_period")
    if account_id is not None:
        resolutions = resolutions.filter(scheme_account_id=account_id)
    result["outage_resolutions"] = resolutions.count()
    result["outage_compensation_months"] = resolutions.filter(outcome="COMPENSATE").count()
    checked_accounts = set()
    for resolution in resolutions.iterator(chunk_size=100):
        try:
            resolution.full_clean()
            if resolution.scheme_account_id not in checked_accounts:
                validated_instalment_periods(resolution.scheme_account)
                checked_accounts.add(resolution.scheme_account_id)
        except ValidationError:
            result["integrity_errors"] += 1
    for claim in claims.iterator(chunk_size=100):
        result["reservations"] += 1
        contribution = claim.contribution
        errors = 0
        if claim.period.scheme_account_id not in checked_accounts:
            try:
                validated_instalment_periods(claim.period.scheme_account)
            except ValidationError:
                errors += 1
            checked_accounts.add(claim.period.scheme_account_id)
        try:
            validate_real_instalment_channel(contribution)
        except ValidationError:
            errors += 1
        if contribution.scheme_account_id != claim.period.scheme_account_id or contribution.amount != claim.period.amount:
            errors += 1
        decisions = sorted(claim.decisions.all(), key=lambda row: row.sequence)
        if (not decisions or decisions[0].state != "RESERVED"
            or decisions[-1].state != claim.state
            or [row.sequence for row in decisions] != list(range(1, len(decisions) + 1))):
            errors += 1
        reversed_seen = False
        for decision in decisions:
            if decision.reason_code == "PROVIDER_ORDER_RECOVERED" and not hasattr(decision, "order_recovery"):
                errors += 1
            if reversed_seen:
                errors += 1
            reversed_seen |= decision.state == "REVERSED"
            for source in (decision.webhook_event, decision.cash_receipt, decision.cash_reversal, decision.reconciliation_audit):
                if source and source.contribution_id != contribution.pk:
                    errors += 1
            if decision.state == "QUALIFIED" and (
                decision.earliest_at is None or decision.latest_at is None
                or decision.latest_at < decision.earliest_at
                or window_for_instant([claim.period], decision.earliest_at) is None
                or window_for_instant([claim.period], decision.latest_at) is None
                or decision.latest_at >= claim.expires_at
            ):
                errors += 1
            if decision.cash_receipt and (
                contribution.payment_channel != "IN_STORE_CASH"
                or decision.earliest_at != decision.cash_receipt.received_at
                or decision.latest_at != decision.cash_receipt.received_at
            ):
                errors += 1
            if decision.owner_review:
                review = decision.owner_review
                source = review.source_decision
                if (review.action != "ACCEPT_TIMING" or review.reservation_id != claim.pk
                    or review.period_id != claim.period_id or source is None
                    or source.reservation_id != claim.pk or source.sequence >= decision.sequence
                    or (source.earliest_at, source.latest_at) != (decision.earliest_at, decision.latest_at)
                    or decision.actor_label != review.actor_label):
                    errors += 1
            if decision.webhook_event and (
                decision.webhook_event.status != ("REVIEW_REQUIRED" if decision.state == "RELEASED_REVIEW" else "PROCESSED") or decision.webhook_event.gateway_mode != "live"
                or decision.webhook_event.event_type != "payment.captured"
                or (decision.state != "RELEASED_REVIEW" and decision.webhook_event.gateway_reference != contribution.gateway_reference)
                or decision.webhook_event.gateway_order_id != contribution.gateway_order_id
            ):
                errors += 1
        if claim.state == "QUALIFIED":
            if contribution.status not in ("PAID", "PAID_UNALLOCATED"):
                errors += 1
            result["qualified_payments"] += 1
        if claim.state in ("REVIEW", "RELEASED_REVIEW"):
            result["review_required"] += 1
        if claim.state == "AWAITING":
            result["awaiting_timing"] += 1
            if contribution.status not in ("PAID", "PAID_UNALLOCATED"):
                errors += 1
        if claim.state == "ORDERING":
            result["order_requests_pending"] += 1
            if not decisions or decisions[-1].request_token is None:
                result["uncorrelated_order_requests"] += 1
            if contribution.status not in ("PENDING", "FAILED") or contribution.gateway_order_id:
                errors += 1
        if claim.state in ("RELEASED", "RELEASED_REVIEW"):
            result["released"] += 1
            if contribution.status != "ABANDONED":
                errors += 1
        if claim.state == "REVERSED":
            result["reversed"] += 1
            if contribution.status != "REVERSED":
                errors += 1
        if contribution.status == "REVERSED" and claim.state != "REVERSED":
            errors += 1
        if contribution.status == "PAID_UNALLOCATED":
            result["paid_unallocated"] += 1
        result["integrity_errors"] += errors
    return result


def owner_instalment_review_periods():
    """Bounded by the view's paginator; includes periods with no payment for outage reports."""
    return SchemeInstalmentPeriod.objects.filter(starts_on__lte=timezone.localdate(timezone=AGREEMENT_TIMEZONE)).exclude(scheme_account__status="CANCELLED").select_related(
        "scheme_account__customer", "scheme_account__metal_grade",
    ).annotate(
        has_payment_review=Exists(InstalmentReservation.objects.filter(period_id=OuterRef("pk"),
            state__in=["ORDERING", "AWAITING", "REVIEW", "RELEASED_REVIEW"])),
        has_capture_review=Exists(unresolved_instalment_captures(period_id=OuterRef(OuterRef("pk")))),
        outage_held=Exists(open_outage_holds().filter(period_id=OuterRef("pk"))),
    ).order_by("-has_capture_review", "-has_payment_review", "-outage_held", "-starts_on", "-pk")
