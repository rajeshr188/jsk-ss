# Project Status

## Current milestone

`FW-PROD-006` completed production acceptance on 2026-09-04 in release
`c889ee6906a8bddd4c7852955025efe42ffa5752`: the Linode pulled and deployed the exact
public-GHCR digest produced and vulnerability-scanned by protected `main`, with no
serving-host build. `FW-ELIG-002` is operational on the same release with migration
`schemes.0019_scheme_reminders` applied and its hardened systemd execution boundary
passing. The first genuine reminder-specific Postmark acceptance remains an
operational observation because the controlled production run had zero candidates;
it does not block beginning fail-closed `FW-AUTH-002` design.

## Completed

- Lithium authentication, Bootstrap/crispy forms, WhiteNoise, and custom user preserved.
- PostgreSQL-only environment configuration and India time zone.
- Jai Sri Krishna Jewellery branding and canonical documentation.
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
- Owner-only, one-time customer password-setup invitations with digest-only secrets,
  bounded expiry, safe resend/supersession, delivery state, and explicit separation
  between login activation and financial enrolment. Public signup remains closed.
- Production release `f9081c1a52a3ce3dc99e1d816cce9846a5b31f92` corrected the
  token-page CSRF/referrer policy; controlled invitation password setup and subsequent
  forgot-password reset both passed on 2026-08-26.
- Direct untracked authentication links, non-cacheable token responses that disclose
  only their origin and not the secret-bearing path,
  Caddy token-path log exclusion, removal of the redundant Gunicorn full-path access
  log, Django error/warning path redaction, and case-insensitive login-email
  uniqueness with a stop-before-migration integrity check.
- Append-oriented contributions with pending/paid/paid-unallocated/failed states.
- Fixed/variable amount validation and once-per-month/flexible frequency rules.
- Debug-only mock payment adapter with verified, idempotent confirmation.
- Customer cash balance/history and owner contribution visibility.
- Owner-published, append-only, exact-grade Scheme Rates with immutable fineness,
  effective timestamps, optional notes, publication identity, and immutable audit records.
- Immutable reference grades `GOLD_22K_916`, `GOLD_24K_9999`, and `SILVER_999`,
  plan-to-grade offerings, exact-grade enrolment contracts, and no cross-grade rate
  derivation or fallback.
- Additive legacy-history mapping from generic Gold to `GOLD_24K_9999` and generic
  Silver to `SILVER_999`, with no rewriting or conversion of stored grams.
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
- Configurable email reminders for upcoming exact-calendar eligibility, owner-only
  paid-unallocated exceptions, and completed redemptions, with deterministic per-
  recipient idempotency, immutable backend-acceptance/failure attempts, bounded
  retries, Postmark tracking disabled, aggregate cron-safe command output, and an
  owner-only delivery-evidence view. The production execution boundary is deployed;
  the first naturally occurring provider acceptance remains to be observed under
  `FW-ELIG-002`.
- Future public-signup requirements documented under `AUTH-*` domain rules.
- Razorpay test-mode order creation and customer Standard Checkout flow.
- Explicit fail-closed Razorpay `test`/`live` configuration: the declared mode must
  match the API key prefix, and missing, unknown, or mixed-mode settings are rejected.
- Mode-stamped Razorpay contributions and webhook events with database constraints,
  cross-mode callback/order/webhook isolation, historical Test backfill, mode-aware
  event uniqueness, owner/admin visibility, and reconciliation-export coverage.
- A no-secret `check_razorpay_live_readiness` activation gate that rejects pending
  contributions from another mode, missing historical labels, failed Live webhooks,
  and unsafe Live configuration before a web-service cutover.
- Mode-accurate customer checkout wording that explicitly distinguishes simulated
  Test payment from a real Live charge and never offers a cross-mode resume action.
- Browser callback verification using the local order ID, HMAC, and a captured-payment server lookup.
- Signed raw-body `payment.captured` webhooks with a unique event ledger and idempotent financial processing.
- Razorpay webhook recovery under ADR-0006: signed permanent mismatches become
  durable owner-review exceptions with HTTP 200, transient failures return a
  sanitized retryable 503, each delivery/recovery appends bounded evidence, and an
  owner can dry-run then apply only an exact mode-matched provider payment through
  the existing idempotent confirmation and locked-rate allocation services.
