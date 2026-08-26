# Future Work Register

This document converts known MVP limitations into explicit follow-up work. Items
here are not implemented behavior and do not relax the financial invariants in
[Domain rules](DOMAIN_RULES.md).

## MVP Beta deployment gate

- **FW-BETA-001 — External Razorpay test journey (completed 2026-08-18):** Enrolment
  through redemption was exercised with a captured Razorpay Test Mode payment and a
  signed `payment.captured` webhook delivered to a public HTTPS endpoint.
- **FW-BETA-002 — Live GoldAPI smoke (superseded by ADR-0003):** External rates were
  removed from the authoritative allocation workflow. No provider smoke is required.
- **FW-BETA-003 — Production operations baseline (completed 2026-08-18):** The
  repository now defines secret rotation, PostgreSQL backup/restore drills, HTTPS
  and HSTS ownership, health/readiness checks, logging/monitoring responsibilities,
  and deployment rollback procedures. The environment-specific exercises below
  remain release gates before handling real customer funds.

## Production rollout

- **FW-PROD-001 — Backup recovery proof (Linode procedure prepared):** Linode
  Managed PostgreSQL provides daily retained backups and forked-cluster restoration;
  complete and record the actual isolated restore with denomination-specific
  liability reconciliation after the cluster exists.
- **FW-PROD-002 — Observability foundation implemented; activation remains:** Caddy
  serves the owned domain with automatic HTTPS, verified proxy trust, masked
  structured access logs, and release labels. The repository includes an aggregate
  financial-exception check plus a five-minute external-heartbeat systemd timer, and
  the runbook selects Better Stack for external checks/log retention and Linode for
  capacity/backup events. Configure the two provider accounts and retain exercised
  evidence for 5xx/readiness, failed webhooks, allocation exceptions, database
  capacity, certificate renewal, backup failure, escalation, and retention before
  marking this item complete.
- **FW-PROD-003 — Delivery verified; rotations remain:** Postmark approved the
  account and a real password-reset message reached the controlled Gmail mailbox on
  2026-08-26. Correct the production Django Site identity from `example.com`, deploy
  and verify direct untracked authentication links, then retain evidence. The owner
  explicitly deferred the SMTP token-rotation rehearsal; Django, database, SMTP,
  Razorpay API, and webhook rotation drills therefore remain open.
- **FW-PROD-004 — Image-build confirmation (completed locally 2026-08-18):** The
  hardened image builds with production static assets and runs as the unprivileged
  `app` user. The same build is an independent CI gate on the next GitHub run.
- **FW-PROD-005 — Public-policy deployment completed; formal review remains:** Public
  business, contact, privacy, terms, cancellation/refund, fulfilment, and
  database-backed pricing pages are deployed; the displayed contact channels and one
  owner-reviewed active plan have been verified. Before treating the pages as binding
  business terms, obtain appropriate Indian legal/accounting review and confirm the
  manual payment-error refund process can meet the stated response timelines.

## Milestone 9 — cash bonus

- **FW-BONUS-001 (completed in Milestone 9):** A dedicated `CASH-BONUS-V1` policy
  service supports a plan percentage and minimum qualifying duration.
- **FW-BONUS-002 (completed in Milestone 9):** Customer and owner reads distinguish
  principal, earned bonus, projected bonus, and redeemable amount without rewriting
  historical contributions.
- **FW-BONUS-003 (completed in Milestone 9):** Enrolments snapshot the versioned
  policy terms; boundary, cutoff, rounding, redemption, and reconciliation tests cover
  the resulting earned entitlement.
- **FW-BONUS-004:** Define any future caps, tiers, discretionary approval, forfeiture,
  cancellation, tax treatment, or policy for projections that include expected future
  contributions. Current projections use paid principal only.
- **FW-BONUS-005:** Optimize aggregate bonus-liability reads only after measured cash
  account volume shows the current correctness-first per-account calculation is costly.

## Milestone 10 — audit and exceptions

- **FW-AUDIT-001 (completed in Milestone 10):** Supported sensitive owner actions
  append immutable actor/timestamp/reason audit events, and an erroneous redemption
  is corrected through one immutable compensating reversal rather than editing it.
- **FW-AUDIT-002:** Define approval and segregation-of-duties rules for sensitive
  settlements, including who may initiate, approve, and review them.
