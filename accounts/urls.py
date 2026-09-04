from django.urls import path

from . import views


urlpatterns = [
    path(
        "register/",
        views.customer_registration,
        name="customer_registration",
    ),
    path(
        "register/submitted/",
        views.customer_registration_submitted,
        name="customer_registration_submitted",
    ),
    path(
        "registrations/verify/<uuid:application_id>/<str:token>/",
        views.customer_registration_verify,
        name="customer_registration_verify",
    ),
    path(
        "registrations/verified/",
        views.customer_registration_verified,
        name="customer_registration_verified",
    ),
    path(
        "owner/registrations/",
        views.customer_registration_list,
        name="customer_registration_list",
    ),
    path(
        "owner/registrations/<uuid:application_id>/",
        views.customer_registration_detail,
        name="customer_registration_detail",
    ),
    path(
        "owner/registrations/<uuid:application_id>/approve/",
        views.customer_registration_approve,
        name="customer_registration_approve",
    ),
    path(
        "owner/registrations/<uuid:application_id>/reject/",
        views.customer_registration_reject,
        name="customer_registration_reject",
    ),
    path(
        "owner/registrations/<uuid:application_id>/resend-verification/",
        views.customer_registration_resend_verification,
        name="customer_registration_resend_verification",
    ),
    path(
        "invitations/<uuid:invitation_id>/<str:token>/",
        views.customer_invitation_accept,
        name="customer_invitation_accept",
    ),
]
