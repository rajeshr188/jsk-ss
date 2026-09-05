from allauth.account.adapter import DefaultAccountAdapter
from allauth.account.models import EmailAddress
from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.socialaccount.providers.base import AuthProcess
from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import redirect


class AccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request):
        # Customer credentials are created through the owner workflow.
        return False

    def render_mail(self, template_prefix, email, context, headers=None):
        # Authentication links must remain direct, untracked owned-domain URLs.
        headers = {
            **(headers or {}),
            "X-PM-TrackLinks": "None",
            "X-PM-TrackOpens": "false",
        }
        return super().render_mail(
            template_prefix,
            email,
            context,
            headers=headers,
        )


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    """Restrict Google to an explicit credential link for approved customers."""

    login_denied_message = (
        "Google sign-in is available only after it has been connected from an "
        "approved customer account. Please sign in with your password first."
    )

    def is_open_for_signup(self, request, sociallogin):
        # Social providers are credentials only; they never create local users.
        return False

    def pre_social_login(self, request, sociallogin):
        process = sociallogin.state.get("process", AuthProcess.LOGIN)
        if (
            not settings.CUSTOMER_GOOGLE_LOGIN_ENABLED
            or sociallogin.account.provider != "google"
        ):
            self._deny(request, process)

        if process == AuthProcess.CONNECT:
            self._validate_connection(request, sociallogin, process)
            return

        if process != AuthProcess.LOGIN or not sociallogin.is_existing:
            self._deny(request, process)

        if request.user.is_authenticated or not self._is_eligible_customer(
            sociallogin.user
        ):
            self._deny(request, process)
        if not self._has_verified_login_email(sociallogin.user):
            self._deny(request, process)

    def validate_disconnect(self, account, accounts):
        # Phase 1 preserves the identity binding. A separately audited removal
        # workflow is required before customers can disconnect it themselves.
        raise ValidationError(
            "Google sign-in cannot be removed online yet. Contact the showroom "
            "if the connected account must be disabled."
        )

    def _validate_connection(self, request, sociallogin, process):
        user = request.user
        if not user.is_authenticated or not self._is_eligible_customer(user):
            self._deny(request, process)

        login_email = self._normalize_email(user.email)
        provider_emails = {
            self._normalize_email(address.email)
            for address in sociallogin.email_addresses
            if address.verified
        }
        local_email_is_verified = self._has_verified_login_email(user)
        if (
            not login_email
            or not local_email_is_verified
            or login_email not in provider_emails
        ):
            messages.error(
                request,
                "The verified Google email must exactly match your verified customer "
                "login email. No account was connected.",
            )
            raise ImmediateHttpResponse(redirect("socialaccount_connections"))

        if sociallogin.is_existing and sociallogin.user != user:
            self._deny(request, process)

    @staticmethod
    def _normalize_email(value):
        return (value or "").strip().casefold()

    @staticmethod
    def _is_eligible_customer(user):
        return bool(
            user.is_active
            and user.role == user.Role.CUSTOMER
            and not user.is_staff
            and not user.is_superuser
            and user.has_usable_password()
            and hasattr(user, "customer_profile")
        )

    @staticmethod
    def _has_verified_login_email(user):
        return bool(
            user.email
            and EmailAddress.objects.filter(
                user=user,
                email__iexact=user.email,
                verified=True,
            ).exists()
        )

    def _deny(self, request, process):
        messages.error(request, self.login_denied_message)
        destination = (
            "socialaccount_connections"
            if request.user.is_authenticated and process == AuthProcess.CONNECT
            else "account_login"
        )
        raise ImmediateHttpResponse(redirect(destination))
