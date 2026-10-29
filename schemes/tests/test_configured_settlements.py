"""Synthetic gated contracts; actual financial services, no external payments."""
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from io import StringIO
from threading import Barrier
from unittest.mock import patch

from django.core import signing
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import close_old_connections, connection
from django.db.migrations.executor import MigrationExecutor
from django.db.models.deletion import ProtectedError
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse

from schemes.closure_selectors import validate_closure_history
from schemes.models import ConfiguredSettlement, Contribution, MetalAllocation, Redemption, SchemeAccount
from schemes.selectors import get_metal_balance, get_customer_payment_availability
from schemes.services import reverse_redemption
from schemes.settlement_selectors import validate_configured_settlement
from schemes.settlements import preview_full_settlement, settle_configured_agreement, reverse_configured_settlement, SALT
from schemes.tests.test_scheme_closures import ClosureFixture
from schemes.tests import test_monthly_eligibility as monthly
from schemes.tests import test_instalment_payment_integration as integration
from schemes.tests import test_configured_agreements as calendar
from schemes.tests.test_instalment_payments import NOW


class SettlementFixture(ClosureFixture):
    instant = monthly.MonthlyEligibilityTests.instant
    pay_periods = monthly.MonthlyEligibilityTests.pay_periods
    callback = integration.InstalmentPaymentIntegrationTests.callback

    def accepted(self):
        return self.review(self.request_closure())

    def values(self, request, **changes):
        evidence, token = preview_full_settlement(request_id=request.pk, actor=self.owner)
        values = dict(request_id=request.pk, actor=self.owner, preview_token=token,
            invoice_reference="INV-001", authorization_reference="Signed exact quantity and delivery confirmation",
            reason="Full jewellery fulfilment", idempotency_key=uuid.uuid4())
        values.update(changes)
        return values

    def settle(self, request, **changes):
        return settle_configured_agreement(**self.values(request, **changes))

    def reversal_values(self, settlement, **changes):
        values = dict(settlement_id=settlement.pk, actor=self.owner, reason="Invoice corrected; entitlement restored",
            authorization_reference="CORRECTION-001", idempotency_key=uuid.uuid4(),
            expected_sequence=settlement.closure.events.count())
        values.update(changes)
        return values


@override_settings(IN_STORE_CASH_CONTRIBUTIONS_ENABLED=True, PAYMENT_GATEWAY="razorpay",
    RAZORPAY_MODE="live", RAZORPAY_KEY_ID="rzp_live_fixture", RAZORPAY_KEY_SECRET="fixture")
