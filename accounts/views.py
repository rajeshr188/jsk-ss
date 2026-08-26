from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache

from .forms import CustomerInvitationPasswordForm
from .models import CustomerInvitation
from .services import (
    InvalidCustomerInvitation,
    accept_customer_invitation,
    invitation_is_available,
)


def _invitation_or_none(invitation_id):
    return (
        CustomerInvitation.objects.select_related("user")
        .filter(pk=invitation_id)
        .first()
    )


@never_cache
def customer_invitation_accept(request, invitation_id, token):
    invitation = _invitation_or_none(invitation_id)
    if invitation is None or not invitation_is_available(invitation, token):
        return render(
            request,
            "account/customer_invitation_invalid.html",
            status=200,
        )

    form = CustomerInvitationPasswordForm(invitation.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            accept_customer_invitation(
                invitation_id=invitation.pk,
                raw_token=token,
                new_password=form.cleaned_data["new_password1"],
            )
        except (InvalidCustomerInvitation, ObjectDoesNotExist):
            return render(
                request,
                "account/customer_invitation_invalid.html",
                status=200,
            )
        messages.success(
            request,
            "Your password is set. You can now sign in with your email address.",
        )
        return redirect("account_login")

    return render(
        request,
        "account/customer_invitation_accept.html",
        {"form": form, "invitation": invitation},
    )