- Unique Razorpay order/payment identifiers and one resumable pending order for once-per-month accounts.
- Dry-run-first reconciliation for aged Razorpay orders, with mode-matched provider
  inspection, an explicit application-side `ABANDONED` status, retained order/rate
  references, immutable provider evidence, independent flexible-attempt handling,
  monthly replacement/resume behavior, and late-capture escalation through the
  financial-exception workflow. Razorpay provider orders are never described as
  cancelled because its Orders API exposes no cancellation operation.
- Shared callback/webhook confirmation services that create at most one cash or metal benefit.
- India-local, date-derived active/not-yet-eligible, redemption-eligible, and redeemed display states.
- Owner dashboard counts for eligible now and exclusive 1–30, 31–60, and 61–90-day forecast windows.
- Owner-only grouped eligibility review and customer-facing eligibility guidance without automatic account closure.
- Immutable, idempotent owner-recorded cash, metal, and jewellery-purchase redemptions.
- Partial/full settlement with denomination-specific outstanding balances and exact final account closure.
- Customer redemption history, owner redemption ledger, and liability reconciliation after settlement.
- External Razorpay Test Mode payment captured through Standard Checkout on a public
  HTTPS endpoint, with the signed `payment.captured` webhook processed exactly once.
- Razorpay Live Mode acceptance completed on release `5fa726b` with two real captured
  contributions (INR `150.00` and INR `200.00`), two processed signed
  `payment.captured` webhooks, and exactly one immutable gold allocation per payment
  (`0.008973` g and `0.012229` g). Two unused Live orders with no attempts or payments
  were reconciled against Razorpay and retired through the contribution service. The
  final state has zero pending Live contributions, `0.021202` g allocated from Live
  payments, `0.329272` g total outstanding gold, and zero financial exceptions.
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
- `FW-PROD-001` completed on 2026-08-27 with an isolated Linode Managed PostgreSQL
  newest-full-plus-incremental restore. The fork became ready in 15 minutes, retained
  every migration through `schemes.0011`, exactly matched the five-customer,
  six-account and denomination-specific liability baseline, passed authentication and
  financial-exception checks, and left the original production release healthy. The
  restored cluster and temporary environment/CA files were removed after verification.
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
- Inbound and outbound GoDaddy-hosted mail both passed after the Cloudflare DNS
  cutover. The public-rendition cache rule is deployed, and a fresh production smoke
  proved its 24-hour public cache header and a real Cloudflare cache `HIT` while WAF
  and cleanup behavior remained correct.
- The production R2 credential-rotation rehearsal passed on 2026-08-24: a new token
  scoped to the production bucket passed the complete smoke, the old token was
  deleted, and the new token passed again. A transient local DNS/TLS failure during a
  WAF probe recovered through bounded retries without weakening any access control.
- `FW-CATALOG-001` adds a bounded `catalog` application with one catalogue index,
  focused product pages, reusable category and marketing-collection snippets, ordered
  Wagtail image galleries with required alt text, revision-safe content, and an
  optional positive informational INR display price. The model and preview templates
  support product discovery and showroom enquiry only; they do not introduce
  inventory, carts, checkout, invoices, fulfilment, payments, or Scheme Rate coupling.
- `FW-CATALOG-002` adds an explicit, idempotent catalogue authorization bootstrap.
  It creates a draft catalogue root, dedicated media collection, subtree-scoped
  Catalogue Editors/Publishers/Administrators groups, collection-scoped image access,
  and a publisher approval workflow. Editors can prepare and submit drafts;
  publishers or catalogue administrators approve publication. Application roles do
  not grant group membership, non-staff users remain denied even if assigned by
  mistake, and every workflow, publish, and unpublish action stays in Wagtail's
  actor-attributed audit history.
- `FW-CATALOG-003` provides accessible Bootstrap 5 catalogue and product pages with
  live-only search and category/collection filters, featured-first 12-item pagination,
  responsive Wagtail/R2 renditions, image-free and no-result states, canonical/Open
  Graph/JSON-LD metadata, and explicit phone, email, and Vellore-showroom enquiry
  paths. Global navigation remains default-off for safe rollout and appears only when
  the flag is enabled and the catalogue root is independently live/public.
