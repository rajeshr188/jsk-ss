from io import StringIO

from allauth.account.models import EmailAddress
from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.models import SocialAccount, SocialLogin, SocialToken
from allauth.socialaccount.providers.base import AuthProcess
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.middleware import SessionMiddleware
from django.core.management import call_command
from django.core.management.base import CommandError
from django.core.exceptions import ValidationError
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from accounts.adapters import SocialAccountAdapter
from accounts.checks import customer_google_login_configuration
from schemes.models import Customer


GOOGLE_SETTINGS = {
    "CUSTOMER_GOOGLE_LOGIN_ENABLED": True,
    "SOCIALACCOUNT_PROVIDERS": {
        "google": {
            "SCOPE": ["profile", "email"],
            "AUTH_PARAMS": {
                "access_type": "online",
                "prompt": "select_account",
            },
            "APP": {
                "client_id": "test-client.apps.googleusercontent.com",
                "secret": "test-secret",
                "key": "",
            }
        }
    },
}


@override_settings(**GOOGLE_SETTINGS)
class CustomerGoogleAccountAdapterTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.adapter = SocialAccountAdapter()
        self.user_model = get_user_model()
        self.customer = self.user_model.objects.create_user(
            username="customer@example.com",
            email="customer@example.com",
            password="strong-customer-password",
            role=self.user_model.Role.CUSTOMER,
        )
        EmailAddress.objects.create(
            user=self.customer,
            email=self.customer.email,
            verified=True,
            primary=True,
        )
        self.create_customer_profile(self.customer, "CUS-GOOGLE-1")

    @staticmethod
    def create_customer_profile(user, number):
        return Customer.objects.create(
            user=user,
            customer_number=number,
            full_name="Google Test Customer",
            mobile_number=f"90000{number[-5:]}",
            email=user.email,
        )

    def request(self, user=None):
        request = self.factory.get("/")
        SessionMiddleware(lambda value: value).process_request(request)
        request.session.save()
        request._messages = FallbackStorage(request)
        request.user = user or AnonymousUser()
        return request

    def social_login(self, *, email="customer@example.com", verified=True, user=None):
        local_user = user or self.user_model()
        return SocialLogin(
            user=local_user,
            account=SocialAccount(
                provider="google",
                uid="google-subject-123",
                user=local_user,
            ),
            email_addresses=[EmailAddress(email=email, verified=verified)],
        )

    def test_social_signup_is_always_closed(self):
        self.assertFalse(
            self.adapter.is_open_for_signup(
                self.request(),
                self.social_login(),
            )
        )

    def test_customer_may_connect_only_exact_verified_email(self):
        sociallogin = self.social_login(email="CUSTOMER@example.com")
        sociallogin.state = {"process": AuthProcess.CONNECT}

        self.adapter.pre_social_login(self.request(self.customer), sociallogin)

    def test_unverified_or_different_google_email_is_rejected(self):
        for email, verified in (
            ("different@example.com", True),
            (self.customer.email, False),
        ):
            with self.subTest(email=email, verified=verified):
                sociallogin = self.social_login(email=email, verified=verified)
                sociallogin.state = {"process": AuthProcess.CONNECT}
                with self.assertRaises(ImmediateHttpResponse) as raised:
                    self.adapter.pre_social_login(
                        self.request(self.customer), sociallogin
                    )
                self.assertEqual(
                    raised.exception.response.url,
                    reverse("socialaccount_connections"),
                )

    def test_owner_staff_and_customer_without_password_cannot_connect(self):
        owner = self.user_model.objects.create_user(
            username="owner@example.com",
            email="owner@example.com",
            password="strong-owner-password",
            role=self.user_model.Role.OWNER,
        )
        staff_customer = self.user_model.objects.create_user(
            username="staff-customer@example.com",
            email="staff-customer@example.com",
            password="strong-staff-password",
            role=self.user_model.Role.CUSTOMER,
            is_staff=True,
        )
        no_password = self.user_model.objects.create_user(
            username="no-password@example.com",
            email="no-password@example.com",
            role=self.user_model.Role.CUSTOMER,
        )
        no_password.set_unusable_password()
        no_password.save(update_fields=["password"])
        self.create_customer_profile(staff_customer, "CUS-GOOGLE-2")
        self.create_customer_profile(no_password, "CUS-GOOGLE-3")

        for user in (owner, staff_customer, no_password):
            with self.subTest(user=user.email):
                sociallogin = self.social_login(email=user.email)
                sociallogin.state = {"process": AuthProcess.CONNECT}
                with self.assertRaises(ImmediateHttpResponse):
                    self.adapter.pre_social_login(self.request(user), sociallogin)

    def test_customer_role_without_approved_profile_cannot_connect(self):
        user = self.user_model.objects.create_user(
            username="role-only@example.com",
            email="role-only@example.com",
            password="strong-role-only-password",
            role=self.user_model.Role.CUSTOMER,
        )
        EmailAddress.objects.create(
            user=user,
            email=user.email,
            verified=True,
            primary=True,
        )
        sociallogin = self.social_login(email=user.email)
        sociallogin.state = {"process": AuthProcess.CONNECT}

        with self.assertRaises(ImmediateHttpResponse):
            self.adapter.pre_social_login(self.request(user), sociallogin)

    def test_unconnected_google_login_never_matches_local_email(self):
        sociallogin = self.social_login()
        sociallogin.state = {"process": AuthProcess.LOGIN}

        with self.assertRaises(ImmediateHttpResponse) as raised:
            self.adapter.pre_social_login(self.request(), sociallogin)

        self.assertEqual(raised.exception.response.url, reverse("account_login"))

    def test_connected_active_customer_can_login_by_provider_uid(self):
        account = SocialAccount.objects.create(
            user=self.customer,
            provider="google",
            uid="google-subject-123",
        )
        sociallogin = SocialLogin(user=self.customer, account=account)
        sociallogin.state = {"process": AuthProcess.LOGIN}

        self.adapter.pre_social_login(self.request(), sociallogin)

    def test_connected_non_customer_or_inactive_customer_cannot_login(self):
        for role, active in (
            (self.user_model.Role.OWNER, True),
            (self.user_model.Role.CUSTOMER, False),
        ):
            user = self.user_model.objects.create_user(
                username=f"blocked-{role}-{active}@example.com",
                email=f"blocked-{role}-{active}@example.com",
                password="strong-blocked-password",
                role=role,
                is_active=active,
            )
            EmailAddress.objects.create(
                user=user,
                email=user.email,
                verified=True,
                primary=True,
            )
            if role == self.user_model.Role.CUSTOMER:
                self.create_customer_profile(user, "CUS-GOOGLE-4")
            account = SocialAccount.objects.create(
                user=user,
                provider="google",
                uid=f"google-{role}-{active}",
            )
            sociallogin = SocialLogin(user=user, account=account)
            sociallogin.state = {"process": AuthProcess.LOGIN}

            with self.subTest(role=role, active=active):
                with self.assertRaises(ImmediateHttpResponse):
                    self.adapter.pre_social_login(self.request(), sociallogin)

    @override_settings(CUSTOMER_GOOGLE_LOGIN_ENABLED=False)
    def test_feature_switch_blocks_an_existing_google_login(self):
        account = SocialAccount.objects.create(
            user=self.customer,
            provider="google",
            uid="google-subject-123",
        )
        sociallogin = SocialLogin(user=self.customer, account=account)
        sociallogin.state = {"process": AuthProcess.LOGIN}

        with self.assertRaises(ImmediateHttpResponse):
            self.adapter.pre_social_login(self.request(), sociallogin)

    def test_online_disconnect_is_blocked(self):
        account = SocialAccount.objects.create(
            user=self.customer,
            provider="google",
            uid="google-subject-123",
        )

        with self.assertRaisesMessage(ValidationError, "cannot be removed online yet"):
            self.adapter.validate_disconnect(account, [account])


