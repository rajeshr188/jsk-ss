"""Registration-first integration behind unchanged financial readiness gates."""
from datetime import timedelta
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from django.core import mail
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import connection, connections, IntegrityError, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.application_contracts import validate_independent_application
from accounts.applications import (application_terms_current, approve_plan_application, complete_plan_application,
    offer_form_digest, submit_plan_application, verify_plan_application)
from accounts.models import CustomerInvitation, CustomerRegistration, PlanApplication, PlanApplicationConfirmation
from accounts.test_plan_applications import APPLICATION_SETTINGS, ApplicationFixtures
from schemes.models import Contribution, Customer, InrPrincipalReceipt, MetalAllocation, SchemeAccount, SchemePlan, SchemePlanOffering
from schemes.plan_governance import ensure_plan_revision
from schemes.tests.test_audit_exceptions import make_owner
from schemes.tests.test_independent_agreement_storage import preparation
from schemes.tests.test_independent_enrolment import future_readiness_only
from schemes.tests.test_independent_policy_fields import independent_values, required_values


SETTINGS = {key: value for key, value in APPLICATION_SETTINGS.items() if key != "PASSWORD_HASHERS"}
SETTINGS.update(CONFIGURED_PLANS_ENABLED=True, PUBLIC_REGISTRATION_ATTEMPTS_PER_HOUR=100)


class IndependentApplicationFixtures:
    def setUp(self):
        self.owner = make_owner()
        self.start_date = timezone.localdate() + timedelta(days=2)
        self.counter = 0

    def offer(self, values=None):
        config, plan, _, grade = preparation(self.owner, values or independent_values(accumulation="INR_PURCHASE_CREDIT"))
        if grade:
            SchemePlanOffering.objects.create(plan=plan, metal_grade=grade)
        plan.active = plan.publicly_listed = True
        revision = ensure_plan_revision(plan=plan, actor=self.owner, reason="Disposable future offer")
        SchemePlan.objects.filter(pk=plan.pk).update(active=True, publicly_listed=True, publication_revision=revision)
        plan.refresh_from_db()
        self.plan, self.grade = plan, grade
        return plan

    def submit(self, **changes):
        self.counter += 1
        args = dict(plan=self.plan, metal_grade=self.grade, amount=Decimal("500"),
            months=self.plan.configuration.duration_months, message="Please review", full_name="Application Customer",
            email=f"future-{self.counter}@example.com", mobile_number=f"900000{self.counter:04d}",
            source_ip="203.0.113.7", offer_digest=offer_form_digest(self.plan), base_url="https://example.test")
        with future_readiness_only():
            return submit_plan_application(**(args | changes))

    verify = ApplicationFixtures.verify
    grant = ApplicationFixtures.grant

    def complete(self, application, **changes):
        args = dict(registration_id=application.registration_id, access_digest=application.progress_token_digest,
            address="12 Fictional Street, Vellore", metal_grade=self.grade, amount=Decimal("500"),
            months=self.plan.configuration.duration_months, message="Reviewed", start_date=self.start_date,
            offer_digest=offer_form_digest(self.plan))
        with future_readiness_only():
            return complete_plan_application(**(args | changes))

    def approve(self, application, **changes):
        with future_readiness_only():
            return ApplicationFixtures.approve(self, application, **changes)

    def ready(self):
        return self.complete(self.verify(self.submit()))


