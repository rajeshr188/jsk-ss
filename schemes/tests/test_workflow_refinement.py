import csv
import io
import uuid
from decimal import Decimal
from datetime import timedelta
from unittest.mock import patch
from urllib.parse import urlencode

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from schemes.models import Contribution, SchemeAccount, AuditEvent, MetalAllocation
from schemes.navigation import application_inbox_url
from schemes.services import enroll_customer, publish_scheme_rate
from schemes.tests import test_owner_workspace as workspace_helpers
from schemes.templatetags.workspace import inr


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
                   EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
                   CUSTOMER_ENROLMENT_REQUESTS_ENABLED=True,
                   IN_STORE_CASH_CONTRIBUTIONS_ENABLED=True,
                   PAYMENT_INITIATION_KILL_SWITCH=False)
class WorkflowRefinementTests(TestCase):
    setUp = workspace_helpers.OwnerWorkspaceTests.setUp
    registration = workspace_helpers.OwnerWorkspaceTests.registration
    plan_request = workspace_helpers.OwnerWorkspaceTests.plan_request

    def agreement(self, customer=None):
        return enroll_customer(customer=customer or self.customer, plan=self.plan,
                               metal_grade=self.grade, start_date=timezone.localdate(),
                               performed_by=self.owner, reason='Synthetic workflow fixture')

    def payment(self, account, status='PAID', mode='live', amount='500'):
        key = uuid.uuid4().hex
        return Contribution.objects.create(
            scheme_account=account, amount=Decimal(amount), status=status,
            contribution_period=timezone.localdate().replace(day=1),
            frequency_rule_snapshot='FLEXIBLE', payment_gateway='razorpay', gateway_mode=mode,
            gateway_order_id='order_' + key, checkout_expires_at=timezone.now() + timedelta(minutes=15),
            gateway_reference='pay_' + key if status in {'PAID', 'PAID_UNALLOCATED'} else None,
            paid_at=timezone.now() if status in {'PAID', 'PAID_UNALLOCATED'} else None,
        )

    def test_payment_scope_matches_export_and_separates_live_test(self):
        own = self.agreement()
        real = self.payment(own, amount='700')
        self.payment(own, mode='test', amount='200')
        pending = self.payment(own, status='PENDING', amount='100')
        other = self.payment(self.agreement(self.other), amount='900')
        params = {'customer': self.customer.pk}
        response = self.client.get(reverse('schemes:contribution_list'), params)
        self.assertEqual(response.context['scope_summary']['record_count'], 3)
        self.assertEqual(response.context['scope_summary']['received_amount'], Decimal('700'))
        self.assertEqual(response.context['scope_summary']['test_amount'], Decimal('200'))
        self.assertIsNone(response.context['daily_summary'])
        self.assertNotContains(response, 'Whole-business totals today')
        exported = self.client.get(reverse('schemes:contribution_export'), params)
        records = list(csv.DictReader(io.StringIO(exported.content.decode())))
        self.assertEqual(len(records), 2)
        self.assertNotIn(other.gateway_reference, exported.content.decode())
        self.assertNotIn(pending.gateway_order_id, exported.content.decode())
        named = self.client.get(reverse('schemes:contribution_list'), {**params, 'q': self.plan.name})
        self.assertEqual(named.context['page_obj'].paginator.count, 3)
        self.assertNotContains(named, self.other.email)
        for extra in [{'q': real.gateway_reference}, {'status': 'PAID', 'mode': 'live'}]:
            query = {**params, **extra}
            listing = self.client.get(reverse('schemes:contribution_list'), query)
            self.assertEqual([c.pk for c in listing.context['contributions']], [real.pk])
            data = self.client.get(reverse('schemes:contribution_export'), query).content.decode()
            self.assertIn(real.gateway_reference, data)
            self.assertNotIn(other.gateway_reference, data)

    def test_invalid_filters_fail_closed_and_exact_scope_cannot_escape_customer(self):
        own = self.payment(self.agreement())
        other = self.payment(self.agreement(self.other))
        for params in [{'status': 'invented'}, {'mode': 'invented'}, {'start': 'invalid'},
                       {'start': '2026-10-10', 'end': '2026-01-01'}]:
            response = self.client.get(reverse('schemes:contribution_list'), params)
            self.assertEqual(response.context['page_obj'].paginator.count, 0)
            self.assertEqual(self.client.get(reverse('schemes:contribution_export'), params).status_code, 400)
        for route in ['contribution_list', 'contribution_export']:
            self.assertEqual(self.client.get(reverse('schemes:' + route), {'customer': self.customer.pk, 'contribution': other.pk}).status_code, 404)
        response = self.client.get(reverse('schemes:contribution_list'), {'contribution': own.pk})
        self.assertEqual([c.pk for c in response.context['contributions']], [own.pk])

    def test_cash_get_explains_pending_before_form_without_financial_side_effects(self):
        account = self.agreement()
        pending = self.payment(account, status='PENDING')
        counts = (Contribution.objects.count(), AuditEvent.objects.count(), MetalAllocation.objects.count())
        with patch('schemes.payments.RazorpayPaymentGateway.verify_payment', side_effect=AssertionError('No provider on GET')):
            response = self.client.get(reverse('schemes:in_store_cash_contribution', args=[account.scheme_number]))
        self.assertContains(response, 'awaiting reconciliation')
        self.assertContains(response, reverse('schemes:owner_payment_detail', args=[pending.pk]))
        self.assertNotContains(response, 'name="amount"')
        self.assertEqual(counts, (Contribution.objects.count(), AuditEvent.objects.count(), MetalAllocation.objects.count()))

    def test_applicant_search_and_safe_return_context(self):
        selected = self.registration(1)
        self.registration(2)
        response = self.client.get(reverse('schemes:owner_applications'), {'q': selected.email})
        self.assertEqual([item.record.pk for item in response.context['applications']], [selected.pk])
        destination = reverse('schemes:owner_applications') + '?q=Applicant&focus=all&page=2'
        review = self.client.get(reverse('customer_registration_detail', args=[selected.pk]), {'return_to': destination})
        self.assertContains(review, 'name="return_to"')
        self.assertEqual(review.context['application_inbox_url'], destination)
        from django.test import RequestFactory
        for bad in ['https://external.example/', '//external.example/', '/accounts/login/', destination + '#bad', '/schemes/applications/\\external']:
            self.assertEqual(application_inbox_url(RequestFactory().get('/', {'return_to': bad})), reverse('schemes:owner_applications'))
        posted = self.client.post(reverse('customer_registration_reject', args=[selected.pk]), {'reason': 'Synthetic rejection review', 'return_to': destination})
        self.assertRedirects(posted, destination, fetch_redirect_response=False)

    def test_fragments_keep_authorization_private_cache_and_full_page_fallback(self):
        url = reverse('schemes:customer_list')
        normal = self.client.get(url, {'q': self.customer.email})
        fragment = self.client.get(url, {'q': self.customer.email}, HTTP_HX_REQUEST='true')
        self.assertContains(normal, '<!DOCTYPE html>')
        self.assertNotContains(fragment, '<!DOCTYPE html>')
        self.assertContains(fragment, self.customer.full_name)
        self.assertNotContains(fragment, self.other.email)
        self.assertIn('no-store', fragment['Cache-Control'])
        self.assertIn('HX-Request', fragment['Vary'])
        self.assertContains(normal, '"historyCacheSize":0')
        restored = self.client.get(url, HTTP_HX_REQUEST='true', HTTP_HX_HISTORY_RESTORE_REQUEST='true')
        self.assertContains(restored, '<!DOCTYPE html>')
        self.assertEqual(self.client.post(url, HTTP_HX_REQUEST='true').status_code, 405)
        for user in [self.customer.user, get_user_model().objects.create_user(username='editor', is_staff=True)]:
            self.client.force_login(user)
            self.assertEqual(self.client.get(url, HTTP_HX_REQUEST='true').status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(url).status_code, 302)
        expired = self.client.get(url, HTTP_HX_REQUEST='true')
        self.assertEqual(expired.status_code, 200)
        self.assertTrue(expired['HX-Redirect'].startswith(reverse('account_login')))
        self.assertNotIn(self.customer.email, expired.content.decode())
        self.assertIn('no-store', expired['Cache-Control'])

    def test_customer_documents_applications_and_history_are_scoped_and_bounded(self):
        account = self.agreement()
        other = self.payment(self.agreement(self.other))
        for _ in range(26):
            self.payment(account)
        self.plan_request()
        self.plan_request(self.other)
        self.client.force_login(self.customer.user)
        docs = self.client.get(reverse('schemes:customer_documents'))
        self.assertEqual(docs.context['page_obj'].paginator.count, 26)
        self.assertEqual(len(docs.context['receipts']), 25)
        self.assertNotContains(docs, other.gateway_reference)
        apps = self.client.get(reverse('schemes:customer_applications'))
        self.assertEqual(apps.context['page_obj'].paginator.count, 1)
        self.assertNotContains(apps, self.other.email)
        detail = self.client.get(reverse('schemes:my_scheme_detail', args=[account.scheme_number]))
        self.assertEqual(len(detail.context['contributions']), 25)
        self.assertEqual(detail.context['page_obj'].paginator.count, 26)
        self.assertContains(detail, 'Agreed plan terms')
        self.assertEqual(self.client.get(reverse('schemes:owner_payment_detail', args=[other.pk])).status_code, 403)

    def test_dashboard_one_primary_payment_action_and_status_get_remains_read_only(self):
        account = self.agreement()
        pending = self.payment(account, status='PENDING', mode='test')
        self.client.force_login(self.customer.user)
        home = self.client.get(reverse('schemes:my_schemes'))
        self.assertContains(home, 'View payment status', count=1)
        url = reverse('schemes:payment_status', args=[pending.pk])
        with patch('schemes.payments.RazorpayPaymentGateway.verify_payment', side_effect=AssertionError('No verification on refresh')):
            fragment = self.client.get(url, HTTP_HX_REQUEST='true')
        self.assertNotContains(fragment, '<!DOCTYPE html>')
        self.assertContains(fragment, 'Recorded status checked')
        pending.refresh_from_db()
        self.assertEqual(pending.status, 'PENDING')
        self.client.force_login(self.other.user)
        self.assertEqual(self.client.get(url, HTTP_HX_REQUEST='true').status_code, 404)

    def test_owner_customer_sections_remain_bounded(self):
        for _ in range(13):
            self.agreement()
        url = reverse('schemes:customer_detail', args=[self.customer.pk])
        response = self.client.get(url, {'section': 'documents'})
        self.assertEqual(len(response.context['page_obj'].object_list), 12)
        self.assertContains(response, 'View statement', count=12)
        self.assertNotContains(response, 'Record in-store cash')
        self.assertContains(self.client.get(url, {'section': 'access'}), 'Customer login')

    def test_display_grouping_preserves_decimal_precision(self):
        self.assertEqual(inr(Decimal('1234567.89')), '12,34,567.89')
        self.assertEqual(inr(Decimal('-10000.1234'), 4), '-10,000.1234')
        self.assertEqual(inr(Decimal('0')), '0.00')
        self.assertEqual(inr(Decimal('NaN')), '\u2014')

    def test_private_search_and_return_queries_are_not_logged(self):
        from accounts.logging import redact_sensitive_auth_paths
        for path in ['/scheme/owner/customers/?q=private@example.com',
                     '/scheme/owner/contributions/?q=pay_private&status=PAID',
                     '/accounts/owner/registrations/record/?return_to=%2Fscheme%2Fowner%2Fapplications%2F%3Fq%3Dprivate']:
            result = redact_sensitive_auth_paths('GET ' + path + ' HTTP/1.1 200')
            self.assertNotIn('private', result)
            self.assertIn('HTTP/1.1 200', result)
            self.assertIn('[REDACTED]', result)
