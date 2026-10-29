"""Opt-in disposable B4/P4 walkthrough, never an application management command.

Run with --synthetic-local; add --check-only to seed/check/clean without a server.
Add --publication-journey to start from draft offers instead of synthetic agreements.
Only a newly created random loopback PostgreSQL database can be used or removed.
"""
import copy
import os
import secrets
import socket
import sys
import tempfile
import uuid
from socketserver import ThreadingMixIn
from wsgiref.simple_server import WSGIServer
from contextlib import ExitStack
from datetime import datetime, time
from decimal import Decimal
from io import StringIO
from time import monotonic
from unittest.mock import patch

from schemes.rehearse_workflow_release import require, validate_database

PORT = 8766
PUBLICATION_PORT = 8767


class ReviewServer(ThreadingMixIn, WSGIServer):
    # Browsers may preconnect without sending a request. One such connection must
    # not block all pages or prevent the review lifetime/cleanup loop from running.
    daemon_threads = True

    def get_request(self):
        request, address = super().get_request()
        request.settimeout(30)
        return request, address


def parse_arguments(arguments):
    require(bool(arguments) and arguments[0] == "--synthetic-local"
            and len(arguments) == len(set(arguments))
            and set(arguments) <= {"--synthetic-local", "--check-only", "--publication-journey"},
            "Explicit --synthetic-local required; no database/host overrides allowed.")
    return "--check-only" in arguments


def seed_review_identities(password, label):
    from allauth.account.models import EmailAddress
    from accounts.models import CustomUser

    from schemes.services import create_customer

    owner = CustomUser.objects.create_user(username="review-owner", email="owner@example.invalid",
                                           password=password, role="OWNER")
    customer = create_customer(full_name=f"SYNTHETIC {label} Customer", email="customer@example.invalid",
        mobile_number="9000000001", address="Local demonstration only", password=password)
    for user in (owner, customer.user):
        EmailAddress.objects.update_or_create(user=user, email=user.email,
                                              defaults=dict(verified=True, primary=True))
    return owner, customer


def seed_publication_walkthrough(password):
    """Draft offers only: no manufactured agreement, payment or publication evidence."""
    from schemes.models import MetalGrade
    from schemes.plan_configuration import (
        MONTHLY_COMPLETION_POLICY, create_configuration_version, create_configured_plan_draft,
    )
    from schemes.services import publish_scheme_rate

    owner, customer = seed_review_identities(password, "P4")
    grade = MetalGrade.objects.get(code=MetalGrade.GOLD_22K_916)
    common = dict(amount_policy="CUSTOMER_FIXED", minimum_amount=Decimal("500"),
                  maximum_amount=Decimal("10000"), amount_step=Decimal("100"))
    variants = {
        "calendar": dict(name="SYNTHETIC calendar eligibility", frequency_rule="ONCE_PER_MONTH",
                         minimum_months=12, default_months=12, allow_contributions_after_eligibility=False),
        "monthly": dict(name="SYNTHETIC monthly completion", frequency_rule="ONCE_PER_PERIOD",
                        **MONTHLY_COMPLETION_POLICY),
    }
    plans = {}
    for label, values in variants.items():
        config = create_configuration_version(values={**common, **values}, actor=owner,
                                               reason="Synthetic P4 review only")
        plans[label] = create_configured_plan_draft(configuration_id=config.pk, name=values["name"],
            code=f"P4-{label.upper()}", metal_grades=[grade], actor=owner,
            reason="Draft for isolated owner publication review")
    publish_scheme_rate(metal_grade=grade, rate_per_gram=Decimal("10000"), published_by=owner)
    return owner, customer, plans


