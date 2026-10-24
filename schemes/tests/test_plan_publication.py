"""Disabled-first P4 publication and real enrolment paths on a disposable database."""
from datetime import date
from decimal import Decimal
from io import StringIO
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError, close_old_connections, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.template.loader import render_to_string
from django.urls import reverse

from schemes.forms import EnrolmentForm
from schemes.models import AuditEvent, Contribution, MetalAllocation, SchemeAccount, SchemePlan
from schemes.plan_configuration import create_configuration_version, create_configured_plan_draft, validate_agreement_configuration
from schemes.plan_governance import plan_edit_digest, save_scheme_plan
from schemes.plan_publication import set_configured_plan_publication
from schemes.selectors import get_public_scheme_plans, get_metal_balance
from schemes.services import enroll_customer, enroll_customer_from_request, submit_scheme_enrolment_request
from schemes.tests.test_audit_exceptions import make_owner
from schemes.tests.test_instalment_schedules import fixture
from schemes.tests.test_configured_settlements import SettlementFixture


class PublicationFixture:
    def setUp(self):
        self.owner = make_owner()
        self.customer, self.grade, self.config, self.plan = fixture(self.owner)

    def publish(self, **changes):
        self.plan.refresh_from_db()
        values = dict(plan_id=self.plan.pk, actor=self.owner, reason="Reviewed full-only offer",
            expected_digest=plan_edit_digest(self.plan), publish=True, confirmed=True)
        values.update(changes)
        result = set_configured_plan_publication(**values)
        self.plan.refresh_from_db()
        return result

    def enroll(self, **changes):
        values = dict(customer=self.customer, plan=self.plan, metal_grade=self.grade,
            start_date=date(2026, 1, 31), agreed_months=12, selected_contribution_amount=Decimal("1000"),
            selected_amount_confirmed=True, expected_configuration_id=self.config.pk,
            expected_plan_digest=plan_edit_digest(self.plan), performed_by=self.owner)
        values.update(changes)
        return enroll_customer(**values)