- `FW-CATALOG-004` completed production rollout on 2026-08-25. Release `2311ccf`
  applied the additive Wagtail, taggit, and `catalog.0001` migrations; reconciled and
  validated the bounded catalogue authorization; passed the production R2
  upload/read/rendition/cleanup smoke; assigned explicit staff publishing access;
  published reviewed catalogue content; passed direct mobile/desktop browser checks;
  and enabled public catalogue navigation only after those gates succeeded.
- The accepted long-term shape is hybrid: Wagtail owns catalogue/editorial content,
  while Django and the `SchemePlan` domain remain authoritative for savings-plan and
  financial behavior. Future Scheme Plan images or richer marketing copy may be
  Wagtail-managed presentation linked to a plan, but must not duplicate or control
  contribution, duration, metal, bonus, eligibility, publication, or enrolment terms.
- `FW-CMS-003` completed production rollout on 2026-08-25 in release
  `71f3e9cea5376cfb0a362ee13510a1162015649f`. The additive `pages.0001_initial`
  migration and editorial authorization configuration completed; About and Our Story
  remain bounded Wagtail editorial types, and Our Story stays outside global navigation.
- `FW-PRODUCT-001` completed production rollout on 2026-08-25 in release
  `93ba4273c976cd427d86a79a58454e2b7e58c55f`. The release used the recorded
  2026-08-24 12:00 PM IST managed recovery point, passed deployment and migration-plan
  gates with no schema changes, and preserved the one empty historical CASH account.
  Production now rejects new CASH enrolments and contributions, exposes only gold and
  silver during enrolment, retains the historical account and statement without a Pay
  action, and returns `403` from its direct contribution route. Post-release live and
  ready checks returned `200`; the CASH boundary and financial-exception checks both
  reported `status=ok` with zero CASH exposure and zero exceptions.
- `FW-PAY-004` completed production rollout and acceptance on 2026-08-31 in release
  `e027b9ae1550c314584c551eb3da31d5529ea544`. Production retains the reviewed
  seven-day Asia/Kolkata schedule. Current-day Gold and Silver Scheme Rates were
  published, the schedule was enabled with an audit reason, and its exact closing and
  reopening boundary worked as expected after the manual pause/resume exercise.
- Grade-specific metal rates completed production rollout and acceptance on
  2026-09-03 in release `df5a7506bfa3c5b255faf284d3f90ef2ac7d7b28`.
  The controlled migration applied `schemes.0015` and `schemes.0016` from a
  recorded 2026-09-03 11:00 AM IST PostgreSQL recovery point after proving zero
  pending Razorpay orders. Legacy Gold remained `GOLD_24K_9999` at the unchanged
  `0.329272` g baseline, new enrolment moved to independently priced
  `GOLD_22K_916`, and exact-grade integrity, financial-exception, Razorpay Live
  readiness, health, and readiness gates all passed. A controlled INR `150.00`
  Live contribution locked the `GOLD_22K_916` rate of INR `14667.0000`/g,
  processed one signed `payment.captured` webhook, and created exactly one
  `GOLD_22K_916` allocation of `0.010227` g with no financial exception.
- `FW-PAY-005` completed production rollout and acceptance on 2026-09-03 in release
  `51c931a9de5b27349f781cd44670c41307479dfa`. From the recorded 2026-09-03
  1:00 PM IST PostgreSQL recovery point, the controlled global pause covered every
  offered grade, provider reconciliation found zero candidates, and migration
  `schemes.0017_contribution_checkout_expiry` applied as the only planned operation.
  The candidate reported the configured 10-minute deadline, zero pending Razorpay
  contributions, zero pending rows missing expiry, and green payment-operations,
  financial-exception, Live-readiness, exact-grade, container-health, liveness, and
  readiness gates before a separately audited reopening of all three grades.
