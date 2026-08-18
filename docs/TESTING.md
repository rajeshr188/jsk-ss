# Testing

All commands require the environment variables documented in the README and a PostgreSQL role able to create a test database.

```powershell
uv run python manage.py test
uv run python manage.py test schemes
uv run python manage.py check
uv run python manage.py makemigrations --check --dry-run
```

Critical future regressions cover amount/frequency enforcement, failed-payment entitlement, exact metal allocation, allocation/webhook idempotency, customer isolation, over-redemption prevention, and owner/customer liability reconciliation.

Mock payment and rate-provider setup will be documented with Milestones 2 and 3.

## Manual smoke test

- Owner login and logout
- Password-reset request renders and sends through the configured backend
- Admin opens for a superuser
- Create a plan and customer
- Enrol the customer
- Customer login shows only that customer's schemes
- Contribution, allocation/balance, owner liability, and redemption checks are added in later milestones

