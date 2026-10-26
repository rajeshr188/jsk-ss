from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from schemes.models import SchemeAccount, SchemePlan, SchemePlanConfiguration
from schemes.plan_configuration import configuration_evidence, validate_agreement_configuration
from schemes.plan_governance import plan_terms


class Command(BaseCommand):
    help = "Read-only checks of configurations, publication evidence and frozen agreements."

    def handle(self, *args, **options):
        definitions = 0
        for configuration in SchemePlanConfiguration.objects.all().iterator():
            try:
                configuration.full_clean()
            except ValidationError:
                definitions += 1
        plans = SchemePlan.objects.filter(configuration__isnull=False).select_related("configuration")
        mismatches = 0
        for plan in plans.iterator():
            try:
                plan.full_clean()
            except ValidationError:
                mismatches += 1
                continue
            revision = plan.revisions.first()
            if not revision or not isinstance(revision.terms, dict) or revision.terms.get("configuration") != configuration_evidence(plan.configuration):
                mismatches += 1
            elif plan.configuration.policy_schema_version == 2:
                inr = plan.configuration.accumulation == "INR_PURCHASE_CREDIT"
                if (revision.terms != plan_terms(plan)
                        or plan.metal_offerings.filter(active=True).exists() == inr):
                    mismatches += 1
        activated = plans.filter(Q(active=True) | Q(publicly_listed=True)).count()
        accounts = SchemeAccount.objects.filter(Q(plan__configuration__isnull=False) | Q(configuration_snapshot__isnull=False))
        agreement_errors = 0
        for account in accounts.select_related("plan_revision", "configuration_snapshot").iterator():
            try:
                if not account.configuration_snapshot_id:
                    raise ValidationError("Missing frozen configuration.")
                validate_agreement_configuration(account)
                if (account.plan_revision.terms.get("active") is not True
                        or account.plan_revision.terms.get("publicly_listed") is not True):
                    raise ValidationError("The agreement was not enrolled against a published offer.")
            except ValidationError:
                agreement_errors += 1
        enrolled = accounts.count()
        errors = definitions + mismatches + agreement_errors
        self.stdout.write(
            f"plan_configuration_check status={'error' if errors else 'ok'} release={settings.APP_RELEASE} "
            f"versions={SchemePlanConfiguration.objects.count()} configured_plans={plans.count()} "
            f"draft_plans={plans.filter(active=False, publicly_listed=False).count()} "
            f"definition_errors={definitions} plan_mismatches={mismatches} "
            f"activated_configured_plans={activated} configured_agreements={enrolled} "
            f"agreement_errors={agreement_errors} release_enabled={str(settings.CONFIGURED_PLANS_ENABLED).lower()}"
        )
        if errors:
            raise CommandError("Configuration boundaries need review; no records were changed.")