- **FW-AUDIT-003 (initial queue completed in Milestone 10):** The owner queue derives
  paid-unallocated/failed-allocation and failed or mismatched webhook exceptions.
  Add provider reconciliation and resolution workflows for delayed/unmatched
  payments, Razorpay refunds/disputes, and other external settlement differences.
- **FW-AUDIT-004:** Automate safe retries and external alerts for
  `PAID_UNALLOCATED` metal contributions while preserving idempotency.
- **FW-AUDIT-005:** Define and implement manual payment correction and payment void
  policies, including compensating-event shape, required evidence, customer
  disclosure, and authorization. Published Scheme Rates are append-only and must
  never be corrected by editing a historical record.

## Milestone 11 — receipts and statements

- **FW-DOC-001 (completed in Milestone 11):** Customer lifetime scheme statements
  show verified contributions, captured metal allocations, redemptions, reversals,
  and current denomination-specific entitlement.
- **FW-DOC-002 (completed for MVP in Milestone 11):** Verified contributions have
  printable HTML acknowledgements with deterministic receipt references; reprinting
  derives the same reference without creating a new financial event.
- **FW-DOC-003 (completed in Milestone 11):** Owner contribution/redemption CSV
  exports use separate INR, gold-gram, and silver-gram columns and exclude indicative
  current metal exposure from booked amounts.
- **FW-DOC-004:** Before treating documents as statutory receipts or tax invoices,
  define business/tax identity fields, numbering jurisdiction, signatures, rendered
  copy retention, delivery/reissue tracking, correction/cancellation treatment, and
  whether server-generated PDF/PDF-A is required. Current HTML is an acknowledgement.

## Payments and settlement operations

- **FW-PRODUCT-001 — Metal-only production boundary (completed in production
  2026-08-25):** Release `93ba4273c976cd427d86a79a58454e2b7e58c55f`
  blocks production CASH enrolment and contribution initiation
  in services and UI whenever `DEBUG=False`; owner forms expose only gold/silver,
  direct legacy CASH payment URLs return `403`, and production checks reject DEBUG.
  Historical CASH reads, statements, exports, bonus calculations, redemptions, and
  audit records remain intact. Pre- and post-release production audits found one open
  CASH account with
  zero pending/verified payments, zero INR exposure, zero redemptions, and no nonzero
  cash-bonus plan. Live/readiness, financial-exception, log, and manual UI checks
  passed; the release required no schema migration.
- **FW-PRODUCT-002 — Empty legacy CASH account disposition:** The one production
  CASH account remains an inert historical record because the lifecycle currently has
  no audited cancellation state. Decide with the customer/business owner whether a
  general no-liability cancellation workflow is required; never mark it redeemed,
  delete it, or rewrite its mode merely to remove it from an active-account list.
- **FW-PAY-001:** Plan Razorpay live-mode onboarding. Live keys remain rejected until
  production verification, reconciliation, refund, dispute, and incident procedures
  are approved and tested.
- **FW-PAY-002:** Add expiry/cancellation and reconciliation handling for abandoned
  Razorpay orders, including flexible-frequency attempts, while retaining a safe
  resume path and preserving provider references for audit.
- **FW-PAY-003:** The stable owned HTTPS endpoint has replaced development quick
  tunnels. Complete webhook-secret synchronization and rotation evidence, retry
  behavior, monitoring, and recovery for invalid or delayed webhook deliveries.
- **FW-SETTLE-001:** Integrate actual payout, metal handover, or point-of-sale
  confirmation if the business later requires the application to execute rather
  than merely record settlement.
- **FW-SETTLE-002:** Define metal-to-cash conversion, including the authoritative
  rate timestamp, spread/fee, taxes, rounding, approval, and customer disclosure.
- **FW-SETTLE-003:** Decide whether partial redemptions need minimum amounts,
  maximum counts, reservations, expiry, or dual approval.
- **FW-SETTLE-004:** If inventory or invoicing is introduced, validate jewellery
  invoice value, taxes, making charges, returns, and stock movement in a separate
  bounded workflow. Milestone 8 stores only an external reference and notes.

## Rates and pricing

- **FW-PRICE-001 (completed 2026-08-19):** Display only active plans explicitly
  approved with `publicly_listed`, using their structured INR amount/range,
  frequency, duration, description, and cash-bonus terms. Existing plans migrate as
  private and owner plan edits continue to be audited.
