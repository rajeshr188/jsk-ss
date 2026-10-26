import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from io import StringIO
from threading import Barrier
from types import SimpleNamespace

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, close_old_connections, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import SimpleTestCase, TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from schemes.closures import _account
from schemes.inr_principal import calculate_inr_final_settlement, record_inr_principal, record_inr_cash_correction
from schemes.inr_selectors import get_inr_principal_summary
from schemes.models import (Contribution, InrPrincipalReceipt, InrPrincipalCorrection, InStoreCashReceipt,
    InStoreCashContributionReversal, MetalAllocation, PaymentWebhookEvent, SchemeAccount,
    SchemePlan, SchemePlanRevision, Redemption)
from schemes.plan_configuration import configuration_evidence, create_configuration_version
from schemes.selectors import (get_cash_balance, get_metal_balance, get_outstanding_entitlement,
    get_owner_liability_summary, get_scheme_statement)
from schemes.services import (validate_contribution_allowed, confirm_contribution, enroll_customer,
    validate_redemption_amount, reverse_in_store_cash_contribution)
from schemes.tests.test_audit_exceptions import make_owner, make_customer, make_plan
from schemes.tests.test_independent_policy_fields import independent_values


def future_contract(owner, customer):
    """Synthetic future workflow state, NOT a test-only production enrolment bypass.

    Schema-2 enrolment/model-save intentionally stays blocked. Populate only the
    disposable test DB to exercise ledger services before the upstream integration.
    """
    config = create_configuration_version(values=independent_values(accumulation="INR_PURCHASE_CREDIT",
        eligibility_policy="CALENDAR", duration_months=12), actor=owner, reason="Synthetic contract")
    identifier = uuid.uuid4().hex[:12]
    plan = SchemePlan(name="INR preparation", code=identifier, configuration=config, active=False,
        publicly_listed=False, amount_rule="VARIABLE", frequency_rule="FLEXIBLE", minimum_contribution=Decimal("100"))
    SchemePlan.objects.bulk_create([plan])
    revision = SchemePlanRevision.objects.create(plan=plan, number=1, actor=owner, actor_label="Owner",
        reason="Synthetic contract", terms=dict(configuration=configuration_evidence(config), metal_grades=[],
                                              name=plan.name, code=plan.code))
    account = SchemeAccount(customer=customer, scheme_number=identifier, plan=plan, plan_revision=revision,
        plan_name_snapshot=plan.name, plan_code_snapshot=plan.code, configuration_snapshot=config,
        agreement_schema_version=2, eligibility_policy_snapshot="DURATION",
        start_date=date(2026, 1, 1), eligible_from=date(2027, 1, 1), agreed_months=12,
        savings_mode="INR_CREDIT", amount_rule_snapshot="VARIABLE", frequency_rule_snapshot="FLEXIBLE",
        minimum_amount_snapshot=Decimal("100"), maximum_amount_snapshot=Decimal("10000"))
    SchemeAccount.objects.bulk_create([account])
    return account


def cash_source(account, owner, amount=Decimal("1000.00")):
    now = timezone.now()
    reference = "CASH-" + uuid.uuid4().hex[:20]
    contribution = Contribution.objects.create(scheme_account=account, amount=amount,
        contribution_period=now.date().replace(day=1), frequency_rule_snapshot="FLEXIBLE", status="PAID",
        payment_gateway="in_store_cash", gateway_reference=reference, paid_at=now)
    receipt = InStoreCashReceipt.objects.create(contribution=contribution, receipt_reference=reference,
        received_by=owner, received_by_label="Owner", received_at=now)
    return contribution, receipt


