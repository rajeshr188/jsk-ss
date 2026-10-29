"""HTTP journeys use real INR financial services on disposable synthetic contracts."""
import time
import uuid
from decimal import Decimal
from unittest.mock import patch

from django.template.loader import render_to_string
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from schemes.inr_settlement_selectors import inr_settlement_balance
from schemes.models import (BenefitInvoiceFulfilment, BenefitInvoiceReversal, InrSettlementProposal,
    InrSettlementFulfilment, InrSettlementCompletion, InrSettlementResolution, SchemeBenefitAward)
from schemes.tests.test_benefit_awards import future_award_readiness
from schemes.tests.test_independent_inr_settlement import InrClosureFixture
from schemes.tests.test_independent_instalment_ledger import NOW
from schemes.tests.test_independent_instalment_reviews import instant
from schemes.tests.test_inr_corrections import return_evidence


class SettlementStatusPresentationTests(SimpleTestCase):
    """INR display must not imply jewellery-only delivery or premature completion."""

    def closure(self, mode, status):
        from schemes.models import SchemeAccount, SchemeClosureRequest
        return SchemeClosureRequest(
            scheme_account=SchemeAccount(scheme_number="SYNTHETIC-STATUS", savings_mode=mode),
            status=status,
        )

    def test_completed_inr_workspace_and_closure_review_use_inr_label(self):
        closure = self.closure("INR_CREDIT", "SETTLED")
        for template in ("schemes/inr_settlement.html", "schemes/closure_workspace.html"):
            with self.subTest(template=template):
                html = render_to_string(template, {"closure": closure, "target": closure,
                    "scheme_account": closure.scheme_account, "blocked": "Read-only display review"})
                self.assertIn("Full INR settlement completed", html)
                self.assertNotIn("Full jewellery settlement completed", html)

    def test_unfinished_inr_status_never_claims_completion(self):
        for status in ("PENDING", "ACCEPTED", "CANCELLED"):
            with self.subTest(status=status):
                closure = self.closure("INR_CREDIT", status)
                html = render_to_string("schemes/includes/closure_status.html", {"closure": closure})
                self.assertEqual(html.strip(), closure.get_status_display())
                self.assertNotIn("completed", html)

    def test_completed_metal_status_preserves_jewellery_wording(self):
        for mode in ("GOLD", "SILVER"):
            with self.subTest(mode=mode):
                html = render_to_string("schemes/includes/closure_status.html",
                    {"closure": self.closure(mode, "SETTLED")})
                self.assertEqual(html.strip(), "Full jewellery settlement completed")


