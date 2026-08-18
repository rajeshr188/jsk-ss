# Production and Deployment Guide

This is the canonical production runbook for the Jai Shri Krishna Jewellery
Savings Scheme. It covers the current Django 6, PostgreSQL, Gunicorn, WhiteNoise,
Razorpay Test Mode, and GoldAPI build. Development setup remains in the
[README](../README.md); business invariants remain in [Domain rules](DOMAIN_RULES.md).

## Production-readiness boundary

The repository is ready to be deployed to production-grade infrastructure, but it
is **not yet approved to handle real customer funds**:

- The deploy check accepts Razorpay Test Mode keys beginning with `rzp_test_` and
  deliberately rejects live keys.
- Live-mode payment reconciliation, refunds, disputes, incident handling, and
  credential rotation must be approved and tested before the code is changed to
  accept live keys.
- GoldAPI has boundary tests but still needs a private authenticated XAU/INR and
  XAG/INR smoke test in the target environment.
- `FW-PROD-001` through `FW-PROD-003` in [Future work](FUTURE_WORK.md) require an
  evidenced restore drill, stable HTTPS and alerting, real email delivery, and
  secret-rotation rehearsal.

Until those gates are closed, a deployment is a production-infrastructure or
staging deployment using Razorpay Test Mode, not a financial go-live.

## Recommended topology

Use a managed container runtime and managed PostgreSQL unless the operator already
has the staff and procedures to run those components safely.

```text
Internet
   |
owned DNS name + TLS edge / load balancer
   |  (overwrites Host and X-Forwarded-Proto)
   v
Django container(s): Gunicorn -> WSGI application
   |        |                 |
   |        |                 +-> stdout logs -> retained log/alert service
   |        +-> WhiteNoise serves versioned static assets from the image
   v
managed PostgreSQL with TLS, snapshots, PITR, and restricted network access

External services: SMTP provider, Razorpay Test Mode webhook/API, GoldAPI
```

The application is stateless between requests except for PostgreSQL. Do not place
the database in the web container. The current application has no user-uploaded
media dependency; if uploads are added later, use durable object storage rather
than a container filesystem.

The checked-in `docker-compose.yml` runs Django's development server and a local
database with development credentials. It is **not** a production deployment file.

## Selected Linode deployment profile

The selected target for this business is:

| Layer | Selected implementation |
| --- | --- |
| Public host | `https://jaishrikrishnajewellery.com` |
| Redirect host | `https://www.jaishrikrishnajewellery.com` redirects to the apex host |
| Compute | One Ubuntu 24.04 LTS Linode Compute Instance running Docker Compose |
| TLS edge | Caddy 2.11.4 with automatic certificate issuance and renewal |
| Application | The approved `jsk-savings` image, private to the Compose network |
| Database | Linode Managed PostgreSQL 16 in the same core region |
| Database transport | CA-verified TLS using `sslmode=verify-full` |

The checked-in [production Compose file](../compose.production.yml),
[environment template](../.env.production.example), and
[Caddyfile](../deploy/Caddyfile) implement this topology. The application container
publishes no host port; only Caddy exposes TCP ports 80 and 443. Caddy ignores
client-supplied `X-Forwarded-*` values and sets `X-Forwarded-Proto`, which is the
required condition for this deployment to enable `TRUST_PROXY_SSL_HEADER=True`.

This single Compute Instance is appropriate for staging and an initial controlled
MVP deployment, but it is not compute-high-availability. A host outage requires
instance recovery. Before availability requirements increase, add a second instance
and a Linode NodeBalancer rather than placing a second proxy on the same host.

### Provision Linode resources

1. Create the Compute Instance and Managed PostgreSQL cluster in the same core
   region. Select PostgreSQL 16, the tested baseline. A single database node costs
   less and is acceptable for staging, but has maintenance/failure downtime. For
   real customer funds, use the available three-node highly available plan unless
   the business explicitly accepts the single-node outage risk.
2. In the database Networking settings, allow only the Compute Instance's exact
   outbound IPv4 and, when used, IPv6 addresses. Do not allow `0.0.0.0/0` or `::/0`.
   Linode clients can prefer IPv6, so the allow-list and chosen connection hostname
   must agree on the protocol being used.
3. Copy the exact host and port and download the database CA certificate from
   Connection Details. Linode Managed
   PostgreSQL requires encrypted connections; this deployment additionally verifies
   the server hostname against that CA.
