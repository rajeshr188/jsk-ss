# Jai Shri Krishna Jewellery Savings Scheme

A single-business Django application for managing customer cash, 24K gold, and silver savings schemes. It reuses the [Lithium](https://github.com/wsvincent/lithium) Django foundation and currently supports customer records and scheme enrolment.

## Technology

- Python 3.12+, Django 6, PostgreSQL
- Lithium's `accounts.CustomUser`, django-allauth, Bootstrap 5, crispy forms
- WhiteNoise, Gunicorn, psycopg, and `uv`

## Quick start

1. Install PostgreSQL and create an application database/user.
2. Copy `.env.example` to `.env` for reference, then export those values in your shell or IDE. Django intentionally does not read `.env` files itself.
3. Install dependencies: `uv sync --frozen`.
4. Apply migrations: `uv run python manage.py migrate`.
5. Create the owner: `uv run python manage.py createsuperuser`. A superuser is always authorized as an owner; its application role can also be set to `OWNER` in admin.
6. Start the server: `uv run python manage.py runserver`.

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
| `SECURE_SSL_REDIRECT` | no | Defaults on outside debug; set for the deployment's TLS topology |
| `SECURE_HSTS_SECONDS` | no | Defaults to 3600 outside debug |
| `SECURE_HSTS_INCLUDE_SUBDOMAINS` | no | Defaults on outside debug |
| `SECURE_HSTS_PRELOAD` | no | Explicit opt-in after confirming the domain is preload-ready |

Mock payments, Razorpay, live metal rates, and `seed_demo` are planned but are not part of the current Milestone 1 implementation. Their configuration will be documented when implemented.

## Verification

```powershell
uv run python manage.py check
uv run python manage.py makemigrations --check --dry-run
uv run python manage.py test
```

## Project guides

- [Agent contract](AGENTS.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Domain rules](docs/DOMAIN_RULES.md)
- [MVP plan](docs/MVP_PLAN.md)
- [Current status](docs/STATUS.md)
- [Development conventions](docs/DEVELOPMENT.md)
- [Testing](docs/TESTING.md)
