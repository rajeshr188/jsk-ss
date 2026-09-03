import uuid
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from schemes.models import (
    Contribution,
    MetalAllocation,
    SchemeRate,
    Redemption,
    SchemeAccount,
    SchemePlan,
)
from schemes.forms import RedemptionForm
from schemes.selectors import (
    get_cash_balance,
    get_customer_scheme_summary,
    get_metal_balance,
    get_owner_liability_summary,
)
from schemes.services import complete_redemption, create_customer, enroll_customer
from schemes.tests.grade_helpers import enrolment_grade_kwargs


def make_redemption_fixture():
    owner = get_user_model().objects.create_user(
        username="redemption-owner@example.com",
        email="redemption-owner@example.com",
        password="owner-password-strong",
        role=get_user_model().Role.OWNER,
    )
    customer = create_customer(
        full_name="Redemption Customer",
        email="redemption-customer@example.com",
        mobile_number="9000000066",
        password="customer-password-strong",
    )
    plan = SchemePlan.objects.create(
        name="Redemption Plan",
        code="REDEMPTION-PLAN",
        amount_rule=SchemePlan.AmountRule.VARIABLE,
        frequency_rule=SchemePlan.FrequencyRule.FLEXIBLE,
        minimum_contribution=Decimal("100.00"),
        maximum_contribution=Decimal("100000.00"),
    )
    return owner, customer, plan


def make_account(*, customer, plan, mode, eligible=True):
    account = enroll_customer(
        customer=customer,
        plan=plan,
        **enrolment_grade_kwargs(plan, mode),
        start_date=timezone.localdate() - timedelta(days=365),
    )
    account.eligible_from = timezone.localdate() + timedelta(days=-1 if eligible else 1)
    account.save(update_fields=["eligible_from"])
    return account


def make_paid_contribution(account, amount, reference):
    return Contribution.objects.create(
        scheme_account=account,
        amount=amount,
        contribution_period=timezone.localdate().replace(day=1),
        frequency_rule_snapshot=SchemePlan.FrequencyRule.FLEXIBLE,
        status=Contribution.Status.PAID,
        payment_gateway="redemption-test",
        gateway_reference=reference,
        paid_at=timezone.now(),
    )


def make_metal_entitlement(account, quantity, reference):
    contribution = make_paid_contribution(account, Decimal("10000.00"), reference)
    scheme_rate = SchemeRate.objects.create(
        metal_grade=account.metal_grade,
        metal=account.savings_mode,
        rate_per_gram=Decimal("12500.0000"),
        purity=account.metal_grade.fineness,
        effective_from=timezone.now(),
    )
    contribution.scheme_rate = scheme_rate
    contribution.rate_locked_at = contribution.created_at
    contribution.save(update_fields=["scheme_rate", "rate_locked_at"])
    return MetalAllocation.objects.create(
        contribution=contribution,
        scheme_rate=scheme_rate,
        metal_grade=account.metal_grade,
        metal=account.savings_mode,
        quantity=quantity,
    )


