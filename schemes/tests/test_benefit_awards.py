"""Retained rights on synthetic contracts; no real operational gate is opened."""
import importlib
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import timedelta
from io import StringIO
from threading import Barrier
from unittest.mock import patch

from django.apps import apps
from django.core.exceptions import ValidationError
from django.core.management import call_command, CommandError
from django.db import connection, connections, IntegrityError, transaction
from django.test import TestCase, TransactionTestCase, override_settings
from django.test.utils import CaptureQueriesContext

from schemes.benefit_awards import preview_benefit_award, record_benefit_award
from schemes.benefit_award_selectors import get_benefit_award_status, validate_benefit_award
from schemes.inr_selectors import get_inr_principal_summary
from schemes.models import (SchemeBenefitAward, SchemeAccount, SchemePlan, Contribution,
    InrPrincipalReceipt, InStoreCashContributionReversal, MetalAllocation)
from schemes.services import reverse_in_store_cash_contribution
from schemes.tests import test_benefit_qualification as qualification
from schemes.tests.test_independent_instalment_reviews import IndependentReviewFixture, instant
from schemes.tests.test_independent_instalment_ledger import NOW


@contextmanager
def future_award_readiness():
    # Simulate only the still-unreleased policy gate, not evidence/roles/calculation.
    with patch("schemes.benefit_awards.require_operational_configuration"), patch(
            "schemes.plan_policies.require_operational_configuration"):
        yield


class AwardFixture(IndependentReviewFixture):
    account = qualification.BenefitQualificationTests.account
    pay = qualification.BenefitQualificationTests.pay
    benefit_account = qualification.BenefitQualificationTests.benefit_account

    def preview(self, account):
        with future_award_readiness():
            return preview_benefit_award(account_id=account.pk, actor=self.owner)

    def record(self, account, token, **changes):
        with future_award_readiness():
            return record_benefit_award(**(dict(account_id=account.pk, actor=self.owner,
                preview_token=token, reason="Verified accepted benefit terms", idempotency_key=uuid.uuid4()) | changes))


