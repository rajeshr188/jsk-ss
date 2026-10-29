"""Owner catalogue housekeeping with explicit confirmation and immutable evidence."""
from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from .catalogue_lifecycle import close_catalogue_item
from .catalogue_selectors import catalogue_closure_preview
from .models import SchemePlan, SchemePlanConfiguration
from .permissions import owner_required


class CatalogueClosureForm(forms.Form):
    expected_digest = forms.CharField(widget=forms.HiddenInput)
    reason = forms.CharField(max_length=1000, widget=forms.Textarea(attrs={"rows": 3}))
    confirmed = forms.BooleanField(label="I understand this removes the item from future selection, preserves its history and does not close customer agreements.")


@owner_required
@require_http_methods(["GET", "POST"])
@never_cache
def catalogue_close(request, plan_id=None, configuration_id=None):
    plan = get_object_or_404(SchemePlan, pk=plan_id) if plan_id is not None else None
    configuration = get_object_or_404(SchemePlanConfiguration, pk=configuration_id) if configuration_id is not None else None
    preview = catalogue_closure_preview(plan=plan, configuration=configuration)
    form = CatalogueClosureForm(request.POST if request.method == "POST" else None,
        initial={"expected_digest": preview["expected_digest"]})
    if request.method == "POST" and form.is_valid():
        try:
            record, created = close_catalogue_item(actor=request.user, plan_id=plan_id,
                configuration_id=configuration_id, **form.cleaned_data)
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(request, f"{record.get_action_display()}. Existing agreements and pending requests are retained.")
            return redirect("schemes:plan_list" if plan is not None else "schemes:plan_configuration_list")
    return render(request, "schemes/catalogue_close.html", {"item": plan if plan is not None else configuration,
        "plan": plan, "preview": preview, "form": form})
