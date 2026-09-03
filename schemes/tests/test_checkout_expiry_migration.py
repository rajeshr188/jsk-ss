from datetime import date, timedelta
from decimal import Decimal

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone


class CheckoutExpiryMigrationTests(TransactionTestCase):
    migrate_from = ("schemes", "0016_graded_rate_precision_labels")
    migrate_to = ("schemes", "0017_contribution_checkout_expiry")
    accounts_target = ("accounts", "0003_customerinvitation_and_more")

    def setUp(self):
        super().setUp()
        executor = MigrationExecutor(connection)
        targets = [self.migrate_from, self.accounts_target]
        executor.migrate(targets)
        self.old_apps = executor.loader.project_state(targets).apps

    def tearDown(self):
        MigrationExecutor(connection).migrate(
            [self.migrate_to, self.accounts_target]
        )
        super().tearDown()

    def test_backfills_only_pending_razorpay_checkout_deadline(self):
        User = self.old_apps.get_model("accounts", "CustomUser")
        Customer = self.old_apps.get_model("schemes", "Customer")
        MetalGrade = self.old_apps.get_model("schemes", "MetalGrade")
        SchemeAccount = self.old_apps.get_model("schemes", "SchemeAccount")
        SchemePlan = self.old_apps.get_model("schemes", "SchemePlan")
        Contribution = self.old_apps.get_model("schemes", "Contribution")

        user = User.objects.create(
            username="checkout-expiry-migration@example.com",
            email="checkout-expiry-migration@example.com",
            password="!",
            role="CUSTOMER",
        )
        customer = Customer.objects.create(
            user=user,
            customer_number="EXPIRY-MIG",
            full_name="Checkout Expiry Migration",
            mobile_number="9000000777",
            email=user.email,
        )
        plan = SchemePlan.objects.create(
            name="Checkout expiry migration plan",
            code="EXPIRY-MIG",
            amount_rule="VARIABLE",
            frequency_rule="FLEXIBLE",
            minimum_contribution=Decimal("100.00"),
            maximum_contribution=Decimal("100000.00"),
        )
        grade = MetalGrade.objects.create(
            code="GOLD_22K_916",
            metal="GOLD",
            display_name="22K Gold",
            fineness=Decimal("0.916000"),
            display_order=10,
        )
        account = SchemeAccount.objects.create(
            scheme_number="JSK-EXPIRY-MIG",
            customer=customer,
            plan=plan,
            start_date=date(2026, 1, 1),
            agreed_months=12,
            eligible_from=date(2027, 1, 1),
            savings_mode="GOLD",
            metal_grade=grade,
            amount_rule_snapshot="VARIABLE",
            frequency_rule_snapshot="FLEXIBLE",
            minimum_amount_snapshot=Decimal("100.00"),
            maximum_amount_snapshot=Decimal("100000.00"),
        )
        pending = Contribution.objects.create(
            scheme_account=account,
            amount=Decimal("5000.00"),
            contribution_period=date(2026, 9, 1),
            frequency_rule_snapshot="FLEXIBLE",
            status="PENDING",
            payment_gateway="razorpay",
            gateway_mode="test",
            gateway_order_id="order_checkout_expiry_migration",
        )
        mock = Contribution.objects.create(
            scheme_account=account,
            amount=Decimal("5000.00"),
            contribution_period=date(2026, 8, 1),
            frequency_rule_snapshot="FLEXIBLE",
            status="FAILED",
            payment_gateway="mock",
        )
        created_at = timezone.now() - timedelta(hours=2)
        Contribution.objects.filter(pk=pending.pk).update(created_at=created_at)

        executor = MigrationExecutor(connection)
        targets = [self.migrate_to, self.accounts_target]
        executor.migrate(targets)
        new_apps = executor.loader.project_state(targets).apps
        NewContribution = new_apps.get_model("schemes", "Contribution")

        migrated_pending = NewContribution.objects.get(pk=pending.pk)
        migrated_mock = NewContribution.objects.get(pk=mock.pk)
        self.assertEqual(
            migrated_pending.checkout_expires_at,
            created_at + timedelta(minutes=10),
        )
        self.assertIsNone(migrated_mock.checkout_expires_at)
