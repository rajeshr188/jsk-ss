from datetime import date
from decimal import Decimal

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class RazorpayModeMigrationTests(TransactionTestCase):
    migrate_from = ("schemes", "0010_manual_scheme_rates")
    migrate_to = ("schemes", "0011_razorpay_gateway_mode")
    restore_to = ("schemes", "0018_in_store_cash_contributions")
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

    def test_existing_razorpay_records_are_truthfully_backfilled_as_test_mode(self):
        User = self.old_apps.get_model("accounts", "CustomUser")
        Customer = self.old_apps.get_model("schemes", "Customer")
        SchemeAccount = self.old_apps.get_model("schemes", "SchemeAccount")
        SchemePlan = self.old_apps.get_model("schemes", "SchemePlan")
        Contribution = self.old_apps.get_model("schemes", "Contribution")
        PaymentWebhookEvent = self.old_apps.get_model(
            "schemes", "PaymentWebhookEvent"
        )

        user = User.objects.create(
            username="mode-migration@example.com",
            email="mode-migration@example.com",
            password="!",
            role="CUSTOMER",
        )
        customer = Customer.objects.create(
            user=user,
            customer_number="MODE-MIG",
            full_name="Mode Migration",
            mobile_number="9000000888",
            email=user.email,
        )
        plan = SchemePlan.objects.create(
            name="Mode migration plan",
            code="MODE-MIG",
            amount_rule="VARIABLE",
            frequency_rule="FLEXIBLE",
            minimum_contribution=Decimal("1000.00"),
            maximum_contribution=Decimal("100000.00"),
        )
        account = SchemeAccount.objects.create(
            scheme_number="JSK-MODE-MIG",
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
        contribution = Contribution.objects.create(
            scheme_account=account,
            amount=Decimal("5000.00"),
            contribution_period=date(2026, 8, 1),
            frequency_rule_snapshot="FLEXIBLE",
            status="PENDING",
            payment_gateway="razorpay",
            gateway_order_id="order_historical_test",
        )
        event = PaymentWebhookEvent.objects.create(
            gateway="razorpay",
            event_id="event_historical_test",
            event_type="payment.captured",
            payload_sha256="a" * 64,
            status="RECEIVED",
        )

        executor = MigrationExecutor(connection)
        targets = [self.migrate_to, self.accounts_target]
        executor.migrate(targets)
        new_apps = executor.loader.project_state(targets).apps

        NewContribution = new_apps.get_model("schemes", "Contribution")
        NewPaymentWebhookEvent = new_apps.get_model(
            "schemes", "PaymentWebhookEvent"
        )
        self.assertEqual(
            NewContribution.objects.get(pk=contribution.pk).gateway_mode, "test"
        )
        self.assertEqual(
            NewPaymentWebhookEvent.objects.get(pk=event.pk).gateway_mode, "test"
        )