@override_settings(**SETTINGS)
class IndependentApplicationTests(IndependentApplicationFixtures, TestCase):
    def test_five_families_both_denominations_pin_confirmation_and_atomic_identity_agreement(self):
        for accumulation in ("EXACT_METAL", "INR_PURCHASE_CREDIT"):
            cases = [independent_values(accumulation=accumulation),
                independent_values(accumulation=accumulation, eligibility_policy="CALENDAR", duration_months=1),
                required_values(accumulation=accumulation, required_count=2),
                required_values(accumulation=accumulation, required_count=2, eligibility_policy="CALENDAR_AND_COUNT", duration_months=18),
                required_values(accumulation=accumulation, required_count=2, eligibility_policy="CALENDAR", duration_months=12,
                    missed_payment_policy="LOSE_UNEARNED_BENEFIT", max_extension_months=None,
                    benefit_policy="VA_DISCOUNT", benefit_percentage=Decimal("5"), benefit_cap_inr=Decimal("500"),
                    benefit_qualification="REQUIRED_SCHEDULE", benefit_on_miss="DISQUALIFY_UNEARNED",
                    eligible_charge_definition="Making charges excluding taxes")]
            for values in cases:
                with self.subTest(accumulation=accumulation, eligibility=values["eligibility_policy"]):
                    self.offer(values)
                    before = (Customer.objects.count(), SchemeAccount.objects.count())
                    application = self.ready()
                    self.assertEqual((Customer.objects.count(), SchemeAccount.objects.count()), before)
                    latest = validate_independent_application(application)
                    self.assertEqual(application.terms_schema_version, 2)
                    self.assertEqual(application.requested_months, values["duration_months"])
                    self.assertEqual(latest.offer["required_count"], values["required_count"])
                    self.assertEqual(latest.plan_revision_id, self.plan.publication_revision_id)
                    account, created = self.approve(application)
                    self.assertTrue(created)
                    application.refresh_from_db()
                    validate_independent_application(application)
                    self.assertEqual(account.required_count_snapshot, values["required_count"])
                    self.assertEqual(account.agreed_months, values["duration_months"])
                    self.assertEqual(self.approve(application), (account, False))
        for model in (Contribution, InrPrincipalReceipt, MetalAllocation):
            self.assertFalse(model.objects.exists())
        output = StringIO()
        call_command("check_public_customer_registrations", stdout=output)
        self.assertIn("status=ok", output.getvalue())

    def test_gates_reject_unpatched_services_and_public_forms(self):
        self.offer()
        application = self.ready()
        for enabled in (False, True):
            with self.settings(CONFIGURED_PLANS_ENABLED=enabled):
                with self.assertRaises(ValidationError):
                    submit_plan_application(plan=self.plan, metal_grade=None, amount=Decimal("500"), months=None,
                        message="", full_name="Blocked", email="blocked@example.com", mobile_number="9000000099",
                        source_ip="203.0.113.8", offer_digest=offer_form_digest(self.plan), base_url="https://example.test")
                with self.assertRaises(ValidationError):
                    approve_plan_application(registration_id=application.registration_id, actor=self.owner,
                        mobile_verified=True, terms_reviewed=True, reason="Reviewed", base_url="https://example.test")
                self.assertFalse(application_terms_current(application))
        self.assertFalse(SchemeAccount.objects.exists())

    def test_stale_offer_requires_new_explicit_confirmation_and_preserves_history(self):
        self.offer(required_values(accumulation="INR_PURCHASE_CREDIT", required_count=2))
        application = self.ready()
        first = application.confirmations.first().offer.copy()
        self.plan.name = "Revised name"
        revision = ensure_plan_revision(plan=self.plan, actor=self.owner, reason="New reviewed offer")
        SchemePlan.objects.filter(pk=self.plan.pk).update(name=self.plan.name, publication_revision=revision)
        with future_readiness_only():
            self.assertFalse(application_terms_current(application))
        with self.assertRaises(ValidationError):
            self.approve(application)
        self.plan.refresh_from_db()
        application = self.complete(application)
        self.assertEqual(application.confirmations.count(), 3)
        self.assertEqual(application.confirmations.first().offer, first)
        self.assertTrue(self.approve(application)[1])

    def test_amount_duration_denomination_and_owner_confirmation_cannot_be_substituted(self):
        self.offer(required_values(accumulation="INR_PURCHASE_CREDIT", required_count=2))
        application = self.ready()
        for changes in (dict(months=2), dict(amount=Decimal("99")), dict(offer_digest="stale")):
            with self.assertRaises(ValidationError):
                self.complete(application, **changes)
        for changes in (dict(mobile_verified="yes"), dict(terms_reviewed=1), dict(terms_reviewed=False)):
            with self.assertRaises(ValidationError):
                self.approve(application, **changes)
        self.assertFalse(Customer.objects.exists())
        self.assertFalse(SchemeAccount.objects.exists())

    def test_corrupt_confirmation_blocks_identity_and_financial_creation(self):
        self.offer()
        application = self.ready()
        confirmation = application.confirmations.last()
        changed = confirmation.offer | dict(required_count=12)
        PlanApplicationConfirmation.objects.filter(pk=confirmation.pk).update(offer=changed)
        with self.assertRaises(ValidationError):
            self.approve(application)
        self.assertFalse(Customer.objects.exists())
        self.assertFalse(CustomerInvitation.objects.exists())
        self.assertFalse(SchemeAccount.objects.exists())

    def test_financial_failure_rolls_back_identity_invitation_and_agreement(self):
        self.offer()
        application = self.ready()
        with patch("schemes.services.record_audit_event", side_effect=RuntimeError), self.assertRaises(RuntimeError):
            self.approve(application)
        self.assertFalse(Customer.objects.exists())
        self.assertFalse(CustomerInvitation.objects.exists())
        self.assertFalse(SchemeAccount.objects.exists())
        application.registration.refresh_from_db()
        self.assertEqual(application.registration.status, "AWAITING_OWNER_APPROVAL")

    def test_frozen_progress_email_distinguishes_inr_and_no_duration(self):
        self.offer()
        with self.captureOnCommitCallbacks(execute=True):
            submission = self.submit()
            application = self.verify(submission)
        self.assertIn("INR jewellery purchase credit", mail.outbox[-1].body)
        self.assertIn("No minimum-duration condition", mail.outbox[-1].body)
        self.assertNotIn("12 months", mail.outbox[-1].body)
        self.assertEqual(mail.outbox[-1].extra_headers["X-PM-TrackLinks"], "None")
        self.assertFalse(Customer.objects.exists())

    def test_browser_contact_completion_owner_review_and_activation_delivery(self):
        self.offer(required_values(accumulation="INR_PURCHASE_CREDIT", required_count=2))
        url = reverse("customer_registration") + f"?plan={self.plan.pk}"
        with future_readiness_only():
            response = self.client.get(url)
            self.assertContains(response, 'name="offer_token"')
            self.assertContains(response, "No minimum-duration condition")
            form = response.context["form"]
            response = self.client.post(url, dict(full_name="Browser Applicant", email="browser@example.com",
                mobile_number="9000000088", requested_contribution_amount="500", requested_months="",
                disclosure_accepted=True, accept_policies=True, offer_digest=form["offer_digest"].value(),
                offer_token=form["offer_token"].value()))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(PlanApplication.objects.count(), 1)
        # Verify through the existing one-use email service using the test-owned raw token.
        application = PlanApplication.objects.get()
        from accounts.services import _token_digest
        raw = "test-owned-verification-token"
        CustomerRegistration.objects.filter(pk=application.registration_id).update(email_token_digest=_token_digest(raw))
        application = verify_plan_application(registration_id=application.registration_id, raw_token=raw, base_url="https://example.test")
        self.grant(application)
        url = reverse("plan_application_progress", args=[application.registration_id])
        with future_readiness_only():
            response = self.client.get(url)
            form = response.context["form"]
            response = self.client.post(url, dict(address="12 Fictional Street, Vellore", start_date=str(self.start_date),
                requested_contribution_amount="500", requested_months="", disclosure_accepted=True, accept_policies=True,
                offer_digest=form["offer_digest"].value(), offer_token=form["offer_token"].value()))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Customer.objects.exists())
        self.client.force_login(self.owner)
        with future_readiness_only():
            response = self.client.get(reverse("customer_registration_detail", args=[application.registration_id]))
            self.assertContains(response, "2 qualifying monthly payments")
            self.assertNotContains(response, "None months")
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(reverse("plan_application_approve", args=[application.registration_id]),
                    dict(mobile_verified=True, terms_reviewed=True, reason="Verified at showroom"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(SchemeAccount.objects.count(), 1)
        self.assertTrue(CustomerInvitation.objects.get().email_sent_at)
        self.assertFalse(Contribution.objects.exists())

    def test_plan_fixed_amount_and_explicit_reconfirmation_have_no_legacy_defaults(self):
        self.offer(independent_values(accumulation="INR_PURCHASE_CREDIT", amount_policy="PLAN_FIXED",
            fixed_amount=Decimal("500"), minimum_amount=Decimal("500"), maximum_amount=Decimal("500")))
        application = self.ready()
        self.grant(application)
        with future_readiness_only():
            response = self.client.get(reverse("plan_application_progress", args=[application.registration_id]))
            self.assertEqual(response.context["form"]["requested_contribution_amount"].value(), Decimal("500"))
            self.assertIsNone(response.context["form"]["requested_months"].value())
        account, _ = self.approve(application)
        self.assertEqual(account.fixed_amount_snapshot, Decimal("500"))
        self.assertIsNone(account.eligible_from)

    def test_consent_versions_expired_grant_and_disabled_completion_fail_closed(self):
        self.offer()
        application = self.ready()
        with self.settings(PUBLIC_REGISTRATION_TERMS_VERSION="new-terms"):
            with self.assertRaises(ValidationError):
                self.approve(application)
        with self.assertRaises(ValidationError):
            self.complete(application, access_digest="wrong")
        with self.settings(CUSTOMER_ENROLMENT_REQUESTS_ENABLED=False), self.assertRaises(ValidationError):
            self.complete(application)
        PlanApplication.objects.filter(pk=application.pk).update(expires_at=timezone.now()-timedelta(seconds=1))
        with self.assertRaises(ValidationError):
            self.approve(application)
        self.assertFalse(Customer.objects.exists())

    def test_changed_denomination_requires_fresh_confirmation_not_a_broken_page(self):
        self.offer(independent_values(accumulation="EXACT_METAL"))
        application = self.ready()
        previous = application.confirmations.last().offer
        original_plan = self.plan
        self.offer(independent_values(accumulation="INR_PURCHASE_CREDIT"))
        replacement = self.plan.configuration
        SchemePlan.objects.filter(pk=original_plan.pk).update(configuration=replacement)
        SchemePlanOffering.objects.filter(plan=original_plan).update(active=False)
        original_plan.refresh_from_db()
        revision = ensure_plan_revision(plan=original_plan, actor=self.owner, reason="New proposed denomination")
        SchemePlan.objects.filter(pk=original_plan.pk).update(publication_revision=revision)
        original_plan.refresh_from_db()
        self.plan, self.grade = original_plan, None
        with future_readiness_only():
            self.assertFalse(application_terms_current(application))
        with self.assertRaises(ValidationError):
            self.approve(application)
        self.grant(application)
        with future_readiness_only():
            response = self.client.get(reverse("plan_application_progress", args=[application.registration_id]))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["needs_confirmation"])
        application = self.complete(application)
        self.assertEqual(application.confirmations.get(sequence=2).offer, previous)
        account, _ = self.approve(application)
        self.assertIsNone(account.metal_grade_id)
        self.assertEqual(account.configuration_snapshot_id, replacement.pk)

    def test_invalid_version_and_confirmation_provenance_database_shapes(self):
        self.offer()
        application = self.ready()
        for changes in (dict(terms_schema_version=3), dict(terms_schema_version=1), dict(requested_months=0)):
            with self.assertRaises(IntegrityError), transaction.atomic():
                PlanApplication.objects.filter(pk=application.pk).update(**changes)
        confirmation = application.confirmations.last()
        for changes in (dict(plan_revision=None), dict(terms_schema_version=1), dict(requested_months=0)):
            with self.assertRaises(IntegrityError), transaction.atomic():
                PlanApplicationConfirmation.objects.filter(pk=confirmation.pk).update(**changes)
        with self.assertRaises(ValidationError):
            confirmation.save()


@override_settings(**SETTINGS)
class IndependentApplicationTransactionTests(IndependentApplicationFixtures, TransactionTestCase):
    def test_forward_migration_refuses_unversioned_independent_consent(self):
        ApplicationFixtures.setUp(self)
        application = self.verify(ApplicationFixtures.submit(self))
        executor = MigrationExecutor(connection)
        leaves = executor.loader.graph.leaf_nodes()
        old = [("accounts", "0008_customerinvitation_recovery_requested_at")]
        executor.migrate(old)
        historical = MigrationExecutor(connection).loader.project_state(old).apps
        Confirmation = historical.get_model("accounts", "PlanApplicationConfirmation")
        row = Confirmation.objects.get(application_id=application.pk)
        original = row.offer.copy()
        Confirmation.objects.filter(pk=row.pk).update(offer=original | {"configuration": {"policy_schema_version": 2}})
        try:
            with self.assertRaisesMessage(RuntimeError, "Unversioned independent applications"):
                MigrationExecutor(connection).migrate(leaves)
        finally:
            Confirmation.objects.filter(pk=row.pk).update(offer=original)
            MigrationExecutor(connection).migrate(leaves)
        self.assertEqual(PlanApplicationConfirmation.objects.get(pk=row.pk).offer, original)

    def test_concurrent_approval_creates_one_identity_agreement_and_invitation(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        self.offer(required_values(accumulation="INR_PURCHASE_CREDIT", required_count=2))
        application = self.ready()
        barrier = Barrier(2)
        def approve():
            connections.close_all()
            try:
                barrier.wait(timeout=20)
                account, created = approve_plan_application(registration_id=application.registration_id, actor=self.owner,
                    mobile_verified=True, terms_reviewed=True, reason="Reviewed", base_url="https://example.test")
                return account.pk, created
            finally:
                connections.close_all()
        with future_readiness_only(), ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: approve(), range(2)))
        self.assertEqual(results[0][0], results[1][0])
        self.assertEqual(sum(created for _, created in results), 1)
        self.assertEqual(Customer.objects.count(), 1)
        self.assertEqual(SchemeAccount.objects.count(), 1)
        self.assertEqual(CustomerInvitation.objects.count(), 1)

    def test_migration_preserves_legacy_and_refuses_erasing_independent_confirmations(self):
        ApplicationFixtures.setUp(self)
        submission = ApplicationFixtures.submit(self)
        application = ApplicationFixtures.complete(self, self.verify(submission))
        before = PlanApplication.objects.filter(pk=application.pk).values().get()
        confirmations = list(PlanApplicationConfirmation.objects.values())
        executor = MigrationExecutor(connection)
        leaves = executor.loader.graph.leaf_nodes()
        self.addCleanup(lambda: MigrationExecutor(connection).migrate(leaves))
        executor.migrate([("accounts", "0008_customerinvitation_recovery_requested_at")])
        MigrationExecutor(connection).migrate(leaves)
        self.assertEqual(PlanApplication.objects.filter(pk=application.pk).values().get(), before)
        self.assertEqual(list(PlanApplicationConfirmation.objects.values()), confirmations)
        self.offer()
        independent = self.ready()
        with self.assertRaisesMessage(RuntimeError, "Independent application evidence exists"):
            MigrationExecutor(connection).migrate([("accounts", "0008_customerinvitation_recovery_requested_at")])
        self.assertTrue(PlanApplication.objects.filter(pk=independent.pk).exists())
