from datetime import date
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from importlib import import_module
from io import StringIO
from types import SimpleNamespace
from threading import Event
from unittest.mock import patch

from django.apps import apps
from django.contrib.admin.sites import AdminSite
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import close_old_connections, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase, RequestFactory, override_settings
from django.urls import reverse

from schemes.admin import SchemePlanAdmin
from schemes.models import AuditEvent, SchemeAccount, SchemePlan, SchemePlanRevision
from schemes.plan_governance import plan_edit_digest, save_scheme_plan
from schemes.services import enroll_customer
from schemes.tests.test_audit_exceptions import make_customer, make_owner, make_plan
from schemes.tests.grade_helpers import grade_for_mode


@override_settings(DEBUG=False)
class PlanGovernanceTests(TestCase):
    def setUp(self):
        self.owner = make_owner()
        self.customer = make_customer()
        self.plan = make_plan()
        self.grade = grade_for_mode(self.plan, SchemeAccount.SavingsMode.GOLD)

    def enroll(self):
        return enroll_customer(customer=self.customer, plan=self.plan, metal_grade=self.grade,
                               start_date=date(2026, 1, 31), agreed_months=18, performed_by=self.owner)

    def edit(self, values, **kwargs):
        self.plan.refresh_from_db()
        return save_scheme_plan(plan_id=self.plan.pk, values=values, metal_grades=[self.grade],
                                actor=self.owner, reason="Approved future offer update.",
                                expected_digest=kwargs.get("digest", plan_edit_digest(self.plan)))

    def test_edit_preserves_existing_agreement_and_versions_future_enrolment(self):
        first = self.enroll()
        revision = first.plan_revision
        self.edit({"name": "New name", "code": "NEW-CODE", "minimum_contribution": Decimal("200.00")})
        first.refresh_from_db()
        self.assertEqual(first.display_plan_name, "Audit Plan")
        self.assertEqual(first.display_plan_code, "AUDIT-PLAN")
        self.assertEqual(first.minimum_amount_snapshot, Decimal("100.00"))
        self.assertEqual(first.eligible_from, date(2027, 7, 31))
        self.assertEqual(first.plan_revision_id, revision.pk)
        second = self.enroll()
        self.assertEqual(second.display_plan_name, "New name")
        self.assertEqual(second.minimum_amount_snapshot, Decimal("200.00"))
        self.assertEqual(second.plan_revision.number, revision.number + 1)
        self.assertEqual(revision.terms["eligibility_basis"], "CALENDAR_MONTHS")
        self.assertEqual(AuditEvent.objects.filter(action="SCHEME_CHANGE").count(), 1)

    def test_stale_edit_and_missing_digest_rejected_without_mutation(self):
        old_digest = plan_edit_digest(self.plan)
        self.edit({"name": "New name"})
        for digest in (old_digest, None):
            with self.assertRaisesMessage(ValidationError, "Reload"):
                self.edit({"name": "Stale replacement"}, digest=digest)
        self.plan.refresh_from_db()
        self.assertEqual(self.plan.name, "New name")
        self.assertEqual(AuditEvent.objects.filter(action="SCHEME_CHANGE").count(), 1)

    def test_noop_does_not_append_revision_or_audit(self):
        self.enroll()
        before = self.plan.revisions.count()
        _, changed = self.edit({"name": self.plan.name})
        self.assertFalse(changed)
        self.assertEqual(self.plan.revisions.count(), before)
        self.assertFalse(AuditEvent.objects.filter(action="SCHEME_CHANGE").exists())

    def test_revisions_and_account_identity_are_immutable(self):
        account = self.enroll()
        revision = account.plan_revision
        revision.reason = "Rewrite history"
        with self.assertRaisesMessage(ValidationError, "immutable"):
            revision.save()
        with self.assertRaisesMessage(ValidationError, "immutable"):
            revision.delete()
        account.plan_name_snapshot = "Rewrite agreement"
        with self.assertRaisesMessage(ValidationError, "immutable"):
            account.save(update_fields=["plan_name_snapshot"])

    def test_audit_failure_rolls_back_plan_and_revision(self):
        with patch("schemes.services.record_scheme_plan_change", side_effect=RuntimeError("audit failed")):
            with self.assertRaises(RuntimeError):
                self.edit({"name": "Must not persist"})
        self.plan.refresh_from_db()
        self.assertEqual(self.plan.name, "Audit Plan")
        self.assertFalse(self.plan.revisions.exists())

    def test_permission_and_production_cash_boundary(self):
        with self.assertRaises(ValidationError):
            save_scheme_plan(plan_id=self.plan.pk, values={"name": "No"}, metal_grades=[self.grade],
                             actor=self.customer.user, reason="No", expected_digest=plan_edit_digest(self.plan))
        with self.assertRaisesMessage(ValidationError, "Legacy cash"):
            self.edit({"cash_bonus_percentage": Decimal("5.00")})

    def test_creation_audited_and_never_public_by_default(self):
        plan, changed = save_scheme_plan(values={"name": "New", "code": "NEW",
            "minimum_contribution": Decimal("100"), "publicly_listed": True,
            "amount_rule": "VARIABLE", "frequency_rule": "FLEXIBLE"}, metal_grades=[self.grade],
            actor=self.owner, reason="Introduce an offer for review.")
        self.assertTrue(changed)
        self.assertFalse(plan.publicly_listed)
        self.assertEqual(plan.revisions.count(), 1)
        self.assertEqual(plan.revisions.first().terms["minimum_contribution"], "100.00")
        enrolled = enroll_customer(customer=self.customer, plan=plan, metal_grade=self.grade, performed_by=self.owner)
        self.assertEqual(enrolled.plan_revision.number, 1)
        self.assertTrue(AuditEvent.objects.filter(scheme_plan=plan, action="SCHEME_CHANGE").exists())

    def test_admin_cannot_bypass_owner_governance(self):
        admin = SchemePlanAdmin(SchemePlan, AdminSite())
        request = RequestFactory().get("/")
        request.user = self.owner
        self.assertFalse(admin.has_change_permission(request, self.plan))
        self.assertFalse(admin.has_add_permission(request))
        self.assertFalse(admin.has_delete_permission(request, self.plan))

    def test_policies_use_agreed_eligibility_not_fixed_twelve_month_discontinuation(self):
        for name in ("terms", "cancellation_refund"):
            with self.subTest(policy=name):
                response = self.client.get(reverse(name))
                self.assertContains(response, "before its normal eligibility conditions are met")
                self.assertContains(response, "including agreements longer than twelve months")
                self.assertNotContains(response, "before its recorded eligibility date")
                self.assertNotContains(response, "within 12 months")

    def test_owner_creation_requires_reason_and_stale_post_is_visible(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse("schemes:plan_edit", args=[self.plan.pk]))
        self.assertContains(response, "What this edit affects")
        self.assertContains(response, 'name="expected_digest"')
        self.assertContains(self.client.get(reverse("schemes:plan_add")), 'name="audit_reason"')

    def test_legacy_backfill_preserves_financial_terms_without_acceptance_claim(self):
        account = self.enroll()
        SchemeAccount.objects.filter(pk=account.pk).update(plan_revision=None, plan_name_snapshot="", plan_code_snapshot="")
        migration = import_module("schemes.migrations.0021_plan_agreement_governance")
        migration.preserve_legacy_display_identity(apps, SimpleNamespace(connection=connection))
        self.edit({"name": "New name"})
        account.refresh_from_db()
        self.assertEqual(account.display_plan_name, "Audit Plan")
        self.assertIsNone(account.plan_revision_id)
        self.assertEqual(account.minimum_amount_snapshot, Decimal("100.00"))
        self.assertEqual(account.eligible_from, date(2027, 7, 31))

    def test_customer_display_uses_agreement_not_edited_offer(self):
        account = self.enroll()
        self.edit({"name": "Future-only offer"})
        self.client.force_login(self.customer.user)
        response = self.client.get(reverse("schemes:my_scheme_detail", args=[account.scheme_number]))
        self.assertContains(response, "Audit Plan")
        self.assertContains(response, "not conditional on twelve")
        self.assertNotContains(response, "Future-only offer")

    def test_current_plan_is_reloaded_before_enrolment(self):
        stale = self.plan
        SchemePlan.objects.filter(pk=self.plan.pk).update(active=False)
        with self.assertRaisesMessage(ValidationError, "Only active"):
            enroll_customer(customer=self.customer, plan=stale, metal_grade=self.grade)

    def test_integrity_check_catches_bypassed_snapshot_changes(self):
        account = self.enroll()
        output = StringIO()
        call_command("check_plan_agreements", stdout=output)
        self.assertIn("status=ok", output.getvalue())
        SchemeAccount.objects.filter(pk=account.pk).update(minimum_amount_snapshot=Decimal("101.00"))
        with self.assertRaises(CommandError):
            call_command("check_plan_agreements", stdout=StringIO())