4. Use the administrative `akmadmin` identity only to create a dedicated application
   role and database. In an interactive `psql` session, use `\password` so the new
   password does not enter shell history:

   ```sql
   CREATE ROLE jsk_app LOGIN;
   \password jsk_app
   CREATE DATABASE jsk_savings OWNER jsk_app;
   ```

5. Configure a Linode Cloud Firewall. Allow TCP 80 and 443 from the internet, allow
   TCP 22 only from the administrator's trusted IP range, and deny other inbound
   traffic. Do not expose ports 8000 or 5432 on the Compute Instance.
6. Point an `A` record for `@` at the Compute Instance IPv4 address and a `CNAME`
   record for `www` at `jaishrikrishnajewellery.com`. Add an `AAAA` record only when
   IPv6 and its firewall rules are ready. Start with a 300-second TTL. DNS may remain
   with the current registrar; moving authoritative DNS to Linode is optional.

As checked on 2026-08-18, the apex currently resolves to `3.33.130.190` and
`15.197.148.33`, returns a small HTTP `/lander` redirect, and does not provide a
usable HTTPS response. This appears to be parking rather than the Django application,
but the domain owner must confirm that replacing those `A` records will not displace
an intended site. Change only the web `A`/`AAAA`/`www` records; preserve existing MX,
TXT, CAA, and other email/domain-verification records unless their owners approve a
separate change.

### Prepare the Compute Instance

Install the supported Docker Engine and Compose plugin from Docker's official Ubuntu
repository. Then place the checkout and environment under `/opt/jsk`:

```bash
sudo mkdir -p /opt/jsk/app /opt/jsk/secrets
sudo chown -R "$USER":"$USER" /opt/jsk/app
sudo chmod 700 /opt/jsk/secrets
git clone https://github.com/rajeshr188/jsk-ss.git /opt/jsk/app
cd /opt/jsk/app
git checkout <approved-commit>
cp .env.production.example .env.production
chmod 600 .env.production
sudo install -m 600 <downloaded-ca-file> /opt/jsk/secrets/linode-db-ca.pem
```

Fill `.env.production` locally on the server without printing it into logs. Generate
a new Django signing key, percent-encode reserved database-password characters, and
use fresh Razorpay Test Mode credentials. Credentials previously pasted into chat or
shared in screenshots must be rotated rather than reused.

A mode-`600` environment file is a practical single-host staging baseline, not an
audited secret manager. Before financial go-live, select the controlled secret store,
access policy, backup, and rotation process that will be authoritative for these
values; root access to the Compute Instance can read container environment variables.

`APP_IMAGE` must name the approved image. Prefer a private registry digest. Until the
GitHub billing lock is resolved and registry publishing exists, a staging-only image
can be built from the checked-out approved commit and tagged locally:

```bash
docker build --pull --tag jsk-savings:<approved-commit> .
```

Set `APP_IMAGE=jsk-savings:<approved-commit>` and set `APP_RELEASE` to the same commit.
Record `docker image inspect` output. Do not call a locally rebuilt image the promoted
production artifact; real go-live still requires green CI and an approved immutable
registry digest.

### Validate and start the Linode deployment

Always pass the production environment explicitly. `config --quiet` validates the
Compose model without printing expanded credentials:

```bash
docker compose --env-file .env.production -f compose.production.yml config --quiet
docker compose --env-file .env.production -f compose.production.yml \
  run --rm --no-deps web python manage.py check --deploy --fail-level ERROR
docker compose --env-file .env.production -f compose.production.yml \
  run --rm --no-deps web python manage.py migrate --plan
docker compose --env-file .env.production -f compose.production.yml \
  run --rm --no-deps web python manage.py migrate --noinput
docker compose --env-file .env.production -f compose.production.yml up -d
```

Caddy starts only after Django's PostgreSQL readiness check succeeds. Once DNS has
propagated and ports 80/443 are reachable, Caddy obtains certificates and redirects
HTTP to HTTPS automatically. Verify:

```bash
curl --fail-with-body https://jaishrikrishnajewellery.com/health/live/
curl --fail-with-body https://jaishrikrishnajewellery.com/health/ready/
curl -I http://jaishrikrishnajewellery.com/
curl -I https://www.jaishrikrishnajewellery.com/
```

The first two responses must contain the expected `APP_RELEASE`; HTTP and `www` must
redirect once to the canonical HTTPS origin. Configure Razorpay Test Mode to deliver
`payment.captured` to:

```text
https://jaishrikrishnajewellery.com/scheme/payments/razorpay/webhook/
```

