# Project Status

## Current milestone

Production hardening — repository baseline complete; deployment exercises pending

## Completed

- Lithium authentication, Bootstrap/crispy forms, WhiteNoise, and custom user preserved.
- PostgreSQL-only environment configuration and India time zone.
- Jai Shri Krishna Jewellery branding and canonical documentation.
- Owner/customer roles, customer records, reusable plans, and snapshotted enrolments.
- Owner customer-management flow and isolated customer scheme view.
- Append-oriented contributions with pending/paid/paid-unallocated/failed states.
- Fixed/variable amount validation and once-per-month/flexible frequency rules.
- Debug-only mock payment adapter with verified, idempotent confirmation.
- Customer cash balance/history and owner contribution visibility.
- Debug-only mock gold/silver rate provider with configurable rates and purity.
- Immutable rate snapshots and one six-decimal metal allocation per paid contribution.
- Customer gold/silver gram balances and historical allocation-rate visibility.
- Owner dashboard with separately reconciled cash principal, gold grams, and silver grams.
- Current gold/silver reference rates and separately rounded indicative INR exposures.
- India-local successful-contribution counts for today and the current calendar month.
- MVP Alpha live workflow verified across owner setup, all three savings modes, customer payments and entitlements, and owner liability reconciliation.
- GoldAPI.io live adapter for XAU/XAG rates in INR with header-only secrets, bounded timeout, strict validation, and short quota-protection cache.
- Recoverable `PAID_UNALLOCATED` state when a verified payment cannot obtain a valid rate.
- Owner alerts, diagnostics, and an authorized idempotent allocation-retry action.
- Future public-signup requirements documented under `AUTH-*` domain rules.
- Razorpay test-mode order creation and customer Standard Checkout flow.
- Browser callback verification using the local order ID, HMAC, and a captured-payment server lookup.
- Signed raw-body `payment.captured` webhooks with a unique event ledger and idempotent financial processing.
- Unique Razorpay order/payment identifiers and one resumable pending order for once-per-month accounts.
- Shared callback/webhook confirmation services that create at most one cash or metal benefit.
- India-local, date-derived active/not-yet-eligible, redemption-eligible, and redeemed display states.
- Owner dashboard counts for eligible now and exclusive 1–30, 31–60, and 61–90-day forecast windows.
- Owner-only grouped eligibility review and customer-facing eligibility guidance without automatic account closure.
- Immutable, idempotent owner-recorded cash, metal, and jewellery-purchase redemptions.
- Partial/full settlement with denomination-specific outstanding balances and exact final account closure.
- Customer redemption history, owner redemption ledger, and liability reconciliation after settlement.
- External Razorpay Test Mode payment captured through Standard Checkout on a public
  HTTPS endpoint, with the signed `payment.captured` webhook processed exactly once.
- The external-payment account completed owner-recorded redemption and reconciled
  customer outstanding cash and owner cash principal from ₹100.00 to ₹0.00.
- Owner-configurable cash bonus percentage and minimum qualifying duration with a
  safe zero-percent default and versioned terms snapshotted at enrolment.
- Separate principal paid/outstanding, earned bonus, projected bonus, and redeemable
  cash amounts on customer and owner views.
- Eligibility-cutoff bonus calculation using `Decimal` and `ROUND_HALF_UP`; projected
  bonus remains outside actual liability and redemption.
- Immutable cash-redemption principal/bonus components with deterministic
  principal-first allocation and exact owner-liability reconciliation.
- Immutable audit events with stable actor labels, timestamps, reasons, targets,
  and outcome/change details for supported sensitive owner workflows.
- Audited plan editing that affects future enrolments without rewriting agreement
  snapshots; enrolment, redemption, and allocation retry now retain owner reasons.
- Immutable one-to-one redemption reversals that restore the matching entitlement,
  reopen fully redeemed accounts, and preserve the original settlement record.
- Owner-only audit log and a derived exception queue for paid-unallocated/failed
  allocations plus failed or mismatched Razorpay webhook reconciliation.
- Customer/owner printable HTML contribution acknowledgements with stable receipt
  references and captured metal-rate/allocation details where applicable.
- Lifetime customer scheme statements showing verified payments, allocations,
  redemptions, reversals, and current denomination-specific entitlement.
- Owner contribution and redemption CSV exports with separated INR/gold/silver
  fields and spreadsheet-formula neutralization.
- Strict namespaced production settings with bounded numeric/boolean parsing,
  signing-key fallback rotation, persistent database health checks, SMTP settings,
  secure cookie/header defaults, proxy trust opt-in, and timestamped stdout logging.
