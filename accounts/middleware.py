SENSITIVE_AUTH_PATH_PREFIXES = (
    "/accounts/password/reset/key/",
    "/accounts/invitations/",
    "/accounts/registrations/verify/",
)


class SensitiveAuthPathMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.path.startswith(SENSITIVE_AUTH_PATH_PREFIXES):
            response["Cache-Control"] = "no-store"
            response["Pragma"] = "no-cache"
            # Share only the scheme and host. Django can validate the same-origin
            # password POST without exposing the secret-bearing path to subresources.
            response["Referrer-Policy"] = "strict-origin"
        return response
