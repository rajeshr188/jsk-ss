"""Synthetic configured agreements exercise future contract rules without opening drafts."""
import uuid
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.applications import offer_snapshot, offer_form_digest
from schemes.eligibility import calculate_eligibility_date
from schemes.forms import SchemeEnrolmentRequestForm
from schemes.models import Contribution, SchemeAccount, SchemePlan
from schemes.plan_configuration import (
    agreement_snapshot_values, create_configuration_version, create_configured_plan_draft,
)
from schemes.services import (
    _normalize_requested_contribution, enroll_customer, initiate_contribution,
    initiate_razorpay_contribution, preview_in_store_cash_contribution, publish_scheme_rate,
    record_in_store_cash_contribution, validate_contribution_amount, validate_redemption_amount,
)
from schemes.tests.grade_helpers import grade_for_mode
from schemes.tests.test_audit_exceptions import make_owner, make_customer, make_plan
from schemes.tests.test_razorpay import FakeRazorpayGateway


@override_settings(DEBUG=False, IN_STORE_CASH_CONTRIBUTIONS_ENABLED=True, PAYMENT_INITIATION_KILL_SWITCH=False)
class ConfiguredAgreementTests(TestCase):
    def setUp(self):
        self.owner = make_owner()
        self.customer = make_customer()
        self.legacy = make_plan()
        self.grade = grade_for_mode(self.legacy, "GOLD")
        self.values = {"name": "Customer fixed", "amount_policy": "CUSTOMER_FIXED",
                       "minimum_amount": Decimal("500"), "maximum_amount": Decimal("5000"),
                       "amount_step": Decimal("100"), "frequency_rule": "FLEXIBLE"}
        self.configuration = create_configuration_version(values=self.values, actor=self.owner, reason="Synthetic fixture")
        self.plan = create_configured_plan_draft(configuration_id=self.configuration.pk, name="Prepared fixed plan",
            code="PREPARED", metal_grades=[self.grade], actor=self.owner, reason="Test fixture")
        self.rate = publish_scheme_rate(metal_grade=self.grade, rate_per_gram=Decimal("10000"),
                                       published_by=self.owner, notes="Synthetic rate")

    def account(self, amount=Decimal("1000"), plan=None, customer=None):
        # Deliberate test-only model fixture. Real enrolment remains blocked; no gate is patched.
        plan = plan or self.plan
        start = timezone.localdate()
        account = SchemeAccount(scheme_number=f"SYN-{uuid.uuid4().hex[:12]}", customer=customer or self.customer,
            plan=plan, plan_revision=plan.revisions.first(), plan_name_snapshot=plan.name, plan_code_snapshot=plan.code,
            start_date=start, agreed_months=12, eligible_from=calculate_eligibility_date(start_date=start, agreed_months=12),
            savings_mode="GOLD", metal_grade=self.grade,
            **agreement_snapshot_values(plan=plan, selected_amount=amount))
        account.full_clean()
        account.save()
        return account

    def test_two_customers_choose_different_fixed_amounts_under_one_configuration(self):
        first = self.account(Decimal("1000"))
        second = self.account(Decimal("2000"), customer=make_customer("second-config@example.com"))
        self.assertEqual(first.configuration_snapshot_id, second.configuration_snapshot_id)
        self.assertEqual(first.fixed_amount_snapshot, Decimal("1000"))
        self.assertEqual(second.fixed_amount_snapshot, Decimal("2000"))
        for account, correct, wrong in [(first, "1000", "2000"), (second, "2000", "1000")]:
            self.assertEqual(validate_contribution_amount(account, Decimal(correct)), Decimal(correct))
            with self.assertRaises(ValidationError):
                validate_contribution_amount(account, Decimal(wrong))

    def test_missing_selection_bounds_precision_and_increment_rejected(self):
        for amount in [None, Decimal("400"), Decimal("5100"), Decimal("550"), Decimal("500.001"), 500.0, Decimal("NaN")]:
            with self.subTest(amount=amount), self.assertRaises(ValidationError):
                agreement_snapshot_values(plan=self.plan, selected_amount=amount)
        self.assertFalse(SchemeAccount.objects.exists())

    def test_legacy_preference_does_not_become_fixed_and_offer_payload_unchanged(self):
        snapshots = agreement_snapshot_values(plan=self.legacy, selected_amount=Decimal("1000"))
        self.assertIsNone(snapshots["fixed_amount_snapshot"])
        self.assertEqual(snapshots["amount_rule_snapshot"], "VARIABLE")
        self.assertIsNone(snapshots["configuration_snapshot_id"])
        self.assertNotIn("configuration", offer_snapshot(self.legacy, self.grade))

    def test_confirmation_evidence_and_digest_pin_configuration_version(self):
        first = offer_snapshot(self.plan, self.grade)
        digest = offer_form_digest(self.plan)
        next_version = create_configuration_version(values=self.values, previous_id=self.configuration.pk,
            actor=self.owner, reason="Another version")
        self.plan.configuration = next_version  # In-memory comparison only; no publication/update.
        self.assertNotEqual(first, offer_snapshot(self.plan, self.grade))
        self.assertNotEqual(digest, offer_form_digest(self.plan))
        self.assertEqual(first["configuration"]["amount_policy"], "CUSTOMER_FIXED")

    def test_all_entry_channels_reject_wrong_amount_before_order_or_allocation(self):
        account = self.account()
        gateway = FakeRazorpayGateway()
        calls = [
            lambda: initiate_contribution(scheme_account=account, amount=Decimal("1100"), payment_gateway="razorpay", gateway_mode="test"),
            lambda: initiate_razorpay_contribution(scheme_account=account, amount=Decimal("1100"), gateway=gateway),
            lambda: preview_in_store_cash_contribution(scheme_account=account, amount=Decimal("1100")),
            lambda: record_in_store_cash_contribution(scheme_account=account, amount=Decimal("1100"), expected_scheme_rate_id=self.rate.pk,
                received_by=self.owner, idempotency_key=uuid.uuid4(), audit_reason="Fixture"),
        ]
        for call in calls:
            with self.subTest(call=call), self.assertRaises(ValidationError):
                call()
        self.assertFalse(Contribution.objects.exists())
        self.assertEqual(gateway.order_calls, 0)

    def test_matching_online_and_cash_amounts_use_same_recorded_contract(self):
        online = self.account()
        cash = self.account(Decimal("2000"))
        contribution = initiate_razorpay_contribution(scheme_account=online, amount=Decimal("1000"), gateway=FakeRazorpayGateway())
        self.assertEqual(contribution.amount, online.fixed_amount_snapshot)
        preview = preview_in_store_cash_contribution(scheme_account=cash, amount=Decimal("2000"))
        record_in_store_cash_contribution(scheme_account=cash, amount=Decimal("2000"), expected_scheme_rate_id=preview.scheme_rate.pk,
            received_by=self.owner, idempotency_key=uuid.uuid4(), audit_reason="Synthetic receipt")
        # Service returns its normal result; inspect persisted financial evidence.
        paid = Contribution.objects.get(scheme_account=cash)
        self.assertEqual(paid.amount, cash.fixed_amount_snapshot)
        self.assertEqual(paid.status, "PAID")
        self.assertEqual(paid.metal_allocation.quantity, Decimal("0.200000"))

    def test_variable_increment_and_fixed_plan_are_distinct(self):
        configuration = create_configuration_version(values={**self.values, "amount_policy": "VARIABLE"},
            actor=self.owner, reason="Variable fixture")
        plan = create_configured_plan_draft(configuration_id=configuration.pk, name="Variable", code="VARIABLE-CFG",
            metal_grades=[self.grade], actor=self.owner, reason="Fixture")
        account = self.account(Decimal("700"), plan=plan)
        self.assertIsNone(account.fixed_amount_snapshot)
        self.assertEqual(account.contribution_step_snapshot, Decimal("100"))
        self.assertEqual(validate_contribution_amount(account, Decimal("900")), Decimal("900"))
        with self.assertRaises(ValidationError):
            validate_contribution_amount(account, Decimal("950"))
        config = create_configuration_version(values={**self.values, "amount_policy": "PLAN_FIXED", "fixed_amount": Decimal("500"),
            "maximum_amount": Decimal("500"), "amount_step": None}, actor=self.owner, reason="Fixed fixture")
        fixed_plan = create_configured_plan_draft(configuration_id=config.pk, name="Fixed", code="FIXED-CFG", metal_grades=[self.grade], actor=self.owner, reason="Fixture")
        self.assertEqual(agreement_snapshot_values(plan=fixed_plan)["fixed_amount_snapshot"], Decimal("500"))

    def test_contract_snapshots_cannot_be_edited_or_detached(self):
        account = self.account()
        for field, value in [("fixed_amount_snapshot", Decimal("2000")), ("configuration_snapshot_id", None),
                             ("contribution_step_snapshot", Decimal("100")), ("agreed_months", 24)]:
            account.refresh_from_db()
            setattr(account, field, value)
            with self.subTest(field=field), self.assertRaisesMessage(ValidationError, "immutable"):
                account.save(update_fields=[field])
        account.refresh_from_db()
        account.status = "REDEMPTION_ELIGIBLE"
        account.save(update_fields=["status"])

    def test_corrupted_snapshot_fails_integrity_and_payment_validation(self):
        account = self.account()
        out = StringIO()
        call_command("check_plan_agreements", stdout=out)
        self.assertIn("status=ok", out.getvalue())
        # Simulates privileged data corruption that bypasses model immutability.
        SchemeAccount.objects.filter(pk=account.pk).update(frequency_rule_snapshot="ONCE_PER_MONTH")
        account.refresh_from_db()
        with self.assertRaises(ValidationError):
            validate_contribution_amount(account, Decimal("1000"))
        with self.assertRaises(CommandError):
            call_command("check_plan_agreements", stdout=StringIO())

    def test_db_rejects_invalid_configured_shape(self):
        account = self.account()
        for values in [{"fixed_amount_snapshot": None}, {"minimum_amount_snapshot": Decimal("500")},
                       {"cash_bonus_percentage_snapshot": Decimal("5")}, {"plan_revision_id": None}]:
            with self.subTest(values=values), self.assertRaises(IntegrityError), transaction.atomic():
                SchemeAccount.objects.filter(pk=account.pk).update(**values)

    def test_new_version_and_plan_metadata_do_not_change_existing_individual_terms(self):
        account = self.account()
        create_configuration_version(values={**self.values, "minimum_amount": Decimal("2000")},
            actor=self.owner, reason="Future terms", previous_id=self.configuration.pk)
        SchemePlan.objects.filter(pk=self.plan.pk).update(name="Future name")
        account.refresh_from_db()
        self.assertEqual(validate_contribution_amount(account, Decimal("1000")), Decimal("1000"))
        self.assertEqual(account.display_plan_name, "Prepared fixed plan")

    def test_actual_enrolment_and_redemption_still_fail_closed(self):
        with self.assertRaisesMessage(ValidationError, "preparation-only"):
            enroll_customer(customer=self.customer, plan=self.plan, metal_grade=self.grade, performed_by=self.owner,
                selected_contribution_amount=Decimal("1000"), selected_amount_confirmed=True, expected_configuration_id=self.configuration.pk)
        self.assertFalse(SchemeAccount.objects.exists())
        account = self.account()
        with self.assertRaisesMessage(ValidationError, "Full-only settlement"):
            validate_redemption_amount(account, Decimal("0.001"))
        with self.assertRaises(CommandError):
            call_command("check_plan_configurations", stdout=StringIO())

    def test_calendar_configuration_also_excludes_legacy_settlement_ui(self):
        from schemes.selectors import get_customer_payment_availability, get_owner_settlement_review_count
        account = self.account()
        self.client.force_login(self.owner)
        url = reverse("schemes:redemption_create", args=[account.scheme_number])
        with patch("django.utils.timezone.localdate", return_value=account.eligible_from):
            self.assertEqual(get_owner_settlement_review_count(), 0)
            self.assertEqual(account.effective_status_label, "Calendar date reached — showroom settlement review")
            with patch("schemes.payments.payment_gateway_is_configured", return_value=True):
                availability = get_customer_payment_availability(account)
                self.assertEqual(availability.code, "CONFIGURED_SETTLEMENT_UNAVAILABLE")
                self.assertFalse(availability.allowed)
            # Even a positive entitlement must not expose the legacy partial form.
            with patch("schemes.views.get_outstanding_entitlement", return_value=Decimal("1")):
                self.assertEqual(self.client.get(url).status_code, 404)
                self.assertEqual(self.client.post(url).status_code, 404)
        self.assertFalse(account.redemptions.exists())

    def test_intake_form_explains_fixed_selection_and_validates_step(self):
        form = SchemeEnrolmentRequestForm(plan=self.plan)
        self.assertEqual(form.fields["requested_contribution_amount"].label, "Your fixed contribution amount")
        data = {"metal_grade": self.grade.pk, "requested_contribution_amount": "550", "requested_months": 12,
                "disclosure_accepted": True}
        self.assertFalse(SchemeEnrolmentRequestForm(data, plan=self.plan).is_valid())
        data["requested_contribution_amount"] = "1000"
        self.assertTrue(SchemeEnrolmentRequestForm(data, plan=self.plan).is_valid())
        with self.assertRaises(ValidationError):
            _normalize_requested_contribution(plan=self.plan, amount=Decimal("550"))

    def test_locked_payment_entry_reloads_the_stored_amount(self):
        account = self.account()
        account.fixed_amount_snapshot = account.minimum_amount_snapshot = account.maximum_amount_snapshot = Decimal("2000")
        gateway = FakeRazorpayGateway()
        with self.assertRaises(ValidationError):
            initiate_razorpay_contribution(scheme_account=account, amount=Decimal("2000"), gateway=gateway)
        with self.assertRaises(ValidationError):
            record_in_store_cash_contribution(scheme_account=account, amount=Decimal("2000"), expected_scheme_rate_id=self.rate.pk,
                received_by=self.owner, idempotency_key=uuid.uuid4(), audit_reason="Synthetic attempt")
        self.assertEqual(gateway.order_calls, 0)
        self.assertFalse(Contribution.objects.exists())

    def test_no_float_or_nonfinite_amounts_enter_payment_validation(self):
        account = self.account()
        for value in [1000.0, True, Decimal("NaN"), Decimal("Infinity"), Decimal("1000.001")]:
            with self.subTest(value=value), self.assertRaises(ValidationError):
                validate_contribution_amount(account, value)
