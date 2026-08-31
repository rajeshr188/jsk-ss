# Production and Deployment Guide

This is the canonical production runbook for the Jai Sri Krishna Jewellery
Savings Scheme. It covers the current Django 6, PostgreSQL, Gunicorn, WhiteNoise,
explicit Razorpay Test/Live modes, and manually published Scheme Rate build. Development setup remains in the
[README](../README.md); business invariants remain in [Domain rules](DOMAIN_RULES.md).

## Production-readiness boundary

Production release `c3e8c46` runs the Live Razorpay path accepted on `5fa726b` and the
deployed FW-PAY-002 abandoned-order lifecycle. This proves the Live payment path and
its conservative stale-order boundary, but the deployment is **not fully
production-gate complete**:

- The deploy check accepts `test` and `live` only when `RAZORPAY_MODE` agrees with
  the `rzp_test_` or `rzp_live_` key prefix. Missing, unknown, and mixed-mode
  configuration fails closed.
- `FW-PAY-001` Live payment, capture, signed-webhook, allocation, and reconciliation
  acceptance is complete. Refund, dispute, incident, alert, webhook-recovery, and
  credential-rotation controls remain governed by the open items below.
- An owner must publish reviewed gold and silver Scheme Rates before metal
  contributions are enabled in an environment.
- `FW-PROD-001` is complete with the evidenced Linode restore drill recorded below.
  `FW-PROD-002` and `FW-PROD-003` in [Future work](FUTURE_WORK.md) retain the stable
  HTTPS/alerting activation and secret-rotation rehearsal requirements.

The owner deferred paid external monitoring under `FW-PROD-002` on 2026-08-27 to
preserve the operating budget. Existing bounded local logs, health endpoints,
financial-exception checks, and provider consoles remain useful manual controls, but
the deferral does not close the external alerting, retained-log, or escalation gate.

The owner explicitly accepted the remaining operational risk when enabling Live
checkout. Do not interpret that decision as closure of `FW-PROD-002`, `FW-PROD-003`,
or `FW-PAY-003`; use the manual controls in this guide and suspend checkout on any
unreconciled provider/local mismatch.

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

External services: SMTP provider, mode-isolated Razorpay webhook/API
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

Use a named, non-root, sudo-capable deployment account. Keep the existing SSH session
open while testing a new account or firewall rule in a second session. On Ubuntu
24.04, install operating-system updates and the required host tools:

```bash
sudo apt update
sudo apt full-upgrade
sudo apt install -y git curl ca-certificates openssl postgresql-client unattended-upgrades
sudo timedatectl set-timezone UTC
sudo systemctl enable --now unattended-upgrades
```

Install Docker Engine, Buildx, and the Compose plugin from Docker's official Ubuntu
repository rather than the convenience script:

```bash
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
sudo tee /etc/apt/sources.list.d/docker.sources >/dev/null <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker containerd
sudo docker run --rm hello-world
sudo docker compose version
```

Add only the deployment operator to the `docker` group, then log out and back in:

```bash
sudo usermod -aG docker "$USER"
```

Membership in this group is effectively root-level host access. Do not add application
users or general staff. Keep the Linode Cloud Firewall as the public perimeter;
Docker-published ports can bypass uncomplicated host-firewall expectations.

After the approved commit exists on the remote, place an exact detached checkout under
`/opt/jsk`. Replace the example value with the full 40-character approved commit SHA:

```bash
sudo mkdir -p /opt/jsk/app /opt/jsk/secrets
sudo chown -R "$USER":"$USER" /opt/jsk/app
sudo chmod 700 /opt/jsk/secrets
git clone https://github.com/rajeshr188/jsk-ss.git /opt/jsk/app
cd /opt/jsk/app
git fetch --prune origin
export JSK_RELEASE_SHA=FULL_40_CHARACTER_APPROVED_COMMIT_SHA
git checkout --detach "$JSK_RELEASE_SHA"
test "$(git rev-parse HEAD)" = "$JSK_RELEASE_SHA"
cp .env.production.example .env.production
chmod 600 .env.production
```

Transfer the downloaded Linode CA from the administrator workstation to a temporary
host path using `scp`, then install and validate it on the Compute Instance:

```text
scp "C:\path\to\database-ca-certificate.crt" deploy@COMPUTE_IPV4:/tmp/linode-db-ca.crt
```

```bash
sudo install -o root -g root -m 0644 /tmp/linode-db-ca.crt \
  /opt/jsk/secrets/linode-db-ca.crt
sudo openssl x509 -in /opt/jsk/secrets/linode-db-ca.crt \
  -noout -subject -issuer -dates
sudo grep -q "PRIVATE KEY" /opt/jsk/secrets/linode-db-ca.crt \
  && echo "ERROR: private key found" || echo "CA certificate only"
rm /tmp/linode-db-ca.crt
```

The CA is public trust material, not a database credential. It must be readable by
the image's non-root `app` user because Compose implements a file-backed secret as a
bind mount and cannot remap its permissions. Keep `/opt/jsk/secrets` mode `0700`, keep
the database password only in the protected environment/secret store, and set:

```dotenv
LINODE_DB_CA_FILE=/opt/jsk/secrets/linode-db-ca.crt
DATABASE_URL=postgresql://jsk_app:<url-encoded-password>@<managed-host>:<port>/jsk_savings?sslmode=verify-full&sslrootcert=/run/secrets/linode_db_ca.pem
```

The `.crt` host filename and `.pem` container target deliberately differ; both are
PEM-encoded certificate files. Do not replace the managed hostname with its current
IP address because `verify-full` verifies the hostname and failover may change IPs.

Fill `.env.production` locally on the server without printing it into logs. Generate
a new Django signing key, percent-encode reserved database-password characters, and
use fresh Razorpay Test Mode credentials. Credentials previously pasted into chat or
shared in screenshots must be rotated rather than reused. `ACME_EMAIL` must be a real,
syntactically valid, monitored address; a placeholder prevents Caddy from registering
with its certificate authority. Before starting, check for template placeholders
without printing the environment:

```bash
if grep -qE 'replace-with|replace_me' .env.production; then
  echo "ERROR: production placeholders remain"
else
  echo "No template placeholders found"
fi
```

A mode-`600` environment file is a practical single-host staging baseline, not an
audited secret manager. Before financial go-live, select the controlled secret store,
access policy, backup, and rotation process that will be authoritative for these
values; root access to the Compute Instance can read container environment variables.

`APP_IMAGE` must name the approved image. Prefer a private registry digest. Until the
GitHub billing lock is resolved and registry publishing exists, a staging-only image
can be built from the checked-out approved commit and tagged locally:

```bash
docker build --pull --tag "jsk-savings:${JSK_RELEASE_SHA}" .
```

Set `APP_IMAGE` to `jsk-savings:` followed by the approved commit and set
`APP_RELEASE` to that same full commit.
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

Also inspect bounded startup logs. The image disables Gunicorn's unused control
socket because Gunicorn 25.1 and newer otherwise tries to create `$HOME/.gunicorn`
on the deliberately read-only application filesystem:

```bash
docker compose --env-file .env.production -f compose.production.yml logs --tail=100 web
docker compose --env-file .env.production -f compose.production.yml logs --tail=100 caddy
```

If `ACME_EMAIL`, application environment, or another Compose-injected value changes,
`docker compose restart` is insufficient because it retains the old container
environment. Re-run `config --quiet` and use `up -d --force-recreate` for the affected
service.

The first two responses must contain the expected `APP_RELEASE`; HTTP and `www` must
redirect once to the canonical HTTPS origin. Configure Razorpay Test Mode to deliver
`payment.captured` to:

```text
https://jaishrikrishnajewellery.com/scheme/payments/razorpay/webhook/
```

### Linode backup and restore evidence

Linode Managed Databases currently include daily backups retained for 14 days and
support restoration to a forked cluster. Run the first drill before real funds:

1. Select either the newest full backup plus incremental changes or a specific
   recovery time in the database Backups tab and restore it as a new cluster. Record
   which option was exercised. This temporarily incurs charges for both clusters.
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

#### Completed restore evidence — 2026-08-27

- Restore option: newest full backup plus incremental changes.
- Restore initiated from the newest available state at 13:57 IST; the isolated fork
  finished provisioning at 14:12 IST, for an observed 15-minute RTO.
- The temporary application used the production image/release
  `5fa726b2d76666abe7063f8b48125d6869566ecc`, a fork-specific endpoint and CA, and
  disabled payment and email providers. No public service or migration was started.
- The restored schema contained every migration through
  `schemes.0011_razorpay_gateway_mode`.
- Reconciliation exactly matched the recorded source baseline: five customers, six
  scheme accounts, no pending Razorpay contribution, INR `0.00` cash principal, INR
  `0.00` earned cash bonus, `0.299097` gold grams, and `0.000000` silver grams.
- `check_auth_email_integrity` reported no duplicate groups or blank-email users;
  `check_financial_exceptions` reported zero paid-unallocated contributions and zero
  failed or mismatched webhooks.
