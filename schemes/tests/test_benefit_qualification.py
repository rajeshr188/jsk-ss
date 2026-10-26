"""Purchase-benefit calculations/progress; actual awards and fulfilment stay gated."""
from datetime import timedelta
from decimal import Decimal, ROUND_DOWN, localcontext
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import connection
from django.test import SimpleTestCase, TestCase, override_settings
from django.test.utils import CaptureQueriesContext

from schemes.benefits import calculate_purchase_bonus, calculate_va_discount
from schemes.benefit_selectors import get_benefit_qualification
from schemes.agreement_eligibility import get_independent_eligibility
from schemes.models import (Contribution, InrPrincipalReceipt, InStoreCashContributionReversal,
    MetalAllocation, SchemeAccount, SchemePlan)
from schemes.plan_policies import require_operational_configuration
from schemes.services import reverse_in_store_cash_contribution
from schemes.tests import test_independent_eligibility as eligibility
from schemes.tests.test_independent_instalment_reviews import IndependentReviewFixture, instant
from schemes.tests.test_independent_instalment_ledger import NOW


class BenefitArithmeticTests(SimpleTestCase):
    def test_single_paise_rounding_cap_and_no_compounding(self):
        cases = [("100.05", "10", "100", "10.01"), ("500", "10", "40", "40.00"),
                 ("0", "10", "40", "0.00"), ("0.01", "100", "40", "0.01"),
                 ("999999999999.99", "100", "999999999999.99", "999999999999.99")]
        for base, percentage, cap, expected in cases:
            with localcontext() as context:
                context.prec, context.rounding = 4, ROUND_DOWN
                result = calculate_purchase_bonus(qualifying_principal=Decimal(base),
                    percentage=Decimal(percentage), cap=Decimal(cap))
            self.assertEqual(result.amount, Decimal(expected))
            self.assertEqual(result.base, Decimal(base))
            self.assertEqual(result.rounding_rule, "PAISE_HALF_UP_ONCE")
            self.assertEqual(result.version, "PURCHASE_BENEFIT_V1")

    def test_va_uses_only_eligible_charges_not_invoice_or_metal(self):
        result = calculate_va_discount(eligible_charges=Decimal("200.05"), invoice_payable=Decimal("20000"),
            percentage=Decimal("10"), cap=Decimal("100"))
        self.assertEqual(result.amount, Decimal("20.01"))
        self.assertEqual(result.base, Decimal("200.05"))
        with self.assertRaises(ValidationError):
            calculate_va_discount(eligible_charges=Decimal("101"), invoice_payable=Decimal("100"),
                percentage=Decimal("10"), cap=Decimal("100"))

    def test_invalid_money_percent_and_cap_fail_without_coercion(self):
        defaults = dict(qualifying_principal=Decimal("100"), percentage=Decimal("10"), cap=Decimal("50"))
        for field in defaults:
            for value in (True, 1, 1.5, "10", None, Decimal("NaN"), Decimal("Infinity"), Decimal("-1"), Decimal("1.001")):
                with self.subTest(field=field, value=value), self.assertRaises(ValidationError):
                    calculate_purchase_bonus(**(defaults | {field: value}))
        for field, value in (("percentage", Decimal("101")), ("percentage", Decimal(0)),
                             ("cap", Decimal(0)), ("qualifying_principal", Decimal("1000000000000"))):
            with self.assertRaises(ValidationError):
                calculate_purchase_bonus(**(defaults | {field: value}))


