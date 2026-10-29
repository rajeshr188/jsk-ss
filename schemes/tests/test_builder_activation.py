"""Unmocked readiness: published offers through verified collection and full closure."""
import uuid
from datetime import datetime, time
from decimal import Decimal
from itertools import product
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings

from schemes.agreement_eligibility import get_independent_eligibility
from schemes.closures import request_scheme_closure, review_scheme_closure
from schemes.inr_settlements import (preview_independent_inr_settlement, propose_inr_settlement,
    record_inr_fulfilment, complete_inr_settlement)
from schemes.instalments import AGREEMENT_TIMEZONE
from schemes.models import Contribution, MetalGrade, SchemeAccount
from schemes.payments import PaymentOrder
from schemes.plan_governance import plan_edit_digest
from schemes.plan_policies import require_current_payment_workflow
from schemes.plan_publication import set_configured_plan_publication, require_configured_offer
from schemes.selectors import get_outstanding_entitlement
from schemes.services import (enroll_customer, publish_scheme_rate,
    record_in_store_cash_contribution, initiate_razorpay_contribution)
from schemes.settlements import preview_full_settlement, settle_configured_agreement
from schemes.tests.test_audit_exceptions import make_owner, make_customer
from schemes.tests import test_collection_matrix as collection
from schemes.tests.test_collection_matrix import benefit_terms
from schemes.tests.test_independent_plan_drafts import draft
from schemes.tests.test_independent_policy_fields import independent_values, required_values
from schemes.tests.test_independent_instalment_ledger import NOW


