from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db.models import F, Q
from django.utils import timezone

from schemes.models import SchemeEnrolmentRequest


class Command(BaseCommand):
    help = "Validate customer enrolment-request integrity without mutation."

    def handle(self, *args, **options):
        now = timezone.now()
        pending = SchemeEnrolmentRequest.objects.filter(
            status=SchemeEnrolmentRequest.Status.PENDING_OWNER_REVIEW,
        )
        checks = {
            "enrolled_missing_account": SchemeEnrolmentRequest.objects.filter(
                status=SchemeEnrolmentRequest.Status.ENROLLED,
                scheme_account__isnull=True,
            ).count(),
            "non_enrolled_with_account": SchemeEnrolmentRequest.objects.exclude(
                status=SchemeEnrolmentRequest.Status.ENROLLED,
            ).filter(scheme_account__isnull=False).count(),
            "account_customer_mismatches": SchemeEnrolmentRequest.objects.filter(
                scheme_account__isnull=False,
            ).exclude(scheme_account__customer=F("customer")).count(),
            "account_plan_mismatches": SchemeEnrolmentRequest.objects.filter(
                scheme_account__isnull=False,
            ).exclude(scheme_account__plan=F("plan")).count(),
            "account_grade_mismatches": SchemeEnrolmentRequest.objects.filter(
                scheme_account__isnull=False,
            ).exclude(scheme_account__metal_grade=F("metal_grade")).count(),
            "customer_role_mismatches": SchemeEnrolmentRequest.objects.exclude(
                customer__user__role="CUSTOMER",
            ).count(),
            "invalid_decision_shape": SchemeEnrolmentRequest.objects.filter(
                Q(
                    status=SchemeEnrolmentRequest.Status.PENDING_OWNER_REVIEW,
                )
                & (
                    Q(scheme_account__isnull=False)
                    | Q(decided_at__isnull=False)
                    | ~Q(decided_by_label="")
                    | ~Q(decision_reason="")
                )
                | Q(
                    status__in=[
                        SchemeEnrolmentRequest.Status.WITHDRAWN,
                        SchemeEnrolmentRequest.Status.DECLINED,
                        SchemeEnrolmentRequest.Status.EXPIRED,
                        SchemeEnrolmentRequest.Status.ENROLLED,
                    ]
                )
                & (
                    Q(decided_at__isnull=True)
                    | Q(decided_by_label="")
                    | Q(decision_reason="")
                )
            ).count(),
        }
        operational = {
            "pending": pending.count(),
            "expired_pending": pending.filter(expires_at__lte=now).count(),
            "enrolled": SchemeEnrolmentRequest.objects.filter(
                status=SchemeEnrolmentRequest.Status.ENROLLED,
            ).count(),
            "declined": SchemeEnrolmentRequest.objects.filter(
                status=SchemeEnrolmentRequest.Status.DECLINED,
            ).count(),
            "withdrawn": SchemeEnrolmentRequest.objects.filter(
                status=SchemeEnrolmentRequest.Status.WITHDRAWN,
            ).count(),
            "expired": SchemeEnrolmentRequest.objects.filter(
                status=SchemeEnrolmentRequest.Status.EXPIRED,
            ).count(),
        }
        status = "ok" if not any(checks.values()) else "error"
        counts = " ".join(
            f"{name}={value}" for name, value in {**operational, **checks}.items()
        )
        self.stdout.write(
            "scheme_enrolment_requests "
            f"status={status} release={settings.APP_RELEASE} "
            "enabled="
            f"{str(settings.CUSTOMER_ENROLMENT_REQUESTS_ENABLED).lower()} "
            f"expiry_days={settings.CUSTOMER_ENROLMENT_REQUEST_EXPIRY_DAYS} "
            f"{counts}"
        )
        if status != "ok":
            raise CommandError(
                "Scheme enrolment-request integrity failed; keep the feature "
                "disabled and investigate the reported counts."
            )