### Linode backup and restore evidence

Linode Managed Databases currently include daily backups retained for 14 days and
support restoration to a forked cluster. Run the first drill before real funds:

1. Select a specific recovery time in the database Backups tab and restore it as a
   new cluster. This temporarily incurs charges for both clusters.
2. Add only the isolated verification host to the restored cluster's access list and
   download its CA/connection details.
3. Point a temporary application container at the fork with payment, rate, and email
   providers disabled. Never point public DNS or Razorpay at the restored cluster.
4. Complete the record-count and denomination-specific liability reconciliation in
   this guide, recording achieved RPO and RTO.
5. Preserve the evidence, confirm the original cluster was never modified, and then
   delete the restored fork to stop the additional charge.

Linode's database backup does not replace portable encrypted `pg_dump` exports.
Maintain both controls and test them independently.

### Linode monitoring boundary

Use Akamai Cloud Pulse for available database/platform metrics and an external HTTPS
monitor for `/health/ready/`. The Compose profile bounds local Docker logs, but local
rotation is not durable centralized retention. Before go-live, select and configure
a log/error service and alert destination for the signals in this guide. Likewise,
select an SMTP provider and prove password-reset delivery. These choices cannot be
completed merely by provisioning the Linode instance.

## Deployment responsibilities

Assign named owners before deployment. One person may hold multiple roles, but no
responsibility should be implicit.

| Responsibility | Required outcome |
| --- | --- |
| Release owner | Approves the commit, image digest, migration plan, and rollout |
| Database owner | Confirms backup/PITR status and can perform a restore |
| Domain/TLS owner | Controls DNS, certificates, proxy rules, and HSTS changes |
| Provider owner | Controls SMTP, Razorpay, and GoldAPI configuration |
| Incident owner | Receives alerts and can disable contributions or roll back |
| Business reconciler | Verifies INR principal/bonus, gold grams, and silver grams separately |

## Platform contract

Any target platform must provide all of the following:

- Linux/amd64 or Linux/arm64 container execution with secrets injected at runtime.
- An immutable image reference, preferably a registry digest as well as a commit tag.
- A stable owned HTTPS hostname and automatic certificate renewal.
- A proxy that rejects unknown hosts and overwrites, rather than merely appends,
  `X-Forwarded-Proto`.
- A one-off release job using the same image and environment as the web service.
- HTTP liveness and readiness probes.
- Graceful process termination with at least 30 seconds for Gunicorn shutdown.
- Retained stdout/stderr logs with searchable release identifiers and external alerts.
- Managed PostgreSQL with encrypted transport, tightly restricted network access
  (private where the provider supports it), automated snapshots, point-in-time
  recovery, and an isolated restore facility.
- A secret manager with access control and audit history.

The container listens on port `8000`, runs as the unprivileged `app` user, and starts:

```text
gunicorn --bind :8000 --workers 2 --timeout 30 --graceful-timeout 30 \
  --max-requests 1000 --max-requests-jitter 100 \
  --access-logfile - --error-logfile - django_project.wsgi
```

Configure probes as follows:

| Probe | Path | Meaning | Platform behavior |
| --- | --- | --- | --- |
| Liveness | `/health/live/` | Django process can answer | Restart after a sustained failure, not one transient error |
| Readiness | `/health/ready/` | Django can execute `SELECT 1` on PostgreSQL | Remove instance from traffic while status is not `200` |

Both responses set `Cache-Control: no-store` and include the configured
`APP_RELEASE`. Do not expose a database error or secret in either response.

## Provisioning checklist

Provision these resources before the first build is promoted:

1. A private image repository.
2. A managed PostgreSQL database on a supported major version. PostgreSQL 16 is the
   tested baseline. Create a dedicated application database and least-privileged
   application identity; keep administrative credentials out of the web service.
3. Automated database snapshots and point-in-time recovery with documented
   retention. Define and approve the required recovery point objective (RPO) and
   recovery time objective (RTO); do not let a platform default make that decision.
4. Separate staging and production databases, secrets, hostnames, provider keys,
   webhook endpoints, and log destinations. Never clone production customer data
   into staging without an approved sanitization process.
5. An owned DNS name and TLS endpoint.
6. An SMTP or transactional email account with an authorized sender domain.
7. Razorpay Test Mode keys and a separate webhook signing secret.
8. A GoldAPI key with enough quota for expected XAU and XAG quote traffic.
9. Uptime, error, database, backup, and financial-exception alert destinations.

