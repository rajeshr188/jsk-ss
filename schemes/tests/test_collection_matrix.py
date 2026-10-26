"""Collection acceptance on synthetic schema-2 contracts, not release permission.

Only readiness and provider I/O are simulated. Benefit terms are frozen inputs;
qualifying a payment is not awarding a benefit or authorizing settlement.
Webhook fixtures enter the post-authentication service; signature verification
remains covered separately by adapter/view tests.
"""
import json
import uuid
from datetime import datetime, time, timedelta
from decimal import Decimal
from itertools import product
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings

from schemes.instalments import AGREEMENT_TIMEZONE
from schemes.instalment_selectors import get_monthly_eligibility, instalment_payment_ledger_summary
from schemes.inr_selectors import get_inr_principal_summary
from schemes.models import InrPrincipalReceipt, InStoreCashContributionReversal, MetalAllocation
from schemes.services import (initiate_razorpay_contribution, process_razorpay_webhook,
    reverse_in_store_cash_contribution)
from schemes.tests import test_independent_payment_entry as entry
from schemes.tests.test_independent_instalment_ledger import NOW


def benefit_terms(kind="VA_DISCOUNT", *, required=True, on_miss="DISQUALIFY_UNEARNED"):
    return dict(benefit_policy=kind, benefit_percentage=Decimal("5"), benefit_cap_inr=Decimal("500"),
        benefit_qualification="REQUIRED_SCHEDULE" if required else "NORMAL_ELIGIBILITY",
        benefit_on_miss=on_miss if required else "NONE",
        eligible_charge_definition="Evidenced making charges, excluding taxes" if kind == "VA_DISCOUNT" else "")


