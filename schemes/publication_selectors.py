"""Read-only publication review using the same policy and denomination authorities."""
from django.conf import settings
from django.core.exceptions import ValidationError

from .catalogue_lifecycle import require_open_catalogue_item
from .plan_policies import require_operational_configuration
from .plan_publication import validate_offer_denomination


def get_publication_blockers(plan):
    blockers = []
    if not settings.CONFIGURED_PLANS_ENABLED:
        blockers.append("The configured-plan release gate is disabled.")
    for check in (
        lambda: require_open_catalogue_item(plan=plan),
        plan.configuration.full_clean,
        lambda: require_operational_configuration(plan.configuration),
        lambda: validate_offer_denomination(plan),
    ):
        try:
            check()
        except ValidationError as error:
            blockers.extend(error.messages)
    return tuple(dict.fromkeys(blockers))
