"""Invoice foundation on synthetic future dispositions, not settlement activation.

Principal disposition fixtures use real retained-proof validators. Only the
unreleased operational gate is simulated; no financial validator is mocked.
"""
import importlib
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from io import StringIO
from threading import Barrier
from unittest.mock import patch

from django.apps import apps
from django.core.exceptions import ValidationError
from django.core.management import call_command, CommandError
from django.db import connection, connections, IntegrityError, transaction
from django.test import TestCase, TransactionTestCase, override_settings
from django.test.utils import CaptureQueriesContext

from schemes.benefit_fulfilments import (preview_benefit_fulfilment, record_benefit_fulfilment,
    reverse_benefit_fulfilment)
from schemes.benefit_fulfilment_selectors import (get_benefit_invoice_status,
    validate_benefit_fulfilment, validate_benefit_reversal)
from schemes.inr_principal import calculate_inr_final_settlement
from schemes.inr_settlement_selectors import inr_payment_source_evidence, refund_legs
from schemes.inr_correction_selectors import disposition_snapshot, return_facts, validate_inr_resolution
from schemes.models import (BenefitInvoiceFulfilment, BenefitInvoiceReversal, Contribution,
    InrPrincipalReceipt, MetalAllocation, InrSettlementProposal, InrSettlementFulfilment,
    InrSettlementResolution, InrFulfilmentReturn, SchemeAccount, SchemeClosureRequest,
    SchemeClosureEvent, ConfiguredSettlement, ConfiguredSettlementReversal, Redemption, RedemptionReversal)
from schemes.settlement_selectors import proof_digest, validate_configured_settlement
from schemes.tests.test_benefit_awards import AwardFixture, future_award_readiness
from schemes.tests.test_independent_instalment_ledger import NOW
from schemes.tests.test_inr_settlements import accepted_request


