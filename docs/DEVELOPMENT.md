# Development

## Structure and conventions

- Keep authentication concerns in `accounts`, public content in `pages`, and current scheme domain work in `schemes`.
- Name mutation functions as commands (`create_customer`, `enroll_customer`) in `services.py`.
- Put reusable/non-trivial ORM reads in `selectors.py`.
- Keep views thin: authorize → validate → call a service/selector → render or redirect.
- Views must not contain substantial financial domain logic; signals must not orchestrate money workflows.
- Use class-based or function-based views according to clarity, server-rendered Bootstrap templates, named URLs, and crispy Django forms.
- Keep migrations committed and run `makemigrations --check --dry-run` before handoff.
- Keep payment and metal-rate providers behind their explicit boundaries; provider-specific fields must not leak through views or scheme models.
- Razorpay secrets remain server-side. Verify browser callbacks against the locally stored order, verify captured payment details through the server API, and validate webhooks against the unmodified request body before parsing.
- Webhook handlers must use the provider event ID for idempotency and route entitlement changes through the same contribution services as browser callbacks.
- Live rate adapters must use bounded network timeouts, validate provider identity/currency/timestamps/rates, avoid credentials in URLs or errors, and raise provider-neutral failures. Tests mock the HTTP boundary and never consume live quota.
- Once payment is verified, allocation failure must preserve the payment as `PAID_UNALLOCATED`; owner retry must call the idempotent allocation service rather than editing records directly.
- Redemption writes must go through `complete_redemption`, lock the scheme account, carry an idempotency key, and append an immutable record. Never edit historical contributions or allocations to represent settlement.
- Redemption corrections must go through `reverse_redemption`; append one immutable compensating record and exclude it through selectors rather than changing the original redemption.
- Sensitive owner workflows must append an `AuditEvent` in the same transaction as the supported mutation. Retain a stable actor label, timestamp, reason, target, and compact before/after or outcome details; do not store secrets or full provider payloads.
- The exception queue is derived from authoritative contribution/webhook state. Do not copy monetary balances into an exception table or treat acknowledging an exception as a financial correction.
- Receipts, statements, and exports are read models over source records. Never persist a second balance, use current metal rates in historical documents, combine denomination columns, or issue receipts for pending/failed payments.
- Escape HTML through Django templates and neutralize CSV text beginning with spreadsheet formula operators. Document access must be scoped to the owning customer or an owner.
- Cash bonus formulas belong in the versioned policy service and reads belong in selectors. Changing a formula requires a new supported policy version; never reinterpret an existing account's snapshotted version or add projected bonus to actual liability.

## Environment

Configuration comes from process environment variables. `.env.example` is documentation; use shell/IDE variables, Replit Secrets, or a deployment secret manager for real values.

## Adding a domain feature

Read the agent contract and domain rules, implement one milestone slice, add constraints and focused tests, apply migrations against PostgreSQL, run the regression suite and checks, manually exercise the flow, then update status/architecture only where reality changed.

## Production deployment and operations

The canonical, step-by-step procedure is the
[Production and deployment guide](PRODUCTION_DEPLOYMENT.md). The notes below are a
compact engineering summary; keep operational changes synchronized with that runbook.

Production configuration must set `DJANGO_DEBUG=False`, a long random
`DJANGO_SECRET_KEY`, explicit `ALLOWED_HOSTS` and HTTPS-only
`CSRF_TRUSTED_ORIGINS`, an immutable `APP_RELEASE`, a PostgreSQL `DATABASE_URL`,
and a real email backend. Use `DJANGO_DEBUG`; the generic `DEBUG` variable is not
read because hosting environments may define it for unrelated purposes. Keep all
credentials in the deployment secret manager, never in an image or repository.

Before every release:

1. Require a green CI run. It applies migrations to PostgreSQL 16, checks migration
   drift, runs Django checks and the full suite, executes production deployment
   checks, collects production static files, and builds the container.