@override_settings(CONFIGURED_PLANS_ENABLED=True, CUSTOMER_ENROLMENT_REQUESTS_ENABLED=True)
class PlanPublicationTests(PublicationFixture, TestCase):
    def test_release_off_blocks_publication_even_debug_and_direct_enrolment(self):
        with self.settings(CONFIGURED_PLANS_ENABLED=False, DEBUG=True):
            with self.assertRaisesMessage(ValidationError, "release gate"):
                self.publish()
            with self.assertRaisesMessage(ValidationError, "preparation-only"):
                self.enroll()
        self.assertFalse(SchemeAccount.objects.exists())
        self.assertEqual(self.plan.revisions.count(), 1)

    def test_publish_records_revision_audit_and_atomic_monthly_enrolment(self):
        self.publish()
        self.assertTrue(self.plan.active and self.plan.publicly_listed)
        self.assertEqual(self.plan.publication_revision.number, 2)
        self.assertEqual(self.plan.publication_revision.terms["configuration"]["id"], self.config.pk)
        self.assertIn(self.plan, get_public_scheme_plans())
        self.assertEqual(AuditEvent.objects.filter(action="SCHEME_CHANGE", scheme_plan=self.plan).count(), 2)
        account = self.enroll()
        self.assertEqual(account.plan_revision_id, self.plan.publication_revision_id)
        self.assertEqual(account.fixed_amount_snapshot, Decimal("1000"))
        self.assertEqual(account.instalment_periods.count(), 15)
        self.assertEqual(account.instalment_periods.get(number=2).starts_on, date(2026, 2, 28))
        self.assertFalse(Contribution.objects.exists())
        self.assertFalse(MetalAllocation.objects.exists())
        output = StringIO()
        call_command("check_plan_configurations", stdout=output)
        self.assertIn("status=ok", output.getvalue())

    def test_published_identity_or_grade_edit_requires_withdrawal(self):
        self.publish()
        with self.assertRaisesMessage(ValidationError, "Withdraw"):
            save_scheme_plan(plan_id=self.plan.pk, expected_digest=plan_edit_digest(self.plan),
                values={"name": "New identity"}, metal_grades=[self.grade], actor=self.owner, reason="Edit")

    def test_withdraw_edit_republish_preserves_agreement_snapshot(self):
        self.publish()
        account = self.enroll()
        before = SchemeAccount.objects.values().get(pk=account.pk)
        revision = account.plan_revision
        self.publish(publish=False)
        self.assertNotIn(self.plan, get_public_scheme_plans())
        with self.assertRaises(ValidationError):
            self.enroll()
        save_scheme_plan(plan_id=self.plan.pk, expected_digest=plan_edit_digest(self.plan),
            values={"name": "New advertised identity"}, metal_grades=[self.grade], actor=self.owner, reason="New offers only")
        self.publish()
        self.assertNotEqual(self.plan.publication_revision_id, revision.pk)
        account.refresh_from_db()
        validate_agreement_configuration(account)
        self.assertEqual(SchemeAccount.objects.values().get(pk=account.pk), before)
        revision.refresh_from_db()
        self.assertNotEqual(revision.terms["name"], self.plan.name)

    def test_disabled_release_hides_offers_but_allows_withdrawal(self):
        self.publish()
        with self.settings(CONFIGURED_PLANS_ENABLED=False):
            self.assertNotIn(self.plan, get_public_scheme_plans())
            self.assertNotIn(self.plan, EnrolmentForm().fields["plan"].queryset)
            with self.assertRaises(ValidationError):
                self.enroll()
            self.publish(publish=False)
        self.assertFalse(self.plan.active)

    def test_stale_revision_role_confirmation_and_reason_rejected(self):
        for changes in ({"expected_digest": "stale"}, {"actor": self.customer.user},
                        {"confirmed": False}, {"reason": " "}):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                self.publish(**changes)
        self.assertEqual(self.plan.revisions.count(), 1)

    def test_db_requires_publication_proof_and_service_checks_ownership(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            SchemePlan.objects.filter(pk=self.plan.pk).update(active=True)
        # Even a foreign revision cannot satisfy service-level publication integrity.
        other = create_configured_plan_draft(configuration_id=self.config.pk, name="Other", code="OTHER",
            metal_grades=[self.grade], actor=self.owner, reason="Other draft")
        SchemePlan.objects.filter(pk=self.plan.pk).update(active=True, publicly_listed=True,
            publication_revision=other.revisions.first())
        self.plan.refresh_from_db()
        with self.assertRaises(ValidationError):
            self.enroll()

    def test_audit_and_schedule_failures_roll_back_all_related_records(self):
        with patch("schemes.services.record_scheme_plan_change", side_effect=RuntimeError("audit unavailable")):
            with self.assertRaises(RuntimeError):
                self.publish()
        self.plan.refresh_from_db()
        self.assertFalse(self.plan.active)
        self.assertEqual(self.plan.revisions.count(), 1)
        self.publish()
        with patch("schemes.instalments.prepare_instalment_periods", side_effect=RuntimeError("schedule unavailable")):
            with self.assertRaises(RuntimeError):
                self.enroll()
        self.assertFalse(SchemeAccount.objects.exists())

    def test_unconfirmed_stale_and_invalid_individual_amount_rejected(self):
        self.publish()
        for changes in ({"selected_amount_confirmed": False}, {"expected_configuration_id": None},
                        {"expected_plan_digest": "stale"}, {"selected_contribution_amount": Decimal("550")},
                        {"performed_by": self.customer.user}):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                self.enroll(**changes)
        self.assertFalse(SchemeAccount.objects.exists())

    def test_request_remains_nonfinancial_until_explicit_owner_conversion(self):
        self.publish()
        submit_scheme_enrolment_request(customer=self.customer, plan=self.plan, metal_grade=self.grade,
            requested_contribution_amount=Decimal("1000"), requested_months=12, customer_message="Join",
            actor=self.customer.user)
        self.assertFalse(SchemeAccount.objects.exists())
        from schemes.models import SchemeEnrolmentRequest
        request = SchemeEnrolmentRequest.objects.get()
        account, created = enroll_customer_from_request(enrolment_request=request, actor=self.owner,
            current_terms_confirmed=True, start_date=date(2026, 1, 31), agreed_months=12, reason="Customer confirmed")
        self.assertTrue(created)
        self.assertEqual(account.instalment_periods.count(), 15)
        self.assertEqual(enroll_customer_from_request(enrolment_request=request, actor=self.owner,
            current_terms_confirmed=True, start_date=date(2026, 1, 31), agreed_months=12, reason="Replay"), (account, False))

    def test_owner_ui_and_csrf_and_monthly_customer_wording(self):
        url = reverse("schemes:configured_plan_publication", args=[self.plan.pk])
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.customer.user)
        self.assertEqual(self.client.post(url, {}).status_code, 403)
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        self.assertEqual(client.post(url, {}).status_code, 403)
        response = client.get(url)
        self.assertContains(response, "No bonus or discount is included")
        self.assertContains(response, "both the agreed duration")
        self.assertNotContains(response, "Eligibility is date-based")
        response = client.post(url, {"expected_digest": plan_edit_digest(self.plan), "reason": "Reviewed offer",
            "confirmed": "on"}, HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value)
        self.assertEqual(response.status_code, 302)
        self.plan.refresh_from_db()
        markup = render_to_string("pages/includes/plan_offer.html", {"plan": self.plan})
        self.assertIn("anniversary", markup)
        self.assertNotIn("Flexible contribution timing", markup)

    def test_owner_enrolment_form_binds_publication_revision(self):
        self.publish()
        token = EnrolmentForm()["configuration_token"].value()
        data = dict(plan=self.plan.pk, metal_grade=self.grade.pk, start_date="2026-01-31", agreed_months=12,
            selected_contribution_amount="1000", selected_amount_confirmed=True, configuration_token=token,
            audit_reason="Customer confirms exact amount")
        self.assertTrue(EnrolmentForm(data).is_valid())
        self.publish(publish=False)
        self.publish()
        form = EnrolmentForm(data)
        self.assertFalse(form.is_valid())
        self.assertIn("changed or expired", str(form.errors))

    def test_request_conversion_form_uses_confirmed_amount_not_owner_substitution(self):
        from schemes.forms import EnrolmentRequestConversionForm
        self.publish()
        request = submit_scheme_enrolment_request(customer=self.customer, plan=self.plan, metal_grade=self.grade,
            requested_contribution_amount=Decimal("1000"), requested_months=12, customer_message="Join",
            actor=self.customer.user).enrolment_request
        initial = EnrolmentRequestConversionForm(enrolment_request=request)
        form = EnrolmentRequestConversionForm(dict(start_date="2026-01-31", agreed_months=12,
            current_terms_confirmed=True, selected_amount_confirmed=True, selected_contribution_amount="2000",
            configuration_token=initial["configuration_token"].value(), audit_reason="Confirmed"), enrolment_request=request)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["selected_contribution_amount"], Decimal("1000"))

    def test_calendar_configuration_has_no_invented_schedule(self):
        config = create_configuration_version(values={"name": "Calendar", "amount_policy": "VARIABLE",
            "minimum_amount": Decimal("100"), "frequency_rule": "FLEXIBLE"}, actor=self.owner, reason="Calendar")
        self.plan = create_configured_plan_draft(configuration_id=config.pk, name="Calendar", code="CALENDAR",
            metal_grades=[self.grade], actor=self.owner, reason="Calendar offer")
        self.config = config
        self.publish()
        account = self.enroll()
        self.assertEqual(account.amount_rule_snapshot, "VARIABLE")
        self.assertFalse(account.instalment_periods.exists())


