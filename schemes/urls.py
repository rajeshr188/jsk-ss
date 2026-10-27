from django.urls import path

from . import views, instalment_views, closure_views, settlement_views, manual_views, benefit_reapplication_views
from .order_reconciliation import order_reconciliation
from .optional_order_views import optional_order_recovery

app_name = "schemes"

urlpatterns = [
    path("owner/exceptions/optional-orders/<int:contribution_id>/", optional_order_recovery, name="optional_order_recovery"),
    path("owner/agreements/<str:scheme_number>/benefit-review/", benefit_reapplication_views.benefit_reapplication_workspace, name="benefit_reapplication"),
    path("owner/exceptions/checkouts/<int:contribution_id>/", order_reconciliation, name="order_reconciliation"),
    path("owner/closures/<uuid:request_id>/settlement/", settlement_views.settlement_workspace, name="configured_settlement"),
    path("owner/closures/", closure_views.closure_queue, name="closure_queue"),
    path("agreements/<str:scheme_number>/closure/", closure_views.closure_workspace, name="closure_workspace"),
    path("start/", views.post_login, name="post_login"),
    path("owner/", views.owner_dashboard, name="owner_dashboard"),
    path("owner/today/", views.owner_today, name="owner_today"),
    path("owner/applications/", views.owner_applications, name="owner_applications"),
    path("owner/activation/", views.owner_activation_queue, name="owner_activation_queue"),
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
    path("owner/instalment-reviews/", instalment_views.review_queue, name="instalment_review_queue"),
    path("owner/instalment-reviews/<int:period_id>/", instalment_views.review_period, name="instalment_review_period"),
    path("owner/instalment-outages/<int:hold_id>/resolve/", instalment_views.resolve_outage, name="instalment_outage_resolution"),
    path("owner/instalment-orders/<int:reservation_id>/recover/", instalment_views.recover_order, name="instalment_order_recovery"),
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
    path("owner/plan-manual/", manual_views.plan_manual, name="plan_manual"),
    path("owner/plan-manual/assets/<str:filename>", manual_views.plan_manual_asset, name="plan_manual_asset"),
    path("owner/plan-configurations/", views.plan_configuration_list, name="plan_configuration_list"),
    path("owner/plan-configurations/add/", views.plan_configuration_create, name="plan_configuration_create"),
    path("owner/plan-configurations/independent/add/", views.plan_configuration_create,
        {"independent": True}, name="independent_configuration_create"),
    path("owner/plan-configurations/<int:configuration_id>/", views.plan_configuration_detail, name="plan_configuration_detail"),
    path("owner/plan-configurations/<int:previous_id>/new-version/", views.plan_configuration_create, name="plan_configuration_new_version"),
    path("owner/plan-configurations/<int:configuration_id>/plan/", views.configured_plan_create, name="configured_plan_create"),
    path("owner/plans/add/", views.plan_add, name="plan_add"),
    path("owner/plans/<int:plan_id>/edit/", views.plan_edit, name="plan_edit"),
    path("owner/plans/<int:plan_id>/publication/", views.configured_plan_publication, name="configured_plan_publication"),
    path("owner/contributions/", views.contribution_list, name="contribution_list"),
    path("owner/contributions/<int:contribution_id>/", views.owner_payment_detail, name="owner_payment_detail"),
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
    path("mine/plans/", views.my_schemes, {"section": "plans"}, name="customer_plans"),
    path("mine/applications/", views.customer_applications, name="customer_applications"),
    path("mine/documents/", views.customer_documents, name="customer_documents"),
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
    path("mine/payments/<int:contribution_id>/status/", views.payment_status, name="payment_status"),
    path(
        "payments/razorpay/webhook/",
        views.razorpay_webhook,
        name="razorpay_webhook",
    ),
]
