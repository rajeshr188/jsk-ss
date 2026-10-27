"""Owner-only exact identity recovery; no provider request on GET."""
import uuid

from django import forms
from django.contrib import messages
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from django.views.decorators.vary import vary_on_cookie

from .models import OptionalPaymentOrderRequest
from .optional_orders import recover_optional_order
from .payments import PaymentGatewayError
from .permissions import owner_required


class OptionalOrderRecoveryForm(forms.Form):
    order_id = forms.RegexField(regex=r"^order_[A-Za-z0-9_]+$", max_length=120,
        label="Candidate Razorpay order ID",
        help_text="Find the original receipt reference in the correct Live merchant account or through support. The server verifies the candidate independently.")
    reason = forms.CharField(max_length=2000, widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Explain the investigation. Do not paste passwords, tokens or raw provider payloads.")
    evidence_reference = forms.CharField(max_length=254, label="Investigation or support reference")
    idempotency_key = forms.UUIDField(widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.initial["idempotency_key"] = uuid.uuid4()
        for field in self.fields.values():
            if not field.widget.is_hidden:
                field.widget.attrs["class"] = "form-control"


@never_cache
@vary_on_cookie
@owner_required
@require_http_methods(["GET", "POST"])
def optional_order_recovery(request, contribution_id):
    intent = get_object_or_404(OptionalPaymentOrderRequest.objects.select_related(
        "contribution__scheme_account", "binding"), contribution_id=contribution_id)
    form = OptionalOrderRecoveryForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        try:
            recover_optional_order(contribution_id=intent.contribution_id,
                actor=request.user, **form.cleaned_data)
        except ValidationError as error:
            form.add_error(None, " ".join(error.messages))
        except (ImproperlyConfigured, PaymentGatewayError):
            form.add_error(None, "Provider identity verification is unavailable. The request remains unresolved; retain it for investigation.")
        else:
            messages.success(request, "Order identity recorded for reconciliation only. No payment was confirmed, no entitlement was credited and checkout was not renewed.")
            return redirect("schemes:optional_order_recovery", contribution_id=contribution_id)
    return render(request, "schemes/optional_order_recovery.html", {
        "intent": intent, "contribution": intent.contribution,
        "binding": getattr(intent, "binding", None), "form": form,
    })
