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
from schemes.benefit_reapplication_selectors import (
    _OwnerHistoryRead, decision_history, owner_reapplication_workspace,
    reapplication_review_status, return_basis,
)
from schemes.benefit_application_selectors import validate_bound_review


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

    def test_workspace_decision_reads_do_not_survive_a_new_invocation(self):
        account, closure, reversal = self.returned_benefit()
        decision = self.approve(account, reversal)
        first = owner_reapplication_workspace(account)
        self.assertEqual(first['review_rows'][0]['status'], 'APPROVED_REVIEW')
        # Simulate retained-decision damage only in the disposable test database.
        reversal.reapplication_decisions.filter(pk=decision.pk).update(
            authorization_reference='Changed retained customer consent')
        later = owner_reapplication_workspace(account)  # Same account instance.
        self.assertEqual(later['review_rows'][0]['status'], 'REVIEW_REQUIRED')
        self.assertFalse(later['reviewable_returns'].exists())
        with self.assertRaises(ValidationError):
            reapplication_review_status(reversal)

    def test_current_binding_ignores_historical_read_reuse_after_a_hold(self):
        account, closure, reversal = self.returned_benefit()
        self.approve(account, reversal)
        proposal = self.replacement_inr(account, closure)
        history_read = _OwnerHistoryRead(account)
        old_rows = decision_history(reversal, _history_read=history_read)
        self.assertEqual(old_rows[-1].outcome, 'APPROVE')
        validate_bound_review(proposal, current=True)
        self.decide(self.review_values(account, self.review_preview(account, reversal, 'HOLD')))
        # Even accidentally supplying this old read must not authorize spending.
        with self.assertRaises(ValidationError):
            validate_bound_review(proposal, current=True, _history_read=history_read)
        self.assertFalse(proposal.fulfilments.exists())

    def test_current_return_basis_reloads_closure_and_disposition_after_historical_read(self):
        account, closure, reversal = self.returned_benefit()
        decision = self.approve(account, reversal)
        history_read = _OwnerHistoryRead(account)
        decision_history(reversal, _history_read=history_read)
        self.note(closure)
        basis = return_basis(reversal, current=True, _history_read=history_read)
        self.assertGreater(basis['closure_sequence'], decision.evidence['basis']['closure_sequence'])
        self.assertEqual(owner_reapplication_workspace(account)['review_rows'][0]['status'], 'STALE')
        # Simulate damaged historical principal proof in this disposable database.
        # Neither a retained read object nor the same account instance can hide it.
        account.inr_settlements.update(evidence_digest='damaged-retained-proof')
        with self.assertRaises(ValidationError):
            return_basis(reversal, current=True, _history_read=history_read)
        later = owner_reapplication_workspace(account)
        self.assertEqual(later['review_rows'][0]['status'], 'REVIEW_REQUIRED')
        self.assertFalse(later['reviewable_returns'].exists())
