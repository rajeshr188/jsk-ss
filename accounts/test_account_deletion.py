import re
from datetime import timedelta
from io import StringIO
from pathlib import Path

from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount
from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.core import mail
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, transaction
from django.test import Client, TestCase, override_settings
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
from schemes.models import Customer, SchemeAccount, SchemePlan, SchemePlanOffering
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


class CustomerAccountDeletionDisabledTests(TestCase):
    @override_settings(CUSTOMER_ACCOUNT_DELETION_ENABLED=False)
    def test_public_and_owner_routes_are_hidden_while_disabled(self):
        self.assertEqual(
            self.client.get(reverse("customer_account_deletion")).status_code,
            404,
        )
