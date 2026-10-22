from django.conf import settings


def public_customer_registration(request):
    return {
        "public_customer_registration_enabled": (
            settings.PUBLIC_CUSTOMER_REGISTRATION_ENABLED
        )
    }


def customer_google_login(request):
    from .adapters import SocialAccountAdapter
    enabled = settings.CUSTOMER_GOOGLE_LOGIN_ENABLED
    eligible = bool(enabled and request.user.is_authenticated and
                    SocialAccountAdapter._is_eligible_customer(request.user) and
                    SocialAccountAdapter._has_verified_login_email(request.user))
    return {
        "customer_google_login_enabled": enabled,
        "customer_google_connection_eligible": eligible,
    }


def customer_account_deletion(request):
    return {
        "customer_account_deletion_enabled": (
            settings.CUSTOMER_ACCOUNT_DELETION_ENABLED
        ),
    }
