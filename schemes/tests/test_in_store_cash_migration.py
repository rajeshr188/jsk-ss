from datetime import date, timedelta
from decimal import Decimal

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone


class InStoreCashMigrationTests(TransactionTestCase):
    migrate_from = ("schemes", "0017_contribution_checkout_expiry")
    migrate_to = ("schemes", "0018_in_store_cash_contributions")
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

    def test_backfills_historical_provider_channels(self):
        User = self.old_apps.get_model("accounts", "CustomUser")
        Customer = self.old_apps.get_model("schemes", "Customer")
        MetalGrade = self.old_apps.get_model("schemes", "MetalGrade")
        SchemeAccount = self.old_apps.get_model("schemes", "SchemeAccount")
        SchemePlan = self.old_apps.get_model("schemes", "SchemePlan")
        Contribution = self.old_apps.get_model("schemes", "Contribution")

        user = User.objects.create(
            username="cash-channel-migration@example.com",
            email="cash-channel-migration@example.com",
            password="!",
            role="CUSTOMER",
        )
        customer = Customer.objects.create(
            user=user,
            customer_number="CASH-CHANNEL-MIG",
            full_name="Cash Channel Migration",
            mobile_number="9000000102",
            email=user.email,
        )
        plan = SchemePlan.objects.create(
            name="Cash channel migration plan",
            code="CASH-CHANNEL-MIG",
            amount_rule="VARIABLE",
            frequency_rule="FLEXIBLE",
            minimum_contribution=Decimal("100.00"),
            maximum_contribution=Decimal("10000.00"),
        )
        grade = MetalGrade.objects.create(
            code="GOLD_22K_916",
            metal="GOLD",
            display_name="22K Gold",
            fineness=Decimal("0.916000"),
            display_order=10,
        )
        account = SchemeAccount.objects.create(
            scheme_number="JSK-CASH-CHANNEL-MIG",
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
            maximum_amount_snapshot=Decimal("10000.00"),
        )
        razorpay = Contribution.objects.create(
            scheme_account=account,
            amount=Decimal("500.00"),
            contribution_period=date(2026, 9, 1),
            frequency_rule_snapshot="FLEXIBLE",
            status="PENDING",
            payment_gateway="razorpay",
            gateway_mode="live",
            gateway_order_id="order_channel_migration",
            checkout_expires_at=timezone.now() + timedelta(minutes=10),
        )
        mock = Contribution.objects.create(
            scheme_account=account,
            amount=Decimal("500.00"),
            contribution_period=date(2026, 8, 1),
            frequency_rule_snapshot="FLEXIBLE",
            status="FAILED",
            payment_gateway="mock",
        )

        executor = MigrationExecutor(connection)
        targets = [self.migrate_to, self.accounts_target]
        executor.migrate(targets)
        NewContribution = executor.loader.project_state(targets).apps.get_model(
            "schemes", "Contribution"
        )

        self.assertEqual(
            NewContribution.objects.get(pk=razorpay.pk).payment_channel,
            "RAZORPAY",
        )
        self.assertEqual(
            NewContribution.objects.get(pk=mock.pk).payment_channel,
            "MOCK",
        )