@override_settings(IN_STORE_CASH_CONTRIBUTIONS_ENABLED=True, PAYMENT_INITIATION_KILL_SWITCH=False)
class BenefitQualificationTests(IndependentReviewFixture, TestCase):
    account = eligibility.IndependentEligibilityTests.account
    pay = eligibility.IndependentEligibilityTests.pay

    def benefit_account(self, *, monthly=True, metal=False, kind="INR_PURCHASE_BONUS", **changes):
        return self.account(monthly, metal, **(dict(
            required_count=1 if monthly else None, benefit_policy=kind,
            benefit_percentage=Decimal("10"), benefit_cap_inr=Decimal("40"),
            benefit_qualification="REQUIRED_SCHEDULE" if monthly else "NORMAL_ELIGIBILITY",
            benefit_on_miss="PRESERVE_ON_COMPLETION" if monthly else "NONE",
            eligible_charge_definition="Making charges excluding taxes" if kind == "VA_DISCOUNT" else "") | changes))

    def evaluate(self, account, at=NOW):
        with patch("django.utils.timezone.now", return_value=at):
            return get_benefit_qualification(account)

    def test_five_family_and_allowed_denomination_matrix(self):
        for kind, metal in (("INR_PURCHASE_BONUS", False), ("VA_DISCOUNT", False), ("VA_DISCOUNT", True)):
            for family in ("optional_anytime", "optional_duration", "count", "both", "benefit_duration"):
                monthly = not family.startswith("optional")
                values = {}
                if family in ("optional_duration", "benefit_duration"):
                    values.update(eligibility_policy="CALENDAR", duration_months=1)
                if family == "both":
                    values.update(eligibility_policy="CALENDAR_AND_COUNT", duration_months=1)
                if family == "benefit_duration":
                    values.update(missed_payment_policy="LOSE_UNEARNED_BENEFIT", max_extension_months=None,
                        benefit_on_miss="DISQUALIFY_UNEARNED")
                account = self.benefit_account(monthly=monthly, metal=metal, kind=kind, **values)
                self.cash(account)
                at = instant(account.eligible_from) if account.eligible_from else NOW
                result = self.evaluate(account, at)
                self.assertTrue(result.qualification_met, (kind, family, result))
                if kind == "INR_PURCHASE_BONUS":
                    self.assertEqual(result.qualifying_principal, Decimal("500"))
                    self.assertEqual(result.calculation.amount, Decimal("40.00"))
                    self.assertEqual(len(result.source_receipt_ids), 1)
                else:
                    self.assertIsNone(result.calculation)
                    self.assertIsNone(result.qualifying_principal)
                    self.assertEqual(result.source_receipt_ids, ())

    def test_preserve_on_completion_differs_from_disqualify_after_ordinary_miss(self):
        for basis in ("CALENDAR_MONTH", "ANNIVERSARY"):
            for outcome, expected in (("PRESERVE_ON_COMPLETION", "QUALIFICATION_MET"),
                                      ("DISQUALIFY_UNEARNED", "UNQUALIFIED_MISS")):
                account = self.benefit_account(period_basis=basis, benefit_on_miss=outcome)
                _, at = self.pay(account, 2)
                result = self.evaluate(account, at)
                self.assertEqual(result.state, expected)
                with patch("django.utils.timezone.now", return_value=at):
                    self.assertTrue(get_independent_eligibility(account).policy_eligible)
                self.assertEqual(result.missed_period_numbers, (1,) if outcome == "DISQUALIFY_UNEARNED" else ())

    def test_date_only_principal_does_not_require_or_award_missing_benefit_count(self):
        account = self.benefit_account(eligibility_policy="CALENDAR", duration_months=1, required_count=2,
            missed_payment_policy="LOSE_UNEARNED_BENEFIT", max_extension_months=None,
            benefit_on_miss="DISQUALIFY_UNEARNED")
        self.cash(account)
        at = instant(account.eligible_from)
        self.assertEqual(self.evaluate(account, at).state, "WAITING_SCHEDULE")
        with patch("django.utils.timezone.now", return_value=at):
            self.assertTrue(get_independent_eligibility(account).policy_eligible)
        ended = instant(account.instalment_periods.get(number=2).ends_before)
        self.assertEqual(self.evaluate(account, ended).state, "UNQUALIFIED_MISS")
        self.assertEqual(InrPrincipalReceipt.objects.get().amount, Decimal("500"))

    def test_completed_schedule_waits_for_duration_before_completion_benefit(self):
        account = self.benefit_account(eligibility_policy="CALENDAR_AND_COUNT", duration_months=18)
        self.cash(account)
        self.assertEqual(self.evaluate(account).state, "WAITING_ELIGIBILITY")
        self.assertTrue(self.evaluate(account, instant(account.eligible_from)).qualification_met)

    def test_exhausted_replacements_need_review_without_forfeiting_principal(self):
        account = self.benefit_account(required_count=2)
        self.cash(account)
        end = instant(account.instalment_periods.order_by("number").last().ends_before)
        self.assertEqual(self.evaluate(account, end).state, "REVIEW")
        self.assertEqual(InrPrincipalReceipt.objects.get().amount, Decimal("500"))

    def test_outage_is_not_a_miss_and_compensation_is_not_free_credit(self):
        account = self.benefit_account(benefit_on_miss="DISQUALIFY_UNEARNED")
        hold = self.hold(account)
        ended = instant(hold.period.ends_before)
        self.assertEqual(self.evaluate(account, ended).state, "REVIEW")
        resolution = self.resolve(hold)
        self.assertEqual(self.evaluate(account, ended).state, "WAITING_SCHEDULE")
        _, at = self.pay(account, resolution.compensation_period.number)
        self.assertTrue(self.evaluate(account, at).qualification_met)

    def test_unpaid_compensation_cannot_be_replaced_by_ordinary_count_completion(self):
        account = self.benefit_account(benefit_on_miss="DISQUALIFY_UNEARNED")
        self.resolve(self.hold(account))
        _, at = self.pay(account, 2)
        result = self.evaluate(account, at)
        self.assertEqual(result.state, "REVIEW")
        self.assertIn("do not request an extra payment", result.message)

    def test_reversal_removes_only_unawarded_preview_not_retained_principal_history(self):
        account = self.benefit_account(monthly=False, allow_contributions_after_eligibility=True)
        first = self.cash(account)
        self.cash(account)
        self.assertEqual(self.evaluate(account).qualifying_principal, Decimal("1000"))
        with patch.object(InStoreCashContributionReversal._meta.get_field("reversed_at"), "_get_default", lambda: NOW):
            reverse_in_store_cash_contribution(contribution=first, processed_by=self.owner,
                reason="Duplicate receipt corrected", reason_code="WRONG_AMOUNT")
        result = self.evaluate(account)
        self.assertEqual(result.qualifying_principal, Decimal("500"))
        self.assertEqual(len(result.source_receipt_ids), 1)
        self.assertEqual(InrPrincipalReceipt.objects.count(), 2)

    def test_timing_uncertainty_source_drift_and_pending_payment_prevent_award(self):
        account = self.benefit_account()
        c = self.online(account)
        self.assertEqual(self.evaluate(account).state, "REVIEW")
        self.capture(c, at=None)
        self.assertEqual(self.evaluate(account, NOW + timedelta(minutes=12)).state, "REVIEW")
        other = self.benefit_account()
        c = self.cash(other)
        InrPrincipalReceipt.objects.filter(contribution=c).update(amount=Decimal("600"))
        self.assertEqual(self.evaluate(other).state, "REVIEW")

    def test_pinned_terms_not_current_plan_and_reads_do_not_write(self):
        account = self.benefit_account()
        self.cash(account)
        other = self.benefit_account(benefit_percentage=Decimal("1"), benefit_cap_inr=Decimal("10"))
        SchemePlan.objects.filter(pk=account.plan_id).update(configuration_id=other.configuration_snapshot_id)
        before = [list(m.objects.values()) for m in (SchemeAccount, Contribution, InrPrincipalReceipt, MetalAllocation)]
        with CaptureQueriesContext(connection) as queries:
            result = self.evaluate(account)
        self.assertEqual(result.calculation.amount, Decimal("40"))
        self.assertEqual(result.configuration_id, account.configuration_snapshot_id)
        self.assertFalse(any(q["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")) for q in queries))
        self.assertEqual(before, [list(m.objects.values()) for m in (SchemeAccount, Contribution, InrPrincipalReceipt, MetalAllocation)])

    def test_closed_or_accepted_agreement_needs_retained_award_history(self):
        from schemes.tests.test_inr_settlements import accepted_request
        account = self.benefit_account()
        self.cash(account)
        accepted_request(account, self.owner)
        self.assertEqual(self.evaluate(account).state, "HISTORY_REVIEW")
        SchemeAccount.objects.filter(pk=account.pk).update(status="REDEEMED")
        self.assertEqual(self.evaluate(account).state, "HISTORY_REVIEW")

    def test_none_and_operational_gates_are_not_bypassed(self):
        self.assertEqual(self.evaluate(self.account()).state, "NONE")
        account = self.benefit_account()
        self.cash(account)
        for flag in (False, True):
            with override_settings(CONFIGURED_PLANS_ENABLED=flag):
                self.assertTrue(self.evaluate(account).qualification_met)
                with self.assertRaises(ValidationError):
                    require_operational_configuration(account.configuration_snapshot)
