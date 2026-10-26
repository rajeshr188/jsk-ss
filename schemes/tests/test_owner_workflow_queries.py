"""Local query budgets for retained financial workspaces, never mutation caches."""
from time import perf_counter

from django.core.exceptions import ValidationError
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from schemes.tests.test_benefit_replacement_integration import IntegrationFixture
from schemes.inr_workspace_selectors import inr_owner_workspace
from schemes.inr_settlement_selectors import inr_settlement_balance
from schemes.models import Contribution


@override_settings(IN_STORE_CASH_CONTRIBUTIONS_ENABLED=True, PAYMENT_INITIATION_KILL_SWITCH=False)
class OwnerWorkflowQueryTests(IntegrationFixture, TestCase):
    # Conservative ceilings for these exact fixtures, not release-wide SLAs.
    # Approved/returned ceilings reject the measured duplicate-validation baseline.
    query_budgets = dict(inr_unreviewed=500, inr_approved=1100,
        inr_returned_settlement=340, metal_unreviewed=240, metal_approved=450,
        inr_three_decisions=3000)

    def read_page(self, label, url):
        def no_writes(execute, sql, params, many, context):
            self.assertNotIn(sql.lstrip().split()[0].upper(), {"INSERT", "UPDATE", "DELETE"})
            return execute(sql, params, many, context)
        started = perf_counter()
        with connection.execute_wrapper(no_writes), CaptureQueriesContext(connection) as queries:
            response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("private", response.headers["Cache-Control"])
        print(f"owner_workflow_profile stage={label} queries={len(queries)} seconds={perf_counter() - started:.3f}", flush=True)
        self.assertLessEqual(len(queries), self.query_budgets[label], label)
        return response, len(queries)

    def test_returned_and_approved_review_pages_and_inr_workspace(self):
        self.client.force_login(self.owner)
        for metal in (False, True):
            account, closure, reversal = self.returned_benefit(
                metal=metal, kind="VA_DISCOUNT" if metal else "INR_PURCHASE_BONUS")
            unit = "metal" if metal else "inr"
            url = reverse("schemes:benefit_reapplication", args=[account.scheme_number])
            response, _ = self.read_page(unit + "_unreviewed", url)
            self.assertContains(response, "Not yet reviewed")
            self.approve(account, reversal)
            response, _ = self.read_page(unit + "_approved", url)
            self.assertContains(response, "Approved for replacement review")
            if not metal:
                self.read_page("inr_returned_settlement", reverse("schemes:configured_settlement", args=[closure.pk]))

    def test_repeated_review_and_source_drift_are_reread_without_cross_request_cache(self):
        self.client.force_login(self.owner)
        account, closure, reversal = self.returned_benefit()
        url = reverse("schemes:benefit_reapplication", args=[account.scheme_number])
        self.approve(account, reversal)
        self.decide(self.review_values(account, self.review_preview(account, reversal, "HOLD")))
        self.assertContains(self.client.get(url), "On hold")
        self.approve(account, reversal)
        response, _ = self.read_page("inr_three_decisions", url)
        self.assertContains(response, "Approved for replacement review")
        self.assertEqual(len(response.context["review_rows"][0]["decisions"]), 3)
        before = inr_owner_workspace(closure)["balance"]
        self.assertEqual(before, inr_settlement_balance(account))
        Contribution.objects.filter(scheme_account=account).update(amount=501)
        with self.assertRaises(ValidationError):
            inr_owner_workspace(closure)  # Same Python objects must not imply cached authority.
        with self.assertRaises(ValidationError):
            inr_settlement_balance(account)
        response = self.client.get(url)
        self.assertContains(response, "Investigation required")
        self.assertFalse(response.context["reviewable_returns"].exists())