@override_settings(IN_STORE_CASH_CONTRIBUTIONS_ENABLED=True, PAYMENT_INITIATION_KILL_SWITCH=False)
class CollectionMatrixTests(TestCase):
    setUp = entry.IndependentPaymentEntryTests.setUp
    account = entry.IndependentPaymentEntryTests.account
    cash = entry.IndependentPaymentEntryTests.cash
    gateway = entry.IndependentPaymentEntryTests.gateway

    def capture(self, contribution, *, earliest=None, latest=None):
        instant = NOW if earliest is None else earliest
        payload = {"event": "payment.captured", "created_at": int((latest or instant).timestamp()),
            "payload": {"payment": {"entity": dict(id=f"pay_{contribution.pk}",
                order_id=contribution.gateway_order_id, amount=50000, currency="INR",
                status="captured", captured=True, created_at=int(instant.timestamp()))}}}
        event = process_razorpay_webhook(gateway_mode="live", event_id=uuid.uuid4().hex,
            payload=payload, body=json.dumps(payload).encode())
        self.assertEqual(event.status, "PROCESSED")
        contribution.refresh_from_db()
        return contribution

    def pay(self, account, channel):
        if channel == "cash":
            return self.cash(account)
        c = initiate_razorpay_contribution(scheme_account=account, amount=Decimal("500"), gateway=self.gateway())
        self.capture(c)
        self.capture(c)  # A new delivery identity must not credit the source again.
        return c

    def assert_entitlement(self, account, *, principal="500", grams="0.050000"):
        if account.savings_mode == "INR_CREDIT":
            summary = get_inr_principal_summary(account)
            self.assertFalse(summary.needs_review)
            self.assertEqual(summary.principal_recorded, Decimal(principal))
            self.assertFalse(MetalAllocation.objects.filter(contribution__scheme_account=account).exists())
            self.assertFalse(account.contributions.filter(scheme_rate__isnull=False).exists())
        else:
            self.assertFalse(InrPrincipalReceipt.objects.filter(contribution__scheme_account=account).exists())
            allocations = MetalAllocation.objects.filter(contribution__scheme_account=account)
            self.assertEqual(sum((a.quantity for a in allocations), Decimal("0")), Decimal(grams))
            self.assertTrue(all(a.metal_grade_id == account.metal_grade_id for a in allocations))

    def test_five_family_collection_matrix_amount_basis_denomination_and_channel(self):
        cases = 0
        for family in ("optional_duration", "optional_anytime", "count", "duration_count", "benefit_duration"):
            required = not family.startswith("optional")
            amounts = ("PLAN_FIXED", "CUSTOMER_FIXED") + (() if required else ("VARIABLE",))
            bases = ("CALENDAR_MONTH", "ANNIVERSARY") + (() if required else (None,))
            for metal, channel, amount, basis in product((False, True), ("cash", "online"), amounts, bases):
                with self.subTest(family=family, metal=metal, channel=channel, amount=amount, basis=basis):
                    changes = dict(amount_policy=amount, period_basis=basis,
                        frequency_rule="ONCE_PER_PERIOD" if basis else "FLEXIBLE")
                    if amount == "PLAN_FIXED":
                        changes.update(fixed_amount=Decimal("500"), minimum_amount=Decimal("500"), maximum_amount=Decimal("500"))
                    if family in ("optional_duration", "benefit_duration"):
                        changes.update(eligibility_policy="CALENDAR", duration_months=18)
                    if family == "duration_count":
                        changes.update(eligibility_policy="CALENDAR_AND_COUNT", duration_months=18)
                    if required:
                        changes["required_count"] = 2
                    if family == "benefit_duration":
                        changes.update(missed_payment_policy="LOSE_UNEARNED_BENEFIT", max_extension_months=None,
                            **benefit_terms())
                    account = self.account(required, metal, **changes)
                    before = (account.eligible_from, account.required_count_snapshot, account.plan_revision.terms)
                    c = self.pay(account, channel)
                    self.assertEqual(c.status, "PAID")
                    self.assertEqual(account.contributions.count(), 1)
                    self.assert_entitlement(account)
                    if required:
                        self.assertEqual(account.instalment_periods.count(), 2 if family == "benefit_duration" else 5)
                        ledger = instalment_payment_ledger_summary(account_id=account.pk)
                        self.assertEqual((ledger["qualified_payments"], ledger["integrity_errors"]), (1, 0))
                        self.assertEqual(c.instalment_reservation.period.number, 1)
                    else:
                        self.assertFalse(account.instalment_periods.exists())
                        self.assertFalse(hasattr(c, "instalment_reservation"))
                    account.refresh_from_db()
                    self.assertEqual((account.eligible_from, account.required_count_snapshot, account.plan_revision.terms), before)
                    self.assertEqual(account.status, "ACTIVE")
                    with self.assertRaisesMessage(ValidationError, "not activated"):
                        get_monthly_eligibility(account)
                    cases += 1
        self.assertEqual(cases, 120)

    def test_bonus_and_discount_terms_never_add_principal_or_metal_on_collection(self):
        for kind, metal in (("INR_PURCHASE_BONUS", False), ("VA_DISCOUNT", False), ("VA_DISCOUNT", True)):
            for required, on_miss in ((False, "NONE"), (True, "PRESERVE_ON_COMPLETION"), (True, "DISQUALIFY_UNEARNED")):
                with self.subTest(kind=kind, metal=metal, required=required, on_miss=on_miss):
                    account = self.account(required, metal, **benefit_terms(kind, required=required, on_miss=on_miss))
                    self.pay(account, "online")
                    self.assert_entitlement(account)
                    self.assertFalse(account.inr_settlements.exists())

    def test_missed_benefit_window_retains_principal_and_original_maturity_without_replacements(self):
        for basis, metal in product(("CALENDAR_MONTH", "ANNIVERSARY"), (False, True)):
            with self.subTest(basis=basis, metal=metal):
                account = self.account(True, metal, required_count=2, period_basis=basis,
                    eligibility_policy="CALENDAR", duration_months=18, max_extension_months=None,
                    missed_payment_policy="LOSE_UNEARNED_BENEFIT", **benefit_terms())
                original_date = account.eligible_from
                periods = list(account.instalment_periods.order_by("number"))
                second_start = datetime.combine(periods[1].starts_on, time.min, tzinfo=AGREEMENT_TIMEZONE)
                with patch("django.utils.timezone.now", return_value=second_start):
                    c = self.cash(account)  # First month intentionally unpaid; no invented catch-up.
                    self.assert_entitlement(account)
                self.assertEqual(c.instalment_reservation.period_id, periods[1].pk)
                self.assertFalse(periods[0].reservations.exists())
                after = datetime.combine(periods[-1].ends_before, time.min, tzinfo=AGREEMENT_TIMEZONE)
                with patch("django.utils.timezone.now", return_value=after), self.assertRaises(ValidationError):
                    self.cash(account)
                self.assertEqual(account.instalment_periods.count(), 2)
                account.refresh_from_db()
                self.assertEqual(account.eligible_from, original_date)

    def test_count_replacements_are_separate_from_duration_and_stop_after_verified_count(self):
        for basis, eligibility in product(("CALENDAR_MONTH", "ANNIVERSARY"), ("COUNT", "CALENDAR_AND_COUNT")):
            with self.subTest(basis=basis, eligibility=eligibility):
                account = self.account(True, required_count=1, period_basis=basis, eligibility_policy=eligibility,
                    duration_months=18 if eligibility == "CALENDAR_AND_COUNT" else None,
                    **benefit_terms("INR_PURCHASE_BONUS", on_miss="PRESERVE_ON_COMPLETION"))
                periods = list(account.instalment_periods.order_by("number"))
                self.assertEqual(len(periods), 4)
                at = datetime.combine(periods[1].starts_on, time.min, tzinfo=AGREEMENT_TIMEZONE)
                with patch("django.utils.timezone.now", return_value=at):
                    c = self.cash(account)
                    self.assert_entitlement(account)
                self.assertEqual(c.instalment_reservation.period.number, 2)
                at = datetime.combine(periods[2].starts_on, time.min, tzinfo=AGREEMENT_TIMEZONE)
                with patch("django.utils.timezone.now", return_value=at), self.assertRaises(ValidationError):
                    self.cash(account)

    def test_benefit_cash_correction_keeps_history_and_releases_only_original_period(self):
        for kind in ("INR_PURCHASE_BONUS", "VA_DISCOUNT"):
            account = self.account(True, required_count=2, eligibility_policy="CALENDAR", duration_months=18,
                max_extension_months=None, missed_payment_policy="LOSE_UNEARNED_BENEFIT", **benefit_terms(kind))
            c = self.cash(account)
            with patch.object(InStoreCashContributionReversal._meta.get_field("reversed_at"), "_get_default", lambda: NOW):
                reverse_in_store_cash_contribution(contribution=c, processed_by=self.owner,
                    reason_code="WRONG_AMOUNT", reason="Synthetic collection acceptance correction")
            replacement = self.cash(account)
            c.refresh_from_db()
            self.assertEqual(c.instalment_reservation.state, "REVERSED")
            self.assertEqual(replacement.instalment_reservation.period_id, c.instalment_reservation.period_id)
            ledger = instalment_payment_ledger_summary(account_id=account.pk)
            self.assertEqual((ledger["qualified_payments"], ledger["reversed"], ledger["integrity_errors"]), (1, 1, 0))
            self.assert_entitlement(account)

    def test_late_signed_benefit_capture_preserves_principal_but_holds_schedule(self):
        account = self.account(True, required_count=2, eligibility_policy="CALENDAR", duration_months=18,
            max_extension_months=None, missed_payment_policy="LOSE_UNEARNED_BENEFIT", **benefit_terms("INR_PURCHASE_BONUS"))
        c = initiate_razorpay_contribution(scheme_account=account, amount=Decimal("500"), gateway=self.gateway())
        late = NOW + timedelta(minutes=11)
        with patch("django.utils.timezone.now", return_value=late):
            self.capture(c, latest=late)
            self.assert_entitlement(account)
            with self.assertRaisesMessage(ValidationError, "reservation or evidence review"):
                self.cash(account)
        self.assertEqual(c.instalment_reservation.state, "REVIEW")
        ledger = instalment_payment_ledger_summary(account_id=account.pk)
        self.assertEqual((ledger["qualified_payments"], ledger["review_required"], ledger["integrity_errors"]), (0, 1, 0))

    def test_signed_capture_boundary_not_delivery_month_controls_benefit_instalment(self):
        # Provider timestamps have whole-second precision: the last second is
        # deliberately ambiguous at the exclusive boundary, not proven on time.
        for basis, seconds_before in product(("CALENDAR_MONTH", "ANNIVERSARY"), (2, 1, 0)):
            review = seconds_before < 2
            with self.subTest(basis=basis, seconds_before=seconds_before):
                account = self.account(True, required_count=2, period_basis=basis,
                    eligibility_policy="CALENDAR", duration_months=18, max_extension_months=None,
                    missed_payment_policy="LOSE_UNEARNED_BENEFIT", **benefit_terms("INR_PURCHASE_BONUS"))
                first = account.instalment_periods.get(number=1)
                boundary = datetime.combine(first.ends_before, time.min, tzinfo=AGREEMENT_TIMEZONE)
                started = boundary - timedelta(minutes=1)
                with patch("django.utils.timezone.now", return_value=started):
                    c = initiate_razorpay_contribution(scheme_account=account, amount=Decimal("500"), gateway=self.gateway())
                self.assertEqual(c.checkout_expires_at, boundary)
                signed_at = boundary - timedelta(seconds=seconds_before)
                with patch("django.utils.timezone.now", return_value=boundary + timedelta(minutes=5)):
                    self.capture(c, earliest=started, latest=signed_at)
                    self.assert_entitlement(account)
                    self.assertEqual(c.instalment_reservation.state, "REVIEW" if review else "QUALIFIED")
                    self.assertEqual(c.instalment_reservation.period_id, first.pk)
                    ledger = instalment_payment_ledger_summary(account_id=account.pk)
                    self.assertEqual(ledger["qualified_payments"], 0 if review else 1)
                    self.assertEqual(ledger["integrity_errors"], 0)
                    if review:
                        with self.assertRaisesMessage(ValidationError, "reservation or evidence review"):
                            self.cash(account)

    def test_all_families_still_reject_real_entry_with_either_release_flag(self):
        accounts = [self.account(), self.account(eligibility_policy="CALENDAR", duration_months=12),
            self.account(True), self.account(True, eligibility_policy="CALENDAR_AND_COUNT", duration_months=18),
            self.account(True, eligibility_policy="CALENDAR", duration_months=18, max_extension_months=None,
                missed_payment_policy="LOSE_UNEARNED_BENEFIT", **benefit_terms())]
        self.ready.stop()
        for account, enabled in product(accounts, (False, True)):
            with self.subTest(account=account.pk, enabled=enabled), override_settings(CONFIGURED_PLANS_ENABLED=enabled):
                with self.assertRaises(ValidationError):
                    self.cash(account)
                gateway = self.gateway()
                with self.assertRaises(ValidationError):
                    initiate_razorpay_contribution(scheme_account=account, amount=Decimal("500"), gateway=gateway)
                gateway.create_order.assert_not_called()
                self.assertFalse(account.contributions.exists())
