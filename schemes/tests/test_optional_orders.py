"""Optional order durability on synthetic contracts, never release acceptance."""
import json
import uuid
from io import StringIO
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.core.management import call_command, CommandError
from django.db import close_old_connections, connection, transaction, IntegrityError
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase, override_settings

from schemes.models import (Contribution, OptionalPaymentOrderRequest, OptionalPaymentOrderBinding,
    InstalmentReservation, InrPrincipalReceipt, MetalAllocation, SchemeInstalmentPeriod)
from schemes.optional_orders import recover_optional_order
from schemes.payments import PaymentGatewayError, PaymentOrder, PaymentOrderIdentity, PaymentOrderInspection, RazorpayPaymentGateway
from schemes.services import initiate_contribution, initiate_razorpay_contribution, process_razorpay_webhook, reconcile_abandoned_razorpay_contribution
from schemes.tests import test_independent_payment_entry as entry
from schemes.tests.test_independent_instalment_ledger import NOW


@override_settings(IN_STORE_CASH_CONTRIBUTIONS_ENABLED=True, PAYMENT_INITIATION_KILL_SWITCH=False)
class OptionalOrderTests(TestCase):
    setUp = entry.IndependentPaymentEntryTests.setUp
    account = entry.IndependentPaymentEntryTests.account
    gateway = entry.IndependentPaymentEntryTests.gateway
    cash = entry.IndependentPaymentEntryTests.cash

    def pay(self, account, gateway, **kwargs):
        return initiate_razorpay_contribution(scheme_account=account, amount=Decimal("500"), gateway=gateway, **kwargs)

    def lost(self, **changes):
        account, gateway = self.account(**changes), self.gateway()
        gateway.create_order.side_effect = TimeoutError("Lost synthetic response")
        with self.assertRaises(TimeoutError):
            self.pay(account, gateway)
        c = account.contributions.get()
        intent = c.optional_order_request
        identity = PaymentOrderIdentity("order_recovered", f"opt_{intent.request_token.hex}", str(c.pk),
            str(intent.request_token), 50000, "INR", "created", int(NOW.timestamp()))
        gateway.inspect_order_identity.return_value = identity
        return account, gateway, c, identity

    def recover(self, c, gateway, **changes):
        return recover_optional_order(**(dict(contribution_id=c.pk, order_id="order_recovered", actor=self.owner,
            reason="Investigated lost response", evidence_reference="dashboard-order-evidence",
            idempotency_key=uuid.uuid4(), gateway=gateway) | changes))

    def test_success_and_resume_both_denominations_without_obligations(self):
        for metal in (False, True):
            a, g = self.account(metal=metal), self.gateway()
            first = self.pay(a, g)
            again = self.pay(a, g)
            self.assertEqual(first.pk, again.pk)
            self.assertEqual(g.create_order.call_count, 1)
            self.assertEqual(first.checkout_expires_at, again.checkout_expires_at)
            self.assertEqual(first.scheme_rate_id, again.scheme_rate_id)
            self.assertEqual(bool(first.scheme_rate_id), metal)
            self.assertFalse(first.optional_order_request.binding.recovered)
            with self.assertRaises(ValidationError):
                initiate_razorpay_contribution(scheme_account=a, amount=Decimal("600"), gateway=g)
            with self.assertRaises(ValidationError):
                self.cash(a)
        self.assertFalse(SchemeInstalmentPeriod.objects.exists())
        self.assertFalse(InstalmentReservation.objects.exists())
        self.assertFalse(InrPrincipalReceipt.objects.exists())
        self.assertFalse(MetalAllocation.objects.exists())

    def test_timeout_provider_error_and_local_failure_never_retry(self):
        for error in (TimeoutError("Lost"), PaymentGatewayError("Provider unavailable"), RuntimeError("Crash")):
            a, g = self.account(), self.gateway()
            g.create_order.side_effect = error
            with self.assertRaises(type(error)):
                self.pay(a, g)
            for action in (lambda: self.pay(a, g), lambda: self.cash(a)):
                with self.assertRaises(ValidationError):
                    action()
            c = a.contributions.get()
            self.assertEqual(c.status, "PENDING")
            self.assertFalse(c.gateway_order_id)
            self.assertFalse(hasattr(c.optional_order_request, "binding"))
            self.assertEqual(g.create_order.call_count, 1)

    def test_binding_failure_rolls_back_order_link_not_durable_intent(self):
        a, g = self.account(), self.gateway()
        with patch.object(OptionalPaymentOrderBinding, "save", side_effect=RuntimeError("Local write failed")):
            with self.assertRaises(RuntimeError):
                self.pay(a, g)
        c = a.contributions.get()
        self.assertFalse(c.gateway_order_id)
        self.assertTrue(OptionalPaymentOrderRequest.objects.filter(contribution=c).exists())
        with self.assertRaises(ValidationError):
            self.pay(a, g)
        self.assertEqual(g.create_order.call_count, 1)

    def test_recovery_exact_idempotent_and_never_resumes_or_credits(self):
        a, g, c, identity = self.lost(metal=True)
        before = (c.checkout_expires_at, c.scheme_rate_id, c.rate_locked_at)
        key = uuid.uuid4()
        result = self.recover(c, g, idempotency_key=key)
        self.assertEqual(self.recover(c, g, idempotency_key=key).pk, result.pk)
        self.assertEqual(g.inspect_order_identity.call_count, 1)
        c.refresh_from_db()
        self.assertEqual(c.gateway_order_id, identity.order_id)
        self.assertEqual((c.checkout_expires_at, c.scheme_rate_id, c.rate_locked_at), before)
        self.assertEqual(c.status, "PENDING")
        for action in (lambda: self.pay(a, g), lambda: self.cash(a),
                       lambda: self.recover(c, g, idempotency_key=key, reason="Different evidence")):
            with self.assertRaises(ValidationError):
                action()
        self.assertFalse(MetalAllocation.objects.exists())
        self.assertFalse(InrPrincipalReceipt.objects.exists())
        self.assertFalse(InstalmentReservation.objects.exists())

    def test_recovery_rejects_mismatches_and_missing_provider_evidence(self):
        a, g, c, identity = self.lost()
        for changes in ({"order_id": "order_other"}, {"receipt": "wrong"}, {"request_token": str(uuid.uuid4())},
                        {"contribution_id": "999"}, {"amount_subunits": 50001}, {"amount_subunits": True},
                        {"currency": "USD"}, {"status": "unknown"}, {"created_at": int(NOW.timestamp())-1},
                        {"created_at": int(NOW.timestamp())+60}):
            g.inspect_order_identity.return_value = replace(identity, **changes)
            with self.assertRaises(ValidationError):
                self.recover(c, g)
        g.inspect_order_identity.side_effect = PaymentGatewayError("Not found")
        with self.assertRaises(PaymentGatewayError):
            self.recover(c, g)
        self.assertFalse(OptionalPaymentOrderBinding.objects.exists())
        with self.assertRaises(ValidationError):
            self.pay(a, g)
        self.assertEqual(g.create_order.call_count, 1)

    def test_recovery_requires_owner_live_mode_and_unchanged_intent(self):
        a, g, c, identity = self.lost()
        with self.assertRaises(ValidationError):
            self.recover(c, g, actor=self.customer.user)
        g.mode = "test"
        with self.assertRaises(ValidationError):
            self.recover(c, g)
        g.mode = "live"
        def drift(**kwargs):
            Contribution.objects.filter(pk=c.pk).update(checkout_expires_at=NOW+timedelta(hours=1))
            return identity
        g.inspect_order_identity.side_effect = drift
        with self.assertRaises(ValidationError):
            self.recover(c, g)
        self.assertFalse(OptionalPaymentOrderBinding.objects.exists())

    def test_expiry_pause_and_containment_during_io_preserve_link_but_refuse_checkout(self):
        for change in ("expiry", "pause", "containment"):
            a, g = self.account(), self.gateway()
            original = g.create_order.side_effect
            def after_create(c):
                if change == "pause":
                    self.control.global_pause = True
                    self.control.save()
                else:
                    type(a).objects.filter(pk=a.pk).update(status="CLOSURE_PENDING")
                return original(c)
            # patch.start() returns the actual mock; change it through the active target.
            with patch("django.utils.timezone.now", return_value=NOW) as clock:
                def io(c):
                    if change == "expiry":
                        clock.return_value = NOW+timedelta(minutes=11)
                        return original(c)
                    return after_create(c)
                g.create_order.side_effect = io
                with self.assertRaises(ValidationError):
                    self.pay(a, g)
            self.assertTrue(OptionalPaymentOrderBinding.objects.filter(request__contribution__scheme_account=a).exists())
            self.control.global_pause = False
            self.control.save()

    def test_calendar_and_anniversary_ceiling_caps_deadline_at_boundary(self):
        for basis, instant in (("CALENDAR_MONTH", NOW.replace(day=31, hour=18, minute=29)),
                               ("ANNIVERSARY", NOW.replace(month=2, day=27, hour=18, minute=29))):
            a, g = self.account(frequency_rule="ONCE_PER_PERIOD", period_basis=basis,
                allow_contributions_after_eligibility=True), self.gateway()
            with patch("django.utils.timezone.now", return_value=instant):
                c = self.pay(a, g)
            self.assertEqual(c.checkout_expires_at, instant.replace(minute=30))
            with patch("django.utils.timezone.now", return_value=c.checkout_expires_at):
                with self.assertRaises(ValidationError):
                    self.pay(a, g)

    def test_successful_capture_adds_principal_once_and_no_instalments(self):
        a, g = self.account(allow_contributions_after_eligibility=True), self.gateway()
        c = self.pay(a, g)
        payload = {"event": "payment.captured", "created_at": int(NOW.timestamp()), "payload": {"payment": {"entity": {
            "id": "pay_optional", "order_id": c.gateway_order_id, "amount": 50000, "currency": "INR",
            "status": "captured", "captured": True, "created_at": int(NOW.timestamp())}}}}
        body = json.dumps(payload).encode()
        for _ in range(2):
            event = process_razorpay_webhook(gateway_mode="live", event_id="evt_optional", body=body, payload=payload)
            self.assertEqual(event.status, "PROCESSED")
        self.assertEqual(InrPrincipalReceipt.objects.count(), 1)
        self.assertFalse(InstalmentReservation.objects.exists())
        self.assertNotEqual(self.pay(a, g).pk, c.pk)

    def test_model_and_database_protect_append_only_identity(self):
        c = self.pay(self.account(), self.gateway())
        intent, binding = c.optional_order_request, c.optional_order_request.binding
        for action in (intent.save, intent.delete, binding.save, binding.delete):
            with self.assertRaises(ValidationError):
                action()
        with self.assertRaises(IntegrityError), transaction.atomic():
            OptionalPaymentOrderBinding.objects.filter(pk=binding.pk).update(recovered=True)

    def test_changed_contract_refuses_optional_order_before_external_api(self):
        a, g = self.account(), self.gateway()
        type(a).objects.filter(pk=a.pk).update(plan_name_snapshot="Unaccepted changed terms")
        a.plan_name_snapshot = "Unaccepted changed terms"
        self.ready.stop()
        for enabled in (False, True):
            with override_settings(CONFIGURED_PLANS_ENABLED=enabled), self.assertRaises(ValidationError):
                self.pay(a, g)
        g.create_order.assert_not_called()
        self.assertFalse(Contribution.objects.exists())

    def test_gateway_sends_and_reads_optional_identity(self):
        a, g, c, identity = self.lost()
        api = RazorpayPaymentGateway(mode="live", key_id="rzp_live_synthetic", key_secret="synthetic", webhook_secret="synthetic")
        payload = dict(id=identity.order_id, entity="order", amount=50000, currency="INR", status="created",
            receipt=identity.receipt, created_at=identity.created_at,
            notes={"contribution_id": str(c.pk), "optional_request": identity.request_token})
        with patch.object(api, "_request_json", return_value=payload) as request:
            api.create_order(c)
            sent = request.call_args.kwargs["payload"]
            self.assertEqual(sent["receipt"], identity.receipt)
            self.assertLessEqual(len(sent["receipt"]), 40)
            self.assertEqual(sent["notes"], payload["notes"])
            self.assertEqual(api.inspect_order_identity(order_id=identity.order_id), identity)

    def test_malformed_or_already_bound_order_response_stays_uncertain(self):
        previous = self.pay(self.account(), self.gateway())
        for response in (PaymentOrder("order_bad", 1, "INR"),
                         PaymentOrder(previous.gateway_order_id, 50000, "INR")):
            a, g = self.account(), self.gateway()
            g.create_order.side_effect = None
            g.create_order.return_value = response
            with self.assertRaises((ValidationError, PaymentGatewayError)):
                self.pay(a, g)
            c = a.contributions.get()
            self.assertFalse(c.gateway_order_id)
            self.assertFalse(hasattr(c.optional_order_request, "binding"))
            with self.assertRaises(ValidationError):
                self.pay(a, g)

    def test_abandonment_requires_provider_evidence_before_replacement(self):
        a, g, c, _ = self.lost()
        self.recover(c, g)
        c.refresh_from_db()
        g.inspect_order.return_value = PaymentOrderInspection(c.gateway_order_id, "created", 50000, 0,
            50000, "INR", 0, 0, ())
        g.create_order.side_effect = lambda c: PaymentOrder(f"order_new_{c.pk}", 50000, "INR")
        with patch("django.utils.timezone.now", return_value=NOW+timedelta(minutes=11)):
            reconcile_abandoned_razorpay_contribution(contribution_id=c.pk, cutoff=NOW,
                apply=True, gateway=g, performed_by=self.owner, reason="Verified untouched expired order")
            self.assertNotEqual(self.pay(a, g).pk, c.pk)
        c.refresh_from_db()
        self.assertEqual(c.status, "ABANDONED")
        self.assertTrue(c.optional_order_request.binding.recovered)

    def test_diagnostic_distinguishes_uncertain_request_from_integrity_error(self):
        a, g, c, _ = self.lost()
        output = StringIO()
        call_command("check_optional_payment_orders", stdout=output)
        self.assertIn("status=review", output.getvalue())
        self.assertIn("unbound_requests=1", output.getvalue())
        Contribution.objects.filter(pk=c.pk).update(gateway_order_id="order_unproven")
        with self.assertRaises(CommandError):
            call_command("check_optional_payment_orders", stdout=StringIO())

    def test_untracked_failed_source_cannot_be_cleared_by_status_alone(self):
        a, g = self.account(), self.gateway()
        c = initiate_contribution(scheme_account=a, amount=Decimal("500"), payment_gateway="razorpay", gateway_mode="live")
        output = StringIO()
        call_command("check_optional_payment_orders", stdout=output)
        self.assertIn("pending_without_request=1", output.getvalue())
        Contribution.objects.filter(pk=c.pk).update(status="FAILED")
        for action in (lambda: self.pay(a, g), lambda: self.cash(a)):
            with self.assertRaises(ValidationError):
                action()
        with self.assertRaises(CommandError):
            call_command("check_optional_payment_orders", stdout=StringIO())
        g.create_order.assert_not_called()

    def test_empty_migration_guard_allows_reverse(self):
        # Historical model guard itself is covered on retained evidence below.
        from importlib import import_module
        from django.apps import apps
        from types import SimpleNamespace
        import_module("schemes.migrations.0043_optional_payment_order_evidence").preserve_optional_orders(
            apps, SimpleNamespace(connection=connection))


