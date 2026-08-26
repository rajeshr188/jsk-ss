import logging
import re


SENSITIVE_AUTH_PATH_PATTERNS = (
    re.compile(r"/accounts/invitations/[^\s?#]+(?:\?[^\s]*)?"),
    re.compile(r"/accounts/password/reset/key/[^\s?#]+(?:\?[^\s]*)?"),
)


def redact_sensitive_auth_paths(message):
    redacted = message
    for pattern in SENSITIVE_AUTH_PATH_PATTERNS:
        redacted = pattern.sub(
            lambda match: (
                "/accounts/invitations/[REDACTED]/"
                if match.group(0).startswith("/accounts/invitations/")
                else "/accounts/password/reset/key/[REDACTED]/"
            ),
            redacted,
        )
    return redacted


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
