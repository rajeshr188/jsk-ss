from wagtail.models import Site

from datetime import datetime, time, timedelta
from django.db.models import Min, OuterRef, Subquery, Sum
from django.utils import timezone

from accounts.models import CustomerInvitation, CustomerRegistration, PlanApplication, PlanApplicationConfirmation
from schemes.models import Contribution, GatewayMode, PaymentChannel, SchemeAccount, SchemeEnrolmentRequest
from .models import PublicFunnelDailyCount


def public_editorial_page(page_model):
    """Return the single live editorial page inside the default Site tree."""
    site = Site.objects.select_related("root_page").filter(is_default_site=True).first()
    if site is None:
        return None
    return (
        page_model.objects.live()
        .public()
        .descendant_of(site.root_page, inclusive=True)
        .first()
    )


def get_funnel_report(*, start, end):
    """Period throughput, not a joined visitor cohort or inferred conversion rate."""
    lower = timezone.make_aware(datetime.combine(start, time.min))
    upper = timezone.make_aware(datetime.combine(end + timedelta(days=1), time.min))

    def during(queryset, field):
        return queryset.filter(**{f"{field}__gte": lower, f"{field}__lt": upper})

    navigation = {step: 0 for step in PublicFunnelDailyCount.Step.values}
    for row in PublicFunnelDailyCount.objects.filter(day__gte=start, day__lte=end).values("step").annotate(total=Sum("count")):
        navigation[row["step"]] = row["total"]

    verified = Contribution.objects.filter(status__in=[Contribution.Status.PAID, Contribution.Status.PAID_UNALLOCATED], paid_at__isnull=False)
    online = verified.filter(payment_channel=PaymentChannel.RAZORPAY, gateway_mode=GatewayMode.LIVE)
    cash = verified.filter(payment_channel=PaymentChannel.IN_STORE_CASH)

    def first_payments(queryset):
        return queryset.order_by().values("scheme_account_id").annotate(first_at=Min("paid_at")).filter(first_at__gte=lower, first_at__lt=upper).count()

    first_online_id = online.filter(scheme_account_id=OuterRef("scheme_account_id")).order_by("paid_at", "pk").values("pk")[:1]
    return {
        "start": start.isoformat(), "end": end.isoformat(), "timezone": "Asia/Kolkata",
        "navigation_requests": navigation,
        "outcomes": {
            "registrations_submitted": during(CustomerRegistration.objects.all(), "submitted_at").count(),
            "registration_emails_verified": during(CustomerRegistration.objects.all(), "email_verified_at").count(),
            "registration_reviews_completed": during(CustomerRegistration.objects.all(), "reviewed_at").count(),
            "registration_approvals": during(CustomerRegistration.objects.filter(status=CustomerRegistration.Status.APPROVED), "reviewed_at").count(),
            "enrolment_requests_submitted": during(SchemeEnrolmentRequest.objects.all(), "created_at").count(),
            "plan_applications_submitted": during(PlanApplication.objects.all(), "registration__submitted_at").count(),
            "plan_applications_customer_confirmed": during(PlanApplicationConfirmation.objects.filter(final=True), "confirmed_at").values("application_id").distinct().count(),
            "agreements_created": during(SchemeAccount.objects.all(), "created_at").count(),
            "logins_activated": during(CustomerInvitation.objects.all(), "accepted_at").values("user_id").distinct().count(),
            "first_live_online_payments": first_payments(online),
            "subsequent_live_online_payments": during(online, "paid_at").exclude(pk=Subquery(first_online_id)).count(),
            "first_showroom_cash_payments": first_payments(cash),
            "live_online_allocations_pending": online.filter(status=Contribution.Status.PAID_UNALLOCATED).count(),
        },
    }
