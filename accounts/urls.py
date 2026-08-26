from django.urls import path

from . import views


urlpatterns = [
    path(
        "invitations/<uuid:invitation_id>/<str:token>/",
        views.customer_invitation_accept,
        name="customer_invitation_accept",
    ),
]
