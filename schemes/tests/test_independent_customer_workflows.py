"""Customer HTTP/read integration; readiness alone is simulated, never provider I/O."""
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import connection
from django.test import TestCase, override_settings
from django.urls import reverse

from schemes.models import Contribution, SchemeAccount
from schemes.payments import PaymentOrder
from schemes.plan_configuration import preview_configuration_agreement
from schemes.selectors import get_customer_payment_availability, get_customer_plan_next_action
from schemes.services import initiate_razorpay_contribution
from schemes.tests import test_independent_payment_entry as entry
from schemes.tests.test_independent_eligibility import BENEFIT
from schemes.tests.test_independent_instalment_ledger import NOW


@override_settings(IN_STORE_CASH_CONTRIBUTIONS_ENABLED=True, PAYMENT_INITIATION_KILL_SWITCH=False,
    PAYMENT_GATEWAY="razorpay", RAZORPAY_MODE="live", RAZORPAY_KEY_ID="rzp_live_synthetic",
    RAZORPAY_KEY_SECRET="synthetic-secret", RAZORPAY_WEBHOOK_SECRET="synthetic-webhook",
    CONFIGURED_PLANS_ENABLED=False)
class IndependentCustomerWorkflowTests(TestCase):
    account = entry.IndependentPaymentEntryTests.account
    cash = entry.IndependentPaymentEntryTests.cash
    gateway = entry.IndependentPaymentEntryTests.gateway

    def setUp(self):
        entry.IndependentPaymentEntryTests.setUp(self)
        self.no_network = patch("schemes.payments.urlopen", side_effect=AssertionError("No external payment calls"))
        self.no_network.start()
        self.addCleanup(self.no_network.stop)
        self.client.force_login(self.customer.user)

    def available(self, account):
        return get_customer_payment_availability(account)

    def pay_url(self, account):
        return reverse("schemes:pay_contribution", args=[account.scheme_number])

    def test_five_families_both_units_show_real_entry_without_writes(self):
        for metal in (False, True):
            for required, options in ((False, {}), (False, dict(eligibility_policy="CALENDAR", duration_months=1)),
                    (True, dict(required_count=2)),
                    (True, dict(required_count=2, eligibility_policy="CALENDAR_AND_COUNT", duration_months=18)),
                    (True, BENEFIT)):
                account = self.account(required, metal, **options)
                def read_only(execute, sql, params, many, context):
                    self.assertNotIn(sql.lstrip().split()[0].upper(), {"INSERT", "UPDATE", "DELETE"})
                    return execute(sql, params, many, context)
                with connection.execute_wrapper(read_only):
                    self.assertTrue(self.available(account).allowed)
                    self.assertTrue(get_customer_plan_next_action(account).get("can_pay"))
                    self.assertEqual(account.effective_status, "ACTIVE")
                    page = self.client.get(self.pay_url(account))
                self.assertEqual(page.status_code, 200)
                self.assertContains(page, "Continue to secure payment")
                if not metal:
                    self.assertNotContains(page, "Current Scheme Rate:")
        self.assertFalse(Contribution.objects.exists())

    def test_actual_readiness_still_blocks_entry_and_post_in_both_flag_states(self):
        account = self.account()
        self.ready.stop()
        for flag in (False, True):
            with self.settings(CONFIGURED_PLANS_ENABLED=flag):
                self.assertEqual(self.available(account).code, "INDEPENDENT_NOT_ACTIVATED")
                self.assertEqual(self.client.get(self.pay_url(account)).status_code, 503)
                self.assertEqual(self.client.post(self.pay_url(account), {"amount": "500"}).status_code, 503)
        self.assertFalse(Contribution.objects.exists())

    def test_http_create_continue_checkout_and_stale_form_cannot_duplicate_inr(self):
        for required in (False, True):
            account = self.account(required)
            with patch("schemes.payments.RazorpayPaymentGateway.create_order",
                    side_effect=lambda c: PaymentOrder(f"order_{c.pk}", 50000, "INR")) as provider:
                response = self.client.post(self.pay_url(account), {"amount": "500"})
                c = account.contributions.get()
                self.assertRedirects(response, reverse("schemes:razorpay_checkout", args=[c.pk]))
                checkout = self.client.get(reverse("schemes:razorpay_checkout", args=[c.pk]))
                self.assertContains(checkout, "INR purchase-credit principal")
                self.assertNotContains(checkout, "Your metal entitlement")
                self.assertTrue(self.available(account).allowed)
                self.assertEqual(get_customer_plan_next_action(account)["label"], "Continue payment")
                retry = self.client.post(self.pay_url(account), {"amount": "500"})
                # A stale creation form directs to the existing payment; resumption
                # uses the checked checkout link, never another order submission.
                self.assertContains(retry, "View existing payment")
                self.assertEqual(provider.call_count, 1)
                self.assertEqual(account.contributions.count(), 1)
                self.assertFalse(c.scheme_rate_id)
            self.assertEqual(account.effective_status, "ACTIVE")

    def test_expired_or_uncertain_orders_are_review_only(self):
        for required in (False, True):
            account = self.account(required)
            c = initiate_razorpay_contribution(scheme_account=account, amount=Decimal("500"), gateway=self.gateway())
            with patch("django.utils.timezone.now", return_value=NOW + timedelta(minutes=11)):
                self.assertFalse(self.available(account).allowed)
                self.assertFalse(get_customer_plan_next_action(account)["can_pay"])
                self.assertEqual(self.client.get(reverse("schemes:razorpay_checkout", args=[c.pk])).status_code, 302)
            uncertain = self.account(required)
            gateway = self.gateway()
            gateway.create_order.side_effect = TimeoutError("Synthetic lost order response")
            with self.assertRaises(TimeoutError):
                initiate_razorpay_contribution(scheme_account=uncertain, amount=Decimal("500"), gateway=gateway)
            self.assertFalse(self.available(uncertain).allowed)
            self.assertFalse(get_customer_plan_next_action(uncertain)["can_pay"])

    def test_operations_apply_to_inr_without_demanding_grade_or_rate(self):
        account = self.account()
        self.control.gold_pause = self.control.silver_pause = True
        self.control.save()
        self.assertTrue(self.available(account).allowed)
        self.control.global_pause = True
        self.control.save()
        self.assertEqual(self.available(account).code, "MANUAL_GLOBAL_PAUSE")
        self.control.global_pause = False
        self.control.schedule_enabled = True
        self.control.save()
        self.control.schedule_windows.all().delete()
        self.assertEqual(self.available(account).code, "OUTSIDE_BUSINESS_HOURS")
        with self.settings(PAYMENT_INITIATION_KILL_SWITCH=True):
            self.assertEqual(self.available(account).code, "ENVIRONMENT_KILL_SWITCH")

    def test_gateway_readiness_real_mode_and_customer_containment(self):
        account = self.account()
        with self.settings(RAZORPAY_WEBHOOK_SECRET=""):
            self.assertEqual(self.available(account).code, "UNCONFIGURED")
        with self.settings(RAZORPAY_MODE="test", RAZORPAY_KEY_ID="rzp_test_synthetic"):
            self.assertEqual(self.available(account).code, "REAL_PAYMENT_REQUIRED")
        self.customer.user.is_active = False
        self.customer.user.save(update_fields=["is_active"])
        self.assertEqual(self.available(account).code, "CUSTOMER_UNAVAILABLE")

    def test_closed_stale_or_corrupted_contract_cannot_offer_payment(self):
        account = self.account()
        for status in ("REDEEMED", "CANCELLED", "CLOSURE_PENDING"):
            SchemeAccount.objects.filter(pk=account.pk).update(status=status)
            self.assertEqual(self.available(account).code, status)
        SchemeAccount.objects.filter(pk=account.pk).update(status="ACTIVE", minimum_amount_snapshot=Decimal("1"))
        self.assertEqual(self.available(account).code, "INDEPENDENT_PAYMENT_REVIEW")

    def test_anytime_entitlement_and_qualification_count_change_read_status_not_storage(self):
        for required in (False, True):
            account = self.account(required, required_count=1) if required else self.account()
            self.assertEqual(account.effective_status, "ACTIVE")
            self.cash(account)
            self.assertEqual(account.effective_status, "REDEMPTION_ELIGIBLE")
            self.assertFalse(self.available(account).allowed)
            account.refresh_from_db()
            self.assertEqual(account.status, "ACTIVE")
            self.assertEqual(account.contributions.count(), 1)

    def test_period_ceiling_and_duration_boundary_match_admission(self):
        account = self.account(frequency_rule="ONCE_PER_PERIOD", period_basis="CALENDAR_MONTH",
            allow_contributions_after_eligibility=True)
        self.cash(account)
        self.assertFalse(self.available(account).allowed)
        with patch("django.utils.timezone.now", return_value=NOW.replace(month=2, day=1)):
            self.assertTrue(self.available(account).allowed)
        duration = self.account(eligibility_policy="CALENDAR", duration_months=1)
        with patch("django.utils.timezone.now", return_value=NOW.replace(month=2, day=28)):
            self.assertFalse(self.available(duration).allowed)

    def test_legacy_preview_cannot_reinterpret_independent_contract_after_activation(self):
        account = self.account()
        with patch("schemes.plan_configuration.require_operational_configuration"), self.assertRaisesMessage(
                ValidationError, "independent-policy preview"):
            preview_configuration_agreement(configuration=account.configuration_snapshot,
                amount=Decimal("500"), months=12, metal_grade=None)
