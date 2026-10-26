"""Family presentation and gated reminders on disposable, real-source agreements."""
from dataclasses import replace
from datetime import timedelta
from unittest.mock import patch

from django.core import mail
from django.db import connection
from django.template.loader import render_to_string
from django.test import TestCase, override_settings
from django.urls import reverse

from schemes.models import SchemeAccount, SchemePlan, SchemeReminder
from schemes.presentation import independent_agreement_presentation
from schemes.reminders import build_scheme_reminder_plan, deliver_scheme_reminder
from schemes.selectors import eligibility_reminder_terms, get_customer_payment_availability
from schemes.tests import test_independent_payment_entry as entry
from schemes.tests import test_independent_eligibility as eligibility
from schemes.tests.test_independent_instalment_reviews import instant
from schemes.tests.test_reminders import REMINDER_SETTINGS

BENEFIT = eligibility.BENEFIT


@override_settings(**REMINDER_SETTINGS, CONFIGURED_PLANS_ENABLED=False,
    IN_STORE_CASH_CONTRIBUTIONS_ENABLED=True, PAYMENT_INITIATION_KILL_SWITCH=False)
class IndependentPresentationTests(TestCase):
    setUp = entry.IndependentPaymentEntryTests.setUp
    account = entry.IndependentPaymentEntryTests.account
    cash = entry.IndependentPaymentEntryTests.cash
    pay = eligibility.IndependentEligibilityTests.pay

    def test_all_families_render_pinned_distinct_terms_without_writes(self):
        for metal in (False, True):
            for required, options in ((False, {}), (False, dict(eligibility_policy="CALENDAR", duration_months=1)),
                    (True, dict(required_count=2)), (True, dict(required_count=2, eligibility_policy="CALENDAR_AND_COUNT", duration_months=18)),
                    (True, BENEFIT)):
                account = self.account(required, metal, **options)
                def forbid_writes(execute, sql, params, many, context):
                    self.assertNotIn(sql.lstrip().split()[0].upper(), {"INSERT", "UPDATE", "DELETE"})
                    return execute(sql, params, many, context)
                with connection.execute_wrapper(forbid_writes):
                    content = render_to_string("schemes/includes/agreement_basis.html", {"scheme_account": account})
                self.assertNotIn("None months", content)
                self.assertNotIn("No bonus or discount is included", content)
                self.assertNotIn("twelve successful monthly", content)
                self.assertIn("no partial withdrawals", content)
                if not account.agreed_months:
                    self.assertIn("No fixed-duration maturity date", content)
                if not metal:
                    self.assertIn("INR jewellery purchase credit; no metal rate or grams", content)
                if options == BENEFIT:
                    self.assertIn("Loss of the named unearned benefit, not principal", content)
                    self.assertIn("Making charges excluding taxes", content)
                SchemePlan.objects.filter(pk=account.plan_id).update(name="Changed current offer")
                self.assertNotIn("Changed current offer", render_to_string(
                    "schemes/includes/agreement_basis.html", {"scheme_account": account}))

    def test_offer_and_owner_policy_share_facts_and_escape_input(self):
        account = self.account(True, False, **(BENEFIT | dict(eligible_charge_definition="Making <script>bad()</script>")))
        config = account.configuration_snapshot
        offer = render_to_string(
            "schemes/includes/configured_offer_rules.html", {"plan": account.plan})
        owner = render_to_string("schemes/includes/independent_policy.html", {"configuration": config})
        for content in (offer, owner):
            self.assertIn("INR jewellery purchase credit", content)
            self.assertIn("enrolment-day payment counts", content)
            self.assertIn("&lt;script&gt;", content)
            self.assertNotIn("<script>", content)
            self.assertNotIn("not INR purchase credit", content)
        self.assertIn("No automatic free instalment", owner)
        card = render_to_string("pages/includes/plan_offer.html", {"plan": account.plan})
        self.assertNotIn("None months", card)
        self.assertIn("Loss of the named unearned benefit", card)

    def test_customer_page_renders_inr_without_rate_or_payment_permission(self):
        account = self.account()
        self.client.force_login(self.customer.user)
        response = self.client.get(reverse("schemes:my_scheme_detail", args=[account.scheme_number]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "INR jewellery purchase credit has no metal rate")
        self.assertNotContains(response, "None months")
        for route in ("schemes:my_schemes", "schemes:customer_plans"):
            page = self.client.get(reverse(route))
            self.assertEqual(page.status_code, 200)
            self.assertNotContains(page, "None months")
            self.assertContains(page, "View purchase-credit principal and settlement statement")
            self.assertNotContains(page, "Current Scheme Rate")
        self.assertFalse(get_customer_payment_availability(account).allowed)
        self.assertNotIn("eligible", account.effective_status_label.lower())
        self.client.force_login(self.owner)
        owner_page = self.client.get(reverse("schemes:customer_detail", args=[self.customer.pk]), {"section": "plans"})
        self.assertEqual(owner_page.status_code, 200)
        self.assertNotContains(owner_page, "None months")
        self.assertNotContains(owner_page, "Record in-store cash")
        self.assertContains(owner_page, "no fixed-duration maturity")
        self.assertEqual(self.client.get(reverse("schemes:plan_list")).status_code, 200)

    def test_corrupt_frozen_terms_do_not_display_current_offer_as_contract(self):
        account = self.account()
        SchemeAccount.objects.filter(pk=account.pk).update(minimum_amount_snapshot=999)
        result = independent_agreement_presentation(account)
        self.assertTrue(result.needs_review)
        self.assertEqual(result.terms, ())
        content = render_to_string("schemes/includes/agreement_basis.html", {"scheme_account": account})
        self.assertIn("requires showroom reconciliation", content)

    def candidate_at(self, account, day):
        self.processing_at = instant(day)
        clock = patch("django.utils.timezone.now", return_value=self.processing_at)
        clock.start()
        self.addCleanup(clock.stop)
        return next(c for c in build_scheme_reminder_plan(as_of=day).candidates
            if c.scheme_account.pk == account.pk and c.audience == "CUSTOMER")

    def future_reminders(self):
        """Simulate only the future release boundary, not evidence or eligibility."""
        flag = self.settings(CONFIGURED_PLANS_ENABLED=True)
        flag.enable()
        self.addCleanup(flag.disable)
        ready = patch("schemes.independent_reminders.require_operational_configuration")
        ready.start()
        self.addCleanup(ready.stop)

    def test_duration_reminder_is_gated_revalidated_and_idempotent(self):
        account = self.account(eligibility_policy="CALENDAR", duration_months=1)
        self.cash(account)
        day = account.eligible_from - timedelta(days=7)
        with patch("django.utils.timezone.now", return_value=instant(day)):
            self.assertIsNone(eligibility_reminder_terms(account, as_of=day))
            with self.settings(CONFIGURED_PLANS_ENABLED=True):
                self.assertIsNone(eligibility_reminder_terms(account, as_of=day))
        self.future_reminders()
        candidate = self.candidate_at(account, day)
        before = list(SchemeAccount.objects.values())
        self.assertEqual(deliver_scheme_reminder(candidate).outcome, "SENT")
        self.assertEqual(deliver_scheme_reminder(candidate).outcome, "ALREADY_SENT")
        self.assertEqual(list(SchemeAccount.objects.values()), before)
        self.assertIn("current principal-rule date", mail.outbox[0].body)
        self.assertIn("not settlement approval", mail.outbox[0].body)
        self.assertIn("no metal rate or grams", mail.outbox[0].body)
        self.assertNotIn("becomes eligible for redemption", mail.outbox[0].body)
        with self.settings(CONFIGURED_PLANS_ENABLED=False):
            self.assertEqual(deliver_scheme_reminder(candidate).outcome, "SKIPPED")
        SchemeAccount.objects.filter(pk=account.pk).update(status="CLOSURE_PENDING")
        self.assertEqual(deliver_scheme_reminder(candidate).outcome, "SKIPPED")

    def test_both_count_and_duration_uses_count_not_months_and_rejects_stale(self):
        account = self.account(True, True, required_count=2, eligibility_policy="CALENDAR_AND_COUNT", duration_months=18)
        self.pay(account, 1)
        self.pay(account, 2)
        self.future_reminders()
        day = account.eligible_from - timedelta(days=7)
        candidate = self.candidate_at(account, day)
        self.assertEqual(candidate.kind, "UPCOMING_MONTHLY_COMPLETION")
        self.assertEqual(deliver_scheme_reminder(replace(candidate, event_date=day)).outcome, "SKIPPED")
        self.assertEqual(deliver_scheme_reminder(candidate).outcome, "SENT")
        self.assertIn("All 2 required qualifying payments", mail.outbox[0].body)
        self.assertNotIn("All 18", mail.outbox[0].body)

    def test_count_anytime_missing_count_and_historical_replay_never_forecast(self):
        self.future_reminders()
        for required, options in ((False, {}), (True, dict(required_count=2)),
                (True, dict(required_count=2, eligibility_policy="CALENDAR_AND_COUNT", duration_months=1))):
            account = self.account(required, **options)
            self.cash(account)
            today = self.processing_at.date() if hasattr(self, "processing_at") else instant(account.start_date).date()
            self.assertIsNone(eligibility_reminder_terms(account, as_of=today))
            self.assertIsNone(eligibility_reminder_terms(account, as_of=today - timedelta(days=1)))
        self.assertFalse(SchemeReminder.objects.exists())

    def test_benefit_schedule_notice_does_not_claim_count_or_award(self):
        account = self.account(True, False, **BENEFIT)
        self.pay(account, 1)
        self.future_reminders()
        candidate = self.candidate_at(account, account.eligible_from - timedelta(days=7))
        self.assertEqual(candidate.kind, "UPCOMING_ELIGIBILITY")
        self.assertEqual(deliver_scheme_reminder(candidate).outcome, "SENT")
        self.assertIn("Benefit qualification is separate", mail.outbox[0].body)
        self.assertNotIn("All 2 required qualifying payments are recorded", mail.outbox[0].body)

    def test_new_pending_payment_between_selection_and_dispatch_suppresses_notice(self):
        from decimal import Decimal
        from schemes.services import initiate_razorpay_contribution
        account = self.account(eligibility_policy="CALENDAR", duration_months=1)
        self.cash(account)
        self.future_reminders()
        candidate = self.candidate_at(account, account.eligible_from - timedelta(days=7))
        gateway = entry.IndependentPaymentEntryTests.gateway(self)
        initiate_razorpay_contribution(scheme_account=account, amount=Decimal("500"), gateway=gateway)
        self.assertEqual(deliver_scheme_reminder(candidate).outcome, "SKIPPED")
        self.assertFalse(SchemeReminder.objects.exists())
        self.assertEqual(len(mail.outbox), 0)