class InvoiceFixture(AwardFixture):
    def disposition(self, kind="INR_PURCHASE_BONUS", metal=False):
        account = self.benefit_account(kind=kind, metal=metal)
        c = self.cash(account)
        award = self.record(account, self.preview(account))
        closure = accepted_request(account, self.owner)
        reference = "INV-" + uuid.uuid4().hex
        if metal:
            key = uuid.uuid4()
            r = Redemption.objects.create(scheme_account=account, redemption_number=uuid.uuid4().hex[:24],
                settlement_type="JEWELLERY_PURCHASE", gold_quantity=c.metal_allocation.quantity,
                metal_grade=account.metal_grade, processed_by=self.owner, notes="Full handover",
                external_reference=reference, idempotency_key=key, completed_at=NOW)
            event = SchemeClosureEvent.objects.create(request=closure, sequence=3, action="SETTLE",
                resulting_status="SETTLED", actor=self.owner, actor_label="Owner", reason=r.notes,
                authorization_reference="Signed invoice", idempotency_key=key, created_at=NOW)
            evidence = dict(version=1, account=account.pk, configuration=account.configuration_snapshot_id,
                closure=str(closure.pk), sequence=2, grade=account.metal_grade_id, basis="NORMAL",
                quantity=format(r.entitlement_amount, ".6f"),
                payments=[dict(id=p["pk"], status=p["status"], amount=p["amount"],
                    allocation=p["metal_allocation__pk"], grams=p["metal_allocation__quantity"],
                    grade=account.metal_grade_id, rate=p["scheme_rate_id"], order=p["gateway_order_id"],
                    payment=p["gateway_reference"], reversal=p["cash_reversal__pk"])
                    for p in award.evidence["payments"]])
            source = ConfiguredSettlement.objects.create(closure=closure, event=event, redemption=r,
                basis="NORMAL", authorization_reference=event.authorization_reference,
                evidence=evidence, evidence_digest=proof_digest(evidence))
            validate_configured_settlement(source)
            SchemeClosureRequest.objects.filter(pk=closure.pk).update(status="SETTLED")
            SchemeAccount.objects.filter(pk=account.pk).update(status="REDEEMED")
        else:
            sources = inr_payment_source_evidence(account)
            # Bonus 40; VA discount on 200 eligible charges is 20. Gross invoice 600.
            net = Decimal("560.00") if kind == "INR_PURCHASE_BONUS" else Decimal("580.00")
            split = calculate_inr_final_settlement(principal=Decimal("500.00"), invoice_payable=net)
            evidence = dict(version=1, closure=str(closure.pk), sequence=2, sources=sources,
                basis="NORMAL", invoice_payable=str(net), refunds=refund_legs(sources, split.principal_to_invoice))
            p = InrSettlementProposal.objects.create(scheme_account=account, closure=closure,
                principal=Decimal("500.00"), invoice_payable=net, principal_to_invoice=split.principal_to_invoice,
                principal_refund=split.principal_refund, separate_top_up=split.separate_top_up,
                invoice_reference=reference, authorization_reference="Signed exact split", basis="NORMAL",
                evidence=evidence, evidence_digest=proof_digest(evidence), recorded_by=self.owner,
                actor_label="Owner", reason="Synthetic future disposition", idempotency_key=uuid.uuid4(), recorded_at=NOW)
            source = InrSettlementFulfilment.objects.create(proposal=p, kind="JEWELLERY", amount=p.principal_to_invoice,
                method="SHOWROOM", external_reference=reference, customer_receipt_reference="Signed handover",
                top_up_reference="External topup", fulfilled_at=NOW, recorded_by=self.owner, actor_label="Owner",
                reason="Actual jewellery handed over", idempotency_key=uuid.uuid4(), recorded_at=NOW)
            SchemeAccount.objects.filter(pk=account.pk).update(status="CLOSURE_PENDING")
        return account, award, source

    def invoice(self, account, award, source, **changes):
        values = dict(account_id=account.pk, award_id=award.pk, actor=self.owner,
            invoice_before_benefit=Decimal("600.00"), eligible_charges=Decimal("200.00") if award.kind == "VA_DISCOUNT" else None,
            eligible_charge_reference="Making charge line" if award.kind == "VA_DISCOUNT" else "",
            invoice_evidence_reference="Retained itemised invoice", customer_receipt_reference="Signed handover",
            **({"inr_fulfilment_id": source.pk} if isinstance(source, InrSettlementFulfilment) else {"metal_settlement_id": source.pk}))
        with future_award_readiness():
            return preview_benefit_fulfilment(**(values | changes))

    def consume(self, account, token, **changes):
        with future_award_readiness():
            return record_benefit_fulfilment(**(dict(account_id=account.pk, actor=self.owner,
                preview_token=token, reason="Recorded actual invoice benefit", idempotency_key=uuid.uuid4()) | changes))

    def returned(self, f):
        if f.inr_fulfilment_id:
            p = f.inr_fulfilment.proposal
            event = SchemeClosureEvent.objects.create(request=p.closure, sequence=3, action="NOTE",
                resulting_status="ACCEPTED", actor=self.owner, actor_label="Owner", reason="Full physical return",
                authorization_reference="Signed return", idempotency_key=uuid.uuid4(), created_at=NOW)
            row = InrFulfilmentReturn(fulfilment=f.inr_fulfilment, amount=f.inr_fulfilment.amount,
                method="GOODS_RETURN", external_reference=uuid.uuid4().hex, customer_confirmation="Signed return",
                invoice_correction_reference="Corrected invoice", top_up_refund_reference="Topup returned", returned_at=NOW)
            evidence = dict(version=1, kind="FULL_RETURN", snapshot=disposition_snapshot(p), sequence=2,
                returns=[return_facts(row)])
            resolution = InrSettlementResolution.objects.create(proposal=p, event=event, kind="FULL_RETURN",
                evidence=evidence, evidence_digest=proof_digest(evidence))
            row.resolution = resolution
            row.save()
            validate_inr_resolution(resolution)
            InrSettlementProposal.objects.filter(pk=p.pk).update(retired=True)
            return {"inr_return_id": row.pk}
        s = f.metal_settlement
        r = RedemptionReversal.objects.create(redemption=s.redemption, reversal_number=uuid.uuid4().hex[:24],
            processed_by=self.owner, reason="Full physical return", reversed_at=NOW)
        event = SchemeClosureEvent.objects.create(request=s.closure, sequence=4, action="REVERSE",
            resulting_status="ACCEPTED", actor=self.owner, actor_label="Owner", reason=r.reason,
            authorization_reference="Signed return", idempotency_key=uuid.uuid4(), created_at=NOW)
        correction = ConfiguredSettlementReversal.objects.create(settlement=s, event=event, reversal=r)
        SchemeClosureRequest.objects.filter(pk=s.closure_id).update(status="ACCEPTED")
        SchemeAccount.objects.filter(pk=f.award.scheme_account_id).update(status="CLOSURE_PENDING")
        return {"metal_reversal_id": correction.pk}

    def reverse(self, f, source, **changes):
        with future_award_readiness():
            return reverse_benefit_fulfilment(**(dict(account_id=f.award.scheme_account_id, fulfilment_id=f.pk,
                actor=self.owner, reason="Recorded actual full return", idempotency_key=uuid.uuid4(),
                invoice_correction_reference="Corrected invoice", customer_confirmation="Signed return",
                returned_at=NOW) | source | changes))