@override_settings(CONFIGURED_PLANS_ENABLED=True, IN_STORE_CASH_CONTRIBUTIONS_ENABLED=True,
    PAYMENT_GATEWAY="razorpay", RAZORPAY_MODE="live", RAZORPAY_KEY_ID="rzp_live_fixture", RAZORPAY_KEY_SECRET="fixture")
class PublishedOfferSettlementTests(SettlementFixture, TestCase):
    def setUp(self):
        # Reuse fake provider/clock/rate helpers but replace the synthetic account
        # factory with the actual publication and enrolment services.
        with patch("schemes.tests.test_instalment_payment_integration.synthetic_account", side_effect=self.published_account):
            super().setUp()

    def published_account(self, customer, grade, plan):
        plan, _ = set_configured_plan_publication(plan_id=plan.pk, publish=True, actor=self.owner,
            reason="Reviewed local offer", expected_digest=plan_edit_digest(plan), confirmed=True)
        return enroll_customer(customer=customer, plan=plan, metal_grade=grade, start_date=date(2026, 1, 31),
            agreed_months=12, selected_contribution_amount=Decimal("1000"), selected_amount_confirmed=True,
            expected_configuration_id=plan.configuration_id, expected_plan_digest=plan_edit_digest(plan), performed_by=self.owner)

    def test_published_enrolled_cash_agreement_can_close_even_with_release_off(self):
        self.assertTrue(self.account.plan.publication_revision_id)
        with self.settings(CONFIGURED_PLANS_ENABLED=False):
            self.cash()
            request = self.accepted()
            redemption = self.settle(request)
        self.assertEqual(redemption.gold_quantity, Decimal("0.100000"))
        self.account.refresh_from_db()
        self.assertEqual(self.account.status, "REDEEMED")
        self.assertEqual(get_metal_balance(self.account), 0)

    def test_published_online_agreement_waits_for_capture_before_full_settlement(self):
        self.assertTrue(self.account.plan.publication_revision_id)
        payment = self.online()
        request = self.accepted()
        with self.assertRaises(ValidationError):
            self.values(request)
        self.webhook(payment)
        self.assertEqual(self.settle(request).gold_quantity, Decimal("0.100000"))


