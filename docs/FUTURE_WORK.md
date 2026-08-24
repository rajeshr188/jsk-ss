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
- **FW-PROD-003 — Delivery and rotation drill:** Verify real password-reset email
  delivery and rehearse separate Django, database, email, Razorpay API, and
  Razorpay webhook secret rotations without exposing credentials.
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

- **FW-AUTH-001:** Prefer owner invitations and customer password setup before open
  self-registration.
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
- **FW-CMS-002 — Foundation spike:** On `agent/wagtail-foundation`, add the smallest
  Wagtail integration needed to prove dependency compatibility, additive migrations,
  `/cms/` and admin coexistence, custom-user access, Django checks, and unchanged
  financial regressions. Keep catalogue models and production deployment out of this
  first code change. Exit when a customer is denied CMS access, an explicitly
  authorized staff user can enter it, and the full regression suite passes.
- **FW-MEDIA-001 — Cloudflare R2 media foundation:** Provision separate non-production
  and production R2 Standard buckets, use bucket-scoped Object Read & Write tokens,
  configure `django-storages` through environment variables, and retain WhiteNoise
  for static files. Exit when upload, Wagtail rendition, retrieval, cache/CORS policy,
  credential rotation, and recovery are exercised. Use an owned custom media domain
  in production; do not use the rate-limited `r2.dev` endpoint there. Record usage
  monitoring because the free allowance is not an unlimited service commitment.
- **FW-CATALOG-001 — Catalogue domain:** Implement a `CatalogIndexPage`, focused
  `ProductPage`, image gallery, and reusable category/collection snippets. Model
  product discovery and showroom enquiry only; do not introduce inventory, cart,
  invoicing, fulfilment, or reuse Scheme Rates as catalogue prices. Exit when model
  validation, uniqueness, preview, revision, and image tests pass.
- **FW-CATALOG-002 — Publishing and authorization:** Define least-privilege editor,
  publisher, and administrator groups; require explicit CMS authorization independent
  of application role; and test draft privacy, publish/unpublish, audit history, and
  owner workflow. Enable workflow email only after production SMTP is verified.
- **FW-CATALOG-003 — Public catalogue:** Add accessible Bootstrap 5 catalogue and
  product pages, responsive R2-backed images, SEO metadata, filtering/search, enquiry
  calls to action, and clear showroom availability language. Exit when accessibility,
  performance, structured-content, empty-state, and public/draft visibility checks
  pass on mobile and desktop.
- **FW-CATALOG-004 — Production rollout:** Back up the database and media inventory,
  run additive migrations against a release candidate, verify the custom media domain,
  security headers, monitoring, restore procedure, and application rollback, then
  train authorized editors. Existing public pages remain Django-owned until a later
  approved content/URL migration.

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
