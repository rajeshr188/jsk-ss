from decimal import Decimal
from io import StringIO
from itertools import product

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse

from schemes.models import Contribution, MetalAllocation, SchemeAccount, SchemePlan, SchemePlanConfiguration
from schemes.forms import PlanConfigurationForm
from schemes.plan_configuration import (
    configuration_evidence, configuration_plan_values, create_configuration_version,
    create_configured_plan_draft, preview_configuration_agreement,
)
from schemes.plan_policies import policy_from_configuration, require_operational_configuration
from schemes.tests.test_audit_exceptions import make_owner, make_customer


def independent_values(**changes):
    return {
        "name": "Independent preparation", "policy_schema_version": 2,
        "amount_policy": "VARIABLE", "minimum_amount": Decimal("100.00"),
        "maximum_amount": Decimal("10000.00"), "fixed_amount": None,
        "frequency_rule": "FLEXIBLE", "minimum_months": None, "default_months": None,
        "duration_months": None, "required_count": None, "eligibility_policy": "ANYTIME",
        "grace_days": 0, "catch_up_policy": "NONE", **changes,
    }


def required_values(**changes):
    return independent_values(
        **{"amount_policy": "CUSTOMER_FIXED", "instalment_policy": "MONTHLY_COMPLETION",
           "frequency_rule": "ONCE_PER_PERIOD", "period_basis": "CALENDAR_MONTH",
           "required_count": 10, "eligibility_policy": "COUNT",
           "missed_payment_policy": "EXTEND_THEN_REVIEW", "max_extension_months": 3, **changes})


class IndependentPolicyTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = make_owner()
        cls.customer = make_customer()

    def create(self, values=None, previous_id=None):
        return create_configuration_version(values=values or independent_values(), actor=self.owner,
                                             reason="Prepare independent contract", previous_id=previous_id)

    def test_all_approved_families_roundtrip_without_financial_writes(self):
        before = [model.objects.count() for model in (Contribution, MetalAllocation, SchemeAccount, SchemePlan)]
        for accumulation, basis in product(("EXACT_METAL", "INR_PURCHASE_CREDIT"), ("CALENDAR_MONTH", "ANNIVERSARY")):
            values = [independent_values(accumulation=accumulation),
                      independent_values(accumulation=accumulation, eligibility_policy="CALENDAR", duration_months=12,
                                         frequency_rule="ONCE_PER_PERIOD", period_basis=basis),
                      required_values(accumulation=accumulation, period_basis=basis),
                      required_values(accumulation=accumulation, period_basis=basis,
                                      eligibility_policy="CALENDAR_AND_COUNT", duration_months=18),
                      required_values(accumulation=accumulation, period_basis=basis, eligibility_policy="CALENDAR",
                                      duration_months=12, missed_payment_policy="LOSE_UNEARNED_BENEFIT", max_extension_months=None,
                                      benefit_policy="VA_DISCOUNT", benefit_percentage=Decimal("5.00"), benefit_cap_inr=Decimal("500"),
                                      benefit_qualification="REQUIRED_SCHEDULE", benefit_on_miss="DISQUALIFY_UNEARNED",
                                      eligible_charge_definition="Documented making charges")]
            for value in values:
                with self.subTest(value=value):
                    config = self.create(value)
                    before_policy = policy_from_configuration(config)
                    config.refresh_from_db()
                    self.assertEqual(policy_from_configuration(config), before_policy)
                    self.assertEqual(configuration_evidence(config)["policy_schema_version"], 2)
        self.assertEqual(before, [model.objects.count() for model in (Contribution, MetalAllocation, SchemeAccount, SchemePlan)])

    def test_owner_only_and_explicit_input(self):
        with self.assertRaises(ValidationError):
            create_configuration_version(values=independent_values(), actor=self.customer.user, reason="Not owner")
        for change in ({"policy_schema_version": 3}, {"policy_schema_version": True},
                       {"duration_months": 12}, {"required_count": True}, {"minimum_months": 12},
                       {"benefit_percentage": 5.0}, {"untrusted_expression": "1+1"}):
            with self.subTest(change=change), self.assertRaises(ValidationError):
                self.create(independent_values(**change))
        self.assertEqual(SchemePlanConfiguration.objects.count(), 0)

    def test_legacy_editor_requires_duration_and_rejects_hidden_schema_fields(self):
        values = dict(name="Legacy", amount_policy="VARIABLE", minimum_amount="100",
                      frequency_rule="FLEXIBLE", minimum_months=12, default_months=12, reason="Prepare")
        self.assertTrue(PlanConfigurationForm(data=values).is_valid())
        for field in ("minimum_months", "default_months"):
            form = PlanConfigurationForm(data={**values, field: ""})
            self.assertFalse(form.is_valid())
            self.assertIn(field, form.errors)
        for field, value in (("policy_schema_version", 2), ("duration_months", 12), ("benefit_cap_inr", "500")):
            form = PlanConfigurationForm(data={**values, field: value})
            self.assertFalse(form.is_valid())
            self.assertIn("Advanced policy dimensions", str(form.non_field_errors()))

    def test_schema_versions_append_without_rewriting_evidence(self):
        old = self.create(dict(name="Old", amount_policy="VARIABLE", minimum_amount=Decimal("100"),
                               frequency_rule="FLEXIBLE"))
        original = configuration_evidence(old)
        new = self.create(required_values(), previous_id=old.pk)
        old.refresh_from_db()
        self.assertEqual(configuration_evidence(old), original)
        self.assertNotIn("policy_schema_version", original)
        self.assertEqual(new.family_id, old.family_id)
        self.assertEqual(new.version, 2)
        self.assertIsNone(new.duration_months)
        self.assertEqual(new.required_count, 10)
        with self.assertRaisesMessage(ValidationError, "downgrade"):
            self.create(dict(name="Old", amount_policy="VARIABLE", minimum_amount=Decimal("100"),
                             frequency_rule="FLEXIBLE"), previous_id=new.pk)
        with self.assertRaises(ValidationError):
            new.save()
        with self.assertRaises(ValidationError):
            new.delete()

    def test_schema_one_cannot_hide_independent_terms(self):
        old = self.create(dict(name="Old", amount_policy="VARIABLE", minimum_amount=Decimal("100"), frequency_rule="FLEXIBLE"))
        for changes in ({"duration_months": 12}, {"required_count": 12}, {"benefit_cap_inr": Decimal("100")},
                        {"minimum_months": None}, {"default_months": None}):
            with self.subTest(changes=changes), self.assertRaises(IntegrityError), transaction.atomic():
                SchemePlanConfiguration.objects.filter(pk=old.pk).update(**changes)

    def test_database_rejects_incompatible_or_null_bypasses(self):
        optional = self.create()
        required = self.create(required_values())
        for config, changes in (
            (optional, {"policy_schema_version": 0}), (optional, {"required_count": 1}),
            (optional, {"eligibility_policy": "CALENDAR"}), (optional, {"minimum_months": 12}),
            (optional, {"period_basis": "ANNIVERSARY"}), (optional, {"grace_days": None}),
            (optional, {"benefit_policy": "VA_DISCOUNT"}), (optional, {"settlement_policy": "PARTIAL"}),
            (required, {"required_count": None}), (required, {"amount_policy": "VARIABLE"}),
            (required, {"max_extension_months": None}), (required, {"period_basis": None}),
            (required, {"eligibility_policy": "ANYTIME"}), (required, {"allow_contributions_after_eligibility": True}),
        ):
            with self.subTest(changes=changes), self.assertRaises(IntegrityError), transaction.atomic():
                SchemePlanConfiguration.objects.filter(pk=config.pk).update(**changes)

    def test_benefit_storage_and_database_guardrails(self):
        config = self.create(required_values(
            accumulation="INR_PURCHASE_CREDIT", benefit_policy="INR_PURCHASE_BONUS",
            benefit_percentage=Decimal("5.25"), benefit_cap_inr=Decimal("500.00"),
            benefit_qualification="REQUIRED_SCHEDULE", benefit_on_miss="PRESERVE_ON_COMPLETION"))
        config.refresh_from_db()
        self.assertEqual(configuration_evidence(config)["benefit_percentage"], "5.25")
        for changes in ({"benefit_percentage": None}, {"benefit_percentage": Decimal("101")},
                        {"benefit_cap_inr": None}, {"benefit_cap_inr": 0}, {"accumulation": "EXACT_METAL"},
                        {"benefit_qualification": "NONE"}, {"benefit_on_miss": "NONE"}):
            with self.subTest(changes=changes), self.assertRaises(IntegrityError), transaction.atomic():
                SchemePlanConfiguration.objects.filter(pk=config.pk).update(**changes)
        # SQL bypass: PostgreSQL numeric NaN must not become a persisted money cap.
        with self.assertRaises(IntegrityError), transaction.atomic(), connection.cursor() as cursor:
            cursor.execute("UPDATE schemes_schemeplanconfiguration SET benefit_cap_inr = 'NaN'::numeric WHERE id = %s", [config.pk])

    def test_future_schema_cannot_enter_existing_runtime_even_when_release_enabled(self):
        # Even a schema-2 policy matching an existing family is not runtime-compatible.
        config = self.create(independent_values(eligibility_policy="CALENDAR", duration_months=12))
        for enabled in (False, True):
            with override_settings(CONFIGURED_PLANS_ENABLED=enabled):
                for action in (
                    lambda: require_operational_configuration(config),
                    lambda: configuration_plan_values(config),
                ):
                    with self.assertRaisesMessage(ValidationError, "preparation-only"):
                        action()
                with self.assertRaisesMessage(ValidationError, "independent-policy preview"):
                    preview_configuration_agreement(configuration=config, amount=Decimal("100"), months=12, metal_grade=None)
        self.assertEqual(SchemePlan.objects.count(), 0)

    def test_owner_read_only_details_do_not_misrepresent_future_terms(self):
        config = self.create(independent_values(accumulation="INR_PURCHASE_CREDIT"))
        self.client.force_login(self.owner)
        url = reverse("schemes:plan_configuration_detail", args=[config.pk])
        response = self.client.get(url)
        self.assertContains(response, "INR jewellery purchase credit")
        self.assertContains(response, "No minimum-duration condition")
        self.assertContains(response, "Use in a draft plan")
        self.assertNotContains(response, "Not INR purchase credit")
        listing = self.client.get(reverse("schemes:plan_configuration_list"))
        self.assertContains(listing, "Preparation only")
        self.assertNotContains(listing, "minimum None")
        editor = self.client.post(reverse("schemes:plan_configuration_new_version", args=[config.pk]), {})
        self.assertEqual(editor.status_code, 200)
        self.assertTrue(editor.context["form"].errors)
        draft = self.client.post(reverse("schemes:configured_plan_create", args=[config.pk]), {})
        self.assertEqual(draft.status_code, 200)
        self.assertTrue(draft.context["form"].errors)
        self.assertEqual(SchemePlanConfiguration.objects.count(), 1)
        self.client.force_login(self.customer.user)
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_integrity_check_accepts_valid_preparation_records(self):
        self.create()
        output = StringIO()
        call_command("check_plan_configurations", stdout=output)
        self.assertIn("definition_errors=0", output.getvalue())


