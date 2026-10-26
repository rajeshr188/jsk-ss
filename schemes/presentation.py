"""Read-only family descriptions from frozen policies, never operational permission."""
from dataclasses import dataclass

from django.core.exceptions import ValidationError

from .agreement_contracts import validate_independent_account_terms
from .agreement_eligibility import IndependentEligibility, get_independent_eligibility
from .enrolment_contracts import policy_description
from .models import SchemeAccount


@dataclass(frozen=True)
class AgreementPresentation:
    account: SchemeAccount
    terms: tuple = ()
    progress: IndependentEligibility | None = None
    needs_review: bool = False


def independent_agreement_presentation(account):
    """Reload pinned evidence; do not substitute today's offer or manufacture dates."""
    account = SchemeAccount.objects.select_related(
        "configuration_snapshot", "plan_revision", "metal_grade", "customer"
    ).get(pk=account.pk)
    try:
        validate_independent_account_terms(account)
        terms = policy_description(account.configuration_snapshot)
    except ValidationError:
        return AgreementPresentation(account=account, needs_review=True)
    return AgreementPresentation(account=account, terms=terms,
        progress=get_independent_eligibility(account))
