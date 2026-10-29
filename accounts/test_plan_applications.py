import re
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from threading import Barrier
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.exceptions import ValidationError
from django.db import connection, connections, transaction
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.applications import (
    application_terms_current, approve_plan_application, complete_plan_application,
    offer_form_digest, reissue_progress_access, submit_plan_application, verify_plan_application,
)
from accounts.logging import redact_sensitive_auth_paths
from accounts.models import CustomerInvitation, CustomerRegistration, PlanApplication, PlanApplicationConfirmation
from accounts.services import approve_customer_registration
from schemes.models import AuditEvent, Contribution, Customer, SchemeAccount, SchemePlan, SchemePlanOffering
from schemes.selectors import get_owner_application_keys
from schemes.services import create_customer
from schemes.tests.grade_helpers import grade_for_mode


APPLICATION_SETTINGS = {
    "PUBLIC_CUSTOMER_REGISTRATION_ENABLED": True,
    "CUSTOMER_ENROLMENT_REQUESTS_ENABLED": True,
    "PUBLIC_REGISTRATION_ATTEMPTS_PER_HOUR": 10,
    "PUBLIC_REGISTRATION_TERMS_VERSION": "terms-test-v1",
    "PUBLIC_REGISTRATION_PRIVACY_VERSION": "privacy-test-v1",
    "CUSTOMER_ENROLMENT_REQUEST_DISCLOSURE_VERSION": "offer-test-v1",
    "CUSTOMER_ENROLMENT_REQUEST_EXPIRY_DAYS": 30,
    "EMAIL_BACKEND": "django.core.mail.backends.locmem.EmailBackend",
    "PASSWORD_HASHERS": ["django.contrib.auth.hashers.MD5PasswordHasher"],
}


class ApplicationFixtures:
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username="application-owner", email="application-owner@example.com", role="OWNER")
        self.plan = SchemePlan.objects.create(
            name="Application flexible plan", code="APPLICATION", minimum_months=12, default_months=12,
            amount_rule="VARIABLE", frequency_rule="FLEXIBLE", minimum_contribution=Decimal("500"),
            maximum_contribution=Decimal("5000"), active=True, publicly_listed=True,
        )
        self.grade = grade_for_mode(self.plan, "GOLD")
        self.start_date = timezone.localdate() + timedelta(days=2)

    def submit(self, **changes):
        args = dict(
            plan=self.plan, metal_grade=self.grade, amount=Decimal("1000"), months=14,
            message="Preferred plan", full_name="Application Customer", email="application-customer@example.com",
            mobile_number="9876543210", source_ip="203.0.113.7", offer_digest=offer_form_digest(self.plan),
            base_url="https://example.test",
        )
        args.update(changes)
        return submit_plan_application(**args)

    def verify(self, submission):
        return verify_plan_application(registration_id=submission.application.pk, raw_token=submission.raw_token, base_url="https://example.test")

    def complete(self, application, **changes):
        args = dict(
            registration_id=application.registration_id, access_digest=application.progress_token_digest,
            address="12 Fictional Street, Vellore", metal_grade=self.grade, amount=Decimal("1000"), months=14,
            message="Preferred plan", start_date=self.start_date, offer_digest=offer_form_digest(self.plan),
        )
        args.update(changes)
        return complete_plan_application(**args)

    def ready(self):
        return self.complete(self.verify(self.submit()))

    def approve(self, application, **changes):
        args = dict(registration_id=application.registration_id, actor=self.owner, mobile_verified=True,
                    terms_reviewed=True, reason="Identity, mobile and confirmed plan reviewed at showroom.", base_url="https://example.test")
        args.update(changes)
        return approve_plan_application(**args)

    def grant(self, application, client=None):
        client = client or self.client
        session = client.session
        session["plan_application_access"] = {"registration": str(application.registration_id), "digest": application.progress_token_digest}
        session.save()