class OptionalOrderTransactionTests(TransactionTestCase):
    setUp = entry.IndependentPaymentEntryTests.setUp
    account = entry.IndependentPaymentEntryTests.account
    gateway = entry.IndependentPaymentEntryTests.gateway

    def test_concurrent_submissions_create_one_request_and_one_order(self):
        a, g = self.account(), self.gateway()
        barrier = Barrier(2)
        def submit():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                try:
                    return initiate_razorpay_contribution(scheme_account=a, amount=Decimal("500"), gateway=g).pk
                except ValidationError:
                    return "held"
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = [f.result(timeout=30) for f in (pool.submit(submit), pool.submit(submit))]
        self.assertTrue(any(isinstance(r, int) for r in results))
        self.assertEqual(Contribution.objects.count(), 1)
        self.assertEqual(OptionalPaymentOrderRequest.objects.count(), 1)
        self.assertEqual(g.create_order.call_count, 1)

    def test_nested_transaction_refuses_provider_io(self):
        a, g = self.account(), self.gateway()
        with self.assertRaises(RuntimeError), transaction.atomic():
            initiate_razorpay_contribution(scheme_account=a, amount=Decimal("500"), gateway=g)
        g.create_order.assert_not_called()
        self.assertFalse(Contribution.objects.exists())

    def test_migration_reverse_refuses_retained_order_evidence(self):
        from importlib import import_module
        from types import SimpleNamespace
        from django.apps import apps
        leaves = MigrationExecutor(connection).loader.graph.leaf_nodes()
        self.addCleanup(lambda: MigrationExecutor(connection).migrate(leaves))
        a, g = self.account(), self.gateway()
        initiate_razorpay_contribution(scheme_account=a, amount=Decimal("500"), gateway=g)
        before = (list(OptionalPaymentOrderRequest.objects.values()),
                  list(OptionalPaymentOrderBinding.objects.values()))
        # 0050 protects this current-schema fixture before reversal reaches 0043.
        # Verify both refusal boundaries without disabling either production guard.
        with self.assertRaisesMessage(RuntimeError, "Retain independent draft policies and revisions"):
            MigrationExecutor(connection).migrate([("schemes", "0042_contribution_independent_frequency")])
        with self.assertRaisesMessage(RuntimeError, "Cannot reverse 0043"):
            import_module("schemes.migrations.0043_optional_payment_order_evidence").preserve_optional_orders(
                apps, SimpleNamespace(connection=connection))
        self.assertEqual((list(OptionalPaymentOrderRequest.objects.values()),
                          list(OptionalPaymentOrderBinding.objects.values())), before)
