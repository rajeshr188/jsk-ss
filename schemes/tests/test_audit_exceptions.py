import uuid
from datetime import date
from decimal import Decimal
from io import StringIO

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import CustomUser
from schemes.models import (
    AuditEvent,
    Contribution,
    PaymentWebhookEvent,
    Redemption,
    SchemeAccount,
    SchemePlan,
    SchemeRate,
)
from schemes.tests.grade_helpers import enrolment_grade_kwargs, metal_grade_for
from schemes.selectors import (
    get_cash_balance,
    get_financial_exception_counts,
    get_owner_exception_queue,
    get_owner_liability_summary,
)
from schemes.services import (
    add_calendar_months,
    complete_redemption,
    create_customer,
    enroll_customer,
    reverse_redemption,
    retry_metal_allocation,
    publish_scheme_rate,
)


def make_plan(code="AUDIT-PLAN"):
    return SchemePlan.objects.create(
        name="Audit Plan",
        code=code,
        minimum_months=12,
        default_months=12,
        amount_rule=SchemePlan.AmountRule.VARIABLE,
        frequency_rule=SchemePlan.FrequencyRule.FLEXIBLE,
        minimum_contribution=Decimal("100.00"),
        maximum_contribution=Decimal("10000.00"),
    )


def make_owner(email="owner-audit@example.com"):
    return CustomUser.objects.create_user(
        username=email,
        email=email,
        password="OwnerPass123!",
        role=CustomUser.Role.OWNER,
    )


def make_customer(email="customer-audit@example.com"):
    return create_customer(
        full_name="Audit Customer",
        email=email,
        mobile_number="9000000001",
        password="CustomerPass123!",
    )


def make_account(*, mode=SchemeAccount.SavingsMode.CASH, owner=None, plan=None):
    today = timezone.localdate()
    plan = plan or make_plan()
    return enroll_customer(
        customer=make_customer(),
        plan=plan,
        **enrolment_grade_kwargs(plan, mode),
        start_date=add_calendar_months(today, -12),
        agreed_months=12,
        performed_by=owner,
        reason="Customer accepted the scheme terms.",
    )


def make_paid_contribution(account, *, status=Contribution.Status.PAID):
    return Contribution.objects.create(
        scheme_account=account,
        amount=Decimal("100.00"),
        contribution_period=date.today().replace(day=1),
        frequency_rule_snapshot=SchemePlan.FrequencyRule.FLEXIBLE,
        status=status,
        payment_gateway="mock",
        gateway_reference=f"pay-{uuid.uuid4()}",
        paid_at=timezone.now(),
        allocation_error=("Unexpected allocation failure" if status == Contribution.Status.PAID_UNALLOCATED else ""),
        allocation_attempted_at=(timezone.now() if status == Contribution.Status.PAID_UNALLOCATED else None),
    )


