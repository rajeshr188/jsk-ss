# Testing

All commands require the environment variables documented in the README and a PostgreSQL role able to create a test database.

```powershell
uv run --env-file .env python manage.py test
uv run --env-file .env python manage.py test schemes
uv run --env-file .env python manage.py check
uv run --env-file .env python manage.py makemigrations --check --dry-run
```

Current regressions cover amount/frequency enforcement, failed-payment entitlement, confirmation/allocation idempotency, Razorpay order/API/HMAC boundaries, duplicate callbacks and webhooks, exact metal calculation, historical-rate stability, GoldAPI request/response validation, paid-unallocated recovery, customer isolation, owner liability reconciliation, current-exposure rounding, India-local activity periods, eligibility status and exact 30/60/90-day boundaries, redemption idempotency and precision, partial/full settlement, over-redemption prevention, denomination separation, immutable history, and database constraints.

Mock financial tests use `override_settings` for payment and rate configuration. For manual testing, put `DEBUG=True`, `PAYMENT_GATEWAY=mock`, and `METAL_RATE_PROVIDER=mock` in the ignored `.env`, plus optional mock rates.

GoldAPI tests replace the standard-library HTTP opener with deterministic responses; they never use a real key or consume provider quota. To perform an optional live check, set `METAL_RATE_PROVIDER=goldapi` and `GOLDAPI_API_KEY` in the ignored `.env`, open the owner dashboard, and confirm both cards show `goldapi` with recent provider timestamps. Do not put the token in a command, test fixture, screenshot, or committed file.

Razorpay tests likewise replace the HTTPS boundary with deterministic order and payment responses. They verify raw-body webhook HMAC, invalid-callback rejection, captured-payment matching, duplicate callback/webhook idempotency, one metal allocation, and customer isolation without using provider credentials. For an external test-mode smoke, use private test keys, expose the webhook endpoint over HTTPS, subscribe to `payment.captured`, and confirm one test payment produces one contribution benefit and one processed webhook event. Use Razorpay's documented Test Mode instruments: select Netbanking and choose **Success**, enter `success@razorpay` for UPI, or use a documented domestic test card and complete the simulated OTP page. A payment left at provider status `created` has not been authorized and must not create entitlement.

## Manual smoke test

- Owner login and logout
- Password-reset request renders and sends through the configured backend
- Admin opens for a superuser
- Create a plan and customer
- Enrol the customer
- Customer login shows only that customer's schemes
- Make a cash mock contribution and confirm the cash principal/history update
- Confirm a second monthly contribution is rejected while flexible contributions can repeat
- Confirm the owner contribution list shows the payment
- Make gold and silver contributions and confirm gram balances/history use their captured rates
- Change a mock rate and confirm earlier allocations remain unchanged
- Confirm the owner dashboard reconciles cash principal, gold grams, and silver grams separately
- Confirm current gold/silver reference rates and indicative exposures update without changing historical allocations
- Confirm contribution-today/month counts include successful payments only
- Simulate a rate failure and confirm payment remains visibly paid/allocation-pending with no invented grams
- Restore the provider and confirm the owner retry creates one allocation and clears the exception
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

The complete checklist through owner liability reconciliation was exercised over live HTTP for the MVP Alpha checkpoint. The checkpoint created its plan, customer, three enrolments, and three payments through authenticated application forms, compared liability deltas against the pre-run dashboard, and removed all disposable records afterward.

Milestone 5 additionally exercised the recovery path over live HTTP across a development-server restart: a verified payment with an invalid rate remained paid/allocation-pending, both roles saw the correct state, and an owner-only retry after restoring the rate created one 0.800000 g allocation. The smoke harness and tagged records were removed afterward.

Milestone 7 exercised owner and customer sessions over live HTTP: the owner dashboard and grouped eligibility view showed the tagged account in eligible-now, the customer saw redemption-eligible guidance, and a direct database check confirmed the account remained stored as `ACTIVE`. The temporary server and tagged records were removed afterward.

Milestone 8 exercised authenticated owner and customer request flows with CSRF enforcement against the configured PostgreSQL database. The owner recorded a partial cash settlement followed by final jewellery-purchase settlement; the account moved from eligible/open to redeemed only at zero outstanding, the customer retained contribution and redemption history with no further payment action, owner cash liability returned to its baseline, and all tagged records were removed.

The MVP Beta checkpoint exercised a real Razorpay Test Mode order over a temporary public HTTPS endpoint. Razorpay reported the ₹100 payment as captured, the signed `payment.captured` webhook was stored and processed once, and Django created one paid cash contribution. The same eligible account was then fully redeemed through the CSRF-protected owner form; its outstanding cash and the owner cash-principal liability both returned to zero. Temporary quick tunnels are development-only and their URL and webhook secret must be synchronized in the Razorpay Test Mode dashboard for each run.
