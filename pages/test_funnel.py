import json
from datetime import timedelta
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import OperationalError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.test_public_registration import REGISTRATION_SETTINGS, submit_application
from accounts.services import verify_customer_registration_email
from pages.models import PublicFunnelDailyCount
from pages.selectors import get_funnel_report
from pages import tests as page_helpers
from schemes.models import Contribution, SchemePlan, SchemePlanOffering
from schemes.services import confirm_razorpay_contribution, initiate_contribution
from schemes.tests.test_razorpay import RAZORPAY_SETTINGS, make_account


@override_settings(PUBLIC_FUNNEL_MEASUREMENT_ENABLED=True, **REGISTRATION_SETTINGS)
class PublicFunnelTests(TestCase):
    make_plan = page_helpers.PublicPricingPageTests.make_plan

    def setUp(self):
        self.plan = self.make_plan(code="FUNNEL", publicly_listed=True)

    def test_selected_plan_is_primary_and_validated_at_registration(self):
        response = self.client.get(reverse("plan_apply", args=[self.plan.pk]), follow=True)
        self.assertContains(response, f"Selected plan: {self.plan.name}")
        if response.context["form"].__class__.__name__ == "PlanApplicationContactForm":
            self.assertContains(response, "Share your contact details and preferences")
        else:
            self.assertContains(response, "After approval and login setup")
        self.assertContains(response, "₹1,000.00")
        self.assertTrue(response["Cache-Control"].find("no-store") >= 0)
        self.assertEqual(PublicFunnelDailyCount.objects.get(step="SELECTED").count, 1)
        self.assertEqual(PublicFunnelDailyCount.objects.get(step="APPLICATION").count, 1)
        self.assertEqual(self.client.get(reverse("plan_apply", args=[99999])).status_code, 404)
        self.plan.publicly_listed = False
        self.plan.save()
        response = self.client.get(reverse("customer_registration"), {"plan": self.plan.pk})
        self.assertNotContains(response, self.plan.name)
        self.assertEqual(self.client.get(reverse("plan_apply", args=[self.plan.pk])).status_code, 404)

    def test_no_offering_no_application(self):
        SchemePlanOffering.objects.filter(plan=self.plan).update(active=False)
        self.assertEqual(self.client.get(reverse("plan_apply", args=[self.plan.pk])).status_code, 404)

    def test_invalid_or_huge_selection_does_not_error(self):
        for value in ["999999999999999999999999", "https://example.com", "-1", "١"]:
            with self.subTest(value=value):
                response = self.client.get(reverse("customer_registration"), {"plan": value})
                self.assertEqual(response.status_code, 200)
                self.assertIsNone(response.context["selected_plan"])

    def test_counts_are_aggregate_and_do_not_collect_query_or_identity(self):
        self.client.get(reverse("home"), {"email": "private@example.com", "token": "never-retain"})
        self.client.get(reverse("home"))
        self.client.head(reverse("home"))
        self.assertEqual(PublicFunnelDailyCount.objects.get(step="HOME").count, 2)
        self.assertEqual(set(f.name for f in PublicFunnelDailyCount._meta.fields), {"id", "day", "step", "count"})
        owner = get_user_model().objects.create_user(username="measurement-owner", role="OWNER")
        self.client.force_login(owner)
        self.client.get(reverse("home"))
        self.assertEqual(PublicFunnelDailyCount.objects.get(step="HOME").count, 2)

    @override_settings(PUBLIC_FUNNEL_MEASUREMENT_ENABLED=False)
    def test_disabled_measurement_does_not_write(self):
        self.client.get(reverse("home"))
        self.assertEqual(PublicFunnelDailyCount.objects.count(), 0)

    def test_counter_failure_does_not_block_page_or_break_transaction(self):
        with patch("pages.services.PublicFunnelDailyCount.objects.get_or_create", side_effect=OperationalError("secret-value")):
            with self.assertLogs("pages.services", level="WARNING") as logs:
                response = self.client.get(reverse("pricing"))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("secret-value", " ".join(logs.output))
        self.assertTrue(self.plan.__class__.objects.filter(pk=self.plan.pk).exists())

    @override_settings(PUBLIC_CUSTOMER_REGISTRATION_ENABLED=False)
    def test_disabled_registration_routes_to_support_and_does_not_count_selection(self):
        response = self.client.get(reverse("plan_apply", args=[self.plan.pk]))
        self.assertRedirects(response, reverse("contact"))
        self.assertFalse(PublicFunnelDailyCount.objects.exists())

    def test_free_text_marketing_is_not_public_and_decimal_precision_is_preserved(self):
        self.plan.description = "Retirement investment with guaranteed soaring prices"
        self.plan.fixed_contribution_amount = Decimal("1000.25")
        self.plan.save()
        for route in ["home", "pricing"]:
            response = self.client.get(reverse(route))
            self.assertContains(response, "₹1000.25")
            self.assertNotContains(response, self.plan.description)

    def test_verification_is_counted_from_source_without_tracking_token_page(self):
        submission = submit_application()
        verify_customer_registration_email(application_id=submission.application.pk, raw_token=submission.raw_token)
        report = get_funnel_report(start=timezone.localdate(), end=timezone.localdate())
        self.assertEqual(report["outcomes"]["registrations_submitted"], 1)
        self.assertEqual(report["outcomes"]["registration_emails_verified"], 1)
        output = StringIO()
        call_command("report_customer_funnel", start=timezone.localdate().isoformat(), stdout=output)
        payload = output.getvalue()
        self.assertEqual(json.loads(payload), report)
        for secret in [submission.raw_token, submission.application.email, submission.application.mobile_number]:
            self.assertNotIn(secret, payload)
        self.assertFalse(PublicFunnelDailyCount.objects.exists())


