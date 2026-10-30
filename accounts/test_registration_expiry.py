"""Explicit owner expiry never grants access, erases identity or changes finances."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from importlib import import_module
from types import SimpleNamespace

from django.apps import apps
from django.core import mail
from django.core.exceptions import ValidationError
from django.db import IntegrityError, close_old_connections, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import CustomUser, CustomerRegistration, PlanApplication
from accounts.registration_selectors import registration_expiry_review
from accounts.services import (
    expire_customer_registration, issue_registration_verification,
    registration_is_verifiable, verify_customer_registration_email,
)
from accounts.test_public_registration import REGISTRATION_SETTINGS, submit_application
from schemes.models import MetalGrade
from schemes.selectors import get_owner_application_stage_counts
from schemes.tests.test_audit_exceptions import make_owner, make_plan


class ExpiryFixture:
    def make_expired(self):
        submission = submit_application()
        application = submission.application
        application.email_verification_expires_at = timezone.now() - timedelta(days=1)
        application.save(update_fields=["email_verification_expires_at"])
        return application, submission.raw_token

    def expire(self, application, **changes):
        args = {"application": application, "reviewed_by": self.owner, "reason": "Expired unverified application reviewed by owner.",
                "confirmed": True, "expected_digest": registration_expiry_review(application)["expected_digest"]}
        return expire_customer_registration(**(args | changes))


@override_settings(**REGISTRATION_SETTINGS)
class RegistrationExpiryTests(ExpiryFixture, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = make_owner()

    def test_expiry_records_decision_moves_queue_and_preserves_all_other_records(self):
        application, raw_token = self.make_expired()
        before = {m._meta.label: list(m.objects.order_by("pk").values()) for m in apps.get_app_config("schemes").get_models()}
        users = list(CustomUser.objects.order_by("pk").values())
        mail_before = len(mail.outbox)
        self.assertEqual(get_owner_application_stage_counts()["attention"], 1)
        result, changed = self.expire(application)
        self.assertTrue(changed)
        self.assertEqual(result.status, "EXPIRED")
        self.assertEqual(result.reviewed_by_id, self.owner.pk)
        self.assertEqual(result.reviewed_by_label, self.owner.email)
        self.assertIsNotNone(result.reviewed_at)
        self.assertIsNone(result.email_verified_at)
        self.assertIsNone(result.approved_user_id)
        self.assertFalse(registration_is_verifiable(result, raw_token))
        self.assertEqual(get_owner_application_stage_counts()["attention"], 0)
        self.assertEqual(get_owner_application_stage_counts()["closed"], 1)
        self.assertEqual(mail_before, len(mail.outbox))
        self.assertEqual(users, list(CustomUser.objects.order_by("pk").values()))
        self.assertEqual(before, {m._meta.label: list(m.objects.order_by("pk").values()) for m in apps.get_app_config("schemes").get_models()})

    def test_exact_retry_is_read_only_and_changed_decision_is_rejected(self):
        application, _ = self.make_expired()
        digest = registration_expiry_review(application)["expected_digest"]
        result, _ = self.expire(application, expected_digest=digest)
        before = CustomerRegistration.objects.values().get(pk=application.pk)
        result, changed = self.expire(application, expected_digest=digest)
        self.assertFalse(changed)
        self.assertEqual(before, CustomerRegistration.objects.values().get(pk=application.pk))
        with self.assertRaises(ValidationError):
            self.expire(application, reason="Replace decision after expiry")

    def test_confirmation_reason_owner_and_fresh_evidence_are_required(self):
        application, _ = self.make_expired()
        before = CustomerRegistration.objects.values().get(pk=application.pk)
        for changes in [{"confirmed": False}, {"confirmed": 1}, {"reason": " "}, {"reason": "x" * 501},
                        {"expected_digest": "invalid"}, {"expected_digest": None}, {"reviewed_by": None}]:
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                self.expire(application, **changes)
        self.assertEqual(before, CustomerRegistration.objects.values().get(pk=application.pk))

    def test_resend_invalidates_a_previously_opened_expiry_form(self):
        application, _ = self.make_expired()
        digest = registration_expiry_review(application)["expected_digest"]
        fresh, raw = issue_registration_verification(application=application, actor=self.owner)
        with self.assertRaises(ValidationError):
            self.expire(application, expected_digest=digest)
        fresh.refresh_from_db()
        self.assertEqual(fresh.status, "PENDING_EMAIL_VERIFICATION")
        self.assertTrue(registration_is_verifiable(fresh, raw))
        self.assertIsNone(fresh.reviewed_at)

    def test_verified_identity_cannot_be_expired_even_when_old_email_deadline_passed(self):
        submission = submit_application()
        verified = verify_customer_registration_email(application_id=submission.application.pk, raw_token=submission.raw_token)
        verified.email_verification_expires_at = timezone.now() - timedelta(days=1)
        verified.save(update_fields=["email_verification_expires_at"])
        with self.assertRaises(ValidationError): self.expire(verified)
        verified.refresh_from_db()
        self.assertEqual(verified.status, "AWAITING_OWNER_APPROVAL")

    def test_linked_plan_application_uses_coordinated_review(self):
        application, _ = self.make_expired()
        plan = make_plan()
        PlanApplication.objects.create(registration=application, plan=plan,
            metal_grade=MetalGrade.objects.get(code="GOLD_22K_916"), requested_amount=Decimal("500"),
            requested_months=12, expires_at=timezone.now() + timedelta(days=5))
        with self.assertRaisesMessage(ValidationError, "coordinated plan"):
            self.expire(application)
        application.refresh_from_db()
        self.assertEqual(application.status, "PENDING_EMAIL_VERIFICATION")

    def test_fresh_application_can_follow_expiry_without_rewriting_the_old_decision(self):
        application, _ = self.make_expired()
        self.expire(application)
        before = CustomerRegistration.objects.values().get(pk=application.pk)
        replacement = submit_application()
        self.assertIsNotNone(replacement.application)
        self.assertNotEqual(replacement.application.pk, application.pk)
        self.assertEqual(before, CustomerRegistration.objects.values().get(pk=application.pk))

    def test_database_accepts_automatic_or_reviewed_expiry_but_refuses_partial_audit(self):
        application, _ = self.make_expired()
        CustomerRegistration.objects.filter(pk=application.pk).update(status="EXPIRED")
        application.refresh_from_db()
        self.assertIsNone(application.reviewed_at)
        with self.assertRaises(IntegrityError), transaction.atomic():
            CustomerRegistration.objects.filter(pk=application.pk).update(review_reason="Unattributed decision")
        CustomerRegistration.objects.filter(pk=application.pk).update(status="PENDING_EMAIL_VERIFICATION")
        application.refresh_from_db()
        self.expire(application)
        application.refresh_from_db()
        with self.assertRaises(IntegrityError), transaction.atomic():
            CustomerRegistration.objects.filter(pk=application.pk).update(email_verified_at=timezone.now())
        migration = import_module("accounts.migrations.0010_owner_registration_expiry")
        with self.assertRaisesMessage(RuntimeError, "Retain this schema"):
            migration.refuse_reverse_reviewed_expiry(apps, SimpleNamespace(connection=connection))

    def test_http_owner_review_is_get_read_only_csrf_protected_and_never_cached(self):
        application, raw = self.make_expired()
        url = reverse("customer_registration_expire", args=[application.pk])
        self.assertEqual(self.client.get(url).status_code, 302)
        staff = CustomUser.objects.create_user(username="expiry-staff", role="STAFF", is_staff=True)
        customer = CustomUser.objects.create_user(username="expiry-customer", role="CUSTOMER")
        for user in [staff, customer]:
            self.client.force_login(user)
            self.assertEqual(self.client.get(url).status_code, 403)
            self.assertEqual(self.client.post(url, {}).status_code, 403)
        self.client.force_login(self.owner)
        before = CustomerRegistration.objects.values().get(pk=application.pk)
        page = self.client.get(url)
        self.assertEqual(page.status_code, 200)
        self.assertIn("no-store", page["Cache-Control"])
        self.assertContains(page, "Record expiry")
        self.assertNotContains(page, raw)
        self.assertEqual(before, CustomerRegistration.objects.values().get(pk=application.pk))
        self.assertContains(self.client.get(reverse("customer_registration_detail", args=[application.pk])), "Review expiry")
        self.assertEqual(self.client.put(url).status_code, 405)
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.owner)
        self.assertEqual(strict.post(url, {}).status_code, 403)
        data = {"reason": "Close obsolete unverified application", "expected_digest": page.context["preview"]["expected_digest"]}
        self.assertEqual(self.client.post(url, data).status_code, 400)
        response = self.client.post(url, data | {"confirmed": "on", "return_to": "https://untrusted.invalid"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("schemes:owner_applications"))
        self.assertContains(self.client.get(url), "Recorded expiry decision")
        detail = self.client.get(reverse("customer_registration_detail", args=[application.pk]))
        self.assertContains(detail, "closed by owner review")
        self.assertContains(detail, data["reason"])
        self.assertNotContains(detail, "superseded by a later submission")


@override_settings(**REGISTRATION_SETTINGS)
class RegistrationExpiryConcurrencyTests(ExpiryFixture, TransactionTestCase):
    def test_resend_and_expiry_serialize_without_closing_a_fresh_verification(self):
        self.owner = make_owner()
        application, _ = self.make_expired()
        digest = registration_expiry_review(application)["expected_digest"]
        def operation(kind):
            close_old_connections()
            try:
                owner = CustomUser.objects.get(pk=self.owner.pk)
                current = CustomerRegistration.objects.get(pk=application.pk)
                try:
                    if kind == "expire":
                        expire_customer_registration(application=current, reviewed_by=owner, reason="Owner expiry review",
                            confirmed=True, expected_digest=digest)
                    else:
                        issue_registration_verification(application=current, actor=owner)
                    return kind
                except ValidationError:
                    return "refused"
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(operation, ["expire", "resend"]))
        self.assertEqual(outcomes.count("refused"), 1)
        application.refresh_from_db()
        if "expire" in outcomes:
            self.assertEqual(application.status, "EXPIRED")
            self.assertIsNotNone(application.reviewed_at)
        else:
            self.assertEqual(application.status, "PENDING_EMAIL_VERIFICATION")
            self.assertGreater(application.email_verification_expires_at, timezone.now())
            self.assertIsNone(application.reviewed_at)


@override_settings(**REGISTRATION_SETTINGS)
class RegistrationExpiryMigrationTests(ExpiryFixture, TransactionTestCase):
    def test_forward_preserves_old_rows_and_reverse_refuses_review_evidence(self):
        self.owner = make_owner()
        executor = MigrationExecutor(connection)
        try:
            executor.migrate([("accounts", "0009_independent_plan_applications")])
            application, _ = self.make_expired()
            before = CustomerRegistration.objects.values().get(pk=application.pk)
            executor = MigrationExecutor(connection)
            executor.migrate([("accounts", "0010_owner_registration_expiry")])
            self.assertEqual(before, CustomerRegistration.objects.values().get(pk=application.pk))
            self.expire(application)
            with self.assertRaisesMessage(RuntimeError, "Owner-reviewed registration expiry"):
                MigrationExecutor(connection).migrate([("accounts", "0009_independent_plan_applications")])
            application.refresh_from_db()
            self.assertEqual(application.status, "EXPIRED")
            self.assertIsNotNone(application.reviewed_at)
        finally:
            executor = MigrationExecutor(connection)
            executor.migrate(executor.loader.graph.leaf_nodes())
