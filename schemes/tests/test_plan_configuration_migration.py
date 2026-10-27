from datetime import date
from decimal import Decimal

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

from .migration_helpers import applied_migration_apps


def historical_calendar_evidence(configuration):
    """Freeze the 0023 evidence format; historical models cannot use today's schema API."""
    fields = (
        "name", "amount_policy", "minimum_amount", "maximum_amount", "fixed_amount",
        "amount_step", "frequency_rule", "minimum_months", "default_months",
        "allow_contributions_after_eligibility", "accumulation", "instalment_policy",
        "eligibility_policy", "missed_payment_policy", "benefit_policy", "settlement_policy",
    )
    result = {"id": configuration.pk, "family_id": str(configuration.family_id), "version": configuration.version}
    for field in fields:
        value = getattr(configuration, field)
        result[field] = format(value, ".2f") if isinstance(value, Decimal) else value
    return result


class ConfigurationMigrationTests(TransactionTestCase):
    def test_existing_plan_and_agreement_are_not_configured_or_rewritten(self):
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        before_target = [("schemes", "0021_plan_agreement_governance")]
        try:
            executor.migrate(before_target)
            old = applied_migration_apps()
            User = old.get_model("accounts", "CustomUser")
            Customer = old.get_model("schemes", "Customer")
            Plan = old.get_model("schemes", "SchemePlan")
            Grade = old.get_model("schemes", "MetalGrade")
            Account = old.get_model("schemes", "SchemeAccount")
            user = User.objects.create(username="config-upgrade", email="config@example.invalid", role="CUSTOMER")
            customer = Customer.objects.create(user=user, customer_number="CONFIG-UPGRADE", full_name="Synthetic", email=user.email)
            plan = Plan.objects.create(name="Existing offer", code="CONFIG-UPGRADE", minimum_contribution=Decimal("100"), amount_rule="VARIABLE", frequency_rule="FLEXIBLE", active=True, publicly_listed=True)
            grade, _ = Grade.objects.get_or_create(code="GOLD_22K_916", defaults={"metal": "GOLD", "display_name": "22K Gold", "fineness": Decimal("0.916000")})
            account = Account.objects.create(scheme_number="CONFIG-UPGRADE", customer=customer, plan=plan,
                plan_name_snapshot="Older agreed name", plan_code_snapshot="OLDER-CODE", start_date=date(2025, 1, 31),
                agreed_months=18, eligible_from=date(2026, 7, 31), savings_mode="GOLD", metal_grade=grade,
                amount_rule_snapshot="VARIABLE", frequency_rule_snapshot="FLEXIBLE", minimum_amount_snapshot=Decimal("75"))
            before_plan = Plan.objects.filter(pk=plan.pk).values().get()
            before_account = Account.objects.filter(pk=account.pk).values().get()
            target = [("schemes", "0022_plan_configuration_foundation")]
            executor = MigrationExecutor(connection)
            executor.migrate(target)
            new = applied_migration_apps()
            after_plan = new.get_model("schemes", "SchemePlan").objects.filter(pk=plan.pk).values().get()
            self.assertEqual({key: after_plan[key] for key in before_plan}, before_plan)
            self.assertIsNone(after_plan["configuration_id"])
            self.assertEqual(new.get_model("schemes", "SchemeAccount").objects.filter(pk=account.pk).values().get(), before_account)
            self.assertEqual(new.get_model("schemes", "SchemePlanConfiguration").objects.count(), 0)
            # The next additive migration must not reinterpret that legacy preference.
            next_target = [("schemes", "0023_configured_agreement_terms")]
            executor = MigrationExecutor(connection)
            executor.migrate(next_target)
            upgraded = applied_migration_apps()
            after_account = upgraded.get_model("schemes", "SchemeAccount").objects.filter(pk=account.pk).values().get()
            self.assertEqual({key: after_account[key] for key in before_account}, before_account)
            self.assertIsNone(after_account["configuration_snapshot_id"])
            self.assertIsNone(after_account["contribution_step_snapshot"])
            self.assertEqual(upgraded.get_model("schemes", "SchemePlan").objects.filter(pk=plan.pk).values().get(), after_plan)
            # P2a adds nullable schedule policy without inventing obligations or rewriting evidence.
            configuration = upgraded.get_model("schemes", "SchemePlanConfiguration").objects.create(
                name="Existing calendar definition", amount_policy="CUSTOMER_FIXED",
                minimum_amount=Decimal("500"), frequency_rule="FLEXIBLE", created_by_id=user.pk,
                actor_label="Migration fixture", reason="Historical preparation",
            )
            from schemes.plan_configuration import configuration_evidence
            old_evidence = historical_calendar_evidence(configuration)
            config_before = upgraded.get_model("schemes", "SchemePlanConfiguration").objects.filter(pk=configuration.pk).values().get()
            schedule_target = [("schemes", "0024_monthly_completion_schedule")]
            executor = MigrationExecutor(connection)
            executor.migrate(schedule_target)
            scheduled = applied_migration_apps()
            config_after = scheduled.get_model("schemes", "SchemePlanConfiguration").objects.filter(pk=configuration.pk).values().get()
            self.assertEqual({key: config_after[key] for key in config_before}, config_before)
            for field in ("period_basis", "grace_days", "catch_up_policy", "max_extension_months"):
                self.assertIsNone(config_after[field])
            self.assertEqual(historical_calendar_evidence(scheduled.get_model("schemes", "SchemePlanConfiguration").objects.get(pk=configuration.pk)), old_evidence)
            self.assertEqual(scheduled.get_model("schemes", "SchemeAccount").objects.filter(pk=account.pk).values().get(), after_account)
            self.assertEqual(scheduled.get_model("schemes", "SchemeInstalmentPeriod").objects.count(), 0)
            # P2b is additive only: do not infer qualification from historical payments.
            payment = scheduled.get_model("schemes", "Contribution").objects.create(
                scheme_account_id=account.pk, amount=Decimal("500"), contribution_period=date(2026, 1, 1),
                frequency_rule_snapshot="FLEXIBLE", payment_gateway="mock", payment_channel="MOCK", status="PENDING",
            )
            payment_before = scheduled.get_model("schemes", "Contribution").objects.filter(pk=payment.pk).values().get()
            ledger_target = [("schemes", "0025_instalment_payment_ledger")]
            executor = MigrationExecutor(connection)
            executor.migrate(ledger_target)
            ledger = applied_migration_apps()
            self.assertEqual(ledger.get_model("schemes", "Contribution").objects.filter(pk=payment.pk).values().get(), payment_before)
            self.assertEqual(ledger.get_model("schemes", "SchemeAccount").objects.filter(pk=account.pk).values().get(), after_account)
            self.assertEqual(ledger.get_model("schemes", "InstalmentReservation").objects.count(), 0)
            self.assertEqual(ledger.get_model("schemes", "InstalmentPaymentDecision").objects.count(), 0)
            integration_target = [("schemes", "0026_instalment_payment_integration")]
            executor = MigrationExecutor(connection)
            executor.migrate(integration_target)
            integrated = applied_migration_apps()
            self.assertEqual(integrated.get_model("schemes", "Contribution").objects.filter(pk=payment.pk).values().get(), payment_before)
            self.assertEqual(integrated.get_model("schemes", "SchemeAccount").objects.filter(pk=account.pk).values().get(), after_account)
            self.assertEqual(integrated.get_model("schemes", "InstalmentReservation").objects.count(), 0)
            self.assertEqual(integrated.get_model("schemes", "InstalmentPaymentDecision").objects.count(), 0)
            review_target = [("schemes", "0027_instalment_owner_reviews")]
            executor = MigrationExecutor(connection)
            executor.migrate(review_target)
            reviewed = applied_migration_apps()
            self.assertEqual(reviewed.get_model("schemes", "Contribution").objects.filter(pk=payment.pk).values().get(), payment_before)
            self.assertEqual(reviewed.get_model("schemes", "SchemeAccount").objects.filter(pk=account.pk).values().get(), after_account)
            self.assertEqual(reviewed.get_model("schemes", "InstalmentReview").objects.count(), 0)
            outage_target = [("schemes", "0028_instalment_outage_resolutions")]
            executor = MigrationExecutor(connection)
            executor.migrate(outage_target)
            amended = applied_migration_apps()
            self.assertEqual(amended.get_model("schemes", "Contribution").objects.filter(pk=payment.pk).values().get(), payment_before)
            self.assertEqual(amended.get_model("schemes", "SchemeAccount").objects.filter(pk=account.pk).values().get(), after_account)
            self.assertEqual(amended.get_model("schemes", "InstalmentOutageResolution").objects.count(), 0)
            self.assertEqual(amended.get_model("schemes", "SchemeInstalmentPeriod").objects.count(), 0)
            self.assertEqual(historical_calendar_evidence(amended.get_model("schemes", "SchemePlanConfiguration").objects.get(pk=configuration.pk)), old_evidence)
            recovery_target = [("schemes", "0029_instalment_order_recovery")]
            executor = MigrationExecutor(connection)
            executor.migrate(recovery_target)
            recovered = applied_migration_apps()
            self.assertEqual(recovered.get_model("schemes", "Contribution").objects.filter(pk=payment.pk).values().get(), payment_before)
            self.assertEqual(recovered.get_model("schemes", "SchemeAccount").objects.filter(pk=account.pk).values().get(), after_account)
            self.assertEqual(recovered.get_model("schemes", "InstalmentOrderRecovery").objects.count(), 0)
            publication_before_target = [("schemes", "0033_configured_full_settlement")]
            executor = MigrationExecutor(connection)
            executor.migrate(publication_before_target)
            before_apps = applied_migration_apps()
            original_plan = before_apps.get_model("schemes", "SchemePlan").objects.values().get(pk=plan.pk)
            original_account = before_apps.get_model("schemes", "SchemeAccount").objects.values().get(pk=account.pk)
            publication_target = [("schemes", "0034_configured_plan_publication")]
            executor = MigrationExecutor(connection)
            executor.migrate(publication_target)
            published_apps = applied_migration_apps()
            migrated_plan = published_apps.get_model("schemes", "SchemePlan").objects.values().get(pk=plan.pk)
            self.assertIsNone(migrated_plan["publication_revision_id"])
            self.assertEqual({key: migrated_plan[key] for key in original_plan}, original_plan)
            self.assertEqual(published_apps.get_model("schemes", "SchemeAccount").objects.values().get(pk=account.pk), original_account)
            self.assertEqual(published_apps.get_model("schemes", "Contribution").objects.values().get(pk=payment.pk), payment_before)
            MigrationExecutor(connection).migrate(latest)
            from schemes.models import SchemePlanConfiguration
            self.assertEqual(configuration_evidence(SchemePlanConfiguration.objects.get(pk=configuration.pk)), old_evidence)
        finally:
            MigrationExecutor(connection).migrate(latest)
