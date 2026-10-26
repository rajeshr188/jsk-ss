import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from threading import Event
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, close_old_connections, connection, transaction
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from schemes.checkout_selectors import checkout_can_resume
from schemes.checkout_services import recover_order_identity
from schemes.models import (AuditEvent, Contribution, MetalAllocation, PaymentOperationsControl,
    RazorpayCheckoutSubmission, RazorpayOrderRequest, RazorpayOrderRecovery, SchemePlan)
from schemes.payments import PaymentGatewayError, PaymentOrderIdentity
from schemes.services import confirm_razorpay_contribution, initiate_contribution, initiate_razorpay_contribution
from .test_razorpay import FakeRazorpayGateway, FakeResponse, RAZORPAY_SETTINGS, make_account

SETTINGS = {**RAZORPAY_SETTINGS, 'DEBUG': True}


@override_settings(**SETTINGS)
class CheckoutIdempotencyTests(TestCase):
    def setUp(self):
        self.customer, self.account = make_account(email='checkout@example.com', frequency=SchemePlan.FrequencyRule.FLEXIBLE)
        self.gateway = FakeRazorpayGateway()
        self.key = uuid.uuid4()

    def start(self, key=None, **kwargs):
        return initiate_razorpay_contribution(scheme_account=self.account, amount=Decimal('5000.00'),
            submission_key=key or self.key, gateway=self.gateway, **kwargs)

    def pay(self, contribution):
        return confirm_razorpay_contribution(contribution_id=contribution.pk,
            callback_order_id=contribution.gateway_order_id, payment_id=f'pay_checkout_{contribution.pk}',
            signature='verified', gateway=self.gateway)

    def test_legacy_service_cannot_bypass_configured_reservation_workflow(self):
        from schemes.checkout_services import initiate_checkout
        with patch('schemes.instalments.has_monthly_instalments', return_value=True), self.assertRaises(ValidationError):
            initiate_checkout(scheme_account=self.account, amount=Decimal('5000'),
                gateway=self.gateway, submission_key=self.key)
        self.assertEqual(self.gateway.order_calls, 0)
        self.assertFalse(RazorpayOrderRequest.objects.exists())

    def test_repeated_submission_and_two_tabs_share_one_order(self):
        first = self.start()
        same = self.start()
        second_key = uuid.uuid4()
        other_tab = self.start(second_key)
        self.assertEqual({first.pk, same.pk, other_tab.pk}, {first.pk})
        self.assertEqual(self.gateway.order_calls, 1)
        self.assertEqual(RazorpayCheckoutSubmission.objects.count(), 2)
        self.pay(first)
        self.assertEqual(self.start().pk, first.pk)
        self.assertEqual(self.start(second_key).pk, first.pk)
        self.assertEqual(self.gateway.order_calls, 1)
        self.assertNotEqual(self.start(uuid.uuid4()).pk, first.pk)
        self.assertEqual(self.gateway.order_calls, 2)

    def test_submission_identity_cannot_change_account_amount_or_mode(self):
        first = self.start()
        _, other = make_account(email='other-checkout@example.com', frequency=SchemePlan.FrequencyRule.FLEXIBLE)
        for account, amount, mode in ((other, Decimal('5000'), 'test'),
                (self.account, Decimal('5001'), 'test'), (self.account, Decimal('5000'), 'live')):
            self.gateway.mode = mode
            with self.subTest(mode=mode, account=account.pk, amount=amount), self.assertRaises(ValidationError):
                initiate_razorpay_contribution(scheme_account=account, amount=amount,
                    submission_key=self.key, gateway=self.gateway)
        self.assertEqual(Contribution.objects.count(), 1)
        self.assertEqual(self.gateway.order_calls, 1)
        self.assertEqual(first.amount, Decimal('5000'))

    def test_uncertain_create_commits_evidence_and_never_retries(self):
        self.gateway.create_order = lambda c: (_ for _ in ()).throw(PaymentGatewayError('timeout'))
        with self.assertRaisesMessage(PaymentGatewayError, 'provider reconciliation'):
            self.start()
        contribution = Contribution.objects.get()
        self.assertEqual(contribution.status, 'PENDING')
        self.assertIsNone(contribution.gateway_order_id)
        self.assertEqual(RazorpayOrderRequest.objects.count(), 1)
        with patch.object(self.gateway, 'create_order') as create:
            self.assertEqual(self.start().pk, contribution.pk)
            alias = uuid.uuid4()
            self.assertEqual(self.start(alias).pk, contribution.pk)
            create.assert_not_called()
        self.assertEqual(RazorpayCheckoutSubmission.objects.count(), 2)
        self.assertFalse(MetalAllocation.objects.exists())

    def test_invalid_provider_response_and_failed_local_binding_remain_held(self):
        original = self.gateway.create_order
        self.gateway.create_order = lambda c: replace(original(c), amount_subunits=1)
        with self.assertRaises(PaymentGatewayError):
            self.start()
        c = Contribution.objects.get()
        self.assertEqual(c.status, 'PENDING')
        self.assertIsNone(c.gateway_order_id)
        self.assertEqual(self.start(uuid.uuid4()).pk, c.pk)
        self.assertEqual(self.gateway.order_calls, 1)

    def test_database_failure_after_provider_response_retains_original_request(self):
        original_save = Contribution.save
        def fail_binding(obj, *args, **kwargs):
            if kwargs.get('update_fields') == ['gateway_order_id']:
                raise RuntimeError('synthetic interrupted binding')
            return original_save(obj, *args, **kwargs)
        with patch.object(Contribution, 'save', fail_binding), self.assertRaises(RuntimeError):
            self.start()
        c = Contribution.objects.get()
        self.assertEqual(c.status, 'PENDING')
        self.assertIsNone(c.gateway_order_id)
        self.assertEqual(RazorpayOrderRequest.objects.count(), 1)
        self.assertEqual(self.start().pk, c.pk)
        self.assertEqual(self.gateway.order_calls, 1)

    def test_legacy_missing_order_identity_is_not_sent_again(self):
        c = initiate_contribution(scheme_account=self.account, amount=Decimal('5000'),
            payment_gateway='razorpay', gateway_mode='test')
        self.assertEqual(self.start().pk, c.pk)
        self.assertEqual(self.gateway.order_calls, 0)
        self.assertFalse(RazorpayOrderRequest.objects.exists())

    def test_expiry_and_new_tab_preserve_deadline_and_lock(self):
        c = self.start()
        deadline = timezone.now() - timedelta(minutes=1)
        Contribution.objects.filter(pk=c.pk).update(checkout_expires_at=deadline)
        RazorpayOrderRequest.objects.filter(contribution=c).update(checkout_expires_at=deadline)
        resumed = self.start(uuid.uuid4())
        self.assertEqual(resumed.pk, c.pk)
        self.assertEqual(resumed.checkout_expires_at, deadline)
        self.assertFalse(checkout_can_resume(resumed))
        self.assertEqual(self.gateway.order_calls, 1)

    def test_request_snapshot_drift_refuses_resumption(self):
        c = self.start()
        RazorpayOrderRequest.objects.filter(contribution=c).update(amount_subunits=1)
        with self.assertRaisesMessage(ValidationError, 'retained order request'):
            self.start()
        c.refresh_from_db()
        self.assertFalse(checkout_can_resume(c))
        self.assertEqual(self.gateway.order_calls, 1)

    def test_nested_application_transaction_is_rejected_before_provider_call(self):
        with transaction.atomic(), self.assertRaisesMessage(ValidationError, 'inside another transaction'):
            self.start()
        self.assertFalse(Contribution.objects.exists())
        self.assertEqual(self.gateway.order_calls, 0)

    def test_database_rejects_another_unresolved_order_across_month_and_mode(self):
        c = self.start()
        values = {f.name: getattr(c, f.name) for f in c._meta.fields
            if f.name not in ('id', 'scheme_account', 'scheme_rate')}
        values.update(gateway_order_id=None, gateway_mode='live', contribution_period=c.contribution_period-timedelta(days=31))
        values['contribution_period'] = values['contribution_period'].replace(day=1)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Contribution.objects.create(scheme_account=self.account, scheme_rate=c.scheme_rate, **values)

    def test_evidence_is_immutable_and_cannot_be_deleted(self):
        c = self.start()
        for record in (c.checkout_order_request, c.checkout_submissions.get()):
            with self.subTest(record=type(record).__name__), self.assertRaises(ValidationError):
                record.save()
            with self.assertRaises(ValidationError):
                record.delete()

    def test_provider_io_occurs_after_durable_request(self):
        original = self.gateway.create_order
        def inspect(c):
            self.assertFalse(any(not getattr(b, '_from_testcase', False) for b in connection.atomic_blocks))
            self.assertTrue(RazorpayOrderRequest.objects.filter(contribution=c).exists())
            return original(c)
        self.gateway.create_order = inspect
        self.start()

    def test_monthly_completed_submission_replays_without_new_payment(self):
        self.account.frequency_rule_snapshot = 'ONCE_PER_MONTH'
        self.account.save(update_fields=['frequency_rule_snapshot'])
        c = self.start()
        self.pay(c)
        self.assertEqual(self.start().pk, c.pk)
        with self.assertRaises(ValidationError):
            self.start(uuid.uuid4())
        self.assertEqual(self.gateway.order_calls, 1)

    def test_pending_allocation_blocks_a_fresh_submission(self):
        c = self.start()
        Contribution.objects.filter(pk=c.pk).update(status='PAID_UNALLOCATED',
            paid_at=timezone.now(), gateway_reference='pay_unallocated')
        with self.assertRaisesMessage(ValidationError, 'metal credit is pending'):
            self.start(uuid.uuid4())
        self.assertEqual(self.start().status, 'PAID_UNALLOCATED')
        self.assertEqual(self.gateway.order_calls, 1)

    def form_data(self):
        self.client.force_login(self.customer.user)
        url = reverse('schemes:pay_contribution', args=[self.account.scheme_number])
        form = self.client.get(url).context['form']
        return url, dict(amount='5000.00', submission_key=str(form.initial['submission_key']),
            submission_context=form.initial['submission_context'])

    def test_browser_double_submission_and_stale_unsubmitted_tab_do_not_charge_again(self):
        url, first = self.form_data()
        _, other_tab = self.form_data()
        with patch('schemes.services.get_payment_gateway', return_value=self.gateway):
            self.assertEqual(self.client.post(url, first).status_code, 302)
            self.assertEqual(self.client.post(url, first).status_code, 302)
            c = Contribution.objects.get()
            self.pay(c)
            result = self.client.post(url, other_tab)
            self.assertRedirects(result, reverse('schemes:payment_status', args=[c.pk]))
            self.assertEqual(self.gateway.order_calls, 1)
            self.assertEqual(Contribution.objects.count(), 1)
            _, fresh = self.form_data()
            self.assertEqual(self.client.post(url, fresh).status_code, 302)
            self.assertEqual(self.gateway.order_calls, 2)

    def test_browser_requires_original_signed_submission_context(self):
        url, data = self.form_data()
        with patch('schemes.services.get_payment_gateway', return_value=self.gateway):
            for bad in (dict(amount='5000.00'), {**data, 'submission_context': 'tampered'},
                    {**data, 'submission_key': str(uuid.uuid4())}):
                with self.subTest(data=bad):
                    self.assertEqual(self.client.post(url, bad).status_code, 400)
        self.assertEqual(self.gateway.order_calls, 0)
        self.assertFalse(Contribution.objects.exists())

    def test_unsigned_form_cannot_consume_monthly_opportunity(self):
        self.account.frequency_rule_snapshot = 'ONCE_PER_MONTH'
        self.account.save(update_fields=['frequency_rule_snapshot'])
        url, data = self.form_data()
        with patch('schemes.services.get_payment_gateway', return_value=self.gateway):
            self.client.post(url, data)
            self.pay(Contribution.objects.get())
            self.assertEqual(self.client.post(url, data).status_code, 302)
            _, fresh = self.form_data()
            self.assertEqual(self.client.post(url, fresh).status_code, 400)
        self.assertEqual(self.gateway.order_calls, 1)

    def test_request_evidence_cannot_be_bypassed_by_marking_failed(self):
        from schemes.services import fail_contribution
        c = self.start()
        with self.assertRaisesMessage(ValidationError, 'provider reconciliation'):
            fail_contribution(contribution_id=c.pk)
        Contribution.objects.filter(pk=c.pk).update(status='FAILED')
        with self.assertRaisesMessage(ValidationError, 'Unresolved provider request evidence'):
            self.start(uuid.uuid4())
        self.assertEqual(self.gateway.order_calls, 1)

    def test_same_amount_from_new_tab_does_not_reset_original_terms(self):
        c = self.start()
        frozen = (c.amount, c.scheme_rate_id, c.rate_locked_at, c.checkout_expires_at)
        other = self.start(uuid.uuid4())
        self.assertEqual((other.amount, other.scheme_rate_id, other.rate_locked_at, other.checkout_expires_at), frozen)

    def test_active_checkout_is_resumable_but_expiry_stays_on_status(self):
        c = self.start()
        self.client.force_login(self.customer.user)
        url = reverse('schemes:payment_status', args=[c.pk])
        self.assertContains(self.client.get(url), 'Continue payment')
        Contribution.objects.filter(pk=c.pk).update(checkout_expires_at=timezone.now()-timedelta(seconds=1))
        self.assertNotContains(self.client.get(url), 'Continue payment')

    def test_real_adapter_sends_and_validates_original_request_identity(self):
        import json
        from schemes.payments import RazorpayPaymentGateway
        c = self.start()
        intent = c.checkout_order_request
        gateway = RazorpayPaymentGateway()
        response = dict(id='order_adapter', amount=500000, currency='INR', receipt=intent.receipt,
            notes=dict(contribution_id=str(c.pk), request_token=str(intent.token)))
        with patch('schemes.payments.urlopen', return_value=FakeResponse(response)) as urlopen:
            gateway.create_order(c)
            sent = json.loads(urlopen.call_args.args[0].data)
            self.assertEqual(sent['receipt'], intent.receipt)
            self.assertLessEqual(len(sent['receipt']), 40)
            self.assertEqual(sent['notes'], response['notes'])
        for bad in ({**response, 'receipt': 'other'}, {**response, 'notes': {}}, {**response, 'amount': 500000.0}):
            with patch('schemes.payments.urlopen', return_value=FakeResponse(bad)), self.assertRaises(PaymentGatewayError):
                gateway.create_order(c)

    def test_real_adapter_validates_minimal_recovery_identity(self):
        from schemes.payments import RazorpayPaymentGateway
        c = self.start()
        intent = c.checkout_order_request
        response = dict(id='order_adapter', entity='order', amount=500000, currency='INR', status='created',
            created_at=int(intent.created_at.timestamp()), receipt=intent.receipt,
            notes=dict(contribution_id=str(c.pk), request_token=str(intent.token)))
        with patch('schemes.payments.urlopen', return_value=FakeResponse(response)):
            identity = RazorpayPaymentGateway().inspect_order_identity(order_id='order_adapter')
            self.assertEqual(identity.request_token, str(intent.token))
        for bad in ({**response, 'entity': 'other'}, {**response, 'created_at': True}, {**response, 'amount': 500000.0}, {**response, 'notes': []}):
            with patch('schemes.payments.urlopen', return_value=FakeResponse(bad)), self.assertRaises(PaymentGatewayError):
                RazorpayPaymentGateway().inspect_order_identity(order_id='order_adapter')

    def test_model_refuses_rewriting_retained_terms_or_provider_identity(self):
        c = self.start()
        for field, value in (('amount', Decimal('6000')), ('gateway_mode', 'live'),
                ('checkout_expires_at', c.checkout_expires_at+timedelta(minutes=10)), ('gateway_order_id', 'order_other')):
            with self.subTest(field=field):
                c.refresh_from_db()
                setattr(c, field, value)
                with self.assertRaisesMessage(ValidationError, 'immutable'):
                    c.save()

    def test_pause_expiry_or_closed_agreement_during_io_retains_identity_and_locked_gold_rate(self):
        from schemes.models import SchemeAccount, SchemeRate
        for change in ('pause', 'expiry', 'closed'):
            with self.subTest(change=change):
                PaymentOperationsControl.objects.filter(pk=1).update(global_pause=False)
                _, account = make_account(email=f'metal-io-{change}@example.com', mode='GOLD', frequency='FLEXIBLE')
                rate = SchemeRate.objects.create(metal_grade=account.metal_grade, metal='GOLD',
                    purity=account.metal_grade.fineness, rate_per_gram=Decimal('12500'), effective_from=timezone.now())
                gateway = FakeRazorpayGateway()
                original = gateway.create_order
                clock = [timezone.now()]
                def change_during_io(c):
                    order = original(c)
                    if change == 'pause':
                        PaymentOperationsControl.objects.filter(pk=1).update(global_pause=True)
                    elif change == 'expiry':
                        clock[0] += timedelta(minutes=11)
                    else:
                        SchemeAccount.objects.filter(pk=account.pk).update(status='REDEEMED')
                    return order
                gateway.create_order = change_during_io
                with patch('django.utils.timezone.now', side_effect=lambda: clock[0]), self.assertRaises(ValidationError):
                    initiate_razorpay_contribution(scheme_account=account, amount=Decimal('5000'), gateway=gateway)
                c = Contribution.objects.get(scheme_account=account)
                self.assertEqual(c.gateway_order_id, f'order_test_{c.pk}')
                self.assertEqual(c.scheme_rate_id, rate.pk)
                self.assertEqual(c.checkout_expires_at, c.checkout_order_request.checkout_expires_at)
                self.assertEqual(c.status, 'PENDING')
                with patch('django.utils.timezone.now', return_value=clock[0]):
                    self.assertFalse(checkout_can_resume(c))
                self.assertFalse(MetalAllocation.objects.filter(contribution=c).exists())


