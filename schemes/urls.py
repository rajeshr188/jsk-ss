from django.urls import path

from . import views

app_name = "schemes"

urlpatterns = [
    path("start/", views.post_login, name="post_login"),
    path("owner/", views.owner_dashboard, name="owner_dashboard"),
    path("owner/customers/", views.customer_list, name="customer_list"),
    path("owner/customers/add/", views.customer_add, name="customer_add"),
    path(
        "owner/customers/<int:customer_id>/",
        views.customer_detail,
        name="customer_detail",
    ),
    path(
        "owner/customers/<int:customer_id>/enrol/",
        views.customer_enroll,
        name="customer_enroll",
    ),
    path("owner/plans/", views.plan_list, name="plan_list"),
    path("owner/plans/add/", views.plan_add, name="plan_add"),
    path("mine/", views.my_schemes, name="my_schemes"),
]