class CustomerGoogleLoginInterfaceTests(TestCase):
    def setUp(self):
        self.user_model = get_user_model()
        self.customer = self.user_model.objects.create_user(
            username="customer@example.com",
            email="customer@example.com",
            password="strong-customer-password",
            role=self.user_model.Role.CUSTOMER,
        )
        EmailAddress.objects.create(
            user=self.customer,
            email=self.customer.email,
            verified=True,
            primary=True,
        )
        Customer.objects.create(
            user=self.customer,
            customer_number="CUS-GOOGLE-UI",
            full_name="Google Interface Customer",
            mobile_number="9000000001",
            email=self.customer.email,
        )

    def test_google_action_is_hidden_while_disabled(self):
        response = self.client.get(reverse("account_login"))

        self.assertNotContains(response, "Continue with Google")

    def test_google_provider_routes_are_not_available_while_disabled(self):
        response = self.client.post(reverse("google_login"))

        self.assertEqual(response.status_code, 404)

    @override_settings(**GOOGLE_SETTINGS)
    def test_google_login_and_customer_connection_actions_are_visible(self):
        response = self.client.get(reverse("account_login"))
        self.assertContains(response, "Continue with Google")
        self.assertContains(response, 'method="post"')

        self.client.force_login(self.customer)
        connections = self.client.get(reverse("socialaccount_connections"))
        self.assertContains(connections, "Connect Google account")
        self.assertContains(connections, self.customer.email)

    @override_settings(**GOOGLE_SETTINGS)
    def test_connections_page_does_not_offer_online_removal(self):
        account = SocialAccount.objects.create(
            user=self.customer,
            provider="google",
            uid="google-subject-123",
        )
        self.client.force_login(self.customer)

        response = self.client.get(reverse("socialaccount_connections"))

        self.assertContains(response, "Google is connected")
        self.assertNotContains(response, "Remove")

        rejected = self.client.post(
            reverse("socialaccount_connections"),
            {"account": account.pk},
        )
        self.assertContains(rejected, "cannot be removed online yet")
        self.assertTrue(SocialAccount.objects.filter(pk=account.pk).exists())


