"""HTTP acceptance uses real settlement services, with readiness simulated only in tests."""
import time
import uuid
from decimal import Decimal
from unittest.mock import patch

from django.test import Client, TestCase, override_settings
from django.urls import reverse

from schemes.models import (BenefitInvoiceFulfilment, BenefitInvoiceReversal,
    ConfiguredSettlement, InrSettlementProposal, Redemption, SchemeBenefitAward)
from schemes.selectors import get_metal_balance
from schemes.tests.test_benefit_awards import future_award_readiness
from schemes.tests.test_independent_instalment_ledger import NOW
from schemes.tests.test_independent_instalment_reviews import instant
from schemes.tests.test_independent_metal_settlement import MetalClosureFixture


@override_settings(IN_STORE_CASH_CONTRIBUTIONS_ENABLED=True, PAYMENT_INITIATION_KILL_SWITCH=False)
class OwnerSettlementWorkspaceTests(MetalClosureFixture, TestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.owner)

    def url(self, closure):
        return reverse("schemes:configured_settlement", args=[closure.pk])

    def preview_http(self, closure, **changes):
        return self.client.post(self.url(closure), dict(operation="preview", include_benefit=True,
            **self.invoice()) | changes)

    def apply_http(self, closure, token, **changes):
        data = self.settlement_values(closure, token)
        data.pop("actor"); data.pop("request_id")
        return self.client.post(self.url(closure), data | {"confirmed": True} | changes)

    def test_five_families_preview_settle_and_full_return_through_owner_forms(self):
        for family in ("anytime", "duration", "count", "both", "benefit_duration"):
            changes = {}
            if family in ("duration", "benefit_duration"):
                changes.update(eligibility_policy="CALENDAR", duration_months=1)
            if family == "both":
                changes.update(eligibility_policy="CALENDAR_AND_COUNT", duration_months=1)
            if family == "benefit_duration":
                changes.update(missed_payment_policy="LOSE_UNEARNED_BENEFIT", max_extension_months=None,
                    benefit_on_miss="DISQUALIFY_UNEARNED")
            account = self.benefit_account(monthly=family in ("count", "both", "benefit_duration"),
                metal=True, kind="VA_DISCOUNT", **changes)
            self.cash(account)
            at = instant(account.eligible_from) if account.eligible_from else NOW
            with patch("django.utils.timezone.now", return_value=at), future_award_readiness():
                self.client.force_login(self.owner)
                closure = self.accepted(account)
                balance = get_metal_balance(account)
                counts = [m.objects.count() for m in (Redemption, SchemeBenefitAward, BenefitInvoiceFulfilment)]
                response = self.preview_http(closure)
                self.assertContains(response, "Contracted discount (INR)")
                self.assertEqual([m.objects.count() for m in (Redemption, SchemeBenefitAward, BenefitInvoiceFulfilment)], counts)
                token = response.context["form"].initial["preview_token"]
                key = uuid.uuid4()
                result = self.apply_http(closure, token, idempotency_key=key, invoice_reference="INV-" + family,
                    benefit_amount="999999", gold_quantity="0.001")
                self.assertEqual(result.status_code, 302)
                settlement = closure.settlements.get()
                self.assertEqual(settlement.redemption.gold_quantity, balance)
                self.assertEqual(settlement.benefitinvoicefulfilment.benefit_amount, Decimal("20.00"))
                self.assertEqual(self.apply_http(closure, token, idempotency_key=key,
                    invoice_reference="INV-" + family).status_code, 302)
                self.assertEqual(closure.settlements.count(), 1)
                page = self.client.get(self.url(closure))
                self.assertContains(page, 'name="invoice_correction_reference"')
                reversal = dict(operation="reverse", settlement_id=settlement.pk, expected_sequence=3,
                    idempotency_key=uuid.uuid4(), reason="Actual full goods return",
                    authorization_reference="Signed correction", confirmed=True)
                self.assertEqual(self.client.post(self.url(closure), reversal).status_code, 200)
                self.assertFalse(hasattr(settlement.redemption, "reversal"))
                reversal.update(invoice_correction_reference="COR-" + family, customer_confirmation="Signed full return",
                    returned_at=at.isoformat())
                self.assertEqual(self.client.post(self.url(closure), reversal).status_code, 302)
                self.assertEqual(get_metal_balance(account), balance)
                self.assertTrue(BenefitInvoiceReversal.objects.filter(fulfilment__metal_settlement=settlement).exists())
                account.refresh_from_db()
                self.assertEqual(account.status, "CLOSURE_PENDING")

    def test_invalid_invoice_tampered_expired_or_unconfirmed_preview_cannot_settle(self):
        account = self.benefit_account(metal=True, kind="VA_DISCOUNT")
        self.cash(account)
        closure = self.accepted(account)
        with future_award_readiness():
            for changes in ({"invoice_before_benefit": "NaN"}, {"eligible_charges": "200.001"},
                    {"customer_receipt_reference": ""}, {"include_benefit": ""}):
                response = self.preview_http(closure, **changes)
                self.assertTrue(response.context["invoice_form"].errors)
                self.assertIsNone(response.context["evidence"])
            response = self.preview_http(closure)
            token = response.context["form"].initial["preview_token"]
            self.assertEqual(self.apply_http(closure, token + "invalid").status_code, 200)
            self.assertEqual(self.apply_http(closure, token, confirmed="").status_code, 200)
            with patch("django.core.signing.time.time", return_value=time.time() + 601):
                self.assertEqual(self.apply_http(closure, token).status_code, 200)
        self.assertFalse(Redemption.objects.exists())
        self.assertFalse(SchemeBenefitAward.objects.exists())

    def test_gate_permission_csrf_and_unknown_operation_remain_closed(self):
        account = self.benefit_account(metal=True, kind="VA_DISCOUNT")
        self.cash(account); closure = self.accepted(account)
        with future_award_readiness():
            token = self.preview_http(closure).context["form"].initial["preview_token"]
        for enabled in (False, True):
            with self.settings(CONFIGURED_PLANS_ENABLED=enabled):
                self.assertEqual(self.apply_http(closure, token).status_code, 200)
                self.assertIsNone(self.preview_http(closure).context["evidence"])
        self.assertFalse(Redemption.objects.exists())
        self.assertEqual(self.client.post(self.url(closure), {"operation": "force"}).status_code, 400)
        self.assertIn("no-store", self.client.get(self.url(closure))["Cache-Control"])
        csrf = Client(enforce_csrf_checks=True); csrf.force_login(self.owner)
        self.assertEqual(csrf.post(self.url(closure), {"operation": "preview"}).status_code, 403)
        self.client.force_login(self.customer.user)
        self.assertEqual(self.client.get(self.url(closure)).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(self.url(closure)).status_code, 302)

    def test_inr_never_uses_the_metal_form_or_mutation_service(self):
        account = self.benefit_account(metal=False)
        self.cash(account); closure = self.accepted(account)
        before = (Redemption.objects.count(), InrSettlementProposal.objects.count())
        with patch("schemes.settlement_views.preview_full_settlement", side_effect=AssertionError("Wrong denomination")), \
                patch("schemes.settlement_views.settle_configured_agreement", side_effect=AssertionError("Wrong denomination")):
            response = self.client.get(self.url(closure))
            self.assertContains(response, "INR purchase-credit settlement")
            self.assertNotContains(response, 'name="preview_token"')
            self.assertEqual(self.client.post(self.url(closure), {"confirmed": True}).status_code, 400)
        self.assertEqual((Redemption.objects.count(), InrSettlementProposal.objects.count()), before)

    def test_early_unearned_benefit_can_be_omitted_but_qualified_right_cannot(self):
        for early in (True, False):
            account = self.benefit_account(monthly=False, metal=True, kind="VA_DISCOUNT", eligibility_policy="CALENDAR", duration_months=1)
            self.cash(account)
            with patch("django.utils.timezone.now", return_value=NOW if early else instant(account.eligible_from)), future_award_readiness():
                self.client.force_login(self.owner)
                closure = self.accepted(account)
                response = self.client.get(self.url(closure))
                if not early:
                    self.assertIsNone(response.context["evidence"])
                    continue
                token = response.context["form"].initial["preview_token"]
                self.assertEqual(self.apply_http(closure, token).status_code, 302)
                self.assertFalse(SchemeBenefitAward.objects.filter(scheme_account=account).exists())