@override_settings(IN_STORE_CASH_CONTRIBUTIONS_ENABLED=True, PAYMENT_INITIATION_KILL_SWITCH=False)
class BenefitAwardTests(AwardFixture, TestCase):
    def test_retained_award_matrix_has_no_principal_or_settlement_side_effects(self):
        for kind, metal in (("INR_PURCHASE_BONUS", False), ("VA_DISCOUNT", False), ("VA_DISCOUNT", True)):
            for family in ("optional_anytime", "optional_duration", "count", "both", "benefit_duration"):
                changes = {}
                if family in ("optional_duration", "benefit_duration"):
                    changes.update(eligibility_policy="CALENDAR", duration_months=1)
                if family == "both":
                    changes.update(eligibility_policy="CALENDAR_AND_COUNT", duration_months=1)
                if family == "benefit_duration":
                    changes.update(missed_payment_policy="LOSE_UNEARNED_BENEFIT", max_extension_months=None,
                        benefit_on_miss="DISQUALIFY_UNEARNED")
                account = self.benefit_account(monthly=not family.startswith("optional"), metal=metal, kind=kind, **changes)
                self.cash(account)
                before = [list(m.objects.values()) for m in (SchemeAccount, Contribution, InrPrincipalReceipt, MetalAllocation)]
                at = instant(account.eligible_from) if account.eligible_from else NOW
                with patch("django.utils.timezone.now", return_value=at):
                    award = self.record(account, self.preview(account))
                    validate_benefit_award(award)
                    self.assertFalse(get_benefit_award_status(account).needs_review)
                self.assertEqual(award.kind, kind)
                self.assertEqual(award.configuration_id, account.configuration_snapshot_id)
                if kind == "INR_PURCHASE_BONUS":
                    self.assertEqual(award.amount, 40)
                    self.assertEqual(award.qualifying_principal, 500)
                else:
                    self.assertIsNone(award.amount)
                    self.assertIsNone(award.qualifying_principal)
                    self.assertTrue(award.eligible_charge_definition)
                self.assertEqual(before, [list(m.objects.values()) for m in (SchemeAccount, Contribution, InrPrincipalReceipt, MetalAllocation)])
                self.assertFalse(account.redemptions.exists())
                self.assertFalse(account.inr_settlements.exists())

    def test_signed_preview_idempotency_conflicts_and_expiry(self):
        account = self.benefit_account()
        self.cash(account)
        token, key = self.preview(account), uuid.uuid4()
        for value in (token + "changed", "not-a-token"):
            with self.assertRaises(ValidationError):
                self.record(account, value)
        with patch("django.utils.timezone.now", return_value=NOW + timedelta(seconds=601)), patch(
                "django.core.signing.time.time", return_value=time.time() + 601):
            with self.assertRaisesMessage(ValidationError, "expired"):
                self.record(account, token)
        award = self.record(account, token, idempotency_key=key)
        self.assertEqual(self.record(account, token, idempotency_key=key).pk, award.pk)
        with self.assertRaises(ValidationError):
            self.record(account, token, idempotency_key=key, reason="Different facts")
        with self.assertRaises(ValidationError):
            self.record(account, token)
        with self.assertRaises(ValidationError):
            self.preview(account)
        self.assertEqual(SchemeBenefitAward.objects.count(), 1)

    def test_insert_failure_rolls_back_and_closed_history_is_not_new_credit(self):
        account = self.benefit_account()
        self.cash(account)
        token = self.preview(account)
        create = SchemeBenefitAward.objects.create

        def fail_after_insert(**facts):
            create(**facts)
            raise ValidationError("Injected post-insert failure")

        with patch("schemes.benefit_awards.SchemeBenefitAward.objects.create", side_effect=fail_after_insert):
            with self.assertRaises(ValidationError):
                self.record(account, token)
        self.assertFalse(SchemeBenefitAward.objects.exists())
        award = self.record(account, token)
        SchemeAccount.objects.filter(pk=account.pk).update(status="REDEEMED")
        status = get_benefit_award_status(account)
        self.assertTrue(status.needs_review)
        self.assertEqual(status.recorded_amount, award.amount)
        self.assertEqual(get_inr_principal_summary(account).principal_recorded, 500)

    def test_preview_binds_actor_account_and_reloads_owner_authority(self):
        account = self.benefit_account()
        self.cash(account)
        token = self.preview(account)
        with self.assertRaises(ValidationError):
            self.record(account, token, actor=self.customer.user)
        other = self.benefit_account()
        self.cash(other)
        with self.assertRaises(ValidationError):
            self.record(other, token)
        type(self.owner).objects.filter(pk=self.owner.pk).update(is_active=False)
        with self.assertRaises(ValidationError):
            self.record(account, token)
        self.assertFalse(SchemeBenefitAward.objects.exists())

    def test_changed_sources_refuse_stale_preview_and_retained_award_never_disappears(self):
        account = self.benefit_account(monthly=False, allow_contributions_after_eligibility=True)
        first = self.cash(account)
        stale = self.preview(account)
        self.cash(account)
        with self.assertRaisesMessage(ValidationError, "changed"):
            self.record(account, stale)
        token, key = self.preview(account), uuid.uuid4()
        award = self.record(account, token, idempotency_key=key)
        before = SchemeBenefitAward.objects.values().get(pk=award.pk)
        with patch.object(InStoreCashContributionReversal._meta.get_field("reversed_at"), "_get_default", lambda: NOW):
            reverse_in_store_cash_contribution(contribution=first, processed_by=self.owner,
                reason="Correct duplicate receipt", reason_code="WRONG_AMOUNT")
        status = get_benefit_award_status(account)
        self.assertTrue(status.needs_review)
        self.assertEqual(status.recorded_amount, 40)
        self.assertEqual(get_inr_principal_summary(account).principal_recorded, 500)
        self.assertEqual(before, SchemeBenefitAward.objects.values().get(pk=award.pk))
        self.assertEqual(self.record(account, token, idempotency_key=key).pk, award.pk)
        with self.assertRaises(CommandError):
            call_command("check_benefit_awards", stdout=StringIO())

    def test_no_award_on_incomplete_held_or_early_exit_agreement(self):
        account = self.benefit_account(required_count=2)
        self.cash(account)
        with self.assertRaises(ValidationError):
            self.preview(account)
        complete = self.benefit_account()
        self.cash(complete)
        self.hold(complete)
        with self.assertRaises(ValidationError):
            self.preview(complete)
        from schemes.tests.test_inr_settlements import accepted_request
        early = self.benefit_account()
        self.cash(early)
        accepted_request(early, self.owner)
        with self.assertRaises(ValidationError):
            self.preview(early)
        self.assertFalse(SchemeBenefitAward.objects.exists())

    def test_retained_terms_survive_current_offer_edits_and_reads_are_nonmutating(self):
        account = self.benefit_account()
        self.cash(account)
        award = self.record(account, self.preview(account))
        other = self.benefit_account()
        SchemePlan.objects.filter(pk=account.plan_id).update(configuration_id=other.configuration_snapshot_id)
        with CaptureQueriesContext(connection) as queries:
            self.assertFalse(get_benefit_award_status(account).needs_review)
            call_command("check_benefit_awards", stdout=StringIO())
        self.assertFalse(any(q["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")) for q in queries))
        with self.assertRaises(ValidationError):
            award.save()
        with self.assertRaises(ValidationError):
            award.delete()
        # Privileged SQL drift is detected, not silently repaired or treated as credit.
        SchemeBenefitAward.objects.filter(pk=award.pk).update(evidence_digest="0" * 64)
        self.assertTrue(get_benefit_award_status(account).needs_review)

    def test_database_shapes_and_retention_reverse_guard(self):
        account = self.benefit_account(kind="VA_DISCOUNT", metal=True)
        self.cash(account)
        award = self.record(account, self.preview(account))
        for facts in (dict(amount=10), dict(percentage=0), dict(cap_inr=0), dict(kind="CASH"), dict(actor_label="")):
            with self.assertRaises(IntegrityError), transaction.atomic():
                SchemeBenefitAward.objects.filter(pk=award.pk).update(**facts)
        award.pk, award.idempotency_key = None, uuid.uuid4()
        with self.assertRaises(IntegrityError), transaction.atomic():
            SchemeBenefitAward.objects.bulk_create([award])
        migration = importlib.import_module("schemes.migrations.0046_retained_benefit_awards")
        with connection.schema_editor(atomic=False) as editor, self.assertRaises(RuntimeError):
            migration.guard_reverse(apps, editor)

    def test_real_gate_blocks_service_and_direct_model_creation_with_flag_off_or_on(self):
        account = self.benefit_account()
        self.cash(account)
        token = self.preview(account)
        for enabled in (False, True):
            with override_settings(CONFIGURED_PLANS_ENABLED=enabled), self.assertRaises(ValidationError):
                preview_benefit_award(account_id=account.pk, actor=self.owner)
            with override_settings(CONFIGURED_PLANS_ENABLED=enabled), self.assertRaises(ValidationError):
                record_benefit_award(account_id=account.pk, actor=self.owner, preview_token=token,
                    reason="Try real gate", idempotency_key=uuid.uuid4())
            with override_settings(CONFIGURED_PLANS_ENABLED=enabled), self.assertRaises(ValidationError):
                SchemeBenefitAward(scheme_account=account).save()
        self.assertFalse(SchemeBenefitAward.objects.exists())

    def test_pending_provider_exposure_blocks_apply_even_after_a_valid_preview(self):
        account = self.benefit_account(monthly=False, allow_contributions_after_eligibility=True)
        self.cash(account)
        token = self.preview(account)
        self.online(account)
        with self.assertRaises(ValidationError):
            self.record(account, token)
        self.assertFalse(SchemeBenefitAward.objects.exists())
        self.assertEqual(get_inr_principal_summary(account).principal_recorded, 500)


