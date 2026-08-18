# Jai Shri Krishna Jewellery Savings Scheme

A single-business Django application for managing customer cash, 24K gold, and silver savings schemes. It reuses the [Lithium](https://github.com/wsvincent/lithium) Django foundation and has reached MVP Alpha with owner-managed enrolment, mock contributions, immutable metal allocations, customer balances, and an owner liability dashboard.

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
$env:DEBUG = "True"
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
| `DATABASE_URL` | yes | PostgreSQL URL; SQLite is intentionally unsupported |
| `DEBUG` | no | `True`, `1`, `yes`, or `on` enables development mode |
| `ALLOWED_HOSTS` | no | Comma-separated host names |
| `CSRF_TRUSTED_ORIGINS` | no | Comma-separated trusted origins |
| `DEFAULT_FROM_EMAIL` | no | Sender for authentication emails |
| `PAYMENT_GATEWAY` | Milestone 2 | Must be `mock` for the development payment flow |
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
| `SECURE_HSTS_INCLUDE_SUBDOMAINS` | no | Defaults on outside debug |
| `SECURE_HSTS_PRELOAD` | no | Explicit opt-in after confirming the domain is preload-ready |

## Mock payment mode

Set both of these values:

```dotenv
DEBUG=True
PAYMENT_GATEWAY=mock
METAL_RATE_PROVIDER=mock
MOCK_GOLD_RATE=12500.0000
MOCK_SILVER_RATE=150.0000
```

The payment screen is unavailable unless mock payment mode is enabled. Gold and silver payments additionally require a configured metal-rate provider. Mock payments record no real transfer; rates are snapshotted and INR is converted to six-decimal grams for local testing. Razorpay and `seed_demo` remain deferred.

The owner dashboard derives outstanding cash principal and gold/silver gram obligations from successful financial records. Current mock rates provide separate indicative INR exposure for each metal; these display values never alter historical allocations and are never combined with cash into one liability total.

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

## Verification

```powershell
uv run --env-file .env python manage.py check
uv run --env-file .env python manage.py makemigrations --check --dry-run
uv run --env-file .env python manage.py test
```

## Project guides

- [Agent contract](AGENTS.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Domain rules](docs/DOMAIN_RULES.md)
- [MVP plan](docs/MVP_PLAN.md)
- [Current status](docs/STATUS.md)
- [Development conventions](docs/DEVELOPMENT.md)
- [Testing](docs/TESTING.md)