- Uncached liveness and PostgreSQL-readiness endpoints that expose the immutable
  application release without returning database error details.
- Deploy-only checks reject mock/unsupported providers, missing selected-provider
  credentials, non-delivering email, wildcard hosts, and insecure CSRF origins.
- A non-root production image with build-time static collection and bounded Gunicorn
  worker recycling/timeouts, plus PostgreSQL-backed CI, deploy-check, and image-build gates.
- Canonical rollout, backup/restore drill, rollback, TLS/HSTS, monitoring, and
  coordinated secret-rotation procedures.
- A detailed platform-neutral production runbook covering the deployment contract,
  environment, immutable-image promotion, staged rollout, smoke tests, capacity,
  alerts, provider incidents, recovery, rotations, and financial go-live gates.
- A Linode-specific deployment profile for `jaishrikrishnajewellery.com`: pinned
  Caddy TLS proxy, private/read-only Django service, restricted Docker capabilities,
  CA-verified Managed PostgreSQL, bounded local logs, and production environment template.
- The canonical runbook now preserves the exact Ubuntu/Docker/CA bootstrap procedure
  and the reviewed branch-to-PR/CI-to-immutable-image-to-Linode deployment, verification,
  configuration-reload, and rollback workflow for future releases.
- Public About, Contact, Terms, Privacy, Cancellation and Refund, and showroom-only
  Shipping and Delivery pages expose consistent business identity and support details.
- Public plans and INR pricing come from structured `SchemePlan` terms only when a
  plan is active and explicitly marked `publicly_listed`; all existing plans migrate
  as private, and publishing changes are included in the immutable plan-change audit.
- Public policy wording distinguishes voluntary early discontinuation from
  duplicate/erroneous payment refunds and remains consistent with eligible CASH,
  GOLD, SILVER, and jewellery-purchase settlement paths.

## In progress

- Environment-specific production proof: isolated database restoration, stable
  domain/TLS/proxy validation, real email delivery, external alert routing, and
  coordinated secret-rotation drills.
- The Ubuntu 24.04 Compute Instance and three-node Managed PostgreSQL 16 cluster are
  provisioned in one region. Database/Cloud Firewall access controls and the database
  CA are in place, SSH access is verified, Docker is installed, and the owned domain
  returns liveness and PostgreSQL readiness `200` through Caddy-managed HTTPS;
  production email, external alerts, and provider validation remain.

## Known limitations

- GoldAPI has deterministic boundary coverage but still requires private-credential
  verification before production deployment.
- Razorpay is verified only in Test Mode. Live keys remain rejected until production
  payment, reconciliation, refund, dispute, monitoring, and secret-rotation procedures exist.
- Temporary quick-tunnel URLs have no uptime guarantee; deployment requires a stable,
  owned HTTPS endpoint and synchronized webhook-secret configuration.
- Repository health checks and logging now exist, but an actual production platform
  must still retain logs and exercise uptime/error/financial-exception alerts.
- Backup and rollback procedures are documented, but the provisioned managed cluster
  has not yet completed an evidenced isolated restoration/reconciliation drill.
- The application records redemptions but does not execute payouts, move inventory,
  create invoices, or convert metal to cash.
- Manual payment/rate correction, voids, refunds/disputes, dual approval, broader
  provider reconciliation, and automated alerts/retries remain.
- Public policy pages require business/legal approval before they are treated as
  binding terms. The exact plan-specific 6+ month wastage/value-addition discount
  schedule is not modeled and no numeric partial discount is advertised.
- Documents are on-demand HTML acknowledgements, not archived statutory tax invoices;
  PDF generation, signatures, tax identity, delivery/reissue logs, and date-filtered
  exports remain future production/legal work.
- Cash bonus has one percentage policy with no caps, tiers, discretionary approval,
  forfeiture, tax treatment, or expected-future-contribution projection.
- Bonus liability reads are calculated per cash account; aggregate optimization is
  deferred until measured account volume requires it.
- Plan-specific early-discontinuation pricing, shared provider caching, payment-order
  expiry, eligibility reminders, public onboarding, and partial-settlement policy are
  not yet defined.
- The detailed, prioritized backlog and milestone-by-milestone limitation history
  are maintained in [Future work](FUTURE_WORK.md).

## Deferred

- See [Future work](FUTURE_WORK.md) for deployment gates and post-MVP operations.

## Verification

