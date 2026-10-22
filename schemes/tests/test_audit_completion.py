import csv
import io
import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts import test_plan_applications as application_helpers
from accounts.application_selectors import application_timeline
from accounts.models import CustomerAccountDeletionRequest, CustomerRegistration
from accounts.services import approve_customer_registration
from schemes.models import Contribution, PaymentWebhookEvent, AuditEvent
from schemes.selectors import get_recorded_first_payment
from schemes.tests import test_workflow_refinement as refinement_helpers


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
                   EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
                   CUSTOMER_ENROLMENT_REQUESTS_ENABLED=True, CUSTOMER_ACCOUNT_DELETION_ENABLED=True)
class AuditCompletionTests(TestCase):
    setUp = refinement_helpers.WorkflowRefinementTests.setUp
    registration = refinement_helpers.WorkflowRefinementTests.registration
    plan_request = refinement_helpers.WorkflowRefinementTests.plan_request
    agreement = refinement_helpers.WorkflowRefinementTests.agreement
    payment = refinement_helpers.WorkflowRefinementTests.payment

    def test_stage_counts_follow_scope_and_each_application_occurs_once(self):
        self.registration(1)
        self.registration(2, verified=False)
        closed = self.registration(3)
        approve_customer_registration(application=closed, reviewed_by=self.owner, reason='Synthetic identity review')
        self.plan_request()
        response = self.client.get(reverse('schemes:owner_applications'))
        self.assertEqual({t['key']: t['count'] for t in response.context['stage_tabs']},
                         {'attention': 2, 'waiting': 1, 'closed': 1, 'all': 4})
        for query, expected in [({'q': 'Applicant 01', 'kind': 'registration'}, 1),
                                ({'customer': self.customer.pk, 'kind': 'plan'}, 1)]:
            scoped = self.client.get(reverse('schemes:owner_applications'), {**query, 'focus': 'all', 'page': 2})
            self.assertEqual(scoped.context['page_obj'].paginator.count, expected)
            self.assertEqual(next(t['count'] for t in scoped.context['stage_tabs'] if t['key'] == 'all'), expected)
            self.assertContains(scoped, 'aria-label="Application stage"')
            self.assertContains(scoped, 'name="focus" value="all"')

    def test_owner_filter_fragments_keep_scope_fallback_permissions_and_cache(self):
        own = self.payment(self.agreement())
        self.payment(self.agreement(self.other))
        self.plan_request()
        for name, params, key in [('owner_applications', {'customer': self.customer.pk, 'focus': 'all'}, 'applications'),
                                   ('contribution_list', {'customer': self.customer.pk, 'q': own.gateway_reference}, 'contributions'),
                                   ('exception_queue', {'category': 'webhook'}, 'exceptions')]:
            url = reverse('schemes:' + name)
            full = self.client.get(url, params)
            fragment = self.client.get(url, params, HTTP_HX_REQUEST='true')
            self.assertContains(full, '<!DOCTYPE html>')
            self.assertNotContains(fragment, '<!DOCTYPE html>')
            self.assertEqual(len(full.context[key]), len(fragment.context[key]))
            self.assertNotContains(fragment, self.other.email)
            self.assertIn('no-store', fragment['Cache-Control'])
            self.assertIn('HX-Request', fragment['Vary'])
            self.assertLess(len(fragment.content), len(full.content))
            print('HTML payload comparison', name, 'full=', len(full.content), 'fragment=', len(fragment.content))
            self.assertContains(self.client.get(url, params, HTTP_HX_REQUEST='true', HTTP_HX_HISTORY_RESTORE_REQUEST='true'), '<!DOCTYPE html>')
            self.assertEqual(self.client.post(url, HTTP_HX_REQUEST='true').status_code, 405)
            self.client.force_login(self.customer.user)
            self.assertEqual(self.client.get(url, HTTP_HX_REQUEST='true').status_code, 403)
            staff = get_user_model().objects.create_user(username='fragment-staff-' + name, is_staff=True)
            self.client.force_login(staff)
            self.assertEqual(self.client.get(url, HTTP_HX_REQUEST='true').status_code, 403)
            self.client.logout()
            expired = self.client.get(url, params, HTTP_HX_REQUEST='true')
            self.assertIn('HX-Redirect', expired)
            self.assertNotIn(self.customer.email, expired.content.decode())
            self.assertEqual(self.client.get(url).status_code, 302)
            self.client.force_login(self.owner)

    def test_payment_fragment_updates_csv_and_invalid_filter_guidance_together(self):
        contribution = self.payment(self.agreement(), amount='1234.56')
        self.payment(self.agreement(self.other))
        query = {'customer': self.customer.pk, 'mode': 'live', 'status': 'PAID'}
        response = self.client.get(reverse('schemes:contribution_list'), query, HTTP_HX_REQUEST='true')
        self.assertEqual(response.context['scope_summary']['record_count'], 1)
        self.assertContains(response, 'customer=' + str(self.customer.pk))
        self.assertContains(response, 'mode=live')
        self.assertNotContains(response, self.other.email)
        exported = self.client.get(reverse('schemes:contribution_export'), query)
        records = list(csv.DictReader(io.StringIO(exported.content.decode())))
        self.assertEqual(len(records), 1)
        self.assertIn(contribution.gateway_reference, exported.content.decode())
        invalid = self.client.get(reverse('schemes:contribution_list'), {'customer': self.customer.pk, 'status': 'invalid'}, HTTP_HX_REQUEST='true')
        self.assertContains(invalid, 'Check the selected filters')
        self.assertEqual(invalid.context['scope_summary']['record_count'], 0)
        invalid_dates = self.client.get(reverse('schemes:contribution_list'), {'start': '2026-10-22', 'end': '2026-10-01'}, HTTP_HX_REQUEST='true')
        self.assertContains(invalid_dates, 'The to date must be on or after the from date.')
        self.assertContains(invalid_dates, 'Correct the filters to view payment attempts.')
        self.assertNotContains(invalid_dates, '__all__')
        self.assertEqual(self.client.get(reverse('schemes:contribution_export'), {'status': 'invalid'}).status_code, 400)

    def test_exception_categories_are_paginated_before_hydration_and_read_only(self):
        account = self.agreement()
        self.payment(account, status='PAID_UNALLOCATED')
        for i in range(26):
            PaymentWebhookEvent.objects.create(gateway='razorpay', gateway_mode='test', event_type='payment.captured',
                event_id='audit-completion-' + str(i), payload_sha256='a' * 64, status='REVIEW_REQUIRED')
        before = (Contribution.objects.count(), AuditEvent.objects.count(), PaymentWebhookEvent.objects.count())
        url = reverse('schemes:exception_queue')
        with patch('schemes.payments.RazorpayPaymentGateway.verify_payment', side_effect=AssertionError('No provider read')):
            allocations = self.client.get(url, {'category': 'allocation'}, HTTP_HX_REQUEST='true')
            webhooks = self.client.get(url, {'category': 'webhook', 'order': 'oldest', 'page': 2}, HTTP_HX_REQUEST='true')
        self.assertEqual(allocations.context['page_obj'].paginator.count, 1)
        self.assertEqual(webhooks.context['page_obj'].paginator.count, 26)
        self.assertEqual(len(webhooks.context['exceptions']), 1)
        self.assertTrue(webhooks.context['oldest_first'])
        self.assertEqual(before, (Contribution.objects.count(), AuditEvent.objects.count(), PaymentWebhookEvent.objects.count()))

    def privacy_record(self, customer):
        return CustomerAccountDeletionRequest.objects.create(customer=customer, requested_email=customer.email,
            email_digest='a' * 64, source_ip_digest='b' * 64, verification_token_digest=uuid.uuid4().hex * 2,
            source='AUTHENTICATED', status='EXPIRED', policy_version='fixture-v1',
            verification_expires_at=timezone.now() - timedelta(days=1), closed_at=timezone.now())

    def test_customer_privacy_history_is_bounded_scoped_and_never_contained_by_get(self):
        for _ in range(26):
            self.privacy_record(self.customer)
        other = self.privacy_record(self.other)
        before = AuditEvent.objects.count()
        response = self.client.get(reverse('schemes:customer_detail', args=[self.customer.pk]), {'section': 'access'})
        self.assertEqual(response.context['privacy_page'].paginator.count, 26)
        self.assertEqual(len(response.context['privacy_page']), 25)
        self.assertNotContains(response, str(other.pk))
        self.assertContains(response, 'Verification not recorded')
        detail = self.client.get(reverse('customer_account_deletion_detail', args=[self.customer.account_deletion_requests.first().pk]))
        self.assertContains(detail, 'aria-label="Customer context"')
        self.assertContains(detail, reverse('schemes:customer_detail', args=[self.customer.pk]) + '?section=access')
        self.assertEqual(before, AuditEvent.objects.count())
        self.customer.user.refresh_from_db()
        self.assertTrue(self.customer.user.is_active)
        with override_settings(CUSTOMER_ACCOUNT_DELETION_ENABLED=False):
            hidden = self.client.get(reverse('schemes:customer_detail', args=[self.customer.pk]), {'section': 'access'})
            self.assertIsNone(hidden.context['privacy_page'])
            self.assertContains(hidden, 'currently unavailable')
        self.client.force_login(self.customer.user)
        self.assertEqual(self.client.get(reverse('schemes:customer_detail', args=[self.customer.pk]), {'section': 'access'}).status_code, 403)

    def test_print_documents_group_money_keep_precision_and_role_return_destinations(self):
        account = self.agreement()
        payment = self.payment(account, amount='1234567.89')
        # Display fixtures exercise recorded amounts without submitting a financial action.
        for user in [self.owner, self.customer.user]:
            self.client.force_login(user)
            receipt = self.client.get(reverse('schemes:contribution_receipt', args=[payment.pk]))
            statement = self.client.get(reverse('schemes:scheme_statement', args=[account.scheme_number]))
            self.assertContains(receipt, '12,34,567.89')
            self.assertContains(statement, '12,34,567.89')
            self.assertContains(receipt, 'not a tax invoice')
            self.assertContains(statement, 'Document actions')
            self.assertIn('no-store', receipt['Cache-Control'])
            self.assertContains(receipt, 'Back to customer documents' if user == self.owner else 'Back to this plan')
        payment.refresh_from_db()
        self.assertEqual(payment.amount, Decimal('1234567.89'))

    def test_test_receipts_and_statements_cannot_look_like_live_money(self):
        account = self.agreement()
        payment = self.payment(account, mode='test', amount='12500')
        self.client.force_login(self.customer.user)
        receipt = self.client.get(reverse('schemes:contribution_receipt', args=[payment.pk]))
        statement = self.client.get(reverse('schemes:scheme_statement', args=[account.scheme_number]))
        self.assertContains(receipt, 'Test payment acknowledgement')
        self.assertContains(receipt, 'no live payment')
        self.assertContains(receipt, 'Recorded amount')
        self.assertContains(statement, 'Contains Test/practice records')
        self.assertContains(statement, 'Test payment - no live payment')
        self.assertContains(receipt, '12,500.00')


