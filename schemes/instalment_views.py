"""Owner-only, server-rendered instalment investigation workspace."""
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods

from .instalment_review_forms import InstalmentReviewForm, OutageResolutionForm, OrderRecoveryForm
from .instalment_order_recovery import recover_instalment_order
from .instalment_outages import resolve_instalment_outage
from .instalments import compensation_window
from .instalment_reviews import record_instalment_review
from .instalment_selectors import open_outage_holds, owner_instalment_review_periods, unresolved_instalment_captures
from .models import InstalmentReservation, InstalmentReview
from .payments import PaymentGatewayError
from .permissions import owner_required


@never_cache
@owner_required
@require_GET
def review_queue(request):
    page = Paginator(owner_instalment_review_periods(), 25).get_page(request.GET.get("page"))
    return render(request, "schemes/instalment_review_queue.html", {"page_obj": page})


@never_cache
@owner_required
@require_http_methods(["GET", "POST"])
def recover_order(request, reservation_id):
    claim = get_object_or_404(InstalmentReservation.objects.select_related("period__scheme_account", "contribution"), pk=reservation_id)
    form = OrderRecoveryForm(request.POST if request.method == "POST" else None, claim=claim)
    if request.method == "POST" and form.is_valid():
        try:
            recover_instalment_order(contribution_id=claim.contribution_id, actor=request.user, **form.cleaned_data)
        except (ValidationError, PaymentGatewayError) as error:
            form.add_error(None, error if isinstance(error, ValidationError) else str(error))
        else:
            messages.success(request, "Provider order identity recovered. Payment is not confirmed and checkout cannot resume. Reconcile captures or, after expiry, the untouched order through the existing workflow.")
            return redirect("schemes:instalment_review_period", period_id=claim.period_id)
    return render(request, "schemes/instalment_order_recovery.html", {"claim": claim, "form": form,
        "intent": claim.decisions.filter(state="ORDERING").first()})


@never_cache
@owner_required
@require_http_methods(["GET", "POST"])
def review_period(request, period_id):
    period = get_object_or_404(owner_instalment_review_periods(), pk=period_id)
    claims = list(period.reservations.select_related("contribution").prefetch_related("decisions").order_by("-pk"))
    target = None
    if request.method == "POST" and request.POST.get("reservation_id"):
        try:
            reservation_id = int(request.POST["reservation_id"])
        except (TypeError, ValueError):
            raise Http404 from None
        target = get_object_or_404(period.reservations, pk=reservation_id)
    bound = None
    if request.method == "POST":
        bound = InstalmentReviewForm(request.POST, period=period, reservation=target, prefix=None)
        if bound.is_valid():
            values = bound.cleaned_data
            try:
                record_instalment_review(period_id=period.pk, actor=request.user,
                    action=values["action"], reason=values["reason"], evidence_reference=values["evidence_reference"],
                    idempotency_key=values["idempotency_key"], expected_review_sequence=values["expected_review_sequence"],
                    reservation_id=target.pk if target else None,
                    source_decision_id=values["source_decision"].pk if values["source_decision"] else None,
                    expected_payment_sequence=values["expected_payment_sequence"])
            except ValidationError as error:
                bound.add_error(None, error)
            else:
                messages.success(request, "Review recorded. No money, metal, rate, deadline or benefit was changed.")
                return redirect("schemes:instalment_review_period", period_id=period.pk)
    period_form = bound if bound is not None and target is None else InstalmentReviewForm(period=period, auto_id="period_%s")
    rows = [{"claim": claim, "decisions": claim.decisions.order_by("-sequence")[:50],
        "form": bound if target is not None and target.pk == claim.pk else InstalmentReviewForm(
            period=period, reservation=claim, auto_id=f"claim_{claim.pk}_%s")} for claim in claims]
    return render(request, "schemes/instalment_review_period.html", {
        "period": period, "period_form": period_form, "rows": rows,
        "reviews": period.reviews.select_related("source_decision", "outage_resolution__compensation_period").order_by("-sequence")[:50],
        "outage_held": open_outage_holds().filter(period__scheme_account=period.scheme_account).exists(),
        "capture_exceptions": unresolved_instalment_captures(account_id=period.scheme_account_id).order_by("-received_at", "-pk")[:50],
    })


@never_cache
@owner_required
@require_http_methods(["GET", "POST"])
def resolve_outage(request, hold_id):
    hold = get_object_or_404(InstalmentReview.objects.select_related("period__scheme_account"), pk=hold_id, action="OUTAGE_HOLD")
    account = hold.period.scheme_account
    form = OutageResolutionForm(request.POST if request.method == "POST" else None, hold=hold)
    if request.method == "POST" and form.is_valid():
        values = dict(form.cleaned_data)
        values.pop("evidence_confirmed")
        try:
            resolve_instalment_outage(hold_id=hold.pk, actor=request.user, **values)
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(request, "Outage resolution recorded. Original terms and financial records are unchanged. Other holds or payment reviews may still block initiation.")
            return redirect("schemes:instalment_review_period", period_id=hold.period_id)
    used = account.outage_resolutions.filter(outcome="COMPENSATE").count()
    try:
        proposed = compensation_window(account, used + 1)
    except ValidationError:
        proposed = None
    return render(request, "schemes/instalment_outage_resolution.html", {
        "hold": hold, "account": account, "form": form, "used": used, "proposed": proposed,
    })
