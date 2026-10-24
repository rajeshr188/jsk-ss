import uuid

from django import forms

from .models import InstalmentOutageResolution, InstalmentPaymentDecision, InstalmentReview


class OrderRecoveryForm(forms.Form):
    order_id = forms.RegexField(regex=r"^order_[A-Za-z0-9_]+$", max_length=120,
        label="Candidate Razorpay order ID", help_text="Obtain from the correct Live merchant dashboard/support. The server independently verifies it; a screenshot is not proof.")
    reason = forms.CharField(max_length=2000, widget=forms.Textarea(attrs={"rows": 3}))
    evidence_reference = forms.CharField(max_length=254, label="Investigation/support reference")
    expected_payment_sequence = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    idempotency_key = forms.UUIDField(widget=forms.HiddenInput)

    def __init__(self, *args, claim, **kwargs):
        super().__init__(*args, **kwargs)
        last = claim.decisions.order_by("-sequence").first()
        self.initial.update(expected_payment_sequence=last.sequence if last else 0, idempotency_key=uuid.uuid4())
        for field in self.fields.values():
            if not field.widget.is_hidden:
                field.widget.attrs["class"] = "form-control"


class OutageResolutionForm(forms.Form):
    outcome = forms.ChoiceField(choices=InstalmentOutageResolution.Outcome.choices)
    reason = forms.CharField(max_length=2000, widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Explain restoration and, for compensation, why an exceptional merchant/provider outage caused this unpaid window to be lost. Routine non-office hours do not qualify.")
    evidence_reference = forms.CharField(max_length=254, label="Incident and reconciliation evidence reference")
    incident_started_at = forms.DateTimeField(help_text="Include timezone offset, e.g. 2026-10-23 09:00:00+05:30.")
    service_restored_at = forms.DateTimeField(help_text="Actual restoration time, including timezone offset.")
    customer_acknowledged_at = forms.DateTimeField(help_text="Actual acknowledgement time, including timezone offset. Never invent consent.")
    acknowledgement_reference = forms.CharField(max_length=254,
        help_text="Reference the customer's acceptance of this exact outcome and dates, unchanged count, amount and grade; do not paste private messages or tokens.")
    evidence_confirmed = forms.BooleanField(label="I verified the incident evidence and the customer's acknowledgement of this proposal.")
    idempotency_key = forms.UUIDField(widget=forms.HiddenInput)
    expected_review_sequence = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    expected_period_count = forms.IntegerField(min_value=1, widget=forms.HiddenInput)

    def __init__(self, *args, hold, **kwargs):
        super().__init__(*args, **kwargs)
        self.initial.update(idempotency_key=uuid.uuid4(),
            expected_review_sequence=hold.period.reviews.order_by("-sequence").first().sequence,
            expected_period_count=hold.period.scheme_account.instalment_periods.count())
        for field in self.fields.values():
            if not field.widget.is_hidden:
                field.widget.attrs["class"] = ("form-check-input" if isinstance(field.widget, forms.CheckboxInput)
                    else "form-select" if isinstance(field.widget, forms.Select) else "form-control")


class TimingEvidenceChoice(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f"Decision {obj.pk}: {obj.reason_code} ({obj.earliest_at} to {obj.latest_at})"


class InstalmentReviewForm(forms.Form):
    action = forms.ChoiceField(label="Review action")
    reason = forms.CharField(max_length=2000, widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Describe the investigation. Do not enter passwords, tokens or raw provider payloads.")
    evidence_reference = forms.CharField(max_length=254, label="Incident or support reference")
    source_decision = TimingEvidenceChoice(queryset=InstalmentPaymentDecision.objects.none(), required=False,
        label="Existing signed timing evidence", help_text="Required only for accepting timing. No timestamp can be entered manually.")
    reservation_id = forms.IntegerField(required=False, widget=forms.HiddenInput)
    expected_payment_sequence = forms.IntegerField(required=False, widget=forms.HiddenInput)
    expected_review_sequence = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    idempotency_key = forms.UUIDField(widget=forms.HiddenInput)

    def __init__(self, *args, period, reservation=None, **kwargs):
        super().__init__(*args, **kwargs)
        last = period.reviews.order_by("-sequence").first()
        self.initial.update(expected_review_sequence=last.sequence if last else 0, idempotency_key=uuid.uuid4())
        choices = [(InstalmentReview.Action.NOTE, "Record investigation note")]
        if reservation is None:
            choices.append((InstalmentReview.Action.OUTAGE_HOLD, "Record outage hold (requires further agreement review)"))
            self.fields["source_decision"].widget = forms.HiddenInput()
        else:
            self.initial.update(reservation_id=reservation.pk,
                expected_payment_sequence=reservation.decisions.order_by("-sequence").first().sequence)
            # Permit validation of an exact POST retry after success. The service
            # verifies the idempotency key/content before allowing a terminal state.
            if reservation.state in ("REVIEW", "AWAITING") or (self.is_bound and self.data.get("action") == "ACCEPT_TIMING"):
                choices.append((InstalmentReview.Action.ACCEPT_TIMING, "Accept existing verified timing"))
            self.fields["source_decision"].queryset = reservation.decisions.filter(webhook_event__isnull=False).order_by("-sequence")
        self.fields["action"].choices = choices
        for field in self.fields.values():
            if not field.widget.is_hidden:
                field.widget.attrs["class"] = "form-select" if isinstance(field.widget, forms.Select) else "form-control"
