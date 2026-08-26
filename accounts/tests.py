from datetime import timedelta
from unittest.mock import patch

from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core import mail
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import CustomerInvitation
from accounts.services import issue_customer_invitation, send_customer_invitation


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
        self.assertEqual(mail.outbox[0].extra_headers["X-PM-TrackLinks"], "None")
        self.assertEqual(mail.outbox[0].extra_headers["X-PM-TrackOpens"], "false")

    def test_public_signup_is_closed(self):
        response = self.client.get(reverse("account_signup"))
        self.assertContains(response, "Sign Up Closed")
        self.assertContains(response, "Public signup is not available")
        self.assertContains(response, 'class="auth-shell"')

    def test_password_reset_token_response_is_not_cacheable_or_referrable(self):
        response = self.client.get("/accounts/password/reset/key/not-a-real-token/")

        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertEqual(response["Pragma"], "no-cache")
        self.assertEqual(response["Referrer-Policy"], "no-referrer")


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    CUSTOMER_INVITATION_EXPIRY_HOURS=72,
)
class CustomerInvitationTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(
            username="owner@example.com",
            email="owner@example.com",
            password="owner-password-strong",
            role=user_model.Role.OWNER,
        )
        self.customer = user_model.objects.create_user(
            username="invited@example.com",
            email="invited@example.com",
            role=user_model.Role.CUSTOMER,
        )
        self.customer.set_unusable_password()
        self.customer.save(update_fields=["password"])

    def issue(self):
        return issue_customer_invitation(
            user=self.customer,
            created_by=self.owner,
        )

    def invitation_url(self, invitation, raw_token):
        return reverse(
            "customer_invitation_accept",
            kwargs={"invitation_id": invitation.pk, "token": raw_token},
        )

    def test_invitation_stores_only_a_digest_and_email_uses_direct_untracked_url(self):
        invitation, raw_token = self.issue()
        setup_url = f"https://jaishrikrishnajewellery.com{self.invitation_url(invitation, raw_token)}"

        sent = send_customer_invitation(
            invitation=invitation,
            raw_token=raw_token,
            setup_url=setup_url,
        )

        self.assertTrue(sent)
        self.assertNotEqual(invitation.token_digest, raw_token)
        self.assertNotIn(raw_token, str(invitation.__dict__))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(setup_url, mail.outbox[0].body)
        self.assertEqual(mail.outbox[0].extra_headers["X-PM-TrackLinks"], "None")
        self.assertEqual(mail.outbox[0].extra_headers["X-PM-TrackOpens"], "false")

    def test_customer_sets_password_once_without_being_enrolled(self):
        invitation, raw_token = self.issue()
        url = self.invitation_url(invitation, raw_token)

        get_response = self.client.get(url)
        self.assertEqual(get_response.status_code, 200)
        self.assertEqual(get_response["Cache-Control"], "no-store")
        self.assertEqual(get_response["Referrer-Policy"], "no-referrer")

        response = self.client.post(
            url,
            {
                "new_password1": "customer-password-strong",
                "new_password2": "customer-password-strong",
            },
        )

        self.assertRedirects(response, reverse("account_login"))
        self.customer.refresh_from_db()
        invitation.refresh_from_db()
        self.assertTrue(self.customer.check_password("customer-password-strong"))
        self.assertIsNotNone(invitation.accepted_at)
        self.assertTrue(
            EmailAddress.objects.filter(
                user=self.customer,
                email=self.customer.email,
                primary=True,
                verified=True,
            ).exists()
        )
        self.assertContains(self.client.get(url), "Invitation unavailable")

    def test_new_invitation_supersedes_old_token(self):
        first, first_token = self.issue()
        second, second_token = self.issue()

        first.refresh_from_db()
        self.assertIsNotNone(first.revoked_at)
        self.assertContains(
            self.client.get(self.invitation_url(first, first_token)),
            "Invitation unavailable",
        )
        self.assertContains(
            self.client.get(self.invitation_url(second, second_token)),
            "Set up your login",
        )

    def test_expired_invitation_is_rejected(self):
        invitation, raw_token = self.issue()
        invitation.expires_at = timezone.now() - timedelta(seconds=1)
        invitation.save(update_fields=["expires_at"])

        response = self.client.get(self.invitation_url(invitation, raw_token))

        self.assertContains(response, "Invitation unavailable")

    def test_non_owner_cannot_issue_an_invitation(self):
        with self.assertRaisesMessage(ValidationError, "Only an active owner"):
            issue_customer_invitation(
                user=self.customer,
                created_by=self.customer,
            )

    def test_delivery_failure_records_only_error_type_and_can_be_retried(self):
        invitation, raw_token = self.issue()
        with patch(
            "accounts.services.EmailMultiAlternatives.send",
            side_effect=RuntimeError("secret provider detail"),
        ):
            sent = send_customer_invitation(
                invitation=invitation,
                raw_token=raw_token,
                setup_url="https://jaishrikrishnajewellery.com/setup/secret-token/",
            )

        self.assertFalse(sent)
        invitation.refresh_from_db()
        self.assertEqual(invitation.delivery_error, "RuntimeError")
        self.assertNotIn("secret provider detail", invitation.delivery_error)
        self.assertTrue(
            send_customer_invitation(
                invitation=invitation,
                raw_token=raw_token,
                setup_url="https://jaishrikrishnajewellery.com/setup/secret-token/",
            )
        )

    def test_customer_with_password_must_use_password_reset(self):
        self.customer.set_password("already-active-password")
        self.customer.save(update_fields=["password"])

        with self.assertRaisesMessage(ValidationError, "password reset"):
            self.issue()