class IndependentPolicyMigrationTests(TransactionTestCase):
    def test_0036_preserves_historical_fields_and_evidence(self):
        owner = make_owner()
        old_config = create_configuration_version(values=dict(name="Preserved", amount_policy="VARIABLE",
            minimum_amount=Decimal("100"), frequency_rule="FLEXIBLE"), actor=owner, reason="History")
        before_evidence = configuration_evidence(old_config)
        executor = MigrationExecutor(connection)
        leaves = executor.loader.graph.leaf_nodes()
        self.addCleanup(lambda: MigrationExecutor(connection).migrate(leaves))
        target = [("schemes", "0035_calendar_month_instalments")]
        executor.migrate(target)
        historical = executor.loader.project_state(target).apps.get_model("schemes", "SchemePlanConfiguration")
        before_row = historical.objects.get(pk=old_config.pk)
        before_values = {field.name: getattr(before_row, field.attname) for field in historical._meta.fields}
        MigrationExecutor(connection).migrate(leaves)
        old_config.refresh_from_db()
        self.assertEqual(old_config.policy_schema_version, 1)
        self.assertEqual(configuration_evidence(old_config), before_evidence)
        self.assertEqual({field.name: getattr(old_config, field.attname) for field in historical._meta.fields}, before_values)

    def test_reverse_migration_refuses_to_discard_schema_two_contracts(self):
        leaves = MigrationExecutor(connection).loader.graph.leaf_nodes()
        # A later additive migration may reverse before 0036 refuses; always restore it.
        self.addCleanup(lambda: MigrationExecutor(connection).migrate(leaves))
        owner = make_owner()
        config = create_configuration_version(values=independent_values(), actor=owner, reason="Keep evidence")
        before = configuration_evidence(config)
        with self.assertRaisesMessage(RuntimeError, "Cannot reverse 0036"):
            MigrationExecutor(connection).migrate([("schemes", "0035_calendar_month_instalments")])
        config.refresh_from_db()
        self.assertEqual(configuration_evidence(config), before)
