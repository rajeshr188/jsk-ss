"""Read cost and retained-prefix safety after a real replacement and full return."""
import re
from collections import Counter
from time import perf_counter

from django.core.exceptions import ValidationError
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from schemes.models import BenefitInvoiceFulfilment, BenefitInvoiceReversal
from schemes.closure_selectors import validate_closure_history
from schemes.tests.test_benefit_replacement_integration import IntegrationFixture


@override_settings(IN_STORE_CASH_CONTRIBUTIONS_ENABLED=True, PAYMENT_INITIATION_KILL_SWITCH=False)
class OwnerHistoryQueryTests(IntegrationFixture, TestCase):
    # These fixture ceilings catch the measured two-return regression; they are
    # not a production latency target or a limit on retained financial history.
    query_budgets = {
        "INR_PURCHASE_BONUS_one_return": 680,
        "INR_PURCHASE_BONUS_two_returns": 1900,
        "VA_DISCOUNT_one_return": 300,
        "VA_DISCOUNT_two_returns": 850,
    }

    def measure(self, account, stage):
        def no_writes(execute, sql, params, many, context):
            self.assertNotIn(sql.lstrip().split()[0].upper(), {"INSERT", "UPDATE", "DELETE"})
            return execute(sql, params, many, context)
        started = perf_counter()
        with connection.execute_wrapper(no_writes), CaptureQueriesContext(connection) as queries:
            response = self.client.get(reverse("schemes:benefit_reapplication", args=[account.scheme_number]))
        self.assertEqual(response.status_code, 200)
        self.assertIn("private", response.headers["Cache-Control"])
        tables = Counter()
        for query in queries:
            match = re.search(r'FROM "([a-z_]+)"', query["sql"])
            if match:
                tables[match.group(1)] += 1
        print(f"owner_history_profile stage={stage} queries={len(queries)} seconds={perf_counter() - started:.3f} tables={tables.most_common(5)}", flush=True)
        self.assertLessEqual(len(queries), self.query_budgets[stage], stage)
        return response, len(queries)

    def exercise(self, metal):
        self.client.force_login(self.owner)
        kind = "VA_DISCOUNT" if metal else "INR_PURCHASE_BONUS"
        account, closure, reversal = self.returned_benefit(kind=kind, metal=metal)
        self.approve(account, reversal)
        self.measure(account, kind + "_one_return")
        if metal:
            proof, values = self.metal_values(closure)
            redemption = self.settle(values)
            self.reverse(self.reversal_values(redemption) | {"expected_sequence": proof["sequence"] + 1})
            invoice = BenefitInvoiceFulfilment.objects.get(metal_settlement=redemption.configured_settlement)
        else:
            proposal = self.replacement_inr(account, closure)
            self.complete(proposal)
            self.return_all(proposal)
            invoice = BenefitInvoiceFulfilment.objects.get(inr_fulfilment__proposal=proposal)
        latest = BenefitInvoiceReversal.objects.get(fulfilment=invoice)
        self.approve(account, latest)
        response, _ = self.measure(account, kind + "_two_returns")
        self.assertEqual(len(response.context["review_rows"]), 2)
        self.assertContains(response, "Used by a replacement invoice")
        self.assertContains(response, "Approved for replacement review")
        self.assertEqual(list(response.context["reviewable_returns"].values_list("pk", flat=True)), [latest.pk])
        # A consumed predecessor still matters. Bypass append-only model guards
        # only in this disposable fixture to simulate historical evidence drift.
        closure.refresh_from_db()
        self.assertEqual(validate_closure_history(closure), closure.events.count())
        original = closure.events.filter(action="SETTLE").earliest("sequence")
        closure.events.filter(pk=original.pk).update(authorization_reference="Tampered historical consent")
        with self.assertRaises(ValidationError):
            validate_closure_history(closure)  # Same instance must read fresh links.
        response = self.client.get(reverse("schemes:benefit_reapplication", args=[account.scheme_number]))
        self.assertContains(response, "Investigation required")
        self.assertFalse(response.context["reviewable_returns"].exists())

    def test_inr_replacement_return_history(self):
        self.exercise(False)

    def test_metal_replacement_return_history(self):
        self.exercise(True)
