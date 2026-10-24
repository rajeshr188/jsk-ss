from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db.models import F, Q

from schemes.models import SchemeAccount


class Command(BaseCommand):
    help = "Read-only checks for agreement identity and recorded plan revision consistency."

    def handle(self, *args, **options):
        accounts = SchemeAccount.objects.all()
        missing = accounts.filter(Q(plan_name_snapshot="") | Q(plan_code_snapshot="")).count()
        wrong_plan = accounts.filter(plan_revision__isnull=False).exclude(plan_id=F("plan_revision__plan_id")).count()
        mismatch = 0
        fields = {
            "plan_name_snapshot": "name", "plan_code_snapshot": "code",
            "amount_rule_snapshot": "amount_rule", "frequency_rule_snapshot": "frequency_rule",
            "fixed_amount_snapshot": "fixed_contribution_amount", "minimum_amount_snapshot": "minimum_contribution",
            "maximum_amount_snapshot": "maximum_contribution",
            "allow_post_eligibility_contributions_snapshot": "allow_contributions_after_eligibility",
            "cash_bonus_percentage_snapshot": "cash_bonus_percentage",
            "cash_bonus_minimum_months_snapshot": "cash_bonus_minimum_months",
        }
        for account in accounts.filter(plan_revision__isnull=False).select_related("plan_revision", "metal_grade", "configuration_snapshot").iterator():
            terms = account.plan_revision.terms
            if account.configuration_snapshot_id:
                from schemes.plan_configuration import validate_agreement_configuration
                try:
                    validate_agreement_configuration(account)
                except ValidationError:
                    mismatch += 1
                continue
            if (
                not isinstance(terms, dict)
                or any(key not in terms or str(getattr(account, field)) != str(terms[key]) for field, key in fields.items())
                or terms.get("eligibility_basis") != "CALENDAR_MONTHS"
                or (account.metal_grade_id and account.metal_grade.code not in terms.get("metal_grades", []))
            ):
                mismatch += 1
        missing_configuration = accounts.filter(
            Q(configuration_snapshot__isnull=False, plan_revision__isnull=True)
            | Q(configuration_snapshot__isnull=True, contribution_step_snapshot__isnull=False)
            | Q(configuration_snapshot__isnull=True, plan_revision__terms__has_key="configuration")
        ).count()
        errors = missing + wrong_plan + mismatch + missing_configuration
        self.stdout.write(
            f"plan_agreement_check status={'error' if errors else 'ok'} release={settings.APP_RELEASE} "
            f"legacy_agreements={accounts.filter(plan_revision__isnull=True).count()} "
            f"missing_identity={missing} revision_plan_mismatches={wrong_plan} revision_term_mismatches={mismatch} "
            f"configuration_snapshot_errors={missing_configuration}"
        )
        if errors:
            raise CommandError("Agreement metadata needs review; this check has not changed any records.")
