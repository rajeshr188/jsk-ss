# Project Status

## Current milestone

Cloudflare R2 media foundation — production smoke passed; operations proof pending

## Completed

- Lithium authentication, Bootstrap/crispy forms, WhiteNoise, and custom user preserved.
- PostgreSQL-only environment configuration and India time zone.
- Jai Sri Krishna Jewelley branding and canonical documentation.
- Bootstrap 5-only responsive interface modernization with a simplified owner
  navigation, wider financial data surfaces, consistent cards/forms/tables,
  refreshed public and authenticated journeys, and keyboard/reduced-motion
  accessibility improvements; no new frontend framework or dependency was added.
- Figma-principle refinement pass with WCAG-AA small-text contrast, structured
  financial form fieldsets, progressively disclosed owner records, consistent
  account-recovery and owner-list surfaces, explicit table-header semantics, and
  mobile customer contribution/redemption cards; gold-label, Bootstrap secondary-
  text, and warm-gradient homepage colors meet axe/WCAG AA normal-text contrast
  thresholds against their lightest-risk theme surfaces.
- Conversion-focused public homepage with a prospect-first plan/showroom journey,
  distinct existing-customer access, an explicit INR-to-locked-metal-to-jewellery
  visual redemption flow, concise gold/silver copy, local business details,
  BIS hallmark/HUID trust cues, embedded Bootstrap Icons, and one optimized,
  self-hosted Pexels jewellery photograph clearly labelled as illustrative; repeated
  plan/contact actions and pre-enrolment policy links remain prominent.
- Owner/customer roles, customer records, reusable plans, and snapshotted enrolments.
- Owner customer-management flow and isolated customer scheme view.
- Append-oriented contributions with pending/paid/paid-unallocated/failed states.
- Fixed/variable amount validation and once-per-month/flexible frequency rules.
- Debug-only mock payment adapter with verified, idempotent confirmation.
- Customer cash balance/history and owner contribution visibility.
- Owner-published, append-only gold/silver Scheme Rates with fixed established purity,
  effective timestamps, optional notes, publication identity, and immutable audit records.
- Current-rate selection from the database with a 5% large-change confirmation safeguard.
- Scheme Rate locking before mock payment or Razorpay order creation; no rate means no
  metal payment/order, while cash contributions remain available.
- Immutable Scheme Rates and one six-decimal metal allocation per paid contribution.
- Customer gold/silver gram balances and historical locked-rate visibility.
- Owner dashboard with separately reconciled cash principal, gold grams, and silver grams.
- Current gold/silver Scheme Rates and separately rounded indicative INR exposures.
- India-local successful-contribution counts for today and the current calendar month.
- MVP Alpha live workflow verified across owner setup, all three savings modes, customer payments and entitlements, and owner liability reconciliation.
- External metal-rate providers, API credentials, provider settings, quote caching, and
  provider-failure allocation paths removed from the authoritative workflow.
- Verified metal payments are durably `PAID_UNALLOCATED` until allocation succeeds,
  so exceptions or process interruption remain visible; owner retry is idempotent
  and reuses the original locked Scheme Rate.
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
- Deploy-only checks reject mock/unsupported payment gateways, missing selected-payment
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
- The runbook also records post-merge local checkout hygiene: distinguish deployed
  SHA from branch names, preserve unrelated work, fast-forward local `main`, retire
  merged branches only after stabilization, and start each change on a fresh branch.
- The Linode observability profile now defines privacy-reduced structured Caddy access
  logs, Better Stack off-host retention and independent live/ready/5xx checks, Linode
  capacity/backup notifications, and an aggregate financial-exception command driven
  by a hardened five-minute systemd heartbeat timer.
- Public About, Contact, Terms, Privacy, Cancellation and Refund, and showroom-only
  Shipping and Delivery pages expose consistent business identity and support details.
- Public plans and INR pricing come from structured `SchemePlan` terms only when a
  plan is active and explicitly marked `publicly_listed`; all existing plans migrate
  as private, and publishing changes are included in the immutable plan-change audit.
- Customer-facing navigation and page headings call these offers "Savings plans"
  rather than "Plans & pricing"; displayed INR values are identified as contribution
  amounts, while the stable `/plans/` route and internal URL name remain unchanged.
- Public product and policy wording consistently describes the currently marketed
  gold/silver journey, distinguishes voluntary early discontinuation from payment-
  error refunds, and explains showroom-only metal or jewellery fulfilment.
- A public Our Story page credits owner Dilip Kumar and developer Rajesh Rathod H,
  explains their family partnership, and uses accessible monogram portraits until
  approved photographs are supplied. Its route is retained for later publication,
  but links to it are currently hidden from public navigation and page calls to action.
