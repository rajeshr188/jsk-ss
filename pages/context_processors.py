from django.conf import settings

from .business import showroom_details


def pwa(request):
    return {"pwa_enabled": settings.PWA_ENABLED}


def showroom(request):
    return {"showroom": showroom_details()}
