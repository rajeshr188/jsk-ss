from django.conf import settings
from django.http import HttpResponseNotFound


SENSITIVE_AUTH_PATH_PREFIXES = (
    "/accounts/password/reset/key/",
    "/accounts/invitations/",
    "/accounts/registrations/verify/",
    "/accounts/google/login/callback/",
)


class SensitiveAuthPathMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith(
            "/accounts/google/"
        ) and not settings.CUSTOMER_GOOGLE_LOGIN_ENABLED:
            response = HttpResponseNotFound()
        else:
            response = self.get_response(request)
        if request.path.startswith(SENSITIVE_AUTH_PATH_PREFIXES):
            response["Cache-Control"] = "no-store"
            response["Pragma"] = "no-cache"
            # Share only the scheme and host. Django can validate the same-origin
            # password POST without exposing the secret-bearing path to subresources.
            response["Referrer-Policy"] = "strict-origin"
        return response
