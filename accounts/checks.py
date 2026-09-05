from django.conf import settings
from django.core.checks import Error, Tags, register


@register(Tags.security, deploy=True)
def public_registration_configuration(app_configs, **kwargs):
    if not settings.PUBLIC_CUSTOMER_REGISTRATION_ENABLED:
        return []

    issues = []
    if settings.ACCOUNT_ADAPTER != "accounts.adapters.AccountAdapter":
        issues.append(
            Error(
                "Public customer requests require the closed allauth signup adapter.",
                hint=(
                    "Keep ACCOUNT_ADAPTER=accounts.adapters.AccountAdapter; use the "
                    "staged registration route instead of direct allauth signup."
                ),
                id="jsk.E016",
            )
        )
    from_email = settings.DEFAULT_FROM_EMAIL.lower()
    if not from_email or "example.com" in from_email:
        issues.append(
            Error(
                "Public customer requests require an owned-domain sender address.",
                hint="Set DEFAULT_FROM_EMAIL to the verified production sender.",
                id="jsk.E017",
            )
        )
    return issues


@register(Tags.security, deploy=True)
def customer_google_login_configuration(app_configs, **kwargs):
    issues = []
    required_apps = {
        "allauth.socialaccount",
        "allauth.socialaccount.providers.google",
    }
    missing_apps = required_apps.difference(settings.INSTALLED_APPS)
    if missing_apps:
        issues.append(
            Error(
                "Customer Google login requires the django-allauth Google provider.",
                hint=f"Add these applications: {', '.join(sorted(missing_apps))}.",
                id="jsk.E018",
            )
        )
    if settings.SOCIALACCOUNT_ADAPTER != "accounts.adapters.SocialAccountAdapter":
        issues.append(
            Error(
                "Customer Google login requires the restricted social adapter.",
                hint="Keep SOCIALACCOUNT_ADAPTER=accounts.adapters.SocialAccountAdapter.",
                id="jsk.E019",
            )
        )
    if settings.ACCOUNT_ADAPTER != "accounts.adapters.AccountAdapter":
        issues.append(
            Error(
                "Social credentials require the closed local-signup adapter.",
                hint="Keep ACCOUNT_ADAPTER=accounts.adapters.AccountAdapter.",
                id="jsk.E020",
            )
        )
    unsafe_settings = [
        name
        for name in (
            "SOCIALACCOUNT_AUTO_SIGNUP",
            "SOCIALACCOUNT_EMAIL_AUTHENTICATION",
            "SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT",
            "SOCIALACCOUNT_STORE_TOKENS",
            "SOCIALACCOUNT_LOGIN_ON_GET",
        )
        if getattr(settings, name)
    ]
    if unsafe_settings:
        issues.append(
            Error(
                "Customer Google login has unsafe automatic-authentication settings.",
                hint=f"Keep these settings False: {', '.join(unsafe_settings)}.",
                id="jsk.E021",
            )
        )
    if not settings.ACCOUNT_REAUTHENTICATION_REQUIRED:
        issues.append(
            Error(
                "Connecting a Google identity requires recent authentication.",
                hint="Keep ACCOUNT_REAUTHENTICATION_REQUIRED=True.",
                id="jsk.E022",
            )
        )
    if settings.CUSTOMER_GOOGLE_LOGIN_ENABLED and not (
        settings.GOOGLE_OAUTH_CLIENT_ID and settings.GOOGLE_OAUTH_CLIENT_SECRET
    ):
        issues.append(
            Error(
                "Customer Google login is enabled without complete OAuth credentials.",
                hint="Set both server-side GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET.",
                id="jsk.E023",
            )
        )
    google_configuration = settings.SOCIALACCOUNT_PROVIDERS.get("google", {})
    if set(google_configuration.get("SCOPE", ())) != {"profile", "email"}:
        issues.append(
            Error(
                "Customer Google login must request only the approved identity scopes.",
                hint="Keep the Google SCOPE list limited to profile and email.",
                id="jsk.E024",
            )
        )
    expected_auth_params = {"access_type": "online", "prompt": "select_account"}
    if google_configuration.get("AUTH_PARAMS") != expected_auth_params:
        issues.append(
            Error(
                "Customer Google login must use the reviewed authorization parameters.",
                hint="Keep access_type=online and prompt=select_account.",
                id="jsk.E025",
            )
        )
    return issues