- `FW-PAY-006` completed production rollout and acceptance on 2026-09-03 in release
  `315f836ac0717fbaaf2d8d90268471ac1670e5b1`. From the recorded 2026-09-03
  4:00 PM IST PostgreSQL recovery point, migration
  `schemes.0018_in_store_cash_contributions` applied as the only planned operation
  after every grade was paused and the pending Razorpay count was zero. The feature
  remained disabled through migration, integrity, health, and owner-path review,
  then was enabled before a separately audited reopening. The first legitimate
  showroom receipt, `CASH-150E7205`, recorded INR `1000.00` on contribution `15`,
  locked the `GOLD_22K_916` rate of INR `14667.0000`/g, and allocated exactly
  `0.068180` g. The immutable receipt, one audit event, statement, owner ledger, and
  CSV reconciled; cash, financial-exception, exact-grade, and Razorpay Live-readiness
  checks remained green.
- `FW-ELIG-001` completed production rollout and acceptance on 2026-09-04 in release
  `50bfd3673c57dff51b46238094bcad899a36c8fa`. Its no-op migration plan, exact-calendar
  production probes, public Terms wording, unchanged eight-account financial
  baseline, and all financial/provider gates passed. The on-host build caused a
  recoverable OOM origin outage before cutover on the 1 GiB Compute Instance; no
  environment, release, schema, or database mutation had occurred. Reboot restored
  the old release, and the retained candidate was then deployed sequentially without
  rebuilding. Future serving-host builds are prohibited under `FW-PROD-006`.

## In progress

- `FW-ELIG-002` awaits only the first naturally occurring reminder-specific Postmark
  acceptance and matching owner delivery record. Its deployed zero-candidate run is
  correct evidence that no message is invented merely to satisfy a rollout smoke.
- `FW-PAY-003` retains two no-mutation recovery evidence exercises: an isolated
  Test-mode review/dry-run/apply case and an idempotent replay of an already-processed
  Live capture. External alerting and coordinated secret rotation remain separately
  deferred under `FW-PROD-002` and `FW-PROD-003`.
- `FW-MEDIA-002` tracks the accepted backup/recovery and usage-monitoring deferral.
  It does not block catalogue use, but approved source photographs must
  remain outside R2 until an isolated backup target and restore proof exist.
- Environment-specific production proof: isolated database restoration, external
  alert routing/exercises, and coordinated secret-rotation drills. Postmark SMTP and
  real password-reset delivery passed on 2026-08-26, production Site 1 now uses
  `jaishrikrishnajewellery.com`, and direct invitation/password-reset credential setup
  passed after the CSRF-policy hotfix. The owner deferred SMTP token rotation. The stable owned domain/TLS/proxy
  path and repository observability foundation are operational; Better Stack and
  Linode alert activation still require account-side configuration and retained test
  evidence.
- The Ubuntu 24.04 Compute Instance and three-node Managed PostgreSQL 16 cluster are
  provisioned in one region. Database/Cloud Firewall access controls and the database
  CA are in place, SSH access is verified, Docker is installed, and the owned domain
  returns liveness and PostgreSQL readiness `200` through Caddy-managed HTTPS;
  paid external alert exercises remain deferred.
- Production release `50bfd3673c57dff51b46238094bcad899a36c8fa` is healthy with
  migrations through `schemes.0018_in_store_cash_contributions`,
  `catalog.0001_initial`, `pages.0001_initial`,
  and `accounts.0003_customerinvitation_and_more`
  applied, zero reported financial exceptions, successful live/ready checks, valid
  catalogue authorization, working R2 media, published reviewed products, and public
  Jewellery links in the primary and footer navigation. Its production metal-only
  boundary, payment-operations manual pause/resume, and audited in-store cash receipt
  path passed owner/customer smoke.

## Known limitations

- The application intentionally does not derive one grade's Scheme Rate from another.
  Every offered grade needs its own owner-published current rate; that fail-closed
  behavior can temporarily block contributions for only the missing grade.
- Three-decimal customer gram values are rounded display values, not a reduction in
  accounting precision. Exact settlement entry and all authoritative quantities
  remain six-decimal; customer wording must not imply the displayed value is the
  complete source record.
- Razorpay exposes no order-cancellation operation. A reconciled `ABANDONED`
  contribution therefore retains its locked Scheme Rate and provider reference for
  evidence; a replacement locks the then-current rate, while any late capture is a
  financial exception requiring manual provider reconciliation and refund handling.