class ConfiguredSettlementTests(SettlementFixture, TestCase):
    def test_full_early_settlement_is_exact_and_append_only(self):
        payment = self.cash()
        original = list(Contribution.objects.values())
        request = self.accepted()
        redemption = self.settle(request)
        self.assertEqual(redemption.gold_quantity, Decimal("0.100000"))
        self.assertIsNone(redemption.cash_amount)
        self.assertEqual(redemption.configured_settlement.basis, "EARLY")
        self.assertEqual(redemption.metal_grade_id, self.grade.pk)
        self.assertEqual(get_metal_balance(self.account), 0)
        self.assertEqual(original, list(Contribution.objects.values()))
        self.account.refresh_from_db()
        request.refresh_from_db()
        self.assertEqual(self.account.status, "REDEEMED")
        self.assertEqual(request.status, "SETTLED")
        self.assertEqual(validate_closure_history(request), 3)
        self.assertTrue(self.account.customer.user.is_active)
        self.assertEqual(payment.metal_allocation.quantity, Decimal("0.100000"))
        for obj in (redemption, redemption.configured_settlement):
            for action in (obj.save, obj.delete):
                with self.assertRaises((ValidationError, ProtectedError)):
                    action()
        call_command("check_scheme_closures", stdout=StringIO())

    def test_real_live_capture_can_settle_after_closure(self):
        payment = self.online()
        request = self.accepted()
        with self.assertRaises(ValidationError):
            self.values(request)
        self.webhook(payment)
        redemption = self.settle(request)
        self.assertEqual(redemption.gold_quantity, Decimal("0.100000"))

    def test_monthly_count_waits_until_last_period_end(self):
        self.pay_periods(range(1, 13))
        request = self.accepted()
        boundary = self.instant(12, end=True)
        with patch("django.utils.timezone.now", return_value=boundary - timedelta(microseconds=1)):
            evidence, _ = preview_full_settlement(request_id=request.pk, actor=self.owner)
            self.assertEqual(evidence["basis"], "EARLY")
        with patch("django.utils.timezone.now", return_value=boundary):
            redemption = self.settle(request)
            self.assertEqual(redemption.configured_settlement.basis, "NORMAL")
            self.assertEqual(redemption.gold_quantity, Decimal("1.200000"))

    def test_date_without_completed_instalments_is_early_not_normal(self):
        self.cash()
        request = self.accepted()
        with patch("django.utils.timezone.now", return_value=self.instant(12, end=True)):
            self.assertEqual(self.settle(request).configured_settlement.basis, "EARLY")

    def test_reversal_restores_exact_balance_without_reopening_and_can_resettle(self):
        self.cash()
        request = self.accepted()
        redemption = self.settle(request)
        values = self.reversal_values(redemption.configured_settlement)
        reversal = reverse_configured_settlement(**values)
        self.assertEqual(reverse_configured_settlement(**values).pk, reversal.pk)
        self.account.refresh_from_db()
        request.refresh_from_db()
        self.assertEqual(self.account.status, "CLOSURE_PENDING")
        self.assertEqual(request.status, "ACCEPTED")
        self.assertEqual(get_metal_balance(self.account), Decimal("0.100000"))
        self.assertFalse(get_customer_payment_availability(self.account).allowed)
        for action in (self.cash, self.online):
            with self.assertRaises(ValidationError):
                action()
        second = self.settle(request, invoice_reference="INV-002")
        self.assertNotEqual(second.pk, redemption.pk)
        self.assertEqual(get_metal_balance(self.account), 0)
        request.refresh_from_db()
        self.assertEqual(validate_closure_history(request), 5)
        call_command("check_scheme_closures", stdout=StringIO())

    def test_legacy_reversal_service_cannot_reopen_configured_agreement(self):
        self.cash()
        redemption = self.settle(self.accepted())
        with self.assertRaises(ValidationError):
            reverse_redemption(redemption=redemption, processed_by=self.owner, reason="Wrong path")
        self.assertEqual(get_metal_balance(self.account), 0)

    def test_idempotent_replay_and_changed_payload(self):
        self.cash()
        request = self.accepted()
        values = self.values(request)
        first = settle_configured_agreement(**values)
        with patch("django.utils.timezone.now", return_value=NOW + timedelta(hours=1)):
            self.assertEqual(settle_configured_agreement(**values).pk, first.pk)
        with self.assertRaises(ValidationError):
            settle_configured_agreement(**(values | {"invoice_reference": "different"}))
        self.assertEqual(Redemption.objects.count(), 1)

    def test_stale_review_preview_cannot_settle(self):
        self.cash()
        request = self.accepted()
        values = self.values(request)
        self.review(request, action="NOTE", reason="New investigation evidence")
        with self.assertRaisesMessage(ValidationError, "changed"):
            settle_configured_agreement(**values)
        self.assertFalse(Redemption.objects.exists())

    def test_expired_tampered_and_wrong_actor_tokens(self):
        self.cash()
        request = self.accepted()
        values = self.values(request)
        with patch("django.core.signing.time.time", return_value=9999999999), self.assertRaises(ValidationError):
            settle_configured_agreement(**values)
        for token in ("invalid", signing.dumps([], salt=SALT), signing.dumps(dict(request=str(request.pk), actor=-1), salt=SALT)):
            with self.subTest(token=token), self.assertRaises(ValidationError):
                settle_configured_agreement(**(values | {"preview_token": token}))
        self.assertFalse(Redemption.objects.exists())

    def test_invoice_customer_confirmation_and_reason_required(self):
        self.cash()
        values = self.values(self.accepted())
        for field in ("invoice_reference", "authorization_reference", "reason"):
            with self.subTest(field=field), self.assertRaises(ValidationError):
                settle_configured_agreement(**(values | {field: " "}))
        self.assertFalse(Redemption.objects.exists())

    def test_zero_balance_uses_unused_cancellation_not_settlement(self):
        request = self.accepted()
        with self.assertRaisesMessage(ValidationError, "positive"):
            self.values(request)

    def test_pending_and_abandoned_provider_history_remains_blocked(self):
        payment = self.online()
        request = self.accepted()
        for state in ("PENDING", "FAILED", "ABANDONED"):
            Contribution.objects.filter(pk=payment.pk).update(status=state)
            with self.subTest(state=state), self.assertRaises(ValidationError):
                self.values(request)
        self.assertFalse(Redemption.objects.exists())

    def test_paid_unallocated_and_missing_capture_timing_block(self):
        payment = self.online()
        request = self.accepted()
        self.callback(payment)
        with self.assertRaises(ValidationError):
            self.values(request)
        Contribution.objects.filter(pk=payment.pk).update(status="PAID_UNALLOCATED")
        with self.assertRaises(ValidationError):
            self.values(request)

    def test_allocation_corruption_blocked(self):
        payment = self.cash()
        request = self.accepted()
        MetalAllocation.objects.filter(contribution=payment).update(quantity=Decimal("0.100001"))
        with self.assertRaises(ValidationError):
            self.values(request)

    def test_outage_hold_blocks_early_settlement(self):
        self.cash()
        with patch("django.utils.timezone.now", return_value=self.instant(2)):
            self.hold(number=2)
        with self.assertRaises(ValidationError):
            self.values(self.accepted())

    def test_customer_cannot_preview_settle_or_reverse(self):
        self.cash()
        request = self.accepted()
        with self.assertRaises(ValidationError):
            preview_full_settlement(request_id=request.pk, actor=self.account.customer.user)
        values = self.values(request)
        with self.assertRaises(ValidationError):
            settle_configured_agreement(**(values | {"actor": self.account.customer.user}))
        redemption = settle_configured_agreement(**values)
        with self.assertRaises(ValidationError):
            reverse_configured_settlement(**self.reversal_values(redemption.configured_settlement, actor=self.account.customer.user))

    def test_owner_page_confirmation_csrf_and_server_derived_quantity(self):
        self.cash()
        request = self.accepted()
        url = reverse("schemes:configured_settlement", args=[request.pk])
        self.client.force_login(self.account.customer.user)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_login(self.owner)
        response = self.client.get(url)
        self.assertContains(response, "0.100000")
        self.assertIn("no-store", response.headers["Cache-Control"])
        values = self.values(request)
        data = {key: value for key, value in values.items() if key not in ("actor", "request_id")}
        self.assertEqual(self.client.post(url, data).status_code, 200)
        self.assertFalse(Redemption.objects.exists())
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.owner)
        self.assertEqual(csrf.post(url, data | {"confirmed": True}).status_code, 403)
        response = self.client.post(url, data | {"confirmed": True, "gold_quantity": "0.001", "basis": "NORMAL"})
        self.assertEqual(response.status_code, 302)
        redemption = Redemption.objects.get()
        self.assertEqual(redemption.gold_quantity, Decimal("0.100000"))
        self.assertEqual(redemption.configured_settlement.basis, "EARLY")
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_integrity_check_detects_settlement_proof_tampering(self):
        self.cash()
        redemption = self.settle(self.accepted())
        ConfiguredSettlement.objects.filter(redemption=redemption).update(evidence_digest="invalid")
        with self.assertRaises(ValidationError):
            validate_configured_settlement(ConfiguredSettlement.objects.get())
        with self.assertRaises(CommandError):
            call_command("check_scheme_closures", stdout=StringIO())

    def test_direct_terminal_status_edit_is_rejected(self):
        for status in ("REDEEMED", "CLOSURE_PENDING"):
            self.account.status = status
            with self.assertRaises(ValidationError):
                self.account.save()
        self.account.refresh_from_db()
        self.assertEqual(self.account.status, "ACTIVE")

    def test_reversal_stale_and_duplicate_key_with_changed_evidence(self):
        self.cash()
        redemption = self.settle(self.accepted())
        values = self.reversal_values(redemption.configured_settlement)
        with self.assertRaises(ValidationError):
            reverse_configured_settlement(**(values | {"expected_sequence": 2}))
        reverse_configured_settlement(**values)
        with self.assertRaises(ValidationError):
            reverse_configured_settlement(**(values | {"reason": "different"}))
        self.assertEqual(get_metal_balance(self.account), Decimal("0.100000"))

    def test_cash_correction_invalidates_preview_and_preserves_zero_history(self):
        from schemes.services import reverse_in_store_cash_contribution
        payment = self.cash()
        values = self.values(self.accepted())
        reverse_in_store_cash_contribution(contribution=payment, processed_by=self.owner,
            reason_code="WRONG_AMOUNT", reason="Wrong receipt")
        with self.assertRaises(ValidationError):
            settle_configured_agreement(**values)
        self.assertFalse(Redemption.objects.exists())
        self.assertEqual(Contribution.objects.get().status, "REVERSED")

    def test_test_mode_money_is_never_delivered_as_real_metal(self):
        payment = self.online()
        self.webhook(payment)
        Contribution.objects.filter(pk=payment.pk).update(gateway_mode="test")
        with self.assertRaises(ValidationError):
            self.values(self.accepted())

    def test_reversal_legacy_route_redirects_to_controlled_workspace(self):
        self.cash()
        redemption = self.settle(self.accepted())
        self.client.force_login(self.owner)
        response = self.client.get(reverse("schemes:redemption_reverse", args=[redemption.redemption_number]))
        self.assertRedirects(response, reverse("schemes:configured_settlement", args=[redemption.configured_settlement.closure_id]))


