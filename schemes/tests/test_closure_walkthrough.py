from unittest.mock import Mock, patch

from django.test import SimpleTestCase, TestCase, override_settings

from schemes.review_closure_locally import (
    ReviewBanner, ReviewServer, main, parse_arguments, seed_publication_walkthrough, seed_walkthrough,
)


class ClosureWalkthroughIsolationTests(SimpleTestCase):
    def test_browser_preconnections_have_a_timeout_and_daemon_workers(self):
        request = Mock()
        server = object.__new__(ReviewServer)
        with patch("wsgiref.simple_server.WSGIServer.get_request", return_value=(request, ("127.0.0.1", 1234))):
            self.assertEqual(server.get_request(), (request, ("127.0.0.1", 1234)))
        request.settimeout.assert_called_once_with(30)
        self.assertTrue(server.daemon_threads)

    def test_only_explicit_local_modes_are_accepted_before_setup(self):
        self.assertFalse(parse_arguments(["--synthetic-local"]))
        self.assertTrue(parse_arguments(["--synthetic-local", "--check-only"]))
        self.assertFalse(parse_arguments(["--synthetic-local", "--publication-journey"]))
        self.assertTrue(parse_arguments(["--synthetic-local", "--publication-journey", "--check-only"]))
        for arguments in ([], ["--database", "production"], ["--synthetic-local", "--host", "0.0.0.0"],
                          ["--publication-journey"], ["--synthetic-local", "--synthetic-local"]):
            with self.subTest(arguments=arguments), patch("sys.argv", ["review", *arguments]), patch("django.setup") as setup:
                with self.assertRaises(RuntimeError):
                    main()
                setup.assert_not_called()

    def test_banner_marks_html_without_changing_non_html_responses(self):
        for content_type, body in (("text/html", b'<html><body class="app">Page</body></html>'),
                                   ("application/json", b'{"ok":true}')):
            def application(environ, start_response):
                start_response("200 OK", [("Content-Type", content_type), ("Content-Length", str(len(body)))])
                return [body]
            captured = {}
            def response_start(status, headers, exc_info=None):
                captured.update(status=status, headers=dict(headers))
            result = b"".join(ReviewBanner(application)({}, response_start))
            self.assertEqual(int(captured["headers"]["Content-Length"]), len(result))
            if content_type == "text/html":
                self.assertIn(b"SYNTHETIC LOCAL REVIEW ONLY", result)
                self.assertEqual(captured["headers"]["Cache-Control"], "no-store")
            else:
                self.assertEqual(body, result)


