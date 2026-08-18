# Testing

All commands require the environment variables documented in the README and a PostgreSQL role able to create a test database.

```powershell
uv run --env-file .env python manage.py test
uv run --env-file .env python manage.py test schemes
uv run --env-file .env python manage.py check
uv run --env-file .env python manage.py makemigrations --check --dry-run
```

Current regressions cover amount/frequency enforcement, failed-payment entitlement, confirmation/allocation idempotency, exact metal calculation, historical-rate stability, GoldAPI request/response validation, paid-unallocated recovery, customer isolation, owner liability reconciliation, current-exposure rounding, India-local activity periods, and database constraints. Future suites must add webhook idempotency and over-redemption prevention.

Mock financial tests use `override_settings` for payment and rate configuration. For manual testing, put `DEBUG=True`, `PAYMENT_GATEWAY=mock`, and `METAL_RATE_PROVIDER=mock` in the ignored `.env`, plus optional mock rates.

GoldAPI tests replace the standard-library HTTP opener with deterministic responses; they never use a real key or consume provider quota. To perform an optional live check, set `METAL_RATE_PROVIDER=goldapi` and `GOLDAPI_API_KEY` in the ignored `.env`, open the owner dashboard, and confirm both cards show `goldapi` with recent provider timestamps. Do not put the token in a command, test fixture, screenshot, or committed file.

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
- Redemption checks are added in later milestones

The complete checklist through owner liability reconciliation was exercised over live HTTP for the MVP Alpha checkpoint. The checkpoint created its plan, customer, three enrolments, and three payments through authenticated application forms, compared liability deltas against the pre-run dashboard, and removed all disposable records afterward.

Milestone 5 additionally exercised the recovery path over live HTTP across a development-server restart: a verified payment with an invalid rate remained paid/allocation-pending, both roles saw the correct state, and an owner-only retry after restoring the rate created one 0.800000 g allocation. The smoke harness and tagged records were removed afterward.
