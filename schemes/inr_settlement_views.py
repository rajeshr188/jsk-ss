"""Owner forms over the existing gated INR services; no financial writes in views."""
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render

from .inr_corrections import preview_inr_resolution, resolve_inr_settlement
from .inr_settlement_forms import (InrActionForm, InrCorrectionForm, InrFulfilmentForm,
    InrPreviewForm, InrProposalForm, InrReturnForm)
from .inr_settlements import (complete_inr_settlement, preview_independent_inr_settlement,
    propose_inr_settlement, record_inr_fulfilment)
from .inr_workspace_selectors import inr_owner_workspace


def inr_settlement_workspace(request, closure):
    """Called only by the CSRF-protected, never-cached owner settlement route."""
    operation = request.POST.get("operation") if request.method == "POST" else None
    allowed = ("preview", "propose", "fulfil", "complete", "preview_correction", "correct")
    context = dict(closure=closure)
    if request.method == "POST" and operation not in allowed:
        return render(request, "schemes/inr_settlement.html", context | {"blocked": "Unknown settlement operation."}, status=400)
    try:
        context.update(inr_owner_workspace(closure))
    except ValidationError as error:
        return render(request, "schemes/inr_settlement.html", context | {"blocked": " ".join(error.messages)})
    if (closure.scheme_account.agreement_schema_version != 2
            or any("independent" not in p.evidence for p in context["history"])):
        return render(request, "schemes/inr_settlement.html", context | {
            "blocked": "This owner workflow requires an independent policy agreement and disposition proof. Existing foundation history is read-only; retain it for separate review."})
    proposal = context["current"]
    if operation in ("fulfil", "complete", "preview_correction", "correct"):
        # Do not permit a posted proposal ID to cross the authorized closure boundary.
        try:
            proposal_id = int(request.POST.get("proposal_id", ""))
        except ValueError:
            return render(request, "schemes/inr_settlement.html", context | {"blocked": "Choose a retained proposal."}, status=400)
        proposal = get_object_or_404(closure.scheme_account.inr_settlements, pk=proposal_id, closure=closure)
    data = request.POST if request.method == "POST" else None
    preview = InrPreviewForm(data if operation == "preview" else None, prefix="preview",
        benefit_kind=closure.scheme_account.configuration_snapshot.benefit_policy)
    proposed = InrProposalForm(data if operation == "propose" else None, prefix="propose")
    fulfilment = InrFulfilmentForm(data if operation == "fulfil" else None, proposal=proposal, prefix="fulfil")
    completion = InrActionForm(data if operation == "complete" else None, prefix="complete")
    correcting = operation in ("preview_correction", "correct")
    correction = InrCorrectionForm(data if correcting else None, prefix="correction", applying=operation == "correct")
    returns = [InrReturnForm(data if correcting else None, fulfilment=f, prefix=f"return-{f.pk}")
        for f in proposal.fulfilments.order_by("pk")] if proposal else []
    context.update(preview_form=preview, proposal_form=proposed, fulfilment_form=fulfilment,
        completion_form=completion, correction_form=correction, return_forms=returns, selected_proposal=proposal)
    selected = {"preview": preview, "propose": proposed, "fulfil": fulfilment, "complete": completion,
        "preview_correction": correction, "correct": correction}.get(operation)
    if selected is not None and selected.is_valid():
        values = selected.cleaned_data.copy()
        values.pop("confirmed", None)
        try:
            if operation == "preview":
                split, token = preview_independent_inr_settlement(request_id=closure.pk, actor=request.user,
                    invoice_payable=values["invoice_payable"], benefit_invoice=preview.benefit_invoice())
                context["split"] = split
                if values["include_benefit"]:
                    context["reviewed_benefit"] = values["invoice_before_benefit"] - split.invoice_payable
                proposed.initial["preview_token"] = token
            elif operation == "propose":
                propose_inr_settlement(request_id=closure.pk, actor=request.user, **values)
            elif operation == "fulfil":
                leg = fulfilment.legs[values.pop("leg")]
                # Amount, source and route come only from the retained proposal.
                record_inr_fulfilment(proposal_id=proposal.pk, actor=request.user, **values,
                    **{name: leg[name] for name in ("kind", "method", "receipt_id")})
            elif operation == "complete":
                complete_inr_settlement(proposal_id=proposal.pk, actor=request.user, **values)
            else:
                row_results = [row.is_valid() for row in returns] if values["kind"] == "FULL_RETURN" else []
                if not all(row_results):
                    raise ValidationError("Complete return evidence for every actually fulfilled portion.")
                rows = [row.evidence() for row in returns] if values["kind"] == "FULL_RETURN" else []
                if operation == "preview_correction":
                    token = preview_inr_resolution(proposal_id=proposal.pk, actor=request.user,
                        kind=values["kind"], return_evidence=rows)
                    # Keep the same visible evidence on review. Editing it invalidates the signed preview.
                    reviewed = data.copy()
                    reviewed["correction-preview_token"] = token
                    reviewed["correction-confirmed"] = ""
                    context["correction_form"] = InrCorrectionForm(reviewed, prefix="correction")
                    context["correction_reviewed"] = True
                else:
                    resolve_inr_settlement(proposal_id=proposal.pk, actor=request.user, return_evidence=rows, **values)
        except ValidationError as error:
            selected.add_error(None, error.messages)
        else:
            if operation not in ("preview", "preview_correction"):
                messages.success(request, "INR settlement action recorded or already recorded. Review the retained status and outstanding principal below.")
                return redirect("schemes:configured_settlement", request_id=closure.pk)
    return render(request, "schemes/inr_settlement.html", context)
