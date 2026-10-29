"""Private, configured-agreement closure preparation. No settlement endpoint."""
import uuid

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods

from .closures import cancel_unused_agreement, request_scheme_closure, review_scheme_closure
from .closure_selectors import closure_payment_review, closure_requests, validate_closure_history
from .models import SchemeAccount
from .permissions import owner_required


class ClosureForm(forms.Form):
    reason = forms.CharField(max_length=2000, widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Explain the request or decision. This does not confirm jewellery delivery or a refund.")
    authorization_reference = forms.CharField(max_length=254, required=False,
        help_text="Owner-assisted requests/withdrawals require a retained reference to actual customer authorization. Do not enter passwords or payment secrets.")
    idempotency_key = forms.UUIDField(initial=uuid.uuid4, widget=forms.HiddenInput)
    action = forms.ChoiceField(choices=[], required=False)
    expected_sequence = forms.IntegerField(min_value=1, required=False, widget=forms.HiddenInput)
    request_id = forms.UUIDField(required=False, widget=forms.HiddenInput)

    def __init__(self, *args, owner, target=None, **kwargs):
        super().__init__(*args, **kwargs)
        if not owner:
            self.fields.pop("authorization_reference")
        if target is None:
            self.fields.pop("action")
            self.fields.pop("expected_sequence")
            self.fields.pop("request_id")
            if owner:
                self.fields["authorization_reference"].required = True
        else:
            choices = [("NOTE", "Add review note")] if owner else []
            if target.status == "PENDING":
                choices += [("ACCEPT", "Accept for closure — block new payments"), ("REJECT", "Reject before acceptance")] if owner else []
                choices += [("WITHDRAW", "Withdraw before acceptance")]
            self.fields["action"].choices = choices
            self.fields["action"].required = True
            self.fields["expected_sequence"].required = True
            self.fields["expected_sequence"].initial = target.events.count()
            self.fields["request_id"].required = True
            self.fields["request_id"].initial = target.pk


@never_cache
@owner_required
@require_GET
def closure_queue(request):
    page = Paginator(closure_requests().filter(status__in=["PENDING", "ACCEPTED"]), 25).get_page(request.GET.get("page"))
    return render(request, "schemes/closure_queue.html", {"page_obj": page})


class UnusedCancellationForm(forms.Form):
    request_id = forms.UUIDField(widget=forms.HiddenInput)
    expected_sequence = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    idempotency_key = forms.UUIDField(initial=uuid.uuid4, widget=forms.HiddenInput)
    reason = forms.CharField(max_length=2000, widget=forms.Textarea(attrs={"rows": 3}))
    confirm_unused_cancellation = forms.BooleanField(
        label="Cancel this unused agreement permanently; keep the customer's login and records.",
        help_text="The server rechecks all history. This is not a refund or jewellery settlement; a new saving cycle needs a new agreement.")


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
def closure_workspace(request, scheme_number):
    owner = request.user.is_superuser or request.user.role == "OWNER"
    if not request.user.is_active or (not owner and request.user.role != "CUSTOMER"):
        raise PermissionDenied
    accounts = SchemeAccount.objects.filter(configuration_snapshot__isnull=False).select_related("customer__user", "metal_grade")
    if not owner:
        accounts = accounts.filter(customer__user=request.user)
    account = get_object_or_404(accounts, scheme_number=scheme_number)
    history = closure_requests().filter(scheme_account=account)
    target = history.filter(status__in=["PENDING", "ACCEPTED"]).first()
    # Replays/competing decisions must be checked against the original request,
    # never reinterpreted as creation after somebody else closes a request.
    if request.method == "POST" and request.POST.get("request_id"):
        try:
            target_id = uuid.UUID(request.POST["request_id"])
        except ValueError:
            raise PermissionDenied from None
        target = get_object_or_404(history, pk=target_id)
    cancellation_post = request.method == "POST" and request.POST.get("operation") == "cancel_unused"
    if cancellation_post and not owner:
        raise PermissionDenied
    can_submit = account.status not in ("REDEEMED", "CANCELLED") and (target is None or target.status == "PENDING" or (owner and target.status == "ACCEPTED"))
    form = ClosureForm(request.POST if request.method == "POST" and not cancellation_post else None, owner=owner, target=target)
    cancel_form = UnusedCancellationForm(request.POST if cancellation_post else None, auto_id="cancel_%s", initial={
        "request_id": target.pk if target else None,
        "expected_sequence": target.events.count() if target else None,
    })
    if cancellation_post:
        if target is None:
            cancel_form.add_error(None, "Select an accepted closure first.")
        elif cancel_form.is_valid():
            values = cancel_form.cleaned_data.copy()
            values.pop("confirm_unused_cancellation")
            try:
                cancel_unused_agreement(actor=request.user, **values)
            except ValidationError as error:
                cancel_form.add_error(None, error)
            else:
                messages.success(request, "Unused agreement cancelled. No redemption or refund was created; customer login and records are retained.")
                return redirect("schemes:closure_workspace", scheme_number=account.scheme_number)
    elif request.method == "POST":
        if not can_submit:
            form.add_error(None, "This closure is no longer open for that action. Reload to review its history.")
        elif form.is_valid():
            values = form.cleaned_data.copy()
            try:
                if target:
                    request_id = values.pop("request_id")
                    review_scheme_closure(request_id=request_id, actor=request.user, **values)
                else:
                    request_scheme_closure(account_id=account.pk, actor=request.user, **values)
            except ValidationError as error:
                form.add_error(None, error)
            else:
                messages.success(request, "Closure evidence recorded. No settlement, refund or account cancellation has been performed.")
                return redirect("schemes:closure_workspace", scheme_number=account.scheme_number)
    integrity_error = False
    if target:
        try:
            validate_closure_history(target)
        except ValidationError:
            integrity_error = True
    return render(request, "schemes/closure_workspace.html", {"scheme_account": account, "history": history,
        "target": target, "form": form, "can_submit": can_submit, "owner_view": owner,
        "cancel_form": cancel_form,
        "can_cancel": owner and target is not None and (target.status == "ACCEPTED" or cancellation_post),
        "integrity_error": integrity_error, "payment_review": {
            name.replace("_", " ").capitalize(): value for name, value in closure_payment_review(account).items()}})
