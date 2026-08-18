from django.urls import path

from . import views

app_name = "schemes"

urlpatterns = [
    path("start/", views.post_login, name="post_login"),
    path("owner/", views.owner_dashboard, name="owner_dashboard"),
    path(
        "owner/redemptions/eligibility/",
        views.redemption_eligibility,
        name="redemption_eligibility",
    ),
    path("owner/redemptions/", views.redemption_list, name="redemption_list"),
    path("owner/audit/", views.audit_log, name="audit_log"),
    path("owner/exceptions/", views.exception_queue, name="exception_queue"),
    path(
        "owner/schemes/<str:scheme_number>/redeem/",
        views.redemption_create,
        name="redemption_create",
    ),
    path(
        "owner/redemptions/<str:redemption_number>/reverse/",
        views.redemption_reverse,
        name="redemption_reverse",
    ),
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
    path("owner/plans/<int:plan_id>/edit/", views.plan_edit, name="plan_edit"),
    path("owner/contributions/", views.contribution_list, name="contribution_list"),
    path(
        "owner/contributions/<int:contribution_id>/retry-allocation/",
        views.retry_contribution_allocation,
        name="retry_contribution_allocation",
    ),
    path("mine/", views.my_schemes, name="my_schemes"),
    path("mine/<str:scheme_number>/", views.my_scheme_detail, name="my_scheme_detail"),
    path(
        "mine/<str:scheme_number>/pay/",
        views.pay_contribution,
        name="pay_contribution",
    ),
    path(
        "mine/payments/<int:contribution_id>/checkout/",
        views.razorpay_checkout,
        name="razorpay_checkout",
    ),
    path(
        "mine/payments/<int:contribution_id>/confirm/",
        views.razorpay_confirm,
        name="razorpay_confirm",
    ),
    path(
        "payments/razorpay/webhook/",
        views.razorpay_webhook,
        name="razorpay_webhook",
    ),
]