@override_settings(**SETTINGS)
class CheckoutRecoveryTests(TestCase):
    def setUp(self):
        self.customer, self.account = make_account(email='recover-checkout@example.com', frequency='FLEXIBLE')
        self.gateway = FakeRazorpayGateway()
        with patch.object(self.gateway, 'create_order', side_effect=PaymentGatewayError('lost response')):
            with self.assertRaises(PaymentGatewayError):
                initiate_razorpay_contribution(scheme_account=self.account, amount=Decimal('5000'), gateway=self.gateway)
        self.c = Contribution.objects.get(scheme_account=self.account)
        self.intent = self.c.checkout_order_request
        self.owner = get_user_model().objects.create_user(username='checkout-owner', role='OWNER', password='owner-password-strong')
        self.identity = PaymentOrderIdentity(order_id='order_recovered', receipt=self.intent.receipt,
            contribution_id=str(self.c.pk), request_token=str(self.intent.token), amount_subunits=500000,
            currency='INR', status='created', created_at=int(self.intent.created_at.timestamp()))
        self.gateway.inspect_order_identity = lambda **kwargs: self.identity

    def recover(self, **kwargs):
        return recover_order_identity(contribution_id=self.c.pk, order_id='order_recovered', actor=self.owner,
            reason='Provider investigation', evidence_reference='case-synthetic-1', gateway=self.gateway, **kwargs)

    def test_dry_run_then_apply_retains_original_terms_and_does_not_reopen_checkout(self):
        self.recover()
        self.c.refresh_from_db()
        self.assertIsNone(self.c.gateway_order_id)
        self.recover(apply=True)
        self.c.refresh_from_db()
        self.assertEqual(self.c.gateway_order_id, 'order_recovered')
        self.assertEqual(self.c.status, 'PENDING')
        self.assertEqual(self.c.checkout_expires_at, self.intent.checkout_expires_at)
        self.assertFalse(checkout_can_resume(self.c))
        self.assertEqual(RazorpayOrderRecovery.objects.count(), 1)
        self.assertTrue(AuditEvent.objects.filter(contribution=self.c, details__outcome='ORDER_IDENTITY_RECOVERED').exists())
        self.assertFalse(MetalAllocation.objects.exists())

    def test_mismatched_authenticated_order_is_never_bound(self):
        for field, value in (('receipt', 'other'), ('request_token', str(uuid.uuid4())), ('contribution_id', '9999'),
                ('amount_subunits', 1), ('currency', 'USD'), ('created_at', 1), ('status', 'unknown')):
            with self.subTest(field=field):
                self.gateway.inspect_order_identity = lambda **kwargs: replace(self.identity, **{field: value})
                with self.assertRaises(ValidationError):
                    self.recover(apply=True)
        self.c.refresh_from_db()
        self.assertIsNone(self.c.gateway_order_id)
        self.assertFalse(RazorpayOrderRecovery.objects.exists())

    def test_recovery_requires_owner_and_matching_mode(self):
        with self.assertRaises(ValidationError):
            recover_order_identity(contribution_id=self.c.pk, order_id='order_recovered', actor=self.customer.user,
                reason='Reason', evidence_reference='case', gateway=self.gateway)
        self.gateway.mode = 'live'
        with self.assertRaises(ValidationError):
            self.recover()

    def test_owner_ui_requires_review_confirmation_and_fresh_inspection(self):
        url = reverse('schemes:checkout_identity_recovery', args=[self.c.pk])
        self.client.force_login(self.owner)
        data = dict(order_id='order_recovered', reason='Provider investigation', evidence_reference='case-1', action='APPLY')
        with patch('schemes.payments.get_payment_gateway', return_value=self.gateway):
            self.assertContains(self.client.get(url), 'Recover payment order')
            denied = self.client.post(url, data)
            self.assertContains(denied, 'review is missing')
            inspected = self.client.post(url, {**data, 'action': 'INSPECT'})
            token = inspected.context['form'].initial['review_token']
            self.gateway.inspect_order_identity = lambda **kwargs: replace(self.identity, amount_subunits=1)
            changed = self.client.post(url, {**data, 'review_token': token, 'confirmed': True})
            self.assertContains(changed, 'does not exactly match')
        self.c.refresh_from_db()
        self.assertIsNone(self.c.gateway_order_id)

    def test_owner_ui_applies_only_identity_then_verified_capture_can_credit_once(self):
        url = reverse('schemes:checkout_identity_recovery', args=[self.c.pk])
        self.client.force_login(self.owner)
        data = dict(order_id='order_recovered', reason='Provider investigation', evidence_reference='case-1', action='INSPECT')
        with patch('schemes.payments.get_payment_gateway', return_value=self.gateway), patch.object(
                self.gateway, 'inspect_order_identity', wraps=self.gateway.inspect_order_identity) as inspect:
            self.client.get(url)
            inspect.assert_not_called()
            result = self.client.post(url, data)
            token = result.context['form'].initial['review_token']
            applied = self.client.post(url, {**data, 'action': 'APPLY', 'review_token': token, 'confirmed': True})
            self.assertContains(applied, 'Provider order identity recovered')
            self.assertEqual(inspect.call_count, 2)
        self.c.refresh_from_db()
        self.assertEqual(self.c.status, 'PENDING')
        self.assertFalse(checkout_can_resume(self.c))
        for _ in range(2):
            confirm_razorpay_contribution(contribution_id=self.c.pk, callback_order_id='order_recovered',
                payment_id='pay_recovered_capture', signature='verified', gateway=self.gateway)
        self.assertEqual(Contribution.objects.get(pk=self.c.pk).status, 'PAID')
        self.assertEqual(Contribution.objects.count(), 1)

    def test_recovery_endpoint_enforces_customer_denial_and_csrf(self):
        from django.test import Client
        url = reverse('schemes:checkout_identity_recovery', args=[self.c.pk])
        self.client.force_login(self.customer.user)
        self.assertEqual(self.client.get(url).status_code, 403)
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        self.assertEqual(client.post(url, dict(action='INSPECT')).status_code, 403)


