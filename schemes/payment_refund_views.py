"""Explicit private owner confirmation; never provider I/O on GET."""
from django import forms
from django.contrib import messages
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from django.views.decorators.vary import vary_on_cookie

from .models import Contribution, PaymentWebhookEvent
from .payment_refund_observations import inspect_payment_error_refund
from .payment_refund_resolutions import resolve_payment_error_refund
from .payment_refund_workspace_selectors import (payment_refund_workspace, refund_review_history,
    refunded_order_workspace, order_review_comparison)
from .payments import PaymentGatewayError
from .permissions import owner_required
from .refunded_orders import refunded_order_review_token, retire_refunded_order


class RefundReviewForm(forms.Form):
    action = forms.ChoiceField(choices=[("INSPECT", "Inspect"), ("APPLY", "Confirm")])
    reason = forms.CharField(max_length=2000, label="Audit reason",
        help_text="Explain this investigation. Do not enter passwords, tokens, bank details or raw provider payloads.",
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}))
    review_token = forms.CharField(required=False, max_length=65536, widget=forms.HiddenInput)
    confirmed = forms.BooleanField(required=False, label="I reviewed this exact evidence and confirm the stated action.",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}))

    def clean(self):
        data = super().clean()
        if data.get("action") == "APPLY":
            if not data.get("confirmed"):
                self.add_error("confirmed", "Review the evidence and explicitly confirm this action.")
            if not data.get("review_token"):
                self.add_error("review_token", "Inspect and review fresh evidence first.")
        return data


@never_cache
@vary_on_cookie
@owner_required
@require_http_methods(["GET"])
def refund_history(request):
    page = Paginator(refund_review_history(), 20).get_page(request.GET.get("page"))
    return render(request, "schemes/refund_history.html", {"page_obj": page})


@never_cache
@vary_on_cookie
@owner_required
@require_http_methods(["GET", "POST"])
def payment_refund_review(request, event_id):
    event = get_object_or_404(PaymentWebhookEvent, pk=event_id, gateway="razorpay", gateway_mode="live", event_type="payment.captured")
    form = RefundReviewForm(request.POST if request.method == "POST" else None)
    failed = False
    if request.method == "POST" and form.is_valid():
        try:
            if form.cleaned_data["action"] == "INSPECT":
                inspect_payment_error_refund(webhook_event_id=event.pk, performed_by=request.user, reason=form.cleaned_data["reason"])
                messages.info(request, "Provider inspection retained. Review the exact payment, refund totals and entitlement check below.")
            else:
                resolve_payment_error_refund(review_token=form.cleaned_data["review_token"], confirmed=form.cleaned_data["confirmed"],
                    performed_by=request.user, reason=form.cleaned_data["reason"], expected_event_id=event.pk)
                messages.success(request, "Exact-payment refund resolution recorded. No credit or qualifying instalment was created. Any pending order needs its separate all-attempt review.")
        except ValidationError as error:
            form.add_error(None, " ".join(error.messages))
            failed = True
        except (ImproperlyConfigured, PaymentGatewayError):
            form.add_error(None, "Provider inspection is unavailable or inconsistent. No resolution was applied; retain the case for investigation and inspect again.")
            failed = True
        else:
            return redirect("schemes:payment_refund_review", event_id=event.pk)
    context = payment_refund_workspace(event, request.user)
    if not form.is_bound:
        form.initial["review_token"] = context["review_token"]
    if failed:
        context["can_resolve"] = False
    return render(request, "schemes/payment_refund_review.html", {"event": event, "form": form, **context})


@never_cache
@vary_on_cookie
@owner_required
@require_http_methods(["GET", "POST"])
def refunded_order_review(request, contribution_id):
    contribution = get_object_or_404(Contribution.objects.select_related("scheme_account__customer"),
        pk=contribution_id, payment_gateway="razorpay", gateway_mode="live")
    form = RefundReviewForm(request.POST if request.method == "POST" else None)
    comparison = None
    if request.method == "POST" and form.is_valid():
        try:
            if form.cleaned_data["action"] == "INSPECT":
                token = refunded_order_review_token(contribution_id=contribution.pk, performed_by=request.user)
                comparison = order_review_comparison(token, request.user, contribution)
                form = RefundReviewForm(initial={"review_token": token, "reason": form.cleaned_data["reason"]})
            else:
                order_review_comparison(form.cleaned_data["review_token"], request.user, contribution)
                retire_refunded_order(review_token=form.cleaned_data["review_token"], confirmed=form.cleaned_data["confirmed"],
                    performed_by=request.user, reason=form.cleaned_data["reason"], expected_contribution_id=contribution.pk)
                messages.success(request, "Order retired with retained evidence. Its original reservation was released where applicable; no entitlement, benefit or agreement closure was created.")
                return redirect("schemes:refunded_order_review", contribution_id=contribution.pk)
        except ValidationError as error:
            form.add_error(None, " ".join(error.messages))
        except (ImproperlyConfigured, PaymentGatewayError):
            form.add_error(None, "The all-attempt provider check is unavailable or inconsistent. The order remains held; inspect again or continue investigation.")
    contribution.refresh_from_db()
    return render(request, "schemes/refunded_order_review.html", {"contribution": contribution, "form": form,
        "comparison": comparison, **refunded_order_workspace(contribution)})
