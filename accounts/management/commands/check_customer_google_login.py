from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount, SocialApp, SocialToken
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Validate customer Google identity links without mutation or secret output."

    def handle(self, *args, **options):
        accounts = list(
            SocialAccount.objects.select_related("user", "user__customer_profile")
        )
        verified_emails = {
            (address.user_id, address.email.strip().casefold())
            for address in EmailAddress.objects.filter(verified=True).only(
                "user_id", "email"
            )
        }
        checks = {
            "non_google_links": sum(
                account.provider != "google" for account in accounts
            ),
            "non_customer_links": sum(
                account.user.role != account.user.Role.CUSTOMER
                or account.user.is_staff
                or account.user.is_superuser
                for account in accounts
            ),
            "links_without_customer_profile": sum(
                not hasattr(account.user, "customer_profile") for account in accounts
            ),
            "inactive_links": sum(not account.user.is_active for account in accounts),
            "links_without_password_fallback": sum(
                not account.user.has_usable_password() for account in accounts
            ),
            "links_without_verified_login_email": sum(
                (account.user_id, account.user.email.strip().casefold())
                not in verified_emails
                for account in accounts
            ),
            "stored_social_tokens": SocialToken.objects.count(),
            "database_google_apps": SocialApp.objects.filter(
                provider="google"
            ).count(),
        }
        status = "ok" if not any(checks.values()) else "error"
        counts = " ".join(f"{name}={value}" for name, value in checks.items())
        self.stdout.write(
            "customer_google_login "
            f"status={status} release={settings.APP_RELEASE} "
            f"enabled={str(settings.CUSTOMER_GOOGLE_LOGIN_ENABLED).lower()} "
            f"linked_customers={len(accounts)} {counts}"
        )
        if status != "ok":
            raise CommandError(
                "Customer Google identity integrity failed; keep the feature "
                "disabled and investigate the reported counts."
            )
