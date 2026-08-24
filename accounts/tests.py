from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
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
        self.assertContains(response, "Public signup is not available")
        self.assertContains(response, 'class="auth-shell"')


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
