# Testing

All commands require the environment variables documented in the README and a PostgreSQL role able to create a test database.

```powershell
uv run --env-file .env python manage.py test
uv run --env-file .env python manage.py test schemes
uv run --env-file .env python manage.py check
uv run --env-file .env python manage.py makemigrations --check --dry-run
```

Current regressions cover amount/frequency enforcement, failed-payment entitlement, confirmation/allocation idempotency, exact metal calculation, historical-rate stability, customer isolation, owner liability reconciliation, current-exposure rounding, India-local activity periods, and database constraints. Future suites must add webhook idempotency and over-redemption prevention.

Mock financial tests use `override_settings` for payment and rate configuration. For manual testing, put `DEBUG=True`, `PAYMENT_GATEWAY=mock`, and `METAL_RATE_PROVIDER=mock` in the ignored `.env`, plus optional mock rates.

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
- Redemption checks are added in later milestones
