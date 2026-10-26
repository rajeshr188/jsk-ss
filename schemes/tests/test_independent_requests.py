"""Future request integration in disposable PostgreSQL; runtime gates stay closed."""
from datetime import date
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.core import mail
from django.core.management import call_command
from django.db import IntegrityError, transaction, connection, connections, close_old_connections
from django.db.migrations.executor import MigrationExecutor
from django.template.loader import render_to_string
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse

from schemes.enrolment_contracts import validate_request_terms
from schemes.forms import EnrolmentRequestConversionForm, SchemeEnrolmentRequestForm
from schemes.models import (AuditEvent, Contribution, InrPrincipalReceipt, MetalAllocation,
    SchemeAccount, SchemeEnrolmentRequest, SchemePlan, SchemePlanOffering)
from schemes.plan_governance import ensure_plan_revision, plan_edit_digest
from schemes.services import (submit_scheme_enrolment_request, enroll_customer_from_request,
    enrolment_request_offer_is_current, withdraw_scheme_enrolment_request)
from schemes.tests.test_audit_exceptions import make_owner, make_customer, make_plan
from schemes.tests.test_independent_agreement_storage import preparation
from schemes.tests.test_independent_enrolment import future_readiness_only
from schemes.tests.test_independent_policy_fields import independent_values, required_values


@override_settings(CONFIGURED_PLANS_ENABLED=True, CUSTOMER_ENROLMENT_REQUESTS_ENABLED=True,
    CUSTOMER_ENROLMENT_REQUEST_DISCLOSURE_VERSION="test-independent-v2")
class IndependentRequestTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner, cls.customer = make_owner(), make_customer()

    def offer(self, values=None):
        config, plan, _, grade = preparation(self.owner, values or independent_values(accumulation="INR_PURCHASE_CREDIT"))
        if grade:
            SchemePlanOffering.objects.create(plan=plan, metal_grade=grade)
        plan.active = plan.publicly_listed = True
        revision = ensure_plan_revision(plan=plan, actor=self.owner, reason="Disposable public offer")
        SchemePlan.objects.filter(pk=plan.pk).update(active=True, publicly_listed=True, publication_revision=revision)
        plan.refresh_from_db()
        return dict(customer=self.customer, plan=plan, metal_grade=grade,
            requested_contribution_amount=Decimal("500"), requested_months=config.duration_months,
            customer_message="Please review", actor=self.customer.user, expected_plan_digest=plan_edit_digest(plan))

    def submit(self, offer):
        with future_readiness_only():
            return submit_scheme_enrolment_request(**offer).enrolment_request

    def convert(self, request, **changes):
        args = dict(enrolment_request=request, actor=self.owner, current_terms_confirmed=True,
            start_date=date(2026, 1, 30), agreed_months=request.requested_months, reason="Reviewed exact request")
        with future_readiness_only():
            return enroll_customer_from_request(**(args | changes))

    def form_data(self, offer):
        form = SchemeEnrolmentRequestForm(plan=offer["plan"])
        return dict(metal_grade=offer["metal_grade"].pk if offer["metal_grade"] else "",
            requested_contribution_amount="500", requested_months=offer["requested_months"] or "",
            customer_message="Review", disclosure_accepted=True, offer_token=form["offer_token"].value())

    def test_five_families_both_denominations_submit_and_convert_without_financial_effect(self):
        for accumulation in ("INR_PURCHASE_CREDIT", "EXACT_METAL"):
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
                    offer = self.offer(values)
                    before = SchemeAccount.objects.count()
                    request = self.submit(offer)
                    self.assertEqual(SchemeAccount.objects.count(), before)
                    self.assertEqual(request.request_schema_version, 2)
                    self.assertEqual(request.requested_months, values["duration_months"])
                    self.assertEqual(request.required_count_snapshot, values["required_count"])
                    validate_request_terms(request)
                    account, created = self.convert(request)
                    self.assertTrue(created)
                    self.assertEqual(SchemeAccount.objects.count(), before + 1)
                    request.refresh_from_db()
                    validate_request_terms(request)
                    self.assertEqual(account.plan_revision_id, request.plan_revision_snapshot_id)
                    self.assertEqual(account.agreed_months, request.requested_months)
                    self.assertEqual(account.required_count_snapshot, request.required_count_snapshot)
                    self.assertEqual(self.convert(request), (account, False))
        for model in (Contribution, InrPrincipalReceipt, MetalAllocation):
            self.assertFalse(model.objects.exists())

    def test_request_and_conversion_forms_keep_count_separate_from_duration(self):
        for accumulation in ("INR_PURCHASE_CREDIT", "EXACT_METAL"):
            offer = self.offer(required_values(accumulation=accumulation, required_count=2))
            data = self.form_data(offer)
            with future_readiness_only():
                form = SchemeEnrolmentRequestForm(data, plan=offer["plan"])
                self.assertTrue(form.is_valid(), form.errors)
                self.assertIsNone(form.cleaned_data["requested_months"])
                wrong = SchemeEnrolmentRequestForm(data | dict(requested_months=2), plan=offer["plan"])
                self.assertFalse(wrong.is_valid())
            request = self.submit(offer)
            initial = EnrolmentRequestConversionForm(enrolment_request=request)
            conversion = EnrolmentRequestConversionForm(dict(start_date="2026-01-30", audit_reason="Reviewed",
                selected_amount_confirmed=True, current_terms_confirmed=True,
                configuration_token=initial["configuration_token"].value()), enrolment_request=request)
            self.assertTrue(conversion.is_valid(), conversion.errors)
            self.assertIsNone(conversion.cleaned_data["agreed_months"])

    def test_stale_form_digest_and_stale_request_are_rejected(self):
        offer = self.offer()
        data = self.form_data(offer)
        request = self.submit(offer)
        SchemePlan.objects.filter(pk=offer["plan"].pk).update(name="Changed offer")
        offer["plan"].refresh_from_db()
        with future_readiness_only():
            form = SchemeEnrolmentRequestForm(data, plan=offer["plan"])
            self.assertFalse(form.is_valid())
            self.assertFalse(enrolment_request_offer_is_current(request))
        with self.assertRaises(ValidationError):
            self.convert(request)
        self.assertFalse(SchemeAccount.objects.exists())

    def test_digest_signature_and_disclosure_version_required(self):
        offer = self.offer()
        data = self.form_data(offer)
        with future_readiness_only():
            for token in ("", "forged"):
                self.assertFalse(SchemeEnrolmentRequestForm(data | dict(offer_token=token), plan=offer["plan"]).is_valid())
            with self.settings(CUSTOMER_ENROLMENT_REQUEST_DISCLOSURE_VERSION="changed"):
                self.assertFalse(SchemeEnrolmentRequestForm(data, plan=offer["plan"]).is_valid())
            with self.assertRaises(ValidationError):
                submit_scheme_enrolment_request(**(offer | dict(expected_plan_digest=None)))

    def test_runtime_gates_still_reject_requests_and_conversion(self):
        offer = self.offer()
        data = self.form_data(offer)
        request = self.submit(offer)
        for enabled in (False, True):
            with self.settings(CONFIGURED_PLANS_ENABLED=enabled):
                self.assertFalse(SchemeEnrolmentRequestForm(data, plan=offer["plan"]).is_valid())
                with self.assertRaises(ValidationError):
                    submit_scheme_enrolment_request(**offer)
                with self.assertRaises(ValidationError):
                    enroll_customer_from_request(enrolment_request=request, actor=self.owner, current_terms_confirmed=True,
                        start_date=date(2026, 1, 30), agreed_months=None, reason="Review")
        self.assertFalse(SchemeAccount.objects.exists())

    def test_inr_retry_unique_null_grade_and_immutable_snapshots(self):
        offer = self.offer()
        request = self.submit(offer)
        with future_readiness_only():
            repeat = submit_scheme_enrolment_request(**offer)
        self.assertFalse(repeat.created)
        self.assertEqual(repeat.enrolment_request.pk, request.pk)
        import copy, uuid
        duplicate = copy.copy(request)
        duplicate.pk = uuid.uuid4()
        with self.assertRaises(IntegrityError), transaction.atomic():
            SchemeEnrolmentRequest.objects.bulk_create([duplicate])
        request.offer_digest = "0" * 64
        with self.assertRaises(ValidationError):
            request.save()
        self.assertEqual(SchemeEnrolmentRequest.objects.count(), 1)

    def test_invalid_count_duration_and_grade_shapes_rejected_by_database(self):
        request = self.submit(self.offer())
        for changes in (dict(request_schema_version=3), dict(requested_months=12),
                        dict(savings_mode_snapshot="GOLD"), dict(required_count_snapshot=1),
                        dict(plan_revision_snapshot=None)):
            with self.subTest(changes=changes), self.assertRaises(IntegrityError), transaction.atomic():
                SchemeEnrolmentRequest.objects.filter(pk=request.pk).update(**changes)

    def test_conversion_requires_owner_exact_confirmation_and_duration(self):
        request = self.submit(self.offer(required_values(accumulation="INR_PURCHASE_CREDIT")))
        for changes in (dict(actor=self.customer.user), dict(current_terms_confirmed="yes"),
                        dict(current_terms_confirmed=False), dict(agreed_months=12)):
            with self.assertRaises(ValidationError):
                self.convert(request, **changes)
        self.assertFalse(SchemeAccount.objects.exists())

    def test_audit_failure_rolls_back_submission_and_conversion(self):
        offer = self.offer()
        with future_readiness_only(), patch("schemes.services.record_audit_event", side_effect=RuntimeError), self.assertRaises(RuntimeError):
            submit_scheme_enrolment_request(**offer)
        self.assertFalse(SchemeEnrolmentRequest.objects.exists())
        request = self.submit(offer)
        with patch("schemes.services.record_audit_event", side_effect=RuntimeError), self.assertRaises(RuntimeError):
            self.convert(request)
        self.assertFalse(SchemeAccount.objects.exists())
        request.refresh_from_db()
        self.assertEqual(request.status, "PENDING_OWNER_REVIEW")
        from schemes.services import record_audit_event
        def final_audit(**kwargs):
            if kwargs["action"] == "ENROLMENT_REQUEST_ENROLLED":
                raise RuntimeError("Final conversion audit failed")
            return record_audit_event(**kwargs)
        with patch("schemes.services.record_audit_event", side_effect=final_audit), self.assertRaises(RuntimeError):
            self.convert(request)
        self.assertFalse(SchemeAccount.objects.exists())
        request.refresh_from_db()
        self.assertEqual(request.status, "PENDING_OWNER_REVIEW")

    def test_frozen_email_terms_no_false_maturity_or_metal_and_integrity_check(self):
        request = self.submit(self.offer())
        context = dict(enrolment_request=request, audience="customer", event="received", action_url="https://example.invalid/request/")
        for extension in ("txt", "html"):
            body = render_to_string("schemes/email/enrolment_request_message." + extension, context)
            self.assertIn("INR jewellery purchase credit", body)
            self.assertIn("No minimum-duration condition", body)
            self.assertIn("No mandatory instalments", body)
            self.assertNotIn("12 months", body)
        output = StringIO()
        call_command("check_scheme_enrolment_requests", stdout=output)
        self.assertIn("independent_term_mismatches=0", output.getvalue())
        withdraw_scheme_enrolment_request(enrolment_request=request, actor=self.customer.user)
        request.refresh_from_db()
        self.assertEqual(request.status, "WITHDRAWN")

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_browser_request_review_and_conversion_email_path(self):
        offer = self.offer(required_values(accumulation="INR_PURCHASE_CREDIT", required_count=2))
        self.client.force_login(self.customer.user)
        url = reverse("schemes:scheme_enrolment_request_create", args=[offer["plan"].pk])
        with future_readiness_only():
            page = self.client.get(url)
            self.assertContains(page, "No minimum-duration condition")
            self.assertNotContains(page, "12 months")
            data = self.form_data(offer)
            response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        request = SchemeEnrolmentRequest.objects.get()
        self.assertFalse(SchemeAccount.objects.exists())
        self.assertEqual(len(mail.outbox), 2)
        self.assertIn("INR jewellery purchase credit", mail.outbox[0].body)
        self.client.force_login(self.owner)
        with future_readiness_only():
            page = self.client.get(reverse("schemes:owner_enrolment_request_detail", args=[request.pk]))
            self.assertContains(page, "2 qualifying monthly payments")
            self.assertNotContains(page, "None months")
            form = page.context["form"]
            response = self.client.post(reverse("schemes:owner_enrolment_request_enroll", args=[request.pk]),
                dict(start_date="2026-01-30", audit_reason="Reviewed with customer", current_terms_confirmed=True,
                    selected_amount_confirmed=True, configuration_token=form["configuration_token"].value()))
        self.assertEqual(response.status_code, 302)
        request.refresh_from_db()
        self.assertEqual(request.status, "ENROLLED")
        self.assertEqual(len(mail.outbox), 3)
        self.assertIn("agreement has been created", mail.outbox[-1].body)
        self.assertEqual(SchemeAccount.objects.count(), 1)
        self.assertFalse(Contribution.objects.exists())
        output = StringIO()
        call_command("check_scheme_enrolment_requests", stdout=output)
        self.assertIn("status=ok", output.getvalue())

    def test_foreign_grade_configuration_substitution_and_html_escaping(self):
        offer = self.offer(required_values(accumulation="EXACT_METAL", required_count=2))
        request = self.submit(offer)
        other = self.offer(required_values(accumulation="EXACT_METAL", required_count=3))
        SchemeEnrolmentRequest.objects.filter(pk=request.pk).update(configuration_snapshot=other["plan"].configuration)
        with self.assertRaises(ValidationError):
            self.convert(request)
        self.assertFalse(SchemeAccount.objects.exists())
        inr = self.offer()
        with self.assertRaises(ValidationError):
            self.submit(inr | dict(metal_grade=offer["metal_grade"]))
        safe_request = self.submit(inr)
        safe_request.plan_name_snapshot = "<script>alert(1)</script>"
        html = render_to_string("schemes/email/enrolment_request_message.html",
            dict(enrolment_request=safe_request, audience="customer", event="received"))
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)


