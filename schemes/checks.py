from django.conf import settings
from django.core.checks import Error, Tags, Warning, register


@register(Tags.security, deploy=True)
def production_configuration(app_configs, **kwargs):
    issues = []

    if settings.PAYMENT_GATEWAY == "mock":
        issues.append(
            Error(
                "The mock payment gateway must not be deployed.",
                hint="Configure a supported non-mock gateway or disable contributions.",
                id="jsk.E001",
            )
        )
    elif settings.PAYMENT_GATEWAY == "razorpay":
        missing = [
            name
            for name in (
                "RAZORPAY_KEY_ID",
                "RAZORPAY_KEY_SECRET",
                "RAZORPAY_WEBHOOK_SECRET",
            )
            if not getattr(settings, name)
        ]
        if missing:
            issues.append(
                Error(
                    "Razorpay is selected but required credentials are missing.",
                    hint=f"Configure these server-side values: {', '.join(missing)}.",
                    id="jsk.E006",
                )
            )
        elif not settings.RAZORPAY_KEY_ID.startswith("rzp_test_"):
            issues.append(
                Error(
                    "This release accepts only Razorpay Test Mode credentials.",
                    hint="Keep live mode disabled until its operational gates are complete.",
                    id="jsk.E007",
                )
            )
    elif settings.PAYMENT_GATEWAY:
        issues.append(
            Error(
                "The configured payment gateway is unsupported.",
                hint="Use razorpay or leave the setting empty to disable contributions.",
                id="jsk.E008",
            )
        )
    if settings.METAL_RATE_PROVIDER == "mock":
        issues.append(
            Error(
                "The mock metal-rate provider must not be deployed.",
                hint="Configure GoldAPI or disable metal contributions.",
                id="jsk.E002",
            )
        )
    elif settings.METAL_RATE_PROVIDER == "goldapi" and not settings.GOLDAPI_API_KEY:
        issues.append(
            Error(
                "GoldAPI is selected but GOLDAPI_API_KEY is missing.",
                id="jsk.E009",
            )
        )
    elif settings.METAL_RATE_PROVIDER not in {"", "goldapi"}:
        issues.append(
            Error(
                "The configured metal-rate provider is unsupported.",
                hint="Use goldapi or leave the setting empty to disable metal rates.",
                id="jsk.E010",
            )
        )

    unsafe_email_backends = {
        "django.core.mail.backends.console.EmailBackend",
        "django.core.mail.backends.dummy.EmailBackend",
        "django.core.mail.backends.locmem.EmailBackend",
    }
    if settings.EMAIL_BACKEND in unsafe_email_backends:
        issues.append(
            Error(
                "The configured email backend does not deliver production email.",
                hint="Configure and verify an SMTP or transactional email backend.",
                id="jsk.E003",
            )
        )
    elif (
        settings.EMAIL_BACKEND == "django.core.mail.backends.smtp.EmailBackend"
        and not settings.EMAIL_HOST
    ):
        issues.append(
            Error(
                "SMTP email is selected but EMAIL_HOST is empty.",
                id="jsk.E011",
            )
        )

    if "*" in settings.ALLOWED_HOSTS:
        issues.append(
            Error(
                "ALLOWED_HOSTS must not contain a wildcard in production.",
                hint="List each public application hostname explicitly.",
                id="jsk.E004",
            )
        )

    insecure_origins = [
        origin
        for origin in settings.CSRF_TRUSTED_ORIGINS
        if not origin.lower().startswith("https://")
    ]
    if insecure_origins:
        issues.append(
            Error(
                "CSRF_TRUSTED_ORIGINS contains a non-HTTPS origin.",
                hint="Production trusted origins must use HTTPS.",
                id="jsk.E005",
            )
        )

    if settings.APP_RELEASE == "unknown":
        issues.append(
            Warning(
                "APP_RELEASE is not configured.",
                hint="Set it to the deployed commit or immutable image version.",
                id="jsk.W001",
            )
        )

    sslmode = settings.DATABASES["default"].get("OPTIONS", {}).get("sslmode")
    if sslmode in {None, "disable", "allow", "prefer"}:
        issues.append(
            Warning(
                "The database connection does not require TLS.",
                hint="For a remote production database, set sslmode=require or stronger.",
                id="jsk.W002",
            )
        )

    return issues
