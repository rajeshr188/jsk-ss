from django.conf import settings


def public_customer_registration(request):
    return {
        "public_customer_registration_enabled": (
            settings.PUBLIC_CUSTOMER_REGISTRATION_ENABLED
        )
    }


def customer_google_login(request):
    return {
        "customer_google_login_enabled": settings.CUSTOMER_GOOGLE_LOGIN_ENABLED,
    }