def online_source(account, amount=Decimal("500.00"), mode="live"):
    now = timezone.now()
    contribution = Contribution.objects.create(scheme_account=account, amount=amount,
        contribution_period=now.date().replace(day=1), frequency_rule_snapshot="FLEXIBLE", status="PAID",
        payment_gateway="razorpay", gateway_mode=mode, gateway_order_id="order_" + uuid.uuid4().hex,
        gateway_reference="pay_" + uuid.uuid4().hex, paid_at=now)
    event = PaymentWebhookEvent.objects.create(contribution=contribution, gateway="razorpay", gateway_mode=mode,
        event_id=uuid.uuid4().hex, event_type="payment.captured", payload_sha256="a" * 64, status="PROCESSED",
        processed_at=now, gateway_reference=contribution.gateway_reference, gateway_order_id=contribution.gateway_order_id)
    return contribution, event


def record(owner, contribution, cash=None, event=None, key=None, **kwargs):
    return record_inr_principal(contribution_id=contribution.pk, actor=owner, reason="Verified source bookkeeping",
        idempotency_key=key or uuid.uuid4(), cash_receipt_id=cash.pk if cash else None,
        webhook_event_id=event.pk if event else None, **kwargs)


def cash_reversal(contribution, owner):
    Contribution.objects.filter(pk=contribution.pk).update(status="REVERSED")
    return InStoreCashContributionReversal.objects.create(contribution=contribution,
        reversal_number="REV-" + uuid.uuid4().hex[:20], reason_code="WRONG_AMOUNT", reason="Source correction",
        processed_by=owner, processed_by_label="Owner")


class InrPrincipalTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = make_owner()
        cls.customer = make_customer()
        cls.account = future_contract(cls.owner, cls.customer)

    def test_cash_and_live_credit_are_separate_from_metal_cash_bonus_and_test(self):
        cash, proof = cash_source(self.account, self.owner)
        online, event = online_source(self.account)
        record(self.owner, cash, cash=proof)
        record(self.owner, online, event=event)
        test, test_event = online_source(self.account, mode="test")
        with self.assertRaises(ValidationError):
            record(self.owner, test, event=test_event)
        summary = get_inr_principal_summary(self.account)
        self.assertEqual(summary.principal_recorded, Decimal("1500.00"))
        self.assertFalse(summary.needs_review)
        self.assertEqual(get_cash_balance(self.account), 0)
        self.assertEqual(get_metal_balance(self.account), 0)
        self.assertEqual(get_outstanding_entitlement(self.account), Decimal("1500.00"))
        liabilities = get_owner_liability_summary()
        self.assertEqual(liabilities.inr_purchase_principal, Decimal("1500.00"))
        self.assertEqual(liabilities.cash_principal, 0)
        self.assertEqual(liabilities.cash_earned_bonus, 0)
        self.assertEqual(MetalAllocation.objects.count(), 0)
        self.assertEqual(Redemption.objects.count(), 0)

    def test_record_does_not_change_payment_or_agreement(self):
        contribution, cash = cash_source(self.account, self.owner)
        before_payment = Contribution.objects.values().get(pk=contribution.pk)
        before_account = SchemeAccount.objects.values().get(pk=self.account.pk)
        record(self.owner, contribution, cash=cash)
        self.assertEqual(Contribution.objects.values().get(pk=contribution.pk), before_payment)
        self.assertEqual(SchemeAccount.objects.values().get(pk=self.account.pk), before_account)

    def test_idempotency_same_facts_and_duplicate_source(self):
        contribution, cash = cash_source(self.account, self.owner)
        key = uuid.uuid4()
        receipt = record(self.owner, contribution, cash=cash, key=key)
        self.assertEqual(record(self.owner, contribution, cash=cash, key=key).pk, receipt.pk)
        with self.assertRaises(ValidationError):
            record(self.owner, contribution, cash=cash)
        other, other_cash = cash_source(self.account, self.owner)
        with self.assertRaises(ValidationError):
            record(self.owner, other, cash=other_cash, key=key)
        self.assertEqual(InrPrincipalReceipt.objects.count(), 1)

    def test_owner_authority_reloaded_and_invalid_identifiers(self):
        source, cash = cash_source(self.account, self.owner)
        with self.assertRaises(ValidationError):
            record(self.customer.user, source, cash=cash)
        type(self.owner).objects.filter(pk=self.owner.pk).update(is_active=False)
        with self.assertRaises(ValidationError):
            record(self.owner, source, cash=cash)
        type(self.owner).objects.filter(pk=self.owner.pk).update(is_active=True)
        with self.assertRaises(ValidationError):
            record(self.owner, source, cash=cash, key="invalid")
        self.assertEqual(InrPrincipalReceipt.objects.count(), 0)

    def test_unverified_and_mismatched_live_evidence_rejected(self):
        source, event = online_source(self.account)
        for field, bad in (("status", "FAILED"), ("event_type", "payment.authorized"),
                           ("gateway_mode", "test"), ("gateway_reference", "wrong"),
                           ("gateway_order_id", "wrong"), ("payload_sha256", "x" * 64), ("processed_at", None)):
            old = getattr(event, field)
            PaymentWebhookEvent.objects.filter(pk=event.pk).update(**{field: bad})
            with self.subTest(field=field), self.assertRaises(ValidationError):
                record(self.owner, source, event=event)
            PaymentWebhookEvent.objects.filter(pk=event.pk).update(**{field: old})
        with self.assertRaises(ValidationError):
            record(self.owner, source)
        Contribution.objects.filter(pk=source.pk).update(status="PENDING", paid_at=None, checkout_expires_at=timezone.now())
        with self.assertRaises(ValidationError):
            record(self.owner, source, event=event)

    def test_source_requires_same_account_and_cash_evidence(self):
        source, cash = cash_source(self.account, self.owner)
        other, other_cash = cash_source(self.account, self.owner)
        with self.assertRaises(ValidationError):
            record(self.owner, source, cash=other_cash)
        receipt = record(self.owner, source, cash=cash)
        other_account = future_contract(self.owner, self.customer)
        Contribution.objects.filter(pk=source.pk).update(scheme_account=other_account)
        summary = get_inr_principal_summary(self.account)
        self.assertEqual(summary.principal_recorded, receipt.amount)
        self.assertEqual(summary.source_errors, 1)
        self.assertEqual(get_inr_principal_summary(other_account).unrecorded_sources, 1)

    def test_correction_requires_actual_full_source_reversal_and_replays(self):
        source, cash = cash_source(self.account, self.owner)
        receipt = record(self.owner, source, cash=cash)
        reversal = cash_reversal(source, self.owner)
        summary = get_inr_principal_summary(self.account)
        self.assertEqual(summary.principal_recorded, Decimal("1000"))
        self.assertTrue(summary.needs_review)
        key = uuid.uuid4()
        args = dict(receipt_id=receipt.pk, cash_reversal_id=reversal.pk, actor=self.owner,
                    reason="Follow confirmed cash correction", idempotency_key=key)
        correction = record_inr_cash_correction(**args)
        self.assertEqual(record_inr_cash_correction(**args).pk, correction.pk)
        self.assertEqual(get_inr_principal_summary(self.account).principal_recorded, 0)
        self.assertFalse(get_inr_principal_summary(self.account).needs_review)
        with self.assertRaises(ValidationError):
            record_inr_cash_correction(**{**args, "idempotency_key": uuid.uuid4()})
        with self.assertRaises(ValidationError):
            record_inr_cash_correction(**{**args, "reason": "Different"})
        # Source drift after correction cannot silently rewrite the retained ledger.
        Contribution.objects.filter(pk=source.pk).update(status="PAID")
        summary = get_inr_principal_summary(self.account)
        self.assertEqual(summary.principal_recorded, 0)
        self.assertTrue(summary.needs_review)

    def test_correction_cannot_clear_online_money_or_closed_agreement(self):
        online, event = online_source(self.account)
        online_receipt = record(self.owner, online, event=event)
        source, cash = cash_source(self.account, self.owner)
        receipt = record(self.owner, source, cash=cash)
        reversal = cash_reversal(source, self.owner)
        args = dict(cash_reversal_id=reversal.pk, actor=self.owner, reason="Invalid", idempotency_key=uuid.uuid4())
        with self.assertRaises(ValidationError):
            record_inr_cash_correction(receipt_id=online_receipt.pk, **args)
        SchemeAccount.objects.filter(pk=self.account.pk).update(status="CLOSURE_PENDING")
        with self.assertRaises(ValidationError):
            record_inr_cash_correction(receipt_id=receipt.pk, **args)
        self.assertEqual(InrPrincipalCorrection.objects.count(), 0)

    def test_unrecorded_or_mutated_sources_require_reconciliation(self):
        source, cash = cash_source(self.account, self.owner)
        self.assertEqual(get_inr_principal_summary(self.account).unrecorded_sources, 1)
        with self.assertRaises(ValidationError):
            get_owner_liability_summary()
        receipt = record(self.owner, source, cash=cash)
        Contribution.objects.filter(pk=source.pk).update(amount=Decimal("2000"))
        summary = get_inr_principal_summary(self.account)
        self.assertEqual(summary.principal_recorded, receipt.amount)
        self.assertEqual(summary.source_errors, 1)
        with self.assertRaises(ValidationError):
            get_outstanding_entitlement(self.account)

    def test_contract_tampering_legacy_cash_and_metal_are_not_inr(self):
        source, cash = cash_source(self.account, self.owner)
        revision = self.account.plan_revision
        SchemePlanRevision.objects.filter(pk=revision.pk).update(terms={})
        with self.assertRaises(ValidationError):
            record(self.owner, source, cash=cash)
        SchemePlanRevision.objects.filter(pk=revision.pk).update(terms=revision.terms)
        for mode in ("CASH", "GOLD", "SILVER"):
            candidate = SchemeAccount.objects.get(pk=self.account.pk)
            candidate.savings_mode = mode
            with self.subTest(mode=mode), self.assertRaises(ValidationError):
                get_inr_principal_summary(candidate)

    def test_immutable_models_and_database_checks(self):
        source, cash = cash_source(self.account, self.owner)
        receipt = record(self.owner, source, cash=cash)
        for operation in (receipt.save, receipt.delete):
            with self.assertRaises(ValidationError):
                operation()
        for changes in ({"amount": 0}, {"cash_receipt": None}, {"source_reference": ""}):
            with self.subTest(changes=changes), self.assertRaises(IntegrityError), transaction.atomic():
                InrPrincipalReceipt.objects.filter(pk=receipt.pk).update(**changes)
        with self.assertRaises(IntegrityError), transaction.atomic(), connection.cursor() as cursor:
            cursor.execute("UPDATE schemes_inrprincipalreceipt SET amount = 'NaN'::numeric WHERE id = %s", [receipt.pk])
        with self.assertRaises(IntegrityError), transaction.atomic():
            SchemeAccount.objects.filter(pk=self.account.pk).update(configuration_snapshot=None)
        reversal = cash_reversal(source, self.owner)
        correction = record_inr_cash_correction(receipt_id=receipt.pk, cash_reversal_id=reversal.pk,
            actor=self.owner, reason="Correction", idempotency_key=uuid.uuid4())
        for operation in (correction.save, correction.delete):
            with self.assertRaises(ValidationError):
                operation()

    def test_read_only_check_detects_errors_without_printing_customer_data(self):
        output = StringIO()
        call_command("check_inr_principal", stdout=output)
        self.assertIn("workflow=not_activated", output.getvalue())
        cash_source(self.account, self.owner)
        output = StringIO()
        with self.assertRaises(CommandError):
            call_command("check_inr_principal", stdout=output)
        self.assertIn("unrecorded_sources=1", output.getvalue())
        self.assertNotIn(self.customer.email, output.getvalue())
        self.assertEqual(InrPrincipalReceipt.objects.count(), 0)

    def test_existing_entrypoints_remain_blocked_even_with_release_flag(self):
        from accounts.selectors import customer_account_deletion_disposition
        source, cash = cash_source(self.account, self.owner)
        with override_settings(CONFIGURED_PLANS_ENABLED=True, CASH_SCHEMES_ENABLED=True):
            for operation in (
                lambda: validate_contribution_allowed(self.account, Decimal("100")),
                lambda: confirm_contribution(contribution_id=source.pk, payment_gateway="in_store_cash",
                    gateway_reference=source.gateway_reference, verified=True),
                lambda: validate_redemption_amount(self.account, Decimal("100")),
                lambda: get_scheme_statement(self.account),
                lambda: _account(self.account.pk),
                lambda: reverse_in_store_cash_contribution(contribution=source, processed_by=self.owner,
                    reason_code="WRONG_AMOUNT", reason="Blocked until integrated"),
                lambda: Redemption(scheme_account=self.account).clean(),
                lambda: enroll_customer(customer=self.customer, plan=self.account.plan, savings_mode="INR_CREDIT"),
                self.account.save,
                lambda: customer_account_deletion_disposition(SimpleNamespace(customer=self.customer)),
            ):
                with self.subTest(operation=operation), self.assertRaises(ValidationError):
                    operation()
        self.assertEqual(InrPrincipalReceipt.objects.count(), 0)

    def test_late_verified_money_during_closure_remains_principal_not_settlement(self):
        SchemeAccount.objects.filter(pk=self.account.pk).update(status="CLOSURE_PENDING")
        source, cash = cash_source(self.account, self.owner)
        record(self.owner, source, cash=cash)
        self.account.refresh_from_db()
        self.assertEqual(self.account.status, "CLOSURE_PENDING")
        self.assertEqual(Redemption.objects.count(), 0)
        SchemeAccount.objects.filter(pk=self.account.pk).update(status="REDEEMED")
        other, proof = cash_source(self.account, self.owner)
        with self.assertRaises(ValidationError):
            record(self.owner, other, cash=proof)


