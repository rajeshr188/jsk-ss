"""Archive/retire future offers without erasing history or changing agreements."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from importlib import import_module
from types import SimpleNamespace
from unittest.mock import patch

from django.apps import apps
from django.core.exceptions import ValidationError
from django.db import IntegrityError, close_old_connections, connection, transaction
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse

from schemes.catalogue_lifecycle import close_catalogue_item
from schemes.catalogue_selectors import catalogue_closure_preview
from schemes.models import (Contribution, MetalAllocation, InrPrincipalReceipt, PlanCatalogueClosure,
    SchemeAccount, SchemePlan, SchemePlanConfiguration, SchemePlanRevision, AuditEvent)
from schemes.plan_configuration import create_configuration_version, create_configured_plan_draft
from schemes.plan_governance import save_scheme_plan, plan_edit_digest
from schemes.plan_publication import set_configured_plan_publication, require_configured_offer
from schemes.selectors import get_owner_plan_configuration, get_plan_configurations, get_enrollable_scheme_plans
from schemes.services import enroll_customer, enroll_customer_from_request, submit_scheme_enrolment_request, validate_contribution_allowed, enrolment_request_offer_is_current
from schemes.tests.test_audit_exceptions import make_owner, make_customer, make_plan
from schemes.tests.test_independent_policy_fields import independent_values
from schemes.tests.grade_helpers import grade_for_mode


class CatalogueFixture:
    def setUp(self):
        self.owner = make_owner()
        self.configuration = create_configuration_version(values=independent_values(accumulation="INR_PURCHASE_CREDIT"),
            actor=self.owner, reason="Prepare fixture")
        self.plan = create_configured_plan_draft(configuration_id=self.configuration.pk, name="Unused draft",
            code="ARCHIVE-DRAFT", metal_grades=[], actor=self.owner, reason="Prepare draft")

    def close(self, plan=None, configuration=None, **changes):
        if plan is None and configuration is None:
            plan = self.plan
        preview = catalogue_closure_preview(plan=plan, configuration=configuration)
        return close_catalogue_item(actor=self.owner, reason="Remove unused offer from catalogue", confirmed=True,
            plan_id=plan.pk if plan else None, configuration_id=configuration.pk if configuration else None,
            **({"expected_digest": preview["expected_digest"]} | changes))


@override_settings(CONFIGURED_PLANS_ENABLED=False)
class CatalogueLifecycleTests(CatalogueFixture, TestCase):
    def test_archive_draft_retains_policy_revisions_and_hides_default_list(self):
        terms = list(self.plan.revisions.values())
        record, created = self.close()
        self.assertTrue(created)
        self.assertEqual(record.action, "ARCHIVE_DRAFT")
        self.assertEqual(list(self.plan.revisions.values()), terms)
        self.assertFalse(get_owner_plan_configuration().filter(pk=self.plan.pk).exists())
        self.assertTrue(get_owner_plan_configuration(closed=True).filter(pk=self.plan.pk).exists())
        self.assertEqual(SchemePlan.objects.count(), 1)
        for model in (SchemeAccount, Contribution, MetalAllocation, InrPrincipalReceipt):
            self.assertFalse(model.objects.exists())
        self.assertEqual(self.close()[0].pk, record.pk)
        self.assertEqual(PlanCatalogueClosure.objects.count(), 1)

    def test_configuration_archive_requires_linked_plans_closed_and_preserves_terms(self):
        with self.assertRaisesMessage(ValidationError, "plans using this version"):
            self.close(configuration=self.configuration)
        before = SchemePlanConfiguration.objects.values().get(pk=self.configuration.pk)
        self.close()
        self.close(configuration=self.configuration)
        self.assertEqual(before, SchemePlanConfiguration.objects.values().get(pk=self.configuration.pk))
        self.assertFalse(get_plan_configurations().exists())
        self.assertTrue(get_plan_configurations(closed=True).exists())
        with self.assertRaisesMessage(ValidationError, "archived or retired"):
            create_configured_plan_draft(configuration_id=self.configuration.pk, name="Bypass", code="BYPASS",
                metal_grades=[], actor=self.owner, reason="Try stale selection")
        with self.assertRaisesMessage(ValidationError, "archived or retired"):
            create_configuration_version(values=independent_values(), previous_id=self.configuration.pk,
                actor=self.owner, reason="Try successor")

    def test_closed_plan_cannot_be_edited_or_republished_or_reenrolled(self):
        self.close()
        self.plan.refresh_from_db()
        with self.assertRaisesMessage(ValidationError, "archived or retired"):
            save_scheme_plan(plan_id=self.plan.pk, values={"name": "Reopen"}, metal_grades=[],
                actor=self.owner, reason="Try edit", expected_digest=plan_edit_digest(self.plan))
        with self.assertRaisesMessage(ValidationError, "archived or retired"):
            set_configured_plan_publication(plan_id=self.plan.pk, publish=True, actor=self.owner,
                reason="Try publish", confirmed=True, expected_digest=plan_edit_digest(self.plan))
        # Defence in depth against an out-of-service active flag change.
        SchemePlan.objects.filter(pk=self.plan.pk).update(active=True, publicly_listed=True,
            publication_revision=self.plan.revisions.first())
        self.plan.refresh_from_db()
        self.assertFalse(get_enrollable_scheme_plans().filter(pk=self.plan.pk).exists())
        with self.assertRaisesMessage(ValidationError, "archived or retired"):
            require_configured_offer(self.plan)

    @override_settings(CUSTOMER_ENROLMENT_REQUESTS_ENABLED=True)
    def test_retirement_preserves_agreement_and_pending_request_and_payment_rights(self):
        plan = make_plan()
        plan.publicly_listed = True
        plan.save()
        grade = grade_for_mode(plan, SchemeAccount.SavingsMode.GOLD)
        customer = make_customer()
        account = enroll_customer(customer=customer, plan=plan, metal_grade=grade,
            start_date=date(2026, 10, 1), performed_by=self.owner)
        request = submit_scheme_enrolment_request(customer=customer, plan=plan, metal_grade=grade,
            requested_contribution_amount=Decimal("500"), requested_months=12, customer_message="Fixture",
            actor=customer.user).enrolment_request
        before = SchemeAccount.objects.values().get(pk=account.pk)
        request_before = type(request).objects.values().get(pk=request.pk)
        payment = validate_contribution_allowed(account, Decimal("500"), date(2026, 10, 10))
        record, _ = self.close(plan=plan)
        self.assertEqual(record.action, "RETIRE_PLAN")
        self.assertEqual(before, SchemeAccount.objects.values().get(pk=account.pk))
        self.assertEqual(request_before, type(request).objects.values().get(pk=request.pk))
        self.assertFalse(enrolment_request_offer_is_current(request))
        with self.assertRaises(ValidationError):
            enroll_customer_from_request(enrolment_request=request, actor=self.owner, current_terms_confirmed=True,
                start_date=date(2026, 10, 28), agreed_months=12, reason="Try retired offer")
        self.assertEqual(request_before, type(request).objects.values().get(pk=request.pk))
        account.refresh_from_db()
        self.assertEqual(payment, validate_contribution_allowed(account, Decimal("500"), date(2026, 10, 10)))
        with self.assertRaisesMessage(ValidationError, "archived or retired"):
            enroll_customer(customer=customer, plan=plan, metal_grade=grade, performed_by=self.owner)
        with self.assertRaisesMessage(ValidationError, "archived or retired"):
            submit_scheme_enrolment_request(customer=customer, plan=plan, metal_grade=grade,
                requested_contribution_amount=Decimal("500"), requested_months=12,
                customer_message="Stale page", actor=customer.user)
        plan.refresh_from_db()
        self.assertFalse(plan.active or plan.publicly_listed)
        self.assertTrue(plan.revisions.filter(terms__active=True).exists())

    def test_previously_active_offer_is_retired_even_after_withdrawal(self):
        self.plan.revisions.update(terms={"active": True})  # Synthetic historical offer.
        self.assertEqual(self.close()[0].action, "RETIRE_PLAN")

    def test_stale_confirmation_and_changed_retry_do_not_mutate(self):
        preview = catalogue_closure_preview(plan=self.plan)
        SchemePlan.objects.filter(pk=self.plan.pk).update(name="Changed identity")
        with self.assertRaisesMessage(ValidationError, "Reload"):
            self.close(expected_digest=preview["expected_digest"])
        self.assertFalse(PlanCatalogueClosure.objects.exists())
        self.plan.refresh_from_db()
        record, _ = self.close()
        with self.assertRaisesMessage(ValidationError, "already"):
            close_catalogue_item(actor=self.owner, reason="Change recorded reason", confirmed=True,
                expected_digest="old", plan_id=self.plan.pk)
        with self.assertRaises(ValidationError):
            record.delete()
        with self.assertRaises(ValidationError):
            record.save()

    def test_audit_failure_rolls_back_retirement_and_revisions(self):
        plan = make_plan()
        before = SchemePlan.objects.values().get(pk=plan.pk)
        with patch("schemes.services.record_scheme_plan_change", side_effect=RuntimeError("Audit unavailable")):
            with self.assertRaises(RuntimeError):
                self.close(plan=plan)
        self.assertEqual(before, SchemePlan.objects.values().get(pk=plan.pk))
        self.assertFalse(plan.revisions.exists())
        self.assertFalse(PlanCatalogueClosure.objects.exists())

    def test_owner_confirmation_csrf_and_get_are_required(self):
        url = reverse("schemes:plan_catalogue_close", args=[self.plan.pk])
        self.assertEqual(self.client.get(url).status_code, 302)
        customer = make_customer()
        self.client.force_login(customer.user)
        self.assertEqual(self.client.post(url, {}).status_code, 403)
        self.client.force_login(self.owner)
        page = self.client.get(url)
        self.assertContains(page, "Archive draft")
        self.assertIn("no-store", page["Cache-Control"])
        self.assertFalse(PlanCatalogueClosure.objects.exists())
        self.assertEqual(self.client.put(url).status_code, 405)
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.owner)
        self.assertEqual(strict.post(url, {}).status_code, 403)
        data = {"expected_digest": page.context["preview"]["expected_digest"], "reason": "Unused"}
        self.assertEqual(self.client.post(url, data).status_code, 200)
        self.assertFalse(PlanCatalogueClosure.objects.exists())
        self.assertEqual(self.client.post(url, data | {"confirmed": True}).status_code, 302)
        self.assertContains(self.client.get(url), "Draft archived")

    def test_plan_rows_have_eight_cells_and_closed_history_filter(self):
        from html.parser import HTMLParser
        class Rows(HTMLParser):
            def __init__(self):
                super().__init__(); self.rows = []; self.count = 0
            def handle_starttag(self, tag, attrs):
                if tag == "tr": self.count = 0
                if tag in ("th", "td"): self.count += 1
            def handle_endtag(self, tag):
                if tag == "tr": self.rows.append(self.count)
        make_plan()
        self.client.force_login(self.owner)
        response = self.client.get(reverse("schemes:plan_list"))
        parsed = Rows(); parsed.feed(response.content.decode())
        self.assertEqual(parsed.rows, [8, 8, 8])
        self.assertContains(response, "INR jewellery purchase credit")
        self.close()
        self.assertNotContains(self.client.get(reverse("schemes:plan_list")), "ARCHIVE-DRAFT")
        self.assertContains(self.client.get(reverse("schemes:plan_list") + "?status=closed"), "ARCHIVE-DRAFT")

    def test_database_shape_unique_target_and_downgrade_guard(self):
        record, _ = self.close()
        for changes in ({"action": "ARCHIVE_CONFIGURATION"}, {"configuration_id": self.configuration.pk}, {"reason": ""}):
            with self.assertRaises(IntegrityError), transaction.atomic():
                PlanCatalogueClosure.objects.filter(pk=record.pk).update(**changes)
        with self.assertRaises(IntegrityError), transaction.atomic():
            PlanCatalogueClosure.objects.bulk_create([PlanCatalogueClosure(plan=self.plan, action="ARCHIVE_DRAFT",
                actor=self.owner, actor_label="Owner", reason="Duplicate")])
        guard = import_module("schemes.migrations.0056_plan_catalogue_closure").refuse_history_loss
        with self.assertRaisesMessage(RuntimeError, "Retained catalogue"):
            guard(apps, SimpleNamespace(connection=connection))


class CatalogueConcurrencyTests(CatalogueFixture, TransactionTestCase):
    def test_concurrent_confirmations_retain_one_record(self):
        values = dict(actor=self.owner, reason="Same confirmed review", confirmed=True, plan_id=self.plan.pk,
            expected_digest=catalogue_closure_preview(plan=self.plan)["expected_digest"])
        def close():
            close_old_connections()
            try:
                return close_catalogue_item(**values)[0].pk
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            first, second = list(pool.map(lambda _: close(), range(2)))
        self.assertEqual(first, second)
        self.assertEqual(PlanCatalogueClosure.objects.count(), 1)