- The original production live/readiness endpoints continued returning `ok` with the
  expected release. After evidence capture, the restored fork and its temporary
  environment and CA certificate were removed; the production CA was retained.

### Linode monitoring boundary

The selected baseline is Better Stack for independent HTTPS monitoring, Docker log
retention, incident routing, and the financial-exception heartbeat. Akamai Cloud
Pulse and Cloud Manager remain authoritative for Managed PostgreSQL and Compute
metrics and provider backup events. This split avoids making an application outage
invisible to the system that is supposed to detect it. An equivalent external
service may replace Better Stack only if it supports the same checks, retained logs,
explicit failure heartbeats, escalation, and exercised evidence.

The Compose profile still bounds local Docker logs so a collector outage cannot fill
the host disk. Local rotation is not durable retention. Before sending logs off-host,
approve the data region and retention period. A 30-day searchable baseline is
recommended for incident investigation; this is operational evidence, not a
substitute for immutable financial records or the separately approved legal record
retention policy. Caddy access logs mask IPv4 addresses to `/24`, IPv6 addresses to
`/48`, remove user-agent headers, retain the release label, and rely on Caddy's
default credential-header redaction. Request/response bodies, cookies, payment
signatures, and database URLs must never be added.

### Configure Better Stack monitoring and retained logs

1. Create a Better Stack team protected by multi-factor authentication. Name a
   primary incident responder and a backup responder using private operational
   contact details. Do not assume that the public shop support number is an on-call
   number.
2. In **Telemetry -> Sources**, connect a Docker source named `jsk-production`.
   Choose the approved region and retention period, then copy its source token. On
   the Compute Instance, keep the token out of shell history while using Better
   Stack's generated Vector installer:

   ```bash
   read -rsp "Better Stack source token: " JSK_BS_SOURCE_TOKEN
   echo
   curl -fsS \
     "https://telemetry.betterstack.com/setup-vector/docker/${JSK_BS_SOURCE_TOKEN}" \
     -o /tmp/jsk-vector-install.sh
   unset JSK_BS_SOURCE_TOKEN
   less /tmp/jsk-vector-install.sh
   sudo bash /tmp/jsk-vector-install.sh
   rm /tmp/jsk-vector-install.sh
   sudo usermod -aG docker vector
   sudo systemctl restart vector
   sudo systemctl --no-pager --full status vector
   ```

   The generated `/etc/vector` configuration contains ingestion credentials; keep it
   root-controlled and never commit it. In Live tail, confirm both `web` and `edge`
   container logs arrive and that `com.jsk.release`/the Caddy `release` field matches
   the deployed `APP_RELEASE`. Search for a known health request, then verify no
   cookie, authorization header, signature, full webhook body, or unmasked client IP
   is present.
3. Create two HTTP monitors using the production hostname:

   | Monitor | URL | Expected result | Initial timing |
   | --- | --- | --- | --- |
   | `JSK production liveness` | `https://jaishrikrishnajewellery.com/health/live/` | HTTP 200 and body contains `"status": "ok"` | 60-second checks; alert after 2 minutes; recover after 2 minutes |
   | `JSK production readiness` | `https://jaishrikrishnajewellery.com/health/ready/` | HTTP 200 and body contains `"status": "ok"` | 60-second checks; alert after 2 minutes; recover after 2 minutes |

   Do not match a fixed release value because a valid deployment changes it. Enable
   TLS certificate-expiry notification at 14 days and domain-expiry notification at
   30 days on the liveness monitor. Assign the production escalation policy to both.
4. Create a log alert named `JSK sustained edge 5xx`. Use the Caddy access-log schema
   shown in Live tail (parse the JSON `message` first if the collector has not done
   so) and select production `edge` events whose HTTP status is 500 through 599.
   Start with 5 events in 5 minutes and tune only from measured traffic. Include the
   release, status, method, and path in the incident; do not include headers or bodies.
5. Create a heartbeat named `JSK financial exceptions`, expected every 5 minutes
   with a 2-minute grace period, and assign the production escalation policy. Store
   its secret URL separately from the application environment:

   ```bash
   sudo install -o root -g root -m 0600 /dev/null \
     /opt/jsk/secrets/observability.env
   sudoedit /opt/jsk/secrets/observability.env
   ```

   The file contains one line and must never be committed or printed:

   ```dotenv
   FINANCIAL_EXCEPTIONS_HEARTBEAT_URL=https://uptime.betterstack.com/api/v1/heartbeat/REPLACE_WITH_SECRET_TOKEN
   ```

   Install the versioned service and timer after each relevant deployment:

   ```bash
   cd /opt/jsk/app
   docker compose --env-file .env.production -f compose.production.yml \
     exec -T web python manage.py check_financial_exceptions
   sudo install -o root -g root -m 0644 \
     deploy/systemd/jsk-financial-exceptions.service \
     /etc/systemd/system/jsk-financial-exceptions.service
   sudo install -o root -g root -m 0644 \
     deploy/systemd/jsk-financial-exceptions.timer \
     /etc/systemd/system/jsk-financial-exceptions.timer
   sudo systemctl daemon-reload
   sudo systemctl enable --now jsk-financial-exceptions.timer
   sudo systemctl start jsk-financial-exceptions.service
   sudo systemctl --no-pager --full status jsk-financial-exceptions.timer
   sudo journalctl -u jsk-financial-exceptions.service -n 30 --no-pager
   ```

   The check reads authoritative database state, emits aggregate counts only, and
   exits non-zero for any unresolved failed webhook or `PAID_UNALLOCATED` payment.
   The wrapper reports `/fail` to the heartbeat and never transmits exception text,
   customer data, or provider IDs. A database, Docker, or app failure also prevents a
   healthy heartbeat.

6. Exercise the heartbeat route without creating or changing a financial record:

   ```bash
   sudo bash -c 'set -a; source /opt/jsk/secrets/observability.env; set +a; \
     /usr/bin/bash /opt/jsk/app/deploy/check-financial-exceptions.sh --test-alert'
   ```

   Confirm the named responder receives and acknowledges the test incident, then
   resolve it in Better Stack. Confirm the next normal timer run returns the
   heartbeat to healthy. This tests delivery, not the owner resolution workflow;
   separately retain the existing paid-unallocated recovery smoke evidence.

### Configure Linode capacity and backup alerts

In Cloud Manager, confirm the account's Read-Write notification recipients include
the named incident responder and subscribe to relevant Akamai status notifications.
Enable Compute Instance CPU, disk-I/O, traffic, and transfer-quota email alerts. Use
measured baselines; an initial CPU threshold is 80% of total core capacity sustained
for 15 minutes.

Managed Database metrics and custom alerts may require Akamai Cloud Pulse access. If
the database Metrics/Alerts pages are unavailable, open a support ticket requesting
access rather than pretending the control exists. Once available, route alerts to
the incident responder and start with warning/critical database disk usage at 75% and
85%, CPU at 80% for 15 minutes, and memory at 85% for 15 minutes. Review the plan's
PostgreSQL connection limit and the application's worker/connection budget alongside
readiness failures; do not infer connection capacity from CPU alone.

Managed PostgreSQL creates daily restore points, but the application cannot verify
provider-owned backup execution. Confirm a fresh restore point in the Backups tab
each day during initial go-live and at least weekly after stability, and ensure any
provider backup/system alert or support ticket reaches the incident responder. A
missed restore point or backup alert immediately marks recovery as degraded. This
notification control complements, but does not complete, the isolated restore drill
in `FW-PROD-001`.

Record screenshots or exported incident timestamps for each test below without
capturing secrets or customer data:

| Evidence | Pass condition |
| --- | --- |
| Liveness and readiness monitor test | Named responder receives, acknowledges, and resolves the test |
| Financial heartbeat `/fail` test | Incident arrives; next clean check recovers |
| Caddy 5xx log alert test | A controlled test event reaches the same escalation route |
| TLS/domain warning test | Monitor shows both checks enabled with the intended lead times |
| Compute/database capacity test | Notification channel and threshold test reaches the responder |
| Backup notification test | A provider test/system notification or documented support confirmation reaches the responder |
| Log retention test | A known release-tagged event remains searchable after local Docker rotation |

Do not mark `FW-PROD-002` complete until every applicable row has an owner, UTC test
time, result, and evidence location. Likewise, select an SMTP provider and prove
password-reset delivery under `FW-PROD-003`; observability does not complete email.

## Deployment responsibilities

Assign named owners before deployment. One person may hold multiple roles, but no
responsibility should be implicit.