@override_settings(**APPLICATION_SETTINGS)
class PlanApplicationTests(ApplicationFixtures, TestCase):
    def test_approval_passes_confirmed_selection_without_fixing_legacy_preference(self):
        from schemes.services import enroll_customer
        application = self.ready()
        with patch("accounts.applications.enroll_customer", wraps=enroll_customer) as enroll:
            account, created = self.approve(application)
        self.assertTrue(created)
        self.assertEqual(enroll.call_args.kwargs["selected_contribution_amount"], application.requested_amount)
        self.assertTrue(enroll.call_args.kwargs["selected_amount_confirmed"])
        self.assertIsNone(enroll.call_args.kwargs["expected_configuration_id"])
        self.assertEqual(account.amount_rule_snapshot, "VARIABLE")
        self.assertIsNone(account.fixed_amount_snapshot)

    def test_contact_submission_persists_choices_without_address_login_or_agreement(self):
        with self.captureOnCommitCallbacks(execute=True):
            submission = self.submit()
        application = PlanApplication.objects.get()
        self.assertEqual(application.registration.address, "")
        self.assertEqual(application.plan, self.plan)
        self.assertEqual(application.metal_grade, self.grade)
        self.assertEqual(application.requested_amount, Decimal("1000"))
        self.assertEqual(application.requested_months, 14)
        self.assertEqual(application.confirmations.get().offer["minimum_amount"], "500.00")
        self.assertFalse(Customer.objects.exists())
        self.assertFalse(SchemeAccount.objects.exists())
        self.assertNotIn(submission.raw_token, application.registration.email_token_digest)
        self.assertEqual(mail.outbox[0].extra_headers["X-PM-TrackLinks"], "None")

    def test_selected_plan_form_contact_first_and_address_after_verification(self):
        response = self.client.get(reverse("customer_registration") + f"?plan={self.plan.pk}")
        self.assertContains(response, "Save and verify email")
        self.assertNotContains(response, 'name="address"')
        content = response.content.decode()
        self.assertLess(content.index('name="full_name"'), content.index('name="metal_grade"'))
        submission = self.submit()
        url = reverse("customer_registration_verify", args=[submission.application.pk, submission.raw_token])
        self.client.get(url)
        submission.application.refresh_from_db()
        self.assertIsNone(submission.application.email_verified_at)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(url)
        self.assertRedirects(response, reverse("plan_application_progress", args=[submission.application.pk]))
        application = PlanApplication.objects.get()
        self.assertContains(self.client.get(response.url), 'name="address"')
        self.assertEqual(application.requested_months, 14)
        self.assertEqual(mail.outbox[-1].extra_headers["X-PM-TrackOpens"], "false")

    def test_email_verification_is_one_use_and_csrf_protected(self):
        submission = self.submit()
        url = reverse("customer_registration_verify", args=[submission.application.pk, submission.raw_token])
        self.assertEqual(Client(enforce_csrf_checks=True).post(url).status_code, 403)
        self.verify(submission)
        with self.assertRaises(ValidationError):
            self.verify(submission)

    def test_progress_secret_is_separate_post_gated_and_not_an_identity_lookup(self):
        submission = self.submit()
        with self.captureOnCommitCallbacks(execute=True):
            application = self.verify(submission)
        progress_token = re.search(r"/access/[^/]+/([^/]+)/", mail.outbox[-1].body).group(1)
        self.assertNotEqual(progress_token, submission.raw_token)
        progress = reverse("plan_application_progress", args=[application.registration_id])
        self.assertContains(self.client.get(progress), "Application access unavailable")
        url = reverse("plan_application_access", args=[application.registration_id, progress_token])
        self.assertNotContains(self.client.get(url), application.registration.email)
        self.assertContains(self.client.get(progress), "Application access unavailable")
        self.assertEqual(Client(enforce_csrf_checks=True).post(url).status_code, 403)
        response = self.client.post(url)
        self.assertRedirects(response, progress)
        response = self.client.get(progress)
        self.assertContains(response, "Complete your details")
        self.assertEqual(response.headers["Referrer-Policy"], "strict-origin")
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertNotContains(response, progress_token)

    def test_progress_rotations_revoke_old_links_and_existing_sessions(self):
        application = self.verify(self.submit())
        self.grant(application)
        original = application.progress_token_digest
        with self.captureOnCommitCallbacks(execute=True):
            reissue_progress_access(registration_id=application.registration_id, actor=self.owner, base_url="https://example.test")
        application.refresh_from_db()
        self.assertNotEqual(application.progress_token_digest, original)
        self.assertContains(self.client.get(reverse("plan_application_progress", args=[application.registration_id])), "Application access unavailable")
        with self.assertRaises(ValidationError):
            self.complete(application, access_digest=original)

    def test_progress_delivery_failure_is_recorded_and_can_be_reissued(self):
        submission = self.submit()
        with patch("accounts.applications.EmailMultiAlternatives.send", side_effect=RuntimeError("sensitive provider detail")):
            with self.captureOnCommitCallbacks(execute=True):
                application = self.verify(submission)
        application.refresh_from_db()
        self.assertEqual(application.progress_delivery_error, "RuntimeError")
        self.assertIsNotNone(application.progress_delivery_failed_at)
        with self.captureOnCommitCallbacks(execute=True):
            reissue_progress_access(registration_id=application.registration_id, actor=self.owner, base_url="https://example.test")
        application.refresh_from_db()
        self.assertIsNone(application.progress_delivery_failed_at)
        self.assertIsNotNone(application.progress_sent_at)

    def test_material_offer_change_blocks_approval_until_new_customer_confirmation(self):
        application = self.ready()
        initial = list(application.confirmations.values_list("offer", flat=True))
        self.plan.minimum_contribution = Decimal("750")
        self.plan.save()
        application.plan = self.plan
        self.assertFalse(application_terms_current(application))
        with self.assertRaises(ValidationError):
            self.approve(application)
        self.assertFalse(Customer.objects.exists())
        self.complete(application)
        application.refresh_from_db()
        account, created = self.approve(application)
        self.assertTrue(created)
        self.assertEqual(account.minimum_amount_snapshot, Decimal("750"))
        self.assertEqual(list(application.confirmations.values_list("offer", flat=True))[:2], initial)
        self.assertEqual(application.confirmations.count(), 3)

    def test_stale_display_cannot_silently_confirm_new_terms(self):
        application = self.verify(self.submit())
        stale = offer_form_digest(self.plan)
        self.plan.maximum_contribution = Decimal("4000")
        self.plan.save()
        with self.assertRaisesMessage(ValidationError, "offer changed"):
            self.complete(application, offer_digest=stale)
        application.refresh_from_db()
        self.assertIsNone(application.completed_at)
        self.assertEqual(application.confirmations.count(), 1)

    def test_changed_start_date_or_expiry_needs_customer_action(self):
        application = self.ready()
        with patch("accounts.applications.timezone.localdate", return_value=self.start_date + timedelta(days=1)):
            with self.assertRaises(ValidationError):
                self.approve(application)
        PlanApplication.objects.filter(pk=application.pk).update(expires_at=timezone.now() - timedelta(seconds=1))
        with self.assertRaisesMessage(ValidationError, "expired"):
            self.approve(application)

    def test_closed_plan_or_grade_blocks_approval_without_substitution(self):
        application = self.ready()
        SchemePlanOffering.objects.filter(plan=self.plan, metal_grade=self.grade).update(active=False)
        with self.assertRaises(ValidationError):
            self.approve(application)
        self.assertFalse(SchemeAccount.objects.exists())

    def test_coordinated_approval_records_separate_evidence_and_no_payment(self):
        application = self.ready()
        with self.captureOnCommitCallbacks(execute=True):
            account, created = self.approve(application)
        application.refresh_from_db()
        registration = application.registration
        self.assertTrue(created)
        self.assertEqual(registration.status, "APPROVED")
        self.assertIsNotNone(registration.mobile_verified_at)
        self.assertEqual(registration.approved_user_id, account.customer.user_id)
        self.assertEqual(application.scheme_account, account)
        self.assertEqual(account.agreed_months, 14)
        self.assertEqual(account.start_date, self.start_date)
        self.assertFalse(account.customer.user.has_usable_password())
        self.assertEqual(AuditEvent.objects.filter(action="CUSTOMER_ENROLMENT", scheme_account=account).count(), 1)
        self.assertFalse(Contribution.objects.exists())
        invitation = CustomerInvitation.objects.get(user=account.customer.user)
        self.assertIsNotNone(invitation.email_sent_at)

    def test_duplicate_retry_retains_same_agreement_and_does_not_send_another_invite(self):
        application = self.ready()
        with self.captureOnCommitCallbacks(execute=True):
            first, created = self.approve(application)
        sent = len(mail.outbox)
        with self.captureOnCommitCallbacks(execute=True):
            second, created = self.approve(application)
        self.assertFalse(created)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(SchemeAccount.objects.count(), 1)
        self.assertEqual(len(mail.outbox), sent)

    def test_financial_failure_rolls_back_identity_invitation_and_decision(self):
        application = self.ready()
        with patch("accounts.applications.enroll_customer", side_effect=ValidationError("Agreement rejected")):
            with self.captureOnCommitCallbacks(execute=True):
                with self.assertRaises(ValidationError):
                    self.approve(application)
        application.refresh_from_db()
        self.assertEqual(application.registration.status, "AWAITING_OWNER_APPROVAL")
        self.assertFalse(Customer.objects.exists())
        self.assertFalse(CustomerInvitation.objects.exists())
        self.assertFalse(SchemeAccount.objects.exists())
        self.assertFalse(mail.outbox)

    def test_invitation_runs_only_after_commit_and_failure_does_not_undo_approval(self):
        application = self.ready()
        with patch("accounts.applications.send_customer_invitation", side_effect=RuntimeError("private transport detail")) as sender:
            with self.captureOnCommitCallbacks(execute=True):
                account, created = self.approve(application)
                self.assertFalse(sender.called)
        invitation = CustomerInvitation.objects.get(user=account.customer.user)
        self.assertEqual(invitation.delivery_error, "RuntimeError")
        self.assertIsNotNone(invitation.delivery_failed_at)
        self.assertEqual(SchemeAccount.objects.count(), 1)
        self.assertEqual(CustomerRegistration.objects.get().status, "APPROVED")

    def test_identity_conflict_discovered_at_approval_leaves_no_agreement(self):
        application = self.ready()
        create_customer(full_name="Another Customer", email="other-identity@example.com", mobile_number="+919876543210")
        with self.assertRaises(ValidationError):
            self.approve(application)
        self.assertFalse(SchemeAccount.objects.exists())
        application.refresh_from_db()
        self.assertEqual(application.registration.status, "AWAITING_OWNER_APPROVAL")

    def test_contact_verification_terms_review_and_owner_permissions_are_required(self):
        application = self.ready()
        for changes in [{"mobile_verified": False}, {"terms_reviewed": False}, {"reason": ""}]:
            with self.assertRaises(ValidationError):
                self.approve(application, **changes)
        staff = get_user_model().objects.create_user(username="application-staff", role="STAFF", is_staff=True)
        with self.assertRaises(ValidationError):
            self.approve(application, actor=staff)
        self.client.force_login(staff)
        self.assertEqual(self.client.get(reverse("customer_registration_detail", args=[application.registration_id])).status_code, 403)
        self.assertEqual(self.client.post(reverse("plan_application_approve", args=[application.registration_id])).status_code, 403)

    def test_legacy_identity_approval_cannot_bypass_coordinated_review(self):
        application = self.ready()
        with self.assertRaises(ValidationError):
            approve_customer_registration(application=application.registration, reviewed_by=self.owner, reason="Identity only")
        self.assertFalse(Customer.objects.exists())

    def test_incomplete_verified_application_waits_for_customer_except_delivery_recovery(self):
        with self.captureOnCommitCallbacks(execute=True):
            application = self.verify(self.submit())
        self.assertEqual(get_owner_application_keys(focus="waiting").count(), 1)
        self.assertEqual(get_owner_application_keys(focus="attention").count(), 0)
        PlanApplication.objects.filter(pk=application.pk).update(progress_delivery_failed_at=timezone.now())
        self.assertEqual(get_owner_application_keys(focus="attention").count(), 1)
        self.assertEqual(get_owner_application_keys(focus="waiting").count(), 0)

    def test_customer_completion_post_and_owner_review_share_preserved_context(self):
        application = self.verify(self.submit())
        self.grant(application)
        url = reverse("plan_application_progress", args=[application.registration_id])
        response = self.client.post(url, {
            "address": "12 Fictional Street, Vellore", "metal_grade": self.grade.pk,
            "requested_contribution_amount": "1000", "requested_months": "14", "start_date": self.start_date.isoformat(),
            "customer_message": "Preferred plan", "disclosure_accepted": "on", "accept_policies": "on", "offer_digest": offer_form_digest(self.plan),
        })
        self.assertRedirects(response, url)
        self.assertContains(self.client.get(url), "Showroom review")
        self.client.force_login(self.owner)
        review = self.client.get(reverse("customer_registration_detail", args=[application.registration_id]))
        self.assertContains(review, "Approve identity and plan")
        self.assertContains(review, "Customer confirmation history")
        self.assertNotContains(review, "Approve and invite")
        with self.captureOnCommitCallbacks(execute=True):
            approved = self.client.post(reverse("plan_application_approve", args=[application.registration_id]), {
                "mobile_verified": "on", "terms_reviewed": "on", "reason": "Checked contact and confirmed terms",
            })
        self.assertEqual(approved.status_code, 302)
        self.assertContains(self.client.get(approved.url), "Agreement statement")

    def test_existing_customer_applies_using_existing_profile_without_contact_form(self):
        customer = create_customer(full_name="Existing Customer", email="existing@example.com", mobile_number="9123456789", password="password")
        self.client.force_login(customer.user)
        response = self.client.get(reverse("customer_registration") + f"?plan={self.plan.pk}")
        self.assertRedirects(response, reverse("schemes:scheme_enrolment_request_create", args=[self.plan.pk]))
        response = self.client.get(response.url)
        self.assertNotContains(response, 'name="address"')
        self.assertNotContains(response, 'name="email"')
        self.assertFalse(CustomerRegistration.objects.exists())

    def test_confirmation_evidence_cannot_be_overwritten(self):
        application = self.ready()
        confirmation = application.confirmations.last()
        confirmation.requested_months = 20
        with self.assertRaises(ValidationError):
            confirmation.save()
        with self.assertRaises(ValidationError):
            confirmation.delete()

    def test_disabled_and_expired_progress_are_fail_closed(self):
        with override_settings(CUSTOMER_ENROLMENT_REQUESTS_ENABLED=False):
            with self.assertRaises(ValidationError):
                self.submit()
        application = self.verify(self.submit())
        self.grant(application)
        with override_settings(CUSTOMER_ENROLMENT_REQUESTS_ENABLED=False):
            response = self.client.get(reverse("plan_application_progress", args=[application.registration_id]))
            self.assertContains(response, "Online updates unavailable")
            self.assertNotContains(response, 'name="address"')
        PlanApplication.objects.filter(pk=application.pk).update(expires_at=timezone.now() - timedelta(seconds=1))
        response = self.client.get(reverse("plan_application_progress", args=[application.registration_id]))
        self.assertContains(response, "Application access unavailable")
        self.assertNotContains(response, application.registration.email)

    def test_expired_unverified_application_cannot_reissue_verification(self):
        submission = self.submit()
        application = PlanApplication.objects.get(registration=submission.application)
        original_digest = submission.application.email_token_digest
        PlanApplication.objects.filter(pk=application.pk).update(expires_at=timezone.now()-timedelta(seconds=1))
        from accounts.services import issue_registration_verification
        with self.assertRaisesMessage(ValidationError, "application has expired"):
            issue_registration_verification(application=submission.application, actor=self.owner)
        submission.application.refresh_from_db()
        self.assertEqual(submission.application.email_token_digest, original_digest)
        self.client.force_login(self.owner)
        response = self.client.get(reverse("customer_registration_detail", args=[application.registration_id]))
        self.assertContains(response, "Application expired")
        self.assertNotContains(response, "Send replacement verification")

    def test_disabled_or_removed_customer_cannot_use_progress_bearer_access(self):
        application = self.ready()
        account, _ = self.approve(application)
        self.grant(application)
        account.customer.user.is_active = False
        account.customer.user.save(update_fields=["is_active"])
        response = self.client.get(reverse("plan_application_progress", args=[application.registration_id]))
        self.assertContains(response, "Application access unavailable")

    def test_progress_urls_are_redacted_and_not_counted_by_analytics(self):
        application = self.verify(self.submit())
        self.grant(application)
        from pages.models import PublicFunnelDailyCount
        with override_settings(PUBLIC_FUNNEL_MEASUREMENT_ENABLED=True):
            self.client.get(reverse("plan_application_progress", args=[application.registration_id]))
        self.assertFalse(PublicFunnelDailyCount.objects.exists())
        path = reverse("plan_application_access", args=[application.registration_id, "private-token"])
        self.assertEqual(redact_sensitive_auth_paths(path), "/accounts/applications/[REDACTED]/")

    def test_changed_fixed_amount_is_displayed_and_explicitly_confirmed(self):
        self.plan.amount_rule = "FIXED"
        self.plan.fixed_contribution_amount = Decimal("1000")
        self.plan.minimum_contribution = Decimal("1000")
        self.plan.maximum_contribution = Decimal("1000")
        self.plan.save()
        application = self.ready()
        self.grant(application)
        self.plan.fixed_contribution_amount = Decimal("2000")
        self.plan.minimum_contribution = Decimal("2000")
        self.plan.maximum_contribution = Decimal("2000")
        self.plan.save()
        url = reverse("plan_application_progress", args=[application.registration_id])
        response = self.client.get(url)
        self.assertContains(response, "Confirm current terms")
        self.assertEqual(response.context["form"]["requested_contribution_amount"].value(), Decimal("2000"))
        response = self.client.post(url, {
            "address": "12 Fictional Street, Vellore", "metal_grade": self.grade.pk,
            "requested_contribution_amount": "1000", "requested_months": "14", "start_date": self.start_date.isoformat(),
            "customer_message": "", "disclosure_accepted": "on", "accept_policies": "on", "offer_digest": offer_form_digest(self.plan),
        })
        self.assertRedirects(response, url)
        account, _ = self.approve(application)
        self.assertEqual(account.fixed_amount_snapshot, Decimal("2000"))
        application.refresh_from_db()
        self.assertEqual(application.requested_amount, Decimal("2000"))
        self.assertEqual(application.confirmations.count(), 3)

    def test_expired_application_has_no_owner_approval_action(self):
        application = self.ready()
        PlanApplication.objects.filter(pk=application.pk).update(expires_at=timezone.now()-timedelta(seconds=1))
        self.client.force_login(self.owner)
        response = self.client.get(reverse("customer_registration_detail", args=[application.registration_id]))
        self.assertContains(response, "This application has expired")
        self.assertNotContains(response, "Approve identity and plan")

    def test_approved_application_linkage_and_terms_are_immutable(self):
        application = self.ready()
        self.approve(application)
        application.refresh_from_db()
        application.requested_months = 20
        with self.assertRaises(ValidationError):
            application.save()
        application.refresh_from_db()
        self.assertEqual(application.requested_months, 14)

    def test_source_report_counts_plan_confirmations_once_without_identity_data(self):
        application = self.ready()
        self.complete(application)
        from pages.selectors import get_funnel_report
        report = get_funnel_report(start=timezone.localdate(), end=timezone.localdate())
        self.assertEqual(report["outcomes"]["plan_applications_submitted"], 1)
        self.assertEqual(report["outcomes"]["plan_applications_customer_confirmed"], 1)
        self.assertNotIn(application.registration.email, str(report))
        self.assertNotIn(str(application.registration_id), str(report))

    def test_new_policy_versions_require_new_confirmations_and_preserve_initial_evidence(self):
        application = self.ready()
        initial = application.confirmations.first().offer.copy()
        with override_settings(PUBLIC_REGISTRATION_TERMS_VERSION="updated-terms"):
            with self.assertRaises(ValidationError):
                self.approve(application)
            self.complete(application)
            self.approve(application)
        application.refresh_from_db()
        self.assertEqual(application.registration.terms_version, "terms-test-v1")
        self.assertEqual(application.confirmations.first().offer, initial)
        self.assertEqual(application.confirmations.last().offer["terms_version"], "updated-terms")

    def test_integrity_report_detects_missing_coordinated_agreement_without_identifiers(self):
        application = self.ready()
        self.approve(application)
        PlanApplication.objects.filter(pk=application.pk).update(scheme_account=None)
        from django.core.management import call_command, CommandError
        from io import StringIO
        output = StringIO()
        with self.assertRaises(CommandError):
            call_command("check_public_customer_registrations", stdout=output)
        self.assertIn("approved_without_agreement=1", output.getvalue())
        self.assertNotIn(application.registration.email, output.getvalue())