@override_settings(IN_STORE_CASH_CONTRIBUTIONS_ENABLED=True, PAYMENT_INITIATION_KILL_SWITCH=False)
class BenefitInvoiceTests(InvoiceFixture, TestCase):
    def test_supported_benefit_matrix_preserves_principal_and_retains_one_invoice(self):
        for kind, metal in (("INR_PURCHASE_BONUS", False), ("VA_DISCOUNT", False), ("VA_DISCOUNT", True)):
            a, award, source = self.disposition(kind, metal)
            before = [list(m.objects.values()) for m in (Contribution, InrPrincipalReceipt, MetalAllocation, SchemeAccount)]
            token, key = self.invoice(a, award, source), uuid.uuid4()
            f = self.consume(a, token, idempotency_key=key)
            f.refresh_from_db()
            validate_benefit_fulfilment(f, current=True)
            self.assertEqual(f.benefit_amount, 40 if kind == "INR_PURCHASE_BONUS" else 20)
            self.assertEqual(f.invoice_before_benefit, f.benefit_amount + f.invoice_after_benefit)
            self.assertFalse(get_benefit_invoice_status(award).needs_review)
            self.assertEqual(self.consume(a, token, idempotency_key=key).pk, f.pk)
            with self.assertRaises(ValidationError):
                self.consume(a, token)
            self.assertEqual(before, [list(m.objects.values()) for m in (Contribution, InrPrincipalReceipt, MetalAllocation, SchemeAccount)])
        output = StringIO()
        call_command("check_benefit_awards", stdout=output)
        self.assertIn("invoice_fulfilments=3", output.getvalue())

    def test_actual_full_return_preserves_original_and_never_reopens_award(self):
        for kind, metal in (("INR_PURCHASE_BONUS", False), ("VA_DISCOUNT", False), ("VA_DISCOUNT", True)):
            a, award, source = self.disposition(kind, metal)
            token = self.invoice(a, award, source)
            f = self.consume(a, token)
            before = BenefitInvoiceFulfilment.objects.values().get(pk=f.pk)
            actual_return = self.returned(f)
            key = uuid.uuid4()
            for changes in (dict(returned_at=NOW + timedelta(days=1)), dict(customer_confirmation=""),
                            dict(actor=self.customer.user)):
                with self.assertRaises(ValidationError):
                    self.reverse(f, actual_return, **changes)
            r = self.reverse(f, actual_return, idempotency_key=key)
            r.refresh_from_db()
            validate_benefit_reversal(r)
            self.assertEqual(self.reverse(f, actual_return, idempotency_key=key).pk, r.pk)
            self.assertEqual(r.amount, f.benefit_amount)
            self.assertEqual(before, BenefitInvoiceFulfilment.objects.values().get(pk=f.pk))
            self.assertTrue(get_benefit_invoice_status(award).needs_review)
            with self.assertRaises(ValidationError):
                self.consume(a, token)
            with self.assertRaises(ValidationError):
                self.reverse(f, actual_return)
        with self.assertRaises(CommandError):
            call_command("check_benefit_awards", stdout=StringIO())

    def test_invalid_invoice_amounts_evidence_and_wrong_handover_block(self):
        a, award, source = self.disposition()
        for changes in (dict(invoice_before_benefit=Decimal("30")), dict(invoice_before_benefit=600.0),
                dict(invoice_before_benefit=Decimal("600.001")), dict(invoice_before_benefit=Decimal("NaN")),
                dict(eligible_charges=Decimal("10")), dict(eligible_charge_reference="unexpected"),
                dict(customer_receipt_reference="different receipt"), dict(invoice_evidence_reference=""),
                dict(inr_fulfilment_id=None), dict(invoice_before_benefit=Decimal("700"))):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                self.invoice(a, award, source, **changes)
        other, other_award, other_source = self.disposition()
        with self.assertRaises(ValidationError):
            self.invoice(a, award, other_source)
        a, award, source = self.disposition("VA_DISCOUNT", True)
        for changes in (dict(eligible_charges=None), dict(eligible_charges=Decimal("700")),
                        dict(eligible_charge_reference="")):
            with self.assertRaises(ValidationError):
                self.invoice(a, award, source, **changes)
        self.assertFalse(BenefitInvoiceFulfilment.objects.exists())

    def test_preview_authority_expiry_idempotency_and_source_drift(self):
        a, award, source = self.disposition()
        token, key = self.invoice(a, award, source), uuid.uuid4()
        for changes in (dict(preview_token=token + "bad"), dict(actor=self.customer.user)):
            with self.assertRaises(ValidationError):
                self.consume(a, token, **changes)
        with patch("django.core.signing.time.time", return_value=time.time() + 601), self.assertRaisesMessage(ValidationError, "expired"):
            self.consume(a, token)
        # Current payment evidence changes cannot be hidden by an unchanged invoice.
        c = a.contributions.get()
        Contribution.objects.filter(pk=c.pk).update(gateway_reference="altered")
        with self.assertRaises(ValidationError):
            self.consume(a, token)
        Contribution.objects.filter(pk=c.pk).update(gateway_reference=c.gateway_reference)
        f = self.consume(a, token, idempotency_key=key)
        with self.assertRaises(ValidationError):
            self.consume(a, token, idempotency_key=key, reason="Different reason")
        Contribution.objects.filter(pk=c.pk).update(gateway_reference="altered")
        self.assertTrue(get_benefit_invoice_status(award).needs_review)
        self.assertEqual(BenefitInvoiceFulfilment.objects.get(pk=f.pk).benefit_amount, 40)

    def test_atomic_failure_immutability_constraints_and_reverse_guard(self):
        a, award, source = self.disposition()
        token = self.invoice(a, award, source)
        save = BenefitInvoiceFulfilment.save
        def fail_after_insert(row, *args, **kwargs):
            save(row, *args, **kwargs)
            raise ValidationError("Injected post-insert failure")
        with patch.object(BenefitInvoiceFulfilment, "save", fail_after_insert), self.assertRaises(ValidationError):
            self.consume(a, token)
        self.assertFalse(BenefitInvoiceFulfilment.objects.exists())
        f = self.consume(a, token)
        with self.assertRaises(ValidationError):
            f.save()
        with self.assertRaises(ValidationError):
            f.delete()
        for changes in (dict(benefit_amount=-1), dict(invoice_after_benefit=1), dict(inr_fulfilment=None), dict(actor_label="")):
            with self.assertRaises(IntegrityError), transaction.atomic():
                BenefitInvoiceFulfilment.objects.filter(pk=f.pk).update(**changes)
        migration = importlib.import_module("schemes.migrations.0047_benefit_invoice_fulfilment")
        with connection.schema_editor(atomic=False) as editor, self.assertRaises(RuntimeError):
            migration.guard_reverse(apps, editor)
        r = self.reverse(f, self.returned(f))
        with self.assertRaises(ValidationError):
            r.delete()
        with self.assertRaises(ValidationError):
            r.save()
        for changes in (dict(amount=-1), dict(inr_return=None), dict(customer_confirmation="")):
            with self.assertRaises(IntegrityError), transaction.atomic():
                BenefitInvoiceReversal.objects.filter(pk=r.pk).update(**changes)

    def test_changed_frozen_terms_and_missing_settlement_evidence_refuse_standalone_fulfilment(self):
        from schemes.inr_settlement_selectors import inr_source_evidence
        a, award, source = self.disposition()
        token = self.invoice(a, award, source)
        type(a).objects.filter(pk=a.pk).update(plan_name_snapshot="Unaccepted changed terms")
        a.plan_name_snapshot = "Unaccepted changed terms"
        with self.assertRaises(ValidationError):
            inr_source_evidence(a)
        for flag in (False, True):
            with override_settings(CONFIGURED_PLANS_ENABLED=flag), self.assertRaises(ValidationError):
                record_benefit_fulfilment(account_id=a.pk, actor=self.owner, preview_token=token,
                    reason="Try activation", idempotency_key=uuid.uuid4())
            with override_settings(CONFIGURED_PLANS_ENABLED=flag), self.assertRaises(ValidationError):
                BenefitInvoiceFulfilment(award=award).save()
        self.assertFalse(BenefitInvoiceFulfilment.objects.exists())

    def test_read_only_diagnostics_tamper_and_case_insensitive_invoice_uniqueness(self):
        a, award, source = self.disposition()
        f = self.consume(a, self.invoice(a, award, source))
        b, other_award, other_source = self.disposition()
        other = self.consume(b, self.invoice(b, other_award, other_source))
        with self.assertRaises(IntegrityError), transaction.atomic():
            BenefitInvoiceFulfilment.objects.filter(pk=other.pk).update(invoice_reference=f.invoice_reference.lower())
        with CaptureQueriesContext(connection) as queries:
            self.assertFalse(get_benefit_invoice_status(award).needs_review)
            call_command("check_benefit_awards", stdout=StringIO())
        self.assertFalse(any(q["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")) for q in queries))
        BenefitInvoiceFulfilment.objects.filter(pk=f.pk).update(evidence_digest="0" * 64)
        self.assertTrue(get_benefit_invoice_status(award).needs_review)
        with self.assertRaises(CommandError):
            call_command("check_benefit_awards", stdout=StringIO())

    def test_wrong_or_unrecorded_returns_cannot_reverse_and_failed_insert_is_atomic(self):
        a, award, source = self.disposition()
        f = self.consume(a, self.invoice(a, award, source))
        with self.assertRaises(ValidationError):
            self.reverse(f, {})
        b, other_award, other_source = self.disposition()
        other = self.consume(b, self.invoice(b, other_award, other_source))
        wrong = self.returned(other)
        with self.assertRaises(ValidationError):
            self.reverse(f, wrong)
        actual = self.returned(f)
        for changes in (dict(invoice_correction_reference="Not the invoice correction"),
                        dict(customer_confirmation="Different confirmation")):
            with self.assertRaises(ValidationError):
                self.reverse(f, actual, **changes)
        save = BenefitInvoiceReversal.save
        def fail_after_insert(row, *args, **kwargs):
            save(row, *args, **kwargs)
            raise ValidationError("Injected reversal failure")
        with patch.object(BenefitInvoiceReversal, "save", fail_after_insert), self.assertRaises(ValidationError):
            self.reverse(f, actual)
        self.assertFalse(BenefitInvoiceReversal.objects.exists())
        self.assertEqual(f.award.amount, 40)

    def test_zero_rounded_va_is_retained_without_manufacturing_credit(self):
        a, award, source = self.disposition("VA_DISCOUNT", True)
        token = self.invoice(a, award, source, eligible_charges=Decimal("0.01"))
        f = self.consume(a, token)
        self.assertEqual(f.benefit_amount, Decimal("0.00"))
        self.assertEqual(f.invoice_after_benefit, Decimal("600.00"))
        self.assertFalse(get_benefit_invoice_status(award).needs_review)
        with self.assertRaises(ValidationError):
            self.invoice(a, award, source)

    def test_stale_handover_and_full_metal_source_identity_are_checked(self):
        a, award, source = self.disposition("VA_DISCOUNT", True)
        token = self.invoice(a, award, source)
        # Same quantity is insufficient: it must be this award's actual allocation.
        proof = dict(source.evidence)
        proof["payments"] = [dict(p, allocation=p["allocation"] + 1000) for p in proof["payments"]]
        ConfiguredSettlement.objects.filter(pk=source.pk).update(evidence=proof, evidence_digest=proof_digest(proof))
        with self.assertRaises(ValidationError):
            self.consume(a, token)
        ConfiguredSettlement.objects.filter(pk=source.pk).update(evidence=source.evidence, evidence_digest=source.evidence_digest)
        f = self.consume(a, token)
        self.returned(f)
        self.assertTrue(get_benefit_invoice_status(award).needs_review)
        self.assertFalse(BenefitInvoiceReversal.objects.exists())