@override_settings(IN_STORE_CASH_CONTRIBUTIONS_ENABLED=True)
class CalendarSettlementTests(SettlementFixture, TestCase):
    def setUp(self):
        calendar.ConfiguredAgreementTests.setUp(self)
        self.account = calendar.ConfiguredAgreementTests.account(self)
        del self.values  # The calendar fixture's configuration dictionary is not our helper.

    def test_calendar_requires_only_recorded_date_not_twelve_payments(self):
        from datetime import datetime, time
        from schemes.instalments import AGREEMENT_TIMEZONE
        self.cash()
        request = self.accepted()
        boundary = datetime.combine(self.account.eligible_from, time.min, AGREEMENT_TIMEZONE)
        with patch("django.utils.timezone.now", return_value=boundary):
            self.assertEqual(self.settle(request).configured_settlement.basis, "NORMAL")

    def test_six_decimal_remainder_is_fully_settled_not_rounded_to_three(self):
        from schemes.services import publish_scheme_rate
        self.rate = publish_scheme_rate(metal_grade=self.grade, rate_per_gram=Decimal("14667"), published_by=self.owner)
        self.cash()
        redemption = self.settle(self.accepted())
        self.assertEqual(redemption.gold_quantity, Decimal("0.068180"))
        self.assertEqual(get_metal_balance(self.account), 0)

    def test_silver_is_separate_from_gold_and_inr(self):
        from schemes.tests.grade_helpers import grade_for_mode
        from schemes.plan_configuration import create_configured_plan_draft
        from schemes.services import publish_scheme_rate
        self.grade = grade_for_mode(self.legacy, "SILVER")
        plan = create_configured_plan_draft(configuration_id=self.configuration.pk, name="Silver fixture", code="SILVER-FIXTURE",
            metal_grades=[self.grade], actor=self.owner, reason="Synthetic silver test")
        # New synthetic contract, not an alteration of an enrolled grade.
        self.account.pk = None
        self.account.scheme_number = "SYN-SILVER"
        self.account.savings_mode = "SILVER"
        self.account.metal_grade = self.grade
        self.account.plan = plan
        self.account.plan_revision = plan.revisions.first()
        self.account.plan_name_snapshot = plan.name
        self.account.plan_code_snapshot = plan.code
        self.account.full_clean()
        self.account.save()
        self.rate = publish_scheme_rate(metal_grade=self.grade, rate_per_gram=Decimal("123"), published_by=self.owner)
        self.cash()
        redemption = self.settle(self.accepted())
        self.assertEqual(redemption.silver_quantity, Decimal("8.130081"))
        self.assertIsNone(redemption.gold_quantity)
        self.assertIsNone(redemption.cash_amount)
        self.assertEqual(get_metal_balance(self.account), 0)