@override_settings(CONFIGURED_PLANS_ENABLED=True, IN_STORE_CASH_CONTRIBUTIONS_ENABLED=True,
    PAYMENT_INITIATION_KILL_SWITCH=False, PAYMENT_GATEWAY="razorpay", RAZORPAY_MODE="live",
    RAZORPAY_KEY_ID="rzp_live_synthetic", RAZORPAY_KEY_SECRET="synthetic",
    RAZORPAY_WEBHOOK_SECRET="synthetic", EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class BuilderActivationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner, cls.customer = make_owner(), make_customer()
        cls.grade = MetalGrade.objects.get(code="GOLD_22K_916")

    def values(self, family, metal):
        accumulation = "EXACT_METAL" if metal else "INR_PURCHASE_CREDIT"
        values = independent_values(accumulation=accumulation)
        if family in ("count", "both", "benefit"):
            values = required_values(accumulation=accumulation, required_count=1)
        if family in ("duration", "both", "benefit"):
            values.update(eligibility_policy="CALENDAR_AND_COUNT" if family == "both" else "CALENDAR",
                duration_months=1)
        if family == "benefit":
            values.update(missed_payment_policy="LOSE_UNEARNED_BENEFIT", max_extension_months=None,
                **benefit_terms())
        return values

    def invoice(self):
        return dict(invoice_before_benefit=Decimal("400"), eligible_charges=Decimal("200"),
            invoice_evidence_reference="Synthetic itemised invoice",
            eligible_charge_reference="Synthetic making-charge line")

    def test_all_five_families_both_denominations_and_channels_complete_without_readiness_patches(self):
        # Only time and the external order API are simulated. Real model/service,
        # contract, readiness, source, eligibility and fulfilment checks all execute.
        for family, metal, channel in product(("duration", "anytime", "count", "both", "benefit"),
                (False, True), ("cash", "online")):
            with self.subTest(family=family, metal=metal, channel=channel), patch(
                    "django.utils.timezone.now", return_value=NOW):
                plan = draft(self.owner, self.values(family, metal), [self.grade] if metal else [])
                set_configured_plan_publication(plan_id=plan.pk, publish=True, actor=self.owner,
                    expected_digest=plan_edit_digest(plan), confirmed=True, reason="Accepted synthetic activation")
                plan.refresh_from_db()
                account = enroll_customer(customer=self.customer, plan=plan, metal_grade=self.grade if metal else None,
                    selected_contribution_amount=Decimal("500"), selected_amount_confirmed=True,
                    start_date=NOW.date(), expected_configuration_id=plan.configuration_id,
                    expected_plan_digest=plan_edit_digest(plan), performed_by=self.owner)
                # Pausing new intake does not suspend this agreement's rights.
                with self.settings(CONFIGURED_PLANS_ENABLED=False):
                    with self.assertRaises(ValidationError):
                        require_configured_offer(plan)
                    require_current_payment_workflow(account)
                    rate = publish_scheme_rate(metal_grade=self.grade, rate_per_gram=Decimal("10000"),
                        published_by=self.owner) if metal else None
                    if channel == "cash":
                        contribution = record_in_store_cash_contribution(scheme_account=account, amount=Decimal("500"),
                            expected_scheme_rate_id=rate.pk if rate else None, received_by=self.owner,
                            idempotency_key=uuid.uuid4())
                    else:
                        gateway = Mock(name="Synthetic external API")
                        gateway.name, gateway.mode = "razorpay", "live"
                        gateway.create_order.side_effect = lambda c: PaymentOrder(f"order_{c.pk}", 50000, "INR")
                        contribution = initiate_razorpay_contribution(scheme_account=account, amount=Decimal("500"),
                            gateway=gateway)
                        collection.CollectionMatrixTests.capture(self, contribution)
                        collection.CollectionMatrixTests.capture(self, contribution)
                    self.assertEqual(contribution.status, "PAID")
                    self.assertEqual(get_outstanding_entitlement(account), Decimal("0.050000") if metal else Decimal("500"))
                    eligible_day = account.eligible_from or NOW.date()
                    if family == "both":
                        eligible_day = max(eligible_day, account.instalment_periods.get(number=1).ends_before)
                    at = max(NOW, datetime.combine(eligible_day, time(12), AGREEMENT_TIMEZONE))
                    with patch("django.utils.timezone.now", return_value=at):
                        self.assertTrue(get_independent_eligibility(account).policy_eligible)
                        request = request_scheme_closure(account_id=account.pk, actor=self.customer.user,
                            reason="Synthetic full settlement", idempotency_key=uuid.uuid4())
                        review_scheme_closure(request_id=request.pk, actor=self.owner, action="ACCEPT",
                            reason="Synthetic reviewed customer request", expected_sequence=1, idempotency_key=uuid.uuid4())
                        if metal:
                            invoice = self.invoice() | {"customer_receipt_reference": "Synthetic signed jewellery receipt"}
                            _, token = preview_full_settlement(request_id=request.pk, actor=self.owner,
                                benefit_invoice=invoice if family == "benefit" else None)
                            settle_configured_agreement(request_id=request.pk, actor=self.owner, preview_token=token,
                                invoice_reference="INV-" + uuid.uuid4().hex,
                                authorization_reference="Synthetic approved full quantity", reason="Synthetic actual handover",
                                idempotency_key=uuid.uuid4())
                        else:
                            _, token = preview_independent_inr_settlement(request_id=request.pk, actor=self.owner,
                                invoice_payable=Decimal("390") if family == "benefit" else Decimal("300"),
                                benefit_invoice=self.invoice() if family == "benefit" else None)
                            proposal = propose_inr_settlement(request_id=request.pk, actor=self.owner, preview_token=token,
                                invoice_reference="INV-" + uuid.uuid4().hex, authorization_reference="Synthetic signed final split",
                                reason="Synthetic full disposition", idempotency_key=uuid.uuid4())
                            with self.assertRaises(ValidationError):
                                complete_inr_settlement(proposal_id=proposal.pk, actor=self.owner,
                                    reason="Premature closure must refuse", idempotency_key=uuid.uuid4())
                            record_inr_fulfilment(proposal_id=proposal.pk, actor=self.owner, kind="JEWELLERY", method="SHOWROOM",
                                external_reference=proposal.invoice_reference, customer_receipt_reference="Synthetic jewellery receipt",
                                fulfilled_at=at, reason="Synthetic handover evidence", idempotency_key=uuid.uuid4())
                            for leg in proposal.evidence["refunds"]:
                                self.assertEqual(leg["method"], "CASH_RETURN" if channel == "cash" else "PROVIDER_DASHBOARD")
                                record_inr_fulfilment(proposal_id=proposal.pk, actor=self.owner, kind="REFUND", method=leg["method"],
                                    receipt_id=leg["receipt"], external_reference="REF-" + uuid.uuid4().hex,
                                    customer_receipt_reference="Synthetic original-source refund receipt", fulfilled_at=at,
                                    reason="Synthetic completed source refund", idempotency_key=uuid.uuid4())
                            key = uuid.uuid4()
                            complete_inr_settlement(proposal_id=proposal.pk, actor=self.owner,
                                reason="All actual portions evidenced", idempotency_key=key)
                            complete_inr_settlement(proposal_id=proposal.pk, actor=self.owner,
                                reason="All actual portions evidenced", idempotency_key=key)
                        account.refresh_from_db()
                        self.assertEqual(account.status, "REDEEMED")
                        self.assertEqual(get_outstanding_entitlement(account), 0)
        self.assertEqual(SchemeAccount.objects.count(), 20)
        self.assertEqual(Contribution.objects.count(), 20)

    def test_malformed_encoding_or_denomination_never_acquires_payment_permission(self):
        for schema, mode in ((2, "GOLD"), (1, "INR_CREDIT"), (2, "INR_CREDIT")):
            with self.subTest(schema=schema, mode=mode), self.assertRaises(ValidationError):
                require_current_payment_workflow(SimpleNamespace(agreement_schema_version=schema,
                    savings_mode=mode, configuration_snapshot_id=None))
        plan = draft(self.owner, independent_values(), [self.grade])
        for schema, mode in ((1, "GOLD"), (2, "CASH"), (2, "INR_CREDIT")):
            with self.subTest(schema=schema, mode=mode), self.assertRaises(ValidationError):
                require_current_payment_workflow(SimpleNamespace(agreement_schema_version=schema,
                    savings_mode=mode, configuration_snapshot_id=plan.configuration_id,
                    configuration_snapshot=plan.configuration))
