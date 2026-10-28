"""Explicit synthetic-only image drill; not an application management command.

Mount committed tests read-only into the candidate image. Use a disposable,
network-isolated PostgreSQL container, dump source and restore into target between
seed and verify. Readiness is simulated only by existing test fixture helpers.
No enrolment/publication acceptance or real refund verification is claimed.
"""
import hashlib
import json
import os
from pathlib import Path
from io import StringIO
import sys
from statistics import median
from time import perf_counter, sleep
from unittest import TestCase

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_project.settings")
import django
django.setup()

from django.apps import apps
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection, reset_queries
from django.db.migrations.executor import MigrationExecutor
from django.test import Client, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse


def require_isolation(phase):
    expected = "jsk_builder_configured_source" if phase == "seed" else "jsk_builder_configured_restore"
    database = settings.DATABASES["default"]
    if (os.environ.get("SYNTHETIC_BUILDER_DRILL") != "1"
            or database["HOST"] != "127.0.0.1" or database["NAME"] != expected
            or settings.EMAIL_BACKEND != "django.core.mail.backends.locmem.EmailBackend"
            or settings.CONFIGURED_PLANS_ENABLED):
        raise RuntimeError("Requires explicitly isolated synthetic database, locmem email and closed release gate")


def normalized(value):
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def snapshot():
    """Every retained schemes row/column, including the original contract/proofs."""
    result = {}
    for model in apps.get_app_config("schemes").get_models():
        rows = normalized(list(model.objects.order_by("pk").values()))
        result[model._meta.label] = {
            "count": len(rows),
            "sha256": hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest(),
        }
    return result


def balances():
    from schemes.models import SchemeAccount
    from schemes.selectors import get_outstanding_entitlement
    return {str(a.pk): {"mode": a.savings_mode, "grade": a.metal_grade_id,
        "status": a.status, "outstanding": str(get_outstanding_entitlement(a))}
        for a in SchemeAccount.objects.order_by("pk")}


def seed():
    if connection.introspection.table_names():
        raise RuntimeError("Seed requires a fresh empty synthetic database")
    call_command("migrate", interactive=False, verbosity=0)
    print("configured_history_schema=READY", flush=True)
    from schemes.tests.test_benefit_replacement_integration import IntegrationFixture
    from schemes.tests.test_refunded_order_retirement import RefundedOrderLifecycleTests
    from schemes.models import BenefitInvoiceFulfilment, BenefitInvoiceReversal

    class Fixture(IntegrationFixture, TestCase):
        pass

    fixture = Fixture()
    fixture.setUp()
    accounts = []
    try:
        for metal, kind in ((False, "INR_PURCHASE_BONUS"), (True, "VA_DISCOUNT")):
            account, closure, reversal = fixture.returned_benefit(kind=kind, metal=metal)
            # Preserve an original fulfilment, full return, approved replacement,
            # second fulfilment and second full return. No principal is re-earned.
            fixture.approve(account, reversal)
            if metal:
                proof, values = fixture.metal_values(closure)
                redemption = fixture.settle(values)
                fixture.reverse(fixture.reversal_values(redemption) |
                    {"expected_sequence": proof["sequence"] + 1})
                invoice = BenefitInvoiceFulfilment.objects.get(metal_settlement=redemption.configured_settlement)
            else:
                proposal = fixture.replacement_inr(account, closure)
                fixture.complete(proposal)
                fixture.return_all(proposal)
                invoice = BenefitInvoiceFulfilment.objects.get(inr_fulfilment__proposal=proposal)
            fixture.approve(account, BenefitInvoiceReversal.objects.get(fulfilment=invoice))
            accounts.append(account.pk)
            print(f"configured_history_family=SEEDED kind={kind} metal={metal}", flush=True)

        refund = RefundedOrderLifecycleTests()
        refund.owner, refund.customer, refund.control = fixture.owner, fixture.customer, fixture.control
        for monthly in (False, True):
            for metal in (False, True):
                contribution, _, _, _ = refund.prepare(monthly, metal)
                refund.retire(contribution, refund.order_review(contribution))
                print(f"refunded_order=SEEDED monthly={monthly} metal={metal}", flush=True)
        # Retain the latest catalogue evidence alongside the financial history.
        # These are real preparation/closure services, not database backfills.
        from schemes.catalogue_lifecycle import close_catalogue_item
        from schemes.catalogue_selectors import catalogue_closure_preview
        from schemes.tests.test_audit_exceptions import make_plan
        from schemes.plan_configuration import create_configuration_version, create_configured_plan_draft
        from schemes.tests.test_independent_policy_fields import independent_values
        configuration = create_configuration_version(values=independent_values(
            name="Synthetic archived configuration", accumulation="INR_PURCHASE_CREDIT"),
            actor=fixture.owner, reason="Prepare isolated catalogue recovery history")
        draft = create_configured_plan_draft(configuration_id=configuration.pk,
            name="Synthetic unused draft", code="RESTORE-ARCHIVE", metal_grades=[],
            actor=fixture.owner, reason="Prepare isolated draft")
        exposed = make_plan(code="RESTORE-RETIRE")
        for target in ({"plan": draft}, {"configuration": configuration}, {"plan": exposed}):
            preview = catalogue_closure_preview(**target)
            record, _ = close_catalogue_item(actor=fixture.owner, reason="Synthetic catalogue recovery rehearsal",
                confirmed=True, expected_digest=preview["expected_digest"],
                plan_id=target["plan"].pk if "plan" in target else None,
                configuration_id=target["configuration"].pk if "configuration" in target else None)
            print(f"catalogue_history=SEEDED action={record.action}", flush=True)
        return {"owner": fixture.owner.pk, "profile_accounts": accounts,
                "rows": snapshot(), "balances": balances()}
    finally:
        fixture.doCleanups()