- PostgreSQL 16 migrations applied successfully.
- 144 tests pass, including public-policy route/link coverage, explicit active-plan
  publishing and INR pricing visibility, health/readiness failure sanitization, deploy-configuration
  gates, document access, receipt stability, unallocated disclosure, CSV
  denomination/formula safety, audit immutability, exception classification,
  reversal reconciliation, cash-bonus boundaries/rounding, Razorpay failure handling,
  redemption precision, over-redemption protection,
  idempotency, partial/full closure, denomination separation, access control,
  PostgreSQL constraints, and all prior regressions.
- Migrations through `schemes.0008_auditevent_redemptionreversal` are applied to the
  current deployment. `schemes.0009_schemeplan_publicly_listed` is generated and
  regression-tested; it must be applied during the next release.
- Migration drift check reports no changes.
- Django system check and migration drift check pass.
- Production deployment checks pass with a synthetic secure configuration and no
  issues; the real deployment must supply equivalent secrets, hosts, TLS, and email.
- Production image `jsk-savings:hardening-check` builds successfully, collects 137
  static files (403 post-processed), and is configured to run as user `app`.
- A disposable container smoke returned HTTP 200 from `/health/live/`, reported
  release `hardening-smoke`, and confirmed the running process user is `app`.
- The corrected `jsk-savings:deployment-guide-check` image builds successfully and a
  disposable liveness smoke returns `200` with the expected release; Gunicorn 25.3
  starts without attempting a control socket on the read-only application filesystem.
- GitHub Actions CI is defined with SHA-pinned checkout/setup actions, PostgreSQL 16,
  migrations, drift/system/deploy checks, the regression suite, static collection,
  and an independent production-image build.
- The Linode production Compose model passes `docker compose config --quiet`, and
  Caddy 2.11.4 validates the exact apex-domain and `www` redirect configuration.
- The deployed Linode application returns `200` from both liveness and PostgreSQL
  readiness over `https://jaishrikrishnajewellery.com`; the valid ACME contact and
  Caddy-managed certificate corrected the initial placeholder-contact failure.
- Live-server checkpoint passes for owner and customer login, UI-created plan/customer/CASH-GOLD-SILVER enrolments, three mock payments, customer entitlements, owner contribution visibility, and exact liability/activity deltas.
- Live GoldAPI HTTP behavior is verified at the adapter boundary with deterministic mocked responses; no real provider request was made because no API key is stored in the repository.
- Live-server recovery smoke passes across a rate-failure/server-restart/rate-restoration sequence: verified payment remains unallocated, owner retry creates exactly one 0.800000 g allocation, and all disposable records are removed.
- Milestone 7 live-HTTP smoke passes for owner forecast/detail views and customer redemption-eligible guidance; the database status remains `ACTIVE`, and all disposable records are removed.
- Milestone 8 authenticated request smoke passes with CSRF enforcement: an owner
  records partial cash and final jewellery settlement, the customer sees both
  records and no payment action, liabilities reconcile, and disposable data is removed.
- MVP Beta external smoke passes with private Razorpay Test Mode credentials: a ₹100
  payment is captured, one signed `payment.captured` webhook is processed, one cash
  entitlement is created, an owner completes the full redemption through a
  CSRF-protected form, and customer/owner outstanding cash reconciles to zero.
- Milestone 9 rollback-only authenticated smoke passes through owner plan creation and
  enrolment, customer mock payment, eligibility transition, and owner redemption:
  ₹100 principal earns ₹5, the immutable redemption stores both components, the
  account closes, and owner liability returns exactly to baseline.
- Milestone 10 rollback-only owner smoke passes through audited enrolment, ₹100 cash
  redemption, compensating reversal, restored ₹100 liability, reopened account, and
  owner audit/exception views; exactly three audit events were created and all tagged
  smoke records were rolled back.
- Milestone 11 rollback-only authenticated smoke passes for a gold mock payment,
  stable printable receipt, statement showing 0.080000 g gold, and both owner CSV
  exports; all tagged records were rolled back.

## Next recommended step

Review the new customer-facing policies, create a PR, pass required CI, deploy the
immutable image, apply migration `schemes.0009`, and explicitly publish at least one
reviewed active plan before submitting the URLs to Razorpay. Then retain the owned
DNS/TLS evidence and complete
`FW-PROD-001` through `FW-PROD-003`: a recorded database restore/reconciliation drill,
stable owned HTTPS plus alerts, real email delivery, and secret-rotation rehearsal.
Separately validate GoldAPI privately and define Razorpay live-mode reconciliation,
refund, and dispute operations before handling real customer funds. Follow the
[Production and deployment guide](PRODUCTION_DEPLOYMENT.md) and retain evidence for
each environment-specific gate.
