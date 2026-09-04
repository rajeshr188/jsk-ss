from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db.models import F
from django.utils import timezone

from accounts.models import CustomerRegistration, CustomerRegistrationAttempt


class Command(BaseCommand):
    help = "Check staged public customer-registration integrity and aggregate state."

    def handle(self, *args, **options):
        statuses = {
            status: CustomerRegistration.objects.filter(status=status).count()
            for status in CustomerRegistration.Status.values
        }
        expired_pending = CustomerRegistration.objects.filter(
            status=CustomerRegistration.Status.PENDING_EMAIL_VERIFICATION,
            email_verification_expires_at__lte=timezone.now(),
        ).count()
        approved = CustomerRegistration.objects.filter(
            status=CustomerRegistration.Status.APPROVED
        )
        approved_missing_customer = approved.filter(
            approved_user__customer_profile__isnull=True
        ).count()
        approved_wrong_role = approved.exclude(
            approved_user__role=get_user_model().Role.CUSTOMER
        ).count()
        approved_email_mismatches = approved.exclude(
            email__iexact=F("approved_user__email")
        ).count()
        attempts = CustomerRegistrationAttempt.objects.count()

        errors = (
            approved_missing_customer
            + approved_wrong_role
            + approved_email_mismatches
        )
        status = "ok" if errors == 0 else "error"
        self.stdout.write(
            " ".join(
                [
                    f"public_customer_registrations status={status}",
                    f"release={settings.APP_RELEASE}",
                    f"enabled={str(settings.PUBLIC_CUSTOMER_REGISTRATION_ENABLED).lower()}",
                    f"pending_email={statuses[CustomerRegistration.Status.PENDING_EMAIL_VERIFICATION]}",
                    f"awaiting_owner={statuses[CustomerRegistration.Status.AWAITING_OWNER_APPROVAL]}",
                    f"approved={statuses[CustomerRegistration.Status.APPROVED]}",
                    f"rejected={statuses[CustomerRegistration.Status.REJECTED]}",
                    f"expired={statuses[CustomerRegistration.Status.EXPIRED]}",
                    f"expired_pending={expired_pending}",
                    f"attempts_retained={attempts}",
                    f"approved_missing_customer={approved_missing_customer}",
                    f"approved_wrong_role={approved_wrong_role}",
                    f"approved_email_mismatches={approved_email_mismatches}",
                ]
            )
        )
        if errors:
            raise CommandError(
                "Public customer registration integrity violations require review."
            )