@override_settings(**application_helpers.APPLICATION_SETTINGS)
class ApplicationTimelineTests(application_helpers.ApplicationFixtures, TestCase):
    def setUp(self):
        super().setUp()
        self.start_date = timezone.localdate()

    payment = refinement_helpers.WorkflowRefinementTests.payment

    def test_progress_milestones_come_from_records_not_test_or_pending_attempts(self):
        app = self.ready()
        self.approve(app)
        app.refresh_from_db()
        account = app.scheme_account
        self.assertEqual(next(s['key'] for s in application_timeline(app) if s['current']), 'login')
        user = account.customer.user
        user.set_password('synthetic-password-for-test')
        user.save(update_fields=['password'])
        app = type(app).objects.select_related('registration', 'scheme_account__customer__user').get(pk=app.pk)
        self.assertEqual(next(s['key'] for s in application_timeline(app) if s['current']), 'payment')
        for status in ['PENDING', 'FAILED', 'ABANDONED']:
            self.payment(account, status=status, mode='test')
        test = self.payment(account, mode='test')
        self.assertFalse(application_timeline(app)[-1]['state'] == 'complete')
        self.assertTrue(get_recorded_first_payment(account)['practice_recorded'])
        self.grant(app)
        url = reverse('plan_application_progress', args=[app.registration_id])
        before = Contribution.objects.count()
        response = self.client.get(url)
        self.assertContains(response, 'Test/practice recorded; no live first payment.')
        self.assertEqual(Contribution.objects.count(), before)
        real = self.payment(account, mode='live')
        self.assertEqual(application_timeline(app)[-1]['state'], 'complete')
        self.assertTrue(get_recorded_first_payment(account)['complete'])
        self.assertEqual(self.client.get(url).status_code, 200)

    @override_settings(IN_STORE_CASH_CONTRIBUTIONS_ENABLED=True, PAYMENT_INITIATION_KILL_SWITCH=False)
    def test_preserved_cash_correction_does_not_complete_first_payment(self):
        from schemes.services import publish_scheme_rate, record_in_store_cash_contribution, reverse_in_store_cash_contribution
        app = self.ready()
        account, _ = self.approve(app)
        rate = publish_scheme_rate(metal_grade=self.grade, rate_per_gram=Decimal('10000'), published_by=self.owner)
        paid = record_in_store_cash_contribution(scheme_account=account, amount=Decimal('1000'), expected_scheme_rate_id=rate.pk,
            received_by=self.owner, idempotency_key=uuid.uuid4(), paper_receipt_number='FIXTURE-FIRST', notes='', audit_reason='Synthetic receipt test')
        self.assertTrue(get_recorded_first_payment(account)['complete'])
        reverse_in_store_cash_contribution(contribution=paid, processed_by=self.owner, reason_code='WRONG_AMOUNT', reason='Synthetic correction test')
        self.assertFalse(get_recorded_first_payment(account)['complete'])
        paid.refresh_from_db()
        self.assertEqual(paid.status, 'REVERSED')

    def test_linked_application_is_counted_once_and_changed_terms_are_not_completed(self):
        app = self.ready()
        self.plan.minimum_contribution = Decimal('600')
        self.plan.save(update_fields=['minimum_contribution'])
        self.assertEqual(next(s['key'] for s in application_timeline(app) if s['current']), 'details')
        from schemes.selectors import get_owner_application_stage_counts
        self.assertEqual(get_owner_application_stage_counts(kind='plan')['all'], 1)
        from accounts.applications import complete_plan_application
        self.plan.refresh_from_db()
        self.complete(app)
        app.refresh_from_db()
        self.approve(app)
        app.refresh_from_db()
        self.plan.minimum_contribution = Decimal('700')
        self.plan.save(update_fields=['minimum_contribution'])
        # Later offer edits cannot invalidate an already approved agreement snapshot.
        self.assertEqual(application_timeline(app)[2]['state'], 'complete')