@override_settings(**SETTINGS)
class CheckoutConcurrencyTests(TransactionTestCase):
    def test_tabs_during_provider_io_share_one_durable_order_and_replay_result(self):
        _, account = make_account(email='concurrent-checkout@example.com', frequency='FLEXIBLE')
        gateway = FakeRazorpayGateway()
        entered, release = Event(), Event()
        original = gateway.create_order
        keys = (uuid.uuid4(), uuid.uuid4())
        def create(c):
            entered.set()
            if not release.wait(15):
                raise AssertionError('Concurrent checkout did not finish')
            return original(c)
        gateway.create_order = create
        def start(key):
            close_old_connections()
            try:
                c = initiate_razorpay_contribution(scheme_account=account, amount=Decimal('5000'),
                    gateway=gateway, submission_key=key)
                return c.pk
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(start, keys[0])
            try:
                self.assertTrue(entered.wait(10))
                second_id = pool.submit(start, keys[1]).result(timeout=10)
            finally:
                release.set()
            first_id = first.result(timeout=10)
        self.assertEqual(first_id, second_id)
        self.assertEqual(gateway.order_calls, 1)
        self.assertEqual(RazorpayOrderRequest.objects.count(), 1)
        self.assertEqual(RazorpayCheckoutSubmission.objects.count(), 2)


