# Testing

All commands require the environment variables documented in the README and a PostgreSQL role able to create a test database.

```powershell
uv run --env-file .env python manage.py test
uv run --env-file .env python manage.py test schemes
uv run --env-file .env python manage.py check
uv run --env-file .env python manage.py makemigrations --check --dry-run
```

Authentication regressions cover closed public signup, owner-only digest-backed
customer invitations, bounded expiry and one-time acceptance, resend supersession,
provider failure/retry, direct untracked email links, token-response privacy headers,
edge/access-log exclusion, Django warning/error token redaction, case-insensitive
login-email uniqueness, and login/enrolment separation.

Current regressions cover amount/frequency enforcement, failed-payment entitlement, confirmation/allocation idempotency, Razorpay order/API/HMAC boundaries, duplicate callbacks and webhooks, owner-only Scheme Rate publication, publication validation/warnings, GOLD/SILVER no-rate payment blocking with unaffected CASH orders, pre-order rate locking, durable verified-metal-payment recovery, exact metal calculation, historical-rate stability, paid-unallocated recovery from the original lock, production-shaped `schemes.0009` to `0010` history backfill and blocker behavior, customer isolation, owner liability reconciliation, current-exposure rounding, India-local activity periods, eligibility status and exact 30/60/90-day boundaries, versioned cash-bonus snapshots, projection-versus-earned boundaries, eligibility cutoff, half-up bonus rounding, principal/bonus redemption allocation, redemption idempotency and precision, partial/full settlement, over-redemption prevention, denomination separation, immutable audit/reversal history, exception classification, reversal liability restoration, stable receipt numbering, unallocated-document disclosure, statement source filtering, document/export access control, CSV denomination/formula safety, and database constraints.

Mock financial tests use `override_settings` only for payment configuration. For manual testing, put `DJANGO_DEBUG=True` and `PAYMENT_GATEWAY=mock` in the ignored `.env`, sign in as the owner, and publish gold and silver rates before testing metal payments.

Razorpay tests likewise replace the HTTPS boundary with deterministic order and payment responses. They verify raw-body webhook HMAC, invalid-callback rejection, captured-payment matching, duplicate callback/webhook idempotency, one metal allocation, and customer isolation without using provider credentials. For an external test-mode smoke, use private test keys, expose the webhook endpoint over HTTPS, subscribe to `payment.captured`, and confirm one test payment produces one contribution benefit and one processed webhook event. Use Razorpay's documented Test Mode instruments: select Netbanking and choose **Success**, enter `success@razorpay` for UPI, or use a documented domestic test card and complete the simulated OTP page. A payment left at provider status `created` has not been authorized and must not create entitlement.

## Manual smoke test

- Owner login and logout
- Password-reset request renders and sends through the configured backend
- Create a customer as owner, verify the customer chooses their own password from the
  direct owned-domain invitation link, and confirm no scheme account was created
- Resend an unused invitation, verify the old link is unavailable, and confirm an
  activated customer is directed to password reset instead
