from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from schemes.models import SchemeAccount, SchemePlan
from schemes.selectors import get_redemption_eligibility_summary
from schemes.services import create_customer, enroll_customer
from schemes.tests.grade_helpers import enrolment_grade_kwargs


def make_eligibility_fixture():
    customer = create_customer(
        full_name="Eligibility Customer",
        email="eligibility@example.com",
        mobile_number="9000000088",
        password="customer-password-strong",
    )
    plan = SchemePlan.objects.create(
        name="Eligibility Plan",
        code="ELIGIBILITY-PLAN",
        amount_rule=SchemePlan.AmountRule.VARIABLE,
        frequency_rule=SchemePlan.FrequencyRule.FLEXIBLE,
        minimum_contribution=Decimal("100.00"),
        maximum_contribution=Decimal("100000.00"),
    )
    return customer, plan


def make_account(*, customer, plan, eligible_from, status=SchemeAccount.Status.ACTIVE):
    account = enroll_customer(
        customer=customer,
        plan=plan,
        **enrolment_grade_kwargs(plan, SchemeAccount.SavingsMode.GOLD),
        start_date=date(2025, 1, 1),
    )
    account.eligible_from = eligible_from
    account.status = status
    account.save(update_fields=["eligible_from", "status"])
    return account


class RedemptionEligibilitySelectorTests(TestCase):
    def setUp(self):
        self.as_of = date(2026, 8, 18)
        self.customer, self.plan = make_eligibility_fixture()

    def test_windows_are_exclusive_and_include_boundaries(self):
        expected = {
            "eligible_now": [self.as_of - timedelta(days=1), self.as_of],
            "next_30_days": [
                self.as_of + timedelta(days=1),
                self.as_of + timedelta(days=30),
            ],
            "next_60_days": [
                self.as_of + timedelta(days=31),
                self.as_of + timedelta(days=60),
            ],
            "next_90_days": [
                self.as_of + timedelta(days=61),
                self.as_of + timedelta(days=90),
            ],
            "later": [self.as_of + timedelta(days=91)],
        }
        created_ids = set()
        for dates in expected.values():
            for eligible_from in dates:
                account = make_account(
                    customer=self.customer,
                    plan=self.plan,
                    eligible_from=eligible_from,
                )
                created_ids.add(account.pk)

        summary = get_redemption_eligibility_summary(as_of=self.as_of)

        grouped_ids = set()
        for field_name, dates in expected.items():
            accounts = getattr(summary, field_name)
            self.assertEqual(
                [account.eligible_from for account in accounts],
                dates,
            )
            grouped_ids.update(account.pk for account in accounts)
        self.assertEqual(grouped_ids, created_ids)
        self.assertEqual(summary.eligible_now_count, 2)
        self.assertEqual(summary.next_30_days_count, 2)
        self.assertEqual(summary.next_60_days_count, 2)
        self.assertEqual(summary.next_90_days_count, 2)

    def test_redeemed_account_is_excluded_from_open_windows(self):
        redeemed = make_account(
            customer=self.customer,
            plan=self.plan,
            eligible_from=self.as_of - timedelta(days=10),
            status=SchemeAccount.Status.REDEEMED,
        )
        summary = get_redemption_eligibility_summary(as_of=self.as_of)
        self.assertNotIn(redeemed, summary.eligible_now)
        self.assertEqual(summary.redeemed, (redeemed,))

    def test_effective_status_is_date_derived_without_database_mutation(self):
        account = make_account(
            customer=self.customer,
            plan=self.plan,
            eligible_from=self.as_of,
        )
        with patch("schemes.models.timezone.localdate", return_value=self.as_of):
            self.assertEqual(
                account.effective_status,
                SchemeAccount.Status.REDEMPTION_ELIGIBLE,
            )
        account.refresh_from_db()
        self.assertEqual(account.status, SchemeAccount.Status.ACTIVE)

    def test_future_account_uses_not_yet_eligible_language(self):
        account = make_account(
            customer=self.customer,
            plan=self.plan,
            eligible_from=self.as_of + timedelta(days=1),
        )
        with patch("schemes.models.timezone.localdate", return_value=self.as_of):
            self.assertEqual(
                account.effective_status_label,
                "Active — not yet eligible",
            )


@override_settings(DEBUG=True)
class RedemptionEligibilityViewTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(
            username="eligibility-owner@example.com",
            email="eligibility-owner@example.com",
            password="owner-password-strong",
            role=get_user_model().Role.OWNER,
        )
        self.customer, self.plan = make_eligibility_fixture()
        self.eligible = make_account(
            customer=self.customer,
            plan=self.plan,
            eligible_from=timezone.localdate(),
        )
        self.upcoming = make_account(
            customer=self.customer,
            plan=self.plan,
            eligible_from=timezone.localdate() + timedelta(days=30),
        )

    def test_owner_dashboard_shows_eligibility_counts(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse("schemes:owner_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["eligibility"].eligible_now_count, 1)
        self.assertEqual(response.context["eligibility"].next_30_days_count, 1)
        self.assertContains(response, "Redemption eligibility")
        self.assertContains(response, "View accounts")

    def test_owner_can_review_grouped_accounts(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse("schemes:redemption_eligibility"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Eligible now")
        self.assertContains(response, "Next 30 days")
        self.assertContains(response, self.eligible.scheme_number)
        self.assertContains(response, self.upcoming.scheme_number)
        self.assertContains(response, self.customer.full_name, count=2)

    def test_customer_cannot_view_owner_eligibility(self):
        self.client.force_login(self.customer.user)
        response = self.client.get(reverse("schemes:redemption_eligibility"))
        self.assertEqual(response.status_code, 403)

    def test_customer_sees_eligible_status_without_account_closure(self):
        self.client.force_login(self.customer.user)
        response = self.client.get(
            reverse("schemes:my_scheme_detail", args=[self.eligible.scheme_number])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Redemption eligible")
        self.assertContains(response, "remains open until the store completes a redemption")
        self.eligible.refresh_from_db()
        self.assertEqual(self.eligible.status, SchemeAccount.Status.ACTIVE)