@override_settings(IN_STORE_CASH_CONTRIBUTIONS_ENABLED=True)
class ConfiguredSettlementRaceTests(SettlementFixture, TransactionTestCase):
    def setUp(self):
        MigrationExecutor(connection).migrate(MigrationExecutor(connection).loader.graph.leaf_nodes())
        super().setUp()

    def test_two_owners_submit_same_preview_only_one_full_settlement(self):
        self.cash()
        request = self.accepted()
        values = self.values(request)
        barrier = Barrier(2)
        def submit(key):
            close_old_connections()
            try:
                barrier.wait(timeout=30)
                try:
                    return settle_configured_agreement(**(values | {"idempotency_key": key})).pk
                except ValidationError:
                    return None
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(submit, [uuid.uuid4(), uuid.uuid4()]))
        self.assertEqual(sum(result is not None for result in results), 1)
        self.assertEqual(Redemption.objects.count(), 1)
        self.assertEqual(get_metal_balance(self.account), 0)

    def test_migration_preserves_existing_agreements_and_financial_sources(self):
        self.cash()
        before = (list(Contribution.objects.values()), list(MetalAllocation.objects.values()), self.account.status)
        executor = MigrationExecutor(connection)
        leaves = executor.loader.graph.leaf_nodes()
        try:
            executor.migrate([("schemes", "0032_unused_agreement_cancellation")])
            MigrationExecutor(connection).migrate(leaves)
            self.account.refresh_from_db()
            self.assertEqual(before, (list(Contribution.objects.values()), list(MetalAllocation.objects.values()), self.account.status))
            self.assertFalse(ConfiguredSettlement.objects.exists())
        finally:
            MigrationExecutor(connection).migrate(leaves)
