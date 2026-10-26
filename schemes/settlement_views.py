import uuid

from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from .models import BenefitInvoiceFulfilment, SchemeClosureRequest
from .permissions import owner_required
from .settlements import preview_full_settlement, reverse_configured_settlement, settle_configured_agreement


class SettlementForm(forms.Form):
    preview_token = forms.CharField(widget=forms.HiddenInput)
    idempotency_key = forms.UUIDField(initial=uuid.uuid4, widget=forms.HiddenInput)
    invoice_reference = forms.CharField(max_length=120, label="Jewellery invoice / sales reference")
    authorization_reference = forms.CharField(max_length=254, label="Customer confirmation reference",
        help_text="Retained evidence that the customer confirmed this full exact-grade quantity and jewellery fulfilment. A closure request alone is not delivery confirmation.")
    reason = forms.CharField(max_length=2000, widget=forms.Textarea(attrs={"rows": 3}))
    confirmed = forms.BooleanField(label="I confirm actual jewellery fulfilment against the invoice, the full six-decimal quantity and any contracted benefit shown in this preview. No cash payout or principal deduction is being recorded.")


class SettlementInvoiceForm(forms.Form):
    include_benefit = forms.BooleanField(required=False, label="Include a qualified contracted invoice benefit",
        help_text="The server decides qualification and amount. Leave unchecked for an early closure with no qualified benefit; an earned right cannot be silently omitted.")
    invoice_before_benefit = forms.DecimalField(required=False, max_digits=14, decimal_places=2, min_value=0)
    eligible_charges = forms.DecimalField(required=False, max_digits=14, decimal_places=2, min_value=0)
    invoice_evidence_reference = forms.CharField(required=False, max_length=254)
    eligible_charge_reference = forms.CharField(required=False, max_length=254)
    customer_receipt_reference = forms.CharField(required=False, max_length=254,
        label="Actual customer jewellery receipt evidence", help_text="Retain the signed handover evidence. A preview itself records no fulfilment.")

    def clean(self):
        values = super().clean()
        if values.get("include_benefit"):
            for name in self.fields:
                if name != "include_benefit" and values.get(name) in (None, ""):
                    self.add_error(name, "Complete the invoice evidence before reviewing the benefit.")
        elif any(values.get(name) not in (None, "") for name in self.fields if name != "include_benefit"):
            raise forms.ValidationError("Select Include benefit to review supplied invoice evidence, or clear those fields.")
        return values

    def benefit_invoice(self):
        return {name: self.cleaned_data[name] for name in self.fields if name != "include_benefit"} if self.cleaned_data["include_benefit"] else None


class SettlementReversalForm(forms.Form):
    settlement_id = forms.IntegerField(widget=forms.HiddenInput)
    expected_sequence = forms.IntegerField(widget=forms.HiddenInput)
    idempotency_key = forms.UUIDField(initial=uuid.uuid4, widget=forms.HiddenInput)
    reason = forms.CharField(max_length=2000, widget=forms.Textarea(attrs={"rows": 3}))
    authorization_reference = forms.CharField(max_length=254, label="Invoice correction / restoration evidence reference")
    confirmed = forms.BooleanField(label="The correction is authorized and restores the full entitlement. This does not reopen payments or erase the original invoice history.")

    def __init__(self, *args, benefit_required=False, **kwargs):
        super().__init__(*args, **kwargs)
        if benefit_required:
            self.fields["invoice_correction_reference"] = forms.CharField(max_length=120)
            self.fields["customer_confirmation"] = forms.CharField(max_length=254, label="Customer full-return confirmation")
            self.fields["returned_at"] = forms.DateTimeField(label="Actual full-return date and time",
                help_text="Use an explicit timezone offset, for example 2026-10-27T10:00:00+05:30. No partial or promised returns.")


@never_cache
@owner_required
@require_http_methods(["GET", "POST"])
def settlement_workspace(request, request_id):
    closure = get_object_or_404(SchemeClosureRequest.objects.select_related("scheme_account__metal_grade"),
        pk=request_id, scheme_account__configuration_snapshot__isnull=False)
    if closure.scheme_account.savings_mode == "INR_CREDIT":
        # Do not reinterpret INR principal through a gram-based form or service.
        from .inr_settlement_views import inr_settlement_workspace
        return inr_settlement_workspace(request, closure)
    operation = request.POST.get("operation", "settle")
    preview_post = request.method == "POST" and operation == "preview"
    reverse_post = request.method == "POST" and request.POST.get("operation") == "reverse"
    independent = closure.scheme_account.agreement_schema_version == 2
    latest = closure.settlements.select_related("redemption", "event").order_by("-event__sequence").first()
    benefit_required = bool(latest and BenefitInvoiceFulfilment.objects.filter(metal_settlement=latest).exists())
    form = SettlementForm(request.POST if request.method == "POST" and not reverse_post and not preview_post else None)
    invoice_form = SettlementInvoiceForm(request.POST if preview_post else None, auto_id="invoice_%s")
    correction_form = SettlementReversalForm(request.POST if reverse_post else None,
        benefit_required=benefit_required, auto_id="correction_%s")
    if request.method == "POST" and operation not in ("preview", "settle", "reverse"):
        return render(request, "schemes/configured_settlement.html", {"closure": closure,
            "blocked": "Unknown settlement operation. Reload the workspace."}, status=400)
    if request.method == "POST" and not preview_post:
        selected = correction_form if reverse_post else form
        if selected.is_valid():
            values = selected.cleaned_data.copy()
            values.pop("confirmed")
            try:
                if reverse_post:
                    get_object_or_404(closure.settlements, pk=values["settlement_id"])
                    if benefit_required:
                        values["benefit_return"] = {name: values.pop(name) for name in
                            ("invoice_correction_reference", "customer_confirmation", "returned_at")}
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
            if preview_post and not independent:
                raise ValidationError("Invoice-benefit preview requires an independent agreement.")
            if not preview_post or invoice_form.is_valid():
                evidence, token = preview_full_settlement(request_id=closure.pk, actor=request.user,
                    benefit_invoice=invoice_form.benefit_invoice() if preview_post else None)
        except ValidationError as error:
            blocked = " ".join(error.messages)
        if not form.is_bound:
            form.initial["preview_token"] = token
    if latest and not correction_form.is_bound:
        correction_form.initial.update(settlement_id=latest.pk, expected_sequence=closure.events.count())
    return render(request, "schemes/configured_settlement.html", dict(closure=closure,
        form=form, correction_form=correction_form, evidence=evidence, blocked=blocked,
        invoice_form=invoice_form, independent=independent, benefit_required=benefit_required,
        can_review_benefit=independent and closure.scheme_account.configuration_snapshot.benefit_policy != "NONE",
        latest=latest, settlements=closure.settlements.select_related("redemption__reversal", "event", "benefitinvoicefulfilment").order_by("-event__sequence")))
