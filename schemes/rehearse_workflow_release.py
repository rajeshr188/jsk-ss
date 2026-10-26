"""Opt-in synthetic LOCAL restore/upgrade drill; never a production deploy command.

Run: uv run --env-file .env python -m schemes.rehearse_workflow_release --synthetic-local
Only two freshly created random databases are dumped/restored/migrated and removed.
No server, scheduled job, outbound email or payment provider is started.
"""

import copy
import hashlib
import json
import logging
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
from time import monotonic
import uuid
from contextlib import ExitStack
from datetime import timedelta
from decimal import Decimal
from io import StringIO
from unittest.mock import patch


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def validate_database(database):
    require(database["ENGINE"] == "django.db.backends.postgresql", "PostgreSQL required.")
    require(database["HOST"] in {"localhost", "127.0.0.1", "::1"}, "Only explicit loopback allowed.")
    require(not database.get("OPTIONS"), "Connection-option overrides are not supported.")


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def financial_snapshot():
    from schemes import models

    names = ("SchemeAccount", "Contribution", "MetalAllocation", "SchemeRate", "Redemption",
             "RedemptionReversal", "InStoreCashReceipt", "InStoreCashContributionReversal",
             "AuditEvent", "PaymentWebhookEvent")
    return {name: list(getattr(models, name).objects.order_by("pk").values()) for name in names}


def legacy_snapshot():
    from accounts.models import CustomUser, CustomerInvitation, CustomerRegistration
    from schemes.models import Customer, SchemeEnrolmentRequest

    invitations = list(CustomerInvitation.objects.order_by("pk").values(*(
        field.attname for field in CustomerInvitation._meta.concrete_fields
        if field.name != "recovery_requested_at"
    )))
    return {**financial_snapshot(), "legacy_invitations": invitations, **{
        model._meta.label: list(model.objects.order_by("pk").values())
        for model in (CustomUser, CustomerRegistration, Customer, SchemeEnrolmentRequest)
    }}


