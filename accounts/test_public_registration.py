from datetime import timedelta
from io import StringIO
from pathlib import Path
import re

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import (
    CustomerInvitation,
    CustomerRegistration,
    CustomerRegistrationAttempt,
)
from accounts.checks import public_registration_configuration
from accounts.services import (
    submit_customer_registration,
    verify_customer_registration_email,
)
from schemes.models import Customer, SchemeAccount
from schemes.services import create_customer


REGISTRATION_SETTINGS = {
    "PUBLIC_CUSTOMER_REGISTRATION_ENABLED": True,
    "PUBLIC_REGISTRATION_EMAIL_EXPIRY_HOURS": 24,
    "PUBLIC_REGISTRATION_ATTEMPTS_PER_HOUR": 5,
    "PUBLIC_REGISTRATION_TERMS_VERSION": "terms-test-v1",
    "PUBLIC_REGISTRATION_PRIVACY_VERSION": "privacy-test-v1",
    "EMAIL_BACKEND": "django.core.mail.backends.locmem.EmailBackend",
}


def registration_data(**overrides):
    data = {
        "full_name": "Meera Gupta",
        "email": "Meera@Example.com",
        "mobile_number": "99887 76655",
        "address": "12 Market Road, Vellore",
        "accept_policies": "on",
        "website": "",
    }
    data.update(overrides)
    return data


def submit_application(**overrides):
    values = registration_data(**overrides)
    return submit_customer_registration(
        full_name=values["full_name"],
        email=values["email"],
        mobile_number=values["mobile_number"],
        address=values["address"],
        source_ip=values.get("source_ip", "203.0.113.10"),
    )