2. Run `python manage.py check --deploy --fail-level ERROR` with the intended
   production environment. Warnings require an explicit operator review even when
   they do not fail the command.
3. Record a restorable managed-database snapshot or confirm point-in-time recovery,
   its retention, and the person responsible for restoration. Review
   `python manage.py migrate --plan` before changing the schema.
4. Build one immutable image, set `APP_RELEASE` to its commit/image identifier, and
   promote that same image through environments. Run `python manage.py migrate
   --noinput` once as a release job, not concurrently in every web worker.
5. Roll out the web image, then require `/health/live/` and `/health/ready/` to pass.
   The readiness probe checks PostgreSQL. Configure the TLS proxy to overwrite
   `X-Forwarded-Proto` before enabling `TRUST_PROXY_SSL_HEADER=True`.
6. Smoke-test owner/customer login, password-reset email, static assets, and a
   Razorpay Test Mode payment plus signed webhook. Do not substitute mock adapters
   in a deployed environment.

Terminate TLS at an owned, stable endpoint. Start HSTS with a short value, observe
the deployment, then increase it; enable subdomains and preload only after every
affected hostname is permanently HTTPS-capable. A remote production database should
use `sslmode=require` or stronger in `DATABASE_URL`. Restrict database and provider
credentials to the application and release jobs that need them.

### Backup and restore drill

Use managed snapshots and point-in-time recovery as the primary controls. Also take
periodic PostgreSQL custom-format exports using a restricted service identity and
encrypted storage, for example `pg_dump --format=custom --no-owner --no-acl
--file=<restricted-path> <service-name>`. Use a PostgreSQL service definition or
password file so credentials do not appear in shell history.

At least quarterly, restore the selected backup into a newly created isolated
database with `pg_restore --exit-on-error --no-owner --dbname=<isolated-service>
<backup-file>`. Never point a drill at the production database. Record recovery time,
backup timestamp, and errors; run `showmigrations --plan`, inspect owner/customer
counts, and reconcile cash principal/bonus, gold grams, and silver grams against the
restored owner dashboard before destroying the isolated drill environment.

### Rollback and incident handling

Prefer rolling back to the previous immutable application image when its code is
compatible with the current schema. Database migrations should therefore be
backward-compatible across one release whenever practical. If not, stop the rollout
and use a reviewed migration-specific recovery plan.

Do not restore an older production database after newer payments, webhooks, or
redemptions have been recorded unless the incident plan explicitly reconciles every
post-backup financial event. During a payment incident, prevent new checkout order
creation, retain webhook evidence/provider retries, preserve append-only records,
and reconcile Razorpay before reopening payments. Record the incident, release IDs,
timeline, and reconciliation result.

### Secrets, logs, and monitoring

Rotate database, email, GoldAPI, Razorpay API, and Razorpay webhook credentials
independently. Coordinate webhook-secret changes with the Razorpay endpoint and
verify a signed Test Mode delivery. To rotate Django signing material without an
immediate session cutover, deploy a new `DJANGO_SECRET_KEY` with the previous value
temporarily in `DJANGO_SECRET_KEY_FALLBACKS`, then remove the fallback after the
agreed expiry window. Never log either value.

Django and Gunicorn write timestamped logs to standard output. The hosting platform
must retain them and alert on sustained 5xx responses, readiness failures, failed or
mismatched webhooks, `PAID_UNALLOCATED` records, database capacity/connection limits,
and backup failures. Include `APP_RELEASE` in incident searches. External error
aggregation and alert routing are deployment integrations and must be exercised
before real customer funds are enabled.

Production operations may run `python manage.py check_financial_exceptions`. It
prints only the release and aggregate unresolved `PAID_UNALLOCATED`/failed-webhook
counts, returns success when all counts are zero, and exits non-zero when owner action
is required. The Linode systemd timer reports that result to an external heartbeat;
do not expand the command to emit customer details, exception text, or provider IDs.
