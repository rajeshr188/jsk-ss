"""Owner review of expired Checkout; no provider calls on GET."""
from dataclasses import asdict
from decimal import Decimal

from django import forms
from django.core import signing
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from django.views.decorators.vary import vary_on_cookie

from .models import Contribution
from .payments import PaymentGatewayError
from .permissions import owner_required
from .services import reconcile_abandoned_razorpay_contribution

REVIEW_SALT = "schemes.expired-checkout-review.v1"
REVIEW_MAX_AGE = 600


class OrderReconciliationForm(forms.Form):
    action = forms.ChoiceField(choices=[("INSPECT", "Check provider"), ("APPLY", "Close verified unpaid checkout")])
    reason = forms.CharField(max_length=500, widget=forms.Textarea(attrs={"rows": 2, "class": "form-control"}))
    review_token = forms.CharField(required=False, max_length=2048, widget=forms.HiddenInput)
    confirmed = forms.BooleanField(required=False, label="I reviewed the provider evidence and confirm closing only this unpaid attempt.")


def review_identity(contribution, owner_id):
    return dict(owner=owner_id, contribution=contribution.pk,
                account=contribution.scheme_account_id, status=contribution.status,
                order=contribution.gateway_order_id, mode=contribution.gateway_mode,
                amount=str(contribution.amount), rate=contribution.scheme_rate_id,
                deadline=contribution.checkout_expires_at.isoformat() if contribution.checkout_expires_at else None)


@never_cache
@vary_on_cookie
@owner_required
@require_http_methods(["GET", "POST"])
def order_reconciliation(request, contribution_id):
    contribution = get_object_or_404(
        Contribution.objects.select_related("scheme_account__customer"),
        pk=contribution_id, payment_gateway="razorpay",
    )
    form = OrderReconciliationForm(request.POST or None)
    result = None
    evidence = None
    can_apply = False
    if request.method == "POST" and form.is_valid():
        apply = form.cleaned_data["action"] == "APPLY"
        try:
            if not contribution.razorpay_checkout_expired:
                raise ValidationError("Only an expired pending checkout can be reviewed.")
            if apply:
                try:
                    reviewed = signing.loads(form.cleaned_data["review_token"], salt=REVIEW_SALT, max_age=REVIEW_MAX_AGE)
                except signing.BadSignature:
                    raise ValidationError("The provider review is missing, invalid or expired. Check provider again.") from None
                if reviewed != review_identity(contribution, request.user.pk):
                    raise ValidationError("This payment or owner differs from the reviewed record. Check provider again.")
                can_apply = True
                if not form.cleaned_data["confirmed"]:
                    raise ValidationError("Review the provider evidence and confirm closing this attempt.")
            result = reconcile_abandoned_razorpay_contribution(
                contribution_id=contribution.pk, cutoff=timezone.now(), apply=apply,
                performed_by=request.user, reason=form.cleaned_data["reason"],
            )
            evidence = asdict(result.inspection)
            for field in ("amount", "amount_paid", "amount_due"):
                evidence[field] = Decimal(evidence[field + "_subunits"]) / Decimal("100")
            contribution.refresh_from_db()
            can_apply = not apply and result.outcome == "ELIGIBLE_FOR_ABANDONMENT"
            if can_apply:
                form = OrderReconciliationForm(initial={
                    "reason": form.cleaned_data["reason"],
                    "review_token": signing.dumps(review_identity(contribution, request.user.pk), salt=REVIEW_SALT),
                })
        except (ImproperlyConfigured, PaymentGatewayError, ValidationError) as error:
            message = " ".join(error.messages) if isinstance(error, ValidationError) else "Provider inspection is unavailable. No payment status was changed; retry or investigate with Razorpay."
            form.add_error(None, message)
    return render(request, "schemes/order_reconciliation.html", {
        "contribution": contribution, "form": form, "result": result,
        "evidence": evidence, "can_apply": can_apply,
    })