| Responsibility | Required outcome |
| --- | --- |
| Release owner | Approves the commit, image digest, migration plan, and rollout |
| Database owner | Confirms backup/PITR status and can perform a restore |
| Domain/TLS owner | Controls DNS, certificates, proxy rules, and HSTS changes |
| Provider owner | Controls SMTP and Razorpay configuration |
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
gunicorn --no-control-socket --bind :8000 --workers 2 --timeout 30 --graceful-timeout 30 \
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
8. Uptime, error, database, backup, and financial-exception alert destinations.
9. Separate Cloudflare R2 Standard buckets and bucket-scoped credentials for staging
   and production uploaded media. Production also requires an owned media domain.

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
WAGTAILADMIN_BASE_URL=https://savings.example.com
PUBLIC_CATALOGUE_ENABLED=False

MEDIA_STORAGE_BACKEND=r2
R2_ACCOUNT_ID=<32-character-cloudflare-account-id>
R2_ACCESS_KEY_ID=<bucket-scoped-access-key-id>
R2_SECRET_ACCESS_KEY=<bucket-scoped-secret-access-key>
R2_BUCKET_NAME=<production-media-bucket>
R2_CUSTOM_DOMAIN=media.savings.example.com
R2_SIGNED_URL_EXPIRY_SECONDS=900

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
DEFAULT_FROM_EMAIL=Jai Sri Krishna Jewellery <noreply@example.com>
SERVER_EMAIL=errors@example.com

PAYMENT_GATEWAY=razorpay
RAZORPAY_MODE=test
RAZORPAY_KEY_ID=<rzp_test_key-id>
RAZORPAY_KEY_SECRET=<test-key-secret>
RAZORPAY_WEBHOOK_SECRET=<separate-webhook-secret>
RAZORPAY_TIMEOUT_SECONDS=10

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
- `WAGTAILADMIN_BASE_URL` is the public origin used to build absolute CMS links. Do
  not include `/cms/` or a trailing slash.
- Keep `PUBLIC_CATALOGUE_ENABLED=False` through the initial catalogue deployment.
  Change it to `True` only after the catalogue root and reviewed products are live and
  their direct public URLs pass desktop/mobile, metadata, rendition, and enquiry checks.
  The application independently requires the catalogue root to remain live/public;
  switching the flag back to `False` is the fast navigation rollback.
- Keep `PUBLIC_EDITORIAL_PAGES_ENABLED=False` through the initial editorial migration.
  With the flag disabled—or when a CMS page is draft, restricted, or unpublished—the
  stable `/about/` and `/our-story/` routes serve their reviewed Django fallbacks.
  Enable it only after editorial authorization and the live About revision pass review.
- `MEDIA_STORAGE_BACKEND=r2` is mandatory when Wagtail is deployed. Use a separate
  R2 Standard bucket and Object Read & Write token for each environment. Scope each
  token to its one bucket; never expose either credential to browser code or logs.
- `R2_CUSTOM_DOMAIN` is a hostname without `https://`, port, path, or trailing slash.
  Production checks reject a missing domain and Cloudflare's rate-limited `r2.dev`.
  Private originals/documents use 15-minute signed S3 API URLs; only generated
  renditions use the unsigned custom domain.
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
- Keep `PAYMENT_GATEWAY=razorpay` while pausing new payments so callbacks and signed
  webhooks remain available. Use the audited owner Payment Operations page for normal
  or volatility closure, or `PAYMENT_INITIATION_KILL_SWITCH=True` as the environment
  fail-safe. Never use the mock payment adapter outside debug mode. Metal
  contributions are independently unavailable until an owner has published the
  applicable Scheme Rate.
- `RAZORPAY_MODE` is required when Razorpay is selected and accepts only `test` or
  `live`. It must match the API key prefix. Change the mode, key ID, API key secret,
  and separately generated mode-specific webhook secret as one controlled cutover.
- Keep each Razorpay API secret distinct from the webhook secret. Do not log request
  signatures, secret values, full provider payloads, or database URLs.
- `APP_RELEASE` must identify exactly one source/image build and must be identical in
  the migration job and web service.

