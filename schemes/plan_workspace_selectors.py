"""Private plan usage reads; never change publication or accepted agreements."""
from django.db.models import Count, Q

from accounts.models import PlanApplication

from .models import Customer, SchemeAccount, SchemeEnrolmentRequest, SchemePlan, SchemePlanRevision
from .selectors import get_enrollable_scheme_plans, get_public_scheme_plans


def get_owner_plan_workspace(plan_id):
    plan = (SchemePlan.objects.select_related("configuration", "publication_revision", "catalogue_closure")
            .prefetch_related("metal_offerings__metal_grade").filter(pk=plan_id).first())
    if plan is None:
        return None
    agreements = SchemeAccount.objects.filter(plan_id=plan.pk)
    counts = agreements.aggregate(
        agreements=Count("pk"), customers=Count("customer_id", distinct=True),
        open_agreements=Count("pk", filter=~Q(status__in=[
            SchemeAccount.Status.REDEEMED, SchemeAccount.Status.CANCELLED])),
        redeemed=Count("pk", filter=Q(status=SchemeAccount.Status.REDEEMED)),
        cancelled=Count("pk", filter=Q(status=SchemeAccount.Status.CANCELLED)),
    )
    requests = SchemeEnrolmentRequest.objects.filter(plan_id=plan.pk)
    applications = PlanApplication.objects.filter(plan_id=plan.pk)
    counts["requests"] = requests.count()
    counts["pending_requests"] = requests.filter(status=SchemeEnrolmentRequest.Status.PENDING_OWNER_REVIEW).count()
    counts["applications"] = applications.count()
    return {
        "plan": plan, "counts": counts,
        "publicly_available": get_public_scheme_plans().filter(pk=plan.pk).exists(),
        "enrolment_available": get_enrollable_scheme_plans().filter(pk=plan.pk).exists(),
    }


def get_plan_agreements(plan_id):
    return (SchemeAccount.objects.filter(plan_id=plan_id)
            .select_related("customer", "plan", "metal_grade", "configuration_snapshot", "plan_revision")
            .order_by("-created_at", "-pk"))


def get_plan_customers(plan_id):
    # A customer may have several agreements; both the result and its counts are plan-scoped.
    return (Customer.objects.filter(scheme_accounts__plan_id=plan_id)
            .annotate(plan_agreement_count=Count("scheme_accounts"),
                      plan_open_count=Count("scheme_accounts", filter=~Q(scheme_accounts__status__in=[
                          SchemeAccount.Status.REDEEMED, SchemeAccount.Status.CANCELLED])))
            .order_by("full_name", "pk"))


def get_plan_requests(plan_id):
    return (SchemeEnrolmentRequest.objects.filter(plan_id=plan_id)
            .select_related("customer", "metal_grade", "scheme_account").order_by("-created_at", "-pk"))


def get_plan_applications(plan_id):
    return (PlanApplication.objects.filter(plan_id=plan_id)
            .select_related("registration", "metal_grade", "scheme_account")
            .order_by("-registration__submitted_at", "-pk"))


def get_plan_revisions(plan_id):
    return (SchemePlanRevision.objects.filter(plan_id=plan_id)
            .annotate(agreement_count=Count("scheme_accounts")).order_by("-number", "-pk"))