def seed_legacy(apps):
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from allauth.account.models import EmailAddress
    from accounts.models import CustomerRegistration
    from schemes.models import Contribution, MetalGrade, SchemeAccount, SchemePlan, SchemePlanOffering
    from schemes.eligibility import calculate_eligibility_date
    from schemes.services import (
        create_customer, enroll_customer, publish_scheme_rate,
        record_in_store_cash_contribution, submit_scheme_enrolment_request,
    )

    owner = get_user_model().objects.create_user(username="rehearsal-owner", role="OWNER",
                                                email="owner@example.invalid")
    customer = create_customer(full_name="Synthetic restored customer", email="customer@example.invalid",
                               mobile_number="9000000001", address="Synthetic address only",
                               password="synthetic-rehearsal-only")
    EmailAddress.objects.create(user=customer.user, email=customer.email, verified=True, primary=True)
    plan = SchemePlan.objects.create(name="Synthetic release plan", code="RESTORE-DRILL",
                                    amount_rule="VARIABLE", frequency_rule="FLEXIBLE",
                                    minimum_contribution=Decimal("500"), maximum_contribution=Decimal("5000"),
                                    active=True, publicly_listed=True)
    today = timezone.localdate()
    accounts = []
    for code, rate_value in ((MetalGrade.GOLD_22K_916, "10000"), (MetalGrade.SILVER_999, "100")):
        grade = MetalGrade.objects.get(code=code)
        SchemePlanOffering.objects.create(plan=plan, metal_grade=grade, active=True)
        rate = publish_scheme_rate(metal_grade=grade, rate_per_gram=Decimal(rate_value), published_by=owner)
        account = enroll_customer(customer=customer, plan=plan, metal_grade=grade, start_date=today,
                                  performed_by=owner, reason="Synthetic pre-upgrade fixture")
        record_in_store_cash_contribution(scheme_account=account, amount=Decimal("1000"),
            expected_scheme_rate_id=rate.pk, received_by=owner, idempotency_key=uuid.uuid4(),
            paper_receipt_number="SYNTHETIC-" + code, notes="No money received; synthetic fixture",
            audit_reason="Synthetic pre-upgrade financial evidence")
        accounts.append(account)
    # Historical cash fixture, not new business enrolment or an input bypass.
    cash = SchemeAccount.objects.create(customer=customer, plan=plan, scheme_number="SYNTHETIC-CASH",
        start_date=today, agreed_months=12,
        eligible_from=calculate_eligibility_date(start_date=today, agreed_months=12), savings_mode="CASH",
        amount_rule_snapshot="VARIABLE", frequency_rule_snapshot="FLEXIBLE",
        minimum_amount_snapshot=Decimal("500"), maximum_amount_snapshot=Decimal("5000"))
    Contribution.objects.create(scheme_account=cash, amount=Decimal("500"), status="PAID",
        contribution_period=today.replace(day=1), frequency_rule_snapshot="FLEXIBLE", payment_gateway="mock",
        gateway_reference="synthetic-legacy-cash", paid_at=timezone.now())
    registration = CustomerRegistration.objects.create(full_name="Synthetic legacy applicant",
        email="legacy-applicant@example.invalid", mobile_number="9000000002", address="Synthetic address",
        email_token_digest=uuid.uuid4().hex * 2, email_verification_expires_at=timezone.now()+timedelta(days=1),
        status="AWAITING_OWNER_APPROVAL", email_verified_at=timezone.now(), terms_version="synthetic-v1",
        privacy_version="synthetic-v1", consent_accepted_at=timezone.now(), source_ip_digest="a"*64)
    request = submit_scheme_enrolment_request(customer=customer, plan=plan, metal_grade=accounts[0].metal_grade,
        requested_contribution_amount=Decimal("1000"), requested_months=12, customer_message="",
        actor=customer.user).enrolment_request
    invitation = apps.get_model("accounts", "CustomerInvitation").objects.create(user_id=customer.user_id,
        email=customer.email, created_by_id=owner.pk, created_by_label=owner.email,
        token_digest=uuid.uuid4().hex*2, expires_at=timezone.now()-timedelta(days=1))
    return owner.pk, customer.pk, plan.pk, registration.pk, request.pk, invitation.pk