@override_settings(**SETTINGS)
class CheckoutMigrationTests(TransactionTestCase):
    previous = [('schemes', '0020_scheme_enrolment_requests')]
    latest = [('schemes', '0021_checkout_idempotency')]

    def restore_current_schema(self):
        from django.db.migrations.executor import MigrationExecutor
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())

    def tearDown(self):
        self.restore_current_schema()
        super().tearDown()

    def test_preflight_refuses_legacy_overlap_and_preserves_remaining_history(self):
        from django.db.migrations.executor import MigrationExecutor
        _, account = make_account(email='migration-checkout@example.com', frequency='FLEXIBLE')
        executor = MigrationExecutor(connection)
        executor.migrate(self.previous)
        old = executor.loader.project_state(self.previous).apps.get_model('schemes', 'Contribution')
        values = dict(scheme_account_id=account.pk, amount=Decimal('5000'),
            contribution_period=timezone.localdate().replace(day=1), frequency_rule_snapshot='FLEXIBLE',
            payment_gateway='razorpay', payment_channel='RAZORPAY', gateway_mode='test', status='PENDING',
            checkout_expires_at=timezone.now()+timedelta(minutes=10))
        first = old.objects.create(**values)
        second = old.objects.create(**values)
        original = old.objects.filter(pk=first.pk).values().get()
        try:
            with self.assertRaisesMessage(RuntimeError, 'Reconcile overlapping'):
                MigrationExecutor(connection).migrate(self.latest)
            self.assertEqual(old.objects.count(), 2)
        finally:
            old.objects.filter(pk=second.pk).delete()
            MigrationExecutor(connection).migrate(self.latest)
        self.assertEqual(old.objects.filter(pk=first.pk).values().get(), original)
        self.assertFalse(RazorpayOrderRequest.objects.exists())

    def test_reverse_refuses_retained_request_before_removing_schema(self):
        from django.db.migrations.executor import MigrationExecutor
        _, account = make_account(email='reverse-checkout@example.com', frequency='FLEXIBLE')
        c = initiate_razorpay_contribution(scheme_account=account, amount=Decimal('5000'), gateway=FakeRazorpayGateway())
        try:
            with self.assertRaisesMessage(RuntimeError, 'Retained checkout evidence'):
                MigrationExecutor(connection).migrate(self.previous)
        finally:
            self.restore_current_schema()
        self.assertTrue(RazorpayOrderRequest.objects.filter(contribution_id=c.pk).exists())
        self.assertEqual(Contribution.objects.get(pk=c.pk).gateway_order_id, c.gateway_order_id)
