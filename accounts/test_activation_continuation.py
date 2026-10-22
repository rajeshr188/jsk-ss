import uuid
from datetime import timedelta
from decimal import Decimal
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch

from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.application_selectors import activated_plan_url
from accounts.models import CustomerInvitation
from accounts.selectors import get_activation_attention
from accounts.services import issue_customer_invitation, request_customer_invitation_recovery
from accounts.test_plan_applications import APPLICATION_SETTINGS, ApplicationFixtures
from accounts.test_social_auth import GOOGLE_SETTINGS
from schemes.models import AuditEvent, Contribution, PaymentOperationsControl, SchemeAccount
from schemes.selectors import get_customer_plan_next_action
from schemes.services import publish_scheme_rate, submit_scheme_enrolment_request
from schemes.tests.test_razorpay import RAZORPAY_SETTINGS


@override_settings(**{**APPLICATION_SETTINGS, **RAZORPAY_SETTINGS, "PAYMENT_INITIATION_KILL_SWITCH": False})
class ActivationContinuationTests(ApplicationFixtures, TestCase):
    def setUp(self):
        super().setUp()
        self.start_date = timezone.localdate()
        self.application = self.ready()
        self.account, _ = self.approve(self.application)
        self.user = self.account.customer.user
        self.invitation, self.token = issue_customer_invitation(user=self.user, created_by=self.owner)
        self.url = reverse("customer_invitation_accept", args=[self.invitation.pk, self.token])
        publish_scheme_rate(metal_grade=self.grade, rate_per_gram=Decimal("12500"), published_by=self.owner)

    def expire(self):
        CustomerInvitation.objects.filter(pk=self.invitation.pk).update(expires_at=timezone.now() - timedelta(seconds=1))

    def activate(self, client=None):
        response = (client or self.client).post(self.url, {
            "new_password1": "phase-four-customer-password", "new_password2": "phase-four-customer-password",
        })
        self.user.refresh_from_db()
        return response

    def payment(self, status, *, gateway="razorpay", mode="test", **extra):
        successful = status in {Contribution.Status.PAID, Contribution.Status.PAID_UNALLOCATED}
        return Contribution.objects.create(
            scheme_account=self.account, amount=Decimal("1000"), contribution_period=timezone.localdate().replace(day=1),
            frequency_rule_snapshot="FLEXIBLE", payment_gateway=gateway, gateway_mode=mode,
            status=status, paid_at=timezone.now() if successful else None,
            gateway_reference=f"fictional-{uuid.uuid4()}" if successful else None,
            **extra,
        )

    def test_activation_continues_through_password_signin_to_linked_plan_without_financial_writes(self):
        response = self.client.get(self.url)
        self.assertContains(response, "Your plan is approved")
        audit_count = AuditEvent.objects.count()
        response = self.activate()
        destination = reverse("schemes:my_scheme_detail", args=[self.account.scheme_number])
        self.assertEqual(parse_qs(urlsplit(response.url).query)["next"], [destination])
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertEqual(Contribution.objects.count(), 0)
        self.assertEqual(SchemeAccount.objects.count(), 1)
        self.assertEqual(AuditEvent.objects.count(), audit_count)
        signed_in = self.client.post(response.url, {"login": self.user.email, "password": "phase-four-customer-password"})
        self.assertRedirects(signed_in, destination, fetch_redirect_response=False)
        self.assertContains(self.client.get(destination), "Ready for first payment")
        self.assertContains(self.client.get(destination), "Open test checkout")

    def test_activation_does_not_accept_supplied_external_destination(self):
        response = self.client.post(self.url + "?next=https://attacker.invalid/", {
            "new_password1": "phase-four-customer-password", "new_password2": "phase-four-customer-password",
        })
        self.assertNotIn("attacker", response.url)
        self.assertEqual(activated_plan_url(self.owner), None)

    def test_first_payment_prefills_saved_variable_amount_only_without_writing_an_order(self):
        self.activate()
        self.client.force_login(self.user)
        response = self.client.get(reverse("schemes:pay_contribution", args=[self.account.scheme_number]))
        self.assertEqual(response.context["form"].initial["amount"], Decimal("1000"))
        self.assertEqual(Contribution.objects.count(), 0)

    def test_expired_get_has_no_identity_or_mutation_and_post_is_repeat_safe(self):
        self.expire()
        response = self.client.get(self.url)
        self.assertContains(response, "Request setup help")
        self.assertNotContains(response, self.user.email)
        self.invitation.refresh_from_db()
        self.assertIsNone(self.invitation.recovery_requested_at)
        for _ in range(2):
            self.assertRedirects(self.client.post(self.url, {"action": "request_recovery"}), reverse("customer_activation_help"))
        self.invitation.refresh_from_db()
        first_time = self.invitation.recovery_requested_at
        self.assertIsNotNone(first_time)
        request_customer_invitation_recovery(invitation_id=self.invitation.pk, raw_token=self.token)
        self.invitation.refresh_from_db()
        self.assertEqual(self.invitation.recovery_requested_at, first_time)
        self.assertEqual(CustomerInvitation.objects.filter(user=self.user).count(), 2)
        self.assertEqual(Contribution.objects.count(), 0)
        self.assertFalse(self.user.has_usable_password())
        self.assertEqual(len(mail.outbox), 0)

    def test_recovery_requires_csrf_and_returns_same_generic_outcome_for_unknown_and_bad_tokens(self):
        self.expire()
        csrf_client = Client(enforce_csrf_checks=True)
        response = csrf_client.get(self.url, secure=True)
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertEqual(response["Referrer-Policy"], "strict-origin")
        self.assertEqual(csrf_client.post(self.url, {"action": "request_recovery"}).status_code, 403)
        result = csrf_client.post(self.url, {"action": "request_recovery"}, secure=True,
                                  HTTP_ORIGIN="https://testserver", HTTP_X_CSRFTOKEN=csrf_client.cookies["csrftoken"].value)
        self.assertEqual(result.url, reverse("customer_activation_help"))
        for invitation_id, token in [(uuid.uuid4(), self.token), (self.invitation.pk, "wrong")]:
            bad = reverse("customer_invitation_accept", args=[invitation_id, token])
            self.assertEqual(self.client.post(bad, {"action": "request_recovery"}).url, result.url)
        self.assertEqual(self.client.put(self.url).status_code, 405)

    def test_recovery_refuses_current_superseded_activated_and_inactive_logins(self):
        request_customer_invitation_recovery(invitation_id=self.invitation.pk, raw_token=self.token)
        self.invitation.refresh_from_db()
        self.assertIsNone(self.invitation.recovery_requested_at)
        self.expire()
        replacement, replacement_token = issue_customer_invitation(user=self.user, created_by=self.owner)
        request_customer_invitation_recovery(invitation_id=self.invitation.pk, raw_token=self.token)
        self.invitation.refresh_from_db()
        self.assertIsNone(self.invitation.recovery_requested_at)
        CustomerInvitation.objects.filter(pk=replacement.pk).update(expires_at=timezone.now() - timedelta(seconds=1))
        get_user_model().objects.filter(pk=self.user.pk).update(is_active=False)
        self.assertFalse(get_activation_attention().exists())
        request_customer_invitation_recovery(invitation_id=replacement.pk, raw_token=replacement_token)
        replacement.refresh_from_db()
        self.assertIsNone(replacement.recovery_requested_at)

    def test_used_invitation_cannot_request_recovery_or_reveal_email(self):
        self.activate()
        self.client.post(self.url, {"action": "request_recovery"})
        self.invitation.refresh_from_db()
        self.assertIsNone(self.invitation.recovery_requested_at)
        self.assertNotContains(self.client.get(self.url), self.user.email)
        self.assertFalse(get_activation_attention().exists())

    def test_owner_queue_includes_latest_expired_and_failed_delivery_only(self):
        CustomerInvitation.objects.filter(pk=self.invitation.pk).update(email_sent_at=timezone.now())
        self.assertFalse(get_activation_attention().exists())
        self.expire()
        request_customer_invitation_recovery(invitation_id=self.invitation.pk, raw_token=self.token)
        self.assertEqual(list(get_activation_attention()), [self.invitation])
        self.client.force_login(self.owner)
        today = self.client.get(reverse("schemes:owner_today"))
        self.assertContains(today, "Customer requested setup help")
        queue = self.client.get(reverse("schemes:owner_activation_queue"))
        self.assertEqual(queue.context["page_obj"].paginator.per_page, 25)
        with patch("accounts.services.EmailMultiAlternatives.send", return_value=0):
            response = self.client.post(reverse("schemes:customer_invitation_resend", args=[self.account.customer_id]))
        self.assertEqual(response.status_code, 302)
        latest = get_activation_attention().get()
        self.assertNotEqual(latest.pk, self.invitation.pk)
        self.assertEqual(latest.delivery_error, "RuntimeError")
        self.invitation.refresh_from_db()
        self.assertIsNotNone(self.invitation.revoked_at)
        self.assertEqual(SchemeAccount.objects.count(), 1)

    def test_customer_cannot_access_owner_recovery_queue_or_another_agreement(self):
        self.activate()
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("schemes:owner_activation_queue")).status_code, 403)
        self.assertEqual(self.client.get(reverse("schemes:my_scheme_detail", args=["not-owned"])).status_code, 404)

    def test_recovery_queue_preview_and_pagination_are_bounded(self):
        from schemes.services import create_customer
        for index in range(26):
            customer = create_customer(full_name=f"Recovery fixture {index}", email=f"recovery-{index}@example.com",
                                       mobile_number=f"900000{index:04}", password="fixture-password-strong")
            customer.user.set_unusable_password()
            customer.user.save(update_fields=["password"])
            issue_customer_invitation(user=customer.user, created_by=self.owner)
        self.client.force_login(self.owner)
        today = self.client.get(reverse("schemes:owner_today"))
        self.assertEqual(len(today.context["activations"]), 8)
        self.assertEqual(today.context["activation_count"], 27)
        queue = self.client.get(reverse("schemes:owner_activation_queue"))
        self.assertEqual(len(queue.context["activations"]), 25)
        second = self.client.get(reverse("schemes:owner_activation_queue"), {"page": 2})
        self.assertEqual(len(second.context["activations"]), 2)

    def test_changed_request_terms_have_a_customer_action_on_dashboard(self):
        self.activate()
        self.client.force_login(self.user)
        submit_scheme_enrolment_request(customer=self.account.customer, plan=self.plan, metal_grade=self.grade,
                                       requested_contribution_amount=Decimal("1500"), requested_months=14,
                                       customer_message="Another request", actor=self.user)
        from schemes.models import SchemePlan
        SchemePlan.objects.filter(pk=self.plan.pk).update(minimum_contribution=Decimal("600"))
        response = self.client.get(reverse("schemes:my_schemes"))
        self.assertContains(response, "Confirm current terms")
        self.assertContains(response, "submit a fresh confirmation")

    def test_successful_payment_removes_first_payment_prefill_and_test_receipt_is_labelled(self):
        payment = self.payment("PAID", mode="test")
        self.activate()
        self.client.force_login(self.user)
        response = self.client.get(reverse("schemes:pay_contribution", args=[self.account.scheme_number]))
        self.assertNotIn("amount", response.context["form"].initial)
        self.assertContains(self.client.get(reverse("schemes:payment_status", args=[payment.pk])), "not a live payment")

    def test_first_action_respects_future_start_pause_and_missing_rate(self):
        SchemeAccount.objects.filter(pk=self.account.pk).update(start_date=timezone.localdate()+timedelta(days=1))
        self.account.refresh_from_db()
        action = get_customer_plan_next_action(self.account)
        self.assertFalse(action["can_pay"])
        self.assertIn("Start date:", action["message"])
        SchemeAccount.objects.filter(pk=self.account.pk).update(start_date=timezone.localdate())
        self.account.refresh_from_db()
        PaymentOperationsControl.objects.filter(pk=1).update(global_pause=True)
        self.assertFalse(get_customer_plan_next_action(self.account)["can_pay"])
        PaymentOperationsControl.objects.filter(pk=1).update(global_pause=False)
        from schemes.models import SchemeRate
        SchemeRate.objects.all().update(effective_from=timezone.now()+timedelta(days=1))
        self.assertFalse(get_customer_plan_next_action(self.account)["can_pay"])

    def test_pending_and_expired_attempts_never_offer_another_first_payment(self):
        payment = self.payment("PENDING", checkout_expires_at=timezone.now()+timedelta(minutes=5))
        action = get_customer_plan_next_action(self.account)
        self.assertEqual(action["url"], reverse("schemes:payment_status", args=[payment.pk]))
        self.assertFalse(action["can_pay"])
        Contribution.objects.filter(pk=payment.pk).update(checkout_expires_at=timezone.now()-timedelta(seconds=1))
        self.assertIn("confirmation pending", get_customer_plan_next_action(self.account)["stage"])
        self.assertEqual(payment.status, "PENDING")

    def test_recorded_unallocated_payment_takes_priority_and_test_never_counts_as_live(self):
        payment = self.payment("PAID_UNALLOCATED")
        action = get_customer_plan_next_action(self.account)
        self.assertIn("Test payment recorded", action["stage"])
        self.assertIn("Do not pay again", action["message"])
        self.assertFalse(action["can_pay"])
        Contribution.objects.filter(pk=payment.pk).update(status="PAID")
        action = get_customer_plan_next_action(self.account)
        self.assertEqual(action["stage"], "Test or practice payment recorded")
        self.assertNotEqual(action["stage"], "First payment recorded")
        self.payment("PAID", mode="live")
        self.assertEqual(get_customer_plan_next_action(self.account)["stage"], "First payment recorded")

    def test_closed_attempt_is_not_payment_success(self):
        self.payment("ABANDONED")
        action = get_customer_plan_next_action(self.account)
        self.assertEqual(action["stage"], "Ready for first payment")

    def test_dashboard_foregrounds_scoped_applications_and_works_when_new_intake_disabled(self):
        self.activate()
        self.client.force_login(self.user)
        submit_scheme_enrolment_request(customer=self.account.customer, plan=self.plan, metal_grade=self.grade,
                                       requested_contribution_amount=Decimal("1500"), requested_months=14,
                                       customer_message="Another plan application", actor=self.user)
        with override_settings(CUSTOMER_ENROLMENT_REQUESTS_ENABLED=False):
            response = self.client.get(reverse("schemes:my_schemes"))
        self.assertContains(response, "Your application progress")
        content = response.content.decode()
        self.assertLess(content.index("Your application progress"), content.index(self.account.scheme_number))
        self.assertContains(response, "No payment is due before an agreement is created")
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(len(response.context["plan_applications"]), 1)
        self.assertEqual(len(response.context["application_updates"]), 1)
        self.client.force_login(self.owner)
        other = self.client.get(reverse("schemes:my_schemes"))
        self.assertNotContains(other, self.account.scheme_number)
        self.assertFalse(other.context["plan_applications"])

    def test_query_payment_claim_cannot_override_server_record(self):
        self.activate()
        self.client.force_login(self.user)
        response = self.client.get(reverse("schemes:my_scheme_detail", args=[self.account.scheme_number]), {"success":"true","paid":"true"})
        self.assertContains(response, "Ready for first payment")
        self.assertEqual(Contribution.objects.count(), 0)

    @override_settings(**GOOGLE_SETTINGS)
    def test_google_copy_and_connection_eligibility_require_activated_verified_customer(self):
        login = self.client.get(reverse("account_login"))
        self.assertContains(login, "activate your login")
        self.activate()
        self.client.force_login(self.user)
        self.assertContains(self.client.get(reverse("schemes:my_schemes")), "Manage Google sign-in")
        self.assertContains(self.client.get(reverse("socialaccount_connections")), "Connect Google account")
        EmailAddress.objects.filter(user=self.user).update(verified=False)
        response = self.client.get(reverse("socialaccount_connections"))
        self.assertNotContains(response, "Connect Google account")
        self.assertContains(response, "First activate your approved customer login")