def verify_restored_journeys(ids):
    from django.contrib.auth import get_user_model
    from django.core import mail
    from django.core.exceptions import ValidationError
    from django.core.management import call_command
    from django.test import Client
    from django.urls import reverse
    from django.utils import timezone
    from accounts.applications import (
        approve_plan_application, complete_plan_application, offer_form_digest,
        submit_plan_application, verify_plan_application,
    )
    from accounts.models import CustomerInvitation, PlanApplication
    from accounts.application_selectors import activated_plan_url, application_timeline, get_plan_application
    from accounts.services import accept_customer_invitation, issue_customer_invitation, send_customer_invitation
    from schemes.models import Customer, MetalGrade, SchemeAccount, SchemePlan
    from schemes.selectors import get_outstanding_entitlement

    owner_id, customer_id, plan_id, registration_id, request_id, invitation_id = ids
    owner = get_user_model().objects.get(pk=owner_id)
    customer = Customer.objects.get(pk=customer_id)
    require(CustomerInvitation.objects.get(pk=invitation_id).recovery_requested_at is None,
            "Historical invitation recovery field must start empty.")
    require(not PlanApplication.objects.exists(), "Migration invented historical application records.")
    balances = {account.savings_mode: get_outstanding_entitlement(account)
                for account in SchemeAccount.objects.filter(customer=customer)}
    require(balances == {"CASH": Decimal("500"), "GOLD": Decimal("0.100000"), "SILVER": Decimal("10.000000")},
            "Restored liabilities differ or currencies/grades were combined.")
    historical_financial = financial_snapshot()
    before_reads = digest(historical_financial)
    client = Client()
    client.force_login(owner)
    views = [reverse("schemes:owner_today"), reverse("schemes:customer_list"),
             reverse("schemes:owner_applications"), reverse("schemes:contribution_list"),
             reverse("schemes:exception_queue"), reverse("schemes:customer_detail", args=[customer.pk]),
             reverse("customer_registration_detail", args=[registration_id]),
             reverse("schemes:owner_enrolment_request_detail", args=[request_id])]
    for url in views:
        require(client.get(url, secure=True).status_code == 200, "Restored owner page failed.")
    for name in ("customer_list", "owner_applications", "contribution_list", "exception_queue"):
        url = reverse("schemes:"+name)
        full = client.get(url, secure=True)
        fragment = client.get(url, secure=True, HTTP_HX_REQUEST="true")
        require(fragment.status_code == 200 and "no-store" in fragment["Cache-Control"], "Unsafe fragment.")
        require(b"<!DOCTYPE html>" not in fragment.content and len(fragment.content) < len(full.content),
                "Fragment did not retain a bounded representation.")
    client.force_login(customer.user)
    for name in ("my_schemes", "customer_applications", "customer_documents"):
        require(client.get(reverse("schemes:"+name), secure=True).status_code == 200, "Legacy customer page failed.")
    for account in SchemeAccount.objects.filter(customer=customer):
        require(client.get(reverse("schemes:scheme_statement", args=[account.scheme_number]), secure=True).status_code == 200,
                "Historical statement unavailable.")
    for url in views[:5]:
        require(client.get(url, secure=True).status_code == 403, "Customer gained owner access.")
    guest = Client()
    require(guest.get(reverse("schemes:owner_applications"), secure=True, HTTP_HX_REQUEST="true").has_header("HX-Redirect"),
            "Expired fragment session did not navigate to login.")
    require(digest(financial_snapshot()) == before_reads, "Read-only journeys changed financial evidence.")
    print("restored_reads=ok owner_pages=8 customer_history=ok fragments=4 permissions=ok liabilities_separate=true", flush=True)

    plan = SchemePlan.objects.get(pk=plan_id)
    grade = MetalGrade.objects.get(code=MetalGrade.GOLD_22K_916)
    submission = submit_plan_application(plan=plan, metal_grade=grade, amount=Decimal("1000"), months=12,
        message="Synthetic restored journey", full_name="Synthetic new applicant", email="new-applicant@example.invalid",
        mobile_number="9000000003", source_ip="127.0.0.1", offer_digest=offer_form_digest(plan),
        base_url="https://example.invalid")
    application = verify_plan_application(registration_id=submission.application.pk, raw_token=submission.raw_token,
                                          base_url="https://example.invalid")

    def confirm():
        return complete_plan_application(registration_id=application.registration_id,
            access_digest=application.progress_token_digest, address="Synthetic complete address",
            metal_grade=grade, amount=Decimal("1000"), months=12, message="Synthetic preferences",
            start_date=timezone.localdate(), offer_digest=offer_form_digest(plan))

    application = confirm()
    plan.minimum_contribution = Decimal("750")
    plan.save()
    approval_args = dict(registration_id=application.registration_id, actor=owner, mobile_verified=True,
                         terms_reviewed=True, reason="Synthetic coordinated review", base_url="https://example.invalid")
    try:
        approve_plan_application(**approval_args)
    except ValidationError:
        pass
    else:
        raise RuntimeError("Changed terms approved without customer reconfirmation.")
    application = confirm()
    with patch("accounts.applications.EmailMultiAlternatives.send", side_effect=RuntimeError("Synthetic mail failure")):
        account, created = approve_plan_application(**approval_args)
    require(created, "New application did not produce an agreement.")
    same, created_again = approve_plan_application(**approval_args)
    require(not created_again and same.pk == account.pk, "Retry duplicated the agreement.")
    require(CustomerInvitation.objects.filter(user=account.customer.user, delivery_failed_at__isnull=False).exists(),
            "Committed approval lost activation delivery-recovery evidence.")
    replacement, token = issue_customer_invitation(user=account.customer.user, created_by=owner)
    require(send_customer_invitation(invitation=replacement, raw_token=token,
            setup_url="https://example.invalid" + reverse("customer_invitation_accept", args=[replacement.pk, token])),
            "Replacement invitation delivery did not recover in memory.")
    user = accept_customer_invitation(invitation_id=replacement.pk, raw_token=token,
                                      new_password="synthetic-activation-only")
    destination = reverse("schemes:my_scheme_detail", args=[account.scheme_number])
    require(activated_plan_url(user) == destination, "Activation lost the approved-plan continuation.")
    require(next(step["key"] for step in application_timeline(get_plan_application(application.registration_id))
                 if step["current"]) == "payment", "Activation or first-payment milestone differs.")
    client.force_login(user)
    require(client.get(destination, secure=True).status_code == 200, "Activated customer cannot open approved plan.")
    require(not account.contributions.exists(), "Activation or continuation created a payment.")
    # New workflow evidence may append rows; every historical financial row must remain exact.
    after = financial_snapshot()
    for name, rows in historical_financial.items():
        recorded = {row["id"]: row for row in after[name]}
        require(all(recorded.get(row["id"]) == row for row in rows), "New workflow changed historical financial rows.")
    for command in ("check_public_customer_registrations", "check_scheme_enrolment_requests",
                    "check_graded_metal_rates", "check_in_store_cash_contributions", "check_auth_email_integrity"):
        call_command(command, stdout=StringIO())
    require(mail.get_connection().__class__.__module__ == "django.core.mail.backends.locmem", "Outbound mail configured.")
    print("new_application=ok changed_terms_blocked=true reconfirmation=ok retry_same_agreement=true mail_recovery=ok activation_continuation=ok first_payment_not_invented=true integrity_commands=5", flush=True)


