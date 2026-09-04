from django.urls import path

from . import views

app_name = "schemes"

urlpatterns = [
    path("start/", views.post_login, name="post_login"),
    path("owner/", views.owner_dashboard, name="owner_dashboard"),
    path(
        "owner/payment-operations/",
        views.payment_operations,
        name="payment_operations",
    ),
    path("owner/rates/", views.scheme_rates, name="scheme_rates"),
    path(
        "owner/redemptions/eligibility/",
        views.redemption_eligibility,
        name="redemption_eligibility",
    ),
    path("owner/redemptions/", views.redemption_list, name="redemption_list"),
    path("owner/audit/", views.audit_log, name="audit_log"),
    path(
        "owner/reminders/",
        views.reminder_delivery_log,
        name="reminder_delivery_log",
    ),
    path("owner/exceptions/", views.exception_queue, name="exception_queue"),
    path(
        "owner/exceptions/webhooks/<int:event_id>/recovery/",
        views.webhook_recovery,
        name="webhook_recovery",
    ),
    path(
        "owner/exports/contributions.csv",
        views.contribution_export,
        name="contribution_export",
    ),
    path(
        "owner/exports/redemptions.csv",
        views.redemption_export,
        name="redemption_export",
    ),
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
    path(
        "owner/enrolment-requests/",
        views.owner_enrolment_request_list,
        name="owner_enrolment_request_list",
    ),
    path(
        "owner/enrolment-requests/<uuid:request_id>/",
        views.owner_enrolment_request_detail,
        name="owner_enrolment_request_detail",
    ),
    path(
        "owner/enrolment-requests/<uuid:request_id>/enrol/",
        views.owner_enrolment_request_enroll,
        name="owner_enrolment_request_enroll",
    ),
    path(
        "owner/enrolment-requests/<uuid:request_id>/decline/",
        views.owner_enrolment_request_decline,
        name="owner_enrolment_request_decline",
    ),
    path(
        "owner/enrolment-requests/<uuid:request_id>/expire/",
        views.owner_enrolment_request_expire,
        name="owner_enrolment_request_expire",
    ),
    path(
        "owner/customers/<int:customer_id>/invitation/resend/",
        views.customer_invitation_resend,
        name="customer_invitation_resend",
    ),
    path("owner/plans/", views.plan_list, name="plan_list"),
    path("owner/plans/add/", views.plan_add, name="plan_add"),
    path("owner/plans/<int:plan_id>/edit/", views.plan_edit, name="plan_edit"),
    path("owner/contributions/", views.contribution_list, name="contribution_list"),
    path(
        "owner/schemes/<str:scheme_number>/cash-contribution/",
        views.in_store_cash_contribution,
        name="in_store_cash_contribution",
    ),
    path(
        "owner/contributions/<int:contribution_id>/reverse-cash/",
        views.in_store_cash_contribution_reverse,
        name="in_store_cash_contribution_reverse",
    ),
    path(
        "owner/contributions/<int:contribution_id>/retry-allocation/",
        views.retry_contribution_allocation,
        name="retry_contribution_allocation",
    ),
    path(
        "documents/contributions/<int:contribution_id>/receipt/",
        views.contribution_receipt,
        name="contribution_receipt",
    ),
    path(
        "documents/schemes/<str:scheme_number>/statement/",
        views.scheme_statement,
        name="scheme_statement",
    ),
    path("mine/", views.my_schemes, name="my_schemes"),
    path(
        "plans/<int:plan_id>/request/",
        views.scheme_enrolment_request_create,
        name="scheme_enrolment_request_create",
    ),
    path(
        "mine/enrolment-requests/",
        views.my_enrolment_requests,
        name="my_enrolment_requests",
    ),
    path(
        "mine/enrolment-requests/<uuid:request_id>/",
        views.my_enrolment_request_detail,
        name="my_enrolment_request_detail",
    ),
    path(
        "mine/enrolment-requests/<uuid:request_id>/withdraw/",
        views.my_enrolment_request_withdraw,
        name="my_enrolment_request_withdraw",
    ),
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
