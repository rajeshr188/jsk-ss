import uuid

from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from .benefit_reapplication_selectors import owner_reapplication_workspace
from .benefit_reapplications import preview_benefit_reapplication, record_benefit_reapplication
from .models import SchemeAccount
from .permissions import owner_required


class ReturnChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, row):
        return f"Return #{row.pk}: {row.fulfilment.award.get_kind_display()} — corrected invoice {row.invoice_correction_reference}"


class ReviewPreviewForm(forms.Form):
    outcome = forms.ChoiceField(choices=(("HOLD", "Hold for further review"), ("APPROVE", "Approve replacement benefit review")))
    authorization_reference = forms.CharField(required=False, max_length=254,
        help_text="Approval needs fresh customer authorization for reapplication. Leave blank for a hold; do not reuse an earlier invoice or return confirmation.")

    def __init__(self, *args, reversals, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["reversal"] = ReturnChoiceField(queryset=reversals, label="Completed benefit return")
        self.order_fields(("reversal", "outcome", "authorization_reference"))

    def clean(self):
        values = super().clean()
        if values.get("outcome") == "APPROVE" and not values.get("authorization_reference"):
            self.add_error("authorization_reference", "Retain fresh customer authorization before approving.")
        if values.get("outcome") == "HOLD" and values.get("authorization_reference"):
            self.add_error("authorization_reference", "A hold must not claim customer approval.")
        return values


class ReviewDecisionForm(forms.Form):
    preview_token = forms.CharField(widget=forms.HiddenInput)
    idempotency_key = forms.UUIDField(initial=uuid.uuid4, widget=forms.HiddenInput)
    reason = forms.CharField(max_length=2000, widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Private owner review reason, retained with this decision.")
    confirmed = forms.BooleanField(label="I checked the full return and proposed decision. This records a review only, not a new award, invoice or payment reopening.")


@never_cache
@owner_required
@require_http_methods(["GET", "POST"])
def benefit_reapplication_workspace(request, scheme_number):
    account = get_object_or_404(SchemeAccount.objects.select_related("configuration_snapshot"),
        scheme_number=scheme_number, configuration_snapshot__isnull=False)
    context = dict(account=account, **owner_reapplication_workspace(account))
    operation = request.POST.get("operation") if request.method == "POST" else None
    if request.method == "POST" and operation not in ("preview", "record"):
        return render(request, "schemes/benefit_reapplication.html", context | {"blocked": "Unknown review operation."}, status=400)
    preview = ReviewPreviewForm(request.POST if operation == "preview" else None,
        reversals=context["reviewable_returns"], prefix="review")
    decision = ReviewDecisionForm(request.POST if operation == "record" else None, prefix="decision")
    context.update(preview_form=preview, decision_form=decision)
    selected = preview if operation == "preview" else decision if operation == "record" else None
    if selected is not None and selected.is_valid():
        try:
            if operation == "preview":
                facts = preview.cleaned_data
                token = preview_benefit_reapplication(account_id=account.pk, actor=request.user,
                    reversal_id=facts["reversal"].pk, outcome=facts["outcome"],
                    authorization_reference=facts["authorization_reference"])
                context["reviewed"] = dict(reversal=facts["reversal"], outcome=facts["outcome"],
                    authorization_reference=facts["authorization_reference"])
                decision.initial["preview_token"] = token
            else:
                values = decision.cleaned_data.copy()
                values.pop("confirmed")
                record_benefit_reapplication(account_id=account.pk, actor=request.user, **values)
        except ValidationError as error:
            selected.add_error(None, error.messages)
        else:
            if operation == "record":
                messages.success(request, "Review recorded or already recorded. Check the latest status below; an older retry does not override a later hold or invoice use.")
                return redirect("schemes:benefit_reapplication", scheme_number=account.scheme_number)
    return render(request, "schemes/benefit_reapplication.html", context)
