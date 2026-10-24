"""Storage shape is not an enrolment bypass; fixtures live only in disposable DBs."""
import uuid
from datetime import date
from decimal import Decimal
from io import StringIO

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase, override_settings

from schemes.agreement_contracts import resolve_independent_agreement_terms
from schemes.models import SchemeAccount, SchemePlan, SchemePlanRevision, MetalGrade
from schemes.plan_configuration import create_configuration_version, configuration_evidence, validate_agreement_configuration
from schemes.plan_policies import require_current_payment_workflow
from schemes.instalments import expected_account_windows
from schemes.instalment_selectors import get_monthly_eligibility
from schemes.selectors import get_customer_payment_availability
from schemes.tests.test_audit_exceptions import make_owner, make_customer, make_plan
from schemes.tests.test_independent_policy_fields import independent_values, required_values


def preparation(owner, values):
    config = create_configuration_version(values=values, actor=owner, reason="Storage fixture")
    plan = SchemePlan(name="Future contract", code=uuid.uuid4().hex[:20], configuration=config,
        active=False, amount_rule="VARIABLE", frequency_rule="FLEXIBLE", minimum_contribution=Decimal("100"))
    SchemePlan.objects.bulk_create([plan])
    # TransactionTestCase flushes migration seed rows between cases.
    grade = (MetalGrade.objects.get_or_create(code="GOLD_22K_916", defaults=dict(
        metal="GOLD", display_name="22K gold (916)", fineness=Decimal("0.916")))[0]
        if config.accumulation == "EXACT_METAL" else None)
    revision = SchemePlanRevision.objects.create(plan=plan, number=1, actor=owner, actor_label="Owner",
        reason="Synthetic preparation", terms=dict(configuration=configuration_evidence(config),
            name=plan.name, code=plan.code, metal_grades=[grade.code] if grade else []))
    return config, plan, revision, grade


def stored_future(owner, customer, values):
    config, plan, revision, grade = preparation(owner, values)
    terms = resolve_independent_agreement_terms(configuration_id=config.pk, start_date=date(2026, 1, 30),
        selected_amount=Decimal("500"), metal_grade_id=grade.pk if grade else None)
    account = SchemeAccount(customer=customer, scheme_number=uuid.uuid4().hex[:20], plan=plan,
        plan_revision=revision, plan_name_snapshot=plan.name, plan_code_snapshot=plan.code,
        **terms.account_snapshots())
    SchemeAccount.objects.bulk_create([account])
    return account


class IndependentAgreementStorageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner, cls.customer = make_owner(), make_customer()

    def test_matrix_roundtrip_preserves_independent_duration_count_and_no_date(self):
        for accumulation in ("EXACT_METAL", "INR_PURCHASE_CREDIT"):
            cases = [independent_values(accumulation=accumulation),
                independent_values(accumulation=accumulation, eligibility_policy="CALENDAR", duration_months=1,
                    frequency_rule="ONCE_PER_PERIOD", period_basis="ANNIVERSARY"),
                required_values(accumulation=accumulation),
                required_values(accumulation=accumulation, eligibility_policy="CALENDAR_AND_COUNT", duration_months=18),
                required_values(accumulation=accumulation, eligibility_policy="CALENDAR", duration_months=12,
                    missed_payment_policy="LOSE_UNEARNED_BENEFIT", max_extension_months=None,
                    benefit_policy="VA_DISCOUNT", benefit_percentage=Decimal("5"), benefit_cap_inr=Decimal("500"),
                    benefit_qualification="REQUIRED_SCHEDULE", benefit_on_miss="DISQUALIFY_UNEARNED",
                    eligible_charge_definition="Published making charges excluding taxes")]
            for values in cases:
                with self.subTest(accumulation=accumulation, eligibility=values["eligibility_policy"]):
                    account = stored_future(self.owner, self.customer, values)
                    account.refresh_from_db()
                    validate_agreement_configuration(account)
                    account.validate_constraints()
                    self.assertEqual(account.agreed_months, values["duration_months"])
                    self.assertEqual(account.required_count_snapshot, values["required_count"])
                    self.assertEqual(account.eligible_from is None, values["duration_months"] is None)
                    with override_settings(CONFIGURED_PLANS_ENABLED=True):
                        for action in (account.full_clean, account.save,
                                       lambda: require_current_payment_workflow(account),
                                       lambda: expected_account_windows(account),
                                       lambda: get_monthly_eligibility(account),
                                       lambda: account.effective_status):
                            with self.assertRaises(ValidationError):
                                action()
                        self.assertFalse(get_customer_payment_availability(account).allowed)
        output = StringIO()
        call_command("check_plan_agreements", stdout=output)
        self.assertIn("revision_term_mismatches=0", output.getvalue())

    def test_database_rejects_invented_dates_missing_counts_and_unknown_versions(self):
        account = stored_future(self.owner, self.customer, required_values())
        for change in (dict(required_count_snapshot=None), dict(required_count_snapshot=0),
                dict(agreed_months=12), dict(eligible_from=date(2027, 1, 30)),
                dict(agreement_schema_version=1), dict(agreement_schema_version=3),
                dict(eligibility_policy_snapshot="UNKNOWN"), dict(configuration_snapshot=None),
                dict(frequency_rule_snapshot="ONCE_PER_MONTH")):
            with self.subTest(change=change), self.assertRaises(IntegrityError), transaction.atomic():
                SchemeAccount.objects.filter(pk=account.pk).update(**change)
        for field, value in (("required_count_snapshot", 11), ("eligibility_policy_snapshot", "ANYTIME"),
                             ("agreement_schema_version", 1), ("agreed_months", 12)):
            account.refresh_from_db()
            setattr(account, field, value)
            with self.assertRaisesMessage(ValidationError, "immutable"):
                account.save()

    def test_policy_mismatch_is_detected_even_when_storage_shape_is_valid(self):
        account = stored_future(self.owner, self.customer, required_values())
        SchemeAccount.objects.filter(pk=account.pk).update(required_count_snapshot=11)
        account.refresh_from_db()
        with self.assertRaises(ValidationError):
            validate_agreement_configuration(account)

    def test_legacy_duration_and_frequency_constraints_remain(self):
        account = SchemeAccount.objects.create(customer=self.customer, scheme_number="OLD", plan=make_plan(),
            savings_mode="CASH", start_date=date(2026, 1, 30), agreed_months=12,
            eligible_from=date(2027, 1, 30), amount_rule_snapshot="VARIABLE",
            minimum_amount_snapshot=Decimal("100"), frequency_rule_snapshot="FLEXIBLE")
        for change in (dict(agreed_months=11), dict(agreed_months=None), dict(eligible_from=None),
                dict(required_count_snapshot=12), dict(eligibility_policy_snapshot="DURATION"),
                dict(frequency_rule_snapshot="ONCE_PER_PERIOD")):
            with self.subTest(change=change), self.assertRaises(IntegrityError), transaction.atomic():
                SchemeAccount.objects.filter(pk=account.pk).update(**change)


