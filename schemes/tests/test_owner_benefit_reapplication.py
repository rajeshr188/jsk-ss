"""Owner HTTP review acceptance; real financial services, readiness simulated only."""
import time
import uuid
from unittest.mock import patch

from django.test import Client, TestCase, override_settings
from django.urls import reverse

from schemes.benefit_reapplication_selectors import reapplication_review_status
from schemes.models import (BenefitReapplicationDecision, BenefitInvoiceFulfilment,
    BenefitInvoiceReversal, SchemeBenefitAward, SchemeAccount, Contribution,
    InrPrincipalReceipt, MetalAllocation)
from schemes.tests.test_benefit_awards import future_award_readiness
from schemes.tests.test_benefit_replacement_integration import IntegrationFixture
from schemes.tests.test_audit_exceptions import make_owner


@override_settings(IN_STORE_CASH_CONTRIBUTIONS_ENABLED=True, PAYMENT_INITIATION_KILL_SWITCH=False)
class OwnerBenefitReviewTests(IntegrationFixture, TestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.owner)

    def url(self, a):
        return reverse("schemes:benefit_reapplication", args=[a.scheme_number])

    def preview_http(self, a, reversal, outcome="APPROVE", **changes):
        data = dict(reversal=reversal.pk, outcome=outcome,
            authorization_reference="Fresh signed review " + uuid.uuid4().hex if outcome == "APPROVE" else "") | changes
        return self.client.post(self.url(a), {"operation": "preview"} | {f"review-{k}": v for k, v in data.items()})

    def apply_http(self, a, token, **changes):
        data = dict(preview_token=token, idempotency_key=uuid.uuid4(), reason="Full return and original right checked", confirmed=True) | changes
        return self.client.post(self.url(a), {"operation": "record"} | {f"decision-{k}": v for k, v in data.items()})

    def approve_http(self, a, reversal, outcome="APPROVE"):
        page = self.preview_http(a, reversal, outcome)
        self.assertIn("reviewed", page.context, page.content.decode())
        token = page.context["decision_form"].initial["preview_token"]
        self.assertEqual(self.apply_http(a, token).status_code, 302)
        return token

    def financial_snapshot(self):
        return [list(m.objects.order_by("pk").values()) for m in (SchemeAccount, Contribution,
            InrPrincipalReceipt, MetalAllocation, SchemeBenefitAward, BenefitInvoiceFulfilment, BenefitInvoiceReversal)]

    def test_review_matrix_hold_approval_replay_then_replacement_consumption(self):
        for kind, metal in (("INR_PURCHASE_BONUS", False), ("VA_DISCOUNT", False), ("VA_DISCOUNT", True)):
            a, closure, reversal = self.returned_benefit(kind=kind, metal=metal)
            before = self.financial_snapshot()
            with future_award_readiness():
                preview = self.preview_http(a, reversal)
                self.assertFalse(reversal.reapplication_decisions.exists())
                token = preview.context["decision_form"].initial["preview_token"]
                key = uuid.uuid4()
                self.assertEqual(self.apply_http(a, token, idempotency_key=key,
                    amount="999999", outcome="HOLD").status_code, 302)
                self.assertEqual(reapplication_review_status(reversal), "APPROVED_REVIEW")
                self.approve_http(a, reversal, "HOLD")
                self.assertEqual(self.apply_http(a, token, idempotency_key=key).status_code, 302)
                self.assertEqual(reapplication_review_status(reversal), "HELD")
                self.approve_http(a, reversal)
                self.assertEqual(list(reversal.reapplication_decisions.order_by("sequence").values_list("outcome", flat=True)),
                    ["APPROVE", "HOLD", "APPROVE"])
                self.assertEqual(before, self.financial_snapshot())
                if metal:
                    _, values = self.metal_values(closure)
                    self.settle(values)
                else:
                    self.complete(self.replacement_inr(a, closure, kind))
                page = self.client.get(self.url(a))
                self.assertContains(page, "Used by a replacement invoice")
                self.assertFalse(page.context["reviewable_returns"].exists())
                self.assertTrue(self.preview_http(a, reversal, "HOLD").context["preview_form"].errors)
                self.assertEqual(reversal.reapplication_decisions.count(), 3)

    def test_signed_expired_unconfirmed_and_stale_previews_do_not_record(self):
        a, closure, reversal = self.returned_benefit()
        with future_award_readiness():
            page = self.preview_http(a, reversal)
            token = page.context["decision_form"].initial["preview_token"]
            for submitted, values in ((token + "bad", {}), (token, {"confirmed": False}), (token, {"reason": ""})):
                response = self.apply_http(a, submitted, **values)
                self.assertTrue(response.context["decision_form"].errors)
            with patch("time.time", return_value=time.time() + 601):
                self.assertTrue(self.apply_http(a, token).context["decision_form"].errors)
            self.note(closure)
            self.assertTrue(self.apply_http(a, token).context["decision_form"].errors)
            self.assertFalse(reversal.reapplication_decisions.exists())
            self.approve_http(a, reversal)
            self.note(closure)
            page = self.client.get(self.url(a))
            self.assertContains(page, "Needs a fresh review")

    def test_fresh_authorization_and_hold_shape(self):
        a, _, reversal = self.returned_benefit()
        with future_award_readiness():
            for ref in ("", reversal.customer_confirmation, reversal.fulfilment.customer_receipt_reference):
                page = self.preview_http(a, reversal, authorization_reference=ref)
                self.assertTrue(page.context["preview_form"].errors)
            self.assertTrue(self.preview_http(a, reversal, "HOLD", authorization_reference="Pretend consent").context["preview_form"].errors)
            self.assertTrue(self.preview_http(a, reversal, "UNKNOWN").context["preview_form"].errors)
        self.assertFalse(reversal.reapplication_decisions.exists())

    def test_changed_contract_refuses_owner_preview_and_apply(self):
        a, _, reversal = self.returned_benefit()
        token = self.review_preview(a, reversal)
        type(a).objects.filter(pk=a.pk).update(plan_name_snapshot="Unaccepted changed terms")
        a.plan_name_snapshot = "Unaccepted changed terms"
        for enabled in (False, True):
            with self.settings(CONFIGURED_PLANS_ENABLED=enabled):
                self.assertTrue(self.preview_http(a, reversal).context["preview_form"].errors)
                self.assertTrue(self.apply_http(a, token).context["decision_form"].errors)
        self.assertFalse(reversal.reapplication_decisions.exists())

    def test_owner_account_scope_csrf_no_get_mutation_and_links(self):
        a, closure, reversal = self.returned_benefit()
        other = self.account()
        before = self.financial_snapshot()
        page = self.client.get(self.url(a))
        self.assertContains(page, "Not yet reviewed")
        self.assertIn("no-store", page.headers["Cache-Control"])
        settlement = self.client.get(reverse("schemes:configured_settlement", args=[closure.pk]))
        self.assertContains(settlement, self.url(a))
        self.assertEqual(before, self.financial_snapshot())
        with future_award_readiness():
            self.assertTrue(self.preview_http(other, reversal).context["preview_form"].errors)
            token = self.review_preview(a, reversal)
            self.assertTrue(self.apply_http(other, token).context["decision_form"].errors)
            another_owner = make_owner("second-review-owner@example.com")
            self.client.force_login(another_owner)
            self.assertTrue(self.apply_http(a, token).context["decision_form"].errors)
        self.client.force_login(self.owner)
        csrf = Client(enforce_csrf_checks=True); csrf.force_login(self.owner)
        self.assertEqual(csrf.post(self.url(a), {"operation": "preview"}).status_code, 403)
        self.assertEqual(self.client.post(self.url(a), {"operation": "force"}).status_code, 400)
        self.client.force_login(self.customer.user)
        self.assertEqual(self.client.get(self.url(a)).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(self.url(a)).status_code, 302)

    def test_hold_after_unconsumed_proposal_blocks_handover_and_void_allows_new_review(self):
        a, closure, reversal = self.returned_benefit()
        with future_award_readiness():
            self.approve_http(a, reversal)
            p = self.replacement_inr(a, closure)
            self.approve_http(a, reversal, "HOLD")
            values = self.handover_values(p)
            for key in ("actor", "proposal_id", "kind", "method"):
                values.pop(key)
            values.update(leg="JEWELLERY", confirmed=True)
            response = self.client.post(reverse("schemes:configured_settlement", args=[closure.pk]),
                dict(operation="fulfil", proposal_id=p.pk) | {f"fulfil-{k}": v for k, v in values.items()})
            self.assertTrue(response.context["fulfilment_form"].errors)
            self.assertFalse(p.fulfilments.exists())
            self.correction(p, kind="VOID")
            self.assertContains(self.client.get(self.url(a)), "Needs a fresh review")
            self.approve_http(a, reversal)

    def test_changed_sources_fail_closed_with_retained_history(self):
        a, _, reversal = self.returned_benefit()
        token = self.review_preview(a, reversal)
        Contribution.objects.filter(scheme_account=a).update(amount=501)
        with future_award_readiness():
            page = self.client.get(self.url(a))
            self.assertContains(page, "Investigation required")
            self.assertFalse(page.context["reviewable_returns"].exists())
            self.assertTrue(self.apply_http(a, token).context["decision_form"].errors)
        self.assertFalse(reversal.reapplication_decisions.exists())
