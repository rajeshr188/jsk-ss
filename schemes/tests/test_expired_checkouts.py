from datetime import timedelta
from decimal import Decimal
from io import StringIO
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from schemes.models import AuditEvent, Contribution, PaymentWebhookEvent, SchemePlan
from schemes.payments import PaymentGatewayError, PaymentOrderInspection
from schemes.selectors import (
    get_cash_balance, get_expired_pending_checkouts, get_financial_exception_counts,
    get_owner_exception_keys, get_owner_exception_queue,
)
from schemes.services import confirm_razorpay_contribution, initiate_razorpay_contribution, reconcile_abandoned_razorpay_contribution
from schemes.tests.test_razorpay import FakeRazorpayGateway, RAZORPAY_SETTINGS, make_account


@override_settings(**{**RAZORPAY_SETTINGS, "DEBUG": True})
class ExpiredCheckoutTests(TestCase):
    def setUp(self):
        self.customer, self.account = make_account(email="expired-checkout@example.invalid", frequency=SchemePlan.FrequencyRule.FLEXIBLE)
        self.owner = get_user_model().objects.create_user(username="checkout-owner", email="owner@example.invalid", role="OWNER")
        self.client.force_login(self.owner)
        self.gateway = FakeRazorpayGateway()

    def payment(self, *, expired=True, mode="test", order=True):
        c = initiate_razorpay_contribution(scheme_account=self.account, amount=Decimal("5000"), gateway=self.gateway)
        Contribution.objects.filter(pk=c.pk).update(
            created_at=timezone.now() - timedelta(hours=2),
            checkout_expires_at=timezone.now() + timedelta(minutes=-10 if expired else 10),
            gateway_mode=mode, gateway_order_id=c.gateway_order_id if order else None,
        )
        c.refresh_from_db()
        return c

    def url(self, c):
        return reverse("schemes:order_reconciliation", args=[c.pk])

    def inspect(self, c):
        with patch("schemes.services.get_payment_gateway", return_value=self.gateway):
            return self.client.post(self.url(c), {"action": "INSPECT", "reason": "Review expired payment"})

    def token(self, c):
        response = self.inspect(c)
        self.assertTrue(response.context["can_apply"])
        return response.context["form"].initial["review_token"]

    def apply(self, c, token, **extra):
        data = dict(action="APPLY", reason="Verified the unpaid order", review_token=token, confirmed="on")
        data.update(extra)
        with patch("schemes.services.get_payment_gateway", return_value=self.gateway):
            return self.client.post(self.url(c), data)

    def command(self, *args, **kwargs):
        output = StringIO()
        with patch("schemes.management.commands.reconcile_abandoned_razorpay_orders.get_payment_gateway", return_value=self.gateway):
            call_command("reconcile_abandoned_razorpay_orders", *args, stdout=output, stderr=output, **kwargs)
        return output.getvalue()

    def test_expiry_boundary_counts_all_modes_but_excludes_unexpired_and_paid(self):
        now = timezone.now()
        c = self.payment()
        other_mode = self.payment(mode="live")
        no_order = self.payment(order=False)
        future = self.payment(expired=False)
        Contribution.objects.filter(pk=c.pk).update(checkout_expires_at=now)
        self.assertEqual(set(get_expired_pending_checkouts(at=now).values_list("pk", flat=True)), {c.pk, other_mode.pk, no_order.pk})
        self.assertEqual(get_financial_exception_counts().expired_checkouts, 3)
        self.assertNotIn(future.pk, get_expired_pending_checkouts().values_list("pk", flat=True))

    def test_queue_count_filter_pagination_and_recovery_link_are_read_only(self):
        for _ in range(26):
            self.payment()
        PaymentWebhookEvent.objects.create(gateway="razorpay", gateway_mode="test", event_id="checkout-queue-webhook", event_type="payment.captured", payload_sha256="a" * 64, status="FAILED")
        keys = get_owner_exception_keys(category="checkout")
        self.assertEqual(keys.count(), 26)
        self.assertEqual(get_owner_exception_keys().count(), 27)
        items = get_owner_exception_queue(keys=keys[:25])
        self.assertEqual(len(items), 25)
        self.assertTrue(all(item.queue_kind == "checkout" for item in items))
        with patch("schemes.payments.RazorpayPaymentGateway.inspect_order", side_effect=AssertionError("GET must not inspect provider")):
            response = self.client.get(reverse("schemes:exception_queue"), {"category": "checkout", "page": 2}, HTTP_HX_REQUEST="true")
        self.assertEqual(response.context["page_obj"].paginator.count, 26)
        self.assertEqual(len(response.context["exceptions"]), 1)
        self.assertContains(response, "Review expired checkout")
        self.assertNotContains(response, "Verified payment awaiting allocation")
        self.assertEqual(AuditEvent.objects.filter(action="PAYMENT_ORDER_RECONCILIATION").count(), 0)

    def test_alert_counts_are_aggregate_and_expired_attempt_is_not_healthy(self):
        c = self.payment()
        output = StringIO()
        with self.assertRaises(CommandError):
            call_command("check_financial_exceptions", stdout=output)
        self.assertIn("expired_checkouts=1", output.getvalue())
        self.assertIn("status=alert", output.getvalue())
        for private in [self.customer.email, self.customer.full_name, self.account.scheme_number, c.gateway_order_id]:
            self.assertNotIn(private, output.getvalue())

    def test_default_command_inspects_recent_expiry_without_waiting_24_hours(self):
        c = self.payment()
        self.assertIn("eligible=1", self.command())
        c.refresh_from_db()
        self.assertEqual(c.status, "PENDING")
        self.assertEqual(self.gateway.inspect_calls, 1)

    def test_exact_selection_apply_changes_only_reviewed_attempt(self):
        c, other = self.payment(), self.payment()
        output = self.command("--contribution-id", str(c.pk), "--apply")
        self.assertIn("abandoned=1", output)
        c.refresh_from_db()
        other.refresh_from_db()
        self.assertEqual(c.status, "ABANDONED")
        self.assertEqual(other.status, "PENDING")
        self.assertEqual(get_cash_balance(self.account), Decimal("0.00"))

    def test_grace_age_and_unexpired_filter_never_call_provider(self):
        c = self.payment()
        Contribution.objects.filter(pk=c.pk).update(checkout_expires_at=timezone.now() - timedelta(minutes=2))
        self.assertIn("candidates=0", self.command())
        self.assertIn("candidates=0", self.command("--older-than-hours=24"))
        Contribution.objects.filter(pk=c.pk).update(checkout_expires_at=timezone.now() + timedelta(minutes=2))
        self.assertIn("candidates=0", self.command("--grace-minutes=0"))
        self.assertEqual(self.gateway.inspect_calls, 0)

    def test_other_mode_missing_order_and_limit_backlog_still_alert(self):
        self.payment(mode="live")
        self.payment(order=False)
        self.payment()
        self.payment()
        output = StringIO()
        with patch("schemes.management.commands.reconcile_abandoned_razorpay_orders.get_payment_gateway", return_value=self.gateway):
            with self.assertRaises(CommandError):
                call_command("reconcile_abandoned_razorpay_orders", "--limit=1", "--summary-only", "--fail-on-pending", stdout=output)
        self.assertIn("candidates=1", output.getvalue())
        self.assertIn("expired_pending=4", output.getvalue())
        self.assertNotIn("order_test", output.getvalue())

    def test_provider_errors_are_redacted_and_fail_monitoring(self):
        self.payment()
        output = StringIO()
        with patch.object(self.gateway, "inspect_order", side_effect=PaymentGatewayError("credential-or-provider-body")):
            with patch("schemes.management.commands.reconcile_abandoned_razorpay_orders.get_payment_gateway", return_value=self.gateway):
                with self.assertRaises(CommandError):
                    call_command("reconcile_abandoned_razorpay_orders", "--summary-only", stdout=output, stderr=output)
        self.assertIn("errors=1", output.getvalue())
        self.assertNotIn("credential-or-provider-body", output.getvalue())

    def test_invalid_operator_options_and_unavailable_exact_id_fail_closed(self):
        for args in [("--grace-minutes=-1",), ("--limit=0",), ("--older-than-hours=0",), ("--contribution-id=0",), ("--contribution-id=999999",)]:
            with self.subTest(args=args), self.assertRaises(CommandError):
                self.command(*args)
        self.assertEqual(self.gateway.inspect_calls, 0)

    def test_owner_get_is_read_only_and_other_methods_are_rejected(self):
        c = self.payment()
        with patch("schemes.services.get_payment_gateway", side_effect=AssertionError("No provider GET")):
            response = self.client.get(self.url(c))
        self.assertContains(response, "Check provider")
        self.assertNotContains(response, 'value="APPLY"')
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(self.client.delete(self.url(c)).status_code, 405)
        self.assertEqual(self.client.head(self.url(c)).status_code, 405)

    def test_customer_inactive_owner_and_staff_are_denied(self):
        c = self.payment()
        for role, active in [("CUSTOMER", True), ("OWNER", False), ("STAFF", True)]:
            user = get_user_model().objects.create_user(username=f"blocked-{role}-{active}", role=role, is_active=active)
            self.client.force_login(user)
            # Inactive sessions become anonymous through the authentication backend.
            self.assertIn(self.client.get(self.url(c)).status_code, [302, 403])
            self.assertIn(self.client.post(self.url(c), {"action": "INSPECT", "reason": "Review"}).status_code, [302, 403])
        self.assertEqual(self.gateway.inspect_calls, 0)

    def test_csrf_and_reason_required_before_provider_read(self):
        c = self.payment()
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        self.assertEqual(client.post(self.url(c), {"action": "INSPECT", "reason": "Review"}).status_code, 403)
        self.assertContains(self.client.post(self.url(c), {"action": "INSPECT", "reason": ""}), "This field is required")
        self.assertEqual(self.gateway.inspect_calls, 0)

    def test_owner_inspect_then_apply_rechecks_provider_and_writes_one_audit(self):
        c = self.payment()
        token = self.token(c)
        self.assertEqual(AuditEvent.objects.filter(action="PAYMENT_ORDER_RECONCILIATION").count(), 0)
        response = self.apply(c, token)
        self.assertContains(response, "closed after a fresh provider check")
        self.assertEqual(self.gateway.inspect_calls, 2)
        c.refresh_from_db()
        self.assertEqual(c.status, "ABANDONED")
        audit = AuditEvent.objects.get(action="PAYMENT_ORDER_RECONCILIATION")
        self.assertEqual(audit.actor, self.owner)
        self.assertEqual(audit.details["provider_payment_count"], 0)
        self.apply(c, token)
        self.assertEqual(AuditEvent.objects.filter(action="PAYMENT_ORDER_RECONCILIATION").count(), 1)
        self.assertEqual(get_cash_balance(self.account), Decimal("0.00"))

    def test_apply_requires_confirmation_and_real_bound_unexpired_token(self):
        c = self.payment()
        token = self.token(c)
        for invalid in ["", "tampered", token + "x"]:
            self.assertContains(self.apply(c, invalid), "Check provider again")
        self.assertContains(self.apply(c, token, confirmed=""), "confirm closing this attempt")
        with patch("django.core.signing.time.time", return_value=timezone.now().timestamp() + 601):
            self.assertContains(self.apply(c, token), "expired")
        other = self.payment()
        self.assertContains(self.apply(other, token), "differs from the reviewed record")
        other_owner = get_user_model().objects.create_user(username="other-checkout-owner", role="OWNER")
        self.client.force_login(other_owner)
        self.assertContains(self.apply(c, token), "differs from the reviewed record")
        self.assertEqual(self.gateway.inspect_calls, 1)

    def test_changed_provider_result_stays_pending_after_prior_safe_inspection(self):
        c = self.payment()
        token = self.token(c)
        self.gateway.inspection = PaymentOrderInspection(order_id=c.gateway_order_id, status="attempted", amount_subunits=500000, amount_paid_subunits=0, amount_due_subunits=500000, currency="INR", attempts=1, payment_count=1, payment_statuses=("failed",))
        response = self.apply(c, token)
        self.assertContains(response, "remains pending for investigation")
        c.refresh_from_db()
        self.assertEqual(c.status, "PENDING")
        self.assertFalse(AuditEvent.objects.get(action="PAYMENT_ORDER_RECONCILIATION").details["applied"])

    def test_live_mode_mismatch_and_unexpired_attempt_cannot_be_closed(self):
        for c in [self.payment(mode="live"), self.payment(expired=False)]:
            response = self.inspect(c)
            self.assertFalse(response.context["can_apply"])
        self.assertEqual(self.gateway.inspect_calls, 0)

    def test_unexpired_service_rejects_even_if_operator_age_cutoff_would_allow_it(self):
        c = self.payment(expired=False)
        with self.assertRaisesMessage(ValidationError, "Checkout must expire"):
            reconcile_abandoned_razorpay_contribution(contribution_id=c.pk, cutoff=timezone.now(), apply=True, gateway=self.gateway)
        self.assertEqual(self.gateway.inspect_calls, 0)

    def test_capture_committing_during_inspection_cannot_be_overwritten(self):
        c = self.payment()
        inspection = self.gateway.inspect_order(order_id=c.gateway_order_id)
        def capture_before_lock(**kwargs):
            confirm_razorpay_contribution(
                contribution_id=c.pk, callback_order_id=c.gateway_order_id,
                payment_id="pay_concurrent_capture", signature="verified-signature", gateway=self.gateway,
            )
            return inspection
        with patch.object(self.gateway, "inspect_order", side_effect=capture_before_lock):
            with self.assertRaisesMessage(ValidationError, "changed during reconciliation"):
                reconcile_abandoned_razorpay_contribution(contribution_id=c.pk, cutoff=timezone.now(), apply=True, gateway=self.gateway)
        c.refresh_from_db()
        self.assertEqual(c.status, "PAID")
        self.assertEqual(get_cash_balance(self.account), Decimal("5000.00"))
        self.assertFalse(AuditEvent.objects.filter(action="PAYMENT_ORDER_RECONCILIATION").exists())