@override_settings(IN_STORE_CASH_CONTRIBUTIONS_ENABLED=True, PAYMENT_INITIATION_KILL_SWITCH=False)
class OwnerInrSettlementWorkspaceTests(InrClosureFixture, TestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.owner)

    def url(self, closure):
        return reverse("schemes:configured_settlement", args=[closure.pk])

    def post(self, closure, operation, values, *, proposal=None, **extra):
        prefix = "correction" if operation in ("correct", "preview_correction") else operation
        data = {f"{prefix}-{k}": v for k, v in values.items() if v is not None}
        data.update(operation=operation, **extra)
        if proposal:
            data["proposal_id"] = proposal.pk
        return self.client.post(self.url(closure), data)

    def preview_http(self, closure, net="360.00", kind="INR_PURCHASE_BONUS", **changes):
        return self.post(closure, "preview", dict(invoice_payable=net,
            include_benefit=True, **self.invoice(kind)) | changes)

    def propose_http(self, closure, response, **changes):
        data = self.proposal_values(closure, response.context["proposal_form"].initial["preview_token"])
        data.pop("request_id"); data.pop("actor")
        data.update({"confirmed": True} | changes)
        return self.post(closure, "propose", data)

    def fulfil_http(self, closure, proposal, leg="JEWELLERY", **changes):
        data = self.handover_values(proposal)
        for name in ("actor", "proposal_id", "kind", "method"):
            data.pop(name)
        data.update({"leg": leg, "confirmed": True} | changes)
        return self.post(closure, "fulfil", data, proposal=proposal, amount="0.01", method="CASH_RETURN")

    def action(self, **changes):
        return dict(idempotency_key=uuid.uuid4(), reason="Checked actual evidence", confirmed=True) | changes

    def correction_http(self, closure, proposal, rows=(), kind="FULL_RETURN", **changes):
        facts = self.action(kind=kind, authorization_reference="Customer signed complete correction")
        evidence = {f"return-{row['fulfilment_id']}-{key}": value for row in rows
            for key, value in row.items() if key != "fulfilment_id"}
        preview = self.post(closure, "preview_correction", facts, proposal=proposal, **evidence)
        self.assertTrue(preview.context.get("correction_reviewed"), preview.content.decode())
        facts["preview_token"] = preview.context["correction_form"].data["correction-preview_token"]
        evidence.update(changes)
        return self.post(closure, "correct", facts, proposal=proposal, **evidence)

    def test_five_families_bonus_and_va_complete_then_full_return(self):
        for kind, net in (("INR_PURCHASE_BONUS", "360.00"), ("VA_DISCOUNT", "380.00")):
            for family in ("anytime", "duration", "count", "both", "benefit_duration"):
                changes = {}
                if family in ("duration", "benefit_duration"):
                    changes.update(eligibility_policy="CALENDAR", duration_months=1)
                if family == "both":
                    changes.update(eligibility_policy="CALENDAR_AND_COUNT", duration_months=1)
                if family == "benefit_duration":
                    changes.update(missed_payment_policy="LOSE_UNEARNED_BENEFIT", max_extension_months=None,
                        benefit_on_miss="DISQUALIFY_UNEARNED")
                account = self.benefit_account(monthly=family not in ("anytime", "duration"), kind=kind, **changes)
                self.cash(account)
                at = instant(account.eligible_from) if account.eligible_from else NOW
                with patch("django.utils.timezone.now", return_value=at), future_award_readiness():
                    self.client.force_login(self.owner)
                    closure = self.accepted(account)
                    before = [m.objects.count() for m in (SchemeBenefitAward, InrSettlementProposal)]
                    response = self.preview_http(closure, net, kind)
                    self.assertContains(response, "Verified contracted invoice benefit")
                    self.assertEqual([m.objects.count() for m in (SchemeBenefitAward, InrSettlementProposal)], before)
                    key = uuid.uuid4()
                    self.assertEqual(self.propose_http(closure, response, idempotency_key=key,
                        invoice_reference="INV-" + kind + family).status_code, 302)
                    self.assertEqual(self.propose_http(closure, response, idempotency_key=key,
                        invoice_reference="INV-" + kind + family).status_code, 302)
                    p = account.inr_settlements.get()
                    self.assertEqual(inr_settlement_balance(account).outstanding, Decimal("500"))
                    self.assertEqual(self.post(closure, "complete", self.action(), proposal=p).status_code, 200)
                    self.assertFalse(InrSettlementCompletion.objects.filter(proposal=p).exists())
                    fkey = uuid.uuid4()
                    self.assertEqual(self.fulfil_http(closure, p, idempotency_key=fkey).status_code, 302)
                    self.assertEqual(self.fulfil_http(closure, p, idempotency_key=fkey).status_code, 302)
                    self.assertEqual(p.fulfilments.count(), 1)
                    benefit = BenefitInvoiceFulfilment.objects.get(inr_fulfilment__proposal=p)
                    self.assertEqual(benefit.benefit_amount, Decimal("40") if kind == "INR_PURCHASE_BONUS" else Decimal("20"))
                    self.assertEqual(inr_settlement_balance(account).outstanding, Decimal("500") - Decimal(net))
                    self.assertEqual(self.post(closure, "complete", self.action(), proposal=p).status_code, 200)
                    leg = p.evidence["refunds"][0]
                    self.assertEqual(self.fulfil_http(closure, p, leg=f"REFUND:{leg['receipt']}",
                        external_reference="REF-" + uuid.uuid4().hex).status_code, 302)
                    self.assertEqual(self.post(closure, "complete", self.action(), proposal=p).status_code, 302)
                    account.refresh_from_db()
                    self.assertEqual(account.status, "REDEEMED")
                    rows = [return_evidence(f) for f in p.fulfilments.all()]
                    self.assertEqual(self.correction_http(closure, p, rows).status_code, 302)
                    self.assertTrue(BenefitInvoiceReversal.objects.filter(fulfilment=benefit).exists())
                    self.assertEqual(inr_settlement_balance(account).outstanding, Decimal("500"))
                    account.refresh_from_db()
                    self.assertEqual(account.status, "CLOSURE_PENDING")

    def test_real_preview_supports_existing_rights_and_refuses_invalid_signature_or_confirmation(self):
        a = self.benefit_account(); self.cash(a); closure = self.accepted(a)
        with future_award_readiness():
            gated_token_response = self.preview_http(closure)
        for enabled in (False, True):
            with override_settings(CONFIGURED_PLANS_ENABLED=enabled):
                response = self.preview_http(closure)
                self.assertFalse(response.context["preview_form"].errors)
                self.assertIn("split", response.context)
                self.assertEqual(self.propose_http(closure, gated_token_response, preview_token="forged").status_code, 200)
        with future_award_readiness():
            for changes in ({"invoice_payable": "NaN"}, {"invoice_payable": "360.001"},
                    {"eligible_charges": "200"}, {"invoice_evidence_reference": ""}, {"include_benefit": ""}):
                response = self.preview_http(closure, **changes)
                self.assertTrue(response.context["preview_form"].errors)
            response = self.preview_http(closure)
            self.assertEqual(self.propose_http(closure, response, preview_token="forged").status_code, 200)
            self.assertEqual(self.propose_http(closure, response, confirmed=False).status_code, 200)
            with patch("time.time", return_value=time.time() + 700):
                self.assertEqual(self.propose_http(closure, response).status_code, 200)
        self.assertFalse(InrSettlementProposal.objects.exists())

    def test_fresh_form_offers_only_pending_portions_without_breaking_exact_retries(self):
        account, closure, proposal = self.prepared_bonus()
        refund_key = f"REFUND:{proposal.evidence['refunds'][0]['receipt']}"
        page = self.client.get(self.url(closure))
        self.assertEqual(set(dict(page.context['fulfilment_form'].fields['leg'].choices)),
            {'JEWELLERY', refund_key})
        for name in ('proposal_form', 'fulfilment_form', 'correction_form'):
            self.assertEqual(list(page.context[name].fields)[-1], 'confirmed')
        key = uuid.uuid4()
        with future_award_readiness():
            self.assertEqual(self.fulfil_http(closure, proposal, idempotency_key=key).status_code, 302)
            page = self.client.get(self.url(closure))
            choices = dict(page.context['fulfilment_form'].fields['leg'].choices)
            self.assertEqual(set(choices), {refund_key})
            self.assertIn('Principal refund', choices[refund_key])
            self.assertIn('Original cash payment returned', choices[refund_key])
            self.assertNotIn('CASH_RETURN', choices[refund_key])
            self.assertEqual(inr_settlement_balance(account).outstanding, Decimal('140'))
            self.assertEqual(self.fulfil_http(closure, proposal, idempotency_key=key).status_code, 302)
            # A fresh/altered submission cannot pay an already completed portion.
            rejected = self.fulfil_http(closure, proposal)
            self.assertEqual(rejected.status_code, 200)
            self.assertTrue(rejected.context['fulfilment_form'].errors)
            self.assertContains(rejected, 'already recorded; retry only')
            self.assertEqual(proposal.fulfilments.count(), 1)
            self.assertEqual(self.fulfil_http(closure, proposal, leg=refund_key,
                external_reference='REF-' + uuid.uuid4().hex).status_code, 302)
        page = self.client.get(self.url(closure))
        self.assertFalse(list(page.context['fulfilment_form'].fields['leg'].choices))
        self.assertFalse(page.context['remaining'])
        self.assertNotContains(page, 'Record completed fulfilment</button>')
        self.assertContains(page, 'All principal portions have been fulfilled')
        self.assertEqual(inr_settlement_balance(account).outstanding, Decimal('0'))
        self.assertFalse(InrSettlementCompletion.objects.filter(proposal=proposal).exists())

    def test_early_without_benefit_pure_refund_equal_invoice_and_external_top_up(self):
        for invoice in ("0.00", "500.00", "600.00"):
            a = self.benefit_account(monthly=False, eligibility_policy="CALENDAR", duration_months=1)
            self.cash(a); closure = self.accepted(a)
            with future_award_readiness():
                preview = self.post(closure, "preview", {"invoice_payable": invoice})
                self.assertEqual(self.propose_http(closure, preview,
                    invoice_reference="" if invoice == "0.00" else "INV-" + invoice).status_code, 302)
                p = a.inr_settlements.get()
                self.assertEqual(p.basis, "EARLY")
                self.assertFalse(SchemeBenefitAward.objects.filter(scheme_account=a).exists())
                if p.principal_to_invoice:
                    if p.separate_top_up:
                        self.assertEqual(self.fulfil_http(closure, p, top_up_reference="").status_code, 200)
                        self.assertFalse(p.fulfilments.exists())
                    self.assertEqual(self.fulfil_http(closure, p).status_code, 302)
                else:
                    leg = p.evidence["refunds"][0]
                    self.assertEqual(self.fulfil_http(closure, p, leg=f"REFUND:{leg['receipt']}",
                        external_reference="REF-" + uuid.uuid4().hex).status_code, 302)
                self.assertEqual(self.post(closure, "complete", self.action(), proposal=p).status_code, 302)
                self.assertEqual(inr_settlement_balance(a).outstanding, Decimal(0))

    def test_void_has_no_return_rows_and_replacement_needs_fresh_preview(self):
        a, closure, p = self.prepared_bonus()
        with future_award_readiness():
            self.assertEqual(self.correction_http(closure, p, kind="VOID").status_code, 302)
            p.refresh_from_db()
            self.assertTrue(p.retired)
            self.assertEqual(inr_settlement_balance(a).outstanding, Decimal("500"))
            page = self.client.get(self.url(closure))
            self.assertContains(page, "retired by correction")
            self.assertContains(page, "Review the complete split")
            response = self.preview_http(closure)
            self.assertEqual(self.propose_http(closure, response,
                authorization_reference="New authorization after void").status_code, 302)
            self.assertEqual(a.inr_settlements.count(), 2)

    def test_missing_or_edited_full_return_evidence_cannot_restore_principal(self):
        a, closure, p = self.prepared_bonus()
        self.fulfil(self.handover_values(p))
        f = p.fulfilments.get()
        with future_award_readiness():
            facts = self.action(kind="FULL_RETURN", authorization_reference="Signed return")
            response = self.post(closure, "preview_correction", facts, proposal=p)
            self.assertTrue(response.context["return_forms"][0].errors)
            self.assertEqual(self.correction_http(closure, p, [return_evidence(f)],
                **{f"return-{f.pk}-external_reference": "Changed after preview"}).status_code, 200)
        self.assertFalse(InrSettlementResolution.objects.exists())
        self.assertFalse(BenefitInvoiceReversal.objects.exists())
        self.assertEqual(inr_settlement_balance(a).outstanding, Decimal("140"))

    def test_cross_closure_bad_leg_and_missing_actual_evidence_rejected(self):
        a, closure, p = self.prepared_bonus()
        other, other_closure, other_p = self.prepared_bonus()
        with future_award_readiness():
            self.assertEqual(self.post(closure, "complete", self.action(), proposal=other_p).status_code, 404)
            for changes in ({"leg": "REFUND:999999"}, {"customer_receipt_reference": ""},
                    {"confirmed": False}, {"fulfilled_at": "invalid"}, {"external_reference": "WRONG-INVOICE"}):
                self.assertEqual(self.fulfil_http(closure, p, **changes).status_code, 200)
        self.assertFalse(InrSettlementFulfilment.objects.exists())

    def test_owner_only_csrf_private_get_and_no_get_mutation(self):
        a, closure, p = self.prepared_bonus()
        before = (InrSettlementFulfilment.objects.count(), InrSettlementResolution.objects.count())
        page = self.client.get(self.url(closure))
        self.assertContains(page, "INR purchase-credit settlement")
        self.assertIn("no-store", page.headers["Cache-Control"])
        self.assertEqual(before, (InrSettlementFulfilment.objects.count(), InrSettlementResolution.objects.count()))
        csrf = Client(enforce_csrf_checks=True); csrf.force_login(self.owner)
        self.assertEqual(csrf.post(self.url(closure), {"operation": "complete"}).status_code, 403)
        self.assertEqual(self.client.post(self.url(closure), {"operation": "unknown"}).status_code, 400)
        self.client.force_login(self.customer.user)
        self.assertEqual(self.client.get(self.url(closure)).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(self.url(closure)).status_code, 302)

    def test_online_refund_form_keeps_provider_route_and_exact_source_amount(self):
        from schemes.tests.test_collection_matrix import CollectionMatrixTests
        a = self.benefit_account(monthly=False, allow_contributions_after_eligibility=True)
        self.cash(a)
        contribution = self.online(a)
        CollectionMatrixTests.capture(self, contribution)
        closure = self.accepted(a)
        with future_award_readiness():
            preview = self.preview_http(closure, "500.00", invoice_before_benefit="540.00")
            self.assertEqual(self.propose_http(closure, preview).status_code, 302)
            p = a.inr_settlements.get()
            leg = p.evidence["refunds"][0]
            self.assertEqual(leg["method"], "PROVIDER_DASHBOARD")
            # The helper also posts a forged amount and cash method outside the form.
            self.assertEqual(self.fulfil_http(closure, p, leg=f"REFUND:{leg['receipt']}",
                external_reference="Provider completed refund reference").status_code, 302)
            f = p.fulfilments.get()
            self.assertEqual((f.method, f.receipt_id, f.amount),
                ("PROVIDER_DASHBOARD", leg["receipt"], Decimal("500.00")))
            self.assertEqual(inr_settlement_balance(a).outstanding, Decimal("500.00"))
            self.assertFalse(InrSettlementCompletion.objects.exists())

    def test_old_foundation_proof_is_read_only_even_on_a_schema_two_account(self):
        from schemes.tests.test_inr_principal import future_contract, cash_source, record
        from schemes.tests.test_inr_settlements import accepted_request, propose
        a = future_contract(self.owner, self.customer)
        contribution, cash = cash_source(a, self.owner)
        record(self.owner, contribution, cash=cash)
        closure = accepted_request(a, self.owner)
        p = propose(closure, self.owner)
        self.assertEqual(a.agreement_schema_version, 2)
        self.assertNotIn("independent", p.evidence)
        self.assertContains(self.client.get(self.url(closure)), "Existing foundation history is read-only")
        with future_award_readiness():
            self.assertContains(self.fulfil_http(closure, p), "Existing foundation history is read-only")
        self.assertFalse(p.fulfilments.exists())
