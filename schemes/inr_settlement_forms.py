import uuid

from django import forms

from .inr_workspace_selectors import fulfilment_legs, pending_fulfilment_legs


class InrPreviewForm(forms.Form):
    invoice_payable = forms.DecimalField(max_digits=14, decimal_places=2, min_value=0,
        label="Final invoice payable after benefit (INR)", help_text="Use zero for an entirely refunded principal settlement.")
    include_benefit = forms.BooleanField(required=False, label="Review a qualified contracted invoice benefit")
    invoice_before_benefit = forms.DecimalField(required=False, max_digits=14, decimal_places=2, min_value=0)
    eligible_charges = forms.DecimalField(required=False, max_digits=14, decimal_places=2, min_value=0)
    invoice_evidence_reference = forms.CharField(required=False, max_length=254)
    eligible_charge_reference = forms.CharField(required=False, max_length=254)

    def __init__(self, *args, benefit_kind, **kwargs):
        super().__init__(*args, **kwargs)
        self.benefit_kind = benefit_kind

    def clean(self):
        values = super().clean()
        names = ("invoice_before_benefit", "eligible_charges", "invoice_evidence_reference", "eligible_charge_reference")
        if values.get("include_benefit"):
            if self.benefit_kind not in ("VA_DISCOUNT", "INR_PURCHASE_BONUS"):
                raise forms.ValidationError("This contract has no supported invoice benefit.")
            required = names if self.benefit_kind == "VA_DISCOUNT" else (names[0], names[2])
            for name in required:
                if values.get(name) in (None, ""):
                    self.add_error(name, "Retain the evidence for this contracted benefit.")
            if self.benefit_kind == "INR_PURCHASE_BONUS" and any(values.get(n) not in (None, "") for n in (names[1], names[3])):
                raise forms.ValidationError("Eligible-charge fields apply only to VA discounts.")
        elif any(values.get(n) not in (None, "") for n in names):
            raise forms.ValidationError("Select benefit review or clear its invoice fields.")
        return values

    def benefit_invoice(self):
        return {n: self.cleaned_data[n] for n in ("invoice_before_benefit", "eligible_charges",
            "invoice_evidence_reference", "eligible_charge_reference")} if self.cleaned_data["include_benefit"] else None


class InrActionForm(forms.Form):
    idempotency_key = forms.UUIDField(initial=uuid.uuid4, widget=forms.HiddenInput)
    reason = forms.CharField(max_length=2000, widget=forms.Textarea(attrs={"rows": 2}))
    confirmed = forms.BooleanField(label="I have checked the retained evidence for this action.")


class InrProposalForm(InrActionForm):
    field_order = ("preview_token", "idempotency_key", "invoice_reference", "authorization_reference", "reason", "confirmed")
    preview_token = forms.CharField(widget=forms.HiddenInput)
    invoice_reference = forms.CharField(required=False, max_length=120)
    authorization_reference = forms.CharField(max_length=254, label="Customer authorization for the complete split")
    confirmed = forms.BooleanField(label="The customer authorized this complete invoice/refund split. Saving it records no delivery or refund.")


class InrFulfilmentForm(InrActionForm):
    field_order = ("idempotency_key", "leg", "external_reference", "customer_receipt_reference",
        "fulfilled_at", "top_up_reference", "reason", "confirmed")
    leg = forms.ChoiceField(label="Complete portion actually fulfilled")
    external_reference = forms.CharField(max_length=120,
        help_text="Jewellery: the agreed invoice reference. Refund: the completed original-source transaction reference.")
    customer_receipt_reference = forms.CharField(max_length=254)
    fulfilled_at = forms.DateTimeField(label="Actual delivery or refund date and time",
        help_text="Actual date/time with timezone, e.g. 2026-10-27T10:00:00+05:30.")
    top_up_reference = forms.CharField(required=False, max_length=120,
        help_text="Required only for jewellery with a separately paid invoice top-up.")
    confirmed = forms.BooleanField(label="This complete delivery or refund has actually occurred and the customer receipt is retained.")

    def __init__(self, *args, proposal, **kwargs):
        super().__init__(*args, **kwargs)
        self.legs = fulfilment_legs(proposal) if proposal else {}
        pending = pending_fulfilment_legs(proposal) if proposal else {}
        choices = dict(pending)
        # A completed leg is retained only for a submitted browser retry. The
        # service still checks idempotency and source evidence under lock.
        submitted = self.data.get(self.add_prefix("leg")) if self.is_bound else None
        if submitted in self.legs and submitted not in choices:
            choices[submitted] = self.legs[submitted]
        self.fields["leg"].choices = [(key, f"{row['kind_label']} — INR {row['amount']} — {row['method_label']}"
            + (f" — principal receipt {row['receipt_id']}" if row['receipt_id'] else "")
            + (" (already recorded; retry only)" if key not in pending else "")) for key, row in choices.items()]


class InrCorrectionForm(InrActionForm):
    field_order = ("idempotency_key", "kind", "authorization_reference", "preview_token", "reason", "confirmed")
    kind = forms.ChoiceField(label="Correction action", choices=(("VOID", "Void an entirely unfulfilled proposal"),
        ("FULL_RETURN", "All actually fulfilled portions have been returned in full")))
    authorization_reference = forms.CharField(max_length=254)
    preview_token = forms.CharField(required=False, widget=forms.HiddenInput)

    def __init__(self, *args, applying=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["confirmed"].required = applying
        self.fields["preview_token"].required = applying


class InrReturnForm(forms.Form):
    external_reference = forms.CharField(max_length=120)
    customer_confirmation = forms.CharField(max_length=254)
    invoice_correction_reference = forms.CharField(required=False, max_length=120)
    top_up_refund_reference = forms.CharField(required=False, max_length=120)
    returned_at = forms.DateTimeField(help_text="Actual full-return date/time with timezone offset; no promised returns.")
    method = forms.ChoiceField()

    def __init__(self, *args, fulfilment, **kwargs):
        super().__init__(*args, **kwargs)
        self.fulfilment = fulfilment
        jewellery = fulfilment.kind == "JEWELLERY"
        self.fields["method"].choices = (("GOODS_RETURN", "Goods received back"),) if jewellery else (
            ("BANK_CREDIT", "Money received back into bank"), ("CASH_RECEIPT", "Cash received back"))
        self.fields["invoice_correction_reference"].required = jewellery
        self.fields["top_up_refund_reference"].required = jewellery and bool(fulfilment.proposal.separate_top_up)

    def evidence(self):
        return dict(fulfilment_id=self.fulfilment.pk, **self.cleaned_data)
