from datetime import date
from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone


class GradedMetalRateMigrationTests(TransactionTestCase):
    migrate_from = ("schemes", "0014_paymentwebhookevent_failure_code_and_more")
    migrate_to = ("schemes", "0016_graded_rate_precision_labels")
    restore_to = ("schemes", "0018_in_store_cash_contributions")
    accounts_target = ("accounts", "0003_customerinvitation_and_more")

    def setUp(self):
        super().setUp()
        executor = MigrationExecutor(connection)
        targets = [self.migrate_from, self.accounts_target]
        executor.migrate(targets)
        self.old_apps = executor.loader.project_state(targets).apps

    def tearDown(self):
        MigrationExecutor(connection).migrate(
            [self.restore_to, self.accounts_target]
        )
        super().tearDown()

    def test_preserves_historical_grade_and_enables_22k_for_new_enrolment(self):
        User = self.old_apps.get_model("accounts", "CustomUser")
        Customer = self.old_apps.get_model("schemes", "Customer")
        Contribution = self.old_apps.get_model("schemes", "Contribution")
        MetalAllocation = self.old_apps.get_model("schemes", "MetalAllocation")
        Redemption = self.old_apps.get_model("schemes", "Redemption")
        SchemeAccount = self.old_apps.get_model("schemes", "SchemeAccount")
        SchemePlan = self.old_apps.get_model("schemes", "SchemePlan")
        SchemeRate = self.old_apps.get_model("schemes", "SchemeRate")

        owner = User.objects.create(
            username="graded-migration-owner@example.com",
            email="graded-migration-owner@example.com",
            password="!",
            role="OWNER",
        )
        customer_user = User.objects.create(
            username="graded-migration-customer@example.com",
            email="graded-migration-customer@example.com",
            password="!",
            role="CUSTOMER",
        )
        customer = Customer.objects.create(
            user=customer_user,
            customer_number="GRADE-MIG",
            full_name="Grade Migration",
            mobile_number="9000000666",
            email=customer_user.email,
        )
        plan = SchemePlan.objects.create(
            name="Grade migration plan",
            code="GRADE-MIG",
            amount_rule="VARIABLE",
            frequency_rule="FLEXIBLE",
            minimum_contribution=Decimal("100.00"),
            maximum_contribution=Decimal("100000.00"),
        )
        now = timezone.now()
        records = {}
        for metal, purity, quantity in (
            ("GOLD", Decimal("0.9999"), Decimal("0.800000")),
            ("SILVER", Decimal("0.9990"), Decimal("50.000000")),
        ):
            account = SchemeAccount.objects.create(
                scheme_number=f"JSK-GRADE-{metal}",
                customer=customer,
                plan=plan,
                start_date=date(2026, 1, 1),
                agreed_months=12,
                eligible_from=date(2027, 1, 1),
                savings_mode=metal,
                amount_rule_snapshot="VARIABLE",
                frequency_rule_snapshot="FLEXIBLE",
                minimum_amount_snapshot=Decimal("100.00"),
                maximum_amount_snapshot=Decimal("100000.00"),
            )
            rate = SchemeRate.objects.create(
                metal=metal,
                rate_per_gram=Decimal("12500.0000"),
                purity=purity,
                effective_from=now,
                published_by=owner,
            )
            contribution = Contribution.objects.create(
                scheme_account=account,
                amount=Decimal("10000.00"),
                contribution_period=date(2026, 8, 1),
                frequency_rule_snapshot="FLEXIBLE",
                status="PAID",
                payment_gateway="mock",
                gateway_reference=f"grade-migration-{metal.lower()}",
                scheme_rate=rate,
                rate_locked_at=now,
                paid_at=now,
            )
            allocation = MetalAllocation.objects.create(
                contribution=contribution,
                scheme_rate=rate,
                metal=metal,
                quantity=quantity,
            )
            records[metal] = (account.pk, rate.pk, allocation.pk)

        redemption = Redemption.objects.create(
            redemption_number="RED-GRADE-MIG",
            scheme_account_id=records["GOLD"][0],
            settlement_type="METAL",
            gold_quantity=Decimal("0.100000"),
            processed_by=owner,
        )

        preflight_output = StringIO()
        call_command("check_graded_metal_rates", stdout=preflight_output)
        self.assertIn(
            "graded_metal_rate_preflight status=ready",
            preflight_output.getvalue(),
        )

        executor = MigrationExecutor(connection)
        targets = [self.migrate_to, self.accounts_target]
        executor.migrate(targets)
        new_apps = executor.loader.project_state(targets).apps
        MetalGrade = new_apps.get_model("schemes", "MetalGrade")
        NewAllocation = new_apps.get_model("schemes", "MetalAllocation")
        NewRedemption = new_apps.get_model("schemes", "Redemption")
        NewSchemeAccount = new_apps.get_model("schemes", "SchemeAccount")
        NewSchemeRate = new_apps.get_model("schemes", "SchemeRate")
        SchemePlanOffering = new_apps.get_model("schemes", "SchemePlanOffering")

        gold_22k = MetalGrade.objects.get(code="GOLD_22K_916")
        gold_24k = MetalGrade.objects.get(code="GOLD_24K_9999")
        silver_999 = MetalGrade.objects.get(code="SILVER_999")
        self.assertEqual(gold_22k.fineness, Decimal("0.916000"))
        self.assertEqual(gold_24k.fineness, Decimal("0.999900"))
        self.assertEqual(silver_999.fineness, Decimal("0.999000"))

        for metal, grade in (("GOLD", gold_24k), ("SILVER", silver_999)):
            account_pk, rate_pk, allocation_pk = records[metal]
            self.assertEqual(
                NewSchemeAccount.objects.get(pk=account_pk).metal_grade_id,
                grade.pk,
            )
            self.assertEqual(
                NewSchemeRate.objects.get(pk=rate_pk).metal_grade_id,
                grade.pk,
            )
            self.assertEqual(
                NewAllocation.objects.get(pk=allocation_pk).metal_grade_id,
                grade.pk,
            )
        self.assertEqual(
            NewRedemption.objects.get(pk=redemption.pk).metal_grade_id,
            gold_24k.pk,
        )

        offerings = {
            offering.metal_grade.code: offering.active
            for offering in SchemePlanOffering.objects.filter(plan_id=plan.pk)
        }
        self.assertEqual(
            offerings,
            {
                "GOLD_22K_916": True,
                "GOLD_24K_9999": False,
                "SILVER_999": True,
            },
        )
