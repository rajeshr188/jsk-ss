"""Upgrade the deployed checkout branch into the combined builder graph."""

import uuid
from datetime import date, timedelta
from decimal import Decimal

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone

from .migration_helpers import applied_migration_apps


class BuilderCheckoutMergeMigrationTests(TransactionTestCase):
    def setUp(self):
        super().setUp()
        executor = MigrationExecutor(connection)
        self.latest = executor.loader.graph.leaf_nodes()
        # Selecting one lateral branch does not unapply the other branch.
        # First return to their common ancestor, then install deployed checkout.
        executor.migrate([("schemes", "0020_scheme_enrolment_requests")])
        executor = MigrationExecutor(connection)
        targets = [node for node in self.latest if node[0] not in {"accounts", "pages", "schemes"}]
        targets += [
            ("accounts", "0008_customerinvitation_recovery_requested_at"),
            ("pages", "0002_publicfunneldailycount"),
            ("schemes", "0021_checkout_idempotency"),
        ]
        executor.migrate(targets)
        self.apps = applied_migration_apps()
        self.assertNotIn("plan_name_snapshot", {
            field.name for field in self.apps.get_model("schemes", "SchemeAccount")._meta.fields
        })

    def tearDown(self):
        MigrationExecutor(connection).migrate(self.latest)
        super().tearDown()

    def test_deployed_checkout_and_financial_evidence_survive_complete_builder_upgrade(self):
        model = lambda name: self.apps.get_model("schemes", name)
        user = self.apps.get_model("accounts", "CustomUser").objects.create(
            username="merge-fixture", email="merge@example.invalid", role="CUSTOMER",
        )
        customer = model("Customer").objects.create(
            user=user, customer_number="MERGE-CUSTOMER", full_name="Synthetic customer", email=user.email,
        )
        plan = model("SchemePlan").objects.create(
            name="Deployed legacy plan", code="MERGE-PLAN", minimum_contribution=Decimal("100"),
            amount_rule="VARIABLE", frequency_rule="FLEXIBLE",
        )
        grade, _ = model("MetalGrade").objects.get_or_create(
            code="GOLD_22K_916", defaults={"metal": "GOLD", "display_name": "22K Gold", "fineness": Decimal("0.916")},
        )
        account = model("SchemeAccount").objects.create(
            scheme_number="MERGE-ACCOUNT", customer=customer, plan=plan,
            start_date=date(2026, 1, 31), agreed_months=12, eligible_from=date(2027, 1, 31),
            savings_mode="GOLD", metal_grade=grade, amount_rule_snapshot="VARIABLE",
            frequency_rule_snapshot="FLEXIBLE", minimum_amount_snapshot=Decimal("100"),
        )
        now = timezone.now()
        rate = model("SchemeRate").objects.create(
            metal="GOLD", purity=Decimal("0.916"), metal_grade=grade, rate_per_gram=Decimal("10000"),
        )
        contribution = model("Contribution").objects.create(
            scheme_account=account, amount=Decimal("1000"), contribution_period=date(2026, 1, 1),
            frequency_rule_snapshot="FLEXIBLE", status="PAID", payment_gateway="razorpay",
            payment_channel="RAZORPAY", gateway_mode="live", gateway_reference="pay_mergefixture",
            gateway_order_id="order_mergefixture", paid_at=now, scheme_rate=rate,
            rate_locked_at=now, checkout_expires_at=now + timedelta(minutes=10),
        )
        model("MetalAllocation").objects.create(
            contribution=contribution, metal="GOLD", metal_grade=grade, scheme_rate=rate,
            quantity=Decimal("0.100000"),
        )
        model("RazorpayCheckoutSubmission").objects.create(key=uuid.uuid4(), contribution=contribution)
        model("RazorpayOrderRequest").objects.create(
            contribution=contribution, amount_subunits=100000, gateway_mode="live",
            scheme_rate=rate, checkout_expires_at=contribution.checkout_expires_at,
        )
        model("PaymentWebhookEvent").objects.create(
            gateway="razorpay", gateway_mode="live", event_id="evt_mergefixture",
            event_type="payment.captured", payload_sha256="a" * 64, status="PROCESSED",
            gateway_order_id=contribution.gateway_order_id, gateway_reference=contribution.gateway_reference,
            contribution=contribution, processed_at=now,
        )
        names = ("Customer", "SchemePlan", "SchemeAccount", "SchemeRate", "Contribution",
                 "MetalAllocation", "RazorpayCheckoutSubmission", "RazorpayOrderRequest", "PaymentWebhookEvent")
        before = {name: list(model(name).objects.order_by("pk").values()) for name in names}
        MigrationExecutor(connection).migrate(self.latest)
        current_apps = applied_migration_apps()
        for name, rows in before.items():
            with self.subTest(model=name):
                after = list(current_apps.get_model("schemes", name).objects.order_by("pk").values(*rows[0]))
                self.assertEqual(after, rows)
        current = current_apps.get_model("schemes", "SchemeAccount").objects.get(pk=account.pk)
        self.assertEqual(current.agreement_schema_version, 1)
        self.assertIsNone(current.configuration_snapshot_id)
        self.assertEqual(current.plan_name_snapshot, plan.name)
        self.assertIsNone(current.plan_revision_id)
        from schemes.models import SchemeAccount
        from schemes.selectors import get_outstanding_entitlement

        self.assertEqual(get_outstanding_entitlement(SchemeAccount.objects.get(pk=account.pk)), Decimal("0.100000"))
