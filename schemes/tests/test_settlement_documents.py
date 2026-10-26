"""Documents and privacy use real ledger history without granting new permission."""
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import connection
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.deletion import complete_customer_account_deletion
from accounts.selectors import customer_account_deletion_disposition
from accounts.services import request_authenticated_customer_account_deletion
from accounts.test_deletion_completion import CompletionFixtures
from schemes.models import (BenefitInvoiceFulfilment, Contribution, InrPrincipalReceipt,
    SchemeBenefitAward, InrSettlementProposal, InrSettlementFulfilment, InrFulfilmentReturn,
    InStoreCashContributionReversal)
from schemes.selectors import get_scheme_statement
from schemes.services import create_customer, reverse_in_store_cash_contribution
from schemes.tests.test_benefit_awards import future_award_readiness
from schemes.tests.test_benefit_replacement_integration import IntegrationFixture


@override_settings(IN_STORE_CASH_CONTRIBUTIONS_ENABLED=True, PAYMENT_INITIATION_KILL_SWITCH=False,
    CUSTOMER_ACCOUNT_DELETION_ENABLED=True, CUSTOMER_ACCOUNT_DELETION_POLICY_VERSION="test",
    CONFIGURED_PLANS_ENABLED=False)
class SettlementDocumentTests(IntegrationFixture, TestCase):
    completion_args = CompletionFixtures.completion_args

    def privacy(self):
        return customer_account_deletion_disposition(SimpleNamespace(
            customer=self.customer, requested_email=self.customer.email))

    def read(self, account):
        def forbid_writes(execute, sql, params, many, context):
            self.assertNotIn(sql.lstrip().split()[0].upper(), {"INSERT", "UPDATE", "DELETE"})
            return execute(sql, params, many, context)
        with connection.execute_wrapper(forbid_writes):
            statement = get_scheme_statement(account)
            preview = self.privacy()
        return statement, preview

    def render_statement(self, account):
        self.client.force_login(self.customer.user)
        return self.client.get(reverse("schemes:scheme_statement", args=[account.scheme_number]))

    def test_inr_proposal_handover_refund_and_completion_are_distinct(self):
        a, _, p = self.prepared_bonus()
        statement, preview = self.read(a)
        self.assertEqual(statement.remaining_entitlement, Decimal("500"))
        self.assertEqual(statement.inr_balance.refund_pending, Decimal("140"))
        self.assertEqual(statement.benefit.amount, Decimal("40"))
        self.assertTrue(statement.benefit.pending_right)
        self.assertFalse(statement.benefit.needs_review)
        self.assertFalse(any(e.principal_debit for e in statement.entries))
        self.assertEqual(preview.account_balances[0].purchase_credit_principal, Decimal("500"))
        self.assertEqual(preview.account_balances[0].cash_earned_bonus, 0)
        self.fulfil(self.handover_values(p))
        statement, _ = self.read(a)
        self.assertEqual(statement.remaining_entitlement, Decimal("140"))
        self.assertFalse(statement.benefit.pending_right)
        self.refunds(p)
        self.finish(p)
        statement, preview = self.read(a)
        self.assertEqual(statement.remaining_entitlement, 0)
        self.assertEqual(sum(e.principal_debit or 0 for e in statement.entries), Decimal("500"))
        self.assertEqual(preview.financial_exceptions, 0)
        response = self.render_statement(a)
        for text in ("Outstanding INR purchase-credit principal", "Purchase benefit history", "Principal refund recorded"):
            self.assertContains(response, text)
        self.assertNotContains(response, p.authorization_reference)
        self.assertNotContains(response, "No bonus or discount is included")
        self.assertNotContains(response, "None months")
        self.assertIn("no-store", response.headers["Cache-Control"])

    def test_full_return_and_reapplication_preserve_gross_history_and_net_principal(self):
        a, r, reversal = self.returned_benefit()
        statement, preview = self.read(a)
        self.assertEqual(statement.remaining_entitlement, Decimal("500"))
        self.assertTrue(statement.benefit.pending_right)
        self.assertEqual(dict((name, count) for name, count, _ in preview.inventory)["Benefit invoice reversals"], 1)
        self.approve(a, reversal)
        p = self.replacement_inr(a, r)
        self.complete(p)
        statement, preview = self.read(a)
        self.assertEqual(statement.remaining_entitlement, 0)
        self.assertFalse(statement.benefit.needs_review)
        self.assertEqual(sum(e.principal_credit or 0 for e in statement.entries), Decimal("1000"))
        self.assertEqual(sum(e.principal_debit or 0 for e in statement.entries), Decimal("1000"))
        self.assertEqual(sum(e.description == "Benefit applied to invoice" for e in statement.benefit.entries), 2)
        self.assertEqual(sum(e.description == "Benefit invoice fully reversed" for e in statement.benefit.entries), 1)
        self.assertFalse(preview.account_balances[0].benefit_pending)
        self.assertContains(self.render_statement(a), "Replaces BEN-INV-")

    def test_metal_va_is_separate_from_exact_grade_balance(self):
        a, _, _ = self.returned_benefit(kind="VA_DISCOUNT", metal=True)
        statement, preview = self.read(a)
        self.assertEqual(statement.remaining_entitlement, Decimal("0.050000"))
        self.assertIsNone(statement.inr_balance)
        self.assertIsNone(statement.benefit.amount)
        self.assertEqual(statement.benefit.percentage, Decimal("10"))
        self.assertEqual(preview.account_balances[0].purchase_credit_principal, 0)
        self.assertEqual(preview.account_balances[0].metal_quantity, Decimal("0.050000"))
        response = self.render_statement(a)
        self.assertContains(response, "Invoice VA discount right")
        self.assertNotContains(response, "No bonus or discount is included")

    def test_receipt_access_and_invalid_principal_never_report_zero(self):
        a = self.account()
        c = self.cash(a)
        self.client.force_login(self.customer.user)
        receipt_url = reverse("schemes:contribution_receipt", args=[c.pk])
        response = self.client.get(receipt_url)
        self.assertContains(response, "INR purchase-credit principal")
        self.assertNotContains(response, "metal allocation is pending")
        stranger = create_customer(full_name="Other", email="document-other@example.com", mobile_number="9000000088")
        self.client.force_login(stranger.user)
        self.assertEqual(self.client.get(receipt_url).status_code, 404)
        self.assertEqual(self.client.get(reverse("schemes:scheme_statement", args=[a.scheme_number])).status_code, 404)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(receipt_url).status_code, 200)
        Contribution.objects.filter(pk=c.pk).update(amount=Decimal("501"))
        self.assertEqual(self.client.get(receipt_url).status_code, 409)
        self.assertEqual(self.client.get(reverse("schemes:scheme_statement", args=[a.scheme_number])).status_code, 409)
        preview = self.privacy()
        self.assertIsNone(preview.account_balances[0].purchase_credit_principal)
        self.assertGreater(preview.financial_exceptions, 0)

    def test_privacy_completion_preserves_all_financial_rows_and_open_identity(self):
        a, _, p = self.prepared_bonus()
        request = request_authenticated_customer_account_deletion(user=self.customer.user, source_ip="203.0.113.8")
        with self.assertRaisesMessage(ValidationError, "Keep the showroom name and email"):
            complete_customer_account_deletion(**self.completion_args(request))
        models = (Contribution, InrPrincipalReceipt, SchemeBenefitAward, InrSettlementProposal,
            InrSettlementFulfilment, InrFulfilmentReturn, BenefitInvoiceFulfilment)
        before = [list(m.objects.values()) for m in models]
        complete_customer_account_deletion(**self.completion_args(request, ("full_name", "email")))
        self.assertEqual(before, [list(m.objects.values()) for m in models])
        self.customer.refresh_from_db()
        self.assertNotEqual(self.customer.email.split("@")[1], "deleted.invalid")
        statement, preview = self.read(a)
        self.assertEqual(statement.remaining_entitlement, Decimal("500"))
        self.assertTrue(preview.account_balances[0].benefit_pending)

    def test_invalid_benefit_blocks_privacy_completion_even_with_zero_principal(self):
        a, _, p = self.prepared_bonus()
        self.complete(p)
        request = request_authenticated_customer_account_deletion(user=self.customer.user, source_ip="203.0.113.8")
        SchemeBenefitAward.objects.filter(scheme_account=a).update(evidence_digest="0" * 64)
        self.assertGreater(self.privacy().financial_exceptions, 0)
        with self.assertRaisesMessage(ValidationError, "Financial exceptions"):
            complete_customer_account_deletion(**self.completion_args(request, ("full_name", "email")))

    def test_settled_privacy_minimization_retains_financial_history_and_readability(self):
        a, _, p = self.prepared_bonus()
        self.complete(p)
        request = request_authenticated_customer_account_deletion(user=self.customer.user, source_ip="203.0.113.8")
        models = (Contribution, InrPrincipalReceipt, SchemeBenefitAward, InrSettlementProposal,
            InrSettlementFulfilment, BenefitInvoiceFulfilment)
        before = [list(m.objects.values()) for m in models]
        complete_customer_account_deletion(**self.completion_args(request))
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.email.split("@")[1], "deleted.invalid")
        self.assertEqual(before, [list(m.objects.values()) for m in models])
        statement, preview = self.read(a)
        self.assertEqual(statement.remaining_entitlement, 0)
        self.assertFalse(statement.benefit.pending_right)
        self.assertEqual(preview.financial_exceptions, 0)

    def test_cash_receipt_correction_remains_a_separate_principal_event(self):
        a = self.account()
        c = self.cash(a)
        with future_award_readiness(), patch.object(
                InStoreCashContributionReversal._meta.get_field("reversed_at"), "_get_default", lambda: timezone.now()):
            reverse_in_store_cash_contribution(contribution=c, processed_by=self.owner,
                reason_code="WRONG_AMOUNT", reason="Evidenced full cash-entry error")
        statement, _ = self.read(a)
        self.assertEqual(statement.remaining_entitlement, 0)
        self.assertEqual([e.principal_credit for e in statement.entries if e.principal_credit is not None], [Decimal("500")])
        self.assertEqual([e.principal_debit for e in statement.entries if e.principal_debit is not None], [Decimal("500")])
        self.client.force_login(self.customer.user)
        response = self.client.get(reverse("schemes:contribution_receipt", args=[c.pk]))
        self.assertContains(response, "Reversed financial record")
        self.assertContains(response, "INR purchase-credit principal")