class InrSettlementArithmeticTests(SimpleTestCase):
    def test_full_principal_split_below_equal_above_and_refund_only(self):
        for invoice, applied, refund, top_up in (("10000", "10000", "2000", "0"),
                ("12000", "12000", "0", "0"), ("14000", "12000", "0", "2000"), ("0", "0", "12000", "0")):
            split = calculate_inr_final_settlement(principal=Decimal("12000"), invoice_payable=Decimal(invoice))
            self.assertEqual((split.principal_to_invoice, split.principal_refund, split.separate_top_up),
                             tuple(map(Decimal, (applied, refund, top_up))))
            self.assertEqual(split.principal_to_invoice + split.principal_refund, split.principal)

    def test_no_rounding_float_negative_infinite_or_unused_settlement(self):
        for amount in (0, True, 100.0, "100", Decimal("NaN"), Decimal("Infinity"), Decimal("-1"),
                       Decimal("0"), Decimal("0.001"), Decimal("1000000000000")):
            with self.subTest(amount=amount), self.assertRaises(ValidationError):
                calculate_inr_final_settlement(principal=amount, invoice_payable=Decimal("100"))
        with self.assertRaises(ValidationError):
            calculate_inr_final_settlement(principal=Decimal("100"), invoice_payable=Decimal("1.001"))