@override_settings(**APPLICATION_SETTINGS)
class PlanApplicationConcurrencyTests(ApplicationFixtures, TransactionTestCase):
    def test_simultaneous_approval_creates_one_agreement_and_one_invitation(self):
        if connection.vendor != "postgresql":
            self.skipTest("Requires PostgreSQL row locks")
        application = self.ready()
        barrier = Barrier(2)

        def approve():
            connections.close_all()
            try:
                actor = get_user_model().objects.get(pk=self.owner.pk)
                barrier.wait(timeout=10)
                account, created = approve_plan_application(
                    registration_id=application.registration_id, actor=actor, mobile_verified=True, terms_reviewed=True,
                    reason="Concurrent showroom approval", base_url="https://example.test",
                )
                return account.pk, created
            finally:
                connections.close_all()

        with patch("accounts.applications._send_activation") as sender:
            with ThreadPoolExecutor(max_workers=2) as executor:
                results = list(executor.map(lambda _: approve(), range(2)))
        self.assertEqual(len({pk for pk, _ in results}), 1)
        self.assertEqual(sum(created for _, created in results), 1)
        self.assertEqual(SchemeAccount.objects.count(), 1)
        self.assertEqual(CustomerInvitation.objects.count(), 1)
        self.assertEqual(AuditEvent.objects.filter(action="CUSTOMER_ENROLMENT").count(), 1)
        sender.assert_called_once()

    def test_outer_transaction_rollback_does_not_deliver_activation(self):
        application = self.ready()
        with patch("accounts.applications._send_activation") as sender:
            with self.assertRaises(RuntimeError):
                with transaction.atomic():
                    self.approve(application)
                    raise RuntimeError("Transaction aborted")
            sender.assert_not_called()
        self.assertFalse(SchemeAccount.objects.exists())
        self.assertFalse(CustomerInvitation.objects.exists())
        self.assertFalse(Customer.objects.exists())
