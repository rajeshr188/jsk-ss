"""Durable, idempotent online checkout. Financial confirmation stays in services."""
import uuid
from datetime import datetime, timezone as datetime_timezone

from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db import connection, transaction
from django.db.models import Q
from django.utils import timezone

from .models import Contribution, RazorpayCheckoutSubmission, RazorpayOrderRequest, RazorpayOrderRecovery, SchemeAccount
from .payments import PaymentGatewayError, PaymentGatewayValidationError, RAZORPAY_ID_PATTERN


UNCERTAIN = "The original checkout is awaiting provider reconciliation. Do not start another payment; contact the showroom."


class CheckoutPendingProviderError(PaymentGatewayError):
    status_code = 503


def _check_identity(contribution, account, amount, mode):
    if contribution.payment_gateway != "razorpay" or contribution.scheme_account_id != account.pk or contribution.amount != amount:
        raise ValidationError("This submission belongs to a different agreement or amount. Review the original payment.")
    if contribution.gateway_mode != mode:
        raise ValidationError("A Razorpay payment from a different provider mode is already pending; reconcile it first.")


def _check_resumption(contribution):
    if contribution.status in ("PAID", "PAID_UNALLOCATED", "ABANDONED", "FAILED", "REVERSED"):
        return
    if contribution.razorpay_checkout_expired:
        raise ValidationError("Checkout expired; provider reconciliation is required before a replacement payment.")
    request = RazorpayOrderRequest.objects.filter(contribution=contribution).first()
    if request and (not contribution.gateway_order_id or hasattr(request, "recovery")):
        raise PaymentGatewayError(UNCERTAIN)