@override_settings(IN_STORE_CASH_CONTRIBUTIONS_ENABLED=True, PAYMENT_INITIATION_KILL_SWITCH=False)
class BenefitInvoiceConcurrencyTests(InvoiceFixture, TransactionTestCase):
    def test_concurrent_retry_consumes_one_award_once(self):
        a, award, source = self.disposition()
        token, key, barrier = self.invoice(a, award, source), uuid.uuid4(), Barrier(2)
        def apply():
            try:
                barrier.wait(timeout=10)
                return record_benefit_fulfilment(account_id=a.pk, actor=self.owner, preview_token=token,
                    reason="Same actual invoice", idempotency_key=key).pk
            finally:
                connections.close_all()
        with future_award_readiness(), ThreadPoolExecutor(max_workers=2) as pool:
            ids = list(pool.map(lambda _: apply(), range(2)))
        self.assertEqual(ids[0], ids[1])
        self.assertEqual(BenefitInvoiceFulfilment.objects.count(), 1)

    def test_concurrent_return_retries_record_one_full_reversal(self):
        a, award, source = self.disposition()
        f = self.consume(a, self.invoice(a, award, source))
        returned, key, barrier = self.returned(f), uuid.uuid4(), Barrier(2)
        def apply():
            try:
                barrier.wait(timeout=10)
                return reverse_benefit_fulfilment(account_id=a.pk, fulfilment_id=f.pk, actor=self.owner,
                    reason="Same actual return", idempotency_key=key, invoice_correction_reference="Corrected invoice",
                    customer_confirmation="Signed return", returned_at=NOW, **returned).pk
            finally:
                connections.close_all()
        with future_award_readiness(), ThreadPoolExecutor(max_workers=2) as pool:
            ids = list(pool.map(lambda _: apply(), range(2)))
        self.assertEqual(ids[0], ids[1])
        self.assertEqual(BenefitInvoiceReversal.objects.count(), 1)