class InrPrincipalConcurrencyAndMigrationTests(TransactionTestCase):
    def test_concurrent_same_source_creates_one_receipt(self):
        owner = make_owner()
        account = future_contract(owner, make_customer())
        source, cash = cash_source(account, owner)
        barrier, key = Barrier(2), uuid.uuid4()

        def worker():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return record(owner, source, cash=cash, key=key).pk
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(worker) for _ in range(2)]
            ids = [future.result(timeout=30) for future in futures]
        self.assertEqual(ids[0], ids[1])
        self.assertEqual(InrPrincipalReceipt.objects.count(), 1)

    def test_concurrent_correction_never_subtracts_principal_twice(self):
        owner = make_owner()
        account = future_contract(owner, make_customer())
        source, cash = cash_source(account, owner)
        receipt = record(owner, source, cash=cash)
        reversal = cash_reversal(source, owner)
        barrier, key = Barrier(2), uuid.uuid4()

        def worker():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return record_inr_cash_correction(receipt_id=receipt.pk, cash_reversal_id=reversal.pk,
                    actor=owner, reason="One confirmed correction", idempotency_key=key).pk
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(worker) for _ in range(2)]
            ids = [future.result(timeout=30) for future in futures]
        self.assertEqual(ids[0], ids[1])
        self.assertEqual(InrPrincipalCorrection.objects.count(), 1)
        self.assertEqual(get_inr_principal_summary(account).principal_recorded, Decimal("0.00"))

    def test_reverse_migration_refuses_to_drop_inr_contract_or_receipt(self):
        from importlib import import_module
        from django.apps import apps
        guard = import_module("schemes.migrations.0037_inr_principal_foundation").preserve_inr_history
        leaves = MigrationExecutor(connection).loader.graph.leaf_nodes()
        self.addCleanup(lambda: MigrationExecutor(connection).migrate(leaves))
        owner = make_owner()
        account = future_contract(owner, make_customer())
        with self.assertRaisesMessage(RuntimeError, "Cannot reverse 0040"):
            MigrationExecutor(connection).migrate([("schemes", "0036_independent_policy_fields")])
        with self.assertRaisesMessage(RuntimeError, "Cannot reverse 0037"):
            guard(apps, SimpleNamespace(connection=connection))
        # A later empty migration may already have reversed before 0037 refuses.
        MigrationExecutor(connection).migrate(leaves)
        source, cash = cash_source(account, owner)
        record(owner, source, cash=cash)
        with self.assertRaisesMessage(RuntimeError, "Cannot reverse 0040"):
            MigrationExecutor(connection).migrate([("schemes", "0036_independent_policy_fields")])
        with self.assertRaisesMessage(RuntimeError, "Cannot reverse 0037"):
            guard(apps, SimpleNamespace(connection=connection))
        # Empty later migrations (including 0044's nullable API-source field)
        # may have reversed before the retained-account guard refused. Restore
        # the leaf schema before using current-model selectors.
        MigrationExecutor(connection).migrate(leaves)
        self.assertEqual(get_inr_principal_summary(account).principal_recorded, Decimal("1000"))

    def test_migration_preserves_legacy_rows_and_does_not_invent_inr_credit(self):
        plan = make_plan()
        customer = make_customer()
        account = SchemeAccount.objects.create(customer=customer, scheme_number="OLD", plan=plan,
            savings_mode="CASH", start_date=date(2026, 1, 1), eligible_from=date(2027, 1, 1), agreed_months=12,
            amount_rule_snapshot="VARIABLE", frequency_rule_snapshot="FLEXIBLE", minimum_amount_snapshot=Decimal("100"))
        before = SchemeAccount.objects.values().get(pk=account.pk)
        leaves = MigrationExecutor(connection).loader.graph.leaf_nodes()
        self.addCleanup(lambda: MigrationExecutor(connection).migrate(leaves))
        MigrationExecutor(connection).migrate([("schemes", "0036_independent_policy_fields")])
        MigrationExecutor(connection).migrate(leaves)
        self.assertEqual(SchemeAccount.objects.values().get(pk=account.pk), before)
        self.assertEqual(InrPrincipalReceipt.objects.count(), 0)
        self.assertEqual(InrPrincipalCorrection.objects.count(), 0)
