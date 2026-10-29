from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db.models import F, Q
from django.utils import timezone

from accounts.models import CustomerRegistration, CustomerRegistrationAttempt, PlanApplication


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
        plan_applications = PlanApplication.objects.all()
        approved_without_agreement = plan_applications.filter(
            registration__status="APPROVED", scheme_account__isnull=True,
        ).count()
        linked = plan_applications.filter(scheme_account__isnull=False)
        valid_identity = Q(
            registration__status="APPROVED",
            registration__approved_user_id=F("scheme_account__customer__user_id"),
            plan_id=F("scheme_account__plan_id"), start_date=F("scheme_account__start_date"),
        ) & (Q(metal_grade_id=F("scheme_account__metal_grade_id"))
             | Q(metal_grade__isnull=True, scheme_account__metal_grade__isnull=True)) & (
            Q(requested_months=F("scheme_account__agreed_months"))
            | Q(requested_months__isnull=True, scheme_account__agreed_months__isnull=True))
        agreement_identity_mismatches = linked.exclude(valid_identity).count()
        from accounts.application_contracts import validate_independent_application
        independent_term_mismatches = 0
        for application in plan_applications.filter(terms_schema_version=2).select_related("scheme_account").iterator():
            try:
                validate_independent_application(application)
            except (ValidationError, ObjectDoesNotExist):
                independent_term_mismatches += 1

        errors = (
            approved_missing_customer
            + approved_wrong_role
            + approved_email_mismatches
            + approved_without_agreement
            + agreement_identity_mismatches
            + independent_term_mismatches
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
                    f"plan_applications={plan_applications.count()}",
                    f"approved_without_agreement={approved_without_agreement}",
                    f"agreement_identity_mismatches={agreement_identity_mismatches}",
                    f"independent_term_mismatches={independent_term_mismatches}",
                ]
            )
        )
        if errors:
            raise CommandError(
                "Public customer registration integrity violations require review."
            )
