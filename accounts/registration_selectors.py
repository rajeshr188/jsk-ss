"""Read-only expiry review for standalone, unverified access applications."""
import hashlib
import json

from django.core.serializers.json import DjangoJSONEncoder
from django.utils import timezone

from .models import CustomerRegistration, PlanApplication


def registration_expiry_review(application, *, at=None):
    at = at or timezone.now()
    linked_plan = PlanApplication.objects.filter(registration_id=application.pk).exists()
    if linked_plan:
        blocker = "This is a coordinated plan application. Use its existing review workflow; standalone expiry is unavailable."
    elif application.status != CustomerRegistration.Status.PENDING_EMAIL_VERIFICATION:
        blocker = "Only an unverified application awaiting email verification can be expired."
    elif application.email_verified_at or application.approved_user_id or application.mobile_verified_at:
        blocker = "This application has verification or approval evidence; review that evidence instead."
    elif application.email_verification_expires_at > at:
        blocker = "Its verification link has not expired. Allow the applicant to verify before closing it."
    else:
        blocker = ""
    # The hidden confirmation is a digest, never a raw verification secret/contact field.
    evidence = {field: getattr(application, field) for field in (
        "pk", "status", "full_name", "email", "mobile_number", "address",
        "email_verification_expires_at", "email_token_digest", "email_verified_at",
        "mobile_verified_at", "approved_user_id", "reviewed_at", "reviewed_by_id", "review_reason",
    )}
    evidence["linked_plan"] = linked_plan
    digest = hashlib.sha256(json.dumps(evidence, cls=DjangoJSONEncoder, sort_keys=True).encode()).hexdigest()
    return {"available": not blocker, "blocker": blocker, "expected_digest": digest}