- Wagtail feasibility is accepted in ADR-0004 as a bounded catalogue CMS. Wagtail
  7.4.3 now runs additively with PostgreSQL search, `accounts.CustomUser`, `/cms/`,
  the existing `/admin/` and `/scheme/` routes, and unchanged Bootstrap 5 public
  pages. CMS entry requires the explicit `wagtailadmin.access_admin` permission;
  customer and application-owner roles alone do not grant it.
- The `FW-MEDIA-001` repository foundation uses environment-selected
  `django-storages` R2 storage while retaining WhiteNoise for static files. Wagtail
  originals and documents use short-lived signed S3 URLs; generated image renditions
  use a separate public custom-domain storage alias. Production checks reject local
  media, `r2.dev`, missing owned media domains, and non-view document serving. A
  no-residue command exercises real upload, read, rendition, and cleanup behavior.
- The isolated non-production R2 smoke passed on 2026-08-24: Django uploaded and read
  the original, generated and read a Wagtail rendition, and removed the temporary
  database and object-storage records without printing credentials or signed URLs.
- The complete Linode DNS record set was reproduced in Cloudflare, including the
  initially missed GoDaddy and Postmark DKIM records. Authority changed to Cloudflare
  without a stale DNSSEC delegation; both authoritative servers agree, and apex,
  `www`, live, and ready HTTPS checks return `200` while web and mail records remain
  DNS-only during stabilization.

## In progress

- The Bootstrap 5 UI modernization is merged into `main` at `24ed76d`; production
  promotion remains separate from the Wagtail foundation work.
- `FW-CMS-002` is complete locally. `FW-MEDIA-001` is implemented and tested in the
  repository, and its non-production and production R2 smokes have passed. Its
  remaining external exit criteria are cache verification, mail-after-DNS-cutover
  confirmation, token rotation, monitoring, and recovery evidence. Catalogue models
  and production promotion remain blocked until that operational proof is retained.
- The first production-bucket smoke correctly failed because the R2 attachment used
  the apex instead of the intended media hostname. The attachment was corrected to
  `media.jaishrikrishnajewellery.com`; DNS/TLS, public rendition routing, `403` WAF
  protection for originals/documents, upload, read, rendition, and cleanup all passed
  on 2026-08-24. Apex, `www`, live, and ready remained healthy. Cleanup continues
  independently after individual storage failures and reports incomplete cleanup
  without identifiers.
- Environment-specific production proof: isolated database restoration, real email
  delivery, external alert routing/exercises, and coordinated secret-rotation drills.
  The stable owned domain/TLS/proxy path and repository observability foundation are
  operational; Better Stack and Linode alert activation still require account-side
  configuration and retained test evidence.
- The Ubuntu 24.04 Compute Instance and three-node Managed PostgreSQL 16 cluster are
  provisioned in one region. Database/Cloud Firewall access controls and the database
  CA are in place, SSH access is verified, Docker is installed, and the owned domain
  returns liveness and PostgreSQL readiness `200` through Caddy-managed HTTPS;
  production email, external alerts, and Razorpay live-mode readiness remain.
- Production release `2f87e042a72cb5c95222d619bb1ca8edbe7831e6` is healthy with
  migration `schemes.0010_manual_scheme_rates` applied, zero reported financial
  exceptions, and successful live, ready, static, and public-page checks. All public
  compliance routes return `200`, and an owner-reviewed active plan is publicly listed.

## Known limitations

- Quote expiry is deferred: a pending contribution retains its locked Scheme Rate until
  it is paid or failed. Add expiry only with a reviewed payment-order lifecycle design.
- Razorpay is verified only in Test Mode. Live keys remain rejected until production
  payment, reconciliation, refund, dispute, monitoring, and secret-rotation procedures exist.
- Public prospect and policy pages now market only gold/silver jewellery purchase
  plans, but owner workflows and the database still permit CASH accounts, bonus rules,
  maturity cash settlement, and Razorpay test payments. Copy alone does not enforce
  that product boundary. Before Razorpay submission or Live Mode, decide whether CASH
  is legacy-only, enforce that decision in enrolment/payment services, and obtain
  qualified legal review and written provider approval for the permitted flow.
- Temporary quick-tunnel URLs have no uptime guarantee; deployment requires a stable,
  owned HTTPS endpoint and synchronized webhook-secret configuration.
- Repository health checks, privacy-reduced edge access logs, and a financial-
  exception heartbeat now exist, but Better Stack/Linode must still be configured to
  retain logs and exercise uptime, 5xx, capacity, backup, TLS, and financial alerts.
- Backup and rollback procedures are documented, but the provisioned managed cluster
  has not yet completed an evidenced isolated restoration/reconciliation drill.
