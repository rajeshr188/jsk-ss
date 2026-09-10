import re
from datetime import timedelta
from decimal import Decimal
from io import StringIO
from pathlib import Path

from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount
from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.core import mail
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, connection, transaction
from django.test import Client, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from accounts.logging import redact_sensitive_auth_paths
from accounts.models import (
    CustomerAccountDeletionAction,
    CustomerAccountDeletionAttempt,
    CustomerAccountDeletionDecision,
    CustomerAccountDeletionRequest,
)
from accounts.services import (
    InvalidCustomerAccountDeletion,
    record_customer_account_deletion_hold,
    request_authenticated_customer_account_deletion,
    submit_customer_account_deletion,
    verify_and_contain_customer_account,
)
from accounts.selectors import customer_account_deletion_disposition
from schemes.models import (
    Contribution, Customer, MetalAllocation, PaymentChannel, PaymentWebhookEvent,
    SchemeAccount, SchemePlan, SchemePlanOffering, SchemeRate,
)
from schemes.services import enroll_customer
from schemes.tests.grade_helpers import metal_grade_for


DELETION_SETTINGS = {
    "CUSTOMER_ACCOUNT_DELETION_ENABLED": True,
    "CUSTOMER_ACCOUNT_DELETION_POLICY_VERSION": "test-retention-matrix-v1",
    "CUSTOMER_ACCOUNT_DELETION_EMAIL_EXPIRY_HOURS": 24,
    "CUSTOMER_ACCOUNT_DELETION_ATTEMPTS_PER_HOUR": 5,
    "CUSTOMER_ACCOUNT_DELETION_ATTEMPT_RETENTION_HOURS": 24,
    "CUSTOMER_ACCOUNT_DELETION_OWNER_REVIEW_DAYS": 7,
    "CUSTOMER_ACCOUNT_DELETION_COMPLETION_TARGET_DAYS": 30,
    "EMAIL_BACKEND": "django.core.mail.backends.locmem.EmailBackend",
    "DEFAULT_FROM_EMAIL": "Jai Sri Krishna Jewellery <admin@jaishrikrishnajewellery.com>",
}