def initiate_checkout(*, scheme_account, amount, contribution_date=None, gateway, submission_key=None, expected_latest_id=None):
    from .services import ensure_payment_initiation_allowed, initiate_contribution, validate_contribution_allowed, validate_contribution_amount

    # Otherwise a caller could roll back durable identity after the provider accepted it.
    if any(not getattr(block, "_from_testcase", False) for block in connection.atomic_blocks):
        raise ValidationError("Checkout creation cannot run inside another transaction.")
    if gateway.name != "razorpay" or gateway.mode not in ("test", "live"):
        raise ImproperlyConfigured("A mode-specific Razorpay gateway is required.")
    if expected_latest_id is not None and (type(expected_latest_id) is not int or expected_latest_id < 0):
        raise ValidationError("The payment history review is invalid.")
    try:
        key = uuid.UUID(str(submission_key)) if submission_key is not None else uuid.uuid4()
    except (ValueError, TypeError, AttributeError):
        raise ValidationError("A valid payment submission identifier is required.") from None

    created_new = False
    with transaction.atomic(durable=True):
        account = SchemeAccount.objects.select_for_update().get(pk=scheme_account.pk)
        from .instalments import has_monthly_instalments
        if account.agreement_schema_version != 1 or has_monthly_instalments(account):
            raise ValidationError("Configured checkout must use its retained reservation workflow.")
        amount = validate_contribution_amount(account, amount)
        if int(amount * 100) < 100:
            raise PaymentGatewayValidationError("Razorpay requires a minimum payment amount of INR 1.00.")
        submitted = RazorpayCheckoutSubmission.objects.select_related("contribution").filter(key=key).first()
        if submitted:
            contribution = submitted.contribution
            _check_identity(contribution, account, amount, gateway.mode)
            if contribution.status != "PENDING":
                return contribution
        else:
            if RazorpayOrderRequest.objects.filter(contribution__scheme_account=account).filter(
                    Q(contribution__status="FAILED") | ((Q(contribution__gateway_order_id__isnull=True)
                    | Q(contribution__gateway_order_id="")) & ~Q(contribution__status="PENDING"))).exists():
                raise ValidationError("Unresolved provider request evidence requires showroom reconciliation.")
            unresolved = Contribution.objects.filter(scheme_account=account).filter(
                Q(status="PENDING", payment_gateway="razorpay") | Q(status="PAID_UNALLOCATED")
            ).order_by("created_at", "pk")
            pending = list(unresolved[:2])
            if len(pending) > 1:
                raise ValidationError("Multiple earlier payment attempts require showroom reconciliation.")
            if pending:
                contribution = pending[0]
                if contribution.status == "PAID_UNALLOCATED":
                    raise ValidationError("Payment received; metal credit is pending. Do not pay again.")
                _check_identity(contribution, account, amount, gateway.mode)
            else:
                latest = Contribution.objects.filter(scheme_account=account).order_by("-pk").first()
                if expected_latest_id is not None and (latest.pk if latest else 0) != expected_latest_id:
                    if latest is None or latest.payment_gateway != "razorpay":
                        raise ValidationError("Payment history changed. Open your plan and review the recorded result.")
                    _check_identity(latest, account, amount, gateway.mode)
                    RazorpayCheckoutSubmission.objects.create(key=key, contribution=latest)
                    return latest
                contribution = initiate_contribution(scheme_account=account, amount=amount,
                    payment_gateway="razorpay", gateway_mode=gateway.mode, contribution_date=contribution_date)
                created_new = True
            RazorpayCheckoutSubmission.objects.create(key=key, contribution=contribution)
        # Retain aliases even while creation is in flight or checkout is held. A
        # later retry of either tab must still resolve to this same contribution.
        request = RazorpayOrderRequest.objects.filter(contribution=contribution).first()
        if request and (request.amount_subunits != contribution.amount * 100
                or request.gateway_mode != contribution.gateway_mode
                or request.scheme_rate_id != contribution.scheme_rate_id
                or request.checkout_expires_at != contribution.checkout_expires_at):
            raise ValidationError("The retained order request differs from this payment; showroom review is required.")
        if contribution.razorpay_checkout_expired or (request and hasattr(request, "recovery")):
            return contribution
        if request and not contribution.gateway_order_id:
            return contribution
        validate_contribution_allowed(account, amount, contribution_date,
            exclude_contribution_id=contribution.pk)
        ensure_payment_initiation_allowed(metal_grade=account.metal_grade, lock=True)
        if contribution.gateway_order_id:
            return contribution
        # A legacy contribution without an ID may already have reached the provider.
        if not created_new:
            return contribution
        request = RazorpayOrderRequest.objects.create(contribution=contribution,
            amount_subunits=int(contribution.amount * 100), gateway_mode=gateway.mode, scheme_rate_id=contribution.scheme_rate_id,
            checkout_expires_at=contribution.checkout_expires_at)

    if created_new:
        # Exactly one create call. Every exception leaves the committed request pending.
        try:
            order = gateway.create_order(contribution)
            with transaction.atomic():
                account = SchemeAccount.objects.select_for_update().get(pk=account.pk)
                contribution = Contribution.objects.select_for_update().get(pk=contribution.pk)
                if (contribution.status != "PENDING" or contribution.gateway_order_id
                        or contribution.scheme_account_id != account.pk or contribution.payment_gateway != "razorpay"
                        or contribution.amount * 100 != request.amount_subunits or contribution.gateway_mode != request.gateway_mode
                        or contribution.scheme_rate_id != request.scheme_rate_id
                        or contribution.checkout_expires_at != request.checkout_expires_at):
                    raise ValidationError("The original order request changed; provider reconciliation is required.")
                if (not isinstance(order.order_id, str) or not order.order_id.startswith("order_")
                        or len(order.order_id) > 120 or not RAZORPAY_ID_PATTERN.fullmatch(order.order_id)
                        or type(order.amount_subunits) is not int or order.amount_subunits != request.amount_subunits
                        or order.currency != "INR"):
                    raise PaymentGatewayError(UNCERTAIN)
                contribution.gateway_order_id = order.order_id
                contribution.full_clean()
                contribution.save(update_fields=["gateway_order_id"])
        except PaymentGatewayError:
            raise CheckoutPendingProviderError(UNCERTAIN) from None
    # Retain returned identity even if a pause/expiry occurred while awaiting the provider.
    with transaction.atomic():
        account = SchemeAccount.objects.select_for_update().get(pk=account.pk)
        contribution.refresh_from_db()
        if contribution.status != "PENDING":
            return contribution
        _check_resumption(contribution)
        validate_contribution_allowed(account, contribution.amount, exclude_contribution_id=contribution.pk)
        ensure_payment_initiation_allowed(metal_grade=account.metal_grade, lock=True)
        return contribution


