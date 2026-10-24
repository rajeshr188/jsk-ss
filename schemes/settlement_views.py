import uuid

from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from .models import SchemeClosureRequest
from .permissions import owner_required
from .settlements import preview_full_settlement, reverse_configured_settlement, settle_configured_agreement


class SettlementForm(forms.Form):
    preview_token = forms.CharField(widget=forms.HiddenInput)
    idempotency_key = forms.UUIDField(initial=uuid.uuid4, widget=forms.HiddenInput)
    invoice_reference = forms.CharField(max_length=120, label="Jewellery invoice / sales reference")
    authorization_reference = forms.CharField(max_length=254, label="Customer confirmation reference",
        help_text="Retained evidence that the customer confirmed this full exact-grade quantity and jewellery fulfilment. A closure request alone is not delivery confirmation.")
    reason = forms.CharField(max_length=2000, widget=forms.Textarea(attrs={"rows": 3}))
    confirmed = forms.BooleanField(label="I confirm actual jewellery fulfilment against the invoice and customer agreement to the full six-decimal quantity. No cash payout, fee or bonus is being recorded.")


class SettlementReversalForm(forms.Form):
    settlement_id = forms.IntegerField(widget=forms.HiddenInput)
    expected_sequence = forms.IntegerField(widget=forms.HiddenInput)
    idempotency_key = forms.UUIDField(initial=uuid.uuid4, widget=forms.HiddenInput)
    reason = forms.CharField(max_length=2000, widget=forms.Textarea(attrs={"rows": 3}))
    authorization_reference = forms.CharField(max_length=254, label="Invoice correction / restoration evidence reference")
    confirmed = forms.BooleanField(label="The correction is authorized and restores the full entitlement. This does not reopen payments or erase the original invoice history.")


@never_cache
@owner_required
@require_http_methods(["GET", "POST"])
def settlement_workspace(request, request_id):
    closure = get_object_or_404(SchemeClosureRequest.objects.select_related("scheme_account__metal_grade"),
        pk=request_id, scheme_account__configuration_snapshot__isnull=False)
    reverse_post = request.method == "POST" and request.POST.get("operation") == "reverse"
    form = SettlementForm(request.POST if request.method == "POST" and not reverse_post else None)
    correction_form = SettlementReversalForm(request.POST if reverse_post else None, auto_id="correction_%s")
    if request.method == "POST":
        selected = correction_form if reverse_post else form
        if selected.is_valid():
            values = selected.cleaned_data.copy()
            values.pop("confirmed")
            try:
                if reverse_post:
                    get_object_or_404(closure.settlements, pk=values["settlement_id"])
                    reverse_configured_settlement(actor=request.user, **values)
                else:
                    redemption = settle_configured_agreement(request_id=closure.pk, actor=request.user, **values)
            except ValidationError as error:
                selected.add_error(None, error.messages)
            else:
                if reverse_post:
                    message = "Settlement correction recorded; payments remain blocked. Review the current retained history."
                elif hasattr(redemption, "reversal"):
                    message = "This submission was already recorded and subsequently reversed. No new settlement was created; review the current retained history."
                else:
                    message = "Full jewellery settlement recorded. The agreement is closed; customer login is unchanged."
                messages.success(request, message)
                return redirect("schemes:configured_settlement", request_id=closure.pk)
    evidence = token = None
    blocked = ""
    if closure.status == "ACCEPTED":
        try:
            evidence, token = preview_full_settlement(request_id=closure.pk, actor=request.user)
        except ValidationError as error:
            blocked = " ".join(error.messages)
        if not form.is_bound:
            form.initial["preview_token"] = token
    latest = closure.settlements.select_related("redemption", "event").order_by("-event__sequence").first()
    if latest and not correction_form.is_bound:
        correction_form.initial.update(settlement_id=latest.pk, expected_sequence=closure.events.count())
    return render(request, "schemes/configured_settlement.html", dict(closure=closure,
        form=form, correction_form=correction_form, evidence=evidence, blocked=blocked,
        latest=latest, settlements=closure.settlements.select_related("redemption__reversal", "event").order_by("-event__sequence")))