- Public prospect and policy pages market only gold/silver jewellery purchase plans.
  Production enforces that boundary for new enrolments and contributions while
  preserving the one empty historical CASH record. Qualified legal, accounting, and
  provider review of the marketed flow still remains necessary.
- Temporary quick-tunnel URLs have no uptime guarantee; deployment requires a stable,
  owned HTTPS endpoint and synchronized webhook-secret configuration.
- Repository health checks, privacy-reduced edge access logs, and a financial-
  exception heartbeat now exist, but Better Stack/Linode must still be configured to
  retain logs and exercise uptime, 5xx, capacity, backup, TLS, and financial alerts.
- The application records redemptions but does not execute payouts, move inventory,
  create invoices, or convert metal to cash.
- Generic online-payment correction, voids, refunds/disputes, dual approval, provider
  settlement import, and automated retries remain. In-store cash bookkeeping errors
  now have a bounded append-only reversal, but this is not a refund. The Live runbook permits only a
  tightly bounded manual Dashboard refund for a captured payment that created no
  local entitlement; any credited-payment refund or chargeback remains an incident.
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
- Plan-specific early-discontinuation pricing, open public self-registration, and
  partial-settlement policy are not yet defined. Email reminders are implemented but
  production rollout remains pending; SMS/WhatsApp, inbox-delivery/read proof,
  automatic multi-day catch-up, and end-to-end exactly-once SMTP delivery are not
  claimed. Owner-invitation onboarding is deployed; public self-registration remains
  intentionally closed.
- The production catalogue is active and its deployment, authorization, content,
  browser, and R2 smoke gates pass. There is still no isolated media backup/restore
  proof. Retain approved source photographs outside R2; production must not rely on
  R2 as their only copy. This accepted limitation remains `FW-MEDIA-002`.
- The detailed, prioritized backlog and milestone-by-milestone limitation history
  are maintained in [Future work](FUTURE_WORK.md).

## Deferred

- See [Future work](FUTURE_WORK.md) for deployment gates and post-MVP operations.

## Verification

- Wagtail 7.4.3 and Django 6.0.4 pass system checks, production-shaped deploy checks,
  static collection, and an applied-migration check. Wagtail, taggit, and catalogue
  migrations are applied to production PostgreSQL.
- Local and production PostgreSQL 16 migrations are applied through
  `schemes.0019_scheme_reminders`.