class AuthEmailConstraintTests(TestCase):
    def test_nonblank_email_is_unique_case_insensitively(self):
        user_model = get_user_model()
        user_model.objects.create_user(
            username="first@example.com",
            email="Customer@Example.com",
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            user_model.objects.create_user(
                username="second@example.com",
                email="customer@example.com",
            )


class WagtailAdminAccessTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.customer = user_model.objects.create_user(
            username="cms-customer@example.com",
            email="cms-customer@example.com",
            password="correct-horse-battery-staple",
            role=user_model.Role.CUSTOMER,
        )
        self.owner_without_cms_permission = user_model.objects.create_user(
            username="owner-without-cms@example.com",
            email="owner-without-cms@example.com",
            password="correct-horse-battery-staple",
            role=user_model.Role.OWNER,
            is_staff=True,
        )
        self.cms_editor = user_model.objects.create_user(
            username="cms-editor@example.com",
            email="cms-editor@example.com",
            password="correct-horse-battery-staple",
            role=user_model.Role.STAFF,
            is_staff=True,
        )
        self.cms_editor.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="wagtailadmin",
                codename="access_admin",
            )
        )

    def assert_cms_login_redirect(self, user):
        self.client.force_login(user)
        response = self.client.get(reverse("wagtailadmin_home"))
        expected = (
            f'{reverse("wagtailadmin_login")}?next={reverse("wagtailadmin_home")}'
        )
        self.assertRedirects(response, expected, fetch_redirect_response=False)

    def test_customer_cannot_access_wagtail_admin(self):
        self.assert_cms_login_redirect(self.customer)

    def test_owner_role_alone_does_not_grant_wagtail_admin_access(self):
        self.assert_cms_login_redirect(self.owner_without_cms_permission)

    def test_explicitly_authorized_staff_user_can_access_wagtail_admin(self):
        login_response = self.client.post(
            reverse("wagtailadmin_login"),
            {
                "username": self.cms_editor.username,
                "password": "correct-horse-battery-staple",
            },
        )
        self.assertRedirects(
            login_response,
            reverse("wagtailadmin_home"),
            fetch_redirect_response=False,
        )

        response = self.client.get(reverse("wagtailadmin_home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Jai Sri Krishna Jewelley Catalogue")

    def test_existing_django_routes_keep_precedence(self):
        self.assertEqual(reverse("admin:index"), "/admin/")
        self.assertEqual(reverse("wagtailadmin_home"), "/cms/")
        self.assertEqual(self.client.get(reverse("home")).status_code, 200)
