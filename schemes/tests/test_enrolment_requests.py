import io
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from schemes.models import (
    AuditEvent,
    Contribution,
    SchemeAccount,
    SchemeEnrolmentRequest,
    SchemePlan,
)
from schemes.services import (
    create_customer,
    decide_scheme_enrolment_request,
    enroll_customer_from_request,
    submit_scheme_enrolment_request,
    withdraw_scheme_enrolment_request,
)
from schemes.tests.grade_helpers import grade_for_mode


ENROLMENT_REQUEST_SETTINGS = {
    "CUSTOMER_ENROLMENT_REQUESTS_ENABLED": True,
    "CUSTOMER_ENROLMENT_REQUEST_EXPIRY_DAYS": 30,
    "CUSTOMER_ENROLMENT_REQUEST_DISCLOSURE_VERSION": "2026-09-04",
    "EMAIL_BACKEND": "django.core.mail.backends.locmem.EmailBackend",
    "DEFAULT_FROM_EMAIL": "Jai Sri Krishna Jewellery <admin@example.com>",
    "PASSWORD_HASHERS": ["django.contrib.auth.hashers.MD5PasswordHasher"],
}


@override_settings(**ENROLMENT_REQUEST_SETTINGS)
class SchemeEnrolmentRequestTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(
            username="owner-enrolment@example.com",
            email="owner-enrolment@example.com",
            password="owner-password-strong",
            role=get_user_model().Role.OWNER,
        )
        self.customer = create_customer(
            full_name="Request Customer",
            email="request-customer@example.com",
            mobile_number="9000000088",
            password="customer-password-strong",
        )
        self.other_customer = create_customer(
            full_name="Other Customer",
            email="other-request-customer@example.com",
            mobile_number="9000000089",
            password="customer-password-strong",
        )
        self.plan = SchemePlan.objects.create(
            name="Flexible Gold Plan",
            code="FLEX-GOLD-REQUEST",
            minimum_months=12,
            default_months=12,
            amount_rule=SchemePlan.AmountRule.VARIABLE,
            frequency_rule=SchemePlan.FrequencyRule.ONCE_PER_MONTH,
            minimum_contribution=Decimal("500.00"),
            maximum_contribution=Decimal("5000.00"),
            active=True,
            publicly_listed=True,
        )
        self.grade = grade_for_mode(
            self.plan,
            SchemeAccount.SavingsMode.GOLD,
            code="GOLD_22K_916",
        )

    def submit(self, **overrides):
        values = {
            "customer": self.customer,
            "plan": self.plan,
            "metal_grade": self.grade,
            "requested_contribution_amount": Decimal("1000.00"),
            "requested_months": 12,
            "customer_message": "Please call after 6 PM.",
            "actor": self.customer.user,
        }
        values.update(overrides)
        return submit_scheme_enrolment_request(**values)

    def test_submission_snapshots_offer_without_creating_financial_state(self):
        submission = self.submit()
        request = submission.enrolment_request

        self.assertTrue(submission.created)
        self.assertEqual(request.status, request.Status.PENDING_OWNER_REVIEW)
        self.assertEqual(request.plan_name_snapshot, "Flexible Gold Plan")
        self.assertEqual(request.plan_code_snapshot, "FLEX-GOLD-REQUEST")
        self.assertEqual(request.requested_contribution_amount, Decimal("1000.00"))
        self.assertEqual(request.minimum_contribution_snapshot, Decimal("500.00"))
        self.assertEqual(request.maximum_contribution_snapshot, Decimal("5000.00"))
        self.assertEqual(request.disclosure_version, "2026-09-04")
        self.assertGreater(request.expires_at, request.disclosure_accepted_at)
        self.assertEqual(SchemeAccount.objects.count(), 0)
        self.assertEqual(Contribution.objects.count(), 0)
        self.assertTrue(
            AuditEvent.objects.filter(
                action=AuditEvent.Action.ENROLMENT_REQUEST_SUBMITTED,
                actor=self.customer.user,
            ).exists()
        )

    def test_duplicate_pending_submission_is_idempotent(self):
        first = self.submit()
        second = self.submit(requested_contribution_amount=Decimal("2000.00"))

        self.assertTrue(first.created)
        self.assertFalse(second.created)
        self.assertEqual(second.enrolment_request.pk, first.enrolment_request.pk)
        self.assertEqual(SchemeEnrolmentRequest.objects.count(), 1)

    def test_expired_pending_request_is_closed_before_replacement(self):
        first = self.submit().enrolment_request
        submitted_at = timezone.now() - timedelta(days=31)
        SchemeEnrolmentRequest.objects.filter(pk=first.pk).update(
            created_at=submitted_at,
            disclosure_accepted_at=submitted_at,
            expires_at=timezone.now() - timedelta(minutes=1)
        )

        second = self.submit().enrolment_request

        first.refresh_from_db()
        self.assertEqual(first.status, first.Status.EXPIRED)
        self.assertNotEqual(first.pk, second.pk)
        self.assertEqual(second.status, second.Status.PENDING_OWNER_REVIEW)

    def test_submission_rejects_private_plan_inactive_offering_and_wrong_actor(self):
        self.plan.publicly_listed = False
        self.plan.save(update_fields=["publicly_listed"])
        with self.assertRaises(ValidationError):
            self.submit()

        self.plan.publicly_listed = True
        self.plan.save(update_fields=["publicly_listed"])
        offering = self.plan.metal_offerings.get(metal_grade=self.grade)
        offering.active = False
        offering.save(update_fields=["active", "updated_at"])
        with self.assertRaises(ValidationError):
            self.submit()

        offering.active = True
        offering.save(update_fields=["active", "updated_at"])
        with self.assertRaises(ValidationError):
            self.submit(actor=self.other_customer.user)

    def test_amount_and_duration_must_match_public_offer(self):
        with self.assertRaises(ValidationError):
            self.submit(requested_contribution_amount=Decimal("499.00"))
        with self.assertRaises(ValidationError):
            self.submit(requested_contribution_amount=Decimal("5000.01"))
        with self.assertRaises(ValidationError):
            self.submit(requested_months=11)

    def test_customer_can_withdraw_pending_request(self):
        request = self.submit().enrolment_request

        withdrawn = withdraw_scheme_enrolment_request(
            enrolment_request=request,
            actor=self.customer.user,
        )

        self.assertEqual(withdrawn.status, withdrawn.Status.WITHDRAWN)
        self.assertEqual(withdrawn.decided_by, self.customer.user)
        self.assertTrue(
            AuditEvent.objects.filter(
                action=AuditEvent.Action.ENROLMENT_REQUEST_WITHDRAWN,
            ).exists()
        )
        with self.assertRaises(ValidationError):
            withdraw_scheme_enrolment_request(
                enrolment_request=withdrawn,
                actor=self.customer.user,
            )

    def test_owner_can_decline_but_customer_cannot(self):
        request = self.submit().enrolment_request
        with self.assertRaises(ValidationError):
            decide_scheme_enrolment_request(
                enrolment_request=request,
                status=request.Status.DECLINED,
                actor=self.customer.user,
                reason="Not permitted.",
            )

        declined = decide_scheme_enrolment_request(
            enrolment_request=request,
            status=request.Status.DECLINED,
            actor=self.owner,
            reason="Customer chose another plan.",
        )

        self.assertEqual(declined.status, declined.Status.DECLINED)
        self.assertEqual(declined.decision_reason, "Customer chose another plan.")
        self.assertEqual(SchemeAccount.objects.count(), 0)

    def test_conversion_requires_current_offer_and_terms_confirmation(self):
        request = self.submit().enrolment_request
        with self.assertRaises(ValidationError):
            enroll_customer_from_request(
                enrolment_request=request,
                actor=self.owner,
                current_terms_confirmed=False,
                start_date=date(2026, 9, 4),
                agreed_months=12,
                reason="Terms reviewed at showroom.",
            )

        self.plan.maximum_contribution = Decimal("6000.00")
        self.plan.save(update_fields=["maximum_contribution"])
        with self.assertRaisesMessage(ValidationError, "public offer changed"):
            enroll_customer_from_request(
                enrolment_request=request,
                actor=self.owner,
                current_terms_confirmed=True,
                start_date=date(2026, 9, 4),
                agreed_months=12,
                reason="Terms reviewed at showroom.",
            )

    def test_owner_conversion_is_atomic_and_idempotent(self):
        request = self.submit().enrolment_request

        account, created = enroll_customer_from_request(
            enrolment_request=request,
            actor=self.owner,
            current_terms_confirmed=True,
            start_date=date(2026, 9, 4),
            agreed_months=12,
            reason="Current terms confirmed by phone.",
        )
        same_account, created_again = enroll_customer_from_request(
            enrolment_request=request,
            actor=self.owner,
            current_terms_confirmed=True,
            start_date=date(2026, 9, 4),
            agreed_months=12,
            reason="Repeated submission.",
        )

        request.refresh_from_db()
        self.assertTrue(created)
        self.assertFalse(created_again)
        self.assertEqual(account.pk, same_account.pk)
        self.assertEqual(SchemeAccount.objects.count(), 1)
        self.assertEqual(request.status, request.Status.ENROLLED)
        self.assertEqual(request.scheme_account, account)
        self.assertEqual(account.customer, self.customer)
        self.assertEqual(account.plan, self.plan)
        self.assertEqual(account.metal_grade, self.grade)
        self.assertEqual(account.agreed_months, 12)
        self.assertEqual(Contribution.objects.count(), 0)
        self.assertEqual(
            AuditEvent.objects.filter(
                action=AuditEvent.Action.ENROLMENT_REQUEST_ENROLLED,
            ).count(),
            1,
        )

    def test_owner_cannot_convert_for_a_deactivated_customer_login(self):
        request = self.submit().enrolment_request
        self.customer.user.is_active = False
        self.customer.user.save(update_fields=["is_active"])

        with self.assertRaisesMessage(ValidationError, "no longer active"):
            enroll_customer_from_request(
                enrolment_request=request,
                actor=self.owner,
                current_terms_confirmed=True,
                start_date=date(2026, 9, 4),
                agreed_months=12,
                reason="Current terms confirmed by phone.",
            )

        self.assertEqual(SchemeAccount.objects.count(), 0)

    def test_terminal_request_and_snapshot_are_immutable(self):
        request = self.submit().enrolment_request
        decide_scheme_enrolment_request(
            enrolment_request=request,
            status=request.Status.DECLINED,
            actor=self.owner,
            reason="Customer did not confirm.",
        )
        request.customer_message = "Changed later"

        with self.assertRaises(ValidationError):
            request.save()
        with self.assertRaises(ValidationError):
            request.delete()

    def test_integrity_command_reports_valid_state(self):
        self.submit()
        stdout = io.StringIO()

        call_command("check_scheme_enrolment_requests", stdout=stdout)

        output = stdout.getvalue()
        self.assertIn("scheme_enrolment_requests status=ok", output)
        self.assertIn("pending=1", output)
        self.assertIn("enabled=true", output)

    def test_public_flow_sends_acknowledgement_and_owner_notice(self):
        self.client.force_login(self.customer.user)

        response = self.client.post(
            reverse("schemes:scheme_enrolment_request_create", args=[self.plan.pk]),
            {
                "metal_grade": self.grade.pk,
                "requested_contribution_amount": "1000.00",
                "requested_months": "12",
                "customer_message": "Please call after 6 PM.",
                "disclosure_accepted": "on",
            },
        )

        request = SchemeEnrolmentRequest.objects.get()
        self.assertRedirects(
            response,
            reverse("schemes:my_enrolment_request_detail", args=[request.pk]),
        )
        self.assertEqual(len(mail.outbox), 2)
        customer_message = next(
            message
            for message in mail.outbox
            if message.to == [self.customer.email]
        )
        self.assertIn("non-binding", customer_message.body)
        self.assertIn("does not create payment access", customer_message.body)
        self.assertNotIn("contribute now", customer_message.body.lower())

    def test_customer_cannot_view_another_customers_request(self):
        request = self.submit().enrolment_request
        self.client.force_login(self.other_customer.user)

        response = self.client.get(
            reverse("schemes:my_enrolment_request_detail", args=[request.pk])
        )

        self.assertEqual(response.status_code, 404)

    def test_owner_queue_converts_request_only_after_explicit_confirmation(self):
        request = self.submit().enrolment_request
        mail.outbox.clear()
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("schemes:owner_enrolment_request_enroll", args=[request.pk]),
            {
                "plan": self.plan.pk,
                "metal_grade": self.grade.pk,
                "start_date": "2026-09-04",
                "agreed_months": "12",
                "audit_reason": "Current terms confirmed with customer.",
                "current_terms_confirmed": "on",
            },
        )

        self.assertRedirects(
            response,
            reverse("schemes:owner_enrolment_request_detail", args=[request.pk]),
        )
        request.refresh_from_db()
        self.assertEqual(request.status, request.Status.ENROLLED)
        self.assertIsNotNone(request.scheme_account)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("agreement has been created", mail.outbox[0].body)

    def test_feature_flag_hides_cta_and_blocks_new_request(self):
        self.client.force_login(self.customer.user)
        with override_settings(CUSTOMER_ENROLMENT_REQUESTS_ENABLED=False):
            pricing = self.client.get(reverse("pricing"))
            create = self.client.get(
                reverse(
                    "schemes:scheme_enrolment_request_create",
                    args=[self.plan.pk],
                )
            )

        self.assertNotContains(pricing, "Request enrolment")
        self.assertEqual(create.status_code, 404)

    def test_logged_out_pricing_prompts_sign_in_without_promising_enrolment(self):
        response = self.client.get(reverse("pricing"))

        self.assertContains(response, "Sign in to request enrolment")
        self.assertContains(response, "non-binding request")
        self.assertContains(response, "does not create a savings agreement")
