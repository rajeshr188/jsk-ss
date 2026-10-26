"""Owner review of an uncertain create-order response; GET never calls Razorpay."""
from django import forms
from django.core import signing
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.shortcuts import get_object_or_404, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from django.views.decorators.vary import vary_on_cookie

from .checkout_services import recover_order_identity
from .models import RazorpayOrderRequest
from .payments import PaymentGatewayError
from .permissions import owner_required

SALT = "schemes.checkout-order-identity.v1"


class OrderIdentityRecoveryForm(forms.Form):
    order_id = forms.RegexField(r"^order_[A-Za-z0-9_]+$", max_length=120, label="Provider order ID")
    reason = forms.CharField(max_length=2000, widget=forms.Textarea(attrs={"rows": 2}))
    evidence_reference = forms.CharField(max_length=254, label="Provider investigation reference")
    review_token = forms.CharField(required=False, widget=forms.HiddenInput, max_length=4096)
    confirmed = forms.BooleanField(required=False, label="I reviewed this exact order. Recovering its identity does not reopen checkout or credit money.")
    action = forms.ChoiceField(choices=[("INSPECT", "Inspect"), ("APPLY", "Recover identity")])

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("order_id", "reason", "evidence_reference"):
            self.fields[name].widget.attrs["class"] = "form-control"
        self.fields["confirmed"].widget.attrs["class"] = "form-check-input"


def review_identity(intent, owner_id, candidate):
    c = intent.contribution
    return dict(owner=owner_id, request=str(intent.token), contribution=c.pk,
        status=c.status, amount=str(c.amount), rate=c.scheme_rate_id, mode=c.gateway_mode,
        deadline=c.checkout_expires_at.isoformat() if c.checkout_expires_at else None,
        order=c.gateway_order_id, candidate=candidate)


@never_cache
@vary_on_cookie
@owner_required
@require_http_methods(["GET", "POST"])
def checkout_identity_recovery(request, contribution_id):
    intent = get_object_or_404(RazorpayOrderRequest.objects.select_related("contribution__scheme_account"),
        contribution_id=contribution_id)
    form = OrderIdentityRecoveryForm(request.POST if request.method == "POST" else None)
    inspected = applied = False
    if request.method == "POST" and form.is_valid():
        try:
            apply = form.cleaned_data["action"] == "APPLY"
            identity = review_identity(intent, request.user.pk, form.cleaned_data["order_id"])
            if apply:
                try:
                    reviewed = signing.loads(form.cleaned_data["review_token"], salt=SALT, max_age=600)
                except signing.BadSignature:
                    raise ValidationError("Provider review is missing or expired. Inspect again.") from None
                if reviewed != identity or not form.cleaned_data["confirmed"]:
                    raise ValidationError("Review this exact order and confirm its identity first.")
            recover_order_identity(contribution_id=contribution_id, order_id=form.cleaned_data["order_id"],
                actor=request.user, reason=form.cleaned_data["reason"],
                evidence_reference=form.cleaned_data["evidence_reference"], apply=apply)
            inspected, applied = True, apply
            if not apply:
                form = OrderIdentityRecoveryForm(initial={**form.cleaned_data,
                    "review_token": signing.dumps(identity, salt=SALT)})
            intent.contribution.refresh_from_db()
        except (ValidationError, PaymentGatewayError, ImproperlyConfigured) as error:
            message = " ".join(error.messages) if isinstance(error, ValidationError) else "Provider inspection is unavailable. Retain the original request and retry inspection."
            form.add_error(None, message)
    return render(request, "schemes/checkout_identity_recovery.html",
        dict(intent=intent, contribution=intent.contribution, form=form, inspected=inspected, applied=applied))