@override_settings(IN_STORE_CASH_CONTRIBUTIONS_ENABLED=True, PAYMENT_GATEWAY="",
                   EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class ClosureWalkthroughSeedTests(TestCase):
    def test_review_scenarios_have_exact_synthetic_sources_and_gates_remain_shut(self):
        from decimal import Decimal
        from schemes.models import Contribution, MetalAllocation, Redemption
        from schemes.selectors import get_metal_balance
        from schemes.closure_selectors import validate_closure_history
        from schemes.settlements import reverse_configured_settlement
        import uuid

        owner, customer, accounts, closure = seed_walkthrough("Synthetic-local-only-123!")
        self.assertEqual(len(accounts), 3)
        self.assertFalse(accounts["unused"].contributions.exists())
        self.assertEqual(get_metal_balance(accounts["three-paid"]), Decimal("0.300000"))
        self.assertEqual(accounts["three-paid"].contributions.count(), 3)
        accounts["correction"].refresh_from_db()
        self.assertEqual(accounts["correction"].status, "REDEEMED")
        self.assertEqual(get_metal_balance(accounts["correction"]), 0)
        closure.refresh_from_db()
        self.assertEqual(validate_closure_history(closure), 3)
        self.assertEqual(Contribution.objects.count(), 6)
        self.assertEqual(MetalAllocation.objects.count(), 6)
        self.assertEqual(Redemption.objects.count(), 1)
        self.assertTrue(customer.user.is_active)
        self.assertFalse(accounts["unused"].plan.active)
        self.assertFalse(accounts["unused"].plan.publicly_listed)
        settlement = closure.settlements.get()
        reverse_configured_settlement(settlement_id=settlement.pk, actor=owner,
            authorization_reference="DEMO-CORRECTION", reason="Synthetic review", expected_sequence=3,
            idempotency_key=uuid.uuid4())
        self.assertEqual(get_metal_balance(accounts["correction"]), Decimal("0.300000"))


@override_settings(CONFIGURED_PLANS_ENABLED=True, CUSTOMER_ENROLMENT_REQUESTS_ENABLED=True,
                   IN_STORE_CASH_CONTRIBUTIONS_ENABLED=True, PAYMENT_GATEWAY="",
                   EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class PublicationWalkthroughSeedTests(TestCase):
    def test_seed_contains_two_unpublished_offers_and_no_financial_history(self):
        from schemes.models import Contribution, MetalAllocation, Redemption, SchemeAccount, SchemeEnrolmentRequest
        from schemes.selectors import get_public_scheme_plans
        from django.urls import reverse

        owner, customer, plans = seed_publication_walkthrough("Synthetic-local-only-123!")
        self.assertEqual(set(plans), {"calendar", "monthly"})
        self.assertFalse(get_public_scheme_plans().exists())
        for model in (SchemeAccount, SchemeEnrolmentRequest, Contribution, MetalAllocation, Redemption):
            self.assertEqual(model.objects.count(), 0)
        for plan in plans.values():
            self.assertFalse(plan.active or plan.publicly_listed)
            self.assertIsNone(plan.publication_revision_id)
            self.client.force_login(owner)
            self.assertEqual(self.client.get(reverse("schemes:configured_plan_publication", args=[plan.pk])).status_code, 200)
            self.client.force_login(customer.user)
            self.assertEqual(self.client.get(reverse("schemes:configured_plan_publication", args=[plan.pk])).status_code, 403)

    def test_both_seeded_offers_support_actual_publication_request_enrolment_and_full_closure(self):
        import uuid
        from decimal import Decimal
        from io import StringIO

        from django.core.management import call_command
        from django.utils import timezone
        from schemes.closures import request_scheme_closure, review_scheme_closure
        from schemes.models import SchemeAccount, SchemeEnrolmentRequest, SchemeRate
        from schemes.plan_governance import plan_edit_digest
        from schemes.plan_publication import set_configured_plan_publication
        from schemes.selectors import get_metal_balance
        from schemes.services import (
            enroll_customer_from_request, record_in_store_cash_contribution, submit_scheme_enrolment_request,
        )
        from schemes.settlements import preview_full_settlement, settle_configured_agreement

        owner, customer, plans = seed_publication_walkthrough("Synthetic-local-only-123!")
        rate = SchemeRate.objects.get()
        for label, plan in plans.items():
            with self.subTest(plan=label):
                set_configured_plan_publication(plan_id=plan.pk, publish=True, actor=owner,
                    reason="Synthetic review", expected_digest=plan_edit_digest(plan), confirmed=True)
                before = SchemeAccount.objects.count()
                submit_scheme_enrolment_request(customer=customer, plan=plan, metal_grade=rate.metal_grade,
                    requested_contribution_amount=Decimal("1000"), requested_months=12,
                    customer_message="Synthetic request", actor=customer.user)
                self.assertEqual(SchemeAccount.objects.count(), before)
                request = SchemeEnrolmentRequest.objects.get(plan=plan)
                account, created = enroll_customer_from_request(enrolment_request=request, actor=owner,
                    current_terms_confirmed=True, start_date=timezone.localdate(), agreed_months=12,
                    reason="Synthetic confirmed choice")
                self.assertTrue(created)
                self.assertEqual(account.fixed_amount_snapshot, Decimal("1000"))
                self.assertEqual(account.instalment_periods.count(), 15 if label == "monthly" else 0)
                record_in_store_cash_contribution(scheme_account=account, amount=Decimal("1000"),
                    expected_scheme_rate_id=rate.pk, received_by=owner, idempotency_key=uuid.uuid4(),
                    notes="SYNTHETIC ONLY: no cash received", audit_reason="Synthetic test")
                self.assertEqual(get_metal_balance(account), Decimal("0.100000"))
                closure = request_scheme_closure(account_id=account.pk, actor=customer.user,
                    reason="Synthetic early full closure", idempotency_key=uuid.uuid4())
                review_scheme_closure(request_id=closure.pk, actor=owner, action="ACCEPT",
                    reason="Synthetic customer consent", idempotency_key=uuid.uuid4(), expected_sequence=1)
                # Existing obligations remain settleable if future offer intake is disabled.
                with self.settings(CONFIGURED_PLANS_ENABLED=False):
                    _, token = preview_full_settlement(request_id=closure.pk, actor=owner)
                    settle_configured_agreement(request_id=closure.pk, actor=owner, preview_token=token,
                        invoice_reference=f"DEMO-{label}", authorization_reference="DEMO-FULFILMENT",
                        reason="SYNTHETIC ONLY: no jewellery delivered", idempotency_key=uuid.uuid4())
                account.refresh_from_db()
                self.assertEqual(account.status, "REDEEMED")
                self.assertEqual(get_metal_balance(account), 0)
        for command in ("check_plan_configurations", "check_scheme_closures", "check_instalment_payments"):
            output = StringIO()
            call_command(command, stdout=output)
            self.assertIn("status=ok", output.getvalue())