from accounts.test_plan_applications import APPLICATION_SETTINGS, ApplicationFixtures
from schemes.tests.test_instalment_schedules import monthly_values


@override_settings(**APPLICATION_SETTINGS, CONFIGURED_PLANS_ENABLED=True)
class PublishedPlanApplicationTests(ApplicationFixtures, TestCase):
    def setUp(self):
        super().setUp()
        config = create_configuration_version(values=monthly_values(), actor=self.owner, reason="Supported policy")
        plan = create_configured_plan_draft(configuration_id=config.pk, name="Public monthly", code="PUBLIC-MONTHLY",
            metal_grades=[self.grade], actor=self.owner, reason="New offer")
        self.plan, _ = set_configured_plan_publication(plan_id=plan.pk, publish=True, actor=self.owner,
            expected_digest=plan_edit_digest(plan), confirmed=True, reason="Reviewed public offer")

    def test_identity_confirmation_approval_produces_fixed_agreement_and_schedule(self):
        application = self.ready()
        self.assertFalse(SchemeAccount.objects.exists())
        account, created = self.approve(application)
        self.assertTrue(created)
        self.assertEqual(account.fixed_amount_snapshot, Decimal("1000"))
        self.assertEqual(account.instalment_periods.count(), 17)  # 14 agreed + 3 ordinary extensions.
        self.assertEqual(account.plan_revision_id, self.plan.publication_revision_id)
        self.assertFalse(Contribution.objects.exists())

    def test_republication_requires_new_customer_offer_confirmation(self):
        application = self.ready()
        for publish in (False, True):
            self.plan, _ = set_configured_plan_publication(plan_id=self.plan.pk, publish=publish, actor=self.owner,
                expected_digest=plan_edit_digest(self.plan), confirmed=True, reason="Reviewed re-publication")
        with self.assertRaisesMessage(ValidationError, "confirmation"):
            self.approve(application)
        self.assertFalse(SchemeAccount.objects.exists())


@override_settings(CONFIGURED_PLANS_ENABLED=True)
class PublicationConcurrencyTests(PublicationFixture, TransactionTestCase):
    def setUp(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().setUp()

    def test_competing_publications_append_one_publication_revision(self):
        digest = plan_edit_digest(self.plan)
        barrier = Barrier(2)

        def publish():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                try:
                    return set_configured_plan_publication(plan_id=self.plan.pk, publish=True,
                        actor=self.owner, reason="Concurrent decision", expected_digest=digest, confirmed=True)[1]
                except ValidationError:
                    return "stale"
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertCountEqual(list(pool.map(lambda _: publish(), range(2))), [True, "stale"])
        self.assertEqual(self.plan.revisions.count(), 2)

    def test_enrolment_and_withdrawal_serialize_without_partial_schedule(self):
        self.publish()
        digest = plan_edit_digest(self.plan)
        barrier = Barrier(2)

        def operation(kind):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                try:
                    if kind == "enrol":
                        return self.enroll(expected_plan_digest=digest).pk
                    set_configured_plan_publication(plan_id=self.plan.pk, publish=False, actor=self.owner,
                        reason="Withdraw", expected_digest=digest, confirmed=True)
                    return "withdrawn"
                except ValidationError:
                    return "blocked"
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(operation, ["enrol", "withdraw"]))
        self.assertEqual(results[1], "withdrawn")
        self.plan.refresh_from_db()
        self.assertFalse(self.plan.active)
        for account in SchemeAccount.objects.all():
            self.assertEqual(account.instalment_periods.count(), 15)
            validate_agreement_configuration(account)
        self.assertEqual(SchemeAccount.objects.count(), 0 if results[0] == "blocked" else 1)
