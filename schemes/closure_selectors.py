"""Read-only closure review. Nothing here authorizes financial settlement."""
from django.core.exceptions import ValidationError
from django.db.models import Q

from schemes.payment_refund_selectors import unresolved_payment_events

from .models import SchemeClosureRequest, PaymentWebhookEvent


def accepted_closure(account):
    return account.configuration_snapshot_id and SchemeClosureRequest.objects.filter(
        scheme_account_id=account.pk).filter(Q(status="ACCEPTED") | Q(events__action="ACCEPT")).exists()


def require_no_accepted_closure(account):
    if account.status == "CANCELLED":
        raise ValidationError("This unused agreement is cancelled and cannot accept new payments.")
    if accepted_closure(account):
        raise ValidationError("Closure has been accepted. New contributions and checkout resumption are blocked; existing payments still require reconciliation.")


def closure_requests():
    return SchemeClosureRequest.objects.select_related(
        "scheme_account__customer", "scheme_account__metal_grade", "requested_by"
    ).prefetch_related("events")


def closure_payment_review(account):
    """Current investigation counts, NEVER an unused/settleable verdict.

    Expired/abandoned orders can still capture. Retain every order/history for B2/B3;
    zero balances or zero counters cannot authorize cancellation or full settlement.
    """
    payments = account.contributions.all()
    orders = payments.exclude(gateway_order_id="").filter(gateway_order_id__isnull=False)
    events = PaymentWebhookEvent.objects.filter(
        Q(contribution__in=payments) | Q(gateway_order_id__in=orders.values("gateway_order_id"))
    )
    events = unresolved_payment_events(events)
    missing_entitlement = (Q(status="PAID", inr_principal_receipt__isnull=True)
        if account.savings_mode == "INR_CREDIT" else Q(status="PAID", metal_allocation__isnull=True))
    return {
        "payment_history": payments.count(),
        "pending_payments": payments.filter(status="PENDING").count(),
        "allocation_gaps": payments.filter(Q(status="PAID_UNALLOCATED") | missing_entitlement).count(),
        "unresolved_webhooks": events.count(),
        "provider_order_history": orders.count(),
        "redemption_history": account.redemptions.count(),
    }


def validate_closure_history(request):
    # Load immutable event-source links together. Keep the state-machine and
    # source validators below unchanged, including detection of missing links.
    events = list(request.events.select_related(
        "settlement__redemption__scheme_account", "settlement__closure", "settlement_correction__reversal",
        "inr_completion__proposal__scheme_account", "inr_resolution__proposal__scheme_account",
        "inr_completion__proposal__closure", "inr_resolution__proposal__closure",
    ).order_by("sequence"))
    state = None
    current_settlement = None
    for number, event in enumerate(events, 1):
        if event.sequence != number or not event.reason.strip() or not event.actor_label.strip():
            raise ValidationError("Closure evidence sequence or attribution requires review.")
        if number == 1:
            if (event.action != "REQUESTED" or event.resulting_status != "PENDING"
                or event.actor_id != request.requested_by_id or event.reason != request.reason
                or event.authorization_reference != request.authorization_reference):
                raise ValidationError("Closure request evidence requires review.")
            state = "PENDING"
        elif event.action == "NOTE" and state in ("PENDING", "ACCEPTED"):
            resolution = getattr(event, "inr_resolution", None)
            if resolution:
                from .inr_correction_selectors import validate_inr_resolution
                if state != "ACCEPTED":
                    raise ValidationError("INR correction requires an accepted closure.")
                validate_inr_resolution(resolution)
        elif state == "PENDING" and event.action in ("ACCEPT", "WITHDRAW", "REJECT"):
            state = {"ACCEPT": "ACCEPTED", "WITHDRAW": "WITHDRAWN", "REJECT": "REJECTED"}[event.action]
        elif state == "ACCEPTED" and event.action == "CANCEL":
            if event.authorization_reference:
                raise ValidationError("Cancellation must retain the original closure authorization, not replace it.")
            state = "CANCELLED"
        elif state == "ACCEPTED" and event.action == "SETTLE":
            from .settlement_selectors import validate_configured_settlement
            current_settlement = getattr(event, "settlement", None)
            inr_completion = getattr(event, "inr_completion", None)
            if (current_settlement is None) == (inr_completion is None):
                raise ValidationError("Full settlement source evidence is missing.")
            if inr_completion:
                from .inr_settlement_selectors import validate_inr_completion
                validate_inr_completion(inr_completion)
                current_settlement = inr_completion
            else:
                validate_configured_settlement(current_settlement)
            state = "SETTLED"
        elif state == "SETTLED" and event.action == "REVERSE":
            if request.scheme_account.savings_mode == "INR_CREDIT":
                from .inr_correction_selectors import validate_inr_resolution
                resolution = getattr(event, "inr_resolution", None)
                if resolution is None or resolution.proposal_id != current_settlement.proposal_id:
                    raise ValidationError("INR full-return sequence requires review.")
                validate_inr_resolution(resolution)
            else:
                correction = getattr(event, "settlement_correction", None)
                if correction is None or correction.settlement_id != current_settlement.pk:
                    raise ValidationError("Settlement reversal sequence requires review.")
            state = "ACCEPTED"
        else:
            raise ValidationError("Closure lifecycle evidence requires review.")
        if event.resulting_status != state:
            raise ValidationError("Closure event state is inconsistent.")
    if not events or request.status != state:
        raise ValidationError("Closure state does not match retained evidence.")
    if state == "SETTLED" and (request.scheme_account.status != "REDEEMED" or hasattr(current_settlement, "correction")):
        raise ValidationError("Completed settlement does not match its agreement or reversal state.")
    if state == "SETTLED" and request.scheme_account.savings_mode == "INR_CREDIT" and current_settlement.proposal.retired:
        raise ValidationError("Retired INR disposition cannot remain settled.")
    if state == "ACCEPTED" and current_settlement and request.scheme_account.status != "CLOSURE_PENDING":
        raise ValidationError("Reversed settlement must remain closed to new payments pending full settlement.")
    if state == "CANCELLED":
        if request.scheme_account.status != "CANCELLED":
            raise ValidationError("Cancellation evidence does not match agreement status.")
        require_unused_agreement(request.scheme_account)
    return len(events)


def require_unused_agreement(account):
    """Strict V1 proof, called under the agreement lock for cancellation.

    No net-balance inference: ANY attempt (including test, failed, abandoned or
    reversed), redemption, reservation or period investigation needs a separate
    disposition. Empty scheduled periods and closure notes themselves are allowed.
    Financial children are protected by their contribution/redemption foreign keys.
    """
    from .models import InstalmentReservation, InstalmentReview

    if (account.contributions.exists() or account.redemptions.exists()
        or InstalmentReservation.objects.filter(period__scheme_account=account).exists()
        or InstalmentReview.objects.filter(period__scheme_account=account).exists()
        or account.outage_resolutions.exists()):
        raise ValidationError("This agreement has payment, settlement or instalment-review history. It cannot be cancelled as unused; retain it for separate resolution and settlement review.")
