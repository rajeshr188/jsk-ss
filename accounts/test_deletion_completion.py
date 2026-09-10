from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from io import StringIO
from threading import Barrier
from unittest.mock import patch

from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, close_old_connections, transaction
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.deletion import (
    RETENTION_CATEGORIES, complete_customer_account_deletion, send_completion_notice,
    review_customer_account_retention,
)
from accounts.models import (
    CustomerAccountDeletionDecision as Decision,
    CustomerAccountDeletionNotice as Notice,
    CustomerAccountDeletionRequest as Request,
    CustomerRegistration, CustomerInvitation,
)
from accounts.services import request_authenticated_customer_account_deletion
from accounts import test_account_deletion as foundation
from schemes.models import Contribution, MetalAllocation, PaymentChannel
from schemes.services import (
    confirm_contribution, confirm_razorpay_contribution, enroll_customer,
    retry_metal_allocation, validate_contribution_allowed,
)


class CompletionFixtures:
    setUp = foundation.CustomerAccountDeletionTests.setUp
    preview_account = foundation.CustomerAccountDeletionTests.preview_account

    def contain(self):
        return request_authenticated_customer_account_deletion(user=self.user, source_ip="203.0.113.20")

    def completion_args(self, request, retained=()):
        rows = [{
            "category": key,
            "treatment": "NOT_APPLICABLE" if key == "profile" and not retained else "RETAIN",
            "purpose": "Synthetic review purpose; not a real legal decision.",
            "fields": "Named fields and evidence reviewed in this synthetic test.",
            "period_start": "Verified request date",
            "period_or_condition": "Review disposal after the synthetic hold ends.",
            "review_on": (timezone.localdate() + timedelta(days=30)).isoformat(),
        } for key, label in RETENTION_CATEGORIES]
        return dict(
            request_id=request.pk, actor=self.owner, retention_plan=rows,
            retain_profile_fields=list(retained), reason="Synthetic owner disposition.",
            external_review="Synthetic provider/export/backup review recorded; no external actions performed.",
            confirmation=str(request.pk),
        )