## Production environment

Store values in the platform secret/configuration manager. Django does not load a
`.env` file by itself, and no production `.env` file should be copied into the image.
Generate the Django key locally with a cryptographically secure generator, for example:

```powershell
uv run python -c "import secrets; print(secrets.token_urlsafe(64))"
```

Use a profile equivalent to the following. Values in angle brackets are placeholders,
not literals:

```dotenv
DJANGO_DEBUG=False
DJANGO_SECRET_KEY=<long-random-production-only-value>
DJANGO_SECRET_KEY_FALLBACKS=
APP_RELEASE=<immutable-commit-or-image-id>

ALLOWED_HOSTS=savings.example.com
CSRF_TRUSTED_ORIGINS=https://savings.example.com

DATABASE_URL=postgresql://<app-user>:<url-encoded-password>@<private-host>:5432/<database>?sslmode=require
DATABASE_CONN_MAX_AGE=60

EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=<smtp-host>
EMAIL_PORT=587
EMAIL_HOST_USER=<smtp-user>
EMAIL_HOST_PASSWORD=<smtp-password>
EMAIL_USE_TLS=True
EMAIL_USE_SSL=False
EMAIL_TIMEOUT=10
DEFAULT_FROM_EMAIL=Jai Shri Krishna Jewellery <noreply@example.com>
SERVER_EMAIL=errors@example.com

PAYMENT_GATEWAY=razorpay
RAZORPAY_KEY_ID=<rzp_test_key-id>
RAZORPAY_KEY_SECRET=<test-key-secret>
RAZORPAY_WEBHOOK_SECRET=<separate-webhook-secret>
RAZORPAY_TIMEOUT_SECONDS=10

METAL_RATE_PROVIDER=goldapi
GOLDAPI_API_KEY=<provider-key>
GOLDAPI_TIMEOUT_SECONDS=10
GOLDAPI_CACHE_SECONDS=60

SECURE_SSL_REDIRECT=True
TRUST_PROXY_SSL_HEADER=True
SECURE_HSTS_SECONDS=3600
SECURE_HSTS_INCLUDE_SUBDOMAINS=False
SECURE_HSTS_PRELOAD=False

LOG_LEVEL=INFO
```

Configuration rules:

- `DJANGO_DEBUG` must be exactly a supported false value such as `False`; never set
  generic `DEBUG`, because this project intentionally ignores it.
- `ALLOWED_HOSTS` contains bare hostnames, not schemes or paths. Do not use `*`.
- `CSRF_TRUSTED_ORIGINS` contains complete HTTPS origins and includes a port only if
  the public origin uses a non-default port.
- Percent-encode reserved characters in database usernames/passwords. Require
  `sslmode=require` or the stronger certificate-validation mode supported by the
  provider. Prefer a private network in addition to TLS where available; the selected
  Linode service instead uses its public database hostname plus exact-IP access controls.
- Set `TRUST_PROXY_SSL_HEADER=True` only after verifying that all requests traverse
  a trusted proxy which overwrites `X-Forwarded-Proto`. Otherwise a client may spoof
  the header. Keep `SECURE_SSL_REDIRECT=True` when Django is expected to enforce HTTPS.
- Start HSTS at `3600`. Increase it only after observing correct HTTPS behavior.
  Enable subdomains and preload only after every affected hostname is permanently
  HTTPS-capable and the domain owner accepts the long-lived consequences.
- `EMAIL_USE_TLS` and `EMAIL_USE_SSL` are mutually exclusive.
- Leave `PAYMENT_GATEWAY` empty to disable new contribution checkout. Leave
  `METAL_RATE_PROVIDER` empty to disable live metal quotes. Never use either mock
  adapter outside debug mode.
- Keep each Razorpay API secret distinct from the webhook secret. Do not log request
  signatures, secret values, full provider payloads, or database URLs.
- `APP_RELEASE` must identify exactly one source/image build and must be identical in
  the migration job and web service.

