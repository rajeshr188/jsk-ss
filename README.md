# Jai Shri Krishna Jewellery Savings Scheme

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
| `METAL_RATE_PROVIDER` | metal schemes | `mock` in debug or `goldapi` for live XAU/XAG-to-INR rates |
| `GOLDAPI_API_KEY` | live rates | Required when `METAL_RATE_PROVIDER=goldapi`; never commit it |
| `GOLDAPI_TIMEOUT_SECONDS` | no | GoldAPI HTTPS timeout; defaults to `10`, maximum `30` |
| `GOLDAPI_CACHE_SECONDS` | no | Per-metal live quote cache; defaults to `60`, maximum `3600` |
| `MOCK_GOLD_RATE` | no | Development 24K gold rate per gram; defaults to `12500.0000` |
| `MOCK_SILVER_RATE` | no | Development silver rate per gram; defaults to `150.0000` |
| `MOCK_GOLD_PURITY` | no | Development gold fineness metadata; defaults to `0.9999` |
| `MOCK_SILVER_PURITY` | no | Development silver fineness metadata; defaults to `0.9990` |
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
METAL_RATE_PROVIDER=mock
MOCK_GOLD_RATE=12500.0000
MOCK_SILVER_RATE=150.0000
```

The payment screen is unavailable unless a payment adapter is configured. Gold and silver payments additionally require a configured metal-rate provider. Mock payments record no real transfer; rates are snapshotted and INR is converted to six-decimal grams for local testing. `seed_demo` remains deferred.

The owner dashboard derives outstanding cash principal, earned cash bonus, and gold/silver gram obligations from successful financial records. Projected cash bonus is shown separately and is not an actual liability. Current mock rates provide separate indicative INR exposure for each metal; these display values never alter historical allocations and are never combined with cash into one liability total.

## Cash bonus

Scheme plans may define a cash bonus percentage and minimum qualifying duration; 0% disables bonus. Enrolment snapshots those terms and policy version, so later plan changes do not rewrite an agreement. Before eligibility, the customer sees a projected estimate based on principal paid so far. On eligibility, earned bonus is calculated from successful cash contributions paid by the eligibility-date cutoff and becomes redeemable. Later contributions remain principal without changing the matured bonus. Cash redemptions allocate principal first and then earned bonus while preserving both components in the immutable record.

## Redemption

Once a scheme reaches its India-local eligibility date, an owner can record a partial or full redemption. Cash accounts support cash or jewellery-purchase settlement and may include earned bonus; gold and silver accounts support matching metal or jewellery-purchase settlement. Jewellery purchase requires an invoice or sales reference. Outstanding balances and owner liabilities subtract completed, unreversed redemptions while retaining all historical contributions and allocations. A full redemption closes the account; partial redemption leaves it eligible. If an owner records a settlement in error, an immutable reversal restores the entitlement and reopens a fully redeemed account without editing or deleting the original redemption. Both events retain actor, timestamp, and reason in the owner audit log.

The MVP records settlement facts only. It does not execute payouts, convert metal to cash, manage inventory/invoices, or edit a historical redemption.

## Audit and exceptions

Owner enrolment, plan changes, redemptions, redemption reversals, and manual allocation retries require or retain an actor, timestamp, and reason in immutable audit records. Plan changes apply only to future enrolments; existing agreement snapshots remain unchanged. The exception queue derives unresolved `PAID_UNALLOCATED` contributions and failed Razorpay webhook reconciliation records from their source records, so successful allocation recovery removes the live allocation exception without deleting its audit history.

Manual payment correction and manual rate override actions are deliberately unavailable until their accounting, pricing, approval, and customer-disclosure rules are defined. Refunds, disputes, automated retries/alerts, and dual approval also remain future operational work.

## Receipts, statements, and exports

Each verified contribution has a printable HTML acknowledgement with a stable `JSK-RCT-<year>-<contribution id>` reference, customer and scheme details, INR amount, payment reference, and—when allocated—the captured metal, applied rate, and quantity. Paid-unallocated metal receipts explicitly show allocation pending and never invent missing values. Pending and failed payment attempts have no receipt.

Customers can print a lifetime statement for each of their own schemes. It lists verified payments, immutable allocation rates/quantities, redemptions, and reversals, followed by the current denomination-specific entitlement. Owners can view the same documents and download separate contribution and redemption CSV exports; INR, gold grams, and silver grams remain separate columns. Spreadsheet formula-like text is neutralized in CSV output.

Documents are generated on demand from source records and are acknowledgements, not tax invoices. The MVP does not generate PDFs, email documents, archive rendered copies, add signatures, or include statutory business/tax fields.

## Live metal rates

Create a GoldAPI.io account and keep its token only in your ignored `.env` or deployment secret manager. The official endpoint supports gold (`XAU`) and silver (`XAG`) in INR and supplies per-gram prices.

```dotenv
METAL_RATE_PROVIDER=goldapi
GOLDAPI_API_KEY=replace-with-your-real-token
GOLDAPI_TIMEOUT_SECONDS=10
GOLDAPI_CACHE_SECONDS=60
```

The adapter calls `https://www.goldapi.io/api/XAU/INR` or `XAG/INR` over HTTPS and sends the key in the `x-access-token` header, never in the URL. It validates metal, currency, timestamp, and the per-gram rate before creating a snapshot. Quotes are cached briefly to protect provider quota. See the [official GoldAPI documentation](https://www.goldapi.io/api-documentation) and [official integration examples](https://github.com/goldapi-io).

If payment verification succeeds but a rate cannot be obtained, the contribution becomes **Paid — allocation pending**. No rate or grams are invented. The owner dashboard warns about the exception, and the owner can retry safely from the contributions page after restoring provider access.

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
standard output. The detailed rollout, backup/restore, rollback, monitoring, and
secret-rotation procedure is in [Development conventions](docs/DEVELOPMENT.md).

## Project guides

- [Agent contract](AGENTS.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Domain rules](docs/DOMAIN_RULES.md)
- [MVP plan](docs/MVP_PLAN.md)
- [Future work](docs/FUTURE_WORK.md)
- [Current status](docs/STATUS.md)
- [Development conventions](docs/DEVELOPMENT.md)
- [Testing](docs/TESTING.md)