def main():
    started = monotonic()
    require(sys.argv[1:] == ["--synthetic-local"], "Explicit --synthetic-local required.")
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_project.settings")
    from django.conf import settings

    original = copy.deepcopy(settings.DATABASES["default"])
    validate_database(original)
    executables = {name: shutil.which(name) for name in ("pg_dump", "pg_restore")}
    require(all(executables.values()), "PostgreSQL dump/restore clients required.")
    stem = "jsk_workflow_drill_" + uuid.uuid4().hex[:16]
    source, restored = stem + "_source", stem + "_restore"
    require(original["NAME"] not in {source, restored}, "Application database cannot be targeted.")
    settings.DATABASES["default"]["NAME"] = source
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    settings.PAYMENT_GATEWAY = "razorpay"
    settings.RAZORPAY_MODE = "test"
    settings.RAZORPAY_KEY_ID = "rzp_test_synthetic_only"
    settings.RAZORPAY_KEY_SECRET = settings.RAZORPAY_WEBHOOK_SECRET = "synthetic-only"
    settings.SCHEME_REMINDERS_ENABLED = False
    settings.IN_STORE_CASH_CONTRIBUTIONS_ENABLED = True
    settings.PUBLIC_CUSTOMER_REGISTRATION_ENABLED = settings.CUSTOMER_ENROLMENT_REQUESTS_ENABLED = True
    settings.PUBLIC_REGISTRATION_TERMS_VERSION = settings.PUBLIC_REGISTRATION_PRIVACY_VERSION = "synthetic-v1"
    settings.CUSTOMER_ENROLMENT_REQUEST_DISCLOSURE_VERSION = "synthetic-v1"
    settings.DEBUG = False
    settings.ALLOWED_HOSTS = ["testserver"]
    settings.CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
    settings.STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "renditions": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
    logging.disable(logging.CRITICAL)
    import django
    django.setup()
    import psycopg
    from psycopg import sql
    from django.core.management import call_command
    from django.db import connection, connections
    from django.db.migrations.executor import MigrationExecutor

    args = dict(host=original["HOST"], port=original["PORT"], user=original["USER"],
                password=original["PASSWORD"], connect_timeout=5)
    env = {key: value for key, value in os.environ.items() if not key.startswith("PG")}
    env.update(PGPASSWORD=original["PASSWORD"], PGCONNECT_TIMEOUT="5")
    cli = ["--host", original["HOST"], "--port", str(original["PORT"] or 5432),
           "--username", original["USER"], "--no-password"]
    real_connect = socket.socket.connect
    created = []

    def isolated_connect(sock, address):
        require(isinstance(address, tuple) and address[0] in {"localhost", "127.0.0.1", "::1"}
                and address[1] == int(original["PORT"] or 5432), "Rehearsal blocked outbound network access.")
        return real_connect(sock, address)

    def run_pg(name, arguments):
        result = subprocess.run([executables[name], *cli, *arguments], env=env, capture_output=True, timeout=120)
        require(result.returncode == 0, f"{name} failed on a synthetic drill database.")

    try:
        with ExitStack() as stack:
            stack.enter_context(patch.object(socket.socket, "connect", isolated_connect))
            with psycopg.connect(dbname="postgres", autocommit=True, **args) as admin:
                for name in (source, restored):
                    admin.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(sql.Identifier(name)))
                    created.append(name)
            print("isolation=ok fresh_databases=2 configured_application_database_untouched=true outbound_network=blocked", flush=True)
            with tempfile.TemporaryDirectory(prefix="jsk-workflow-synthetic-") as directory:
                executor = MigrationExecutor(connection)
                targets = [node for node in executor.loader.graph.leaf_nodes() if node[0] not in {"accounts", "pages", "schemes"}]
                targets += [("accounts", "0006_customer_deletion_completion"), ("pages", "0001_initial"),
                            ("schemes", "0020_scheme_enrolment_requests")]
                executor.migrate(targets)
                ids = seed_legacy(executor.loader.project_state(targets).apps)
                before = digest(legacy_snapshot())
                dump = Path(directory) / "synthetic-pre-conversion.dump"
                connections.close_all()
                run_pg("pg_dump", ["--format=custom", "--no-owner", "--no-acl", "--file", str(dump), source])
                run_pg("pg_restore", ["--exit-on-error", "--no-owner", "--no-acl", "--dbname", restored, str(dump)])
                connection.settings_dict["NAME"] = restored
                require(digest(legacy_snapshot()) == before, "Restored historical baseline differs.")
                executor = MigrationExecutor(connection)
                pending = executor.migration_plan(executor.loader.graph.leaf_nodes())
                require(pending and not any(backwards for _, backwards in pending), "Expected only additive pending migrations.")
                print("pg_dump=ok pg_restore=ok legacy_baseline_match=true pending_migrations="+
                      ",".join(migration.app_label+"."+migration.name for migration, _ in pending), flush=True)
                call_command("migrate", interactive=False, verbosity=0, stdout=StringIO())
                require(digest(legacy_snapshot()) == before, "Upgrade changed historical identity/financial records.")
                require(not MigrationExecutor(connection).migration_plan(MigrationExecutor(connection).loader.graph.leaf_nodes()),
                        "Pending migrations remain after upgrade.")
                verify_restored_journeys(ids)
                call_command("check", stdout=StringIO())
                print("upgrade=ok historical_records_unchanged=true production_like_debug=false external_staging_acceptance=false", flush=True)
    finally:
        connections.close_all()
        with psycopg.connect(dbname="postgres", autocommit=True, **args) as admin:
            for name in reversed(created):
                require(name in {source, restored} and name.startswith(stem+"_"), "Unsafe cleanup target.")
                admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))
        print(f"cleanup=ok temporary_databases_removed={len(created)} synthetic_files_removed=true", flush=True)
        print(f"elapsed_seconds={monotonic()-started:.3f}", flush=True)


if __name__ == "__main__":
    main()