@override_settings(DEBUG=True)
class RedemptionServiceTests(TestCase):
    def setUp(self):
        self.owner, self.customer, self.plan = make_redemption_fixture()

    def test_partial_then_full_cash_redemption_updates_balance_and_status(self):
        account = make_account(
            customer=self.customer,
            plan=self.plan,
            mode=SchemeAccount.SavingsMode.CASH,
        )
        contribution = make_paid_contribution(
            account, Decimal("10000.00"), "cash-redemption-source"
        )
        partial = complete_redemption(
            scheme_account=account,
            settlement_type=Redemption.SettlementType.CASH,
            amount=Decimal("4000.00"),
            processed_by=self.owner,
            idempotency_key=uuid.uuid4(),
        )
        account.refresh_from_db()
        self.assertEqual(partial.cash_amount, Decimal("4000.00"))
        self.assertEqual(get_cash_balance(account), Decimal("6000.00"))
        self.assertEqual(account.status, SchemeAccount.Status.ACTIVE)

        complete_redemption(
            scheme_account=account,
            settlement_type=Redemption.SettlementType.JEWELLERY_PURCHASE,
            amount=Decimal("6000.00"),
            external_reference="INV-REDEEM-1",
            processed_by=self.owner,
            idempotency_key=uuid.uuid4(),
        )
        account.refresh_from_db()
        self.assertEqual(get_cash_balance(account), Decimal("0.00"))
        self.assertEqual(account.status, SchemeAccount.Status.REDEEMED)
        self.assertTrue(Contribution.objects.filter(pk=contribution.pk).exists())
        self.assertEqual(Redemption.objects.count(), 2)

    def test_duplicate_submission_is_idempotent(self):
        account = make_account(
            customer=self.customer,
            plan=self.plan,
            mode=SchemeAccount.SavingsMode.CASH,
        )
        make_paid_contribution(account, Decimal("10000.00"), "cash-idempotent-source")
        key = uuid.uuid4()
        first = complete_redemption(
            scheme_account=account,
            settlement_type=Redemption.SettlementType.CASH,
            amount=Decimal("3000.00"),
            processed_by=self.owner,
            idempotency_key=key,
            notes="Counter settlement",
        )
        second = complete_redemption(
            scheme_account=account,
            settlement_type=Redemption.SettlementType.CASH,
            amount=Decimal("3000.00"),
            processed_by=self.owner,
            idempotency_key=key,
            notes="Counter settlement",
        )
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(Redemption.objects.count(), 1)
        self.assertEqual(get_cash_balance(account), Decimal("7000.00"))

    def test_reused_token_with_changed_details_is_rejected(self):
        account = make_account(
            customer=self.customer,
            plan=self.plan,
            mode=SchemeAccount.SavingsMode.CASH,
        )
        make_paid_contribution(account, Decimal("10000.00"), "cash-token-source")
        key = uuid.uuid4()
        complete_redemption(
            scheme_account=account,
            settlement_type=Redemption.SettlementType.CASH,
            amount=Decimal("1000.00"),
            processed_by=self.owner,
            idempotency_key=key,
        )
        with self.assertRaises(ValidationError):
            complete_redemption(
                scheme_account=account,
                settlement_type=Redemption.SettlementType.CASH,
                amount=Decimal("2000.00"),
                processed_by=self.owner,
                idempotency_key=key,
            )
        self.assertEqual(get_cash_balance(account), Decimal("9000.00"))

    def test_over_redemption_and_pre_eligibility_are_rejected(self):
        eligible = make_account(
            customer=self.customer,
            plan=self.plan,
            mode=SchemeAccount.SavingsMode.CASH,
        )
        upcoming = make_account(
            customer=self.customer,
            plan=self.plan,
            mode=SchemeAccount.SavingsMode.CASH,
            eligible=False,
        )
        make_paid_contribution(eligible, Decimal("5000.00"), "cash-over-source")
        make_paid_contribution(upcoming, Decimal("5000.00"), "cash-early-source")
        with self.assertRaises(ValidationError):
            complete_redemption(
                scheme_account=eligible,
                settlement_type=Redemption.SettlementType.CASH,
                amount=Decimal("5000.01"),
                processed_by=self.owner,
                idempotency_key=uuid.uuid4(),
            )
        with self.assertRaises(ValidationError):
            complete_redemption(
                scheme_account=upcoming,
                settlement_type=Redemption.SettlementType.CASH,
                amount=Decimal("1000.00"),
                processed_by=self.owner,
                idempotency_key=uuid.uuid4(),
            )
        self.assertFalse(Redemption.objects.exists())

    def test_gold_and_silver_redemptions_reduce_only_their_dimension(self):
        accounts = {}
        for mode, quantity, amount in (
            (SchemeAccount.SavingsMode.GOLD, Decimal("0.800000"), Decimal("0.300000")),
            (SchemeAccount.SavingsMode.SILVER, Decimal("60.000000"), Decimal("10.000000")),
        ):
            account = make_account(
                customer=self.customer,
                plan=self.plan,
                mode=mode,
            )
            make_metal_entitlement(account, quantity, f"{mode.lower()}-source")
            redemption = complete_redemption(
                scheme_account=account,
                settlement_type=Redemption.SettlementType.METAL,
                amount=amount,
                processed_by=self.owner,
                idempotency_key=uuid.uuid4(),
            )
            accounts[mode] = account
            expected = quantity - amount
            self.assertEqual(get_metal_balance(account), expected)
            if mode == SchemeAccount.SavingsMode.GOLD:
                self.assertEqual(redemption.gold_quantity, amount)
                self.assertIsNone(redemption.silver_quantity)
            else:
                self.assertEqual(redemption.silver_quantity, amount)
                self.assertIsNone(redemption.gold_quantity)

        summary = get_owner_liability_summary()
        liabilities = {
            item.metal_grade.code: item for item in summary.metal_grades
        }
        self.assertEqual(
            liabilities["GOLD_24K_9999"].quantity,
            Decimal("0.500000"),
        )
        self.assertEqual(
            liabilities["SILVER_999"].quantity,
            Decimal("50.000000"),
        )

    def test_full_metal_redemption_closes_account(self):
        account = make_account(
            customer=self.customer,
            plan=self.plan,
            mode=SchemeAccount.SavingsMode.GOLD,
        )
        make_metal_entitlement(account, Decimal("0.800000"), "gold-full-source")
        complete_redemption(
            scheme_account=account,
            settlement_type=Redemption.SettlementType.METAL,
            amount=Decimal("0.800000"),
            processed_by=self.owner,
            idempotency_key=uuid.uuid4(),
        )
        account.refresh_from_db()
        self.assertEqual(get_metal_balance(account), Decimal("0.000000"))
        self.assertEqual(account.status, SchemeAccount.Status.REDEEMED)

    def test_redemption_precision_is_rejected_not_rounded(self):
        cases = (
            (SchemeAccount.SavingsMode.CASH, Decimal("1000.001")),
            (SchemeAccount.SavingsMode.GOLD, Decimal("0.1000001")),
        )
        for mode, amount in cases:
            with self.subTest(mode=mode):
                account = make_account(
                    customer=self.customer,
                    plan=self.plan,
                    mode=mode,
                )
                if mode == SchemeAccount.SavingsMode.CASH:
                    make_paid_contribution(account, Decimal("5000.00"), "precision-cash")
                    settlement_type = Redemption.SettlementType.CASH
                else:
                    make_metal_entitlement(
                        account, Decimal("0.800000"), "precision-gold"
                    )
                    settlement_type = Redemption.SettlementType.METAL
                with self.assertRaises(ValidationError):
                    complete_redemption(
                        scheme_account=account,
                        settlement_type=settlement_type,
                        amount=amount,
                        processed_by=self.owner,
                        idempotency_key=uuid.uuid4(),
                    )
        self.assertFalse(Redemption.objects.exists())

    def test_owner_metal_redemption_input_preserves_six_decimal_settlement(self):
        account = make_account(
            customer=self.customer,
            plan=self.plan,
            mode=SchemeAccount.SavingsMode.GOLD,
        )
        form = RedemptionForm(
            data={
                "settlement_type": Redemption.SettlementType.METAL,
                "amount": "0.123456",
                "external_reference": "",
                "notes": "",
                "audit_reason": "Customer requested a metal redemption.",
                "idempotency_key": str(uuid.uuid4()),
            },
            scheme_account=account,
            outstanding=Decimal("0.800000"),
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["amount"], Decimal("0.123456"))

    def test_metal_to_cash_and_unreferenced_jewellery_are_rejected(self):
        account = make_account(
            customer=self.customer,
            plan=self.plan,
            mode=SchemeAccount.SavingsMode.GOLD,
        )
        make_metal_entitlement(account, Decimal("0.800000"), "gold-invalid-source")
        for settlement_type in (
            Redemption.SettlementType.CASH,
            Redemption.SettlementType.JEWELLERY_PURCHASE,
        ):
            with self.assertRaises(ValidationError):
                complete_redemption(
                    scheme_account=account,
                    settlement_type=settlement_type,
                    amount=Decimal("0.100000"),
                    processed_by=self.owner,
                    idempotency_key=uuid.uuid4(),
                )

    def test_customer_summary_subtracts_multiple_redemptions_without_join_duplication(self):
        account = make_account(
            customer=self.customer,
            plan=self.plan,
            mode=SchemeAccount.SavingsMode.CASH,
        )
        make_paid_contribution(account, Decimal("4000.00"), "summary-source-1")
        make_paid_contribution(account, Decimal("6000.00"), "summary-source-2")
        for amount in (Decimal("1000.00"), Decimal("2000.00")):
            complete_redemption(
                scheme_account=account,
                settlement_type=Redemption.SettlementType.CASH,
                amount=amount,
                processed_by=self.owner,
                idempotency_key=uuid.uuid4(),
            )
        summary_account = get_customer_scheme_summary(self.customer.user).get(pk=account.pk)
        self.assertEqual(summary_account.cash_balance, Decimal("7000.00"))

    def test_database_constraint_and_immutability_protect_history(self):
        account = make_account(
            customer=self.customer,
            plan=self.plan,
            mode=SchemeAccount.SavingsMode.CASH,
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            Redemption.objects.create(
                redemption_number="RED-INVALID",
                scheme_account=account,
                settlement_type=Redemption.SettlementType.CASH,
                cash_amount=Decimal("100.00"),
                gold_quantity=Decimal("0.100000"),
                processed_by=self.owner,
            )
        make_paid_contribution(account, Decimal("1000.00"), "immutable-source")
        redemption = complete_redemption(
            scheme_account=account,
            settlement_type=Redemption.SettlementType.CASH,
            amount=Decimal("500.00"),
            processed_by=self.owner,
            idempotency_key=uuid.uuid4(),
        )
        redemption.notes = "Changed"
        with self.assertRaises(ValidationError):
            redemption.save()


@override_settings(DEBUG=True, PAYMENT_GATEWAY="mock")
class RedemptionViewTests(TestCase):
    def setUp(self):
        self.owner, self.customer, self.plan = make_redemption_fixture()
        self.account = make_account(
            customer=self.customer,
            plan=self.plan,
            mode=SchemeAccount.SavingsMode.CASH,
        )
        make_paid_contribution(self.account, Decimal("5000.00"), "view-source")

    def test_owner_completes_redemption_and_customer_sees_history(self):
        self.client.force_login(self.owner)
        url = reverse("schemes:redemption_create", args=[self.account.scheme_number])
        page = self.client.get(url)
        key = page.context["form"].fields["idempotency_key"].initial
        response = self.client.post(
            url,
            {
                "settlement_type": Redemption.SettlementType.CASH,
                "amount": "5000.00",
                "external_reference": "SETTLEMENT-5000",
                "notes": "Paid at store counter",
                "audit_reason": "Customer collected the matured amount.",
                "idempotency_key": str(key),
            },
            follow=True,
        )
        self.assertContains(response, "Redemption RED-")
        redemption = Redemption.objects.get()
        self.account.refresh_from_db()
        self.assertEqual(self.account.status, SchemeAccount.Status.REDEEMED)

        self.client.force_login(self.customer.user)
        detail = self.client.get(
            reverse("schemes:my_scheme_detail", args=[self.account.scheme_number])
        )
        self.assertContains(detail, redemption.redemption_number)
        self.assertContains(detail, "5000.00")
        self.assertNotContains(detail, ">Pay now<")

    def test_customer_cannot_access_owner_redemption_views(self):
        self.client.force_login(self.customer.user)
        create_response = self.client.get(
            reverse("schemes:redemption_create", args=[self.account.scheme_number])
        )
        list_response = self.client.get(reverse("schemes:redemption_list"))
        self.assertEqual(create_response.status_code, 403)
        self.assertEqual(list_response.status_code, 403)

    def test_redemption_form_rejects_missing_jewellery_reference(self):
        self.client.force_login(self.owner)
        url = reverse("schemes:redemption_create", args=[self.account.scheme_number])
        page = self.client.get(url)
        key = page.context["form"].fields["idempotency_key"].initial
        response = self.client.post(
            url,
            {
                "settlement_type": Redemption.SettlementType.JEWELLERY_PURCHASE,
                "amount": "1000.00",
                "external_reference": "",
                "notes": "",
                "idempotency_key": str(key),
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Enter the jewellery invoice or sales reference")
        self.assertFalse(Redemption.objects.exists())

    def test_eligible_account_without_entitlement_has_no_redemption_link(self):
        empty_account = make_account(
            customer=self.customer,
            plan=self.plan,
            mode=SchemeAccount.SavingsMode.CASH,
        )
        self.client.force_login(self.owner)
        response = self.client.get(reverse("schemes:redemption_eligibility"))
        self.assertContains(response, "No outstanding entitlement")
        self.assertNotContains(
            response,
            reverse("schemes:redemption_create", args=[empty_account.scheme_number]),
        )