@override_settings(**REGISTRATION_SETTINGS)
class PublicCustomerRegistrationTests(TestCase):
    def test_feature_is_fail_closed_by_default(self):
        with override_settings(PUBLIC_CUSTOMER_REGISTRATION_ENABLED=False):
            response = self.client.get(reverse("customer_registration"))

        self.assertEqual(response.status_code, 404)

    def test_allauth_direct_signup_stays_closed_when_requests_are_enabled(self):
        response = self.client.get(reverse("account_signup"))

        self.assertContains(response, "Sign Up Closed")
        self.assertContains(response, reverse("customer_registration"))

    def test_submission_records_profile_consent_and_sends_untracked_verification(self):
        response = self.client.post(
            reverse("customer_registration"),
            registration_data(),
            REMOTE_ADDR="203.0.113.10",
        )

        self.assertRedirects(response, reverse("customer_registration_submitted"))
        application = CustomerRegistration.objects.get()
        self.assertEqual(application.full_name, "Meera Gupta")
        self.assertEqual(application.email, "meera@example.com")
        self.assertEqual(application.mobile_number, "+919988776655")
        self.assertEqual(application.terms_version, "terms-test-v1")
        self.assertEqual(application.privacy_version, "privacy-test-v1")
        self.assertIsNotNone(application.consent_accepted_at)
        self.assertEqual(
            application.status,
            CustomerRegistration.Status.PENDING_EMAIL_VERIFICATION,
        )
        self.assertEqual(CustomerRegistrationAttempt.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].extra_headers["X-PM-TrackLinks"], "None")
        self.assertEqual(mail.outbox[0].extra_headers["X-PM-TrackOpens"], "false")
        verification_url = re.search(
            r"https?://[^\s]+/accounts/registrations/verify/[^\s]+",
            mail.outbox[0].body,
        ).group(0)
        raw_token = verification_url.rstrip("/").split("/")[-1]
        self.assertNotEqual(application.email_token_digest, raw_token)
        self.assertNotIn(raw_token, str(application.__dict__))
        self.assertFalse(get_user_model().objects.filter(email=application.email).exists())
        self.assertFalse(Customer.objects.exists())
        self.assertFalse(SchemeAccount.objects.exists())

    def test_verification_requires_explicit_post_and_creates_no_login_or_scheme(self):
        self.client.post(reverse("customer_registration"), registration_data())
        application = CustomerRegistration.objects.get()
        verification_path = re.search(
            r"/accounts/registrations/verify/[^\s]+",
            mail.outbox[0].body,
        ).group(0)

        get_response = self.client.get(verification_path)
        application.refresh_from_db()
        self.assertEqual(get_response.status_code, 200)
        self.assertEqual(get_response["Cache-Control"], "no-store")
        self.assertEqual(get_response["Referrer-Policy"], "strict-origin")
        self.assertIsNone(application.email_verified_at)

        response = self.client.post(verification_path)
        self.assertRedirects(response, reverse("customer_registration_verified"))
        application.refresh_from_db()
        self.assertEqual(
            application.status,
            CustomerRegistration.Status.AWAITING_OWNER_APPROVAL,
        )
        self.assertIsNotNone(application.email_verified_at)
        self.assertFalse(get_user_model().objects.filter(email=application.email).exists())
        self.assertFalse(SchemeAccount.objects.exists())

    def test_verification_rejects_null_origin_but_accepts_same_origin(self):
        self.client.post(reverse("customer_registration"), registration_data())
        verification_path = re.search(
            r"/accounts/registrations/verify/[^\s]+",
            mail.outbox[0].body,
        ).group(0)
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.get(verification_path, secure=True)
        csrf_token = csrf_client.cookies["csrftoken"].value

        rejected = csrf_client.post(
            verification_path,
            secure=True,
            HTTP_ORIGIN="null",
            HTTP_X_CSRFTOKEN=csrf_token,
        )
        self.assertEqual(rejected.status_code, 403)

        accepted = csrf_client.post(
            verification_path,
            secure=True,
            HTTP_ORIGIN="https://testserver",
            HTTP_X_CSRFTOKEN=csrf_token,
        )
        self.assertRedirects(accepted, reverse("customer_registration_verified"))

    def test_expired_verification_is_unavailable(self):
        submission = submit_application()
        application = submission.application
        application.email_verification_expires_at = timezone.now() - timedelta(seconds=1)
        application.save(update_fields=["email_verification_expires_at"])
        url = reverse(
            "customer_registration_verify",
            args=[application.pk, submission.raw_token],
        )

        response = self.client.post(url)

        self.assertContains(response, "Verification unavailable")
        application.refresh_from_db()
        self.assertEqual(
            application.status,
            CustomerRegistration.Status.PENDING_EMAIL_VERIFICATION,
        )

    def test_existing_identity_gets_same_generic_response_without_email(self):
        get_user_model().objects.create_user(
            username="meera@example.com",
            email="meera@example.com",
        )

        response = self.client.post(
            reverse("customer_registration"),
            registration_data(),
        )

        self.assertRedirects(response, reverse("customer_registration_submitted"))
        self.assertContains(
            self.client.get(reverse("customer_registration_submitted")),
            "Existing, duplicate, or rate-limited requests receive the same response",
        )
        self.assertFalse(CustomerRegistration.objects.exists())
        self.assertEqual(CustomerRegistrationAttempt.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 0)

    def test_existing_mobile_gets_generic_response_without_creating_application(self):
        create_customer(
            full_name="Existing Customer",
            email="existing@example.com",
            mobile_number="9988776655",
            password="existing-customer-password",
        )

        response = self.client.post(
            reverse("customer_registration"),
            registration_data(email="different@example.com"),
        )

        self.assertRedirects(response, reverse("customer_registration_submitted"))
        self.assertFalse(CustomerRegistration.objects.exists())
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(PUBLIC_REGISTRATION_ATTEMPTS_PER_HOUR=1)
    def test_database_backed_rate_limit_stops_additional_requests(self):
        first = self.client.post(
            reverse("customer_registration"),
            registration_data(),
            REMOTE_ADDR="203.0.113.10",
        )
        second = self.client.post(
            reverse("customer_registration"),
            registration_data(
                email="second@example.com",
                mobile_number="9876543210",
            ),
            REMOTE_ADDR="203.0.113.10",
        )

        self.assertEqual(first.status_code, 302)
        self.assertEqual(second.status_code, 302)
        self.assertEqual(CustomerRegistration.objects.count(), 1)
        self.assertEqual(CustomerRegistrationAttempt.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 1)

    def test_honeypot_returns_generic_response_without_persisting(self):
        response = self.client.post(
            reverse("customer_registration"),
            registration_data(website="https://spam.invalid"),
        )

        self.assertRedirects(response, reverse("customer_registration_submitted"))
        self.assertFalse(CustomerRegistration.objects.exists())
        self.assertFalse(CustomerRegistrationAttempt.objects.exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_old_abuse_attempt_digests_are_pruned_on_submission(self):
        old = CustomerRegistrationAttempt.objects.create(
            email_digest="a" * 64,
            mobile_digest="b" * 64,
            source_ip_digest="c" * 64,
            outcome=CustomerRegistrationAttempt.Outcome.IGNORED,
        )
        CustomerRegistrationAttempt.objects.filter(pk=old.pk).update(
            attempted_at=timezone.now() - timedelta(hours=25)
        )

        submit_application()

        self.assertFalse(CustomerRegistrationAttempt.objects.filter(pk=old.pk).exists())

    def test_complete_profile_and_consent_are_required(self):
        response = self.client.post(
            reverse("customer_registration"),
            registration_data(address="", accept_policies=""),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This field is required", count=2)
        self.assertFalse(CustomerRegistration.objects.exists())


@override_settings(**REGISTRATION_SETTINGS)
class CustomerRegistrationOwnerReviewTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(
            username="owner@example.com",
            email="owner@example.com",
            password="owner-password-strong",
            role=user_model.Role.OWNER,
        )
        self.customer_user = user_model.objects.create_user(
            username="customer@example.com",
            email="customer@example.com",
            password="customer-password-strong",
            role=user_model.Role.CUSTOMER,
        )
        submission = submit_application()
        self.application = verify_customer_registration_email(
            application_id=submission.application.pk,
            raw_token=submission.raw_token,
        )

    def test_only_owner_can_view_registration_queue(self):
        self.client.force_login(self.customer_user)
        self.assertEqual(
            self.client.get(reverse("customer_registration_list")).status_code,
            403,
        )

        self.client.force_login(self.owner)
        response = self.client.get(reverse("customer_registration_list"))
        self.assertContains(response, "Meera Gupta")
        self.assertContains(response, "Awaiting owner approval")

    def test_approval_requires_mobile_confirmation_and_reason(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("customer_registration_approve", args=[self.application.pk]),
            {"reason": "Identity checked by phone."},
        )

        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "This field is required", status_code=400)
        self.application.refresh_from_db()
        self.assertEqual(
            self.application.status,
            CustomerRegistration.Status.AWAITING_OWNER_APPROVAL,
        )
        self.assertFalse(Customer.objects.exists())

    def test_approval_creates_invited_customer_but_no_scheme(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("customer_registration_approve", args=[self.application.pk]),
            {
                "mobile_verified": "on",
                "reason": "Called the applicant and verified contact details.",
            },
        )

        customer = Customer.objects.get(email="meera@example.com")
        self.assertRedirects(
            response,
            reverse("schemes:customer_detail", args=[customer.pk]),
        )
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, CustomerRegistration.Status.APPROVED)
        self.assertEqual(self.application.approved_user, customer.user)
        self.assertEqual(self.application.reviewed_by, self.owner)
        self.assertIsNotNone(self.application.mobile_verified_at)
        self.assertFalse(customer.user.has_usable_password())
        self.assertEqual(CustomerInvitation.objects.filter(user=customer.user).count(), 1)
        self.assertEqual(customer.scheme_accounts.count(), 0)
        self.assertEqual(SchemeAccount.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/accounts/invitations/", mail.outbox[0].body)
        output = StringIO()
        call_command(
            "check_public_customer_registrations",
            stdout=output,
        )
        self.assertIn("status=ok", output.getvalue())
        self.assertIn("approved=1", output.getvalue())

    def test_rejection_records_review_without_creating_identity(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("customer_registration_reject", args=[self.application.pk]),
            {"reason": "Applicant could not be verified."},
        )

        self.assertRedirects(response, reverse("customer_registration_list"))
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, CustomerRegistration.Status.REJECTED)
        self.assertEqual(self.application.reviewed_by, self.owner)
        self.assertEqual(
            self.application.review_reason,
            "Applicant could not be verified.",
        )
        self.assertIsNone(self.application.approved_user)
        self.assertFalse(Customer.objects.exists())
        self.assertFalse(SchemeAccount.objects.exists())

    def test_approval_rechecks_identity_conflicts(self):
        get_user_model().objects.create_user(
            username="later@example.com",
            email=self.application.email,
        )
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("customer_registration_approve", args=[self.application.pk]),
            {
                "mobile_verified": "on",
                "reason": "Attempted approval after verification.",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "login with this email now exists", status_code=400)
        self.application.refresh_from_db()
        self.assertEqual(
            self.application.status,
            CustomerRegistration.Status.AWAITING_OWNER_APPROVAL,
        )
        self.assertFalse(Customer.objects.exists())


