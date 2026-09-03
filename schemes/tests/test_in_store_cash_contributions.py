import csv
import io
import uuid
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from schemes.models import (
    AuditEvent,
    Contribution,
    InStoreCashContributionReversal,
    InStoreCashReceipt,
    MetalAllocation,
    PaymentChannel,
    SchemeAccount,
    SchemePlan,
    SchemeRate,
)
from schemes.selectors import (
    get_in_store_cash_daily_summary,
    get_metal_balance,
    get_scheme_statement,
)
from schemes.services import (
    add_calendar_months,
    complete_redemption,
    create_customer,
    enroll_customer,
    preview_in_store_cash_contribution,
    publish_scheme_rate,
    record_in_store_cash_contribution,
    reverse_in_store_cash_contribution,
)
from schemes.tests.grade_helpers import enrolment_grade_kwargs, metal_grade_for


@override_settings(
    DEBUG=False,
    PAYMENT_INITIATION_KILL_SWITCH=False,
    IN_STORE_CASH_CONTRIBUTIONS_ENABLED=True,
    IN_STORE_CASH_REVERSAL_HOURS=24,
)
class InStoreCashContributionTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(
            username="cash-owner@example.com",
            email="cash-owner@example.com",
            password="OwnerPass123!",
            role=user_model.Role.OWNER,
        )
        self.customer = create_customer(
            full_name="Cash Desk Customer",
            email="cash-customer@example.com",
            mobile_number="9000000101",
            password="CustomerPass123!",
        )
        self.plan = SchemePlan.objects.create(
            name="Cash desk metal plan",
            code="CASH-DESK-METAL",
            amount_rule=SchemePlan.AmountRule.VARIABLE,
            frequency_rule=SchemePlan.FrequencyRule.FLEXIBLE,
            minimum_contribution=Decimal("100.00"),
            maximum_contribution=Decimal("10000.00"),
            allow_contributions_after_eligibility=True,
        )
        self.account = enroll_customer(
            customer=self.customer,
            plan=self.plan,
            **enrolment_grade_kwargs(self.plan, SchemeAccount.SavingsMode.GOLD),
            start_date=add_calendar_months(timezone.localdate(), -12),
            agreed_months=12,
            performed_by=self.owner,
            reason="Set up in-store cash test account.",
        )
        self.rate = publish_scheme_rate(
            metal_grade=metal_grade_for(SchemeRate.Metal.GOLD),
            rate_per_gram=Decimal("10000.0000"),
            published_by=self.owner,
            notes="In-store cash test rate.",
        )

    def record_cash(self, **overrides):
        preview = preview_in_store_cash_contribution(
            scheme_account=self.account,
            amount=overrides.get("amount", Decimal("500.00")),
        )
        values = {
            "scheme_account": self.account,
            "amount": Decimal("500.00"),
            "expected_scheme_rate_id": preview.scheme_rate.pk,
            "received_by": self.owner,
            "idempotency_key": uuid.uuid4(),
            "paper_receipt_number": "BOOK-101",
            "notes": "Counted at cash desk.",
            "audit_reason": "Cash physically received at showroom.",
        }
        values.update(overrides)
        return record_in_store_cash_contribution(**values)

    def test_records_cash_then_allocates_locked_grade(self):
        contribution = self.record_cash()

        receipt = InStoreCashReceipt.objects.get(contribution=contribution)
        allocation = MetalAllocation.objects.get(contribution=contribution)
        self.assertEqual(contribution.status, Contribution.Status.PAID)
        self.assertEqual(contribution.payment_channel, PaymentChannel.IN_STORE_CASH)
        self.assertEqual(contribution.payment_gateway, "in_store_cash")
        self.assertEqual(contribution.gateway_reference, receipt.receipt_reference)
        self.assertEqual(receipt.paper_receipt_number, "BOOK-101")
        self.assertEqual(receipt.received_by, self.owner)
        self.assertEqual(contribution.scheme_rate, self.rate)
        self.assertEqual(allocation.metal_grade, self.account.metal_grade)
        self.assertEqual(allocation.quantity, Decimal("0.050000"))
        self.assertEqual(get_metal_balance(self.account), Decimal("0.050000"))
        self.assertTrue(
            AuditEvent.objects.filter(
                action=AuditEvent.Action.IN_STORE_CASH_RECEIPT,
                contribution=contribution,
                actor=self.owner,
            ).exists()
        )

    def test_submission_token_is_idempotent_and_cannot_be_reused_differently(self):
        token = uuid.uuid4()
        first = self.record_cash(idempotency_key=token)
        second = self.record_cash(idempotency_key=token)

        self.assertEqual(first.pk, second.pk)
        self.assertEqual(InStoreCashReceipt.objects.count(), 1)
        self.assertEqual(MetalAllocation.objects.count(), 1)
        with self.assertRaisesMessage(ValidationError, "submission token"):
            self.record_cash(idempotency_key=token, amount=Decimal("600.00"))

    def test_changed_rate_requires_a_new_preview(self):
        preview = preview_in_store_cash_contribution(
            scheme_account=self.account,
            amount=Decimal("500.00"),
        )
        publish_scheme_rate(
            metal_grade=self.account.metal_grade,
            rate_per_gram=Decimal("11000.0000"),
            published_by=self.owner,
        )

        with self.assertRaisesMessage(ValidationError, "changed after preview"):
            record_in_store_cash_contribution(
                scheme_account=self.account,
                amount=Decimal("500.00"),
                expected_scheme_rate_id=preview.scheme_rate.pk,
                received_by=self.owner,
                idempotency_key=uuid.uuid4(),
            )

        self.assertFalse(InStoreCashReceipt.objects.exists())

    def test_pending_razorpay_order_blocks_cash_recording(self):
        Contribution.objects.create(
            scheme_account=self.account,
            amount=Decimal("500.00"),
            contribution_period=timezone.localdate().replace(day=1),
            frequency_rule_snapshot=SchemePlan.FrequencyRule.FLEXIBLE,
            status=Contribution.Status.PENDING,
            payment_gateway="razorpay",
            gateway_mode="live",
            gateway_order_id="order_cash_conflict",
            checkout_expires_at=timezone.now() + timedelta(minutes=10),
            scheme_rate=self.rate,
            rate_locked_at=timezone.now(),
        )

        with self.assertRaisesMessage(ValidationError, "pending Razorpay order"):
            self.record_cash()

        self.assertFalse(InStoreCashReceipt.objects.exists())

    @override_settings(PAYMENT_INITIATION_KILL_SWITCH=True)
    def test_payment_pause_blocks_cash_recording(self):
        with self.assertRaisesMessage(ValidationError, "temporarily paused"):
            preview_in_store_cash_contribution(
                scheme_account=self.account,
                amount=Decimal("500.00"),
            )

    def test_reversal_is_append_only_and_removes_active_entitlement(self):
        contribution = self.record_cash()
        original = {
            "amount": contribution.amount,
            "rate": contribution.scheme_rate_id,
            "reference": contribution.gateway_reference,
            "quantity": contribution.metal_allocation.quantity,
        }

        reversal = reverse_in_store_cash_contribution(
            contribution=contribution,
            processed_by=self.owner,
            reason_code=InStoreCashContributionReversal.ReasonCode.WRONG_AMOUNT,
            reason="Cash was counted correctly but the entered amount was wrong.",
        )

        contribution.refresh_from_db()
        self.assertEqual(contribution.status, Contribution.Status.REVERSED)
        self.assertEqual(contribution.amount, original["amount"])
        self.assertEqual(contribution.scheme_rate_id, original["rate"])
        self.assertEqual(contribution.gateway_reference, original["reference"])
        self.assertEqual(contribution.metal_allocation.quantity, original["quantity"])
        self.assertEqual(get_metal_balance(self.account), Decimal("0.000000"))
        self.assertEqual(reversal.processed_by, self.owner)
        self.assertTrue(
            AuditEvent.objects.filter(
                action=AuditEvent.Action.IN_STORE_CASH_REVERSAL,
                contribution=contribution,
            ).exists()
        )
        summary = get_in_store_cash_daily_summary()
        self.assertEqual(summary.received_amount, Decimal("500.00"))
        self.assertEqual(summary.reversed_amount, Decimal("500.00"))
        self.assertEqual(summary.net_amount, Decimal("0.00"))
        statement = get_scheme_statement(self.account)
        self.assertEqual(statement.remaining_entitlement, Decimal("0.000000"))
        self.assertEqual(
            [entry.description for entry in statement.entries],
            [
                f"{self.account.entitlement_name} contribution allocated",
                "In-store cash contribution correction",
            ],
        )
        self.client.force_login(self.customer.user)
        response = self.client.get(
            reverse("schemes:contribution_receipt", args=[contribution.pk])
        )
        self.assertContains(response, "Reversed financial record")
        self.assertContains(response, reversal.reversal_number)

    def test_reversal_releases_once_per_month_slot_for_new_receipt(self):
        monthly_plan = SchemePlan.objects.create(
            name="Monthly cash desk plan",
            code="MONTHLY-CASH-DESK",
            amount_rule=SchemePlan.AmountRule.FIXED,
            frequency_rule=SchemePlan.FrequencyRule.ONCE_PER_MONTH,
            fixed_contribution_amount=Decimal("500.00"),
            minimum_contribution=Decimal("500.00"),
            maximum_contribution=Decimal("500.00"),
            allow_contributions_after_eligibility=True,
        )
        monthly_account = enroll_customer(
            customer=self.customer,
            plan=monthly_plan,
            **enrolment_grade_kwargs(
                monthly_plan,
                SchemeAccount.SavingsMode.GOLD,
            ),
            start_date=add_calendar_months(timezone.localdate(), -12),
            agreed_months=12,
            performed_by=self.owner,
            reason="Set up monthly correction test account.",
        )
        preview = preview_in_store_cash_contribution(
            scheme_account=monthly_account,
            amount=Decimal("500.00"),
        )
        first = record_in_store_cash_contribution(
            scheme_account=monthly_account,
            amount=Decimal("500.00"),
            expected_scheme_rate_id=preview.scheme_rate.pk,
            received_by=self.owner,
            idempotency_key=uuid.uuid4(),
            paper_receipt_number="MONTHLY-WRONG",
        )
        reverse_in_store_cash_contribution(
            contribution=first,
            processed_by=self.owner,
            reason_code=InStoreCashContributionReversal.ReasonCode.WRONG_ACCOUNT,
            reason="Receipt was assigned to the wrong scheme account.",
        )

        replacement_preview = preview_in_store_cash_contribution(
            scheme_account=monthly_account,
            amount=Decimal("500.00"),
        )
        replacement = record_in_store_cash_contribution(
            scheme_account=monthly_account,
            amount=Decimal("500.00"),
            expected_scheme_rate_id=replacement_preview.scheme_rate.pk,
            received_by=self.owner,
            idempotency_key=uuid.uuid4(),
            paper_receipt_number="MONTHLY-CORRECT",
        )

        first.refresh_from_db()
        self.assertEqual(first.status, Contribution.Status.REVERSED)
        self.assertEqual(replacement.status, Contribution.Status.PAID)
        self.assertEqual(get_metal_balance(monthly_account), Decimal("0.050000"))

    def test_reversal_window_and_downstream_redemption_are_enforced(self):
        old_contribution = self.record_cash(paper_receipt_number="BOOK-OLD")
        Contribution.objects.filter(pk=old_contribution.pk).update(
            paid_at=timezone.now() - timedelta(hours=25)
        )
        old_contribution.refresh_from_db()
        with self.assertRaisesMessage(ValidationError, "window has closed"):
            reverse_in_store_cash_contribution(
                contribution=old_contribution,
                processed_by=self.owner,
                reason_code=InStoreCashContributionReversal.ReasonCode.WRONG_AMOUNT,
                reason="Old data-entry error.",
            )

        current = self.record_cash(paper_receipt_number="BOOK-NEW")
        complete_redemption(
            scheme_account=self.account,
            settlement_type="METAL",
            amount=current.metal_allocation.quantity,
            processed_by=self.owner,
            idempotency_key=uuid.uuid4(),
        )
        with self.assertRaisesMessage(ValidationError, "downstream redemption"):
            reverse_in_store_cash_contribution(
                contribution=current,
                processed_by=self.owner,
                reason_code=InStoreCashContributionReversal.ReasonCode.WRONG_AMOUNT,
                reason="Attempt after settlement.",
            )

    def test_two_step_owner_view_and_customer_receipt(self):
        token = uuid.uuid4()
        url = reverse(
            "schemes:in_store_cash_contribution",
            args=[self.account.scheme_number],
        )
        payload = {
            "amount": "500.00",
            "idempotency_key": str(token),
            "paper_receipt_number": "BOOK-VIEW",
            "notes": "View flow.",
            "audit_reason": "Cash physically received at showroom.",
            "action": "preview",
        }
        self.client.force_login(self.owner)
        preview = self.client.post(url, payload)
        self.assertContains(preview, "Confirm receipt preview")
        self.assertFalse(InStoreCashReceipt.objects.exists())

        payload.update(
            {
                "action": "confirm",
                "expected_scheme_rate_id": str(self.rate.pk),
                "confirm_cash_received": "on",
            }
        )
        confirmed = self.client.post(url, payload, follow=True)
        contribution = Contribution.objects.get(payment_gateway="in_store_cash")
        self.assertContains(confirmed, "In-store cash")
        self.assertContains(confirmed, "BOOK-VIEW")

        self.client.force_login(self.customer.user)
        receipt = self.client.get(
            reverse("schemes:contribution_receipt", args=[contribution.pk])
        )
        self.assertContains(receipt, "In-store cash")
        self.assertContains(receipt, "BOOK-VIEW")

    def test_only_owner_can_use_cash_desk_and_flag_defaults_closed(self):
        url = reverse(
            "schemes:in_store_cash_contribution",
            args=[self.account.scheme_number],
        )
        self.client.force_login(self.customer.user)
        self.assertEqual(self.client.get(url).status_code, 403)

        self.client.force_login(self.owner)
        with override_settings(IN_STORE_CASH_CONTRIBUTIONS_ENABLED=False):
            self.assertEqual(self.client.get(url).status_code, 404)

    def test_integrity_check_is_non_mutating_and_reports_no_secrets(self):
        self.record_cash()
        output = io.StringIO()

        call_command("check_in_store_cash_contributions", stdout=output)

        value = output.getvalue()
        self.assertIn("in_store_cash_check status=ok", value)
        self.assertIn("cash_contributions_missing_receipt=0", value)
        self.assertIn("today_received=500.00", value)

    def test_owner_csv_exposes_cash_receipt_and_reversal_metadata(self):
        contribution = self.record_cash()
        reversal = reverse_in_store_cash_contribution(
            contribution=contribution,
            processed_by=self.owner,
            reason_code=InStoreCashContributionReversal.ReasonCode.DUPLICATE_ENTRY,
            reason="Duplicate paper entry.",
        )
        self.client.force_login(self.owner)

        response = self.client.get(reverse("schemes:contribution_export"))
        row = list(
            csv.DictReader(io.StringIO(response.content.decode("utf-8")))
        )[0]

        self.assertEqual(row["payment_channel"], "IN_STORE_CASH")
        self.assertEqual(row["paper_receipt_number"], "BOOK-101")
        self.assertEqual(row["cash_reversal_number"], reversal.reversal_number)
        self.assertEqual(row["cash_reversal_reason_code"], "DUPLICATE_ENTRY")
