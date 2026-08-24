# Jai Sri Krishna Jewelley Savings Scheme

A single-business Django application for managing customer cash, 24K gold, and silver savings schemes. It reuses the [Lithium](https://github.com/wsvincent/lithium) Django foundation and now includes owner-managed enrolment, verified contributions, versioned cash bonus, immutable metal allocations, eligibility, an owner exception queue, and append-oriented audit/reversal records.

## Technology

- Python 3.12+, Django 6, PostgreSQL
- Lithium's `accounts.CustomUser`, django-allauth, Bootstrap 5, crispy forms
- WhiteNoise, Gunicorn, psycopg, and `uv`

## Quick start

1. Install PostgreSQL and create an application database/user.
2. Copy `.env.example` to `.env` and replace its placeholders. Django does not read `.env` itself; use `uv run --env-file .env ...` or export the values through your shell/IDE.
3. Install dependencies: `uv sync --frozen`.
4. Apply migrations: `uv run --env-file .env python manage.py migrate`.
5. Create the owner: `uv run --env-file .env python manage.py createsuperuser`. A superuser is always authorized as an owner; its application role can also be set to `OWNER` in admin.
6. Start the server: `uv run --env-file .env python manage.py runserver`.

PowerShell example for the current session:

```powershell
$env:DJANGO_SECRET_KEY = "local-development-only"
$env:DJANGO_DEBUG = "True"
$env:ALLOWED_HOSTS = "localhost,127.0.0.1"
$env:DATABASE_URL = "postgresql://jsk_user:password@localhost:5432/jsk_savings"
uv run python manage.py migrate
uv run python manage.py runserver
```

Alternatively, set `DJANGO_SECRET_KEY` and run `docker compose up --build`; Compose provides an isolated development-only PostgreSQL database.

## Environment variables

| Variable | Required | Purpose |
| --- | --- | --- |
| `DJANGO_SECRET_KEY` | yes | Django cryptographic signing secret |
| `DJANGO_SECRET_KEY_FALLBACKS` | rotation | Comma-separated previous signing keys used only during a controlled rotation window |
| `DATABASE_URL` | yes | PostgreSQL URL; SQLite is intentionally unsupported |
| `DATABASE_CONN_MAX_AGE` | no | Persistent database connection lifetime; defaults to `0` in debug and `60` seconds otherwise |
| `DJANGO_DEBUG` | no | `True`, `1`, `yes`, or `on` enables development mode |
| `APP_RELEASE` | production | Commit SHA or immutable image version included in health responses |
| `ALLOWED_HOSTS` | no | Comma-separated host names |
| `CSRF_TRUSTED_ORIGINS` | no | Comma-separated trusted origins |
| `WAGTAILADMIN_BASE_URL` | CMS | Public origin used for absolute Wagtail admin links; omit `/cms/` and a trailing slash |
| `DEFAULT_FROM_EMAIL` | no | Sender for authentication emails |
| `EMAIL_BACKEND` | production | Delivery backend; deploy checks reject console, dummy, and in-memory backends |
| `EMAIL_HOST`, `EMAIL_PORT` | SMTP | SMTP server and port |
| `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` | SMTP | SMTP credentials; password remains server-side |
| `EMAIL_USE_TLS`, `EMAIL_USE_SSL` | SMTP | Mutually exclusive SMTP transport modes |
| `EMAIL_TIMEOUT` | no | SMTP timeout in seconds; defaults to `10`, maximum `60` |
| `SERVER_EMAIL` | no | Sender for framework-generated error email |
| `PAYMENT_GATEWAY` | contributions | `mock` in debug or `razorpay` for test-mode checkout |
| `RAZORPAY_KEY_ID` | Razorpay | Test key ID beginning with `rzp_test_`; live keys are rejected |
| `RAZORPAY_KEY_SECRET` | Razorpay | Test key secret; server-side only and never committed |
| `RAZORPAY_WEBHOOK_SECRET` | Razorpay | Secret configured separately for webhook signing |
| `RAZORPAY_TIMEOUT_SECONDS` | no | Razorpay API timeout; defaults to `10`, maximum `30` |
| `SECURE_SSL_REDIRECT` | no | Defaults on outside debug; set for the deployment's TLS topology |
| `SECURE_HSTS_SECONDS` | no | Defaults to 3600 outside debug |
| `SECURE_HSTS_INCLUDE_SUBDOMAINS` | no | Explicit opt-in after every affected subdomain is HTTPS-capable |
| `SECURE_HSTS_PRELOAD` | no | Explicit opt-in after confirming the domain is preload-ready |
| `TRUST_PROXY_SSL_HEADER` | no | Trust an overwriting proxy's `X-Forwarded-Proto`; enable only for a verified proxy topology |
| `LOG_LEVEL` | no | Standard server log level; defaults to `INFO` |

## Mock payment mode

Set both of these values:

```dotenv
DJANGO_DEBUG=True
PAYMENT_GATEWAY=mock
```

The payment screen is unavailable unless a payment adapter is configured. Before a gold or silver payment can start, an owner must publish the corresponding Scheme Rate from **Owner → Scheme rates**. Mock payments record no real transfer; the current database-backed Scheme Rate is locked to the contribution before payment and INR is converted to six-decimal grams for local testing. `seed_demo` remains deferred.

The owner dashboard derives outstanding cash principal, earned cash bonus, and gold/silver gram obligations from successful financial records. Projected cash bonus is shown separately and is not an actual liability. Current published Scheme Rates provide separate indicative INR exposure for each metal; these display values never alter historical allocations and are never combined with cash into one liability total.

## Cash bonus

Scheme plans may define a cash bonus percentage and minimum qualifying duration; 0% disables bonus. Enrolment snapshots those terms and policy version, so later plan changes do not rewrite an agreement. Before eligibility, the customer sees a projected estimate based on principal paid so far. On eligibility, earned bonus is calculated from successful cash contributions paid by the eligibility-date cutoff and becomes redeemable. Later contributions remain principal without changing the matured bonus. Cash redemptions allocate principal first and then earned bonus while preserving both components in the immutable record.

## Redemption

Once a scheme reaches its India-local eligibility date, an owner can record a partial or full redemption. Cash accounts support cash or jewellery-purchase settlement and may include earned bonus; gold and silver accounts support matching metal or jewellery-purchase settlement. Jewellery purchase requires an invoice or sales reference. Outstanding balances and owner liabilities subtract completed, unreversed redemptions while retaining all historical contributions and allocations. A full redemption closes the account; partial redemption leaves it eligible. If an owner records a settlement in error, an immutable reversal restores the entitlement and reopens a fully redeemed account without editing or deleting the original redemption. Both events retain actor, timestamp, and reason in the owner audit log.

The MVP records settlement facts only. It does not execute payouts, convert metal to cash, manage inventory/invoices, or edit a historical redemption.

## Public business and policy pages

The public site provides About, Contact, Terms, Privacy, Cancellation and Refund,
Shipping and Delivery, and Plans and Pricing pages. Pricing is sourced from
`SchemePlan`; a plan is public only when both `active` and `publicly_listed` are
selected. New and migrated plans default to private. Review every customer-facing
field before publishing a plan, and use the owner plan list to confirm its public
status. Existing enrolments retain their snapshotted terms when a public plan changes.

Public self-registration remains closed. Prospective customers contact the showroom
for enrolment, while enrolled customers sign in to access the contribution checkout.
The policy pages describe showroom pickup only and a manual payment-error refund
process; the application does not yet initiate Razorpay refunds automatically.

## Audit and exceptions

Owner enrolment, plan changes, Scheme Rate publications, redemptions, redemption reversals, and manual allocation retries require or retain an actor, timestamp, and reason in immutable audit records. Plan and rate changes apply only to future enrolments or contributions as appropriate; existing agreement snapshots and locked contributions remain unchanged. The exception queue derives unresolved `PAID_UNALLOCATED` contributions and failed Razorpay webhook reconciliation records from their source records, so successful allocation recovery removes the live allocation exception without deleting its audit history.

Manual payment correction remains unavailable until its accounting, approval, and customer-disclosure rules are defined. Refunds, disputes, automated retries/alerts, dual approval, and quote expiry also remain future operational work.

## Receipts, statements, and exports

Each verified contribution has a printable HTML acknowledgement with a stable `JSK-RCT-<year>-<contribution id>` reference, customer and scheme details, INR amount, payment reference, and—when allocated—the locked Scheme Rate, metal, and quantity. Paid-unallocated metal receipts explicitly show allocation pending and never invent missing values. Pending and failed payment attempts have no receipt.

Customers can print a lifetime statement for each of their own schemes. It lists verified payments, immutable allocation rates/quantities, redemptions, and reversals, followed by the current denomination-specific entitlement. Owners can view the same documents and download separate contribution and redemption CSV exports; INR, gold grams, and silver grams remain separate columns. Spreadsheet formula-like text is neutralized in CSV output.

Documents are generated on demand from source records and are acknowledgements, not tax invoices. The MVP does not generate PDFs, email documents, archive rendered copies, add signatures, or include statutory business/tax fields.

## Manual Scheme Rates

Only an active owner may publish gold or silver Scheme Rates. Each publication creates a new immutable timestamped record with the established fineness; it never edits an earlier publication. The owner screen shows current rates, recent history, and the difference from the previous rate. Changes greater than 5% require an additional confirmation.

For a metal contribution, the current applicable Scheme Rate is locked to the pending contribution before mock payment initiation or Razorpay order creation. Payment confirmation and webhook processing calculate the allocation only from that lock, so a later publication cannot change an in-progress checkout or historical grams. If no applicable rate exists, no payment or Razorpay order is created. A verified metal payment is durably `PAID_UNALLOCATED` until its allocation is stored, then becomes `PAID`; this makes exceptions and process interruption recoverable without using the state for rate retrieval.

## Razorpay test mode

Generate test-mode API keys in the Razorpay Dashboard and configure a separate webhook secret in the ignored `.env`:

```dotenv
PAYMENT_GATEWAY=razorpay
RAZORPAY_KEY_ID=rzp_test_replace_me
RAZORPAY_KEY_SECRET=replace-me
RAZORPAY_WEBHOOK_SECRET=replace-me-with-a-separate-secret
RAZORPAY_TIMEOUT_SECONDS=10
```

Configure the test-mode webhook URL as `https://your-host.example/scheme/payments/razorpay/webhook/` and subscribe to `payment.captured`. The browser callback is verified with HMAC using the order ID stored locally, then the server fetches the payment and requires the same order, amount, INR currency, and captured status. Webhooks are verified against the untouched request body; duplicate `X-Razorpay-Event-Id` values are idempotent.

Only test keys are accepted in this milestone. Razorpay test mode simulates transactions and does not move real money. See the official [server integration](https://razorpay.com/docs/payments/server-integration/python/integration-steps/), [webhook validation](https://razorpay.com/docs/webhooks/validate-test/), and [test/live mode](https://razorpay.com/docs/payments/dashboard/test-live-modes/) guides.

## Verification

```powershell
uv run --env-file .env python manage.py check
uv run --env-file .env python manage.py makemigrations --check --dry-run
uv run --env-file .env python manage.py test
```

For a release candidate, run `python manage.py check --deploy --fail-level ERROR`
with the actual production environment. The application exposes `/health/live/` for
process liveness and `/health/ready/` for PostgreSQL readiness; neither response is
cached and both include `APP_RELEASE`. The container image runs as an unprivileged
`app` user, contains collected static assets, and emits Gunicorn/Django logs to
standard output. The detailed environment, rollout, smoke-test, backup/restore,
rollback, monitoring, incident, and secret-rotation procedure is in the
[Production and deployment guide](docs/PRODUCTION_DEPLOYMENT.md).

The selected deployment target is a Linode Compute Instance behind Caddy at
`jaishrikrishnajewellery.com`, connected to Linode Managed PostgreSQL with
CA-verified TLS. Start from [.env.production.example](.env.production.example) and
[compose.production.yml](compose.production.yml); the checked-in `docker-compose.yml`
remains development-only.

## Project guides

- [Agent contract](AGENTS.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Domain rules](docs/DOMAIN_RULES.md)
- [MVP plan](docs/MVP_PLAN.md)
- [Future work](docs/FUTURE_WORK.md)
- [Current status](docs/STATUS.md)
- [Development conventions](docs/DEVELOPMENT.md)
- [Production and deployment](docs/PRODUCTION_DEPLOYMENT.md)
- [Testing](docs/TESTING.md)