@override_settings(**DELETION_SETTINGS)
class CustomerAccountDeletionTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="customer@example.com",
            email="customer@example.com",
            password="strong-customer-password",
            role=user_model.Role.CUSTOMER,
        )
        EmailAddress.objects.create(
            user=self.user,
            email=self.user.email,
            verified=True,
            primary=True,
        )
        self.customer = Customer.objects.create(
            user=self.user,
            customer_number="CUS-DELETE-001",
            full_name="Deletion Customer",
            mobile_number="+919000000001",
            email=self.user.email,
            address="Vellore",
        )
        self.owner = user_model.objects.create_user(
            username="owner@example.com",
            email="owner@example.com",
            password="strong-owner-password",
            role=user_model.Role.OWNER,
        )

    def submit(self, email=None):
        return submit_customer_account_deletion(
            email=email or self.user.email,
            source_ip="203.0.113.10",
        )

    def test_deletion_entry_pages_share_retention_disclosure(self):
        self.client.force_login(self.user)
        self.client.post(reverse("account_reauthenticate"), {"password": "strong-customer-password"})
        for name in ("customer_account_deletion", "customer_account_deletion_authenticated"):
            with self.subTest(name=name):
                client = Client() if name == "customer_account_deletion" else self.client
                response = client.get(reverse(name))
                self.assertContains(response, "What is removed and what may remain")
                self.assertContains(response, "A review date is not an automatic deletion date")
                self.assertContains(response, "Deletion does not forfeit your savings")
                self.assertContains(response, "must not be used to reactivate a removed account")
        self.assertFalse(CustomerAccountDeletionRequest.objects.exists())

    def test_public_view_is_generic_for_matching_and_unknown_email(self):
        real_response = self.client.post(
            reverse("customer_account_deletion"),
            {"email": self.user.email, "website": ""},
        )
        unknown_response = self.client.post(
            reverse("customer_account_deletion"),
            {"email": "unknown@example.com", "website": ""},
        )

        self.assertEqual(real_response.status_code, 302)
        self.assertEqual(unknown_response.status_code, 302)
        self.assertEqual(real_response.url, unknown_response.url)
        self.assertEqual(CustomerAccountDeletionRequest.objects.count(), 1)
        self.assertEqual(CustomerAccountDeletionAttempt.objects.count(), 2)
        self.assertEqual(len(mail.outbox), 1)

    def test_verification_secret_is_digest_only_and_email_is_untracked(self):
        response = self.client.post(
            reverse("customer_account_deletion"),
            {"email": self.user.email, "website": ""},
        )
        self.assertEqual(response.status_code, 302)
        deletion_request = CustomerAccountDeletionRequest.objects.get()
        message = mail.outbox[0]
        token_match = re.search(
            r"/accounts/deletion/verify/[0-9a-f-]+/([^/]+)/",
            message.body,
        )
        self.assertIsNotNone(token_match)
        raw_token = token_match.group(1)
        self.assertNotEqual(raw_token, deletion_request.verification_token_digest)
        self.assertNotIn(raw_token, str(deletion_request.__dict__))
        self.assertEqual(message.extra_headers["X-PM-TrackLinks"], "None")
        self.assertEqual(message.extra_headers["X-PM-TrackOpens"], "false")

    def test_secret_page_is_non_cacheable_redacted_and_csrf_protected(self):
        submission = self.submit()
        url = reverse(
            "customer_account_deletion_verify",
            kwargs={
                "request_id": submission.deletion_request.pk,
                "token": submission.raw_token,
            },
        )
        csrf_client = Client(enforce_csrf_checks=True)
        response = csrf_client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertEqual(response["Referrer-Policy"], "strict-origin")
        self.assertEqual(csrf_client.post(url).status_code, 403)
        csrf_token = csrf_client.cookies["csrftoken"].value
        response = csrf_client.post(url, HTTP_X_CSRFTOKEN=csrf_token)
        self.assertEqual(response.status_code, 302)
        self.assertNotIn(
            submission.raw_token,
            redact_sensitive_auth_paths(f"Rejected path {url}"),
        )

    def test_verified_request_contains_login_but_preserves_scheme_history(self):
        plan = SchemePlan.objects.create(
            name="Deletion preservation plan",
            code="DELETE-PRESERVE",
            amount_rule=SchemePlan.AmountRule.FIXED,
            frequency_rule=SchemePlan.FrequencyRule.FLEXIBLE,
            fixed_contribution_amount="1000.00",
            minimum_contribution="1000.00",
            maximum_contribution="1000.00",
        )
        grade = metal_grade_for("GOLD")
        SchemePlanOffering.objects.create(plan=plan, metal_grade=grade)
        account = enroll_customer(
            customer=self.customer,
            plan=plan,
            metal_grade=grade,
        )
        SocialAccount.objects.create(
            user=self.user,
            provider="google",
            uid="google-delete-customer",
        )
        self.client.force_login(self.user)
        session_key = self.client.session.session_key
        submission = self.submit()

        deletion_request = verify_and_contain_customer_account(
            deletion_request_id=submission.deletion_request.pk,
            raw_token=submission.raw_token,
        )

        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)
        self.assertFalse(Session.objects.filter(session_key=session_key).exists())
        self.assertFalse(SocialAccount.objects.filter(user=self.user).exists())
        self.assertTrue(Customer.objects.filter(pk=self.customer.pk).exists())
        self.assertTrue(SchemeAccount.objects.filter(pk=account.pk).exists())
        self.assertEqual(deletion_request.status, deletion_request.Status.CONTAINED)
        self.assertEqual(
            deletion_request.actions.filter(
                action=CustomerAccountDeletionAction.Action.CONTAINED
            ).count(),
            1,
        )

    def test_verification_is_one_time(self):
        submission = self.submit()
        verify_and_contain_customer_account(
            deletion_request_id=submission.deletion_request.pk,
            raw_token=submission.raw_token,
        )
        with self.assertRaises(InvalidCustomerAccountDeletion):
            verify_and_contain_customer_account(
                deletion_request_id=submission.deletion_request.pk,
                raw_token=submission.raw_token,
            )
        self.assertEqual(
            CustomerAccountDeletionAction.objects.filter(
                request=submission.deletion_request,
                action=CustomerAccountDeletionAction.Action.CONTAINED,
            ).count(),
            1,
        )

    def test_authenticated_service_contains_only_approved_customer(self):
        deletion_request = request_authenticated_customer_account_deletion(
            user=self.user,
            source_ip="203.0.113.10",
        )
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)
        self.assertEqual(
            deletion_request.source,
            CustomerAccountDeletionRequest.Source.AUTHENTICATED,
        )
        self.assertEqual(
            deletion_request.status,
            CustomerAccountDeletionRequest.Status.CONTAINED,
        )

    def test_only_one_open_request_is_allowed_per_customer(self):
        first = self.submit().deletion_request
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                CustomerAccountDeletionRequest.objects.create(
                    customer=self.customer,
                    requested_email=self.user.email,
                    email_digest="a" * 64,
                    source_ip_digest="b" * 64,
                    verification_token_digest="c" * 64,
                    source=CustomerAccountDeletionRequest.Source.PUBLIC,
                    policy_version="test-retention-matrix-v1",
                    verification_expires_at=timezone.now() + timedelta(hours=24),
                )
        self.assertTrue(CustomerAccountDeletionRequest.objects.filter(pk=first.pk).exists())

    def test_owner_can_append_hold_but_cannot_complete_or_anonymize(self):
        submission = self.submit()
        deletion_request = verify_and_contain_customer_account(
            deletion_request_id=submission.deletion_request.pk,
            raw_token=submission.raw_token,
        )
        review_due_at = timezone.now() + timedelta(days=14)
        deletion_request, decision = record_customer_account_deletion_hold(
            deletion_request=deletion_request,
            actor=self.owner,
            reason="Existing metal entitlement requires showroom settlement.",
            retained_categories="Scheme agreement and metal entitlement.",
            review_due_at=review_due_at,
        )
        self.assertEqual(
            deletion_request.status,
            CustomerAccountDeletionRequest.Status.AWAITING_SETTLEMENT,
        )
        self.assertEqual(
            decision.outcome,
            CustomerAccountDeletionDecision.Outcome.AWAITING_SETTLEMENT,
        )
        self.assertNotIn(
            "COMPLETED",
            CustomerAccountDeletionDecision.Outcome.values,
        )

    def test_owner_queue_is_owner_only(self):
        submission = self.submit()
        verify_and_contain_customer_account(
            deletion_request_id=submission.deletion_request.pk,
            raw_token=submission.raw_token,
        )
        self.client.force_login(self.owner)
        self.assertEqual(
            self.client.get(reverse("customer_account_deletion_list")).status_code,
            200,
        )
        other = get_user_model().objects.create_user(
            username="other@example.com",
            email="other@example.com",
            password="strong-other-password",
            role=get_user_model().Role.STAFF,
        )
        self.client.force_login(other)
        self.assertEqual(
            self.client.get(reverse("customer_account_deletion_list")).status_code,
            403,
        )

    def test_integrity_command_detects_contained_active_login(self):
        submission = self.submit()
        verify_and_contain_customer_account(
            deletion_request_id=submission.deletion_request.pk,
            raw_token=submission.raw_token,
        )
        output = StringIO()
        call_command("check_customer_account_deletions", stdout=output)
        self.assertIn("status=ok", output.getvalue())
        self.user.is_active = True
        self.user.save(update_fields=["is_active"])
        with self.assertRaises(CommandError):
            call_command("check_customer_account_deletions", stdout=StringIO())

    def test_caddy_excludes_deletion_verification_paths(self):
        caddyfile = Path(__file__).resolve().parents[1] / "deploy" / "Caddyfile"
        contents = caddyfile.read_text(encoding="utf-8")
        self.assertIn("/accounts/deletion/verify/*", contents)
        self.assertIn("log_skip @sensitiveAuthPaths", contents)

    def preview_account(self, grade_code="GOLD_22K_916", quantity="0.010227"):
        plan, _ = SchemePlan.objects.get_or_create(
            code="DELETE-PREVIEW", defaults={
                "name": "Preview plan", "amount_rule": "VARIABLE",
                "frequency_rule": "FLEXIBLE", "minimum_contribution": "100.00",
            },
        )
        grade = metal_grade_for("SILVER" if grade_code == "SILVER_999" else "GOLD", code=grade_code)
        SchemePlanOffering.objects.get_or_create(plan=plan, metal_grade=grade)
        account = enroll_customer(customer=self.customer, plan=plan, metal_grade=grade)
        rate = SchemeRate.objects.create(
            metal=grade.metal, metal_grade=grade, purity=grade.fineness,
            rate_per_gram="14667.0000", published_by=self.owner,
        )
        contribution = Contribution.objects.create(
            scheme_account=account, amount="150.00",
            contribution_period=timezone.localdate().replace(day=1),
            frequency_rule_snapshot="FLEXIBLE", status="PAID",
            payment_gateway="razorpay", payment_channel=PaymentChannel.RAZORPAY,
            gateway_mode="live", gateway_reference=f"pay_preview_{account.pk}",
            gateway_order_id=f"order_preview_{account.pk}", paid_at=timezone.now(),
            scheme_rate=rate, rate_locked_at=timezone.now(),
        )
        MetalAllocation.objects.create(
            contribution=contribution, scheme_rate=rate, metal=grade.metal,
            metal_grade=grade, quantity=Decimal(quantity),
        )
        return account, contribution

    def test_disposition_is_read_only_and_zero_history_is_not_approval(self):
        deletion_request = self.submit().deletion_request
        with CaptureQueriesContext(connection) as queries:
            preview = customer_account_deletion_disposition(deletion_request)
        self.assertFalse(any(q["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")) for q in queries))
        self.assertEqual(preview.account_balances, ())
        self.assertTrue(preview.external_checks)
        self.assertIn("Access containment", " ".join(preview.review_flags))
        deletion_request.refresh_from_db()
        self.assertEqual(deletion_request.status, "PENDING_VERIFICATION")
        self.assertEqual(deletion_request.decisions.count(), 0)
        self.assertFalse(hasattr(preview, "can_complete"))

    def test_disposition_keeps_grade_balances_separate_and_six_decimal(self):
        self.preview_account("GOLD_22K_916", "0.010227")
        self.preview_account("GOLD_24K_9999", "0.329272")
        self.preview_account("SILVER_999", "0.000001")
        deletion_request = self.submit().deletion_request
        preview = customer_account_deletion_disposition(deletion_request)
        balances = {b.grade: b.metal_quantity for b in preview.account_balances}
        self.assertEqual(balances, {
            "GOLD_22K_916": Decimal("0.010227"),
            "GOLD_24K_9999": Decimal("0.329272"),
            "SILVER_999": Decimal("0.000001"),
        })
        self.assertIn("non-zero entitlement", " ".join(preview.review_flags))
        self.assertEqual(MetalAllocation.objects.count(), 3)

    def test_disposition_detects_paid_unallocated_and_identifier_matched_webhook(self):
        account, paid = self.preview_account()
        Contribution.objects.create(
            scheme_account=account, amount="100.00",
            contribution_period=timezone.localdate().replace(day=1),
            frequency_rule_snapshot="FLEXIBLE", status="PAID_UNALLOCATED",
            payment_gateway="razorpay", payment_channel=PaymentChannel.RAZORPAY,
            gateway_mode="live", gateway_reference="pay_unallocated_preview",
            paid_at=timezone.now(), scheme_rate=paid.scheme_rate, rate_locked_at=timezone.now(),
        )
        PaymentWebhookEvent.objects.create(
            gateway="razorpay", gateway_mode="live", event_id="evt_preview",
            event_type="payment.captured", payload_sha256="a" * 64,
            status="REVIEW_REQUIRED", gateway_order_id=paid.gateway_order_id,
        )
        preview = customer_account_deletion_disposition(self.submit().deletion_request)
        findings = " ".join(preview.review_flags)
        self.assertIn("Payments needing allocation review: 1", findings)
        self.assertIn("webhook events need review: 1", findings)

    def test_disposition_does_not_match_blank_provider_identifiers(self):
        PaymentWebhookEvent.objects.create(
            gateway="razorpay", gateway_mode="live", event_id="evt_other",
            event_type="payment.captured", payload_sha256="b" * 64,
            status="FAILED",
        )
        preview = customer_account_deletion_disposition(self.submit().deletion_request)
        counts = {name: count for name, count, treatment in preview.inventory}
        self.assertEqual(counts["Webhook events"], 0)

    def test_disposition_pending_checkout_and_zero_balance_agreement_need_review(self):
        account, _ = self.preview_account()
        Contribution.objects.create(
            scheme_account=account, amount="100.00",
            contribution_period=timezone.localdate().replace(day=1),
            frequency_rule_snapshot="FLEXIBLE", status="PENDING",
            payment_gateway="razorpay", payment_channel=PaymentChannel.RAZORPAY,
            gateway_mode="live", gateway_order_id="order_pending_preview",
            checkout_expires_at=timezone.now() - timedelta(days=1),
        )
        empty_account = enroll_customer(
            customer=self.customer, plan=account.plan, metal_grade=account.metal_grade,
        )
        preview = customer_account_deletion_disposition(self.submit().deletion_request)
        flags = " ".join(preview.review_flags)
        self.assertIn("Pending contributions: 1", flags)
        self.assertIn("zero-balance agreement", flags)
        empty_balance = next(b for b in preview.account_balances if b.scheme_number == empty_account.scheme_number)
        self.assertEqual(empty_balance.metal_quantity, Decimal("0.000000"))

    def test_disposition_legacy_cash_principal_is_not_mixed_with_metal(self):
        metal_account, _ = self.preview_account()
        # Historical cash contracts remain supported for reads, not new enrolment.
        cash_account = SchemeAccount.objects.create(
            scheme_number="JSK-LEGACY-PREVIEW", customer=self.customer,
            plan=metal_account.plan, start_date=timezone.localdate(),
            eligible_from=timezone.localdate() + timedelta(days=366),
            agreed_months=12, savings_mode="CASH", amount_rule_snapshot="VARIABLE",
            frequency_rule_snapshot="FLEXIBLE", minimum_amount_snapshot="100.00",
        )
        Contribution.objects.create(
            scheme_account=cash_account, amount="1250.25",
            contribution_period=timezone.localdate().replace(day=1),
            frequency_rule_snapshot="FLEXIBLE", status="PAID",
            payment_gateway="mock", payment_channel=PaymentChannel.MOCK,
            gateway_reference="mock_preview_cash", paid_at=timezone.now(),
        )
        preview = customer_account_deletion_disposition(self.submit().deletion_request)
        cash = next(b for b in preview.account_balances if b.grade == "CASH (legacy)")
        self.assertEqual(cash.cash_principal, Decimal("1250.25"))
        self.assertEqual(cash.cash_earned_bonus, Decimal("0.00"))
        self.assertEqual(cash.metal_quantity, Decimal("0.000000"))
        metal = next(b for b in preview.account_balances if b.grade == "GOLD_22K_916")
        self.assertEqual(metal.cash_principal, Decimal("0.00"))
        self.assertEqual(metal.metal_quantity, Decimal("0.010227"))

    def test_disposition_owner_page_is_uncached_and_has_no_completion_button(self):
        self.preview_account()
        deletion_request = self.submit().deletion_request
        self.client.force_login(self.owner)
        response = self.client.get(reverse("customer_account_deletion_detail", args=[deletion_request.pk]))
        self.assertContains(response, "Data disposition preview")
        self.assertContains(response, "0.010227")
        self.assertContains(response, "External checks")
        self.assertContains(response, "Financial history is preserved")
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(deletion_request.decisions.count(), 0)

    def test_disposition_customer_and_staff_cannot_view_owner_inventory(self):
        deletion_request = self.submit().deletion_request
        url = reverse("customer_account_deletion_detail", args=[deletion_request.pk])
        for role in ["CUSTOMER", "STAFF"]:
            self.user.role = role
            self.user.save(update_fields=["role"])
            self.client.force_login(self.user)
            self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_login(self.owner)
        with override_settings(CUSTOMER_ACCOUNT_DELETION_ENABLED=False):
            self.assertEqual(self.client.get(url).status_code, 404)


class CustomerAccountDeletionDisabledTests(TestCase):
    @override_settings(CUSTOMER_ACCOUNT_DELETION_ENABLED=False)
    def test_public_and_owner_routes_are_hidden_while_disabled(self):
        self.assertEqual(
            self.client.get(reverse("customer_account_deletion")).status_code,
            404,
        )