def seed_walkthrough(password):
    """Synthetic agreements only; real services create their local financial evidence."""
    from django.utils import timezone
    from schemes.eligibility import add_calendar_months
    from schemes.instalments import AGREEMENT_TIMEZONE, prepare_instalment_periods
    from schemes.models import MetalGrade
    from schemes.plan_configuration import create_configuration_version, create_configured_plan_draft
    from schemes.services import publish_scheme_rate, record_in_store_cash_contribution
    from schemes.closures import request_scheme_closure, review_scheme_closure
    from schemes.settlements import preview_full_settlement, settle_configured_agreement
    from schemes.tests.test_instalment_schedules import monthly_values, synthetic_account

    owner, customer = seed_review_identities(password, "B4")
    grade = MetalGrade.objects.get(code=MetalGrade.GOLD_22K_916)
    config = create_configuration_version(values=monthly_values(), actor=owner, reason="Synthetic B4 review")
    plan = create_configured_plan_draft(configuration_id=config.pk, name="SYNTHETIC monthly review",
        code="B4-REVIEW", metal_grades=[grade], actor=owner, reason="Synthetic review; stays unpublished")
    start = add_calendar_months(timezone.localdate().replace(day=1), -2)
    accounts = {}
    for name in ("unused", "three-paid", "correction"):
        account = synthetic_account(customer, grade, plan, start=start)
        prepare_instalment_periods(account_id=account.pk, actor=owner, reason="Synthetic B4 schedule")
        accounts[name] = account
        if name == "unused":
            continue
        for period in account.instalment_periods.filter(number__lte=3).order_by("number"):
            instant = datetime.combine(period.starts_on, time(0, 1), AGREEMENT_TIMEZONE)
            with patch("django.utils.timezone.now", return_value=instant):
                rate = publish_scheme_rate(metal_grade=grade, rate_per_gram=Decimal("10000"), published_by=owner)
                record_in_store_cash_contribution(scheme_account=account, amount=Decimal("1000"),
                    expected_scheme_rate_id=rate.pk, received_by=owner, idempotency_key=uuid.uuid4(),
                    notes="SYNTHETIC ONLY: no cash received", audit_reason="Synthetic walkthrough")
    closure = request_scheme_closure(account_id=accounts["correction"].pk, actor=customer.user,
        reason="Synthetic correction practice", idempotency_key=uuid.uuid4())
    review_scheme_closure(request_id=closure.pk, actor=owner, action="ACCEPT",
        reason="Synthetic customer request", idempotency_key=uuid.uuid4(), expected_sequence=1)
    _, token = preview_full_settlement(request_id=closure.pk, actor=owner)
    settle_configured_agreement(request_id=closure.pk, actor=owner, preview_token=token,
        invoice_reference="DEMO-INVOICE-001", authorization_reference="DEMO-CONFIRMATION-001",
        reason="SYNTHETIC ONLY: no jewellery delivered", idempotency_key=uuid.uuid4())
    return owner, customer, accounts, closure


class ReviewBanner:
    """Visibly distinguish this disposable server without changing application templates."""
    def __init__(self, application):
        self.application = application

    def __call__(self, environ, start_response):
        captured = {}
        def capture(status, headers, exc_info=None):
            captured.update(status=status, headers=headers, exc_info=exc_info)
        response = self.application(environ, capture)
        try:
            body = b"".join(response)
        finally:
            if hasattr(response, "close"):
                response.close()
        headers = captured["headers"]
        if any(k.lower() == "content-type" and "text/html" in v for k, v in headers):
            # Insert after the body opening tag, including when it has attributes.
            position = body.find(b"<body")
            position = body.find(b">", position) if position >= 0 else -1
            if position >= 0:
                banner = (b'<div class="alert alert-warning text-center" role="note">'
                          b'SYNTHETIC LOCAL REVIEW ONLY - no real money or jewellery. '
                          b'Data is discarded when this review server stops.</div>')
                body = body[:position + 1] + banner + body[position + 1:]
            headers = [(k, v) for k, v in headers if k.lower() not in {"content-length", "cache-control"}]
            headers += [("Content-Length", str(len(body))), ("Cache-Control", "no-store")]
        start_response(captured["status"], headers, captured.get("exc_info"))
        return [body]