- **FW-PRICE-002:** Define and model the exact plan-specific early-discontinuation
  wastage/value-addition discount schedule before advertising a numeric scaled
  discount. Until then, the public policy promises no additional discount unless a
  schedule is present in the customer's written enrolment terms.
- **FW-RATE-001 (completed by ADR-0003):** Owner-published Scheme Rates are the sole
  authoritative gold/silver conversion rates. Publication is append-only, audited,
  and protected by validation plus a 5% large-change confirmation.
- **FW-RATE-002:** Decide whether abandoned pending payment orders need a Scheme Rate
  lock expiry. The current simpler rule retains the original lock until payment or
  failure; any expiry must coordinate with Razorpay order lifecycle and disclosure.
- **FW-RATE-003:** If external market data is later useful, add it only as
  owner-facing reference information. It must not become authoritative for customer
  allocation without a new ADR and explicit pricing/disclosure rules.

## Eligibility and communication

- **FW-ELIG-001:** Define business-day, holiday, and grace-period treatment if exact
  India-local calendar eligibility is no longer sufficient.
- **FW-ELIG-002:** Add configurable customer/owner reminders and delivery tracking
  for upcoming eligibility, allocation exceptions, and completed redemptions.

## Customer onboarding

- **FW-AUTH-001 (implemented locally 2026-08-26; deployment pending):** Owner-created
  customer profiles now begin with unusable passwords and receive one-time,
  digest-only, expiring password-setup invitations. Resend supersedes older links;
  activated users use password reset. Provider acceptance/failure is visible without
  storing provider error detail, Postmark tracking is disabled for authentication
  mail, token-bearing responses are non-cacheable/non-referrable and excluded from
  Caddy access logs, and login email uniqueness has a stop-before-migration preflight.
- **FW-AUTH-002:** Before public signup, implement complete customer-profile creation,
  email/mobile verification, duplicate handling, consent capture, abuse controls,
  and an explicit awaiting-owner-approval state.
- **FW-AUTH-003:** Keep contribution access disabled until an owner creates a valid
  `SchemeAccount`; a public login must never imply financial enrolment.

## Catalogue content management

- **FW-CMS-001 — Wagtail feasibility and architecture (completed 2026-08-24):**
  [ADR-0004](decisions/ADR-0004-wagtail-catalog-cms.md) accepts Wagtail 7.4 LTS as a
  bounded catalogue CMS while preserving the existing Django application,
  `accounts.CustomUser`, Bootstrap 5 public UI, and financial-domain separation.
- **FW-CMS-002 — Foundation spike (completed 2026-08-24):** Wagtail 7.4.3 is
  integrated additively at `/cms/` with PostgreSQL search, the existing
  `accounts.CustomUser`, `/admin/`, `/scheme/`, public-route precedence, restricted
  document types, and development-only local media. A customer and an owner without
  `wagtailadmin.access_admin` are denied; an explicitly authorized staff user can
  enter. Wagtail migrations apply locally and all 147 tests pass. Production
  promotion remains separate from this local foundation milestone.
- **FW-MEDIA-001 — Cloudflare R2 media foundation (functionally completed
  2026-08-24):** The application now selects local
  filesystem or Cloudflare R2 storage through environment variables, retains
  WhiteNoise for static files, keeps originals/documents behind short-lived signed
  URLs, publishes only generated renditions through an owned custom domain, and
  rejects an unsafe production configuration. Automated configuration, URL-isolation,
  upload, read, rendition, cleanup, and deployment-check tests pass. The production
  runbook records isolated buckets, bucket-scoped Object Read & Write tokens, the
  smoke command, CORS/cache/WAF policy, token rotation, and media recovery. A real
  isolated non-production R2 upload/read/rendition/cleanup smoke passed on 2026-08-24
  without retaining the temporary media. The real production bucket, owned media
  domain, public rendition path, private-prefix WAF rules, and no-residue smoke also
  passed on 2026-08-24. A second production smoke proved the public 24-hour cache
  header and a real Cloudflare cache hit. A replacement bucket-scoped token passed
  before and after the old token was deleted. Do not use the rate-limited `r2.dev`
  endpoint in production.
