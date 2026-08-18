import csv
import io
import uuid
from datetime import date
from decimal import Decimal

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import CustomUser
from schemes.models import Contribution, Redemption, SchemeAccount, SchemePlan
from schemes.selectors import (
    contribution_receipt_number,
    get_scheme_statement,
)
from schemes.services import (
    add_calendar_months,
    complete_redemption,
    create_customer,
    enroll_customer,
    process_mock_contribution,
    reverse_redemption,
)


def make_owner():
    return CustomUser.objects.create_user(
        username="documents-owner@example.com",
        email="documents-owner@example.com",
        password="OwnerPass123!",
        role=CustomUser.Role.OWNER,
    )


def make_plan():
    return SchemePlan.objects.create(
        name="Document Plan",
        code="DOC-PLAN",
        minimum_months=12,
        default_months=12,
        amount_rule=SchemePlan.AmountRule.VARIABLE,
        frequency_rule=SchemePlan.FrequencyRule.FLEXIBLE,
        minimum_contribution=Decimal("100.00"),
        maximum_contribution=Decimal("10000.00"),
        allow_contributions_after_eligibility=True,
    )


def make_customer(email="documents-customer@example.com", full_name="Document Customer"):
    return create_customer(
        full_name=full_name,
        email=email,
        mobile_number="9000000077",
        password="CustomerPass123!",
    )


def make_account(*, customer, plan, owner, mode=SchemeAccount.SavingsMode.CASH):
    return enroll_customer(
        customer=customer,
        plan=plan,
        savings_mode=mode,
        start_date=add_calendar_months(timezone.localdate(), -12),
        agreed_months=12,
        performed_by=owner,
        reason="Customer requested document-test enrolment.",
    )


def make_paid_contribution(account, amount="100.00", *, status=Contribution.Status.PAID):
    return Contribution.objects.create(
        scheme_account=account,
        amount=Decimal(amount),
        contribution_period=date.today().replace(day=1),
        frequency_rule_snapshot=SchemePlan.FrequencyRule.FLEXIBLE,
        status=status,
        payment_gateway="mock",
        gateway_reference=f"doc-pay-{uuid.uuid4()}",
        paid_at=timezone.now() if status in {
            Contribution.Status.PAID,
            Contribution.Status.PAID_UNALLOCATED,
        } else None,
        allocation_error=(
            "Rate provider unavailable"
            if status == Contribution.Status.PAID_UNALLOCATED
            else ""
        ),
    )


