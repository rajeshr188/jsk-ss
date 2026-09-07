from datetime import timedelta

from allauth.socialaccount.models import SocialAccount
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count, Q
from django.utils import timezone

from accounts.models import (
    CustomerAccountDeletionAction,
    CustomerAccountDeletionAttempt,
    CustomerAccountDeletionRequest,
)


class Command(BaseCommand):
    help = "Check aggregate customer account-deletion workflow integrity."

    def handle(self, *args, **options):
        now = timezone.now()
        statuses = {
            status: CustomerAccountDeletionRequest.objects.filter(status=status).count()
            for status in CustomerAccountDeletionRequest.Status.values
        }
        pending_expired = CustomerAccountDeletionRequest.objects.filter(
            status=CustomerAccountDeletionRequest.Status.PENDING_VERIFICATION,
            verification_expires_at__lte=now,
        ).count()
        contained = CustomerAccountDeletionRequest.objects.filter(
            status__in=[
                CustomerAccountDeletionRequest.Status.CONTAINED,
                CustomerAccountDeletionRequest.Status.AWAITING_SETTLEMENT,
                CustomerAccountDeletionRequest.Status.APPROVED,
            ]
        )
        active_contained_logins = contained.filter(customer__user__is_active=True).count()
        contained_google_links = SocialAccount.objects.filter(
            provider="google",
            user__customer_profile__account_deletion_requests__status__in=[
                CustomerAccountDeletionRequest.Status.CONTAINED,
                CustomerAccountDeletionRequest.Status.AWAITING_SETTLEMENT,
                CustomerAccountDeletionRequest.Status.APPROVED,
            ],
        ).count()
        overdue_owner_reviews = contained.filter(owner_review_due_at__lt=now).count()
        held_without_decision = (
            CustomerAccountDeletionRequest.objects.filter(
                status=CustomerAccountDeletionRequest.Status.AWAITING_SETTLEMENT
            )
            .annotate(decision_count=Count("decisions"))
            .filter(decision_count=0)
            .count()
        )
        requested_missing_actions = (
            CustomerAccountDeletionRequest.objects.annotate(
                requested_actions=Count(
                    "actions",
                    filter=Q(
                        actions__action=CustomerAccountDeletionAction.Action.REQUESTED
                    ),
                )
            )
            .filter(requested_actions=0)
            .count()
        )
        contained_missing_actions = (
            contained.annotate(
                contained_actions=Count(
                    "actions",
                    filter=Q(
                        actions__action=CustomerAccountDeletionAction.Action.CONTAINED
                    ),
                )
            )
            .filter(contained_actions=0)
            .count()
        )
        unsupported_final_states = CustomerAccountDeletionRequest.objects.filter(
            status__in=[
                CustomerAccountDeletionRequest.Status.APPROVED,
                CustomerAccountDeletionRequest.Status.COMPLETED,
                CustomerAccountDeletionRequest.Status.COMPLETED_WITH_RETENTION,
                CustomerAccountDeletionRequest.Status.REJECTED,
                CustomerAccountDeletionRequest.Status.WITHDRAWN,
            ]
        ).count()
        invalid_customer_roles = CustomerAccountDeletionRequest.objects.exclude(
            customer__user__role="CUSTOMER",
        ).count()
        stale_attempts = CustomerAccountDeletionAttempt.objects.filter(
            attempted_at__lt=now
            - timedelta(
                hours=settings.CUSTOMER_ACCOUNT_DELETION_ATTEMPT_RETENTION_HOURS
            )
        ).count()

        errors = sum(
            [
                pending_expired,
                active_contained_logins,
                contained_google_links,
                overdue_owner_reviews,
                held_without_decision,
                requested_missing_actions,
                contained_missing_actions,
                unsupported_final_states,
                invalid_customer_roles,
                stale_attempts,
            ]
        )
        summary = " ".join(
            [
                f"customer_account_deletions status={'ok' if errors == 0 else 'error'}",
                f"release={settings.APP_RELEASE}",
                f"enabled={str(settings.CUSTOMER_ACCOUNT_DELETION_ENABLED).lower()}",
                f"pending_verification={statuses[CustomerAccountDeletionRequest.Status.PENDING_VERIFICATION]}",
                f"contained={statuses[CustomerAccountDeletionRequest.Status.CONTAINED]}",
                f"awaiting_settlement={statuses[CustomerAccountDeletionRequest.Status.AWAITING_SETTLEMENT]}",
                f"completed={statuses[CustomerAccountDeletionRequest.Status.COMPLETED]}",
                f"completed_with_retention={statuses[CustomerAccountDeletionRequest.Status.COMPLETED_WITH_RETENTION]}",
                f"pending_expired={pending_expired}",
                f"active_contained_logins={active_contained_logins}",
                f"contained_google_links={contained_google_links}",
                f"overdue_owner_reviews={overdue_owner_reviews}",
                f"held_without_decision={held_without_decision}",
                f"requested_missing_actions={requested_missing_actions}",
                f"contained_missing_actions={contained_missing_actions}",
                f"unsupported_final_states={unsupported_final_states}",
                f"invalid_customer_roles={invalid_customer_roles}",
                f"stale_attempts={stale_attempts}",
            ]
        )
        if errors:
            raise CommandError(summary)
        self.stdout.write(self.style.SUCCESS(summary))
