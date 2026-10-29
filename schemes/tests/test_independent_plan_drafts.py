"""Draft offers are auditable preparation, never financial activation."""
import uuid
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse

from schemes.models import (AuditEvent, Contribution, InrPrincipalReceipt, MetalAllocation,
    MetalGrade, SchemeAccount, SchemePlan, SchemePlanRevision, SchemePlanOffering)
from schemes.plan_configuration import create_configuration_version, create_configured_plan_draft
from schemes.plan_governance import plan_edit_digest, plan_terms, save_scheme_plan
from schemes.plan_publication import set_configured_plan_publication
from schemes.services import enroll_customer
from schemes.tests.test_audit_exceptions import make_owner, make_customer, make_plan
from schemes.tests.test_independent_policy_fields import independent_values, required_values


def draft(owner, values, grades=()):
    config = create_configuration_version(values=values, actor=owner, reason="Prepare independent policy")
    return create_configured_plan_draft(configuration_id=config.pk, name="Prepared offer", code=uuid.uuid4().hex[:20],
        metal_grades=grades, actor=owner, reason="Prepare draft")


@override_settings(CONFIGURED_PLANS_ENABLED=False)
class IndependentPlanDraftTests(TestCase):
    def setUp(self):
        self.owner, self.customer = make_owner(), make_customer()
        self.grade = MetalGrade.objects.get(code="GOLD_22K_916")
        self.client.force_login(self.owner)

    def assert_no_finance(self):
        for model in (SchemeAccount, Contribution, InrPrincipalReceipt, MetalAllocation):
            self.assertFalse(model.objects.exists())

    def test_five_families_both_denominations_and_bases_preserve_exact_terms(self):
        for accumulation in ("EXACT_METAL", "INR_PURCHASE_CREDIT"):
            for basis in ("CALENDAR_MONTH", "ANNIVERSARY"):
                cases = [independent_values(accumulation=accumulation),
                    independent_values(accumulation=accumulation, eligibility_policy="CALENDAR", duration_months=1,
                        frequency_rule="ONCE_PER_PERIOD", period_basis=basis),
                    required_values(accumulation=accumulation, period_basis=basis),
                    required_values(accumulation=accumulation, period_basis=basis,
                        eligibility_policy="CALENDAR_AND_COUNT", duration_months=18),
                    required_values(accumulation=accumulation, period_basis=basis, eligibility_policy="CALENDAR",
                        duration_months=12, missed_payment_policy="LOSE_UNEARNED_BENEFIT", max_extension_months=None,
                        benefit_policy="VA_DISCOUNT", benefit_percentage=Decimal("5"), benefit_cap_inr=Decimal("500"),
                        benefit_qualification="REQUIRED_SCHEDULE", benefit_on_miss="DISQUALIFY_UNEARNED",
                        eligible_charge_definition="Making charges before tax")]
                for values in cases:
                    with self.subTest(values=values):
                        plan = draft(self.owner, values, [self.grade] if accumulation == "EXACT_METAL" else [])
                        plan.full_clean()
                        self.assertFalse(plan.active or plan.publicly_listed)
                        self.assertIsNone(plan.publication_revision_id)
                        self.assertEqual(plan.minimum_months, values.get("duration_months"))
                        self.assertEqual(plan.default_months, values.get("duration_months"))
                        self.assertEqual(plan.frequency_rule, values["frequency_rule"])
                        self.assertEqual(plan.revisions.get().terms, plan_terms(plan))
                        self.assertEqual(plan.revisions.get().actor, self.owner)
                        if accumulation == "INR_PURCHASE_CREDIT":
                            self.assertFalse(plan.metal_offerings.exists())
        out = StringIO()
        call_command("check_plan_configurations", stdout=out)
        self.assertIn("status=ok", out.getvalue())
        self.assertEqual(AuditEvent.objects.filter(action="SCHEME_CHANGE").count(), 20)
        self.assert_no_finance()

    def test_grade_rules_unknown_fields_permission_and_audit_rollback(self):
        inr = independent_values(accumulation="INR_PURCHASE_CREDIT")
        for values, grades in ((inr, [self.grade]), (independent_values(), [])):
            with self.assertRaises(ValidationError):
                draft(self.owner, values, grades)
        with self.assertRaises(ValidationError):
            draft(self.customer.user, inr)
        with patch("schemes.services.record_scheme_plan_change", side_effect=RuntimeError("Audit failed")):
            with self.assertRaises(RuntimeError):
                draft(self.owner, inr)
        self.assertFalse(SchemePlan.objects.exists())
        self.assertFalse(SchemePlanRevision.objects.exists())
        self.assertFalse(SchemePlanOffering.objects.exists())

    def test_fixed_amount_bonus_and_grade_edit_keep_original_policy_and_revision(self):
        values = independent_values(accumulation="INR_PURCHASE_CREDIT", amount_policy="PLAN_FIXED",
            minimum_amount=Decimal("500"), maximum_amount=Decimal("500"), fixed_amount=Decimal("500"),
            benefit_policy="INR_PURCHASE_BONUS", benefit_percentage=Decimal("3"), benefit_cap_inr=Decimal("500"),
            benefit_qualification="NORMAL_ELIGIBILITY")
        plan = draft(self.owner, values)
        self.assertEqual(plan.fixed_contribution_amount, Decimal("500"))
        self.assertEqual(plan.cash_bonus_percentage, Decimal("0"))
        self.assertEqual(plan.revisions.get().terms["configuration"]["benefit_percentage"], "3.00")
        plan = draft(self.owner, independent_values(), [self.grade])
        original = plan.revisions.get().terms
        silver = MetalGrade.objects.get(code="SILVER_999")
        plan, _ = save_scheme_plan(plan_id=plan.pk, expected_digest=plan_edit_digest(plan),
            values={"name": plan.name}, metal_grades=[silver], actor=self.owner, reason="Offer silver in this draft")
        self.assertEqual(plan.revisions.get(number=1).terms, original)
        self.assertEqual(plan.revisions.get(number=2).terms["metal_grades"], ["SILVER_999"])
        self.assertEqual(plan.revisions.get(number=2).terms["configuration"], original["configuration"])
        self.assert_no_finance()

    def test_draft_requires_intake_permission_and_audited_publication_before_enrolment(self):
        for accumulation in ("EXACT_METAL", "INR_PURCHASE_CREDIT"):
            plan = draft(self.owner, independent_values(accumulation=accumulation),
                [self.grade] if accumulation == "EXACT_METAL" else [])
            before = plan_terms(plan)
            with self.settings(CONFIGURED_PLANS_ENABLED=False), self.assertRaises(ValidationError):
                set_configured_plan_publication(plan_id=plan.pk, publish=True, actor=self.owner,
                    reason="Blocked intake", expected_digest=plan_edit_digest(plan), confirmed=True)
            for enabled in (False, True):
                with self.settings(CONFIGURED_PLANS_ENABLED=enabled), self.assertRaises(ValidationError):
                    enroll_customer(customer=self.customer, plan=plan, performed_by=self.owner)
            for changes in ({"active": True}, {"publicly_listed": True}):
                with self.assertRaises(IntegrityError), transaction.atomic():
                    SchemePlan.objects.filter(pk=plan.pk).update(**changes)
            plan.refresh_from_db()
            self.assertEqual(plan_terms(plan), before)
            with self.settings(CONFIGURED_PLANS_ENABLED=True):
                set_configured_plan_publication(plan_id=plan.pk, publish=True, actor=self.owner,
                    reason="Approved separate publication", expected_digest=plan_edit_digest(plan), confirmed=True)
            plan.refresh_from_db()
            self.assertTrue(plan.active and plan.publicly_listed)
            self.assertEqual(plan_terms(plan)["configuration"], before["configuration"])
            self.assertEqual(plan.revisions.count(), 2)
        self.assert_no_finance()

    def test_identity_edit_appends_revision_and_rejects_stale_or_policy_mutations(self):
        plan = draft(self.owner, independent_values(accumulation="INR_PURCHASE_CREDIT"))
        old_digest, old_terms = plan_edit_digest(plan), plan.revisions.get().terms
        kwargs = dict(plan_id=plan.pk, actor=self.owner, reason="Correct draft name", metal_grades=[], expected_digest=old_digest)
        plan, changed = save_scheme_plan(values={"name": "New draft name", "description": "Private notes"}, **kwargs)
        self.assertTrue(changed)
        self.assertEqual(plan.revisions.count(), 2)
        self.assertEqual(plan.revisions.get(number=1).terms, old_terms)
        with self.assertRaisesMessage(ValidationError, "changed"):
            save_scheme_plan(values={"name": "Stale edit"}, **kwargs)
        for values in ({"minimum_months": 12}, {"active": True}, {"frequency_rule": "FLEXIBLE"}):
            with self.assertRaises(ValidationError):
                save_scheme_plan(values=values, **(kwargs | {"expected_digest": plan_edit_digest(plan)}))
        self.assertEqual(plan.revisions.count(), 2)
        self.assert_no_finance()

    def test_owner_ui_exact_rules_no_writes_on_get_and_private_access(self):
        config = create_configuration_version(values=independent_values(accumulation="INR_PURCHASE_CREDIT"),
            actor=self.owner, reason="Prepare")
        url = reverse("schemes:configured_plan_create", args=[config.pk])
        page = self.client.get(url)
        self.assertContains(page, "No minimum-duration condition")
        self.assertNotContains(page, 'name="metal_grades"')
        self.assertIn("no-store", page["Cache-Control"])
        self.assertFalse(SchemePlan.objects.exists())
        data = dict(name="Owner draft", code="OWNER", reason="Prepare", description="Notes")
        for extra in ({"active": "True"}, {"metal_grades": self.grade.pk}, {"configuration_id": config.pk}):
            self.assertEqual(self.client.post(url, data | extra).status_code, 200)
            self.assertFalse(SchemePlan.objects.exists())
        self.assertEqual(self.client.post(url, data).status_code, 302)
        plan = SchemePlan.objects.get()
        listing = self.client.get(reverse("schemes:plan_list"))
        self.assertContains(listing, "INR jewellery purchase credit")
        with self.settings(CONFIGURED_PLANS_ENABLED=True):
            review = self.client.get(reverse("schemes:configured_plan_publication", args=[plan.pk]))
            self.assertNotContains(review, "Independent offers remain preparation-only")
            self.assertContains(review, "No minimum-duration condition")
            self.assertNotContains(review, "No bonus or discount is included.")
            self.assertNotContains(review, 'disabled>Publish reviewed offer')
        self.assertEqual(plan.revisions.count(), 1)
        edit_url = reverse("schemes:plan_edit", args=[plan.pk])
        edit = self.client.get(edit_url)
        self.assertContains(edit, "No minimum-duration condition")
        self.assertNotContains(edit, 'name="minimum_months"')
        self.assertEqual(self.client.post(edit_url, data | {"name": "Renamed", "expected_digest": plan_edit_digest(plan)}).status_code, 302)
        self.assertEqual(self.client.put(url).status_code, 405)
        self.assertEqual(self.client.put(edit_url).status_code, 405)
        csrf = Client(enforce_csrf_checks=True); csrf.force_login(self.owner)
        self.assertEqual(csrf.post(url, data).status_code, 403)
        self.client.force_login(self.customer.user)
        self.assertEqual(self.client.get(edit_url).status_code, 403)
        self.assertEqual(self.client.post(url, data).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(url).status_code, 302)
        self.assert_no_finance()

    def test_database_duration_shapes_and_read_only_drift_diagnostic(self):
        legacy = make_plan()
        plan = draft(self.owner, independent_values(accumulation="INR_PURCHASE_CREDIT"))
        for row, changes in ((legacy, {"minimum_months": None, "default_months": None}),
                (legacy, {"minimum_months": 1}), (legacy, {"frequency_rule": "ONCE_PER_PERIOD"}),
                (plan, {"minimum_months": 1}), (plan, {"minimum_months": 0, "default_months": 0})):
            with self.assertRaises(IntegrityError), transaction.atomic():
                SchemePlan.objects.filter(pk=row.pk).update(**changes)
        SchemePlan.objects.filter(pk=plan.pk).update(description="Unaudited SQL edit")
        with self.assertRaises(CommandError):
            call_command("check_plan_configurations", stdout=StringIO())
        plan.refresh_from_db()
        self.assertEqual(plan.description, "Unaudited SQL edit")
        self.assertEqual(plan.revisions.count(), 1)