def verify(manifest):
    if snapshot() != manifest["rows"] or balances() != manifest["balances"]:
        raise AssertionError("Restored retained columns or separate liabilities differ")
    # These fixtures intentionally end after a full return. Approval permits a
    # new review, not automatic re-spending: the award diagnostic must stay held.
    from schemes.models import SchemeBenefitAward
    from schemes.benefit_application_selectors import application_history
    from schemes.benefit_fulfilment_selectors import validate_benefit_reversal
    from schemes.benefit_reapplication_selectors import reapplication_review_status
    awards = list(SchemeBenefitAward.objects.all())
    if len(awards) != 2:
        raise AssertionError("Expected two retained original awards")
    for award in awards:
        history = application_history(award)
        if len(history) != 2:
            raise AssertionError("Expected original and replacement benefit invoice")
        latest = award.invoice_fulfilments.latest("pk").reversal
        validate_benefit_reversal(latest, current=True)
        if reapplication_review_status(latest) != "APPROVED_REVIEW":
            raise AssertionError("Returned benefit lost its retained review state")
    output = StringIO()
    try:
        call_command("check_benefit_awards", stdout=output)
    except CommandError:
        if "awards=2 review_required=2 invoice_fulfilments=4 invoice_reversals=4" not in output.getvalue():
            raise
        print("expected_returned_award_hold=PASS", output.getvalue().strip(), flush=True)
    else:
        raise AssertionError("A returned invoice must not automatically reopen benefit spending")
    for name in ("check_inr_principal", "check_benefit_reapplications",
                 "check_scheme_closures", "check_financial_exceptions", "check_graded_metal_rates"):
        call_command(name)
    print("retained_history_restore=PASS", json.dumps(manifest["balances"], sort_keys=True), flush=True)