class IndependentAgreementMigrationTests(TransactionTestCase):
    def test_legacy_rows_survive_roundtrip_without_new_obligations(self):
        account = SchemeAccount.objects.create(customer=make_customer(), scheme_number="OLD", plan=make_plan(),
            savings_mode="CASH", start_date=date(2026, 1, 30), agreed_months=12,
            eligible_from=date(2027, 1, 30), amount_rule_snapshot="VARIABLE",
            minimum_amount_snapshot=Decimal("100"), frequency_rule_snapshot="FLEXIBLE")
        before = SchemeAccount.objects.values().get(pk=account.pk)
        leaves = MigrationExecutor(connection).loader.graph.leaf_nodes()
        self.addCleanup(lambda: MigrationExecutor(connection).migrate(leaves))
        MigrationExecutor(connection).migrate([("schemes", "0039_inr_settlement_corrections")])
        MigrationExecutor(connection).migrate(leaves)
        self.assertEqual(SchemeAccount.objects.values().get(pk=account.pk), before)

    def test_reverse_refuses_to_discard_even_unused_independent_agreement(self):
        account = stored_future(make_owner(), make_customer(), required_values())
        with self.assertRaisesMessage(RuntimeError, "Cannot reverse 0040"):
            MigrationExecutor(connection).migrate([("schemes", "0039_inr_settlement_corrections")])
        account.refresh_from_db()
        self.assertEqual(account.required_count_snapshot, 10)
        self.assertIsNone(account.eligible_from)
        # A forged storage tag must not bypass the retained policy-schema-2 evidence.
        SchemeAccount.objects.filter(pk=account.pk).update(agreement_schema_version=1,
            eligibility_policy_snapshot="", required_count_snapshot=None, agreed_months=12,
            eligible_from=date(2027, 1, 30), frequency_rule_snapshot="FLEXIBLE")
        with self.assertRaisesMessage(RuntimeError, "Cannot reverse 0040"):
            MigrationExecutor(connection).migrate([("schemes", "0039_inr_settlement_corrections")])

    def test_forward_refuses_unversioned_schema_two_accounts(self):
        owner, customer = make_owner(), make_customer()
        config, plan, revision, _ = preparation(owner, independent_values(accumulation="INR_PURCHASE_CREDIT",
            eligibility_policy="CALENDAR", duration_months=12))
        executor = MigrationExecutor(connection)
        leaves = executor.loader.graph.leaf_nodes()
        target = [("schemes", "0039_inr_settlement_corrections")]
        executor.migrate(target)
        historical = executor.loader.project_state(target).apps.get_model("schemes", "SchemeAccount")
        # This deliberately invalid historical fixture exists only in this disposable test DB.
        def cleanup():
            historical.objects.filter(scheme_number="UNVERSIONED").delete()
            MigrationExecutor(connection).migrate(leaves)
        self.addCleanup(cleanup)
        historical.objects.create(customer_id=customer.pk, scheme_number="UNVERSIONED", plan_id=plan.pk,
            plan_revision_id=revision.pk, configuration_snapshot_id=config.pk,
            plan_name_snapshot=plan.name, plan_code_snapshot=plan.code, savings_mode="INR_CREDIT",
            start_date=date(2026, 1, 30), agreed_months=12, eligible_from=date(2027, 1, 30),
            amount_rule_snapshot="VARIABLE", minimum_amount_snapshot=Decimal("100"), frequency_rule_snapshot="FLEXIBLE")
        with self.assertRaisesMessage(RuntimeError, "Cannot apply 0040"):
            MigrationExecutor(connection).migrate(leaves)
        self.assertEqual(historical.objects.filter(scheme_number="UNVERSIONED").count(), 1)
