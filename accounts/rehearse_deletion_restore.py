"""Opt-in synthetic LOCAL PostgreSQL drill, not a production recovery command.

Run: uv run --env-file .env python -m accounts.rehearse_deletion_restore --synthetic-local
Creates two random empty databases. Never dumps, migrates or restores the configured
application database. Temporary synthetic databases/files are removed on exit.
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
import uuid
from io import StringIO
from unittest.mock import patch


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def main():
    require(sys.argv[1:] == ["--synthetic-local"], "Explicit --synthetic-local required.")
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_project.settings")
    from django.conf import settings

    original = copy.deepcopy(settings.DATABASES["default"])
    require(original["ENGINE"] == "django.db.backends.postgresql", "PostgreSQL required.")
    require(original["HOST"] in {"localhost", "127.0.0.1", "::1"}, "Only explicit loopback allowed.")
    require(not original.get("OPTIONS"), "Use a local database without connection-option overrides.")
    executables = {tool: shutil.which(tool) for tool in ("pg_dump", "pg_restore")}
    require(all(executables.values()), "Install PostgreSQL client tools first.")
    stem = "jsk_privacy_drill_" + uuid.uuid4().hex[:16]
    source, restored = stem + "_source", stem + "_restore"
    require(original["NAME"] not in {source, restored}, "Application database must not be a target.")
    settings.DATABASES["default"]["NAME"] = source
    # Disable providers before app initialization; never start a server or timer.
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    settings.PAYMENT_GATEWAY = ""
    settings.RAZORPAY_KEY_ID = settings.RAZORPAY_KEY_SECRET = ""
    settings.SCHEME_REMINDERS_ENABLED = False
    logging.disable(logging.CRITICAL)

    import django
    django.setup()
    import psycopg
    from psycopg import sql
    from django.db import connections
    from django.core.management import call_command
    from django.test import override_settings
    from django.core import mail
    from accounts.test_account_deletion import DELETION_SETTINGS

    # Database credentials use the normally configured local connection only.
    connection_args = dict(host=original["HOST"], port=original["PORT"],
                           user=original["USER"], password=original["PASSWORD"],
                           connect_timeout=5)
    env = {k: v for k, v in os.environ.items() if not k.startswith("PG")}
    env["PGPASSWORD"] = original["PASSWORD"]
    env["PGCONNECT_TIMEOUT"] = "5"
    cli = ["--host", original["HOST"], "--port", str(original["PORT"]),
           "--username", original["USER"], "--no-password"]
    created = []
    real_connect = socket.socket.connect

    def local_connect(sock, address):
        require(isinstance(address, tuple) and address[0] in {"127.0.0.1", "::1", "localhost"},
                "Rehearsal blocked non-loopback network access.")
        return real_connect(sock, address)

    def run_pg(tool, args):
        result = subprocess.run([executables[tool], *cli, *args], env=env,
                                capture_output=True, timeout=120)
        require(result.returncode == 0, f"{tool} failed; no target outside the drill was used.")

    try:
        with patch.object(socket.socket, "connect", local_connect):
            with psycopg.connect(dbname="postgres", autocommit=True, **connection_args) as admin:
                for name in (source, restored):
                    # No IF NOT EXISTS: collisions must fail; never reuse an existing database.
                    admin.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(sql.Identifier(name)))
                    created.append(name)
            print("isolation=ok fresh_databases=2 configured_application_database_untouched=true", flush=True)
            with tempfile.TemporaryDirectory(prefix="jsk-privacy-synthetic-") as directory:
                with override_settings(**DELETION_SETTINGS):
                    call_command("migrate", interactive=False, verbosity=0, stdout=StringIO())
                    perform_drill(Path(directory), source, restored, run_pg)
    finally:
        connections.close_all()
        # Only exact names successfully created by this invocation are eligible.
        with psycopg.connect(dbname="postgres", autocommit=True, **connection_args) as admin:
            for name in reversed(created):
                require(name in {source, restored} and name.startswith(stem + "_"), "Unsafe cleanup target.")
                admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))
        print(f"cleanup=ok temporary_databases_removed={len(created)} synthetic_files_removed=true", flush=True)


def financial_snapshot():
    from schemes.models import (
        SchemeAccount, Contribution, MetalAllocation, Redemption, RedemptionReversal,
        InStoreCashReceipt, InStoreCashContributionReversal, AuditEvent, SchemeRate,
        PaymentWebhookEvent,
    )
    return {model._meta.label: list(model.objects.order_by("pk").values()) for model in (
        SchemeAccount, Contribution, MetalAllocation, Redemption, RedemptionReversal,
        InStoreCashReceipt, InStoreCashContributionReversal, AuditEvent, SchemeRate,
        PaymentWebhookEvent,
    )}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def check_recovery_record(record):
    from accounts.models import CustomerAccountDeletionRequest as Request
    require(digest(financial_snapshot()) == record["financial_digest"],
            "Financial history differs: reconcile before any privacy replay.")
    for item in record["items"]:
        require(Request.objects.filter(pk=item["request_id"], customer_id=item["customer_id"],
                                       customer__user_id=item["user_id"], status="CONTAINED",
                                       policy_version=item["policy_version"]).exists(),
                "Verified request missing or identity/state differs: supervised recovery required.")


def perform_drill(directory, source, restored, run_pg):
    from django.contrib.auth import get_user_model
    from django.contrib.sessions.models import Session
    from django.core import mail
    from django.core.management import call_command
    from django.db import connections
    from allauth.account.models import EmailAddress
    from allauth.socialaccount.models import SocialAccount
    from accounts.models import CustomerAccountDeletionRequest as Request, CustomerAccountDeletionNotice as Notice
    from accounts.deletion import complete_customer_account_deletion, review_customer_account_retention, send_completion_notice
    from accounts.test_deletion_completion import CompletionFixtures

    # Reuse synthetic test fixtures only after creating/migrating a fresh database.
    fixture = CompletionFixtures()
    fixture.setUp()
    fixture.preview_account()
    history_request = fixture.contain()
    history_args = fixture.completion_args(history_request, ("full_name", "email"))
    history_user, history_customer = fixture.user, fixture.customer
    user_model = get_user_model()
    from schemes.models import Customer
    fixture.user = user_model.objects.create_user(username="empty@example.invalid", email="empty@example.invalid",
                                                   password="synthetic-password-only", role="CUSTOMER")
    fixture.customer = Customer.objects.create(user=fixture.user, customer_number="SYNTHETIC-EMPTY",
                                               full_name="Synthetic Empty", email=fixture.user.email,
                                               mobile_number="9000000000", address="Synthetic only")
    EmailAddress.objects.create(user=fixture.user, email=fixture.user.email, verified=True, primary=True)
    empty_request = fixture.contain()
    empty_args = fixture.completion_args(empty_request, ("full_name", "email"))
    before = financial_snapshot()
    dump = directory / "contained-before-completion.dump"
    run_pg("pg_dump", ["--format=custom", "--no-owner", "--no-acl", "--file", str(dump), source])
    print("pg_dump=ok stage=verified_contained_before_completion", flush=True)

    decisions = []
    for args in (history_args, empty_args):
        _, decision = complete_customer_account_deletion(**args)
        send_completion_notice(notice_id=decision.notice.pk, actor=fixture.owner)
        decisions.append(decision)
    # Latest review removes fields that the original completion retained.
    review_args = fixture.completion_args(empty_request)
    review_args["reason"] = "Synthetic contact purpose ended; not a statutory retention decision."
    _, latest_review = review_customer_account_retention(**review_args)
    send_completion_notice(notice_id=latest_review.notice.pk, actor=fixture.owner)
    require(financial_snapshot() == before, "Source financial history changed.")
    items = []
    for request, customer, decision, completion in (
        (history_request, history_customer, decisions[0], decisions[0]),
        (empty_request, fixture.customer, latest_review, decisions[1]),
    ):
        items.append(dict(request_id=str(request.pk), customer_id=customer.pk, user_id=customer.user_id,
                          policy_version=decision.policy_version, completion_id=completion.pk,
                          completed_at=completion.decided_at.isoformat(), latest_decision_id=decision.pk,
                          latest_decision_at=decision.decided_at.isoformat(), disposition=decision.disposition))
    ledger_path = directory / "independent-synthetic-decisions.json"
    ledger_path.write_text(json.dumps({"version": 1, "financial_digest": digest(before), "items": items}), encoding="utf-8")
    # Files are synthetic generated artifacts, not an export of any real customer's data.
    record = json.loads(ledger_path.read_text(encoding="utf-8"))
    require("customer@example.com" not in ledger_path.read_text(encoding="utf-8"), "Ledger copied contact data.")
    connections.close_all()
    run_pg("pg_restore", ["--exit-on-error", "--no-owner", "--no-acl", "--dbname", restored, str(dump)])
    connections["default"].settings_dict["NAME"] = restored
    require(user_model.objects.filter(privacy_erased_at__isnull=False).count() == 0, "Unexpected restored marker.")
    require(user_model.objects.get(pk=fixture.user.pk).email == "empty@example.invalid", "PII restoration not demonstrated.")
    require(financial_snapshot() == before, "Restored financial baseline differs.")
    print("pg_restore=ok restored_identity_detected=true financial_baseline_match=true", flush=True)
    for broken in (dict(record, financial_digest="mismatch"),
                   dict(record, items=[dict(record["items"][0], request_id=str(uuid.uuid4()))])):
        try:
            check_recovery_record(broken)
        except RuntimeError:
            pass
        else:
            raise RuntimeError("Unsafe recovery record was not rejected.")
    check_recovery_record(record)
    owner = user_model.objects.get(pk=fixture.owner.pk)
    for item in record["items"]:
        disposition = item["disposition"]
        # Synthetic demonstration of a freshly reviewed service call, not a general
        # restore replay API. Historical evidence stays in the independent record.
        _, decision = complete_customer_account_deletion(
            request_id=item["request_id"], actor=owner,
            retention_plan=disposition["retention_plan"], retain_profile_fields=disposition["retain_profile_fields"],
            confirmation=item["request_id"], reason="Synthetic isolated restore disposition reapplied.",
            external_review=f"Synthetic recovery record references latest decision {item['latest_decision_id']}.",
        )
        send_completion_notice(notice_id=decision.notice.pk, actor=owner)
        user = user_model.objects.get(pk=item["user_id"])
        require(not user.is_active and not user.has_usable_password() and user.privacy_erased_at,
                "Removed login restored.")
        require(not EmailAddress.objects.filter(user=user).exists() and not SocialAccount.objects.filter(user=user).exists(),
                "Authentication bindings remain.")
    fixture.customer.refresh_from_db()
    require(fixture.customer.email.endswith("@deleted.invalid") and fixture.customer.full_name == "Removed customer",
            "Latest retained-field review was not reapplied.")
    require(financial_snapshot() == before, "Privacy replay changed financial facts.")
    require(not Notice.objects.exclude(recipient_email="").exists(), "Temporary notice contact remains.")
    call_command("check_customer_account_deletions", stdout=StringIO())
    require(not Session.objects.exists(), "Unexpected customer sessions.")
    require(mail.get_connection().__class__.__module__ == "django.core.mail.backends.locmem", "Unsafe email backend.")
    print("reapplication=ok cases=2 latest_review_applied=true negative_guards=2 financial_facts_unchanged=true", flush=True)
    print("integrity=ok outbound_email=in_memory_only production_recovery_acceptance=false", flush=True)


if __name__ == "__main__":
    main()