@override_settings(CONFIGURED_PLANS_ENABLED=True, CUSTOMER_ENROLMENT_REQUESTS_ENABLED=True,
    CUSTOMER_ENROLMENT_REQUEST_DISCLOSURE_VERSION="test-independent-v2")
class IndependentRequestTransactionTests(TransactionTestCase):
    offer = IndependentRequestTests.offer
    submit = IndependentRequestTests.submit

    def setUp(self):
        self.owner, self.customer = make_owner(), make_customer()

    def test_legacy_migration_roundtrip_preserves_history_and_version_two_blocks_reverse(self):
        from schemes.tests.grade_helpers import grade_for_mode
        plan = make_plan()
        SchemePlan.objects.filter(pk=plan.pk).update(publicly_listed=True)
        plan.refresh_from_db()
        grade = grade_for_mode(plan, "GOLD", code="GOLD_22K_916")
        legacy = submit_scheme_enrolment_request(customer=self.customer, plan=plan, metal_grade=grade,
            requested_contribution_amount=Decimal("500"), requested_months=12, customer_message="Preserve",
            actor=self.customer.user).enrolment_request
        before = SchemeEnrolmentRequest.objects.filter(pk=legacy.pk).values().get()
        executor = MigrationExecutor(connection)
        leaves = executor.loader.graph.leaf_nodes()
        self.addCleanup(lambda: MigrationExecutor(connection).migrate(leaves))
        executor.migrate([("schemes", "0044_inr_api_capture_evidence")])
        MigrationExecutor(connection).migrate(leaves)
        self.assertEqual(SchemeEnrolmentRequest.objects.filter(pk=legacy.pk).values().get(), before)
        request = self.submit(self.offer())
        with self.assertRaisesMessage(RuntimeError, "Independent enrolment requests exist"):
            MigrationExecutor(connection).migrate([("schemes", "0044_inr_api_capture_evidence")])
        self.assertTrue(SchemeEnrolmentRequest.objects.filter(pk=request.pk, request_schema_version=2).exists())

    def test_concurrent_inr_submission_is_single_request_and_audit(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        offer = self.offer()
        barrier = Barrier(2)
        def submit():
            close_old_connections()
            try:
                barrier.wait(timeout=20)
                result = submit_scheme_enrolment_request(**offer)
                return result.enrolment_request.pk, result.created
            finally:
                connections.close_all()
        with future_readiness_only(), ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: submit(), range(2)))
        self.assertEqual(results[0][0], results[1][0])
        self.assertEqual(sum(created for _, created in results), 1)
        self.assertEqual(SchemeEnrolmentRequest.objects.count(), 1)
        self.assertEqual(AuditEvent.objects.filter(action="ENROLMENT_REQUEST_SUBMITTED").count(), 1)

    def test_forward_migration_refuses_inventing_terms_for_unversioned_requests(self):
        from schemes.tests.grade_helpers import grade_for_mode
        plan = make_plan()
        SchemePlan.objects.filter(pk=plan.pk).update(publicly_listed=True)
        plan.refresh_from_db()
        grade = grade_for_mode(plan, "GOLD", code="GOLD_22K_916")
        request = submit_scheme_enrolment_request(customer=self.customer, plan=plan, metal_grade=grade,
            requested_contribution_amount=Decimal("500"), requested_months=12, customer_message="Keep",
            actor=self.customer.user).enrolment_request
        config = self.offer(required_values(accumulation="EXACT_METAL"))["plan"].configuration
        executor = MigrationExecutor(connection)
        leaves = executor.loader.graph.leaf_nodes()
        target = [("schemes", "0044_inr_api_capture_evidence")]
        executor.migrate(target)
        Historical = executor.loader.project_state(target).apps.get_model("schemes", "SchemeEnrolmentRequest")
        def restore():
            Historical.objects.filter(pk=request.pk).update(configuration_snapshot=None)
            MigrationExecutor(connection).migrate(leaves)
        self.addCleanup(restore)
        Historical.objects.filter(pk=request.pk).update(configuration_snapshot_id=config.pk)
        with self.assertRaisesMessage(RuntimeError, "Unversioned independent requests require review"):
            MigrationExecutor(connection).migrate(leaves)
        self.assertEqual(Historical.objects.get(pk=request.pk).requested_months, 12)

    def test_concurrent_conversion_creates_one_account_and_audit(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        request = self.submit(self.offer())
        barrier = Barrier(2)
        def convert():
            close_old_connections()
            try:
                barrier.wait(timeout=20)
                account, created = enroll_customer_from_request(enrolment_request=request, actor=self.owner,
                    current_terms_confirmed=True, start_date=date(2026, 1, 30), agreed_months=None, reason="Reviewed")
                return account.pk, created
            finally:
                connections.close_all()
        with future_readiness_only(), ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: convert(), range(2)))
        self.assertEqual(results[0][0], results[1][0])
        self.assertEqual(sum(created for _, created in results), 1)
        self.assertEqual(SchemeAccount.objects.count(), 1)
        self.assertEqual(AuditEvent.objects.filter(action="ENROLMENT_REQUEST_ENROLLED").count(), 1)
