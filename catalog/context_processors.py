from django.conf import settings

from .selectors import public_catalogue_root


def public_catalogue_navigation(request):
    if not settings.PUBLIC_CATALOGUE_ENABLED:
        return {
            "public_catalogue_page": None,
            "public_catalogue_url": "",
            "public_catalogue_is_current": False,
        }
    catalogue = public_catalogue_root()
    catalogue_url = catalogue.get_url(request=request) if catalogue else ""
    return {
        "public_catalogue_page": catalogue,
        "public_catalogue_url": catalogue_url,
        "public_catalogue_is_current": bool(
            catalogue_url and request.path.startswith(catalogue_url)
        ),
    }
