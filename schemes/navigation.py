"""Local presentation destinations; never a permission or financial authority."""
from urllib.parse import urlencode, urlsplit

from django.urls import reverse


def application_inbox_url(request):
    value = request.POST.get("return_to", request.GET.get("return_to", ""))
    default = reverse("schemes:owner_applications")
    if len(value) > 1200 or any(char in value for char in ("\\", "\r", "\n")):
        return default
    try:
        parts = urlsplit(value)
    except ValueError:
        return default
    if parts.scheme or parts.netloc or parts.path != default or parts.fragment:
        return default
    return value


def review_destination(request, name, **kwargs):
    if not (request.POST.get("return_to") or request.GET.get("return_to")):
        return reverse(name, kwargs=kwargs)
    return reverse(name, kwargs=kwargs) + "?" + urlencode({"return_to": application_inbox_url(request)})


def workspace_context(request):
    user = request.user
    owner = bool(user.is_authenticated and user.is_active and (user.is_superuser or user.role == "OWNER"))
    customer = bool(user.is_authenticated and user.is_active and user.role == "CUSTOMER" and not owner)
    return {
        "workspace_owner": owner, "workspace_customer": customer,
        "application_inbox_url": application_inbox_url(request),
    }


def fragment_session(view):
    """Only adapt expired-session navigation; existing view guards still authorize."""
    from functools import wraps
    from django.http import HttpResponse
    from django.utils.cache import add_never_cache_headers, patch_vary_headers

    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if request.headers.get("HX-Request") == "true" and not request.user.is_authenticated:
            response = HttpResponse(headers={"HX-Redirect": reverse("account_login") + "?" + urlencode({"next": request.get_full_path()})})
        else:
            response = view(request, *args, **kwargs)
        add_never_cache_headers(response)
        patch_vary_headers(response, ("HX-Request", "HX-History-Restore-Request"))
        return response
    return wrapped


def private_read_template(request, full, fragment):
    return fragment if request.headers.get("HX-Request") == "true" and request.headers.get("HX-History-Restore-Request") != "true" else full