def recover_order_identity(*, contribution_id, order_id, actor, reason, evidence_reference, apply=False, gateway=None):
    from .services import _validate_owner, record_audit_event
    from .payments import get_payment_gateway
    _validate_owner(actor)
    if not reason.strip() or not evidence_reference.strip() or len(evidence_reference) > 254:
        raise ValidationError("Record the reason and provider investigation reference.")
    gateway = gateway or get_payment_gateway()
    contribution = Contribution.objects.get(pk=contribution_id)
    request = RazorpayOrderRequest.objects.get(contribution=contribution)
    if contribution.status != "PENDING" or contribution.gateway_order_id or hasattr(request, "recovery"):
        raise ValidationError("Only an unresolved order identity may be recovered.")
    if gateway.name != "razorpay" or gateway.mode != contribution.gateway_mode:
        raise ValidationError("The configured provider mode differs from the original request.")
    if (request.gateway_mode != contribution.gateway_mode or request.amount_subunits != contribution.amount * 100
            or request.scheme_rate_id != contribution.scheme_rate_id
            or request.checkout_expires_at != contribution.checkout_expires_at):
        raise ValidationError("The retained order request differs from this payment; showroom review is required.")
    identity = gateway.inspect_order_identity(order_id=order_id)
    if (identity.order_id != order_id or identity.receipt != request.receipt
            or identity.contribution_id != str(contribution.pk) or identity.request_token != str(request.token)
            or identity.amount_subunits != request.amount_subunits or identity.currency != "INR"
            or identity.status not in ("created", "attempted", "paid")
            or identity.created_at < int(request.created_at.timestamp())
            or identity.created_at > timezone.now().timestamp()):
        raise ValidationError("The authenticated provider order does not exactly match the original request.")
    if not apply:
        return identity
    with transaction.atomic():
        SchemeAccount.objects.select_for_update().get(pk=contribution.scheme_account_id)
        locked = Contribution.objects.select_for_update().get(pk=contribution.pk)
        if (locked.status != "PENDING" or locked.gateway_order_id or locked.amount != contribution.amount
                or locked.gateway_mode != contribution.gateway_mode or locked.scheme_rate_id != request.scheme_rate_id
                or locked.checkout_expires_at != request.checkout_expires_at
                or locked.amount * 100 != request.amount_subunits):
            raise ValidationError("The original request changed; inspect again.")
        locked.gateway_order_id = identity.order_id
        locked.full_clean()
        locked.save(update_fields=["gateway_order_id"])
        RazorpayOrderRecovery.objects.create(request=request, gateway_order_id=identity.order_id,
            provider_created_at=datetime.fromtimestamp(identity.created_at, tz=datetime_timezone.utc),
            recovered_by=actor, reason=reason.strip(), evidence_reference=evidence_reference.strip())
        record_audit_event(action="PAYMENT_ORDER_RECONCILIATION", actor=actor, reason=reason.strip(),
            scheme_account=locked.scheme_account, contribution=locked,
            details=dict(outcome="ORDER_IDENTITY_RECOVERED", request_token=str(request.token),
                         gateway_order_id=identity.order_id, evidence_reference=evidence_reference.strip(),
                         gateway_mode=locked.gateway_mode, checkout_reopened=False))
    return identity