class CustomerGoogleLoginConfigurationTests(TestCase):
    def test_security_check_rejects_email_auto_linking(self):
        with override_settings(SOCIALACCOUNT_EMAIL_AUTHENTICATION=True):
            issues = customer_google_login_configuration(None)

        self.assertIn("jsk.E021", {issue.id for issue in issues})

    def test_security_check_rejects_additional_google_scope(self):
        with override_settings(
            SOCIALACCOUNT_PROVIDERS={
                "google": {"SCOPE": ["profile", "email", "calendar"]}
            }
        ):
            issues = customer_google_login_configuration(None)

        self.assertIn("jsk.E024", {issue.id for issue in issues})

    @override_settings(**GOOGLE_SETTINGS)
    def test_integrity_command_accepts_valid_customer_link_without_tokens(self):
        user_model = get_user_model()
        customer = user_model.objects.create_user(
            username="linked@example.com",
            email="linked@example.com",
            password="strong-linked-password",
            role=user_model.Role.CUSTOMER,
        )
        SocialAccount.objects.create(
            user=customer,
            provider="google",
            uid="google-subject-123",
        )
        EmailAddress.objects.create(
            user=customer,
            email=customer.email,
            verified=True,
            primary=True,
        )
        Customer.objects.create(
            user=customer,
            customer_number="CUS-GOOGLE-CHECK",
            full_name="Google Integrity Customer",
            mobile_number="9000000002",
            email=customer.email,
        )
        output = StringIO()

        call_command("check_customer_google_login", stdout=output)

        self.assertIn("status=ok", output.getvalue())
        self.assertIn("linked_customers=1", output.getvalue())
        self.assertFalse(SocialToken.objects.exists())

    def test_integrity_command_rejects_privileged_identity_link(self):
        owner = get_user_model().objects.create_user(
            username="owner@example.com",
            email="owner@example.com",
            password="strong-owner-password",
            role=get_user_model().Role.OWNER,
        )
        SocialAccount.objects.create(
            user=owner,
            provider="google",
            uid="google-owner-subject",
        )

        with self.assertRaises(CommandError):
            call_command("check_customer_google_login", stdout=StringIO())