- **FW-MEDIA-002 — Media backup, recovery, and monitoring (accepted deferral
  2026-08-24):** The owner accepted deferring the isolated copy/delete/restore/hash
  drill and ongoing usage-monitoring evidence to keep the catalogue roadmap moving.
  This does not block local `FW-CATALOG-001` work. Until a separate backup target and
  periodic restore test exist, retain approved source photographs outside R2 and do
  not treat R2 as their only copy. Production editor activation requires explicit
  acceptance of this limitation and a source-original retention process.
- **FW-CATALOG-001 — Catalogue domain (completed 2026-08-24):** A dedicated
  `catalog` application provides one `CatalogIndexPage`, focused `ProductPage`,
  reusable category and marketing-collection snippets, and ordered image galleries
  with required alt text. Optional positive INR display prices are explicitly
  informational and independent of Scheme Rates or customer entitlements. Model
  validation, case-insensitive uniqueness, preview, revision, image, rendition, and
  showroom-only boundary tests pass; no inventory, cart, checkout, invoicing,
  fulfilment, or financial mutations were introduced. Production promotion remains
  a later catalogue rollout step.
- **FW-CATALOG-002 — Publishing and authorization (completed 2026-08-24):**
  An explicit idempotent bootstrap creates a draft catalogue root, dedicated media
  collection, subtree-scoped Catalogue Editors/Publishers/Administrators groups,
  collection-scoped image permissions, and a publisher approval workflow. Group
  membership is never inferred from application role, and non-staff users remain
  denied if mistakenly assigned. Drift detection, CMS entry, draft privacy, editor
  submission, publisher approval, publish/unpublish visibility, and actor-attributed
  Wagtail audit history tests pass. Workflow email is not an activation dependency;
  production group assignment remains part of rollout/training.
- **FW-CATALOG-003 — Public catalogue (completed 2026-08-24):** Accessible
  Bootstrap 5 catalogue/product pages now provide live-only search, category and
  collection filters, 12-item pagination, responsive Wagtail renditions, empty states,
  canonical/Open Graph/Product and CollectionPage metadata, and phone/email/showroom
  enquiry paths. Global navigation is protected by a default-off rollout flag and a
  second live/public check. Automated checks cover discovery, structured content,
  responsive image attributes, showroom-only wording, pagination, and draft/public
  visibility; production browser accessibility/performance proof remains in
  `FW-CATALOG-004`.
- **FW-CATALOG-004 — Production rollout (completed 2026-08-25):** Production release
  `2311ccf` was promoted after a current database recovery point and clean financial
  baseline. Additive Wagtail/taggit/catalogue migrations, authorization reconciliation,
  R2 upload/read/rendition/cleanup, explicit staff publishing access, reviewed content,
  direct mobile/desktop browser checks, health checks, and navigation activation all
  passed. `FW-MEDIA-002` remains an accepted limitation, so approved source originals
  must remain independently retained outside R2.
- **FW-CMS-003 — Editorial-page migration (completed locally 2026-08-25):** About and
  Our Story now have constrained Wagtail page types, seeded draft content, optional
  accessible R2-backed images, dedicated Editorial groups/media/workflow, stable named
  routes, and a default-off rollout gate with reviewed Django fallbacks. Catalogue
  permissions remain independent; savings plans, financial flows, policies, contact
  identity, and the conversion-focused homepage remain Django-owned. Production
  migration, staff assignment, content approval, and flag activation remain a separate
  reviewed rollout.
- **FW-CATALOG-005 — Scheme Plan marketing media:** If richer plan marketing is later
  required, design an optional Wagtail-managed image/editorial presentation linked to
  an authoritative `SchemePlan`. Do not duplicate or let CMS state control contribution
  amounts, duration, frequency, metal, bonus, eligibility, public-listing state, or
  enrolment terms. Define deletion/unpublish fallbacks, accessibility, approval, and
  historical-enrolment behavior before implementation.

## Prioritization rule

Complete the remaining production deployment gates before handling real funds. Feature
work may continue in the [MVP plan](MVP_PLAN.md), but production use should prioritize
the operational and audit items above feature expansion.

## Historical milestone ledger

This ledger preserves what was documented at each checkpoint. “Resolved” means a
later milestone implemented the deferred capability; it remains here for provenance
and is not current work.

