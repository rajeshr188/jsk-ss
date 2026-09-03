from datetime import date, timedelta
from decimal import Decimal

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone


class ManualSchemeRateMigrationTests(TransactionTestCase):
    migrate_from = ("schemes", "0009_schemeplan_publicly_listed")
    migrate_to = ("schemes", "0010_manual_scheme_rates")
    restore_to = ("schemes", "0017_contribution_checkout_expiry")
    accounts_target = ("accounts", "0002_customuser_role")

    def setUp(self):
        super().setUp()
        executor = MigrationExecutor(connection)
        targets = [self.migrate_from, self.accounts_target]
        executor.migrate(targets)
        self.old_apps = executor.loader.project_state(targets).apps

    def tearDown(self):
        MigrationExecutor(connection).migrate([self.restore_to, self.accounts_target])
        super().tearDown()

    def make_gold_account(self, suffix):
        User = self.old_apps.get_model("accounts", "CustomUser")
        Customer = self.old_apps.get_model("schemes", "Customer")
        SchemeAccount = self.old_apps.get_model("schemes", "SchemeAccount")
        SchemePlan = self.old_apps.get_model("schemes", "SchemePlan")

        user = User.objects.create(
            username=f"migration-{suffix}@example.com",
            email=f"migration-{suffix}@example.com",
            password="!",
            role="CUSTOMER",
        )
        customer = Customer.objects.create(
            user=user,
            customer_number=f"MIG-{suffix}",
            full_name=f"Migration {suffix}",
            mobile_number="9000000999",
            email=user.email,
        )
        plan = SchemePlan.objects.create(
            name=f"Migration plan {suffix}",
            code=f"MIG-{suffix}",
            amount_rule="VARIABLE",
            frequency_rule="FLEXIBLE",
            minimum_contribution=Decimal("1000.00"),
            maximum_contribution=Decimal("100000.00"),
        )
        return SchemeAccount.objects.create(
            scheme_number=f"JSK-MIG-{suffix}",
            customer=customer,
            plan=plan,
            start_date=date(2026, 1, 1),
            agreed_months=12,
            eligible_from=date(2027, 1, 1),
            savings_mode="GOLD",
            amount_rule_snapshot="VARIABLE",
            frequency_rule_snapshot="FLEXIBLE",
            minimum_amount_snapshot=Decimal("1000.00"),
            maximum_amount_snapshot=Decimal("100000.00"),
        )

    def migrate_forward(self):
        executor = MigrationExecutor(connection)
        targets = [self.migrate_to, self.accounts_target]
        executor.migrate(targets)
        return executor.loader.project_state(targets).apps

    def test_backfills_historical_rate_link_with_truthful_rate_timestamp(self):
        Contribution = self.old_apps.get_model("schemes", "Contribution")
        MetalAllocation = self.old_apps.get_model("schemes", "MetalAllocation")
        RateSnapshot = self.old_apps.get_model("schemes", "RateSnapshot")
        account = self.make_gold_account("BACKFILL")
        now = timezone.now()
        rate_fetched_at = now - timedelta(minutes=5)
        contribution = Contribution.objects.create(
            scheme_account=account,
            amount=Decimal("10000.00"),
            contribution_period=date(2026, 8, 1),
            frequency_rule_snapshot="FLEXIBLE",
            status="PAID",
            payment_gateway="mock",
            gateway_reference="mock_migration_backfill",
            paid_at=now,
        )
        rate = RateSnapshot.objects.create(
            metal="GOLD",
            provider="legacy-provider",
            provider_timestamp=rate_fetched_at,
            provider_rate=Decimal("12500.0000"),
            applied_rate=Decimal("12500.0000"),
            purity=Decimal("0.9999"),
        )
        RateSnapshot.objects.filter(pk=rate.pk).update(fetched_at=rate_fetched_at)
        MetalAllocation.objects.create(
            contribution=contribution,
            rate_snapshot=rate,
            metal="GOLD",
            quantity=Decimal("0.800000"),
        )

        new_apps = self.migrate_forward()
        NewContribution = new_apps.get_model("schemes", "Contribution")
        SchemeRate = new_apps.get_model("schemes", "SchemeRate")
        migrated_contribution = NewContribution.objects.get(pk=contribution.pk)
        migrated_rate = SchemeRate.objects.get(pk=rate.pk)

        self.assertEqual(migrated_contribution.scheme_rate_id, migrated_rate.pk)
        self.assertEqual(migrated_contribution.rate_locked_at, rate_fetched_at)
        self.assertEqual(migrated_rate.published_at, rate_fetched_at)
        self.assertEqual(migrated_rate.rate_per_gram, Decimal("12500.0000"))
        self.assertIsNone(migrated_rate.published_by_id)
        self.assertIn("former provider-backed architecture", migrated_rate.notes)

    def test_blocks_all_verified_unallocated_metal_and_open_orders(self):
        Contribution = self.old_apps.get_model("schemes", "Contribution")
        account = self.make_gold_account("BLOCKERS")
        now = timezone.now()
        paid = Contribution.objects.create(
            scheme_account=account,
            amount=Decimal("10000.00"),
            contribution_period=date(2026, 8, 1),
            frequency_rule_snapshot="FLEXIBLE",
            status="PAID",
            payment_gateway="razorpay",
            gateway_reference="pay_migration_unallocated",
            paid_at=now,
        )
        pending = Contribution.objects.create(
            scheme_account=account,
            amount=Decimal("10000.00"),
            contribution_period=date(2026, 9, 1),
            frequency_rule_snapshot="FLEXIBLE",
            status="PENDING",
            payment_gateway="razorpay",
            gateway_order_id="order_migration_open",
        )

        with self.assertRaises(RuntimeError) as raised:
            self.migrate_forward()

        message = str(raised.exception)
        self.assertIn("verified_metal_without_allocation=1", message)
        self.assertIn("open_razorpay_orders=1", message)

        Contribution.objects.filter(pk__in=[paid.pk, pending.pk]).delete()
        self.migrate_forward()
