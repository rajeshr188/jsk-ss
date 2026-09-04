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