| Checkpoint | Limitations or deferred scope recorded then | Current disposition |
| --- | --- | --- |
| Milestones 0–1 | No issue was identified inside the implemented foundation/enrolment slice. Contributions, providers, rates, allocations, liabilities, and redemption were deferred. | Resolved by Milestones 2–8. |
| Milestone 2 | Real payment providers, rates, metal allocations, liability reporting, and redemption were deferred. | Allocations, liabilities, redemption, the external Razorpay test journey, and manual Scheme Rates are resolved. The production-operations baseline is complete; environment proof and live-mode readiness remain `FW-PROD-001`–`FW-PROD-003`, `FW-PAY-001`, and `FW-PAY-003`. |
| Milestone 3 | Real payment/rate providers, paid-unallocated retry handling, liability reporting, and redemption were deferred. | Manual allocation recovery, liabilities, redemption, external Razorpay Test Mode validation, and manual Scheme Rates are resolved. Unexpected-allocation automation remains `FW-AUDIT-004`. |
| Milestone 4 / MVP Alpha | Real providers, paid-unallocated retry handling, and redemption remained deferred. | External test-mode payment, manual Scheme Rates, recovery, redemption, and the production-operations baseline are resolved. Deployment proof and automated recovery remain in the production and audit items above. |
| Milestone 5 | GoldAPI had deterministic boundary tests but no private-key live smoke; applied rate had no premium/margin/tax/approval policy; cache was process-local; allocation retry and alerts were manual. Razorpay, redemption, bonus, and audit/corrections were deferred. | ADR-0003 superseded the API architecture with audited manual Scheme Rates locked before payment. Remaining work is tracked by `FW-RATE-002`, `FW-RATE-003`, `FW-AUDIT-004`, `FW-PAY-001`, `FW-BONUS-004`–`FW-BONUS-005`, and the Milestone 10 audit items. |
| Milestone 6 | No external Razorpay transaction/webhook had been exercised; live keys were rejected pending live operations; abandoned monthly orders had no expiry/cancellation. Earlier Milestone 5 limitations remained. | The external Test Mode transaction, signed webhook, and production-operations baseline are resolved. Environment proof, live operations, stable HTTPS/webhook operations, abandoned-order handling, and carried-forward rate/recovery work remain `FW-PROD-001`–`FW-PROD-003`, `FW-PAY-001`–`FW-PAY-003`, and the related items above. |
| Milestone 7 | Eligibility had no reminders and did not initiate/complete redemption. The later review also noted exact-calendar behavior with no business-day or grace-period policy. | Redemption execution was resolved by Milestone 8. Communication and calendar policy remain `FW-ELIG-001` and `FW-ELIG-002`. |
| Milestone 8 | Redemption only recorded settlement; no payout, metal handover, POS, inventory, invoice validation, or metal-to-cash policy existed. Bonus, correction/reversal/approval, and configurable partial-settlement policies remained deferred. Receipts/statements were also deferred. | Initial bonus, audit/reversal, and MVP documents are resolved by Milestones 9–11. Remaining settlement, bonus, approval, and statutory-document work is tracked by the corresponding open items. |
| Milestone 9 | The initial cash bonus has one plan-configured percentage, a minimum qualifying duration, a paid-principal eligibility cutoff, and principal-first redemption. It has no caps, tiers, approval/forfeiture/tax policy, future-contribution projection, or optimized aggregate read model. | Tracked by `FW-BONUS-004` and `FW-BONUS-005`; initial audit/reversal is resolved by Milestone 10 while dual approval remains `FW-AUDIT-002`. |
| Milestone 10 | Immutable audit events cover supported sensitive actions; redemption reversal is append-only; the exception queue covers current paid-unallocated and failed webhook records. There is no manual payment/rate correction, void, refund/dispute reconciliation, dual approval, automated retry/alerting, or immutable database trigger protection against bulk ORM updates. | Tracked by `FW-AUDIT-002` through `FW-AUDIT-005`, `FW-PAY-001` through `FW-PAY-003`, and the production operations gate. |
| Milestone 11 | Receipts and statements are on-demand printable HTML, not archived rendered files or statutory tax invoices. There is no server-side PDF, email delivery/reissue log, signature, statutory business/tax identity, formal invoice numbering, or export date filtering. | MVP scope is complete; production/legal document requirements remain `FW-DOC-004`. |