@override_settings(**REGISTRATION_SETTINGS)
class CustomerRegistrationConstraintTests(TestCase):
    def test_only_one_active_application_exists_per_email(self):
        first = submit_application()

        with self.assertRaises(IntegrityError), transaction.atomic():
            CustomerRegistration.objects.create(
                full_name="Duplicate Applicant",
                email=first.application.email.upper(),
                mobile_number="+919876543210",
                address="Another complete address",
                email_token_digest="f" * 64,
                email_verification_expires_at=timezone.now() + timedelta(hours=1),
                terms_version="terms-test-v1",
                privacy_version="privacy-test-v1",
                consent_accepted_at=timezone.now(),
                source_ip_digest="e" * 64,
            )

    def test_database_rejects_approved_state_without_review_evidence(self):
        submission = submit_application()
        application = submission.application

        with self.assertRaises(IntegrityError), transaction.atomic():
            CustomerRegistration.objects.filter(pk=application.pk).update(
                status=CustomerRegistration.Status.APPROVED
            )


class PublicRegistrationConfigurationCheckTests(TestCase):
    @override_settings(
        PUBLIC_CUSTOMER_REGISTRATION_ENABLED=True,
        DEFAULT_FROM_EMAIL="noreply@example.com",
    )
    def test_owned_domain_sender_is_required_before_enablement(self):
        issues = public_registration_configuration(None)

        self.assertEqual([issue.id for issue in issues], ["jsk.E017"])


class PublicRegistrationSecretBoundaryTests(SimpleTestCase):
    def test_caddy_excludes_registration_verification_tokens_from_access_logs(self):
        caddyfile = Path(__file__).resolve().parents[1] / "deploy" / "Caddyfile"

        contents = caddyfile.read_text(encoding="utf-8")

        self.assertIn("/accounts/registrations/verify/*", contents)
        self.assertIn("log_skip @sensitiveAuthPaths", contents)
