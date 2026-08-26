from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count
from django.db.models.functions import Lower


class Command(BaseCommand):
    help = "Check login email uniqueness before deploying customer invitations."

    def handle(self, *args, **options):
        user_model = get_user_model()
        duplicate_groups = list(
            user_model.objects.exclude(email="")
            .annotate(normalized_email=Lower("email"))
            .values("normalized_email")
            .annotate(matches=Count("pk"))
            .filter(matches__gt=1)
            .order_by("normalized_email")
        )
        blank_email_users = user_model.objects.filter(email="").count()

        if duplicate_groups:
            duplicate_accounts = sum(group["matches"] for group in duplicate_groups)
            raise CommandError(
                "Auth email integrity failed: "
                f"duplicate_groups={len(duplicate_groups)} "
                f"affected_accounts={duplicate_accounts}. "
                "Inspect and resolve these accounts deliberately before migration; "
                "do not delete or merge financial records automatically."
            )

        self.stdout.write(
            self.style.SUCCESS(
                "Auth email integrity passed: "
                f"duplicate_groups=0 blank_email_users={blank_email_users}."
            )
        )
