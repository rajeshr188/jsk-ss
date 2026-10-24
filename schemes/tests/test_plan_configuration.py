from decimal import Decimal
from io import StringIO
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, close_old_connections, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse

from schemes.models import (
    AuditEvent, Contribution, MetalAllocation, SchemeAccount, SchemePlan,
    SchemePlanConfiguration, SchemePlanRevision,
)
from schemes.plan_configuration import (
    create_configuration_version, create_configured_plan_draft,
    preview_configuration_agreement,
)
from schemes.plan_governance import plan_edit_digest, save_scheme_plan
from schemes.services import enroll_customer
from schemes.tests.grade_helpers import grade_for_mode
from schemes.tests.test_audit_exceptions import make_customer, make_owner, make_plan


@override_settings(DEBUG=False)
class PlanConfigurationTests(TestCase):
    def setUp(self):
        self.owner = make_owner()
        self.customer = make_customer()
        self.legacy = make_plan()
        self.grade = grade_for_mode(self.legacy, SchemeAccount.SavingsMode.GOLD)
        self.values = {
            "name": "Customer-selected calendar metal", "amount_policy": "CUSTOMER_FIXED",
            "minimum_amount": Decimal("500.00"), "maximum_amount": Decimal("10000.00"),
            "fixed_amount": None, "amount_step": Decimal("100.00"),
            "frequency_rule": "ONCE_PER_MONTH", "minimum_months": 12, "default_months": 12,
            "allow_contributions_after_eligibility": False,
        }

    def create(self, **changes):
        return create_configuration_version(values={**self.values, **changes}, actor=self.owner, reason="Prepare policy for review.")

    def draft(self, configuration, code="DRAFT"):
        return create_configured_plan_draft(configuration_id=configuration.pk, name="Prepared plan", code=code,
                                            metal_grades=[self.grade], actor=self.owner, reason="Prepare offer.")

    def preview(self, configuration, **changes):
        return preview_configuration_agreement(configuration=configuration, **{
            "amount": Decimal("1500"), "months": 12, "metal_grade": self.grade, **changes,
        })

    def test_version_append_and_reuse_do_not_modify_old_plans(self):
        first = self.create()
        plan = self.draft(first)
        other = self.draft(first, "DRAFT-TWO")
        second = create_configuration_version(values={**self.values, "minimum_amount": Decimal("1000.00")},
            actor=self.owner, reason="New offers only.", previous_id=first.pk)
        self.assertEqual(second.family_id, first.family_id)
        self.assertEqual(second.version, 2)
        self.assertEqual(second.previous_id, first.pk)
        plan.refresh_from_db()
        self.assertEqual(plan.configuration_id, first.pk)
        self.assertEqual(plan.minimum_contribution, Decimal("500"))
        self.assertEqual(other.configuration_id, first.pk)
        self.assertEqual(plan.revisions.get().terms["configuration"]["id"], first.pk)
        self.assertEqual(AuditEvent.objects.filter(action="SCHEME_CHANGE").count(), 2)
        with self.assertRaisesMessage(ValidationError, "newer version"):
            create_configuration_version(values=self.values, actor=self.owner, reason="Stale editor", previous_id=first.pk)

    def test_configuration_immutable_and_not_deletable(self):
        configuration = self.create()
        configuration.name = "Changed"
        with self.assertRaisesMessage(ValidationError, "immutable"):
            configuration.save()
        with self.assertRaisesMessage(ValidationError, "cannot be deleted"):
            configuration.delete()

    def test_owner_permission_and_reason_required(self):
        for actor, reason in [(self.customer.user, "No permission"), (self.owner, "  ")]:
            with self.subTest(actor=actor.pk, reason=reason), self.assertRaises(ValidationError):
                create_configuration_version(values=self.values, actor=actor, reason=reason)
        self.assertFalse(SchemePlanConfiguration.objects.exists())

    def test_unsupported_policies_and_invalid_combinations_rejected(self):
        for changes in [
            {"accumulation": "INR"}, {"benefit_policy": "CASH_BONUS"}, {"eligibility_policy": "ANYTIME"},
            {"eligibility_policy": "PAID_INSTALMENTS"}, {"instalment_policy": "MONTHLY"},
            {"missed_payment_policy": "FORFEIT"}, {"settlement_policy": "PARTIAL"},
            {"minimum_amount": Decimal("0")}, {"maximum_amount": Decimal("400")},
            {"amount_step": Decimal("0")}, {"minimum_months": 11}, {"default_months": 11},
            {"amount_policy": "UNSUPPORTED"}, {"fixed_amount": Decimal("500")},
            {"amount_policy": "PLAN_FIXED"}, {"frequency_rule": "DAILY"}, {"untrusted": "payload"},
        ]:
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                self.create(**changes)
        self.assertFalse(SchemePlanConfiguration.objects.exists())

    def test_customer_fixed_preview_has_exact_individual_limits_and_no_writes(self):
        configuration = self.create()
        before = [model.objects.count() for model in [SchemeAccount, Contribution, MetalAllocation, AuditEvent, SchemePlanRevision]]
        selected = self.preview(configuration)
        self.assertEqual(selected["amount_rule_snapshot"], "FIXED")
        for key in ["fixed_amount_snapshot", "minimum_amount_snapshot", "maximum_amount_snapshot"]:
            self.assertEqual(selected[key], "1500.00")
        self.assertEqual(selected["metal_grade"], self.grade.code)
        self.assertEqual(selected["settlement_policy"], "FULL_ONLY")
        self.assertFalse(selected["publishable"])
        self.assertEqual(before, [model.objects.count() for model in [SchemeAccount, Contribution, MetalAllocation, AuditEvent, SchemePlanRevision]])

    def test_preview_amount_boundaries_and_precision(self):
        configuration = self.create()
        for amount in ["499.99", "10000.01", "550", "500.001", "NaN", "Infinity", "no", None, 500.0, True]:
            with self.subTest(amount=amount), self.assertRaises(ValidationError):
                self.preview(configuration, amount=amount)
        for amount in [Decimal("500"), Decimal("10000")]:
            self.assertEqual(self.preview(configuration, amount=amount)["fixed_amount_snapshot"], format(amount, ".2f"))
        for months in [11, 12.0, True, 32768, None]:
            with self.subTest(months=months), self.assertRaises(ValidationError):
                self.preview(configuration, months=months)

    def test_plan_fixed_and_variable_preview_are_distinct(self):
        fixed = self.create(amount_policy="PLAN_FIXED", minimum_amount=Decimal("500"),
                            maximum_amount=Decimal("500"), fixed_amount=Decimal("500"), amount_step=None)
        self.assertEqual(self.preview(fixed, amount=Decimal("500"))["fixed_amount_snapshot"], "500.00")
        with self.assertRaises(ValidationError):
            self.preview(fixed)
        variable = self.create(amount_policy="VARIABLE", maximum_amount=None)
        result = self.preview(variable)
        self.assertEqual(result["amount_rule_snapshot"], "VARIABLE")
        self.assertIsNone(result["fixed_amount_snapshot"])
        self.assertEqual(result["minimum_amount_snapshot"], "500.00")

    def test_draft_cannot_publish_activate_or_enrol_even_with_stale_instance(self):
        plan = self.draft(self.create())
        self.assertFalse(plan.active)
        self.assertFalse(plan.publicly_listed)
        for values in [{"active": True}, {"publicly_listed": True}, {"minimum_contribution": Decimal("1")}]:
            with self.subTest(values=values), self.assertRaises(ValidationError):
                save_scheme_plan(plan_id=plan.pk, expected_digest=plan_edit_digest(plan), values=values,
                    metal_grades=[self.grade], actor=self.owner, reason="Attempt activation")
        plan.active = True
        with self.assertRaisesMessage(ValidationError, "preparation-only"):
            enroll_customer(customer=self.customer, plan=plan, metal_grade=self.grade, performed_by=self.owner)
        self.assertFalse(SchemeAccount.objects.exists())

    def test_database_blocks_activation_and_unsupported_policy(self):
        configuration = self.create()
        plan = self.draft(configuration)
        for changes in [{"active": True}, {"publicly_listed": True}]:
            with self.subTest(changes=changes), self.assertRaises(IntegrityError), transaction.atomic():
                SchemePlan.objects.filter(pk=plan.pk).update(**changes)
        for changes in [{"benefit_policy": "CASH"}, {"amount_policy": "PLAN_FIXED", "fixed_amount": None},
                        {"amount_step": Decimal("0")}, {"version": 2}]:
            with self.subTest(changes=changes), self.assertRaises(IntegrityError), transaction.atomic():
                SchemePlanConfiguration.objects.filter(pk=configuration.pk).update(**changes)

    def test_draft_audit_failure_rolls_back(self):
        configuration = self.create()
        with patch("schemes.services.record_scheme_plan_change", side_effect=RuntimeError("audit failed")):
            with self.assertRaises(RuntimeError):
                self.draft(configuration)
        self.assertFalse(SchemePlan.objects.filter(configuration=configuration).exists())
        self.assertFalse(SchemePlanRevision.objects.exists())

    def test_existing_plan_enrolment_remains_unchanged(self):
        self.draft(self.create())
        account = enroll_customer(customer=self.customer, plan=self.legacy, metal_grade=self.grade, performed_by=self.owner)
        self.assertEqual(account.amount_rule_snapshot, "VARIABLE")
        self.assertIsNone(account.fixed_amount_snapshot)
        self.assertEqual(account.minimum_amount_snapshot, Decimal("100"))
        self.legacy.refresh_from_db()
        self.assertIsNone(self.legacy.configuration_id)

    def test_owner_ui_create_preview_version_and_reuse(self):
        self.client.force_login(self.owner)
        payload = {key: "" if value is None else value for key, value in self.values.items()}
        payload.pop("allow_contributions_after_eligibility")
        payload["reason"] = "Owner draft preparation"
        response = self.client.post(reverse("schemes:plan_configuration_create"), payload)
        self.assertEqual(response.status_code, 302)
        configuration = SchemePlanConfiguration.objects.get()
        self.assertContains(self.client.get(reverse("schemes:plan_configuration_list")), "Preparation only")
        url = reverse("schemes:plan_configuration_detail", args=[configuration.pk])
        self.assertContains(self.client.post(url, {"amount": "1500", "months": 12, "metal_grade": self.grade.pk}), "1500.00")
        draft_url = reverse("schemes:configured_plan_create", args=[configuration.pk])
        self.assertContains(self.client.get(draft_url), "inactive, unlisted")
        self.assertEqual(self.client.post(draft_url, {"name": "Draft", "code": "DRAFT", "metal_grades": [self.grade.pk], "reason": "Prepare"}).status_code, 302)
        plan = SchemePlan.objects.get(code="DRAFT")
        self.assertContains(self.client.get(reverse("schemes:plan_edit", args=[plan.pk])), "Preparation-only plan")
        self.assertContains(self.client.get(reverse("schemes:plan_list")), "Customer chooses once")
        version_url = reverse("schemes:plan_configuration_new_version", args=[configuration.pk])
        self.assertContains(self.client.get(version_url), "Earlier versions")
        self.assertEqual(self.client.post(version_url, payload).status_code, 302)
        self.assertEqual(SchemePlanConfiguration.objects.count(), 2)
        self.assertEqual(self.client.post(version_url, payload).status_code, 200)
        self.assertEqual(SchemePlanConfiguration.objects.count(), 2)

    def test_forged_policy_field_rejected_by_form(self):
        self.client.force_login(self.owner)
        payload = {**self.values, "reason": "Forged", "benefit_policy": "CASH"}
        payload.pop("fixed_amount")
        response = self.client.post(reverse("schemes:plan_configuration_create"), payload)
        self.assertContains(response, "Advanced policy dimensions")
        self.assertFalse(SchemePlanConfiguration.objects.exists())

    def test_customer_and_anonymous_cannot_access_owner_catalogue(self):
        configuration = self.create()
        names = [("plan_configuration_list", []), ("plan_configuration_create", []),
                 ("plan_configuration_detail", [configuration.pk]), ("configured_plan_create", [configuration.pk]),
                 ("plan_configuration_new_version", [configuration.pk])]
        for name, args in names:
            url = reverse(f"schemes:{name}", args=args)
            self.assertEqual(self.client.get(url).status_code, 302)
            self.client.force_login(self.customer.user)
            self.assertEqual(self.client.get(url).status_code, 403)
            self.assertEqual(self.client.post(url, {}).status_code, 403)
            self.client.logout()

    def test_integrity_check_detects_projection_and_revision_drift(self):
        configuration = self.create()
        plan = self.draft(configuration)
        output = StringIO()
        call_command("check_plan_configurations", stdout=output)
        self.assertIn("status=ok", output.getvalue())
        SchemePlan.objects.filter(pk=plan.pk).update(minimum_contribution=Decimal("600"))
        with self.assertRaises(CommandError):
            call_command("check_plan_configurations", stdout=StringIO())
        SchemePlan.objects.filter(pk=plan.pk).update(minimum_contribution=Decimal("500"))
        SchemePlanRevision.objects.filter(plan=plan).update(terms={})
        with self.assertRaises(CommandError):
            call_command("check_plan_configurations", stdout=StringIO())

    def test_csrf_required_for_configuration_post(self):
        from django.test import Client
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        self.assertEqual(client.post(reverse("schemes:plan_configuration_create"), {}).status_code, 403)
        self.assertFalse(SchemePlanConfiguration.objects.exists())


class ConfigurationVersionConcurrencyTests(TransactionTestCase):
    def test_competing_new_versions_have_one_successor(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        owner = make_owner()
        values = {"name": "Version race", "amount_policy": "VARIABLE", "minimum_amount": Decimal("100"),
                  "frequency_rule": "FLEXIBLE"}
        first = create_configuration_version(values=values, actor=owner, reason="First")
        barrier = Barrier(2)

        def append():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                try:
                    return create_configuration_version(values=values, actor=owner, reason="Append", previous_id=first.pk).version
                except ValidationError:
                    return "stale"
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: append(), range(2)))
        self.assertCountEqual(results, [2, "stale"])
        self.assertEqual(SchemePlanConfiguration.objects.filter(family_id=first.family_id).count(), 2)