@override_settings(DEBUG=False)
class PlanEnrolmentSerializationTests(TransactionTestCase):
    def test_enrolment_waits_for_audited_edit_then_snapshots_one_complete_revision(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        owner = make_owner()
        customer = make_customer()
        plan = make_plan()
        grade = grade_for_mode(plan, SchemeAccount.SavingsMode.GOLD)
        started = Event()

        def enrol_in_other_connection():
            close_old_connections()
            try:
                started.set()
                account = enroll_customer(customer=customer, plan=plan, metal_grade=grade, performed_by=owner)
                return account.pk
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=1) as pool:
            with transaction.atomic():
                locked_plan = SchemePlan.objects.select_for_update().get(pk=plan.pk)
                future = pool.submit(enrol_in_other_connection)
                self.assertTrue(started.wait(timeout=5))
                save_scheme_plan(plan_id=plan.pk, expected_digest=plan_edit_digest(locked_plan),
                                 values={"name": "Serialized offer", "minimum_contribution": Decimal("250.00")},
                                 metal_grades=[grade], actor=owner, reason="Concurrent edit rehearsal.")
            account = SchemeAccount.objects.get(pk=future.result(timeout=15))
        self.assertEqual(account.plan_name_snapshot, "Serialized offer")
        self.assertEqual(account.minimum_amount_snapshot, Decimal("250.00"))
        self.assertEqual(account.plan_revision.terms["minimum_contribution"], "250.00")