The complete variable reference is maintained in the [README](../README.md#environment-variables).

## Edge, DNS, and TLS configuration

1. Configure the service on a temporary platform hostname and validate both health
   endpoints before changing public DNS.
2. Add the owned hostname to the edge, issue its certificate, and point DNS to the
   edge using a low TTL during the first rollout.
3. Configure an explicit allow-list for the public host. The edge should reject an
   unknown `Host` instead of forwarding it to Django.
4. Redirect port 80 to HTTPS at the edge. Forward the original client address using
   the platform's standard trusted mechanism and overwrite `X-Forwarded-Proto=https`.
5. Verify an HTTP request redirects once to HTTPS and an HTTPS request does not loop.
6. Verify secure session and CSRF cookies, login, logout, and a CSRF-protected form.
7. Begin with one-hour HSTS. Observe at least one normal release cycle before raising
   it. Treat `includeSubDomains` and preload as separate, reviewed changes.

Razorpay's webhook must use the stable URL:

```text
https://savings.example.com/scheme/payments/razorpay/webhook/
```

Subscribe only to the events currently handled by the application, which is
`payment.captured`. Keep the platform endpoint public, but do not add an authentication
layer that prevents Razorpay delivery; the application authenticates the untouched
request body with the webhook signature.

## Build and release artifacts

CI is the release gate. It currently uses PostgreSQL 16 to apply migrations, checks
migration drift, runs Django checks and the full regression suite, runs deploy checks,
collects static files, and independently builds the image.

For a release candidate:

```powershell
git status --short
uv sync --frozen
uv run --env-file .env python manage.py makemigrations --check --dry-run
uv run --env-file .env python manage.py check
uv run --env-file .env python manage.py test
docker build --pull --tag <registry>/jsk-savings:<commit-sha> .
```

Run tests only against a disposable CI/test database. Never let Django create or
destroy a test database beside production data.

After the build:

1. Record the source commit, CI run, image tag, and immutable image digest.
2. Scan the final image and its locked Python dependencies using the organization's
   approved scanners; triage findings before promotion.
3. Push the image once. Do not rebuild separately for staging and production.
4. Set `APP_RELEASE` to the recorded commit or digest-derived identifier.
5. Promote the exact same image digest through staging and production.

Static files are collected in the builder stage and served by WhiteNoise from the
image. A runtime `collectstatic` job is neither required nor desired.

## Pre-deployment gate

Run this check using the target environment's real non-secret configuration and
secret injection:

```powershell
python manage.py check --deploy --fail-level ERROR
```

The command must have no errors. Review every warning explicitly; a warning is not
automatically safe. The project's custom checks reject mock or unsupported providers,
missing selected-provider credentials, non-delivering email backends, wildcard hosts,
and non-HTTPS CSRF origins. They also warn if `APP_RELEASE` is unknown or database TLS
is not required.

Then inspect the schema operation without mutating the database:

```powershell
python manage.py showmigrations --plan
python manage.py migrate --plan
```

Review migrations for locks, table rewrites, long data transformations, and backward
compatibility with the currently running image. For a large table or a non-backward-
compatible change, stop and create a migration-specific rollout and recovery plan.

The final gate requires:

- Green CI for the exact commit.
- Approved image digest and deploy-check output.
- A healthy staging rollout of that same image.
- A current restorable backup or confirmed PITR recovery point.
- A reviewed migration plan.
- An on-call operator and business reconciler for the deployment window.
- A defined rollback image.

## Staging rollout

Staging should exercise production topology while using its own data and credentials.

1. Inject staging configuration with `DJANGO_DEBUG=False`.
2. Deploy the release image by digest.
3. Run exactly one release job:

   ```powershell
   python manage.py migrate --noinput
   ```

4. Start or update the web service. Do not run migrations in the container start
   command and do not let every replica race to apply them.
5. Wait for `/health/live/` and `/health/ready/` to return `200` with the expected
   release.
6. Execute the smoke test below.
7. Observe logs, database connections, latency, provider calls, and exceptions for a
   representative period before approving production.

## Production rollout

Use a rolling or blue/green deployment only when the migration is compatible with
both old and new application versions. Otherwise schedule a maintenance window and
use a reviewed migration-specific procedure.

1. Announce the change window and name the release, database, and incident owners.
2. Confirm the previous image digest remains available.
3. Record a pre-release database snapshot or confirm a current PITR recovery point.
4. Record baseline customer/account counts and the owner dashboard's separate cash
   principal, earned cash bonus, gold grams, silver grams, and exception counts.
5. Re-run the deploy check in the production environment.
6. Run `python manage.py migrate --plan` and compare it with the approved plan.
7. Run `python manage.py migrate --noinput` once as the release job.
8. Deploy the approved image digest. Keep old instances until new readiness probes pass.
9. Confirm the live and ready responses show the new `APP_RELEASE`.
10. Execute the production-safe smoke test. Use Razorpay Test Mode only; do not create
    or edit financial records merely to test an infrastructure release unless the
    records are explicitly tagged, reconciled, and removed through an approved method.
11. Compare post-release counts, liabilities, and exceptions to the recorded baseline,
    accounting for any legitimate concurrent activity.
12. Observe the release through the agreed stabilization window, then close the change
    record with evidence.

## Smoke test

Start with unauthenticated checks:

```powershell
curl.exe --fail-with-body https://savings.example.com/health/live/
curl.exe --fail-with-body https://savings.example.com/health/ready/
curl.exe --fail-with-body https://savings.example.com/static/css/base.css
```

Confirm the health JSON contains the expected release. Then test in a browser:

1. Open the home page over HTTPS and confirm there is no redirect loop or mixed content.
2. Sign in as a designated owner and as a staging/test customer; verify role isolation.
3. Submit a CSRF-protected, non-financial form and sign out.
4. Request a password reset for a controlled address and verify sender, link hostname,
   delivery time, and successful reset. Do not inspect message bodies in shared logs.
5. Verify the owner dashboard loads and its INR, gold, and silver liabilities remain
   separate and match the pre-release baseline.
6. Verify the exception queue and audit log load without exposing provider secrets.
7. In staging, complete one Razorpay Test Mode contribution and confirm both browser
   callback verification and a signed `payment.captured` webhook are idempotent.
8. For a controlled staging metal account, verify a GoldAPI-backed allocation captures
   a rate and six-decimal grams. Confirm a provider failure leaves a recoverable
   `PAID_UNALLOCATED` record rather than inventing a rate.
9. Verify a contribution acknowledgement, customer statement, and owner CSV export.

Record time, operator, release, URLs, test identities, provider event identifiers,
and results. Never paste secrets or full webhook bodies into the record.

## Initial application bootstrap

After the first successful migration, create the initial owner through a one-off
platform job attached to the production database:

```powershell
python manage.py createsuperuser
```

Use a controlled mailbox, a unique password, and the organization's credential
handling policy. A Django superuser is authorized as an application owner. Do not
create shared customer/owner accounts. Confirm the deployed domain and display name
for Django's Sites entry in `/admin/`, because authentication emails may use site
context.

## Monitoring and alerting

Django and Gunicorn emit timestamped logs to stdout/stderr. The platform must attach
request metadata and retain logs according to the approved privacy and financial
record policy. Logs must be searchable by `APP_RELEASE`; never log secrets, cookies,
passwords, payment signatures, full webhook bodies, or database URLs.

Create actionable alerts for:

| Signal | Initial response |
| --- | --- |
| Liveness failure | Replace the unhealthy instance; inspect startup and worker logs |
| Readiness failure | Remove from traffic; inspect PostgreSQL health and connection capacity |
| Sustained 5xx or latency increase | Correlate by release and endpoint; consider image rollback |
| Failed/mismatched Razorpay webhook | Preserve ledger evidence; compare provider and local IDs |
| Any new `PAID_UNALLOCATED` record | Restore rate-provider access and use the owner retry workflow |
| Database storage/CPU/connections near limit | Stop scaling web replicas blindly; restore capacity margin |
| Backup/PITR failure or missed snapshot | Treat production recovery as degraded and repair immediately |
| SMTP delivery/authentication failure | Verify provider status and credentials; test password reset |
| GoldAPI quota, timeout, or validation failure | Protect quota, inspect provider status, and monitor allocations |
| Certificate expiry or TLS failure | Renew/replace at the edge before customer access is affected |

Choose thresholds from measured staging/production baselines. Every page-level alert
must name its responder, escalation path, and runbook. Exercise each route before
customer access is enabled; an untested alert is not a control.

Capacity planning must include database connections. Each container currently runs
two Gunicorn workers and may hold persistent connections for 60 seconds. Ensure the
database connection limit covers all workers across the maximum replica count plus
release jobs, administrative work, health traffic, and a safety margin. Do not solve
connection exhaustion by increasing one limit without checking database memory.

Run `python manage.py clearsessions` periodically as a platform-scheduled one-off job
to remove expired database-backed sessions. This job is maintenance, not a financial
workflow, and must use the deployed image and environment.

## Backup and restore

Managed snapshots and point-in-time recovery are the primary controls. PostgreSQL
custom-format exports are an additional portability control, not a substitute for
tested managed recovery. Use a restricted service definition or password file so a
password never appears in shell history:

```powershell
pg_dump --format=custom --no-owner --no-acl --file=<restricted-backup-path> <production-service-name>
```

Encrypt exports, restrict access, keep them outside the application container, and
verify retention and deletion policy. Monitor command exit status and warnings.

At least quarterly, and before relying on a new backup mechanism, restore into a
new isolated database that cannot receive production traffic:

```powershell
createdb <isolated-restore-database>
pg_restore --exit-on-error --no-owner --no-acl --dbname=<isolated-restore-service> <backup-file>
```

Never use the production database as the restore target. Treat a dump as trusted
code only when its source is trusted; PostgreSQL restores execute statements stored
in the archive.

After restoration:

1. Point a temporary application instance at the isolated database.
2. Run `python manage.py showmigrations --plan` and `python manage.py check`.
3. Record source backup time, restore start/end time, errors, and achieved RPO/RTO.
4. Compare customer, account, contribution, allocation, redemption, reversal,
   webhook-ledger, and audit-event counts with the source evidence.
5. Reconcile outstanding cash principal and earned bonus, gold grams, and silver grams
   separately against the restored owner dashboard. Do not use indicative current
   metal INR exposure as a booked balance.
6. Test controlled owner/customer reads without contacting live providers or sending
   real email.
7. Preserve the drill record, then destroy the isolated environment according to the
   platform's approved data-handling procedure.

## Rollback

### Application rollback

If probes, errors, or smoke tests fail and the schema remains compatible:

1. Stop further promotion and record the failure time and release IDs.
2. Route traffic to the previous image digest.
3. Confirm both health endpoints and repeat the safe smoke checks.
4. Verify liabilities and exception counts; reconcile activity during the rollback.
5. Preserve new logs, provider events, and database records for investigation.

### Migration failure

Do not improvise a reverse migration on production. Stop the rollout, retain the
current database, and execute the migration-specific recovery plan reviewed before
release. If old code is incompatible with the migrated schema, keep traffic stopped
or use the explicitly prepared compatible image.

### Database recovery warning

Do **not** restore an older database after newer payments, webhooks, allocations,
redemptions, reversals, or audit events have been recorded merely to roll back code.
That would discard the append-oriented financial source of truth. A database
point-in-time recovery is an incident operation requiring identification and
reconciliation of every event after the chosen recovery point.

## Provider incidents

### Payment or webhook incident

1. Prevent new checkout order creation by deploying configuration with
   `PAYMENT_GATEWAY` empty if necessary; do not use a hidden bypass.
2. Keep the webhook endpoint and provider retry evidence available when safe.
3. Preserve all local contributions and `PaymentWebhookEvent` records. Do not edit or
   delete them to force a match.
4. Reconcile Razorpay order, payment, amount, currency, captured status, event ID,
   and local contribution using authorized provider access.
5. Escalate refunds, disputes, unmatched payments, or manual corrections: the current
   application does not implement those operations.
6. Re-enable checkout only after reconciliation and a signed Test Mode webhook test.

### Metal-rate or allocation incident

1. Leave verified but unallocated payments in `PAID_UNALLOCATED`.
2. Restore GoldAPI credentials, quota, network access, or valid response handling.
3. Use the owner-controlled allocation retry action, which is idempotent and audited.
4. Confirm exactly one immutable rate snapshot and allocation exist and that gold and
   silver remain separate.
5. Never invent, manually overwrite, or backdate a rate.

### Database incident

1. Remove unready instances from traffic and prevent new financial actions.
2. Identify whether the failure is connectivity, capacity, credentials, corruption,
   or a provider outage.
3. Preserve the primary and its logs; use managed failover/PITR procedures.
4. If recovery changes the database timeline, reconcile all post-recovery provider
   activity before reopening contributions.

## Secret rotation

Rotate one credential class at a time and keep a tested rollback path.

### Django signing key

1. Generate a new key and keep the current key securely.
2. Deploy the new key as `DJANGO_SECRET_KEY` and the old key as the sole temporary
   value in `DJANGO_SECRET_KEY_FALLBACKS`.
3. Verify login, logout, password reset, and signed application flows.
4. After the approved session/token overlap window, deploy with an empty fallback.
5. Revoke the old secret and record completion. A fallback is still an active secret.

If a key is known to be exposed, do not preserve it merely for session continuity;
rotate immediately and accept the required session/token invalidation.

### Database, SMTP, and GoldAPI credentials

Create or activate the replacement credential, update the secret manager, roll the
web service, verify the relevant readiness/email/quote path, then revoke the old
credential. Check that release jobs and administrative identities do not share the
web application's secret unnecessarily.

### Razorpay API keys

Use the provider's supported overlap/activation process, update both key ID and
secret atomically, roll the application, and exercise a Test Mode order before
revoking the old key. The current release does not authorize live-key rotation.

### Razorpay webhook secret

Webhook rotation must be coordinated because the provider and application must agree
on one signing secret. Use a controlled change window: pause financial testing,
update the endpoint and application secret in the provider-supported order, deploy,
send and verify a signed Test Mode event, check idempotency, then resume. Preserve
failed deliveries for reconciliation; never accept unsigned events during the gap.

## Routine operations

| Frequency | Action |
| --- | --- |
| Every release | Green CI, image scan, deploy check, migration review, backup/PITR confirmation, smoke test, reconciliation |
| Daily | Review alerts, failed webhooks, allocation exceptions, backup success, database capacity |
| Weekly | Review error trends, certificate status, provider quota, email delivery, and run expired-session cleanup |
| Monthly | Patch/rebuild base images and locked dependencies through a tested release; review access and secret age |
| Quarterly | Perform and evidence an isolated restore/reconciliation drill and an incident/alert exercise |
| After any incident | Preserve timeline/evidence, reconcile financial state, document cause/actions, and test prevention |

Dependency updates must change and review `uv.lock`; do not run an unlocked upgrade
inside a production build. Rebuild regularly with current trusted base-image patches,
then promote the resulting immutable digest through the normal release process.

## Go-live sign-off

Real customer use remains blocked until every applicable item is evidenced:

- [ ] The exact image passed CI, scanning, staging, and production deploy checks.
- [ ] Production uses `DJANGO_DEBUG=False`, explicit hosts/origins, HTTPS, secure
      cookies, staged HSTS, and verified proxy-header behavior.
- [ ] Database TLS/private access, backups, PITR, RPO/RTO, and an isolated restore
      plus denomination-specific reconciliation are proven.
- [ ] Real password-reset email delivery and sender-domain authentication are proven.
- [ ] Logs are retained and tested alerts reach named responders.
- [ ] GoldAPI XAU/INR and XAG/INR requests are privately verified.
- [ ] Razorpay uses a stable HTTPS webhook with signed, idempotent delivery testing.
- [ ] Separate Django, database, SMTP, GoldAPI, Razorpay API, and webhook rotations
      have been rehearsed.
- [ ] Owner/customer access, documents, exports, audit, exceptions, and rollback have
      been smoke-tested.
- [ ] `FW-PROD-001` through `FW-PROD-003` are marked complete with evidence.
- [ ] Before real funds, `FW-PAY-001` and `FW-PAY-003` are complete and the code,
      tests, operations, refund/dispute process, and reconciliation controls have been
      explicitly changed and approved for Razorpay Live Mode.

Record sign-off date, approvers, source commit, image digest, database recovery point,
test evidence, exceptions, and next review date. A checked box without evidence is
not a completed control.

## Primary references

- [Akamai/Linode Managed PostgreSQL](https://techdocs.akamai.com/cloud-computing/docs/aiven-postgresql)
- [Akamai/Linode managed database clusters](https://techdocs.akamai.com/cloud-computing/docs/aiven-database-clusters)
- [Akamai/Linode database backup management](https://techdocs.akamai.com/cloud-computing/docs/aiven-manage-database)
- [Akamai/Linode DNS A and AAAA records](https://techdocs.akamai.com/cloud-computing/docs/a-and-aaaa-records)
- [Caddy automatic HTTPS](https://caddyserver.com/docs/automatic-https)
- [Caddy reverse proxy headers](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy)
- [Django 6 deployment checklist](https://docs.djangoproject.com/en/6.0/howto/deployment/checklist/)
- [Django 6 with Gunicorn](https://docs.djangoproject.com/en/6.0/howto/deployment/wsgi/gunicorn/)
- [Docker build best practices](https://docs.docker.com/build/building/best-practices/)
- [PostgreSQL backup and restore](https://www.postgresql.org/docs/current/backup.html)
- [PostgreSQL `pg_dump`](https://www.postgresql.org/docs/current/app-pgdump.html)
- [PostgreSQL `pg_restore`](https://www.postgresql.org/docs/current/app-pgrestore.html)
- [Razorpay webhook best practices](https://razorpay.com/docs/webhooks/best-practices/)
- [Razorpay webhook validation and testing](https://razorpay.com/docs/webhooks/validate-test/)
