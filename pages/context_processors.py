from django.conf import settings


def pwa(request):
    return {"pwa_enabled": settings.PWA_ENABLED}
