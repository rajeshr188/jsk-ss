import json
from datetime import datetime, time, timedelta
from decimal import Decimal
from io import StringIO
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from schemes.models import (
    AuditEvent,
    Contribution,
    MetalAllocation,
    PaymentOperationsControl,
    PaymentScheduleWindow,
    SchemeAccount,
    SchemePlan,
    SchemeRate,
)
from schemes.operations import get_payment_availability
from schemes.payments import PaymentOrder
from schemes.services import (
    confirm_razorpay_contribution,
    create_customer,
    enroll_customer,
    initiate_razorpay_contribution,
    publish_scheme_rate,
    process_razorpay_webhook,
    update_payment_operations_control,
)


IST = ZoneInfo("Asia/Kolkata")


class FakeRazorpayGateway:
    name = "razorpay"
    mode = "test"

    def __init__(self):
        self.order_calls = 0
        self.verify_calls = 0

    def create_order(self, contribution):
        self.order_calls += 1
        return PaymentOrder(
            order_id=f"order_ops_{contribution.pk}",
            amount_subunits=int(contribution.amount * 100),
            currency="INR",
        )

    def verify_payment(self, **_kwargs):
        self.verify_calls += 1
        return True


@override_settings(
    DEBUG=False,
    PAYMENT_GATEWAY="razorpay",
    PAYMENT_INITIATION_KILL_SWITCH=False,
    RAZORPAY_MODE="test",
    RAZORPAY_KEY_ID="rzp_test_public_key",
    RAZORPAY_KEY_SECRET="test-key-secret",
    RAZORPAY_WEBHOOK_SECRET="test-webhook-secret",
)
class PaymentOperationsTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(
            username="operations-owner@example.com",
            email="operations-owner@example.com",
            password="owner-password-strong",
            role=user_model.Role.OWNER,
        )
        self.customer = create_customer(
            full_name="Operations Customer",
            email="operations-customer@example.com",
            mobile_number="9000000042",
            password="customer-password-strong",
        )
        self.plan = SchemePlan.objects.create(
            name="Operations plan",
            code="OPS-GOLD",
            amount_rule=SchemePlan.AmountRule.FIXED,
            frequency_rule=SchemePlan.FrequencyRule.FLEXIBLE,
            fixed_contribution_amount=Decimal("5000.00"),
            minimum_contribution=Decimal("5000.00"),
            maximum_contribution=Decimal("5000.00"),
        )
        self.account = enroll_customer(
            customer=self.customer,
            plan=self.plan,
            savings_mode=SchemeAccount.SavingsMode.GOLD,
            start_date=timezone.localdate(),
            performed_by=self.owner,
            reason="Set up operations-control test account.",
        )
        self.rate = publish_scheme_rate(
            metal=SchemeRate.Metal.GOLD,
            rate_per_gram=Decimal("12500.0000"),
            published_by=self.owner,
            notes="Operations-control test rate.",
        )
        self.control = PaymentOperationsControl.objects.get(pk=1)

    def schedule_values(self):
        return {
            window.weekday: {
                "enabled": window.enabled,
                "opens_at": window.opens_at,
                "closes_at": window.closes_at,
            }
            for window in self.control.schedule_windows.all()
        }

    def update_control(self, **overrides):
        values = {
            "actor": self.owner,
            "reason": "Exercise the payment operations control.",
            "schedule_enabled": self.control.schedule_enabled,
            "require_current_day_rate": self.control.require_current_day_rate,
            "global_pause": self.control.global_pause,
            "gold_pause": self.control.gold_pause,
            "silver_pause": self.control.silver_pause,
            "customer_message": self.control.customer_message,
            "schedule": self.schedule_values(),
        }
        values.update(overrides)
        self.control = update_payment_operations_control(**values)
        return self.control

    def test_seeded_schedule_is_safe_and_default_off(self):
        windows = list(self.control.schedule_windows.order_by("weekday"))

        self.assertFalse(self.control.schedule_enabled)
        self.assertTrue(self.control.require_current_day_rate)
        self.assertEqual(len(windows), 7)
        self.assertTrue(all(window.opens_at.hour == 9 for window in windows))
        self.assertTrue(all(window.closes_at.hour == 21 for window in windows[:6]))
        self.assertEqual(windows[6].closes_at.hour, 13)
        self.assertTrue(
            get_payment_availability(
                metal=SchemeRate.Metal.GOLD,
                at=datetime(2026, 8, 31, 23, 0, tzinfo=IST),
            ).allowed
        )

    def test_schedule_closes_at_nine_pm_and_reports_next_opening(self):
        self.update_control(
            schedule_enabled=True,
            require_current_day_rate=False,
        )

        availability = get_payment_availability(
            metal=SchemeRate.Metal.GOLD,
            at=datetime(2026, 8, 31, 21, 0, tzinfo=IST),
        )

        self.assertFalse(availability.allowed)
        self.assertEqual(availability.code, "OUTSIDE_BUSINESS_HOURS")
        self.assertEqual(
            availability.next_opening,
            datetime(2026, 9, 1, 9, 0, tzinfo=IST),
        )

    def test_schedule_requires_a_rate_published_on_the_local_day(self):
        SchemeRate.objects.filter(pk=self.rate.pk).update(
            published_at=timezone.now() - timedelta(days=1)
        )
        self.update_control(
            schedule_enabled=True,
            require_current_day_rate=True,
        )
        local_now = timezone.localtime()
        today_window = PaymentScheduleWindow.objects.get(
            control=self.control,
            weekday=local_now.weekday(),
        )
        today_window.opens_at = time(0, 0)
        today_window.closes_at = time(23, 59, 59)
        today_window.save(update_fields=["opens_at", "closes_at"])

        availability = get_payment_availability(metal=SchemeRate.Metal.GOLD)

        self.assertFalse(availability.allowed)
        self.assertEqual(availability.code, "RATE_REVIEW_REQUIRED")

    def test_manual_metal_pause_is_audited_with_before_and_after_state(self):
        self.update_control(gold_pause=True, customer_message="Rates under review.")

        gold = get_payment_availability(metal=SchemeRate.Metal.GOLD)
        silver = get_payment_availability(metal=SchemeRate.Metal.SILVER)
        event = AuditEvent.objects.get(
            action=AuditEvent.Action.PAYMENT_OPERATIONS_CHANGE
        )
        self.assertFalse(gold.allowed)
        self.assertEqual(gold.message, "Rates under review.")
        self.assertFalse(event.details["before"]["gold_pause"])
        self.assertTrue(event.details["after"]["gold_pause"])
        self.assertEqual(event.actor, self.owner)
        self.assertEqual(silver.code, "RATE_UNAVAILABLE")

    @override_settings(PAYMENT_INITIATION_KILL_SWITCH=True)
    def test_environment_kill_switch_overrides_database_open_state(self):
        availability = get_payment_availability(metal=SchemeRate.Metal.GOLD)

        self.assertFalse(availability.allowed)
        self.assertEqual(availability.code, "ENVIRONMENT_KILL_SWITCH")

    def test_pause_blocks_order_creation_without_creating_a_contribution(self):
        self.update_control(global_pause=True)
        gateway = FakeRazorpayGateway()

        with self.assertRaisesMessage(ValidationError, "temporarily paused"):
            initiate_razorpay_contribution(
                scheme_account=self.account,
                amount=Decimal("5000.00"),
                gateway=gateway,
            )

        self.assertEqual(gateway.order_calls, 0)
        self.assertFalse(Contribution.objects.filter(scheme_account=self.account).exists())

    def test_pause_does_not_block_confirmation_or_locked_rate_allocation(self):
        gateway = FakeRazorpayGateway()
        contribution = initiate_razorpay_contribution(
            scheme_account=self.account,
            amount=Decimal("5000.00"),
            gateway=gateway,
        )
        self.update_control(global_pause=True)

        confirmed = confirm_razorpay_contribution(
            contribution_id=contribution.pk,
            callback_order_id=contribution.gateway_order_id,
            payment_id="pay_ops_captured",
            signature="signed-callback",
            gateway=gateway,
        )

        self.assertEqual(confirmed.status, Contribution.Status.PAID)
        allocation = MetalAllocation.objects.get(contribution=confirmed)
        self.assertEqual(allocation.scheme_rate, self.rate)
        self.assertEqual(allocation.quantity, Decimal("0.400000"))
        self.assertEqual(gateway.verify_calls, 1)

    def test_pause_does_not_block_captured_webhook_or_allocation(self):
        gateway = FakeRazorpayGateway()
        contribution = initiate_razorpay_contribution(
            scheme_account=self.account,
            amount=Decimal("5000.00"),
            gateway=gateway,
        )
        self.update_control(global_pause=True)
        payload = {
            "event": "payment.captured",
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_ops_webhook",
                        "order_id": contribution.gateway_order_id,
                        "status": "captured",
                        "captured": True,
                        "currency": "INR",
                        "amount": 500000,
                    }
                }
            },
        }
        body = json.dumps(payload, separators=(",", ":")).encode()

        event = process_razorpay_webhook(
            gateway_mode="test",
            event_id="event_ops_captured",
            body=body,
            payload=payload,
        )

        contribution.refresh_from_db()
        self.assertEqual(event.status, event.Status.PROCESSED)
        self.assertEqual(contribution.status, Contribution.Status.PAID)
        self.assertTrue(MetalAllocation.objects.filter(contribution=contribution).exists())

    def test_customer_checkout_and_resume_links_are_hidden_during_pause(self):
        gateway = FakeRazorpayGateway()
        contribution = initiate_razorpay_contribution(
            scheme_account=self.account,
            amount=Decimal("5000.00"),
            gateway=gateway,
        )
        self.update_control(global_pause=True)
        self.client.force_login(self.customer.user)

        detail = self.client.get(
            reverse("schemes:my_scheme_detail", args=[self.account.scheme_number])
        )
        checkout = self.client.get(
            reverse("schemes:razorpay_checkout", args=[contribution.pk]),
            follow=True,
        )

        self.assertNotContains(detail, ">Pay now<")
        self.assertNotContains(detail, "Resume payment")
        self.assertContains(detail, "temporarily paused")
        self.assertContains(checkout, "temporarily paused")

    def test_owner_page_requires_owner_access(self):
        self.client.force_login(self.customer.user)
        denied = self.client.get(reverse("schemes:payment_operations"))
        self.client.force_login(self.owner)
        allowed = self.client.get(reverse("schemes:payment_operations"))

        self.assertEqual(denied.status_code, 403)
        self.assertEqual(allowed.status_code, 200)
        self.assertContains(allowed, "Payment operations")

    def test_owner_can_activate_reviewed_schedule_through_control_page(self):
        payload = {
            "schedule_enabled": "on",
            "require_current_day_rate": "on",
            "audit_reason": "Activate reviewed showroom payment hours.",
        }
        for window in self.control.schedule_windows.all():
            payload[f"day_{window.weekday}_enabled"] = "on"
            payload[f"day_{window.weekday}_opens_at"] = window.opens_at.strftime(
                "%H:%M"
            )
            payload[f"day_{window.weekday}_closes_at"] = window.closes_at.strftime(
                "%H:%M"
            )
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("schemes:payment_operations"),
            payload,
            follow=True,
        )

        self.assertContains(response, "Payment operations policy updated")
        self.control.refresh_from_db()
        self.assertTrue(self.control.schedule_enabled)
        self.assertEqual(self.control.updated_by, self.owner)
        self.assertTrue(
            AuditEvent.objects.filter(
                action=AuditEvent.Action.PAYMENT_OPERATIONS_CHANGE,
                reason="Activate reviewed showroom payment hours.",
            ).exists()
        )

    def test_non_owner_cannot_mutate_control_through_service(self):
        with self.assertRaisesMessage(ValidationError, "Only an active owner"):
            update_payment_operations_control(
                actor=self.customer.user,
                reason="Unauthorized change.",
                schedule_enabled=False,
                require_current_day_rate=True,
                global_pause=True,
                gold_pause=False,
                silver_pause=False,
                customer_message="",
                schedule=self.schedule_values(),
            )

        self.control.refresh_from_db()
        self.assertFalse(self.control.global_pause)

    def test_payment_operations_check_reports_effective_state_without_secrets(self):
        output = StringIO()

        call_command("check_payment_operations", stdout=output)

        value = output.getvalue()
        self.assertIn("payment_operations_check status=ok", value)
        self.assertIn("schedule_enabled=false", value)
        self.assertIn("gold=OPEN", value)
        self.assertNotIn("test-key-secret", value)
