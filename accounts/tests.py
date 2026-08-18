from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse


class AuthenticationSmokeTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="customer@example.com",
            email="customer@example.com",
            password="correct-horse-battery-staple",
        )

    def test_email_login_and_logout(self):
        response = self.client.post(
            reverse("account_login"),
            {"login": self.user.email, "password": "correct-horse-battery-staple"},
        )
        self.assertRedirects(response, reverse("schemes:post_login"), fetch_redirect_response=False)

        response = self.client.post(reverse("account_logout"))
        self.assertRedirects(response, reverse("home"), fetch_redirect_response=False)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_password_reset_sends_email(self):
        response = self.client.post(
            reverse("account_reset_password"), {"email": self.user.email}
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)

    def test_public_signup_is_closed(self):
        response = self.client.get(reverse("account_signup"))
        self.assertContains(response, "Sign Up Closed")