def main():
    check_only = parse_arguments(sys.argv[1:])
    publication_journey = "--publication-journey" in sys.argv[1:]
    port = PUBLICATION_PORT if publication_journey else PORT
    label = "P4" if publication_journey else "B4"
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_project.settings")
    from django.conf import settings
    original = copy.deepcopy(settings.DATABASES["default"])
    validate_database(original)
    database_prefix = f"jsk_{label.lower()}_review_"
    name = database_prefix + uuid.uuid4().hex
    require(name != original["NAME"], "Application database cannot be targeted.")
    settings.DATABASES["default"]["NAME"] = name
    settings.SECRET_KEY = secrets.token_urlsafe(48)
    settings.DEBUG = False
    settings.MIDDLEWARE = [item for item in settings.MIDDLEWARE if not item.startswith("debug_toolbar.")]
    settings.APP_RELEASE = f"SYNTHETIC-{label}-LOCAL"
    settings.ALLOWED_HOSTS = ["127.0.0.1", "localhost", "testserver"]
    settings.SECURE_SSL_REDIRECT = False
    settings.SECURE_HSTS_SECONDS = 0
    settings.SECURE_PROXY_SSL_HEADER = None
    settings.CSRF_COOKIE_SECURE = settings.SESSION_COOKIE_SECURE = False
    settings.CSRF_COOKIE_DOMAIN = settings.SESSION_COOKIE_DOMAIN = None
    settings.CSRF_COOKIE_NAME = f"{label.lower()}_review_csrf"
    settings.SESSION_COOKIE_NAME = f"{label.lower()}_review_session"
    settings.CSRF_TRUSTED_ORIGINS = [f"http://127.0.0.1:{port}"]
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    settings.EMAIL_HOST_PASSWORD = ""
    settings.PAYMENT_GATEWAY = ""
    settings.RAZORPAY_KEY_ID = settings.RAZORPAY_KEY_SECRET = settings.RAZORPAY_WEBHOOK_SECRET = ""
    settings.RAZORPAY_MODE = ""
    settings.IN_STORE_CASH_CONTRIBUTIONS_ENABLED = True
    # Process-only gates on the freshly created database, never environment-file edits.
    settings.CONFIGURED_PLANS_ENABLED = publication_journey
    settings.CUSTOMER_ENROLMENT_REQUESTS_ENABLED = publication_journey
    settings.CUSTOMER_ENROLMENT_REQUEST_DISCLOSURE_VERSION = "SYNTHETIC-LOCAL-ONLY"
    for flag in ("PWA_ENABLED", "ANDROID_TWA_ASSET_LINKS_ENABLED", "CUSTOMER_GOOGLE_LOGIN_ENABLED",
                 "PUBLIC_CUSTOMER_REGISTRATION_ENABLED", "SCHEME_REMINDERS_ENABLED"):
        setattr(settings, flag, False)
    settings.CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
    settings.STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "renditions": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
    import django
    django.setup()
    import psycopg
    from psycopg import sql
    from django.core.management import call_command
    from django.core.wsgi import get_wsgi_application
    from django.contrib.staticfiles.handlers import StaticFilesHandler
    from django.db import connections
    from django.test import Client
    from django.urls import reverse
    from wsgiref.simple_server import make_server

    args = dict(host=original["HOST"], port=original["PORT"] or 5432,
                user=original["USER"], password=original["PASSWORD"], connect_timeout=5)
    real_connect = socket.socket.connect
    def isolated_connect(sock, address):
        require(isinstance(address, tuple) and address[0] in {"localhost", "127.0.0.1", "::1"}
                and address[1] == int(args["port"]), "Review server blocked outbound network access.")
        return real_connect(sock, address)

    created = False
    try:
        with ExitStack() as stack:
            stack.enter_context(patch.object(socket.socket, "connect", isolated_connect))
            directory = stack.enter_context(tempfile.TemporaryDirectory(prefix=f"jsk-{label.lower()}-media-"))
            settings.MEDIA_ROOT = directory
            with psycopg.connect(dbname="postgres", autocommit=True, **args) as admin:
                admin.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(sql.Identifier(name)))
            created = True
            print(f"isolated_database={name} ordinary_database_untouched=true", flush=True)
            call_command("migrate", interactive=False, verbosity=0, stdout=StringIO())
            password = secrets.token_urlsafe(18)
            accounts, plans = {}, {}
            if publication_journey:
                owner, customer, plans = seed_publication_walkthrough(password)
                from schemes.models import Contribution, MetalAllocation, Redemption, SchemeAccount, SchemeEnrolmentRequest
                require(not any(model.objects.exists() for model in
                    (SchemeAccount, SchemeEnrolmentRequest, Contribution, MetalAllocation, Redemption)),
                    "Publication review must start without agreements or financial history.")
                call_command("check_plan_configurations")
            else:
                owner, customer, accounts, closure = seed_walkthrough(password)
            call_command("check_scheme_closures")
            call_command("check_instalment_payments")
            client = Client()
            for user in (owner, customer.user):
                client.force_login(user)
                for account in accounts.values():
                    for route in ("closure_workspace", "scheme_statement"):
                        response = client.get(reverse("schemes:" + route, args=[account.scheme_number]))
                        require(response.status_code == 200, "Walkthrough page did not render.")
                for plan in plans.values():
                    response = client.get(reverse("schemes:configured_plan_publication", args=[plan.pk]))
                    require(response.status_code == (200 if user == owner else 403),
                            "Publication page role boundary failed.")
                client.logout()
            print(f"seed_and_private_pages=PASS isolated_publication_enabled={str(publication_journey).lower()} "
                  "ordinary_database_untouched=true", flush=True)
            if check_only:
                return
            with make_server("127.0.0.1", port, ReviewBanner(StaticFilesHandler(get_wsgi_application())),
                             server_class=ReviewServer) as server:
                base_url = f"http://127.0.0.1:{port}"
                print(f"REVIEW: {base_url}/accounts/login/", flush=True)
                print(f"Owner: owner@example.invalid | Customer: customer@example.invalid | Temporary password: {password}", flush=True)
                for account_label, account in accounts.items():
                    print(f"{account_label}: {base_url}" + reverse("schemes:closure_workspace", args=[account.scheme_number]), flush=True)
                if publication_journey:
                    for plan_label, plan in plans.items():
                        print(f"{plan_label} publication: {base_url}" + reverse("schemes:configured_plan_publication", args=[plan.pk]), flush=True)
                    print(f"Customer offers: {base_url}" + reverse("pricing"), flush=True)
                    print(f"Owner requests: {base_url}" + reverse("schemes:owner_enrolment_request_list"), flush=True)
                    print("Start with draft publication; no agreements/payments were seeded. "
                          "Choose INR 1000 and 12 months; use synthetic cash only. "
                          "Email stays in memory; inbox delivery is not part of this review.", flush=True)
                else:
                    print(f"correction settlement: {base_url}" + reverse("schemes:configured_settlement", args=[closure.pk]), flush=True)
                print("Ctrl+C stops and removes this synthetic database. Automatic stop after four hours.", flush=True)
                server.timeout = 1
                deadline = monotonic() + 4 * 60 * 60
                while monotonic() < deadline:
                    server.handle_request()
    except KeyboardInterrupt:
        pass
    finally:
        connections.close_all()
        if created:
            require(name.startswith(database_prefix) and name != original["NAME"], "Unsafe cleanup target.")
            with psycopg.connect(dbname="postgres", autocommit=True, **args) as admin:
                admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))
            print("cleanup=ok synthetic_review_database_removed=true ordinary_database_untouched=true", flush=True)


if __name__ == "__main__":
    main()
