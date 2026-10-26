from datetime import date
from decimal import Decimal

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

from .migration_helpers import applied_migration_apps


class PlanGovernanceMigrationTests(TransactionTestCase):
    def setUp(self):
        super().setUp()
        executor = MigrationExecutor(connection)
        self.latest = executor.loader.graph.leaf_nodes()
        target = [("schemes", "0020_scheme_enrolment_requests")]
        executor.migrate(target)
        self.old_apps = applied_migration_apps()

    def tearDown(self):
        MigrationExecutor(connection).migrate(self.latest)
        super().tearDown()

    def test_upgrade_freezes_legacy_identity_without_changing_agreement(self):
        User = self.old_apps.get_model("accounts", "CustomUser")
        Customer = self.old_apps.get_model("schemes", "Customer")
        Plan = self.old_apps.get_model("schemes", "SchemePlan")
        Grade = self.old_apps.get_model("schemes", "MetalGrade")
        Account = self.old_apps.get_model("schemes", "SchemeAccount")
        user = User.objects.create(username="revision-upgrade", email="upgrade@example.invalid", role="CUSTOMER")
        customer = Customer.objects.create(user=user, customer_number="REV-UPGRADE", full_name="Upgrade fixture", email=user.email)
        plan = Plan.objects.create(name="Current observed legacy name", code="REV-UPGRADE", minimum_contribution=Decimal("100"), amount_rule="VARIABLE", frequency_rule="FLEXIBLE")
        grade, _ = Grade.objects.get_or_create(code="GOLD_22K_916", defaults={"metal": "GOLD", "display_name": "22K Gold", "fineness": Decimal("0.916000")})
        account = Account.objects.create(scheme_number="JSK-REV-UPGRADE", customer=customer,
            plan=plan, start_date=date(2025, 1, 31), agreed_months=18, eligible_from=date(2026, 7, 31),
            savings_mode="GOLD", metal_grade=grade, amount_rule_snapshot="VARIABLE",
            frequency_rule_snapshot="FLEXIBLE", minimum_amount_snapshot=Decimal("75.00"))
        before = Account.objects.filter(pk=account.pk).values().get()
        executor = MigrationExecutor(connection)
        target = [("schemes", "0021_plan_agreement_governance")]
        executor.migrate(target)
        new_apps = applied_migration_apps()
        after = new_apps.get_model("schemes", "SchemeAccount").objects.values().get(pk=account.pk)
        self.assertEqual({key: after[key] for key in before}, before)
        self.assertEqual(after["plan_name_snapshot"], plan.name)
        self.assertEqual(after["plan_code_snapshot"], plan.code)
        self.assertIsNone(after["plan_revision_id"])
        self.assertEqual(new_apps.get_model("schemes", "SchemePlanRevision").objects.count(), 0)