- 294 tests pass, including exact-calendar eligibility month-end clamping,
  weekend/calendar-marker non-adjustment, exact-day activation without early grace,
  non-expiring eligibility, calendar-day forecast distance, in-store cash
  preview/confirmation, owner authorization,
  payment-control and pending-Razorpay blocking, exact-rate locking, idempotency,
  durable allocation, bounded append-only correction, active-balance removal, daily
  reconciliation, receipt/statement visibility, and provider-channel migration,
  plus Razorpay Checkout expiry/backfill, expired-resume
  blocking, capture-after-expiry confirmation, exact 22K/24K rate separation,
  six-decimal allocation,
  immutable enrolment grade, legacy old-schema preflight, history mapping, default
  plan offerings, Razorpay webhook response classification, append-only
  processing-attempt evidence, provider-backed owner dry-run/apply recovery,
  mismatch/abandoned safeguards, recovery authorization and idempotency,
  payment-operations schedule/manual/kill-switch precedence,
  owner authorization and immutable before/after audit, blocked new order/Checkout
  behavior, uninterrupted callback/webhook confirmation and locked-rate allocation,
  the no-secret deployment check, Razorpay Live/Test configuration and history migration,
  cross-mode order/callback/webhook isolation, Live checkout disclosure, readiness
  blocking, mode-aware reconciliation export, the production metal-only boundary
  and CASH preflight,
  public catalogue search/category/collection filtering,
  bounded pagination, responsive renditions, canonical/Open Graph/JSON-LD metadata,
  accessible discovery and empty states, rollout-gated navigation, direct draft/live
  visibility, catalogue authorization drift repair, exact role/media scope, editor
  submission, publisher approval, publish/unpublish audit history, hierarchy,
  validation, case-insensitive uniqueness, preview, revision, gallery and rendition
  coverage; R2 configuration and signed/private-original versus
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
  PostgreSQL constraints, exact-date reminder candidate selection, audience and
  recipient safety, dry-run non-mutation, accepted-message idempotency, sanitized
  bounded retry evidence, fail-closed disablement, record immutability, and owner-
  only delivery review, plus all prior regressions.
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
- GitHub Actions CI is defined with SHA-pinned checkout, Node-24-compatible Docker,
  and scanner actions, PostgreSQL 16, migrations, drift/system/deploy checks, the
  294-test regression suite, static collection, unprivileged review-image builds,
  and a GHCR publisher restricted to protected `main`, with an immutable digest
  output. Actionlint 1.7.12 validates
  the workflow locally. The first protected-`main` run `33848413888` built merge
  `e78c2b20f013298186b7c742a18ba4d99658d164`, passed the published-digest critical-
  vulnerability gate, and produced
  `ghcr.io/rajeshr188/jsk-ss@sha256:9778089354d7110c8ea04f8ba2d8b4f6098e7d771e24329d0aeac441ae8faf3d`.
  The publisher now targets the repository-linked public `jsk-savings` package. Main
  run `33850511585` built merge `db577e19d015615972347f3546247a4b32df0369`,
  passed the published-digest critical-vulnerability gate, and produced
  `ghcr.io/rajeshr188/jsk-savings@sha256:30df12ac108ce90504c9c33e18e79d2c1c3d304e77e2d8cc9f64339bd5c86c54`.
  On 2026-09-04 the Linode pulled and inspected that digest with an empty temporary
  Docker configuration, proving anonymous access; production remained healthy and
  unchanged on release `50bfd3673c57dff51b46238094bcad899a36c8fa`.
  PR `#41` then merged the public-GHCR boundary as
  `b3d94c9deed8ebd6c78ed096d541620057535093`; protected-`main` run `33851821679`
  passed and published
  `ghcr.io/rajeshr188/jsk-savings@sha256:5dbd8de9ad5493c2c87de08e244e1350c6f774a5ba335996c3f65e3816b8ae61`.
  PR `#42` merged FW-ELIG-002 as
  `94cf3927a7138cf735da733c6ae68a8cce785cff`; protected-`main` run
  `33862547971` passed the 293-test, deploy, static, publish, and critical-
  vulnerability gates and produced
  `ghcr.io/rajeshr188/jsk-savings@sha256:8270e175b9f4789dc12f83b9b41f504b0b3dcd5814a1b82f904aa61116623a7e`.
  PR `#43` merged the reminder service hotfix as
  `c889ee6906a8bddd4c7852955025efe42ffa5752`; protected-`main` run
  `33865158341` passed the 294-test, deploy, static, publish, and critical-
  vulnerability gates and produced
  `ghcr.io/rajeshr188/jsk-savings@sha256:88eea68169da2ea04f9f104358ecb69ec929989b15f5e447825ab0f0bd806c33`.
- The Linode production Compose model passes `docker compose config --quiet`, and
  Caddy 2.11.4 validates the exact apex-domain, `www` redirect, masked JSON access
  log, and release-label configuration. The financial heartbeat shell script passes
  a non-executing syntax check.
- The deployed Linode application returns `200` from both liveness and PostgreSQL
  readiness over `https://jaishrikrishnajewellery.com`; the valid ACME contact and
  Caddy-managed certificate corrected the initial placeholder-contact failure.
- Production release `93ba4273c976cd427d86a79a58454e2b7e58c55f` passed immutable
  image identity, no-op migration, live/readiness, CASH-boundary, financial-exception,
  log review, and manual metal-only UI checks on 2026-08-25. The retained CASH account
  has no pending or verified payments, INR liability, redemption, or enabled Pay path.
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

Record this production evidence through protected `main`, then start `FW-AUTH-002`
on a fresh feature branch. First define the registration, verification, consent,
duplicate-identity, abuse-control, awaiting-owner-approval, rejection, and audit
contract. Public signup must remain disabled by default, must never create a
`SchemeAccount`, and must not grant payment access. Keep the first genuine
`FW-ELIG-002` delivery observation, `FW-PAY-003`, and the accepted
`FW-PROD-002`/`FW-PROD-003` budget deferrals separate.
