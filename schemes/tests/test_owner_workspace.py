import uuid
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import Client, RequestFactory, TestCase, override_settings
from django.core.exceptions import PermissionDenied
from django.urls import reverse
from django.utils import timezone

from accounts.models import CustomerRegistration
from accounts.services import approve_customer_registration
from schemes.models import Contribution, PaymentWebhookEvent, SchemeAccount, SchemeEnrolmentRequest, SchemePlan
from schemes.selectors import get_owner_application_keys, get_owner_application_items
from schemes.services import create_customer, enroll_customer, submit_scheme_enrolment_request
from schemes.tests.grade_helpers import grade_for_mode
from schemes.views import owner_applications, owner_today


@override_settings(
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    CUSTOMER_ENROLMENT_REQUESTS_ENABLED=True,
)
class OwnerWorkspaceTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(
            username="workspace-owner", email="workspace-owner@example.com", role="OWNER",
        )
        self.customer = create_customer(
            full_name="A Customer", email="workspace-customer@example.com",
            mobile_number="9000000200", password="fixture-password",
        )
        self.other = create_customer(
            full_name="Another Customer", email="workspace-other@example.com",
            mobile_number="9000000201", password="fixture-password",
        )
        self.plan = SchemePlan.objects.create(
            name="Workspace Plan", code="WORKSPACE", publicly_listed=True,
            amount_rule="VARIABLE", frequency_rule="FLEXIBLE",
            minimum_contribution=Decimal("100"), maximum_contribution=Decimal("10000"),
        )
        self.grade = grade_for_mode(self.plan, SchemeAccount.SavingsMode.GOLD)
        self.client.force_login(self.owner)

    def registration(self, index=1, verified=True, **changes):
        now = timezone.now()
        values = dict(
            full_name=f"Applicant {index:02}", email=f"applicant-{index}@example.com",
            mobile_number=f"910000{index:04}", address="Fictional fixture address",
            email_token_digest=uuid.uuid4().hex + uuid.uuid4().hex,
            email_verification_expires_at=now + timedelta(days=1),
            terms_version="fixture", privacy_version="fixture", consent_accepted_at=now,
            source_ip_digest="a" * 64,
            status="AWAITING_OWNER_APPROVAL" if verified else "PENDING_EMAIL_VERIFICATION",
            email_verified_at=now if verified else None,
        )
        values.update(changes)
        return CustomerRegistration.objects.create(**values)

    def plan_request(self, customer=None):
        customer = customer or self.customer
        return submit_scheme_enrolment_request(
            customer=customer, plan=self.plan, metal_grade=self.grade,
            requested_contribution_amount=Decimal("500"), requested_months=12,
            customer_message="",
            actor=customer.user,
        ).enrolment_request

    def test_owner_lands_on_today_and_read_does_not_create_financial_records(self):
        self.registration()
        self.plan_request()
        self.assertRedirects(self.client.get(reverse("schemes:post_login")), reverse("schemes:owner_today"))
        response = self.client.get(reverse("schemes:owner_today"))
        self.assertEqual(response.context["application_count"], 2)
        self.assertFalse(SchemeAccount.objects.exists())
        self.assertFalse(Contribution.objects.exists())
        self.assertEqual(len(mail.outbox), 0)
        self.assertIn("no-store", response.headers["Cache-Control"])

    def test_guest_customer_and_cms_staff_cannot_open_owner_workspaces(self):
        urls = [reverse("schemes:owner_today"), reverse("schemes:owner_applications"), reverse("schemes:customer_list")]
        self.client.logout()
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 302)
        staff = get_user_model().objects.create_user(username="cms-staff", is_staff=True)
        for user in [self.customer.user, staff]:
            self.client.force_login(user)
            for url in urls:
                self.assertEqual(self.client.get(url).status_code, 403)

    def test_inactive_owner_is_rejected_even_with_authenticated_request(self):
        self.owner.is_active = False
        for view in [owner_today, owner_applications]:
            request = RequestFactory().get("/")
            request.user = self.owner
            with self.assertRaises(PermissionDenied):
                view(request)

    def test_verified_registrations_first_then_plan_then_delivery_recovery(self):
        oldest = self.registration(1)
        newer = self.registration(2)
        CustomerRegistration.objects.filter(pk=oldest.pk).update(submitted_at=timezone.now() - timedelta(days=4))
        waiting = self.registration(3, verified=False)
        failed = self.registration(4, verified=False, delivery_failed_at=timezone.now())
        expired = self.registration(5, verified=False, email_verification_expires_at=timezone.now() - timedelta(days=1))
        plan_request = self.plan_request()
        # An expired pending plan still needs an explicit owner decision.
        SchemeEnrolmentRequest.objects.filter(pk=plan_request.pk).update(
            disclosure_accepted_at=timezone.now() - timedelta(days=2),
            expires_at=timezone.now() - timedelta(hours=1),
        )
        items = get_owner_application_items(get_owner_application_keys())
        self.assertEqual([item.record.pk for item in items], [oldest.pk, newer.pk, plan_request.pk, failed.pk, expired.pk])
        self.assertEqual(items[2].next_action, "Review and record expiry")
        waiting_keys = list(get_owner_application_keys(focus="waiting"))
        self.assertEqual([key["pk"] for key in waiting_keys], [waiting.pk])

    def test_application_pagination_bounds_both_sources_and_filters(self):
        for index in range(28):
            self.registration(index)
        self.plan_request()
        url = reverse("schemes:owner_applications")
        first = self.client.get(url)
        second = self.client.get(url, {"page": 2})
        self.assertEqual(len(first.context["applications"]), 25)
        self.assertEqual(len(second.context["applications"]), 4)
        first_keys = {item.record.pk for item in first.context["applications"]}
        self.assertFalse(first_keys & {item.record.pk for item in second.context["applications"]})
        filtered = self.client.get(url, {"kind": "plan", "focus": "all"})
        self.assertEqual(filtered.context["page_obj"].paginator.count, 1)
        self.assertEqual(len(self.client.get(reverse("schemes:owner_today")).context["applications"]), 8)

    def test_customer_search_all_identifiers_without_duplicate_rows(self):
        for _ in range(2):
            account = enroll_customer(
                customer=self.customer, plan=self.plan, metal_grade=self.grade,
                start_date=timezone.localdate(), performed_by=self.owner, reason="Fixture agreement",
            )
        url = reverse("schemes:customer_list")
        for query in ["A Customer", self.customer.email.upper(), self.customer.mobile_number, self.customer.customer_number, account.scheme_number]:
            response = self.client.get(url, {"q": query})
            self.assertEqual([c.pk for c in response.context["customers"]], [self.customer.pk])
            self.assertEqual(response.context["customers"][0].scheme_account_count, 2)
        response = self.client.get(url, {"q": "x" * 1000})
        self.assertEqual(len(response.context["search"]), 100)
        self.assertContains(response, "No matching customers")

    def test_customer_results_fixed_size_and_invalid_page_is_safe(self):
        for index in range(26):
            create_customer(full_name=f"Fixture {index:02}", email=f"fixture-{index}@example.com",
                            mobile_number=f"920000{index:04}", password="fixture-password")
        url = reverse("schemes:customer_list")
        first = self.client.get(url, {"per_page": "999999"})
        self.assertEqual(len(first.context["customers"]), 25)
        for bad_page in ["invalid", "-5", "99999"]:
            self.assertEqual(self.client.get(url, {"page": bad_page}).status_code, 200)
        second = self.client.get(url, {"page": 2})
        self.assertEqual(len(second.context["customers"]), 3)

    def test_customer_application_scope_uses_explicit_identity_link(self):
        own = self.plan_request()
        self.plan_request(self.other)
        unlinked = self.registration(verified=False, email=self.customer.email)
        response = self.client.get(reverse("schemes:owner_applications"), {"customer": self.customer.pk, "focus": "all"})
        self.assertEqual([item.record.pk for item in response.context["applications"]], [own.pk])
        self.assertNotContains(response, unlinked.full_name)
        for value in ["not-an-id", "9" * 30, "999999999"]:
            self.assertEqual(self.client.get(reverse("schemes:owner_applications"), {"customer": value}).status_code, 404)

    def test_registration_and_plan_review_share_workspace_and_preserve_guards(self):
        registration = self.registration()
        identity_review = self.client.get(reverse("customer_registration_detail", args=[registration.pk]))
        self.assertContains(identity_review, 'for="id_registration_rejection_reason"')
        self.assertEqual(identity_review.content.decode().count('id="id_reason"'), 1)
        for url in [reverse("customer_registration_detail", args=[registration.pk]),
                    reverse("schemes:owner_enrolment_request_detail", args=[self.plan_request().pk])]:
            response = self.client.get(url)
            self.assertTemplateUsed(response, "schemes/application_review.html")
            self.assertContains(response, "Next action:")
            self.assertContains(response, "Applications inbox")
        request_record = SchemeEnrolmentRequest.objects.get()
        review = self.client.get(reverse("schemes:owner_enrolment_request_detail", args=[request_record.pk]))
        self.assertContains(review, "Create savings agreement")
        self.assertContains(review, "current_terms_confirmed")
        self.assertContains(review, "Minimum ₹100.00; maximum ₹10000.00")
        self.assertFalse(SchemeAccount.objects.exists())
        self.customer.user.is_active = False
        self.customer.user.save(update_fields=["is_active"])
        for route in ["owner_enrolment_request_detail", "owner_enrolment_request_enroll"]:
            response = self.client.get(reverse(f"schemes:{route}", args=[request_record.pk]))
            self.assertContains(response, "login is no longer eligible")
            self.assertNotContains(response, "Create savings agreement")
        plan_item = next(item for item in get_owner_application_items(get_owner_application_keys()) if item.kind == "plan")
        self.assertEqual(plan_item.next_action, "Review customer login eligibility")
        self.customer.user.is_active = True
        self.customer.user.save(update_fields=["is_active"])
        # Changing material terms removes conversion on both current and legacy URLs.
        SchemePlan.objects.filter(pk=self.plan.pk).update(minimum_contribution=Decimal("200"))
        for route in ["owner_enrolment_request_detail", "owner_enrolment_request_enroll"]:
            response = self.client.get(reverse(f"schemes:{route}", args=[request_record.pk]))
            self.assertContains(response, "offer changed or closed")
            self.assertNotContains(response, "Create savings agreement")

    def test_unified_forms_keep_csrf_enforcement(self):
        application = self.registration()
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        response = client.post(reverse("customer_registration_approve", args=[application.pk]),
                               {"mobile_verified": "on", "reason": "Fixture"})
        self.assertEqual(response.status_code, 403)
        self.assertFalse(application.approved_user_id)

    def test_closed_identity_is_visible_in_customer_filtered_history(self):
        application = self.registration()
        customer, _, _ = approve_customer_registration(application=application, reviewed_by=self.owner, reason="Fixture contact check")
        response = self.client.get(reverse("schemes:owner_applications"), {"customer": customer.pk, "focus": "closed"})
        self.assertEqual([item.record.pk for item in response.context["applications"]], [application.pk])
        self.assertContains(response, "View decision and customer record")

    def test_inactive_customer_context_does_not_claim_active_or_offer_invitation(self):
        self.customer.user.is_active = False
        self.customer.user.save(update_fields=["is_active"])
        response = self.client.get(reverse("schemes:customer_detail", args=[self.customer.pk]))
        self.assertContains(response, "Login inactive")
        self.assertNotContains(response, "Resend invitation")

    def test_exception_count_order_bounds_exact_payment_and_customer_scope(self):
        account = enroll_customer(customer=self.customer, plan=self.plan, metal_grade=self.grade,
                                 start_date=timezone.localdate(), performed_by=self.owner, reason="Fixture")
        contribution = Contribution.objects.create(
            scheme_account=account, amount=Decimal("500"), contribution_period=timezone.localdate().replace(day=1),
            frequency_rule_snapshot="FLEXIBLE", status="PAID_UNALLOCATED", payment_gateway="mock",
            gateway_reference="fixture-confirmed", paid_at=timezone.now(),
        )
        for index in range(30):
            PaymentWebhookEvent.objects.create(
                gateway="razorpay", gateway_mode="test", event_type="payment.captured",
                event_id=f"fixture-event-{index}", payload_sha256="a" * 64,
                status="REVIEW_REQUIRED", contribution=contribution if index == 0 else None,
                error="Fixture mismatch" if index == 0 else "Fixture review needed",
            )
        today = self.client.get(reverse("schemes:owner_today"))
        self.assertEqual(today.context["exception_count"], 31)
        self.assertEqual(len(today.context["exceptions"]), 8)
        self.assertEqual(today.context["exceptions"][0].contribution.pk, contribution.pk)
        self.assertContains(today, f'?contribution={contribution.pk}')
        self.assertContains(today, reverse("schemes:webhook_recovery", args=[PaymentWebhookEvent.objects.get(event_id="fixture-event-0").pk]))
        queue = self.client.get(reverse("schemes:exception_queue"))
        self.assertEqual(len(queue.context["exceptions"]), 25)
        payment = self.client.get(reverse("schemes:contribution_list"), {"contribution": contribution.pk})
        self.assertEqual(list(payment.context["contributions"]), [contribution])
        self.assertContains(payment, self.customer.customer_number)
        mismatched = self.client.get(reverse("schemes:contribution_list"), {"customer": self.other.pk, "contribution": contribution.pk})
        self.assertEqual(mismatched.status_code, 404)
        self.assertEqual(Contribution.objects.get(pk=contribution.pk).status, "PAID_UNALLOCATED")
        self.assertFalse(hasattr(Contribution.objects.get(pk=contribution.pk), "metal_allocation"))
        retry = self.client.post(reverse("schemes:retry_contribution_allocation", args=[contribution.pk]), {"reason": ""})
        self.assertRedirects(retry, reverse("schemes:contribution_list") + f"?contribution={contribution.pk}")
        self.assertEqual(Contribution.objects.get(pk=contribution.pk).status, "PAID_UNALLOCATED")

    def test_unsupported_webhook_is_visible_without_broken_recovery_action(self):
        event = PaymentWebhookEvent.objects.create(
            gateway="razorpay", gateway_mode="test", event_id="fixture-unsupported",
            event_type="refund.processed", payload_sha256="a" * 64, status="FAILED",
        )
        response = self.client.get(reverse("schemes:owner_today"))
        self.assertContains(response, "Manual reconciliation required")
        self.assertNotContains(response, reverse("schemes:webhook_recovery", args=[event.pk]))
