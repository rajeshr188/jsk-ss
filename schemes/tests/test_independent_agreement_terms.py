"""Contract resolution is read-only and never overrides publication/payment gates."""
from dataclasses import FrozenInstanceError
from datetime import date, datetime
from decimal import Decimal
from io import StringIO
from itertools import product

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from schemes.agreement_contracts import resolve_independent_agreement_terms, validate_independent_account_terms
from schemes.inr_selectors import validate_inr_contract
from schemes.models import (Contribution, InrPrincipalReceipt, MetalAllocation, MetalGrade,
    SchemeAccount, SchemePlan, SchemePlanConfiguration, SchemePlanRevision)
from schemes.plan_configuration import create_configuration_version, validate_agreement_configuration
from schemes.plan_policies import require_operational_configuration, require_current_payment_workflow
from schemes.tests.test_audit_exceptions import make_owner, make_customer
from schemes.tests.test_independent_policy_fields import independent_values, required_values
from schemes.tests.test_inr_principal import future_contract, cash_source, record


class IndependentAgreementTermsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = make_owner()
        cls.customer = make_customer()
        cls.grade = MetalGrade.objects.get(code="GOLD_22K_916")

    def configuration(self, **changes):
        return create_configuration_version(values=independent_values(**changes),
            actor=self.owner, reason="Prepare independent agreement terms")

    def resolve(self, config, **changes):
        return resolve_independent_agreement_terms(**{
            "configuration_id": config.pk, "start_date": date(2026, 1, 30), "selected_amount": Decimal("500"),
            "metal_grade_id": self.grade.pk if config.accumulation == "EXACT_METAL" else None,
            **changes})

    def test_optional_matrix_keeps_denomination_amount_and_period_independent(self):
        for accumulation, amount, basis in product(("EXACT_METAL", "INR_PURCHASE_CREDIT"),
                ("PLAN_FIXED", "CUSTOMER_FIXED", "VARIABLE"), (None, "CALENDAR_MONTH", "ANNIVERSARY")):
            with self.subTest(accumulation=accumulation, amount=amount, basis=basis):
                config = self.configuration(accumulation=accumulation, amount_policy=amount,
                    fixed_amount=Decimal("500") if amount == "PLAN_FIXED" else None,
                    minimum_amount=Decimal("500") if amount == "PLAN_FIXED" else Decimal("100"),
                    maximum_amount=Decimal("500") if amount == "PLAN_FIXED" else Decimal("10000"),
                    frequency_rule="ONCE_PER_PERIOD" if basis else "FLEXIBLE", period_basis=basis,
                    eligibility_policy="CALENDAR", duration_months=1)
                terms = self.resolve(config)
                self.assertEqual(terms.savings_mode, "GOLD" if accumulation == "EXACT_METAL" else "INR_CREDIT")
                self.assertEqual(terms.duration_not_before, date(2026, 2, 28))
                self.assertEqual(terms.policy.period_basis, basis)
                self.assertIsNone(terms.policy.required_count)
                self.assertEqual(terms.fixed_amount, None if amount == "VARIABLE" else Decimal("500"))
                self.assertEqual(terms.minimum_amount, Decimal("100") if amount == "VARIABLE" else Decimal("500"))
                self.assertEqual(terms.maximum_amount, Decimal("10000") if amount == "VARIABLE" else Decimal("500"))
        self.assertEqual(SchemeAccount.objects.count(), 0)
        self.assertEqual(Contribution.objects.count(), 0)
        self.assertEqual(MetalAllocation.objects.count(), 0)

    def test_count_and_duration_are_not_collapsed_into_agreed_months(self):
        for basis, eligibility in product(("CALENDAR_MONTH", "ANNIVERSARY"), ("COUNT", "CALENDAR_AND_COUNT")):
            config = create_configuration_version(values=required_values(period_basis=basis,
                eligibility_policy=eligibility, duration_months=12 if eligibility == "CALENDAR_AND_COUNT" else None),
                actor=self.owner, reason="Independent count")
            terms = self.resolve(config)
            self.assertEqual(terms.policy.required_count, 10)
            self.assertEqual(terms.policy.duration_months, 12 if eligibility == "CALENDAR_AND_COUNT" else None)
            self.assertEqual(terms.duration_not_before, date(2027, 1, 30) if eligibility == "CALENDAR_AND_COUNT" else None)
        anytime = self.resolve(self.configuration())
        self.assertIsNone(anytime.duration_not_before)
        self.assertIsNone(anytime.policy.required_count)

    def test_benefit_terms_are_retained_but_not_awarded_or_added_to_principal(self):
        config = self.configuration(accumulation="INR_PURCHASE_CREDIT", eligibility_policy="CALENDAR",
            duration_months=12, benefit_policy="INR_PURCHASE_BONUS", benefit_percentage=Decimal("5"),
            benefit_cap_inr=Decimal("1000"), benefit_qualification="NORMAL_ELIGIBILITY")
        terms = self.resolve(config)
        self.assertEqual(terms.policy.benefit_percentage, Decimal("5"))
        self.assertEqual(terms.policy.benefit_cap_inr, Decimal("1000"))
        self.assertIsNone(terms.fixed_amount)
        self.assertEqual(InrPrincipalReceipt.objects.count(), 0)

    def test_customer_fixed_consent_and_amount_increment_are_not_preferences(self):
        config = self.configuration(amount_policy="CUSTOMER_FIXED", amount_step=Decimal("100"))
        for value in (None, True, 500.0, Decimal("550"), Decimal("99"), Decimal("10001"), Decimal("NaN")):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                self.resolve(config, selected_amount=value)
        fixed = self.resolve(config)
        self.assertEqual(fixed.amount_snapshots()["fixed_amount_snapshot"], Decimal("500"))
        self.assertIsNone(fixed.contribution_step)
        variable = self.resolve(self.configuration(amount_step=Decimal("100")))
        self.assertEqual(variable.contribution_step, Decimal("100"))
        self.assertIsNone(variable.fixed_amount)
        plan_fixed = self.configuration(amount_policy="PLAN_FIXED", fixed_amount=Decimal("500"),
            minimum_amount=Decimal("500"), maximum_amount=Decimal("500"))
        self.assertEqual(self.resolve(plan_fixed, selected_amount=None).fixed_amount, Decimal("500"))
        with self.assertRaises(ValidationError):
            self.resolve(plan_fixed, selected_amount=Decimal("600"))

    def test_grade_schema_date_and_calendar_overflow_fail_closed(self):
        inr = self.configuration(accumulation="INR_PURCHASE_CREDIT")
        metal = self.configuration(eligibility_policy="CALENDAR", duration_months=12)
        for config, changes in ((inr, dict(metal_grade_id=self.grade.pk)),
                (metal, dict(metal_grade_id=None)), (metal, dict(metal_grade_id=999999)),
                (metal, dict(start_date="2026-01-30")), (metal, dict(start_date=datetime(2026, 1, 30))),
                (metal, dict(start_date=date(9999, 1, 1)))):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                self.resolve(config, **changes)
        legacy = create_configuration_version(values=dict(name="Old", amount_policy="VARIABLE",
            minimum_amount=Decimal("100"), frequency_rule="FLEXIBLE"), actor=self.owner, reason="Old format")
        with self.assertRaises(ValidationError):
            self.resolve(legacy)

    def test_resolved_terms_are_immutable_and_do_not_unlock_runtime(self):
        config = self.configuration(eligibility_policy="CALENDAR", duration_months=12)
        before = SchemePlanConfiguration.objects.values().get(pk=config.pk)
        for enabled in (False, True):
            with override_settings(CONFIGURED_PLANS_ENABLED=enabled):
                terms = self.resolve(config)
                with self.assertRaises(FrozenInstanceError):
                    terms.fixed_amount = Decimal("5")
                with self.assertRaises(FrozenInstanceError):
                    terms.policy.duration_months = 1
                with self.assertRaisesMessage(ValidationError, "preparation-only"):
                    require_operational_configuration(config)
        self.assertEqual(SchemePlanConfiguration.objects.values().get(pk=config.pk), before)
        self.assertEqual(SchemeAccount.objects.count(), 0)


class IndependentAccountIntegrityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = make_owner()
        cls.customer = make_customer()
        cls.account = future_contract(cls.owner, cls.customer)

    def test_frozen_terms_are_readable_but_not_enrolment_or_payment_permission(self):
        validate_inr_contract(self.account)
        validate_agreement_configuration(self.account)
        output = StringIO()
        call_command("check_plan_agreements", stdout=output)
        self.assertIn("revision_term_mismatches=0", output.getvalue())
        for enabled in (False, True):
            with override_settings(CONFIGURED_PLANS_ENABLED=enabled):
                for action in (self.account.full_clean, self.account.save,
                               lambda: require_current_payment_workflow(self.account)):
                    with self.assertRaises(ValidationError):
                        action()

    def test_changed_current_plan_and_cached_policy_cannot_rewrite_contract(self):
        successor = create_configuration_version(values=independent_values(accumulation="INR_PURCHASE_CREDIT",
            eligibility_policy="CALENDAR", duration_months=18, minimum_amount=Decimal("9000")),
            previous_id=self.account.configuration_snapshot_id, actor=self.owner, reason="Future offers only")
        SchemePlan.objects.filter(pk=self.account.plan_id).update(name="Renamed current offer",
            configuration=successor, minimum_contribution=Decimal("9000"))
        self.account.configuration_snapshot.minimum_amount = Decimal("9000")
        self.account.plan_revision.terms = {}
        terms = validate_independent_account_terms(self.account)
        self.assertEqual(terms.minimum_amount, Decimal("100"))
        self.assertEqual(terms.duration_not_before, date(2027, 1, 1))

    def test_snapshot_drift_blocks_principal_recording_atomically(self):
        source, receipt = cash_source(self.account, self.owner)
        for changes in (dict(minimum_amount_snapshot=Decimal("200")),
                dict(maximum_amount_snapshot=None), dict(contribution_step_snapshot=Decimal("100")),
                dict(frequency_rule_snapshot="ONCE_PER_PERIOD"),
                dict(allow_post_eligibility_contributions_snapshot=True),
                dict(cash_bonus_minimum_months_snapshot=13), dict(agreed_months=13),
                dict(eligible_from=date(2026, 12, 31)), dict(plan_name_snapshot="Different contract")):
            original = {field: getattr(self.account, field) for field in changes}
            with self.subTest(changes=changes):
                SchemeAccount.objects.filter(pk=self.account.pk).update(**changes)
                with self.assertRaises(ValidationError):
                    record(self.owner, source, cash=receipt)
                self.assertEqual(InrPrincipalReceipt.objects.count(), 0)
                with self.assertRaises(CommandError):
                    call_command("check_plan_agreements", stdout=StringIO())
                SchemeAccount.objects.filter(pk=self.account.pk).update(**original)
        record(self.owner, source, cash=receipt)
        self.assertEqual(InrPrincipalReceipt.objects.count(), 1)

    def test_persisted_revision_drift_and_invented_duration_are_not_accepted(self):
        evidence = self.account.plan_revision.terms
        for changes in (dict(metal_grades=["GOLD_22K_916"]), dict(configuration={}), dict(code="OTHER")):
            with self.subTest(changes=changes):
                SchemePlanRevision.objects.filter(pk=self.account.plan_revision_id).update(terms={**evidence, **changes})
                with self.assertRaises(ValidationError):
                    validate_independent_account_terms(self.account)
        SchemePlanRevision.objects.filter(pk=self.account.plan_revision_id).update(terms=evidence)
        anytime = create_configuration_version(values=independent_values(accumulation="INR_PURCHASE_CREDIT"),
            actor=self.owner, reason="No invented duration")
        candidate = SchemeAccount.objects.get(pk=self.account.pk)
        candidate.configuration_snapshot = anytime
        with self.assertRaises(ValidationError):
            validate_independent_account_terms(candidate)
