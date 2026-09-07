from django.db.models import Count, Q

from .models import CustomerAccountDeletionRequest


def customer_account_deletion_queue():
    return (
        CustomerAccountDeletionRequest.objects.filter(
            status__in=[
                CustomerAccountDeletionRequest.Status.CONTAINED,
                CustomerAccountDeletionRequest.Status.AWAITING_SETTLEMENT,
            ]
        )
        .select_related("customer", "customer__user")
        .annotate(
            scheme_account_count=Count(
                "customer__scheme_accounts",
                distinct=True,
            ),
            contribution_count=Count(
                "customer__scheme_accounts__contributions",
                distinct=True,
            ),
            pending_provider_count=Count(
                "customer__scheme_accounts__contributions",
                filter=Q(
                    customer__scheme_accounts__contributions__status="PENDING",
                    customer__scheme_accounts__contributions__payment_gateway="razorpay",
                ),
                distinct=True,
            ),
        )
        .order_by("owner_review_due_at", "requested_at")
    )


def customer_account_deletion_detail(deletion_request_id):
    return (
        CustomerAccountDeletionRequest.objects.select_related(
            "customer",
            "customer__user",
        )
        .prefetch_related("actions", "decisions")
        .annotate(
            scheme_account_count=Count(
                "customer__scheme_accounts",
                distinct=True,
            ),
            contribution_count=Count(
                "customer__scheme_accounts__contributions",
                distinct=True,
            ),
            pending_provider_count=Count(
                "customer__scheme_accounts__contributions",
                filter=Q(
                    customer__scheme_accounts__contributions__status="PENDING",
                    customer__scheme_accounts__contributions__payment_gateway="razorpay",
                ),
                distinct=True,
            ),
        )
        .get(pk=deletion_request_id)
    )
