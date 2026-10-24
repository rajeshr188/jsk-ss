from dataclasses import FrozenInstanceError, replace
from decimal import Decimal
from itertools import product

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, override_settings

from schemes.models import SchemePlanConfiguration
from schemes.plan_configuration import configuration_evidence, configuration_plan_values
from schemes.plan_policies import (
    PlanPolicy, operational_policy_blockers, policy_from_configuration,
    require_operational_policy, validate_plan_policy,
)


class PlanPolicyTests(SimpleTestCase):
    def optional(self, **changes):
        return PlanPolicy(**{
            "accumulation": "EXACT_METAL", "amount_policy": "VARIABLE",
            "obligation": "OPTIONAL", "payment_limit": "FLEXIBLE",
            "eligibility": "DURATION", "duration_months": 12, **changes,
        })

    def monthly(self, **changes):
        return self.optional(**{
            "amount_policy": "CUSTOMER_FIXED", "obligation": "REQUIRED_MONTHLY",
            "payment_limit": "ONCE_PER_PERIOD", "period_basis": "CALENDAR_MONTH",
            "eligibility": "DURATION_AND_COUNT", "required_count": 12,
            "missed_outcome": "EXTEND_THEN_REVIEW", "extension_periods": 3, **changes,
        })

    def discount(self, **changes):
        return self.monthly(**{
            "benefit_kind": "VA_DISCOUNT", "benefit_percentage": Decimal("5.00"),
            "benefit_cap_inr": Decimal("1000.00"),
            "benefit_qualification": "REQUIRED_SCHEDULE",
            "benefit_on_miss": "PRESERVE_ON_COMPLETION",
            "eligible_charge_definition": "Invoice making charges excluding metal and taxes",
            **changes,
        })

    def test_optional_matrix_and_no_invented_obligation(self):
        for accumulation, amount, eligibility, basis in product(
            ("EXACT_METAL", "INR_PURCHASE_CREDIT"),
            ("PLAN_FIXED", "CUSTOMER_FIXED", "VARIABLE"),
            ("DURATION", "ANYTIME"), (None, "CALENDAR_MONTH", "ANNIVERSARY"),
        ):
            with self.subTest(accumulation=accumulation, amount=amount, eligibility=eligibility, basis=basis):
                validate_plan_policy(self.optional(
                    accumulation=accumulation, amount_policy=amount, eligibility=eligibility,
                    duration_months=12 if eligibility == "DURATION" else None,
                    period_basis=basis, payment_limit="ONCE_PER_PERIOD" if basis else "FLEXIBLE",
                ))

    def test_required_matrix_and_independent_count(self):
        for accumulation, amount, eligibility, basis in product(
            ("EXACT_METAL", "INR_PURCHASE_CREDIT"), ("PLAN_FIXED", "CUSTOMER_FIXED"),
            ("COUNT", "DURATION_AND_COUNT"), ("CALENDAR_MONTH", "ANNIVERSARY"),
        ):
            with self.subTest(accumulation=accumulation, amount=amount, eligibility=eligibility, basis=basis):
                validate_plan_policy(self.monthly(
                    accumulation=accumulation, amount_policy=amount, eligibility=eligibility,
                    period_basis=basis, required_count=10,
                    duration_months=12 if eligibility == "DURATION_AND_COUNT" else None,
                ))

    def test_duration_only_required_obligations_are_for_defined_benefit(self):
        policy = self.discount(eligibility="DURATION", missed_outcome="LOSE_UNEARNED_BENEFIT",
                               extension_periods=None, benefit_on_miss="DISQUALIFY_UNEARNED")
        validate_plan_policy(policy)
        for change in ({"benefit_kind": "NONE"}, {"missed_outcome": "NONE"},
                       {"extension_periods": 3}, {"benefit_on_miss": "PRESERVE_ON_COMPLETION"}):
            with self.subTest(change=change), self.assertRaises(ValidationError):
                validate_plan_policy(replace(policy, **change))

    def test_invalid_combinations_fail_closed(self):
        for policy in (
            self.optional(required_count=12), self.optional(missed_outcome="LOSE_UNEARNED_BENEFIT"),
            self.optional(eligibility="COUNT", duration_months=None),
            self.optional(period_basis="ANNIVERSARY"),
            self.monthly(amount_policy="VARIABLE"), self.monthly(payment_limit="FLEXIBLE"),
            self.monthly(period_basis=None), self.monthly(required_count=None),
            self.monthly(eligibility="ANYTIME", duration_months=None),
            self.monthly(eligibility="COUNT"), self.monthly(extension_periods=4),
            self.monthly(allow_post_eligibility=True), self.monthly(catch_up="BULK"),
            self.optional(settlement="PARTIAL"), self.optional(accumulation="CASH"),
        ):
            with self.subTest(policy=policy), self.assertRaises(ValidationError):
                validate_plan_policy(policy)

    def test_strict_types_and_unknown_schema(self):
        for field, values in {
            "schema_version": (True, 2, "1"), "duration_months": (True, 0, 12.0, "12", 32768),
            "grace_days": (False, 1, "0"), "allow_post_eligibility": (0, "False"),
            "eligibility": ([], None, "CUSTOM_CODE"), "eligible_charge_definition": ([], None),
        }.items():
            for value in values:
                with self.subTest(field=field, value=value), self.assertRaises(ValidationError):
                    validate_plan_policy(self.optional(**{field: value}))

    def test_benefit_decimal_inputs_and_explicit_caps(self):
        validate_plan_policy(self.discount())
        for field in ("benefit_percentage", "benefit_cap_inr"):
            for value in (None, True, 5.0, "5", Decimal("NaN"), Decimal("sNaN"),
                          Decimal("Infinity"), Decimal("0"), Decimal("-1"), Decimal("1.001")):
                with self.subTest(field=field, value=value), self.assertRaises(ValidationError):
                    validate_plan_policy(self.discount(**{field: value}))
        with self.assertRaises(ValidationError):
            validate_plan_policy(self.discount(benefit_percentage=Decimal("100.01")))

    def test_bonus_uses_only_inr_principal_and_discount_needs_charge_definition(self):
        bonus = self.discount(accumulation="INR_PURCHASE_CREDIT", benefit_kind="INR_PURCHASE_BONUS",
                              eligible_charge_definition="")
        validate_plan_policy(bonus)
        with self.assertRaises(ValidationError):
            validate_plan_policy(replace(bonus, accumulation="EXACT_METAL"))
        with self.assertRaises(ValidationError):
            validate_plan_policy(self.discount(eligible_charge_definition="  "))
        with self.assertRaises(ValidationError):
            validate_plan_policy(self.discount(benefit_qualification="NONE"))
        with self.assertRaises(ValidationError):
            validate_plan_policy(self.optional(benefit_cap_inr=Decimal("100")))

    def test_valid_design_does_not_mean_operational_support(self):
        for enabled in (False, True):
            with override_settings(CONFIGURED_PLANS_ENABLED=enabled):
                for policy in (
                    self.optional(accumulation="INR_PURCHASE_CREDIT"),
                    self.optional(eligibility="ANYTIME", duration_months=None),
                    self.monthly(eligibility="COUNT", duration_months=None),
                    self.monthly(amount_policy="PLAN_FIXED"), self.monthly(required_count=10),
                    self.optional(period_basis="ANNIVERSARY", payment_limit="ONCE_PER_PERIOD"),
                    self.optional(duration_months=6), self.discount(),
                ):
                    with self.subTest(enabled=enabled, policy=policy):
                        self.assertTrue(operational_policy_blockers(policy))
                        with self.assertRaises(ValidationError):
                            require_operational_policy(policy)
        self.assertIn("MANUAL_REFUND_FULFILMENT_NOT_IMPLEMENTED", operational_policy_blockers(
            self.optional(accumulation="INR_PURCHASE_CREDIT")))

    def test_existing_formats_keep_identical_evidence_and_projection(self):
        for monthly, basis in ((False, None), (True, "ANNIVERSARY"), (True, "CALENDAR_MONTH")):
            config = SchemePlanConfiguration(
                name="Existing", amount_policy="CUSTOMER_FIXED", minimum_amount=Decimal("500"),
                frequency_rule="ONCE_PER_PERIOD" if monthly else "ONCE_PER_MONTH",
                instalment_policy="MONTHLY_COMPLETION" if monthly else "NONE",
                eligibility_policy="CALENDAR_AND_COUNT" if monthly else "CALENDAR",
                missed_payment_policy="EXTEND_THEN_REVIEW" if monthly else "NONE",
                period_basis=basis, grace_days=0 if monthly else None,
                catch_up_policy="NONE" if monthly else None, max_extension_months=3 if monthly else None,
            )
            before = configuration_evidence(config)
            policy = policy_from_configuration(config)
            self.assertEqual(operational_policy_blockers(policy), ())
            self.assertEqual(configuration_plan_values(config)["minimum_months"], 12)
            self.assertEqual(configuration_evidence(config), before)
            self.assertNotIn("schema_version", before)
            self.assertEqual("period_basis" in before, monthly)

    def test_policies_are_immutable_and_no_financial_actions_are_performed(self):
        # SimpleTestCase forbids database access throughout this matrix suite.
        policy = self.optional()
        with self.assertRaises(FrozenInstanceError):
            policy.required_count = 12
        self.assertEqual(operational_policy_blockers(policy), ())

    def test_persisted_unknown_choices_are_not_silently_projected(self):
        for field in ("instalment_policy", "eligibility_policy", "frequency_rule"):
            config = SchemePlanConfiguration(**{field: "FUTURE_UNKNOWN"})
            with self.subTest(field=field), self.assertRaises(ValidationError):
                policy_from_configuration(config)