def profile(manifest, *, latency_ms=0, samples=1):
    """Synthetic latency sensitivity, not a managed-database load test or SLA."""
    from accounts.models import CustomUser
    from schemes.models import SchemeAccount
    client = Client()
    client.force_login(CustomUser.objects.get(pk=manifest["owner"]))
    for pk in manifest["profile_accounts"]:
        account = SchemeAccount.objects.get(pk=pk)
        def readonly(execute, sql, params, many, context):
            if sql.lstrip().split()[0].upper() in {"INSERT", "UPDATE", "DELETE"}:
                raise AssertionError("Read-only owner page attempted a mutation")
            if latency_ms:
                sleep(latency_ms / 1000)
            return execute(sql, params, many, context)
        timings, counts = [], []
        for _ in range(samples):
            reset_queries()
            started = perf_counter()
            with connection.execute_wrapper(readonly), CaptureQueriesContext(connection) as queries:
                response = client.get(reverse("schemes:benefit_reapplication", args=[account.scheme_number]))
            timings.append(round(perf_counter() - started, 3))
            counts.append(len(queries))
            if response.status_code != 200 or "private" not in response.headers.get("Cache-Control", ""):
                raise AssertionError("Expected private owner review response")
            if len(connection.queries_log) >= connection.queries_limit:
                raise AssertionError("Incomplete query capture")
        print("image_history_profile " + json.dumps(dict(mode=account.savings_mode,
            returns=2, injected_per_query_ms=latency_ms, queries=counts,
            seconds=timings, median_seconds=median(timings))), flush=True)
    if snapshot() != manifest["rows"]:
        raise AssertionError("Owner GET changed retained financial history")


def reverse_refusal(manifest):
    from importlib import import_module
    from schemes.tests.migration_helpers import applied_migration_apps
    executor = MigrationExecutor(connection)
    leaves = executor.loader.graph.leaf_nodes()
    try:
        executor.migrate([("schemes", "0055_merge_builder_checkout_prevention")])
    except RuntimeError as exc:
        if "Retained catalogue" not in str(exc):
            raise
        print("whole_graph_downgrade_refusal=PASS", str(exc), flush=True)
    else:
        raise AssertionError("Retained catalogue history did not refuse downgrade")
    MigrationExecutor(connection).migrate(leaves)
    for module, function in (
        ("0047_benefit_invoice_fulfilment", "guard_reverse"),
        ("0048_benefit_reapplication_decisions", "guard_reverse"),
        ("0049_benefit_invoice_reapplication", "guard_reverse"),
        ("0050_independent_plan_drafts", "guard_reverse"),
        ("0052_payment_refund_observations", "preserve_refund_observations"),
        ("0053_payment_error_refund_resolution", "preserve_resolutions"),
        ("0054_refunded_order_retirement", "preserve_retirements"),
        ("0056_plan_catalogue_closure", "refuse_history_loss"),
    ):
        guard = getattr(import_module("schemes.migrations." + module), function)
        try:
            with connection.schema_editor() as editor:
                guard(applied_migration_apps(), editor)
        except RuntimeError as exc:
            print("retained_guard=PASS", module, str(exc), flush=True)
        else:
            raise AssertionError("Expected retained-evidence refusal: " + module)
    verify(manifest)


if __name__ == "__main__":
    phase, manifest_file = sys.argv[1:]
    if phase not in {"seed", "verify", "reverse", "latency"}:
        raise ValueError("Expected seed, verify, reverse or latency")
    require_isolation(phase)
    with override_settings(IN_STORE_CASH_CONTRIBUTIONS_ENABLED=True,
            PAYMENT_INITIATION_KILL_SWITCH=False, PAYMENT_GATEWAY="razorpay",
            RAZORPAY_MODE="live", RAZORPAY_KEY_ID="rzp_live_synthetic",
            RAZORPAY_KEY_SECRET="synthetic", RAZORPAY_WEBHOOK_SECRET="synthetic",
            ALLOWED_HOSTS=["testserver"], SECURE_SSL_REDIRECT=False):
        path = Path(manifest_file)
        if phase == "seed":
            path.write_text(json.dumps(seed(), sort_keys=True), encoding="utf-8")
            print("configured_history_seed=PASS", flush=True)
        else:
            manifest = json.loads(path.read_text(encoding="utf-8"))
            if phase == "verify":
                verify(manifest)
                profile(manifest)
            elif phase == "latency":
                if snapshot() != manifest["rows"]:
                    raise AssertionError("Unexpected synthetic fixture state")
                for latency in (0, 1.5, 10):
                    profile(manifest, latency_ms=latency, samples=3)
            else:
                reverse_refusal(manifest)
