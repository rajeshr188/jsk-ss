import logging
import re


SENSITIVE_AUTH_PATH_PATTERNS = (
    re.compile(r"/accounts/applications/[^\s?#]+(?:\?[^\s]*)?"),
    re.compile(r"/accounts/invitations/[^\s?#]+(?:\?[^\s]*)?"),
    re.compile(r"/accounts/registrations/verify/[^\s?#]+(?:\?[^\s]*)?"),
    re.compile(r"/accounts/deletion/verify/[^\s?#]+(?:\?[^\s]*)?"),
    re.compile(r"/accounts/password/reset/key/[^\s?#]+(?:\?[^\s]*)?"),
    re.compile(r"/accounts/google/login/callback/(?:\?[^\s]*)?"),
)


def redact_sensitive_auth_paths(message):
    redacted = message
    for pattern in SENSITIVE_AUTH_PATH_PATTERNS:
        redacted = pattern.sub(
            lambda match: _redacted_auth_path(match.group(0)),
            redacted,
        )
    # Search terms and return destinations can contain private customer identifiers.
    return re.sub(r'(/(?:scheme|accounts)/[^\s?"<>]*)(?:\?[^\s"<>]*)',
                  lambda match: match.group(1) + "?[REDACTED]", redacted)


def _redacted_auth_path(path):
    if path.startswith("/accounts/applications/"):
        return "/accounts/applications/[REDACTED]/"
    if path.startswith("/accounts/invitations/"):
        return "/accounts/invitations/[REDACTED]/"
    if path.startswith("/accounts/registrations/verify/"):
        return "/accounts/registrations/verify/[REDACTED]/"
    if path.startswith("/accounts/deletion/verify/"):
        return "/accounts/deletion/verify/[REDACTED]/"
    if path.startswith("/accounts/google/login/callback/"):
        return "/accounts/google/login/callback/[REDACTED]/"
    return "/accounts/password/reset/key/[REDACTED]/"


class SensitiveAuthPathFilter(logging.Filter):
    def filter(self, record):
        try:
            message = record.getMessage()
        except Exception:
            return True

        redacted = redact_sensitive_auth_paths(message)
        if redacted != message:
            record.msg = redacted
            record.args = ()
        return True