class IndependentDraftMigrationTests(TransactionTestCase):
    def test_forward_and_reverse_preserve_legacy_rows_and_revisions(self):
        owner = make_owner()
        plan = make_plan()
        from schemes.plan_governance import ensure_plan_revision
        revision = ensure_plan_revision(plan=plan, actor=owner, reason="Historical terms")
        before = plan_terms(plan)
        leaves = MigrationExecutor(connection).loader.graph.leaf_nodes()
        self.addCleanup(lambda: MigrationExecutor(connection).migrate(leaves))
        MigrationExecutor(connection).migrate([("schemes", "0049_benefit_invoice_reapplication")])
        MigrationExecutor(connection).migrate(leaves)
        plan.refresh_from_db(); revision.refresh_from_db()
        self.assertEqual(plan_terms(plan), before)
        self.assertEqual(revision.terms, before)

    def test_reverse_refuses_independent_drafts_without_discarding_evidence(self):
        leaves = MigrationExecutor(connection).loader.graph.leaf_nodes()
        current_tables = set(connection.introspection.table_names())
        # Newer additive migrations may reverse before 0050 refuses. Restore
        # the complete graph even when this test's assertions themselves fail.
        self.addCleanup(lambda: MigrationExecutor(connection).migrate(leaves))
        plan = draft(make_owner(), independent_values(accumulation="INR_PURCHASE_CREDIT"))
        before = plan.revisions.get().terms
        with self.assertRaisesMessage(RuntimeError, "Retain independent draft"):
            MigrationExecutor(connection).migrate([("schemes", "0049_benefit_invoice_reapplication")])
        MigrationExecutor(connection).migrate(leaves)
        self.assertEqual(set(connection.introspection.table_names()), current_tables)
        plan.refresh_from_db()
        self.assertIsNone(plan.minimum_months)
        self.assertEqual(plan.revisions.get().terms, before)