class CheckoutTimerTests(SimpleTestCase):
    def test_five_minute_bounded_inspection_is_dry_run_and_private(self):
        root = Path(settings.BASE_DIR) / "deploy" / "systemd"
        service = (root / "jsk-checkout-reconciliation.service").read_text()
        timer = (root / "jsk-checkout-reconciliation.timer").read_text()
        script = (root.parent / "check-expired-checkouts.sh").read_text()
        self.assertIn("--limit=3 --summary-only --fail-on-pending", script)
        self.assertNotIn("--apply", script)
        self.assertIn("check_financial_exceptions", script)
        self.assertIn("${heartbeat_url%/}/fail", script)
        self.assertIn("delivery=server_only", script)
        self.assertIn("ProtectHome=true", service)
        self.assertIn("RuntimeDirectory=jsk-checkout-reconciliation", service)
        self.assertIn("Environment=REQUIRE_FINANCIAL_HEARTBEAT=true", service)
        self.assertNotIn("docker compose", service)
        self.assertIn("OnUnitActiveSec=5min", timer)

    def test_script_preserves_failures_and_routes_combined_heartbeat_without_disclosure(self):
        bash = "C:/Program Files/Git/bin/bash.exe" if os.name == "nt" else shutil.which("bash")
        if not bash or not Path(bash).is_file():
            self.skipTest("Bash is required for the alert wrapper behavior check")
        source = (Path(settings.BASE_DIR) / "deploy/check-expired-checkouts.sh").read_text()
        with tempfile.TemporaryDirectory(prefix="jsk-checkout-alert-") as directory:
            root = Path(directory)
            docker = root / "docker-stub"
            docker.write_text('#!/usr/bin/env bash\ncase "$*" in *check_financial_exceptions*) exit "$FIN_STATUS" ;; *) exit "$SCAN_STATUS" ;; esac\n', encoding="utf-8", newline="\n")
            curl = root / "curl"
            curl.write_text('#!/usr/bin/env bash\nprintf "%s" "${@: -1}" > "$CURL_TARGET"\nexit "$CURL_STATUS"\n', encoding="utf-8", newline="\n")
            docker.chmod(0o700)
            curl.chmod(0o700)
            script = root / "check.sh"
            script.write_text(source.replace("/usr/bin/docker", '"' + docker.as_posix() + '"').replace("if ! curl ", 'if ! "' + curl.as_posix() + '" '), encoding="utf-8", newline="\n")
            cases = [(0, 0, "", 0, 0), (1, 0, "", 0, 1), (0, 1, "", 0, 1),
                     (1, 0, "https://heartbeat.invalid/private-token", 0, 1),
                     (0, 0, "https://heartbeat.invalid/private-token", 0, 0),
                     (0, 0, "https://heartbeat.invalid/private-token", 1, 69)]
            for financial, scan, heartbeat, delivery, expected in cases:
                with self.subTest(financial=financial, scan=scan, heartbeat=bool(heartbeat), delivery=delivery):
                    target = root / "target"
                    target.unlink(missing_ok=True)
                    env = dict(os.environ, PATH=str(root) + os.pathsep + os.environ.get("PATH", ""),
                        FIN_STATUS=str(financial), SCAN_STATUS=str(scan), CURL_STATUS=str(delivery),
                        REQUIRE_FINANCIAL_HEARTBEAT="false",
                        CURL_TARGET=target.as_posix(), FINANCIAL_EXCEPTIONS_HEARTBEAT_URL=heartbeat)
                    result = subprocess.run([bash, script.as_posix()], env=env, capture_output=True, text=True, timeout=20)
                    self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
                    self.assertNotIn("private-token", result.stdout + result.stderr)
                    if heartbeat:
                        self.assertEqual(target.read_text(), heartbeat + ("/fail" if financial or scan else ""))
            env.update(FIN_STATUS="0", SCAN_STATUS="0", REQUIRE_FINANCIAL_HEARTBEAT="true", FINANCIAL_EXCEPTIONS_HEARTBEAT_URL="")
            strict = subprocess.run([bash, script.as_posix()], env=env, capture_output=True, text=True, timeout=20)
            self.assertEqual(strict.returncode, 64)
            self.assertIn("delivery=unconfigured", strict.stdout)