@override_settings(DEBUG=True)
class AuditAndExceptionTests(TestCase):
    def test_enrolment_records_actor_timestamp_reason_and_snapshot(self):
        owner = make_owner()
        account = make_account(owner=owner)

        event = AuditEvent.objects.get(action=AuditEvent.Action.CUSTOMER_ENROLMENT)
        self.assertEqual(event.actor, owner)
        self.assertEqual(event.actor_label, owner.email)
        self.assertEqual(event.reason, "Customer accepted the scheme terms.")
        self.assertEqual(event.scheme_account, account)
        self.assertEqual(event.details["savings_mode"], SchemeAccount.SavingsMode.CASH)
        self.assertIsNotNone(event.occurred_at)

        event.reason = "Changed"
        with self.assertRaisesMessage(ValidationError, "immutable"):
            event.save()

    def test_audited_plan_edit_does_not_rewrite_enrolment_snapshot(self):
        owner = make_owner()
        plan = make_plan()
        account = make_account(owner=owner, plan=plan)
        original_minimum = account.minimum_amount_snapshot
        gold_grade = metal_grade_for(SchemeRate.Metal.GOLD)
        self.client.force_login(owner)

        response = self.client.post(
            reverse("schemes:plan_edit", args=[plan.pk]),
            {
                "name": plan.name,
                "code": plan.code,
                "description": "Revised for future enrolments",
                "minimum_months": 12,
                "default_months": 12,
                "amount_rule": SchemePlan.AmountRule.VARIABLE,
                "frequency_rule": SchemePlan.FrequencyRule.FLEXIBLE,
                "fixed_contribution_amount": "",
                "minimum_contribution": "250.00",
                "maximum_contribution": "10000.00",
                "cash_bonus_percentage": "0.00",
                "cash_bonus_minimum_months": 12,
                "active": "on",
                "publicly_listed": "on",
                "metal_grades": [gold_grade.pk],
                "audit_reason": "New terms apply to future enrolments only.",
            },
        )

        self.assertRedirects(response, reverse("schemes:plan_list"))
        account.refresh_from_db()
        self.assertEqual(account.minimum_amount_snapshot, original_minimum)
        event = AuditEvent.objects.get(action=AuditEvent.Action.SCHEME_CHANGE)
        self.assertEqual(event.actor, owner)
        self.assertEqual(
            event.details["changes"]["minimum_contribution"],
            {"from": "100.00", "to": "250.00"},
        )
        self.assertEqual(
            event.details["changes"]["publicly_listed"],
            {"from": "False", "to": "True"},
        )

    def test_redemption_reversal_restores_liability_without_editing_original(self):
        owner = make_owner()
        account = make_account(owner=owner)
        make_paid_contribution(account)
        redemption = complete_redemption(
            scheme_account=account,
            settlement_type=Redemption.SettlementType.CASH,
            amount=Decimal("100.00"),
            processed_by=owner,
            idempotency_key=uuid.uuid4(),
            audit_reason="Customer collected the matured amount.",
        )
        self.assertEqual(get_cash_balance(account), Decimal("0.00"))
        account.refresh_from_db()
        self.assertEqual(account.status, SchemeAccount.Status.REDEEMED)

        reversal = reverse_redemption(
            redemption=redemption,
            processed_by=owner,
            reason="Settlement was entered against the wrong account.",
        )

        redemption.refresh_from_db()
        account.refresh_from_db()
        self.assertEqual(Redemption.objects.count(), 1)
        self.assertEqual(redemption.cash_amount, Decimal("100.00"))
        self.assertEqual(get_cash_balance(account), Decimal("100.00"))
        self.assertEqual(account.status, SchemeAccount.Status.ACTIVE)
        self.assertEqual(
            get_owner_liability_summary().cash_principal,
            Decimal("100.00"),
        )
        self.assertEqual(
            AuditEvent.objects.filter(action=AuditEvent.Action.REDEMPTION).count(),
            1,
        )
        self.assertEqual(
            AuditEvent.objects.filter(action=AuditEvent.Action.REVERSAL).count(),
            1,
        )
        reversal.reason = "Changed"
        with self.assertRaisesMessage(ValidationError, "immutable"):
            reversal.save()

    def test_exception_queue_classifies_allocation_and_webhook_failures(self):
        owner = make_owner()
        account = make_account(mode=SchemeAccount.SavingsMode.GOLD, owner=owner)
        contribution = make_paid_contribution(
            account, status=Contribution.Status.PAID_UNALLOCATED
        )
        PaymentWebhookEvent.objects.create(
            gateway="razorpay",
            gateway_mode="test",
            event_id="evt-mismatch",
            event_type="payment.captured",
            payload_sha256="a" * 64,
            status=PaymentWebhookEvent.Status.FAILED,
            gateway_order_id="order-unmatched",
            error="Razorpay webhook payment details do not match.",
            processed_at=timezone.now(),
        )
        PaymentWebhookEvent.objects.create(
            gateway="razorpay",
            gateway_mode="test",
            event_id="evt-failed",
            event_type="payment.captured",
            payload_sha256="b" * 64,
            status=PaymentWebhookEvent.Status.FAILED,
            contribution=contribution,
            error="Contribution does not exist.",
            processed_at=timezone.now(),
        )

        queue = get_owner_exception_queue()
        self.assertEqual(len(queue), 3)
        self.assertEqual(
            {item.category for item in queue},
            {
                "PAID_UNALLOCATED / failed allocation",
                "Payment mismatch / manual correction required",
                "Failed webhook reconciliation",
            },
        )

        counts = get_financial_exception_counts()
        self.assertEqual(counts.paid_unallocated, 1)
        self.assertEqual(counts.failed_webhooks, 2)
        self.assertEqual(counts.mismatched_webhooks, 1)
        self.assertEqual(counts.total, 3)

        output = StringIO()
        with self.assertRaisesMessage(
            CommandError, "3 unresolved financial exception(s) detected"
        ):
            call_command("check_financial_exceptions", stdout=output)
        rendered = output.getvalue()
        self.assertIn("status=alert", rendered)
        self.assertIn("paid_unallocated=1", rendered)
        self.assertIn("failed_webhooks=2", rendered)
        self.assertIn("mismatched_webhooks=1", rendered)
        self.assertNotIn("order-unmatched", rendered)
        self.assertNotIn("Contribution does not exist", rendered)

    def test_financial_exception_check_reports_healthy_without_details(self):
        output = StringIO()
        call_command("check_financial_exceptions", stdout=output)
        self.assertIn(
            "financial_exception_check status=ok",
            output.getvalue(),
        )

    def test_owner_retry_is_audited_with_resulting_scheme_rate(self):
        owner = make_owner()
        account = make_account(mode=SchemeAccount.SavingsMode.GOLD, owner=owner)
        scheme_rate = publish_scheme_rate(
            metal_grade=metal_grade_for(SchemeRate.Metal.GOLD),
            rate_per_gram=Decimal("10000.0000"),
            published_by=owner,
        )
        contribution = make_paid_contribution(
            account, status=Contribution.Status.PAID_UNALLOCATED
        )
        contribution.scheme_rate = scheme_rate
        contribution.rate_locked_at = contribution.created_at
        contribution.save(update_fields=["scheme_rate", "rate_locked_at"])

        allocation = retry_metal_allocation(
            contribution=contribution,
            performed_by=owner,
            reason="Investigated exception; retrying the locked allocation.",
        )

        event = AuditEvent.objects.get(action=AuditEvent.Action.ALLOCATION_RETRY)
        self.assertEqual(event.actor, owner)
        self.assertEqual(event.contribution, contribution)
        self.assertEqual(event.scheme_rate, allocation.scheme_rate)
        self.assertEqual(event.details["outcome"], "SUCCEEDED")

    def test_customer_cannot_access_owner_audit_or_exception_views(self):
        owner = make_owner()
        account = make_account(owner=owner)
        self.client.force_login(account.customer.user)

        self.assertEqual(self.client.get(reverse("schemes:audit_log")).status_code, 403)
        self.assertEqual(
            self.client.get(reverse("schemes:exception_queue")).status_code,
            403,
        )

    def test_reversal_view_requires_reason_and_records_actor(self):
        owner = make_owner()
        account = make_account(owner=owner)
        make_paid_contribution(account)
        redemption = complete_redemption(
            scheme_account=account,
            settlement_type=Redemption.SettlementType.CASH,
            amount="100.00",
            processed_by=owner,
            idempotency_key=uuid.uuid4(),
        )
        self.client.force_login(owner)
        url = reverse("schemes:redemption_reverse", args=[redemption.redemption_number])

        missing_reason = self.client.post(url, {"reason": ""})
        self.assertEqual(missing_reason.status_code, 200)
        self.assertFalse(hasattr(redemption, "reversal"))

        response = self.client.post(url, {"reason": "Duplicate settlement entry."})
        self.assertRedirects(response, reverse("schemes:redemption_list"))
        redemption = Redemption.objects.select_related("reversal").get(pk=redemption.pk)
        self.assertEqual(redemption.reversal.processed_by, owner)