@override_settings(IN_STORE_CASH_CONTRIBUTIONS_ENABLED=True, PAYMENT_INITIATION_KILL_SWITCH=False)
class BenefitAwardConcurrencyTests(AwardFixture, TransactionTestCase):
    def test_concurrent_retries_retain_exactly_one_award(self):
        account = self.benefit_account()
        self.cash(account)
        token, key, barrier = self.preview(account), uuid.uuid4(), Barrier(2)

        def apply():
            try:
                barrier.wait(timeout=10)
                return record_benefit_award(account_id=account.pk, actor=self.owner, preview_token=token,
                    reason="Concurrent verified award", idempotency_key=key).pk
            finally:
                connections.close_all()

        with future_award_readiness(), ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: apply(), range(2)))
        self.assertEqual(results[0], results[1])
        self.assertEqual(SchemeBenefitAward.objects.count(), 1)

    def test_concurrent_new_cash_and_award_serialize_without_using_a_stale_base(self):
        account = self.benefit_account(monthly=False, allow_contributions_after_eligibility=True)
        self.cash(account)
        token, barrier = self.preview(account), Barrier(2)

        def apply(kind):
            try:
                barrier.wait(timeout=10)
                if kind == "cash":
                    return self.cash(account).pk
                try:
                    return record_benefit_award(account_id=account.pk, actor=self.owner, preview_token=token,
                        reason="Concurrent verified award", idempotency_key=uuid.uuid4()).pk
                except ValidationError:
                    return None
            finally:
                connections.close_all()

        with future_award_readiness(), ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(apply, ("cash", "award")))
        self.assertEqual(get_inr_principal_summary(account).principal_recorded, 1000)
        if results[1] is None:
            self.assertFalse(SchemeBenefitAward.objects.exists())
        else:
            award = SchemeBenefitAward.objects.get()
            self.assertEqual(award.qualifying_principal, 500)
            self.assertTrue(get_benefit_award_status(account).needs_review)