The complete variable reference is maintained in the [README](../README.md#environment-variables).

## Cloudflare R2 media setup and proof

The application sends uploads through Django; browsers do not upload directly to
R2. Wagtail originals and documents use the private `default` storage alias and
short-lived signed S3 API URLs. Generated image renditions use the separate
`renditions` alias and the public custom media domain. WhiteNoise remains responsible
for application static files.

1. Create two R2 **Standard** buckets such as `jsk-media-staging` and
   `jsk-media-production`. Do not share a bucket between environments.
2. Create a separate R2 API credential for each bucket. Select **Object Read &
   Write** and restrict it to that one bucket. Save the Access Key ID and Secret
   Access Key immediately in the relevant secret store; never commit or paste them
   into tickets, chat, screenshots, or shell output.
3. For the first non-production smoke, set `MEDIA_STORAGE_BACKEND=r2`, configure the
   account ID, key pair, and staging bucket, and leave `R2_CUSTOM_DOMAIN` empty. This
   keeps generated URLs signed and avoids making the staging bucket public.
4. Apply Wagtail migrations, run normal Django checks, and execute:

   ```powershell
   uv run --env-file .env.r2 python manage.py check_media_storage
   ```

   The command creates a small PNG, reads it back, creates and reads a Wagtail
   rendition, then deletes its database rows and both objects. It must report all
   four checks as successful, leave no `r2-storage-check-*` object, and expose no
   credential or signed URL in output.

   Evidence recorded 2026-08-24: the isolated non-production command reported that
   upload, read, rendition, and cleanup all passed. No credential, URL, or temporary
   object identifier is retained in the repository.
5. Before production, add `jaishrikrishnajewellery.com` as a zone in the same
   Cloudflare account and connect `media.jaishrikrishnajewellery.com` to the
   production bucket under **R2 → bucket → Settings → Custom Domains**. If the
   authoritative DNS is not already on Cloudflare, first inventory and preserve all
   apex, `www`, MX, TXT, CAA, and verification records before changing nameservers or
   using Cloudflare's supported partial-zone setup. Never CNAME the media hostname to
   an `r2.dev` address.

   DNS baseline observed 2026-08-24: authority remains on `ns1.linode.com` through
   `ns5.linode.com`; the apex and `www` resolve to `172.235.9.77`; MX records point
   to `smtp.secureserver.net` at priority 0 and `mailstore1.secureserver.net` at
   priority 10; TXT includes `v=spf1 include:secureserver.net -all` and `T1327472`.
   This public snapshot is not a complete zone export. Export and compare every
   Linode DNS record before changing the registrar's nameservers.

   Cutover evidence recorded 2026-08-24: Cloudflare received all 17 non-NS records,
   including the two GoDaddy DKIM CNAMEs and Postmark DKIM TXT record missed by the
   automatic import. Public authority changed to `carlane.ns.cloudflare.com` and
   `tony.ns.cloudflare.com` with no stale DS delegation. Both authoritative servers
   returned matching apex A/AAAA and MX answers; public apex, `www`, live, and ready
   HTTPS checks returned `200`. Keep the Linode zone intact as the short-term DNS
   rollback source until Cloudflare and mail delivery have remained stable.
6. Disable the production bucket's public `r2.dev` URL. On the Cloudflare zone, add
   one zone-level WAF custom rule with the **Block** action:

   ```text
   (http.host eq "media.jaishrikrishnajewellery.com" and
    (starts_with(http.request.uri.path, "/original_images/") or
     starts_with(http.request.uri.path, "/documents/")))
   ```

   The Free plan currently includes a limited number of zone custom rules, so retain
   evidence that requests to both protected prefixes return `403` while a generated
   `/images/` rendition returns `200`. The S3 API endpoint remains private and is not
   affected by this browser-facing WAF rule.
7. Add a cache rule only for `media.jaishrikrishnajewellery.com/images/*` and respect
   the object's `Cache-Control: public, max-age=86400`. Do not cache signed original
   or document responses. Purge the media hostname after changing cache or CORS rules.
8. No R2 CORS policy is required for the current server-side upload and ordinary
   HTML `<img>` flow. Record that explicit deny-by-default decision. If later browser
   JavaScript, canvas access, or direct uploads require CORS, allow only the exact
   production origins and required `GET`/`HEAD` methods or upload headers; never use
   a wildcard origin for credentialed operations.
9. Re-run `check_media_storage` with the production release candidate and production
   bucket before editor access is enabled. With `R2_CUSTOM_DOMAIN` configured, the
   command also requires the generated `/images/` rendition to return `200`, carry
   `Cache-Control: public, max-age=86400`, and produce a Cloudflare cache `HIT` within
   three requests. The direct custom-domain `/original_images/` and `/documents/`
   prefixes must return `403`. Confirm R2 metrics show the temporary writes, reads,
   and deletes and that the bucket is empty apart from approved media.

   Before running it, the bucket's Custom Domains panel must show the media hostname
   as Active and both Cloudflare authoritative nameservers must resolve it. `NXDOMAIN`
   means the R2 attachment is not ready; do not work around that by manually creating
   a generic CNAME. If the command warns that cleanup was incomplete, inspect and
   remove only `r2-storage-check-*` records and objects before retrying. Public
   rendition and private-prefix checks retry three times and distinguish an HTTP
   status failure from a DNS/network/TLS failure; use that classification before
   changing WAF or cache rules.

   Production evidence recorded 2026-08-24: an initial attachment mistakenly used
   the apex domain and was removed without disrupting the application. The corrected
   `media.jaishrikrishnajewellery.com` attachment became active with valid TLS;
   nonexistent `/images/` returned `404`, both private prefixes returned `403`, and
   the real production smoke passed upload, read, rendition, public delivery, access
   controls, and cleanup. Apex, `www`, live, and ready remained `200`.

   Cache evidence recorded 2026-08-24: after the host-scoped `/images/` cache rule
   was deployed, a fresh production smoke observed the required
   `Cache-Control: public, max-age=86400` response and a Cloudflare cache `HIT`; the
   private-prefix and cleanup checks continued to pass.

Credential rotation uses overlap, not downtime: create a second bucket-scoped token,
replace the two R2 key values, recreate the web service, run `check_media_storage`,
then revoke the old token and run the check again. Roll back to the previous token
only while it remains active; never keep both indefinitely.

Rotation evidence recorded 2026-08-24: a separately created replacement token scoped
to the production media bucket passed the full storage/custom-domain smoke. The old
token was deleted and the replacement passed the full smoke again. A transient local
DNS/TLS interruption affected only a public WAF probe; bounded retries then completed
without changing credentials or Cloudflare security rules.

R2 durability is not a backup against operator deletion or application mistakes.
Before real catalogue media is accepted, copy a non-sensitive test object to the
approved backup target, delete only that test object from the primary bucket, restore
it to the same key, and compare its size and SHA-256 hash. Record the date, operator,
bucket names, evidence, and cleanup. Define a scheduled copy/retention policy for real
media and test restoration periodically; database recovery and media recovery must use
compatible recovery points because Wagtail stores object keys in PostgreSQL.

Accepted deferral recorded 2026-08-24: this recovery drill is not required to begin
local catalogue-domain development. It remains `FW-MEDIA-002`; approved source images
must be retained outside R2, and R2 must not become the only copy until a backup target
and periodic restore proof exist.

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

## Repository change to Linode deployment workflow

Follow this workflow for every application, dependency, configuration-template, or
deployment-file change. Never edit tracked source code directly in `/opt/jsk/app` on
the server, never deploy an uncommitted worktree, and never use a mutable `latest`
tag as release identity.

### 1. Make and validate the change locally

Start from an up-to-date `main` after the current release PR has been merged. Use a
short-lived branch; do not commit directly to `main`:

```powershell
git switch main
git pull --ff-only origin main
git switch -c agent/example-change
```

Implement one coherent change. Add tests for changed behavior and for every change
affecting payments, rates, allocations, balances, bonuses, redemptions, or other
financial invariants. When models change, create and inspect the migration locally;
never hand-edit an applied migration. Update canonical documentation when behavior or
operational state changes.

Run the release-candidate checks against a disposable local PostgreSQL database:

```powershell
uv sync --frozen
uv run --env-file .env python manage.py makemigrations --check --dry-run
uv run --env-file .env python manage.py check
uv run --env-file .env python manage.py test
docker build --pull --tag jsk-savings:local-candidate .
```

Never point these tests at the Linode production database. If a migration exists,
review its SQL/operations, expected locks, runtime, reversibility, and compatibility
with both the old and new application image.

### 2. Review, stage, commit, and push intentionally

Review the complete worktree and stage explicit paths so unrelated user work and
secrets cannot be swept into a commit:

```powershell
git status --short
git diff --check
git diff
git add -- path/to/changed-file another/changed-file
git diff --cached --check
git diff --cached
git commit -m "Describe the change"
git push -u origin HEAD
gh pr create --draft --fill
```

Do not stage `.env`, `.env.production`, CA files, database URLs, provider keys,
webhook secrets, SMTP passwords, exports, backups, or customer data. A tracked
`.env*.example` file must contain placeholders only. The pull request must describe:

- the behavior and reason for the change;
- migrations and old/new-image compatibility;
- financial-invariant and access-control impact;
- tests and manual checks performed;
- provider/configuration changes;
- the exact rollback image and any condition that makes application rollback unsafe.

### 3. Pass the repository release gate

Both GitHub Actions jobs (`django` and `container`) must pass for the exact pull-request
head commit. Review the diff, resolve conversations, and merge to `main`; record the
resulting full commit SHA. Configure GitHub branch protection to require a pull
request and successful checks before merging and to disallow force pushes.

An Actions run that did not start is not a passing run. If GitHub Actions is disabled
or blocked by an account/billing problem, restore it before treating CI as a
production release gate. Locally validated builds alone may be used only for the
documented staging/infrastructure exercise, not a real-funds deployment.

### 3a. Realign the local checkout after merge

A branch name is not the production release identity. Production runs the immutable
image and `APP_RELEASE` commit recorded during deployment; `main` is the protected
source branch from which that release was approved. After the pull request is merged,
refresh the developer checkout instead of continuing work on the merged feature
branch:

```powershell
git status --short
git fetch origin
git switch main
git pull --ff-only origin main
git status -sb
```

The final status should show `main...origin/main` with no tracked changes. An expected
untracked file may remain, but it is not part of `main` and must not be swept into a
later commit. If `git status` shows unfinished tracked or untracked work, do not use
`reset --hard`, forced checkout, or an indiscriminate stash. Move intentional work to
its own branch or stash only explicitly selected paths before switching.

After confirming that the pull request is merged and the production stabilization
window is complete, the merged local feature branch may be deleted safely:

```powershell
git branch -d agent/completed-feature
```

Deleting the remote feature branch is optional and should wait until the release is
stable. It does not affect the merge commit or deployed image. Do not reverse local
database migrations merely because a feature branch is deleted; the local schema
should match the migrations on updated `main`.

Start every later change from a freshly updated protected branch and use a new,
descriptive branch:

```powershell
git switch main
git pull --ff-only origin main
git switch -c agent/descriptive-feature-name
```

`--ff-only` is intentional: it stops instead of creating an accidental merge commit
when the local `main` has diverged. Never deploy by referring only to the current
feature branch; build and deploy the exact merged 40-character commit SHA.

### 4. Build once and identify the release immutably

The production target is a CI-published GHCR image built once from the merged commit,
scanned, and promoted by immutable digest, for example:

```dotenv
APP_IMAGE=ghcr.io/rajeshr188/jsk-ss@sha256:<approved-manifest-digest>
APP_RELEASE=<full-merged-commit-sha>
```

Record the commit, CI run, image digest, scan result, migration plan, and previous
production digest in the release evidence. A digest pins exact image content; a tag
alone can be moved.

Until registry publishing exists, the only permitted substitute is a staging-only
build performed on the Linode from the exact detached commit:

```bash
docker build --pull --tag "jsk-savings:${JSK_RELEASE_SHA}" .
docker image inspect "jsk-savings:${JSK_RELEASE_SHA}"
```

Do not rebuild separately for staging and real production because the resulting
artifact would no longer be the one that passed the gate.

### 5. Prepare the Linode release

Open a planned change window. Record the current `APP_IMAGE`, `APP_RELEASE`, container
status, owner-dashboard customer/account counts, cash principal, earned bonus, gold
grams, silver grams, and exception counts. Confirm a current managed recovery point
and that the previous image remains present or pullable.

Fetch source metadata and detach at the approved merged commit. A fetch alone does not
change the running container:

```bash
cd /opt/jsk/app
git status --short
git fetch --prune origin
export JSK_RELEASE_SHA=FULL_40_CHARACTER_APPROVED_COMMIT_SHA
git checkout --detach "$JSK_RELEASE_SHA"
test "$(git rev-parse HEAD)" = "$JSK_RELEASE_SHA"
```

For a registry release, pull the recorded digest. For the staging-only fallback,
build the local tag shown above. Edit only the two release identity values in the
protected server environment; do not replace the file from the example and thereby
erase production secrets:

```bash
nano .env.production
```

Set `APP_IMAGE` to the approved digest or local staging tag and set `APP_RELEASE` to
the matching full commit SHA. Then validate the exact candidate against the real
production configuration and review database state without mutation:

```bash
docker compose --env-file .env.production -f compose.production.yml config --quiet
docker compose --env-file .env.production -f compose.production.yml \
  run --rm --no-deps web python manage.py check --deploy --fail-level ERROR
docker compose --env-file .env.production -f compose.production.yml \
  run --rm --no-deps web python manage.py showmigrations --plan
docker compose --env-file .env.production -f compose.production.yml \
  run --rm --no-deps web python manage.py migrate --plan
```

Stop if any output differs from the reviewed plan. A non-backward-compatible migration
requires its own maintenance and recovery procedure; do not apply it while the old
image serves traffic.

#### Customer-invitation migration preflight (`accounts.0003`)

Before applying `accounts.0003_customerinvitation_and_more`, run the candidate's
read-only integrity command against production:

```bash
docker compose --env-file .env.production -f compose.production.yml \
  run --rm --no-deps web python manage.py check_auth_email_integrity
```

Record `duplicate_groups=0`. Blank-email administrative users are reported but do not
block the conditional constraint. If duplicates exist, stop. In a private terminal
only, rerun with `--show-identifiers`, inspect each user's role, customer linkage,
scheme accounts, and audit/financial history, and decide which distinct email belongs
to each real person. Do not paste that personal-data output into shared logs, and do
not automatically delete, merge, deactivate, or reassign accounts. Rerun the default
command until it passes. The migration independently repeats this check immediately
before adding the case-insensitive unique constraint.

Set the bounded invitation lifetime in `.env.production` before candidate validation:

```dotenv
CUSTOMER_INVITATION_EXPIRY_HOURS=72
```

The schema addition is backward-compatible with the previous image, but the new owner
workflow must not go live until the candidate migration succeeds and Caddy has loaded
the candidate `deploy/Caddyfile`. That proxy configuration excludes password-reset
and invitation-secret paths from access logs. Validate and recreate Caddy during the
release, then verify its effective configuration before inviting a customer. The
candidate image also disables Gunicorn's redundant full-path access log; Caddy remains
the authoritative privacy-reduced request log while Gunicorn retains error output.
Django's console handler redacts invitation and password-reset secrets if a CSRF
warning or application error includes either path.

Token-bearing responses must return `Cache-Control: no-store`, `Pragma: no-cache`,
and `Referrer-Policy: strict-origin`. Do not use `no-referrer`: production browser
evidence showed that it can produce `Origin: null` on the password POST, which Django
correctly rejects. `strict-origin` supplies only the scheme and host needed for CSRF
validation and never discloses the invitation/reset path to subresources. Do not add
`null` to `CSRF_TRUSTED_ORIGINS` or exempt either password endpoint from CSRF.

Authentication email identity must also be correct. In Django admin, update the
`SITE_ID=1` Sites record to domain `jaishrikrishnajewellery.com` and display name
`Jai Sri Krishna Jewellery`; never leave `example.com`. In Postmark, keep click and open
tracking disabled for the authentication stream. The application additionally sends
per-message opt-out headers, but provider configuration remains defense in depth.

After rollout, use a controlled customer mailbox to verify all of the following:

1. Owner creation sends one direct `https://jaishrikrishnajewellery.com/accounts/invitations/...`
   link and creates no scheme account.
2. The customer sets a password once, can sign in, and remains unenrolled until the
   owner creates a separate agreement.
3. Resending before acceptance invalidates the earlier URL.
4. Provider acceptance is labelled as such and is not treated as proof of receipt.
5. Caddy logs contain neither `/accounts/invitations/` nor
   `/accounts/password/reset/key/` request entries, and web-container logs contain no
   Gunicorn access entries or raw authentication tokens. A deliberately induced safe
   warning may contain only `[REDACTED]`; do not print either real URL while testing.
6. Password reset uses the owned site name/domain and remains a direct, untracked URL.

Production evidence recorded 2026-08-26: release
`f9081c1a52a3ce3dc99e1d816cce9846a5b31f92` returned `strict-origin` on the
token paths, accepted a newly invited customer's password setup, and subsequently
accepted that customer's forgot-password reset flow. The earlier `Origin: null`
rejection no longer occurred; CSRF enforcement, `no-store`, token redaction, and
edge-log exclusions remained enabled.

If the candidate must be rolled back after this additive migration, the previous image
can run against the extended schema. Its old owner form would again ask for temporary
passwords, so suspend customer creation until the corrected candidate is restored.

Before applying `schemes.0010_manual_scheme_rates`, confirm the old architecture has
no verified metal payment without an allocation and no open metal Razorpay order.
This deliberately includes both `PAID` and `PAID_UNALLOCATED`: an interrupted legacy
worker could have committed payment confirmation before recording the allocation.
Complete or reconcile those records on the old release first. The migration
intentionally stops instead of inventing a rate if either count is non-zero:

```bash
docker compose --env-file .env.production -f compose.production.yml \
  run --rm --no-deps web python manage.py shell -c \
  "from schemes.models import Contribution; modes=['GOLD','SILVER']; print('verified_metal_without_allocation=', Contribution.objects.filter(status__in=['PAID','PAID_UNALLOCATED'], scheme_account__savings_mode__in=modes, metal_allocation__isnull=True).count()); print('open_metal_orders=', Contribution.objects.filter(status='PENDING', payment_gateway='razorpay', gateway_order_id__isnull=False, scheme_account__savings_mode__in=modes).count())"
```

Record both zero results with the release evidence. This migration renames/removes
provider-era schema, so the previous image is not schema-compatible after it runs;
use the reviewed maintenance window, database recovery point, and roll-forward plan.
After recording the preflight, prevent a new payment or allocation from racing the
migration by stopping public traffic and the old web process:

```bash
docker compose --env-file .env.production -f compose.production.yml stop caddy
docker compose --env-file .env.production -f compose.production.yml stop web
docker compose --env-file .env.production -f compose.production.yml ps
```

Confirm both services are stopped. Keep them stopped until the migration succeeds and
the candidate web container is healthy. If migration fails, do not start the candidate;
retain the failed output, restore the recorded previous `APP_IMAGE` and `APP_RELEASE`,
start the previous web and Caddy services, and follow the incident/recovery procedure.

### 6. Apply once, deploy, and verify

After the backup/recovery point, migration plan, rollback image, operator, and business
reconciler are confirmed, run migrations exactly once:

```bash
docker compose --env-file .env.production -f compose.production.yml \
  run --rm --no-deps web python manage.py migrate --noinput
```

For a release containing the catalogue authorization milestone, reconcile the
application-owned CMS groups, catalogue subtree, media collection, and approval
workflow while Caddy is still stopped. The command is idempotent but intentionally
resets the three `Catalogue ...` groups to the reviewed least-privilege matrix; do
not reuse those group names for unrelated permissions:

```bash
docker compose --env-file .env.production -f compose.production.yml \
  run --rm --no-deps web python manage.py configure_catalog_permissions
docker compose --env-file .env.production -f compose.production.yml \
  run --rm --no-deps web python manage.py configure_catalog_permissions --check
```

This creates only a **draft** catalogue page and does not grant any user access.
After the production rollout and media-recovery limitation are accepted, a superuser
must explicitly assign an active staff user to `Catalogue Editors`, `Catalogue
Publishers`, or `Catalogue Administrators`. An application `OWNER` role alone must
never be treated as CMS authorization. Retain the successful check output with the
release evidence.

Keep `PUBLIC_CATALOGUE_ENABLED=False` during that authorization rollout. After an
authorized publisher has approved the catalogue root and initial products, verify the
direct `/jewellery/` and product URLs, responsive media-domain renditions, canonical
and Open Graph metadata, JSON-LD, filters, empty/no-result handling, enquiry links,
and mobile/desktop accessibility. Then set `PUBLIC_CATALOGUE_ENABLED=True`, validate
the Compose configuration, recreate `web`, and confirm the Jewellery link appears in
both primary and footer navigation. If discovery must be withdrawn, set the flag back
to `False` and recreate `web`; do not unpublish or delete content merely to hide the
navigation while an incident is assessed.

For a release containing `FW-CMS-003`, keep
`PUBLIC_EDITORIAL_PAGES_ENABLED=False`, apply `pages.0001_initial`, and reconcile the
separate Editorial groups, media collection, seeded draft pages, and approval workflow:

```bash
docker compose --env-file .env.production -f compose.production.yml \
  run --rm --no-deps web python manage.py configure_editorial_pages
docker compose --env-file .env.production -f compose.production.yml \
  run --rm --no-deps web python manage.py configure_editorial_pages --check
```

The command is idempotent and does not overwrite later editor revisions. It resets
only the dedicated `Editorial Editors`, `Editorial Publishers`, and
`Editorial Administrators` groups to their reviewed page/media scopes; never reuse
those names for other access. It creates About and Our Story as drafts and grants no
user membership. Explicitly assign an active staff user, review preview and metadata,
approve and publish About, and confirm `/about/` still shows the static fallback while
the flag is false. Our Story remains unlinked and may stay draft.

After approval, set `PUBLIC_EDITORIAL_PAGES_ENABLED=True`, validate Compose, recreate
only `web`, and verify `/about/` on desktop/mobile, its R2 rendition when an image is
used, and the unchanged policy, Contact, Savings Plans, homepage, and authenticated
routes. Verify `/our-story/` directly only if its CMS revision was deliberately
published; it must not appear in navigation. Fast rollback is to set the flag to
`False` and recreate `web`, which immediately restores both reviewed Django fallbacks
without deleting Wagtail revisions or media.

For the `FW-PRODUCT-001` metal-only boundary release, repeat the read-only CASH audit
immediately before stopping traffic. The approved baseline is one open CASH account,
zero pending CASH payments, zero verified CASH payments/INR, zero CASH redemptions,
and zero plans with a nonzero cash bonus. Stop and investigate if any monetary or
pending-payment value differs; do not strand or silently rewrite a customer payment.
This release has no schema migration and preserves the empty account as an inert
historical record.

Run the candidate image against production configuration while traffic is still on
the previous release:

```bash
docker compose --env-file .env.production -f compose.production.yml \
  run --rm --no-deps web python manage.py check_cash_boundary
```

The command must report `status=ok`, `cash_activity_enabled=False`, and zero pending
payments, verified payments/INR, redemptions, and nonzero cash-bonus plans. Account
counts are informational and may retain the approved empty historical record.

After the candidate is healthy, confirm `DJANGO_DEBUG=False`, verify gold/silver
enrolment remains available, and sign in as the historical CASH customer to prove the
account and statement remain readable, no Pay action is rendered, and the direct
contribution URL returns `403`. Re-run `check_financial_exceptions` and the aggregate
liability snapshot. The release must not change the approved zero CASH exposure.

On the current single-host topology, expect a brief maintenance window. Start the
candidate web container while Caddy remains stopped, and wait until `web` reports
healthy. Do not restore public traffic before that health gate:

```bash
docker compose --env-file .env.production -f compose.production.yml \
  up -d --no-deps web
docker compose --env-file .env.production -f compose.production.yml ps
```

Repeat `ps` until `web` is healthy. Then recreate Caddy so its upstream resolution
cannot retain the prior container address. Caddy's named volumes preserve certificates:

```bash
docker compose --env-file .env.production -f compose.production.yml \
  up -d --force-recreate --no-deps caddy
```

Verify the public release and recent logs:

```bash
curl --fail-with-body https://jaishrikrishnajewellery.com/health/live/
curl --fail-with-body https://jaishrikrishnajewellery.com/health/ready/
curl --fail-with-body https://jaishrikrishnajewellery.com/static/css/base.css
docker compose --env-file .env.production -f compose.production.yml logs --since=10m web
docker compose --env-file .env.production -f compose.production.yml logs --since=10m caddy
```

The health JSON must contain the new `APP_RELEASE`. Complete the production-safe smoke
test and compare post-release liabilities and exception counts with the baseline,
accounting for legitimate activity. Observe through the stabilization window before
closing the release record.

### 7. Propagate configuration-only changes

Validate configuration changes through the same review and change-window controls.
`restart` does not load changed environment values:

| Changed item | Required action after validation |
| --- | --- |
| Django/provider environment | `up -d --force-recreate --no-deps web`, then readiness and provider-specific verification |
| `ACME_EMAIL` or Caddy environment | `up -d --force-recreate --no-deps caddy`, then inspect ACME/TLS logs |
| `deploy/Caddyfile` | Validate with the pinned Caddy image, recreate Caddy, then test redirects/TLS |
| Managed database CA | Validate with OpenSSL, install mode `0644`, recreate `web`, then test readiness |
| Database/SMTP/provider credential | Activate replacement, recreate `web`, verify the affected path, then revoke the old credential |
| Application code/dependency | Build and deploy a new immutable release; never edit the running container |

### 8. Roll back safely

If the schema remains compatible, edit `.env.production` to restore the recorded
previous `APP_IMAGE` and `APP_RELEASE`, then replace `web`, wait for readiness, and
recreate Caddy as in the deployment step. Repeat health, smoke, liability, and
exception checks and preserve the failed release's logs and provider identifiers.

Do not run reverse migrations casually, and do not restore an older database merely
to roll back code. If the applied schema is incompatible with the previous image,
keep traffic stopped or use the migration-specific compatible image/recovery plan.
Any database timeline change after financial events requires full provider-event and
denomination-specific reconciliation.

## Pre-deployment gate

Run this check using the target environment's real non-secret configuration and
secret injection:

```powershell
python manage.py check --deploy --fail-level ERROR
```

The command must have no errors. Review every warning explicitly; a warning is not
automatically safe. The project's custom checks reject mock or unsupported payment
gateways, missing selected-payment credentials, non-delivering email backends, wildcard hosts,
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

## Razorpay Live Mode activation gate

Live-key acceptance is deliberately mode-bound. Migration
`schemes.0011_razorpay_gateway_mode` labels every historical Razorpay contribution
and webhook as `test`, which is truthful because earlier releases rejected Live keys.
New orders and events retain their mode, callback verification rejects a cross-mode
contribution, and webhook event uniqueness includes the provider mode. This migration
does not alter amounts, payment status, Scheme Rates, allocations, or liabilities.

First deploy the supporting release while production still uses Test Mode:

1. Add `RAZORPAY_MODE=test` beside the existing Test credentials.
2. Record the image identity, financial baseline, and current database recovery point.
3. Run the deploy check and review the `0011` migration plan.
4. Apply the migration once, deploy the web service, and confirm Test checkout,
   callback verification, signed webhook processing, financial exceptions, and CSV
   export still pass. The export now includes `gateway_mode` for reconciliation.

Do not activate Live Mode until all of these account-side controls are confirmed:

- Razorpay has activated the merchant account and approved the owned website.
- The owner generated Live API credentials and stored them only in the production
  secret location. Test and Live credentials are never mixed.
- In the Razorpay **Live Mode** dashboard, the stable webhook URL is
  `https://jaishrikrishnajewellery.com/scheme/payments/razorpay/webhook/`, its secret
  is distinct from the API key secret, `payment.captured` is enabled, and a monitored
  failure-alert email is configured.
- Payment Capture is configured to auto-capture. The application creates entitlement
  only after Razorpay reports the exact local order, INR amount, and `captured` state.
- Better Stack/Linode and the financial-exception heartbeat reach named responders.
- A business owner is assigned to daily reconciliation and an incident owner can
  pause new Checkout exposure without disabling Razorpay callback/webhook handling.
- The payment-error refund and dispute procedures below are accepted. General refunds
  of already credited scheme contributions remain unsupported because the application
  has no compensating payment-reversal workflow.

Use a short controlled cutover with no customer checkout in progress:

1. Set `PAYMENT_INITIATION_KILL_SWITCH=True`, validate Compose, and recreate `web`.
   Keep `PAYMENT_GATEWAY=razorpay` and all mode-matched credentials configured.
   Confirm Pay/Resume actions disappear while callbacks, webhooks, reads, statements,
   owner views, live, and ready remain healthy.
2. Confirm Razorpay has no unresolved Test payment for a locally pending order. Do not
   edit a pending contribution merely to pass this gate.
3. In `.env.production`, atomically set:

   ```dotenv
   PAYMENT_GATEWAY=razorpay
   PAYMENT_INITIATION_KILL_SWITCH=True
   RAZORPAY_MODE=live
   RAZORPAY_KEY_ID=rzp_live_...
   RAZORPAY_KEY_SECRET=<live-api-key-secret>
   RAZORPAY_WEBHOOK_SECRET=<separate-live-webhook-secret>
   ```

4. Before changing the running service, exercise the candidate configuration without
   printing credentials:

   ```bash
   docker compose --env-file .env.production -f compose.production.yml \
     run --rm --no-deps web python manage.py check --deploy --fail-level ERROR

   docker compose --env-file .env.production -f compose.production.yml \
     run --rm --no-deps web python manage.py check_razorpay_live_readiness

   docker compose --env-file .env.production -f compose.production.yml \
     run --rm --no-deps web python manage.py check_financial_exceptions
   ```

   Readiness blocks unknown/mixed credentials, missing mode labels, failed Live
   webhooks, and any pending contribution created in another mode (with or without a
   provider order). If it blocks, restore Test
   Mode and reconcile the named condition; never bypass the command or rewrite
   provider references.
5. After every gate passes, set `PAYMENT_INITIATION_KILL_SWITCH=False`, validate
   Compose, recreate `web`, wait for health, recreate Caddy so it resolves the
   replacement upstream, and confirm live/ready return the expected release.
6. Sign in with one controlled real customer account and complete one legitimate
   minimum-value metal contribution. Confirm the UI explicitly says **Live payment**,
   the Dashboard payment is captured, the local contribution has `gateway_mode=live`,
   the signed Live webhook is processed once, exactly one metal allocation uses the
   pre-payment Scheme Rate lock, and liabilities change by exactly that allocation.
   Treat this as a real contribution; do not refund it merely to clean up a smoke test.
7. Export contributions and reconcile mode, payment ID, order, amount, INR currency,
   captured status, local status, allocation, and Dashboard settlement. Re-run the
   financial-exception and readiness commands, inspect logs, and retain redacted
   evidence.

#### Completed Live acceptance evidence — 2026-08-31

- Production image/release: `5fa726b2d76666abe7063f8b48125d6869566ecc`;
  `schemes.0011_razorpay_gateway_mode` was already applied.
- Live readiness passed with no pending contribution from another mode, missing mode
  stamp, or failed Live webhook. Financial exceptions reported zero paid-unallocated,
  failed-webhook, and mismatched-webhook records.
- Two real Live contributions were captured for INR `150.00` and INR `200.00`.
  Their signed `payment.captured` events were each processed once; the corresponding
  `payment.authorized` events were safely retained as ignored.
- Each captured contribution created exactly one immutable gold allocation using its
  pre-payment Scheme Rate lock: `0.008973` g and `0.012229` g, totalling `0.021202` g.
- Two additional Live orders were still in Razorpay `created` state with zero attempts,
  zero payments, and their full amounts due. After provider verification, their local
  pending contributions were retired through `fail_contribution`; no provider or
  financial record was deleted.
- Final reconciliation: zero pending Live contributions, two paid and two safely failed
  Live contributions, two processed capture webhooks, `0.021202` g Live gold allocation,
  `0.329272` g total outstanding gold, and a clean financial-exception check.
- Paid external monitoring and rotation rehearsals remain explicitly deferred under
  `FW-PROD-002` and `FW-PROD-003`; webhook recovery remains `FW-PAY-003`.

### Payment operations circuit-breaker deployment (`FW-PAY-004`)

Migration `schemes.0013_payment_operations_control` adds one singleton control and
seven weekly schedule rows. It seeds Monday–Saturday 09:00–21:00 and Sunday
09:00–13:00 in the configured `Asia/Kolkata` timezone, but leaves the schedule
disabled. Applying the migration therefore does not close an otherwise available
production Checkout. It does not modify any contribution, provider reference, locked
Scheme Rate, allocation, webhook event, redemption, or liability.

Before deployment, retain a current recovery point and the usual financial baseline.
Then run the candidate gates:

```bash
docker compose --env-file .env.production -f compose.production.yml \
  run --rm --no-deps web python manage.py migrate --plan

docker compose --env-file .env.production -f compose.production.yml \
  run --rm --no-deps web python manage.py check --deploy --fail-level ERROR

docker compose --env-file .env.production -f compose.production.yml \
  run --rm --no-deps web python manage.py check_financial_exceptions
```

The migration plan must show only `schemes.0013`. Apply it once, confirm it appears as
`[X]`, then deploy the healthy candidate. After cutover run:

```bash
docker compose --env-file .env.production -f compose.production.yml \
  exec -T web python manage.py check_payment_operations

docker compose --env-file .env.production -f compose.production.yml \
  exec -T web python manage.py check_financial_exceptions
```

The first check must report `status=ok`, seven valid weekdays, the expected release,
and `schedule_enabled=false` on first deployment. Sign in as an owner and open
**Operations → Payment operations**. Review all seven windows and leave the schedule
disabled until a controlled test period is agreed.

For activation, first publish/review the current Gold and Silver Scheme Rates. Enable
the schedule with a mandatory reason. Verify during open hours that Pay is visible,
then use a short controlled manual Gold/Silver or Pause-All test to prove Pay/Resume
disappear while live/readiness and the webhook endpoint remain available. Clear the
manual pause with a second reason. Test the exact closing boundary separately without
creating a real contribution merely for the smoke.

For an owner-driven volatility pause, use the same page; no container recreation is
required. For an application-control incident, set this in `.env.production`:

```dotenv
PAYMENT_INITIATION_KILL_SWITCH=True
```

Validate Compose and recreate only `web`. Do not clear `PAYMENT_GATEWAY`, remove
Razorpay credentials, disable Caddy, or disable the Razorpay webhook. After the
incident, review provider/local pending orders and publish current rates before
setting the variable back to `False` and recreating `web` again.

#### Completed rollout and schedule-activation evidence — 2026-08-31

- Managed PostgreSQL recovery point: 2026-08-31 11:00 AM IST. Rollback image/release:
  `jsk-savings:c3e8c4618c9ec160fcdf764b38d05de6b7e5df9e`.
- Production image/release: `jsk-savings:e027b9ae1550c314584c551eb3da31d5529ea544` /
  `e027b9ae1550c314584c551eb3da31d5529ea544`; locally built image ID
  `sha256:a9e021ceed8b9d08d64b42fc71a3af0cd6c95facdc8f81d4fb90ed1d8623e558`.
- The reviewed migration plan contained only
  `schemes.0013_payment_operations_control`; it applied successfully. The baseline
  was seven customers, seven scheme accounts, zero pending Razorpay contributions,
  zero INR principal/earned bonus, `0.329272` g gold, and zero silver.
- Live/readiness returned the expected release. Payment operations reported
  `status=ok`, `kill_switch=false`, `schedule_enabled=false`, both metals `OPEN`, and
  zero pending exposure. Razorpay Live readiness and financial exceptions both
  reported `status=ok` with no missing/cross-mode records, failed webhooks,
  paid-unallocated records, or mismatches.
- The owner exercised audited Pause All with a customer-safe notice. Customer Pay was
  unavailable while the owner restriction warning remained visible; no Checkout or
  provider order was created. A second audited change restored both metals to `OPEN`,
  and the financial-exception check remained clean.
- After current-day Gold and Silver Scheme Rates were published and reviewed, the
  owner enabled the weekly schedule with an audit reason. Its exact closing and
  reopening boundary worked as expected; the schedule remains enabled in production.

### Abandoned Razorpay order deployment and operation (`FW-PAY-002`)

The release introduces `schemes.0012_abandoned_razorpay_orders`. Its approved plan
adds the `ABANDONED` contribution choice, expands the paid-confirmation constraint to
permit that unpaid terminal state, and adds the payment-order reconciliation audit
action. It does not delete, rewrite, or backfill a contribution.

After the normal recovery-point, candidate-image, baseline, migration-plan, migration,
health, readiness, and financial-exception gates, inspect aged orders from the running
web container. Dry-run is deliberately the default and makes provider reads without
changing the database:

```bash
docker compose --env-file .env.production -f compose.production.yml \
  exec -T web python manage.py reconcile_abandoned_razorpay_orders \
  --older-than-hours=24
```

Review every line against Razorpay Dashboard. `ELIGIBLE_FOR_ABANDONMENT` requires all
of the following from the mode-matched API credentials: order status `created`, zero
attempts, zero associated payments, zero amount paid, the expected INR amount, and the
full amount still due. `REVIEW_REQUIRED` remains pending and must not be overridden.
Provider/API errors make the command fail and leave the affected contribution open.

Only after review, apply the same bounded selection:

```bash
docker compose --env-file .env.production -f compose.production.yml \
  exec -T web python manage.py reconcile_abandoned_razorpay_orders \
  --older-than-hours=24 --apply

docker compose --env-file .env.production -f compose.production.yml \
  exec -T web python manage.py check_financial_exceptions
```

The apply pass re-reads Razorpay, marks only eligible local contributions
`ABANDONED`, and appends an immutable audit event containing the provider snapshot.
It retains the Razorpay order ID and locked Scheme Rate. The customer no longer sees
a resume link for that contribution; a once-per-month account may start a replacement
order, while flexible attempts remain independent.

Razorpay's Orders API has no order-cancellation operation: application-side
`ABANDONED` does **not** make the remote order unpayable. Run this process during an
observed window. If a late signed capture arrives, the application intentionally
creates a failed-webhook financial exception rather than silently issuing entitlement.
Suspend the affected checkout, reconcile the order/payment/amount and any replacement
contribution, and follow the approved no-entitlement payment-error refund procedure.
Never delete the old contribution, provider order, reconciliation audit event, or
failed webhook.

#### Completed production rollout evidence — 2026-08-31

- Recovery point: 2026-08-30 12:00 PM IST. Rollback image/release:
  `jsk-savings:5fa726b2d76666abe7063f8b48125d6869566ecc`.
- Production image/release: `jsk-savings:c3e8c4618c9ec160fcdf764b38d05de6b7e5df9e` /
  `c3e8c4618c9ec160fcdf764b38d05de6b7e5df9e`; locally built candidate image ID
  `sha256:d94f1063b5e362e2da2d4934d722623a60a7412efb606f462fb331f4f36343df`.
- The reviewed plan contained only `schemes.0012_abandoned_razorpay_orders`; it applied
  successfully and every scheme migration through `0012` is recorded as applied.
- Reported Live/Ready checks returned the expected release. The running gateway
  remained Razorpay Live; Live readiness and financial exceptions returned `ok` with
  no missing modes, cross-mode pending order, failed webhook, paid-unallocated record,
  or mismatch.
- The first production reconciliation remained a dry run and reported zero pending or
  aged candidate, zero review requirement, zero abandonment, and zero error. No
  contribution or provider order was changed by that check.

### Live reconciliation, payment-error refund, and dispute boundary

- **Daily reconciliation:** compare Razorpay Live captured payments against the owner
  contribution export using `gateway_mode`, payment reference, INR amount, and local
  status. Investigate provider-only payments, local-only confirmations, amount/order
  mismatches, failed webhooks, and `PAID_UNALLOCATED` records before redemption.
- **Payment-error refunds:** the approved manual path is limited to captured duplicate
  or otherwise erroneous payments that created **no** local contribution entitlement.
  Verify this from the payment ID, order, amount, webhook ledger, contribution, and
  allocation before an authorized owner initiates the refund in Razorpay Dashboard.
  Record the refund ID, amount, reason, approver, timestamps, and final status in the
  incident record. If an entitlement exists, do not refund through the Dashboard:
  disable affected activity and escalate until an audited compensating workflow exists.
- **Disputes:** monitor Razorpay Dashboard and its configured notification address,
  review each item before its response deadline, preserve the agreement, payment,
  acknowledgement, statement, Scheme Rate lock, allocation, and showroom evidence,
  and accept or contest only through an authorized owner. A dispute or chargeback
  against a locally credited contribution is a financial incident requiring checkout
  suspension as appropriate and explicit liability reconciliation; never delete or
  edit the contribution to imitate reversal.

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
10. Execute the production-safe smoke test. Routine infrastructure releases must not
    create a payment merely as a health probe. In Test Mode use controlled test data;
    in Live Mode rely on non-mutating checks unless the business has approved a real,
    fully reconciled contribution.
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
8. Publish reviewed gold and silver Scheme Rates as the staging owner. Start a
   controlled metal checkout, publish a newer rate, complete the original payment,
   and verify it uses the old lock while a new checkout uses the new rate. Also verify
   that no metal order can be created when no applicable rate exists.
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

The Linode profile implements this boundary with masked structured Caddy access logs,
Better Stack/Vector off-host collection, external HTTP monitors, and the versioned
`check_financial_exceptions` heartbeat timer described above. Provider-side account
configuration and exercised incident evidence remain deployment actions, not source
code behavior.

Create actionable alerts for:

| Signal | Initial response |
| --- | --- |
| Liveness failure | Replace the unhealthy instance; inspect startup and worker logs |
| Readiness failure | Remove from traffic; inspect PostgreSQL health and connection capacity |
| Sustained 5xx or latency increase | Correlate by release and endpoint; consider image rollback |
| Failed/mismatched Razorpay webhook | Preserve ledger evidence; compare provider and local IDs |
| Any new `PAID_UNALLOCATED` record | Investigate the unexpected allocation exception; retry only from its original locked Scheme Rate |
| Database storage/CPU/connections near limit | Stop scaling web replicas blindly; restore capacity margin |
| Backup/PITR failure or missed snapshot | Treat production recovery as degraded and repair immediately |
| SMTP delivery/authentication failure | Verify provider status and credentials; test password reset |
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

1. Prevent new checkout order creation through the audited Payment Operations page.
   If that path is unavailable, set `PAYMENT_INITIATION_KILL_SWITCH=True`, validate
   Compose, and recreate only `web`. Keep `PAYMENT_GATEWAY=razorpay` and the webhook
   secret configured.
2. Keep the webhook endpoint and provider retry evidence available when safe.
3. Preserve all local contributions and `PaymentWebhookEvent` records. Do not edit or
   delete them to force a match.
4. Reconcile Razorpay order, payment, amount, currency, captured status, event ID,
   and local contribution using authorized provider access.
5. Follow the bounded manual refund/dispute procedure above. The application does not
   implement refund, chargeback, or payment-reversal mutations.
6. Re-enable checkout only after reconciliation and a signed webhook test in the
   same Razorpay mode as the environment.

### Scheme Rate or allocation incident

1. Leave verified but unallocated payments in `PAID_UNALLOCATED`.
2. Confirm the contribution already has the expected locked Scheme Rate. Do not
   substitute the newest rate after payment.
3. Correct the underlying application/database issue and use the owner-controlled
   allocation retry action, which is idempotent and audited.
4. Confirm exactly one immutable Scheme Rate link and allocation exist and that gold and
   silver remain separate.
5. Never edit, replace, or backdate the contribution's locked rate.

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

### Database and SMTP credentials

Create or activate the replacement credential, update the secret manager, roll the
web service, verify the relevant readiness/email path, then revoke the old
credential. Check that release jobs and administrative identities do not share the
web application's secret unnecessarily.

### Razorpay API keys

Use the provider's supported overlap/activation process, update both key ID and
secret atomically without changing `RAZORPAY_MODE`, roll the application, and verify
authenticated provider access in the same mode before deactivating the old key. Use
Test Mode for rehearsal; a Live rotation must not create an artificial customer
payment merely as a credential probe.

### Razorpay webhook secret

Webhook rotation must be coordinated because the provider and application must agree
on one signing secret. Use a controlled change window: pause financial activity,
update the endpoint and application secret in the provider-supported order, deploy,
send and verify a signed event in the environment's configured mode, check
idempotency, then resume. Older provider retries may still use the former secret, so
do not rotate while deliveries are outstanding. Preserve failed deliveries for
reconciliation; never accept unsigned events during the gap.

## Routine operations

| Frequency | Action |
| --- | --- |
| Every release | Green CI, image scan, deploy check, migration review, backup/PITR confirmation, smoke test, reconciliation |
| Daily | Review alerts, failed webhooks, allocation exceptions, backup success, database capacity |
| Weekly | Review error trends, certificate status, payment/email provider status, email delivery, and run expired-session cleanup |
| Monthly | Patch/rebuild base images and locked dependencies through a tested release; review access and secret age |
| Quarterly | Perform and evidence an isolated restore/reconciliation drill and an incident/alert exercise |
| After any incident | Preserve timeline/evidence, reconcile financial state, document cause/actions, and test prevention |

Dependency updates must change and review `uv.lock`; do not run an unlocked upgrade
inside a production build. Rebuild regularly with current trusted base-image patches,
then promote the resulting immutable digest through the normal release process.

## Go-live sign-off

The target full-production checklist remains below. Live acceptance does not mark
owner-deferred controls complete:

- [ ] The exact image passed CI, scanning, staging, and production deploy checks.
- [ ] Production uses `DJANGO_DEBUG=False`, explicit hosts/origins, HTTPS, secure
      cookies, staged HSTS, and verified proxy-header behavior.
- [ ] Database TLS/private access, backups, PITR, RPO/RTO, and an isolated restore
      plus denomination-specific reconciliation are proven.
- [ ] Real password-reset email delivery and sender-domain authentication are proven.
- [ ] Logs are retained and tested alerts reach named responders.
- [ ] Reviewed gold and silver Scheme Rates are published by an authorized owner,
      and rate-lock/no-rate staging smokes are evidenced.
- [ ] Razorpay uses a stable HTTPS webhook with signed, idempotent delivery testing.
- [ ] Separate Django, database, SMTP, Razorpay API, and webhook rotations
      have been rehearsed.
- [ ] Owner/customer access, documents, exports, audit, exceptions, and rollback have
      been smoke-tested.
- [ ] `FW-PROD-001` through `FW-PROD-003` are marked complete with evidence.
- [x] `FW-PAY-001` Live payment, capture, signed-webhook, allocation, and reconciliation
      acceptance is complete with the evidence above.
- [x] `FW-PAY-002` dry-run-first abandoned-order reconciliation is implemented with
      immutable provider snapshots and late-capture exception handling.
- [ ] Before expanding real-funds use, complete `FW-PAY-003` webhook recovery and the
      remaining refund/dispute, monitoring, and rotation controls, or retain explicit
      owner acceptance of their documented risk with manual compensating checks.

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
- [Docker Engine on Ubuntu](https://docs.docker.com/engine/install/ubuntu/)
- [Docker Compose file-backed secrets](https://docs.docker.com/reference/compose-file/services/#secrets)
- [Docker image pulls by digest](https://docs.docker.com/reference/cli/docker/image/pull/#pull-an-image-by-digest-immutable-identifier)
- [GitHub protected branches and required checks](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)
- [Gunicorn control-socket settings](https://github.com/benoitc/gunicorn/blob/master/docs/content/reference/settings.md#control)
- [PostgreSQL backup and restore](https://www.postgresql.org/docs/current/backup.html)
- [PostgreSQL `pg_dump`](https://www.postgresql.org/docs/current/app-pgdump.html)
- [PostgreSQL `pg_restore`](https://www.postgresql.org/docs/current/app-pgrestore.html)
- [Razorpay webhook best practices](https://razorpay.com/docs/webhooks/best-practices/)
- [Razorpay webhook validation and testing](https://razorpay.com/docs/webhooks/validate-test/)
- [Razorpay Test and Live modes](https://razorpay.com/docs/payments/dashboard/test-live-modes/)
- [Razorpay Orders APIs](https://razorpay.com/docs/api/orders/)
- [Razorpay order payment inspection](https://razorpay.com/docs/api/orders/fetch-payments/)
- [Razorpay payment capture settings](https://razorpay.com/docs/payments/payments/capture-settings/)
- [Razorpay payment Dashboard actions](https://razorpay.com/docs/payments/payments/dashboard/)
- [Razorpay dispute Dashboard actions](https://razorpay.com/docs/payments/disputes/dashboard/)
