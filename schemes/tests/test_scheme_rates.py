from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from schemes.models import AuditEvent, SchemeRate
from schemes.selectors import get_current_scheme_rate
from schemes.services import publish_scheme_rate


class SchemeRatePublicationTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(
            username="owner-rates@example.com",
            email="owner-rates@example.com",
            password="owner-password-strong",
            role=user_model.Role.OWNER,
        )
        self.customer = user_model.objects.create_user(
            username="customer-rates@example.com",
            email="customer-rates@example.com",
            password="customer-password-strong",
            role=user_model.Role.CUSTOMER,
        )
        self.staff = user_model.objects.create_user(
            username="staff-rates@example.com",
            email="staff-rates@example.com",
            password="staff-password-strong",
            role=user_model.Role.STAFF,
        )

    def test_owner_can_publish_gold_and_silver_rates_with_fixed_purity(self):
        gold = publish_scheme_rate(
            metal=SchemeRate.Metal.GOLD,
            rate_per_gram=Decimal("12500.0000"),
            published_by=self.owner,
            notes="Morning rate",
        )
        silver = publish_scheme_rate(
            metal=SchemeRate.Metal.SILVER,
            rate_per_gram=Decimal("150.0000"),
            published_by=self.owner,
        )

        self.assertEqual(gold.purity, Decimal("0.9999"))
        self.assertEqual(silver.purity, Decimal("0.9990"))
        self.assertEqual(gold.notes, "Morning rate")
        self.assertEqual(
            AuditEvent.objects.filter(
                action=AuditEvent.Action.SCHEME_RATE_PUBLICATION
            ).count(),
            2,
        )

    def test_customer_and_staff_cannot_publish(self):
        for user in (self.customer, self.staff):
            with self.subTest(role=user.role):
                with self.assertRaisesMessage(ValidationError, "active owner"):
                    publish_scheme_rate(
                        metal=SchemeRate.Metal.GOLD,
                        rate_per_gram=Decimal("12500.0000"),
                        published_by=user,
                    )
        self.assertFalse(SchemeRate.objects.exists())

    def test_zero_negative_and_invalid_rates_are_rejected(self):
        for invalid in (Decimal("0"), Decimal("-1"), "not-a-rate"):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValidationError):
                    publish_scheme_rate(
                        metal=SchemeRate.Metal.GOLD,
                        rate_per_gram=invalid,
                        published_by=self.owner,
                    )

    def test_new_publication_does_not_mutate_old_publication(self):
        old = publish_scheme_rate(
            metal=SchemeRate.Metal.GOLD,
            rate_per_gram=Decimal("12500.0000"),
            published_by=self.owner,
        )
        new = publish_scheme_rate(
            metal=SchemeRate.Metal.GOLD,
            rate_per_gram=Decimal("12600.0000"),
            published_by=self.owner,
        )
        old.refresh_from_db()
        self.assertNotEqual(old.pk, new.pk)
        self.assertEqual(old.rate_per_gram, Decimal("12500.0000"))
        self.assertEqual(get_current_scheme_rate(SchemeRate.Metal.GOLD), new)

    def test_latest_applicable_rate_ignores_future_publication(self):
        current = publish_scheme_rate(
            metal=SchemeRate.Metal.GOLD,
            rate_per_gram=Decimal("12500.0000"),
            published_by=self.owner,
        )
        publish_scheme_rate(
            metal=SchemeRate.Metal.GOLD,
            rate_per_gram=Decimal("13000.0000"),
            published_by=self.owner,
            effective_from=timezone.now() + timedelta(hours=1),
        )
        self.assertEqual(get_current_scheme_rate(SchemeRate.Metal.GOLD), current)

    def test_owner_page_publishes_and_requires_large_change_confirmation(self):
        publish_scheme_rate(
            metal=SchemeRate.Metal.GOLD,
            rate_per_gram=Decimal("10000.0000"),
            published_by=self.owner,
        )
        self.client.force_login(self.owner)
        url = reverse("schemes:scheme_rates")

        response = self.client.post(
            url,
            {"metal": "GOLD", "rate_per_gram": "11000.0000", "notes": ""},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "exceeds 5%")
        self.assertEqual(SchemeRate.objects.count(), 1)

        response = self.client.post(
            url,
            {
                "metal": "GOLD",
                "rate_per_gram": "11000.0000",
                "notes": "Confirmed correction",
                "confirm_large_change": "on",
            },
            follow=True,
        )
        self.assertContains(response, "Published 24K Gold Scheme Rate")
        self.assertEqual(SchemeRate.objects.count(), 2)

    def test_customer_and_staff_cannot_open_owner_rate_page(self):
        for user in (self.customer, self.staff):
            self.client.force_login(user)
            response = self.client.get(reverse("schemes:scheme_rates"))
            self.assertEqual(response.status_code, 403)
