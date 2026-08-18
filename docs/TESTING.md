# Testing

All commands require the environment variables documented in the README and a PostgreSQL role able to create a test database.

```powershell
uv run --env-file .env python manage.py test
uv run --env-file .env python manage.py test schemes
uv run --env-file .env python manage.py check
uv run --env-file .env python manage.py makemigrations --check --dry-run
```

Current regressions cover amount/frequency enforcement, failed-payment entitlement, payment confirmation idempotency, customer isolation, and database constraints. Future suites must add exact metal allocation, webhook idempotency, over-redemption prevention, and owner/customer liability reconciliation.

Mock payment tests use `override_settings(DEBUG=True, PAYMENT_GATEWAY="mock")`. For manual testing, put `DEBUG=True` and `PAYMENT_GATEWAY=mock` in the ignored `.env`. Mock rates remain deferred to Milestone 3.

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
- Allocation, owner liability, and redemption checks are added in later milestones