@override_settings(**RAZORPAY_SETTINGS)
class FunnelPaymentTests(TestCase):
    def test_only_verified_live_payments_count_and_first_payment_uses_full_history(self):
        customer, account = make_account(email="funnel-private@example.com", mode="GOLD", frequency=SchemePlan.FrequencyRule.FLEXIBLE)
        # Use normal domain services and mocked provider verification, never a browser callback count.
        from schemes.services import publish_scheme_rate
        owner = get_user_model().objects.create_user(username="funnel-owner", role="OWNER")
        publish_scheme_rate(metal_grade=account.metal_grade, rate_per_gram=Decimal("12500"), published_by=owner, notes="Synthetic funnel test")
        payments = []
        for mode in ["test", "live", "live"]:
            contribution = initiate_contribution(scheme_account=account, amount=Decimal("5000"), payment_gateway="razorpay", gateway_mode=mode)
            contribution.gateway_order_id = f"order_funnel_{contribution.pk}"
            contribution.save(update_fields=["gateway_order_id"])
            with override_settings(RAZORPAY_MODE=mode, RAZORPAY_KEY_ID=f"rzp_{mode}_key"):
                with patch("schemes.payments.RazorpayPaymentGateway.verify_payment", return_value=True):
                    confirm_razorpay_contribution(contribution_id=contribution.pk, callback_order_id=contribution.gateway_order_id, payment_id=f"pay_funnel_{contribution.pk}", signature="signed")
            payments.append(contribution)
        day = timezone.localdate()
        report = get_funnel_report(start=day, end=day)
        self.assertEqual(report["outcomes"]["first_live_online_payments"], 1)
        self.assertEqual(report["outcomes"]["subsequent_live_online_payments"], 1)
        Contribution.objects.filter(pk=payments[1].pk).update(paid_at=timezone.now() - timedelta(days=2))
        report = get_funnel_report(start=day, end=day)
        self.assertEqual(report["outcomes"]["first_live_online_payments"], 0)
        self.assertEqual(report["outcomes"]["subsequent_live_online_payments"], 1)
        self.assertNotIn(customer.email, json.dumps(report))