@override_settings(**foundation.DELETION_SETTINGS)
class DeletionCompletionTests(CompletionFixtures, TestCase):
    def test_no_history_removes_credentials_and_profile_but_retains_keys(self):
        request = self.contain()
        original_email = self.user.email
        locked, decision = complete_customer_account_deletion(**self.completion_args(request))
        self.user.refresh_from_db()
        self.customer.refresh_from_db()
        self.assertEqual(locked.status, "COMPLETED_WITH_RETENTION")
        self.assertFalse(self.user.is_active)
        self.assertFalse(self.user.has_usable_password())
        self.assertTrue(self.user.privacy_erased_at)
        self.assertNotEqual(self.user.email, original_email)
        self.assertEqual(self.customer.email, self.user.email)
        self.assertEqual(self.customer.mobile_number, "")
        self.assertEqual(self.customer.address, "")
        self.assertFalse(EmailAddress.objects.filter(user=self.user).exists())
        self.assertFalse(SocialAccount.objects.filter(user=self.user).exists())
        self.assertEqual(decision.notice.recipient_email, original_email)
        self.assertEqual(decision.disposition["retain_profile_fields"], [])
        self.assertNotIn(original_email, str(decision.disposition))
        self.assertFalse(request.actions.filter(actor_label=original_email).exists())

    def test_history_and_entitlement_preserved_exactly(self):
        account, paid = self.preview_account()
        before = list(Contribution.objects.values())
        allocations = list(MetalAllocation.objects.values())
        request = self.contain()
        with self.assertRaisesMessage(ValidationError, "Keep the showroom name and email"):
            complete_customer_account_deletion(**self.completion_args(request))
        complete_customer_account_deletion(**self.completion_args(request, ("full_name", "email")))
        self.assertEqual(list(Contribution.objects.values()), before)
        self.assertEqual(list(MetalAllocation.objects.values()), allocations)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.full_name, "Deletion Customer")
        self.assertEqual(self.customer.email, "customer@example.com")
        self.assertEqual(self.customer.mobile_number, "")
        with self.assertRaisesMessage(ValidationError, "new enrolments"):
            enroll_customer(customer=self.customer, plan=account.plan, metal_grade=account.metal_grade)
        with self.assertRaisesMessage(ValidationError, "new contributions"):
            validate_contribution_allowed(account, "150.00")

    def test_pending_payment_blocks_completion_but_captured_processing_survives_containment(self):
        account, paid = self.preview_account()
        pending = Contribution.objects.create(
            scheme_account=account, amount="150.00",
            contribution_period=timezone.localdate().replace(day=1),
            frequency_rule_snapshot="FLEXIBLE", status="PENDING",
            payment_gateway="razorpay", payment_channel=PaymentChannel.RAZORPAY,
            gateway_mode="live", gateway_order_id="order_pending_deletion",
            checkout_expires_at=timezone.now() + timedelta(minutes=10),
            scheme_rate=paid.scheme_rate, rate_locked_at=timezone.now(),
        )
        request = self.contain()
        args = self.completion_args(request, ("full_name", "email"))
        with self.assertRaisesMessage(ValidationError, "Reconcile pending payments"):
            complete_customer_account_deletion(**args)
        captured = confirm_contribution(
            contribution_id=pending.pk, payment_gateway="razorpay",
            gateway_reference="pay_pending_deletion", verified=True,
        )
        with self.assertRaisesMessage(ValidationError, "Reconcile pending payments"):
            complete_customer_account_deletion(**args)
        retry_metal_allocation(contribution=captured)
        complete_customer_account_deletion(**args)
        # A verified replay of an existing payment still returns its entitlement.
        gateway = type("Gateway", (), {"name": "razorpay", "mode": "live"})()
        replay = confirm_razorpay_contribution(
            contribution_id=pending.pk, callback_order_id=pending.gateway_order_id,
            payment_id="pay_pending_deletion", signature="", gateway=gateway,
        )
        self.assertEqual(replay.status, "PAID")
        self.assertEqual(MetalAllocation.objects.filter(contribution=pending).count(), 1)

    def test_retry_does_not_repeat_erasure_and_clears_temporary_email(self):
        request = self.contain()
        args = self.completion_args(request)
        locked, decision = complete_customer_account_deletion(**args)
        with patch("accounts.deletion.EmailMultiAlternatives.send", side_effect=RuntimeError("secret address should never be stored")):
            self.assertFalse(send_completion_notice(notice_id=decision.notice.pk, actor=self.owner))
        notice = Notice.objects.get(decision=decision)
        self.assertEqual(notice.attempts, 1)
        self.assertNotIn("secret address", notice.last_error)
        with self.assertRaises(CommandError):
            call_command("check_customer_account_deletions", stdout=StringIO())
        self.assertTrue(send_completion_notice(notice_id=notice.pk, actor=self.owner))
        self.assertTrue(send_completion_notice(notice_id=notice.pk, actor=self.owner))
        self.assertEqual(len(mail.outbox), 1)
        notice.refresh_from_db()
        self.assertEqual(notice.recipient_email, "")
        self.assertEqual(notice.attempts, 2)
        self.assertEqual(mail.outbox[0].extra_headers["X-PM-TrackLinks"], "None")
        self.assertIn("financial", mail.outbox[0].body)
        self.assertIn("not automatically deleted", mail.outbox[0].body)
        same, same_decision = complete_customer_account_deletion(**args)
        self.assertEqual(same_decision.pk, decision.pk)
        self.assertEqual(Decision.objects.filter(outcome="COMPLETED_WITH_RETENTION").count(), 1)
        output = StringIO()
        call_command("check_customer_account_deletions", stdout=output)
        self.assertIn("status=ok", output.getvalue())

    def test_invalid_plan_confirmation_or_owner_cannot_change_data(self):
        request = self.contain()
        for alteration in [
            {"confirmation": "wrong"}, {"retention_plan": []},
            {"retain_profile_fields": ["password"]},
        ]:
            with self.assertRaises(ValidationError):
                complete_customer_account_deletion(**{**self.completion_args(request), **alteration})
        with self.assertRaises(PermissionError):
            complete_customer_account_deletion(**{**self.completion_args(request), "actor": self.user})
        with override_settings(CUSTOMER_ACCOUNT_DELETION_ENABLED=False):
            with self.assertRaises(ValidationError):
                complete_customer_account_deletion(**self.completion_args(request))
        self.user.refresh_from_db()
        self.assertIsNone(self.user.privacy_erased_at)
        self.assertEqual(Decision.objects.count(), 0)

    def test_transaction_failure_rolls_back_minimization(self):
        request = self.contain()
        with patch("accounts.deletion.Notice.objects.create", side_effect=RuntimeError("synthetic crash")):
            with self.assertRaises(RuntimeError):
                complete_customer_account_deletion(**self.completion_args(request))
        self.user.refresh_from_db()
        self.assertIsNone(self.user.privacy_erased_at)
        self.assertEqual(self.user.email, "customer@example.com")
        self.assertTrue(EmailAddress.objects.filter(user=self.user).exists())
        self.assertEqual(Decision.objects.count(), 0)

    def test_reactivation_blocked_in_models_and_database(self):
        request = self.contain()
        complete_customer_account_deletion(**self.completion_args(request))
        self.user.refresh_from_db()
        self.user.is_active = True
        with self.assertRaises(ValidationError):
            self.user.save()
        with self.assertRaises(IntegrityError), transaction.atomic():
            get_user_model().objects.filter(pk=self.user.pk).update(is_active=True)
        self.customer.full_name = "Restore original name"
        with self.assertRaises(ValidationError):
            self.customer.save()

    def test_completion_requires_owner_reauthentication_and_csrf(self):
        request = self.contain()
        self.client.force_login(self.owner)
        url = reverse("customer_account_deletion_complete", args=[request.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("reauthenticate", response.url)
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        self.assertEqual(client.post(url).status_code, 403)
        self.assertFalse(Decision.objects.exists())

    def test_owner_form_completes_and_repeated_post_does_not_resend(self):
        request = self.contain()
        self.client.force_login(self.owner)
        response = self.client.post(reverse("account_reauthenticate"), {"password": "strong-owner-password"})
        self.assertEqual(response.status_code, 302)
        url = reverse("customer_account_deletion_complete", args=[request.pk])
        self.assertEqual(self.client.get(url).status_code, 200)
        args = self.completion_args(request)
        data = {
            "reason": args["reason"], "external_review": args["external_review"],
            "confirmation": str(request.pk), "reviewed": "on",
            "retention-TOTAL_FORMS": "7", "retention-INITIAL_FORMS": "7",
            "retention-MIN_NUM_FORMS": "7", "retention-MAX_NUM_FORMS": "7",
        }
        for index, row in enumerate(args["retention_plan"]):
            data.update({f"retention-{index}-{key}": value for key, value in row.items()})
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.get(response.url).status_code, 200)
        self.assertEqual(self.client.post(url, data).status_code, 302)
        self.assertEqual(len(mail.outbox), 1)

    def test_retention_review_can_remove_unneeded_fields_but_never_restore_them(self):
        request = self.contain()
        _, first = complete_customer_account_deletion(**self.completion_args(request, ("full_name", "email")))
        send_completion_notice(notice_id=first.notice.pk, actor=self.owner)
        args = self.completion_args(request)
        args["reason"] = "The synthetic contact retention purpose has ended."
        _, review = review_customer_account_retention(**args)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.full_name, "Removed customer")
        self.assertTrue(self.customer.email.endswith("@deleted.invalid"))
        self.assertEqual(review.notice.recipient_email, "customer@example.com")
        self.assertTrue(send_completion_notice(notice_id=review.notice.pk, actor=self.owner))
        with self.assertRaisesMessage(ValidationError, "never restore"):
            review_customer_account_retention(**self.completion_args(request, ("email",)))
        call_command("check_customer_account_deletions", stdout=StringIO())

    def test_retention_review_cannot_strip_contact_for_open_entitlement(self):
        self.preview_account()
        request = self.contain()
        complete_customer_account_deletion(**self.completion_args(request, ("full_name", "email")))
        with self.assertRaisesMessage(ValidationError, "Keep the showroom name and email"):
            review_customer_account_retention(**self.completion_args(request))

    def test_retention_review_without_contact_does_not_recover_erased_address(self):
        request = self.contain()
        complete_customer_account_deletion(**self.completion_args(request))
        args = self.completion_args(request)
        args["reason"] = "Periodic synthetic evidence review."
        _, review = review_customer_account_retention(**args)
        self.assertFalse(Notice.objects.filter(decision=review).exists())

    def registration(self, *, approved=True):
        return CustomerRegistration.objects.create(
            full_name="Original personal name", email=self.user.email,
            mobile_number=self.customer.mobile_number, address="Original private address",
            status="APPROVED" if approved else "EXPIRED", email_token_digest="a" * 64,
            email_verification_expires_at=timezone.now(),
            email_verified_at=timezone.now() if approved else None,
            terms_version="test-terms", privacy_version="test-privacy",
            consent_accepted_at=timezone.now(), source_ip_digest="b" * 64,
            reviewed_at=timezone.now() if approved else None,
            reviewed_by=self.owner if approved else None,
            reviewed_by_label=self.owner.email if approved else "",
            review_reason="Verified original private address" if approved else "",
            mobile_verified_at=timezone.now() if approved else None,
            approved_user=self.user if approved else None,
        )

    def test_approved_registration_identity_minimized_without_losing_consent(self):
        application = self.registration()
        CustomerInvitation.objects.create(
            user=self.user, email=self.user.email, token_digest="c" * 64,
            created_by=self.owner, created_by_label=self.owner.email,
            expires_at=timezone.now() + timedelta(days=1),
        )
        request = self.contain()
        complete_customer_account_deletion(**self.completion_args(request))
        application.refresh_from_db()
        self.user.refresh_from_db()
        self.assertEqual(application.email, self.user.email)
        self.assertEqual(application.address, "")
        self.assertEqual(application.mobile_number, "")
        self.assertEqual(application.terms_version, "test-terms")
        self.assertEqual(application.status, "APPROVED")
        self.assertEqual(application.approved_user_id, self.user.pk)
        self.assertFalse(CustomerInvitation.objects.filter(user=self.user).exists())
        call_command("check_public_customer_registrations", stdout=StringIO())
        call_command("check_auth_email_integrity", stdout=StringIO())

    def test_other_email_matched_registration_requires_separate_review(self):
        application = self.registration(approved=False)
        request = self.contain()
        with self.assertRaisesMessage(ValidationError, "Other email-matched applications"):
            complete_customer_account_deletion(**self.completion_args(request))
        application.refresh_from_db()
        self.assertEqual(application.email, "customer@example.com")

    def test_original_email_reuse_does_not_restore_or_link_old_customer(self):
        request = self.contain()
        complete_customer_account_deletion(**self.completion_args(request))
        replacement = get_user_model().objects.create_user(
            username="customer@example.com", email="customer@example.com",
            password="a-fresh-unrelated-password", role="CUSTOMER",
        )
        self.assertNotEqual(replacement.pk, self.user.pk)
        self.assertFalse(hasattr(replacement, "customer_profile"))
        self.assertFalse(replacement.customer_deletion_actions.exists())


@override_settings(**foundation.DELETION_SETTINGS)
class DeletionCompletionConcurrencyTests(CompletionFixtures, TransactionTestCase):
    def test_two_completions_create_one_decision_and_one_notice(self):
        request = self.contain()
        barrier = Barrier(2)

        def complete():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return complete_customer_account_deletion(**self.completion_args(request))[1].pk
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: complete(), range(2)))
        self.assertEqual(results[0], results[1])
        self.assertEqual(Decision.objects.filter(outcome="COMPLETED_WITH_RETENTION").count(), 1)
        self.assertEqual(Notice.objects.count(), 1)