@override_settings(
    DEBUG=True,
    PAYMENT_GATEWAY="mock",
    METAL_RATE_PROVIDER="mock",
    MOCK_GOLD_RATE="12500.0000",
    MOCK_SILVER_RATE="150.0000",
)
class ReceiptAndStatementTests(TestCase):
    def setUp(self):
        self.owner = make_owner()
        self.plan = make_plan()
        self.customer = make_customer()
        self.cash_account = make_account(
            customer=self.customer,
            plan=self.plan,
            owner=self.owner,
        )

    def test_cash_receipt_has_stable_number_and_required_fields(self):
        contribution = make_paid_contribution(self.cash_account, "500.00")
        self.client.force_login(self.customer.user)
        url = reverse("schemes:contribution_receipt", args=[contribution.pk])

        first = self.client.get(url)
        second = self.client.get(url)

        expected_number = contribution_receipt_number(contribution)
        self.assertEqual(first.status_code, 200)
        self.assertContains(first, expected_number)
        self.assertContains(first, self.customer.full_name)
        self.assertContains(first, self.cash_account.scheme_number)
        self.assertContains(first, "₹500.00")
        self.assertContains(first, contribution.gateway_reference)
        self.assertContains(first, "not a tax invoice")
        self.assertContains(second, expected_number)

    def test_metal_receipt_shows_rate_and_quantity(self):
        gold_account = make_account(
            customer=self.customer,
            plan=self.plan,
            owner=self.owner,
            mode=SchemeAccount.SavingsMode.GOLD,
        )
        contribution = process_mock_contribution(
            scheme_account=gold_account,
            amount=Decimal("10000.00"),
        )
        self.client.force_login(self.customer.user)

        response = self.client.get(
            reverse("schemes:contribution_receipt", args=[contribution.pk])
        )

        self.assertContains(response, "24K Gold")
        self.assertContains(response, "₹12500.0000 per g")
        self.assertContains(response, "0.800000 g")

    def test_paid_unallocated_receipt_never_invents_rate_or_quantity(self):
        gold_account = make_account(
            customer=self.customer,
            plan=self.plan,
            owner=self.owner,
            mode=SchemeAccount.SavingsMode.GOLD,
        )
        contribution = make_paid_contribution(
            gold_account,
            status=Contribution.Status.PAID_UNALLOCATED,
        )
        self.client.force_login(self.customer.user)

        response = self.client.get(
            reverse("schemes:contribution_receipt", args=[contribution.pk])
        )

        self.assertContains(response, "allocation is pending")
        self.assertContains(response, "No rate or quantity has been assigned")
        self.assertNotContains(response, "Quantity allocated")

    def test_failed_payment_has_no_receipt(self):
        contribution = make_paid_contribution(
            self.cash_account,
            status=Contribution.Status.FAILED,
        )
        self.client.force_login(self.customer.user)
        response = self.client.get(
            reverse("schemes:contribution_receipt", args=[contribution.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_document_access_is_limited_to_customer_or_owner(self):
        contribution = make_paid_contribution(self.cash_account)
        other_customer = make_customer(
            email="other-documents@example.com",
            full_name="Other Customer",
        )
        receipt_url = reverse("schemes:contribution_receipt", args=[contribution.pk])
        statement_url = reverse(
            "schemes:scheme_statement", args=[self.cash_account.scheme_number]
        )

        self.client.force_login(other_customer.user)
        self.assertEqual(self.client.get(receipt_url).status_code, 404)
        self.assertEqual(self.client.get(statement_url).status_code, 404)

        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(receipt_url).status_code, 200)
        self.assertEqual(self.client.get(statement_url).status_code, 200)

    def test_cash_statement_shows_reversal_and_restored_entitlement(self):
        make_paid_contribution(self.cash_account, "100.00")
        redemption = complete_redemption(
            scheme_account=self.cash_account,
            settlement_type=Redemption.SettlementType.CASH,
            amount="100.00",
            processed_by=self.owner,
            idempotency_key=uuid.uuid4(),
        )
        reverse_redemption(
            redemption=redemption,
            processed_by=self.owner,
            reason="Incorrect settlement entry.",
        )

        statement = get_scheme_statement(self.cash_account)

        self.assertEqual(statement.remaining_entitlement, Decimal("100.00"))
        self.assertEqual(statement.entitlement_unit, "INR")
        self.assertEqual(
            [entry.description for entry in statement.entries],
            ["Cash contribution", "Cash redemption", "Redemption reversal"],
        )
        self.assertEqual(statement.entries[1].status, "Reversed")
        self.assertEqual(statement.entries[2].restoration, Decimal("100.00"))

    def test_metal_statement_keeps_inr_payment_and_grams_separate(self):
        silver_account = make_account(
            customer=self.customer,
            plan=self.plan,
            owner=self.owner,
            mode=SchemeAccount.SavingsMode.SILVER,
        )
        process_mock_contribution(
            scheme_account=silver_account,
            amount=Decimal("300.00"),
        )

        statement = get_scheme_statement(silver_account)
        entry = statement.entries[0]

        self.assertEqual(entry.amount_inr, Decimal("300.00"))
        self.assertEqual(entry.applied_rate, Decimal("150.0000"))
        self.assertEqual(entry.metal_allocation, Decimal("2.000000"))
        self.assertEqual(statement.remaining_entitlement, Decimal("2.000000"))
        self.assertEqual(statement.entitlement_unit, "g silver")

    def test_statement_excludes_pending_and_failed_attempts(self):
        make_paid_contribution(self.cash_account, status=Contribution.Status.PENDING)
        make_paid_contribution(self.cash_account, status=Contribution.Status.FAILED)
        paid = make_paid_contribution(self.cash_account)

        statement = get_scheme_statement(self.cash_account)

        self.assertEqual(len(statement.entries), 1)
        self.assertEqual(statement.entries[0].reference, paid.gateway_reference)


@override_settings(DEBUG=True, METAL_RATE_PROVIDER="mock")
class OwnerDocumentExportTests(TestCase):
    def setUp(self):
        self.owner = make_owner()
        self.plan = make_plan()
        self.customer = make_customer(full_name="=HYPERLINK malicious customer")
        self.account = make_account(
            customer=self.customer,
            plan=self.plan,
            owner=self.owner,
        )
        self.contribution = make_paid_contribution(self.account, "250.00")
        self.client.force_login(self.owner)

    def test_contribution_csv_is_accounting_safe_and_formula_neutralized(self):
        response = self.client.get(reverse("schemes:contribution_export"))
        rows = list(csv.reader(io.StringIO(response.content.decode("utf-8"))))

        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertEqual(rows[0][0], "receipt_number")
        self.assertEqual(rows[1][0], contribution_receipt_number(self.contribution))
        self.assertEqual(rows[1][6], "250.00")
        self.assertEqual(rows[1][10:], ["", "", ""])
        self.assertTrue(rows[1][3].startswith("'="))

    def test_redemption_csv_uses_separate_cash_and_metal_columns(self):
        redemption = complete_redemption(
            scheme_account=self.account,
            settlement_type=Redemption.SettlementType.CASH,
            amount="250.00",
            processed_by=self.owner,
            idempotency_key=uuid.uuid4(),
        )
        reverse_redemption(
            redemption=redemption,
            processed_by=self.owner,
            reason="Export reversal test.",
        )

        response = self.client.get(reverse("schemes:redemption_export"))
        rows = list(csv.DictReader(io.StringIO(response.content.decode("utf-8"))))

        self.assertEqual(rows[0]["status"], "REVERSED")
        self.assertEqual(rows[0]["cash_amount_inr"], "250.00")
        self.assertEqual(rows[0]["gold_quantity_g"], "")
        self.assertEqual(rows[0]["silver_quantity_g"], "")
        self.assertTrue(rows[0]["reversal_number"].startswith("REV-"))

    def test_customer_cannot_download_owner_exports(self):
        self.client.force_login(self.customer.user)
        self.assertEqual(
            self.client.get(reverse("schemes:contribution_export")).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(reverse("schemes:redemption_export")).status_code,
            403,
        )