- The application records redemptions but does not execute payouts, move inventory,
  create invoices, or convert metal to cash.
- Manual payment correction, voids, refunds/disputes, dual approval, broader payment
  reconciliation, and automated alerts/retries remain.
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
- Plan-specific early-discontinuation pricing, payment-order
  expiry, eligibility reminders, public onboarding, and partial-settlement policy are
  not yet defined.
- The CMS and R2 configuration foundations exist locally, but there is no catalogue
  model and no real Cloudflare bucket has yet passed the documented smoke, access,
  rotation, monitoring, and recovery exercises. Local filesystem media is
  development-only; production's read-only container cannot persist uploads, so this
  branch must not be promoted and real catalogue media must not yet be accepted.
- The detailed, prioritized backlog and milestone-by-milestone limitation history
  are maintained in [Future work](FUTURE_WORK.md).

## Deferred

- See [Future work](FUTURE_WORK.md) for deployment gates and post-MVP operations.

## Verification

- Wagtail 7.4.3 and Django 6.0.4 pass system checks, production-shaped deploy checks,
  static collection, and an applied-migration check. Wagtail/taggit migrations are
  applied to local PostgreSQL only; production has not received them.
- PostgreSQL 16 migrations applied successfully.
- 160 tests pass, including R2 configuration and signed/private-original versus
  public-rendition URL isolation, no-residue upload/read/rendition/cleanup behavior,
  production media deployment gates, explicit Wagtail permission and route-precedence checks,
  public INR-contribution/metal-to-jewellery copy coverage,
  owner-only Scheme Rate publication, large-change
  confirmation, no-rate payment blocking, pre-order locking, rate-change race
  behavior, durable verified-payment/allocation transition, production-shaped
  `0009` to `0010` history backfill and blocker checks, historical immutability,
  aggregate financial-exception monitoring with
  redacted output, public-policy route/link coverage, explicit active-plan
  publishing and INR pricing visibility, health/readiness failure sanitization,
  deploy-configuration gates, document access, receipt stability, unallocated disclosure, CSV
  denomination/formula safety, audit immutability, exception classification,
  reversal reconciliation, cash-bonus boundaries/rounding, Razorpay failure handling,
  redemption precision, over-redemption protection,
  idempotency, partial/full closure, denomination separation, access control,
  PostgreSQL constraints, and all prior regressions.
- Migrations through `schemes.0010_manual_scheme_rates` are applied to the current
  production deployment and local development database.
- Migration drift check reports no changes.
- Django system check and migration drift check pass.
- The rendered anonymous homepage passes Deque axe-core 4.13's WCAG AA
  `color-contrast` rule with zero violations; the referenced axe 4.12 rule uses
  the same 4.5:1 normal-text and 3:1 qualifying-large-text thresholds.
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
  Caddy 2.11.4 validates the exact apex-domain, `www` redirect, masked JSON access
  log, and release-label configuration. The financial heartbeat shell script passes
  a non-executing syntax check.
- The deployed Linode application returns `200` from both liveness and PostgreSQL
  readiness over `https://jaishrikrishnajewellery.com`; the valid ACME contact and
  Caddy-managed certificate corrected the initial placeholder-contact failure.
- Live-server checkpoint passes for owner and customer login, UI-created plan/customer/CASH-GOLD-SILVER enrolments, three mock payments, customer entitlements, owner contribution visibility, and exact liability/activity deltas.
- Manual Scheme Rate regressions verify owner-only gold/silver publication, validation,
  append-only history, latest-applicable selection, large-change confirmation,
  GOLD/SILVER no-rate payment blocking with unaffected CASH orders, pre-order locking,
  old-lock/new-rate race behavior, legacy history preservation, and deployment blockers.
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

Test inbound/outbound mail after the DNS cutover, verify the rendition cache policy,
then perform the documented R2 token-rotation and media-recovery exercises while
retaining Cloudflare metrics and recovery evidence. Do not create catalogue models
or promote the CMS foundation to production until those durable-media behaviors are
proven.

Complete the CASH product-boundary decision and enforce it in enrolment and payment
services before submitting the public website and policy URLs to Razorpay. Keep live
keys disabled until legal/provider review and live-mode operating procedures are
approved. Retain the owned
DNS/TLS and release evidence and complete
`FW-PROD-001` through `FW-PROD-003`: a recorded database restore/reconciliation drill,
stable owned HTTPS plus alerts, real email delivery, and secret-rotation rehearsal.
Define Razorpay live-mode reconciliation, refund, and dispute operations before
handling real customer funds. Follow the
[Production and deployment guide](PRODUCTION_DEPLOYMENT.md) and retain evidence for
each environment-specific gate.