- Admin opens for a superuser
- Create a plan and customer
- Enrol the customer
- Customer login shows only that customer's schemes
- Make a cash mock contribution and confirm the cash principal/history update
- Confirm a second monthly contribution is rejected while flexible contributions can repeat
- Confirm the owner contribution list shows the payment
- Publish gold and silver Scheme Rates as the owner and confirm the append-only history and audit entry
- Attempt a large rate change and confirm the extra warning/confirmation is required
- Make gold and silver contributions and confirm gram balances/history use their locked Scheme Rates
- Start a metal checkout, publish a new rate, complete the original payment, and confirm it uses the old lock while a new checkout uses the new rate
- Confirm the owner dashboard reconciles cash principal, gold grams, and silver grams separately
- Confirm current gold/silver Scheme Rates and indicative exposures update without changing historical allocations
- Confirm contribution-today/month counts include successful payments only
- Remove all applicable rates in a disposable database and confirm metal payment/order creation is blocked while cash remains available
- Simulate an unexpected allocation exception and confirm owner retry reuses the original locked rate
- Switch to private Razorpay test credentials, create an order, complete Standard Checkout, and confirm the callback and `payment.captured` webhook still produce exactly one benefit
- Repeat the same signed webhook and confirm the contribution, balance, and allocation counts remain unchanged
- Confirm the owner eligibility view groups accounts into eligible now, days 1–30, 31–60, 61–90, later, and redeemed without overlap
- Confirm an eligible customer sees the new status while the underlying account remains open
- Record a partial cash redemption and confirm the customer and owner balances decrease while the account remains redemption eligible
- Complete the remaining cash redemption and confirm the account becomes redeemed while all contribution/redemption history remains visible
- Record gold and silver redemptions and confirm only the matching gram liability decreases
- Confirm jewellery-purchase settlement requires an invoice/reference and records the supplied notes
- Repeat a redemption submission with the same idempotency key and confirm it creates no duplicate event
- Confirm customers cannot access owner redemption actions
- Create a cash-bonus plan and confirm enrolment snapshots its policy version, percentage, and minimum duration
- Before eligibility, confirm projected bonus is visible but excluded from redeemable amount and owner liability
- At eligibility, confirm earned bonus includes only principal paid by the cutoff and post-eligibility contributions do not alter it
- Redeem cash partially and fully; confirm principal is consumed before bonus and both immutable components reconcile
- Edit a plan with an audit reason and confirm existing enrolment snapshots remain unchanged
- Confirm owner enrolment, redemption, and allocation retry actions appear with actor, timestamp, and reason in the audit log
- Create a paid-unallocated contribution or failed webhook event and confirm the owner exception queue classifies it without changing entitlement
- Reverse a redemption and confirm the original remains visible, the restored liability reconciles, and the account reopens when necessary
- Print cash and metal receipts and confirm stable references, payment references, captured rates, and six-decimal allocations
- Confirm pending/failed attempts have no receipt and paid-unallocated receipts show no invented rate or quantity
- Print each customer scheme statement and reconcile its remaining entitlement with the customer detail view
- Download owner contribution/redemption CSV exports and confirm INR, gold grams, and silver grams remain separate

The complete checklist through owner liability reconciliation was exercised over live HTTP for the MVP Alpha checkpoint. The checkpoint created its plan, customer, three enrolments, and three payments through authenticated application forms, compared liability deltas against the pre-run dashboard, and removed all disposable records afterward.

Historical Milestone 5 testing exercised the former provider-recovery path. ADR-0003
supersedes that architecture; current tests instead cover owner publication,
pre-payment locking, no-rate blocking, and retry from an existing lock.

Milestone 7 exercised owner and customer sessions over live HTTP: the owner dashboard and grouped eligibility view showed the tagged account in eligible-now, the customer saw redemption-eligible guidance, and a direct database check confirmed the account remained stored as `ACTIVE`. The temporary server and tagged records were removed afterward.

Milestone 8 exercised authenticated owner and customer request flows with CSRF enforcement against the configured PostgreSQL database. The owner recorded a partial cash settlement followed by final jewellery-purchase settlement; the account moved from eligible/open to redeemed only at zero outstanding, the customer retained contribution and redemption history with no further payment action, owner cash liability returned to its baseline, and all tagged records were removed.

The MVP Beta checkpoint exercised a real Razorpay Test Mode order over a temporary public HTTPS endpoint. Razorpay reported the ₹100 payment as captured, the signed `payment.captured` webhook was stored and processed once, and Django created one paid cash contribution. The same eligible account was then fully redeemed through the CSRF-protected owner form; its outstanding cash and the owner cash-principal liability both returned to zero. Temporary quick tunnels are development-only and their URL and webhook secret must be synchronized in the Razorpay Test Mode dashboard for each run.

Milestone 9 exercised authenticated owner/customer forms inside a rollback-only PostgreSQL transaction. The owner created a 5%/12-month plan and enrolment, the customer completed a ₹100 mock payment before eligibility, the account aged into eligibility with ₹5 earned bonus, and the owner redeemed ₹105. The immutable redemption stored ₹100 principal plus ₹5 bonus, closed the account, and returned owner cash liability exactly to its baseline; no smoke records persisted.

Milestone 10 exercised an owner workflow inside a rollback-only PostgreSQL transaction. Audited enrolment, a ₹100 completed cash redemption, and its compensating reversal produced exactly three immutable audit events; the original redemption remained, the account reopened, and the ₹100 entitlement was restored. Authenticated owner audit and exception pages returned successfully, and no tagged smoke records persisted.

Milestone 11 exercised authenticated customer and owner document reads inside a rollback-only PostgreSQL transaction. A ₹1,000 mock gold contribution produced a stable printable receipt and a scheme statement showing the captured ₹12,500/g rate and 0.080000 g entitlement; owner contribution/redemption CSV exports returned successfully with separated denomination fields. No tagged smoke records persisted.
