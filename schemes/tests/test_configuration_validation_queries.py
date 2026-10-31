"""Batch evaluation keeps Django's CHECK/NULL and uniqueness behaviour unchanged."""
from copy import copy
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import DatabaseError, connection, models
from django.db.backends.utils import CursorWrapper
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from schemes.models import SchemePlanConfiguration
from schemes.tests.test_audit_exceptions import make_owner
from schemes.tests.test_independent_policy_fields import independent_values, required_values


class ConfigurationValidationQueryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = make_owner()

    def configuration(self, **changes):
        return SchemePlanConfiguration(**independent_values(**changes), created_by=self.owner,
            actor_label="Synthetic owner", reason="Validate every current condition")

    def outcome(self, configuration, *, stock=False, exclude=None):
        try:
            if stock:
                models.Model.validate_constraints(configuration, exclude=exclude)
            else:
                configuration.validate_constraints(exclude=exclude)
        except ValidationError as error:
            return error.message_dict
        return None

    def test_valid_configuration_checks_use_fewer_queries_without_writes_or_cache(self):
        configuration = self.configuration()
        with CaptureQueriesContext(connection) as stock:
            self.assertIsNone(self.outcome(configuration, stock=True))
        with CaptureQueriesContext(connection) as batched:
            self.assertIsNone(self.outcome(configuration))
        self.assertLess(len(batched), len(stock) // 2)
        self.assertTrue(all(q["sql"].split()[0].upper() in {"SELECT", "SAVEPOINT", "RELEASE"} for q in batched))
        configuration.minimum_amount = Decimal("-1")
        self.assertEqual(self.outcome(configuration), self.outcome(configuration, stock=True))
        self.assertIsNotNone(self.outcome(configuration))
        configuration.minimum_amount = Decimal("100")
        with CaptureQueriesContext(connection) as repeated:
            self.assertIsNone(self.outcome(configuration))
        self.assertEqual(len(repeated), len(batched))  # No previous pass is reused.

    def test_nullable_invalid_amount_schedule_benefit_version_and_evidence_match_stock_errors(self):
        cases = [{}, {"maximum_amount": None}, {"amount_step": Decimal("10")},
            {"version": 0}, {"version": 2}, {"minimum_amount": Decimal("0")},
            {"maximum_amount": Decimal("10")}, {"amount_step": Decimal("0")},
            {"amount_policy": "PLAN_FIXED"}, {"fixed_amount": Decimal("200")},
            {"frequency_rule": "ONCE_PER_PERIOD"}, {"period_basis": "CALENDAR_MONTH"},
            {"required_count": 3}, {"duration_months": 12}, {"grace_days": None},
            {"grace_days": 1}, {"catch_up_policy": None}, {"settlement_policy": "PARTIAL"},
            {"benefit_policy": "INR_PURCHASE_BONUS"}, {"benefit_cap_inr": Decimal("1000000000000")},
            {"benefit_percentage": Decimal("0")}, {"policy_schema_version": 99}]
        for changes in cases:
            with self.subTest(changes=changes):
                configuration = self.configuration(**changes)
                self.assertEqual(self.outcome(configuration), self.outcome(configuration, stock=True))
        for field in ("actor_label", "reason"):
            configuration = self.configuration()
            setattr(configuration, field, "")
            self.assertEqual(self.outcome(configuration), self.outcome(configuration, stock=True))
            self.assertIsNotNone(self.outcome(configuration))
        for values in (required_values(), independent_values(accumulation="INR_PURCHASE_CREDIT",
                benefit_policy="INR_PURCHASE_BONUS", benefit_percentage=Decimal("5"),
                benefit_cap_inr=Decimal("1000"), benefit_qualification="NORMAL_ELIGIBILITY")):
            configuration = SchemePlanConfiguration(**values, created_by=self.owner, actor_label="Owner", reason="Parity")
            self.assertIsNone(self.outcome(configuration, stock=True))
            self.assertIsNone(self.outcome(configuration))

    def test_uniqueness_excluded_fields_and_persisted_reload_are_not_bypassed(self):
        configuration = self.configuration()
        configuration.save()
        duplicate = copy(configuration)
        duplicate._state = copy(configuration._state)
        duplicate.pk = None
        duplicate._state.adding = True
        self.assertEqual(self.outcome(duplicate), self.outcome(duplicate, stock=True))
        self.assertIsNotNone(self.outcome(duplicate))
        configuration.minimum_amount = Decimal("-1")
        self.assertEqual(self.outcome(configuration, exclude={"minimum_amount"}),
            self.outcome(configuration, stock=True, exclude={"minimum_amount"}))
        configuration.refresh_from_db()
        self.assertEqual(configuration.minimum_amount, Decimal("100"))
        configuration.full_clean()

    def test_swallowed_batch_sql_error_cannot_hide_an_invalid_individual_check(self):
        configuration = self.configuration(minimum_amount=Decimal("-1"))
        expected = self.outcome(configuration, stock=True)
        original = CursorWrapper._execute
        failed = False
        def fail_batch(cursor, sql, params, *args):
            nonlocal failed
            if not failed and '"_check"' in sql:
                failed = True
                raise DatabaseError("Synthetic batch evaluation failure")
            return original(cursor, sql, params, *args)
        with patch.object(CursorWrapper, "_execute", fail_batch), self.assertLogs("django.db.models", level="WARNING"):
            self.assertEqual(self.outcome(configuration), expected)
        self.assertTrue(failed)
        self.assertIsNotNone(expected)
