"""Read-only catalogue lifecycle previews; existing agreement terms stay independent."""
import hashlib
import json

from .models import PlanCatalogueClosure
from .plan_configuration import configuration_evidence
from .plan_governance import plan_edit_digest


def catalogue_closure_preview(*, plan=None, configuration=None):
    if (plan is None) == (configuration is None):
        raise ValueError("Choose one catalogue item.")
    target = plan if plan is not None else configuration
    lookup = {"plan_id" if plan is not None else "configuration_id": target.pk}
    record = PlanCatalogueClosure.objects.filter(**lookup).select_related("actor").first()
    if plan is not None:
        counts = {"agreements": plan.scheme_accounts.count(),
            "requests": plan.enrolment_requests.count(),
            "applications": plan.planapplication_set.count()}
        exposed = (plan.active or plan.publicly_listed or plan.publication_revision_id
            or any(counts.values()) or plan.revisions.filter(terms__active=True).exists()
            or plan.revisions.filter(terms__publicly_listed=True).exists())
        action = "RETIRE_PLAN" if exposed else "ARCHIVE_DRAFT"
        evidence = plan_edit_digest(plan)
        blocked = ""
    else:
        counts = {"open_plans": configuration.plans.filter(catalogue_closure__isnull=True).count()}
        action = "ARCHIVE_CONFIGURATION"
        evidence = configuration_evidence(configuration)
        blocked = "Archive or retire the plans using this version first." if counts["open_plans"] else ""
    digest = hashlib.sha256(json.dumps({"evidence": evidence, "counts": counts,
        "closed": record.pk if record else None, "action": action}, sort_keys=True).encode()).hexdigest()
    return {"record": record, "action": action, "counts": counts, "blocked": blocked,
        "expected_digest": digest,
        "label": {"ARCHIVE_CONFIGURATION": "Archive configuration", "ARCHIVE_DRAFT": "Archive draft",
            "RETIRE_PLAN": "Retire plan"}[action]}
