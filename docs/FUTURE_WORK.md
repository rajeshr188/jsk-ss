# Future Work Register

This is the actionable backlog for known limitations that remain unresolved. It does
not describe implemented behavior and does not relax the financial invariants in
[Domain rules](DOMAIN_RULES.md).

Detailed completed-work evidence belongs in [Project status](STATUS.md), the
[production runbook](PRODUCTION_DEPLOYMENT.md), and the applicable
[architecture decisions](decisions/README.md). A compact completed-item index and the
historical milestone ledger remain here so stable `FW-*` identifiers and previously
recorded limitations are not lost.

## Prioritization

1. Protect real funds: monitoring, recovery, rotation, webhook reconciliation, and
   correction controls.
2. Complete legal/accounting and statutory-document review for the live business
   flows.
3. Improve settlement, eligibility communication, and customer onboarding only after
   their business rules are approved.
4. Add catalogue and pricing enhancements without coupling CMS state to financial
   contracts.

## Production operations

- **FW-PROD-002 — Activate and exercise external observability:** Caddy already
  provides masked structured logs, release-labelled health endpoints, and the
  repository includes a five-minute financial-exception heartbeat. Configure the
  selected external monitoring/log-retention accounts and retain exercised evidence
  for readiness/5xx failures, webhook and allocation exceptions, database capacity,
  certificate renewal, backup failure, escalation, and retention. Paid monitoring
  remains explicitly deferred for budget reasons; local checks and provider consoles
  do not close this item.
- **FW-PROD-003 — Rehearse coordinated secret rotation:** Postmark delivery and the
  owned Django Site identity are verified. Rehearse Django signing-key, database,
  SMTP, Razorpay API, and webhook-secret changes with bounded overlap or coordinated
  cutover, rollback criteria, and retained evidence. SMTP token rotation remains
  explicitly deferred.
- **FW-PROD-005 — Obtain formal policy review:** Public business, contact, privacy,
  terms, cancellation/refund, fulfilment, and database-backed pricing pages are live.
  Obtain appropriate Indian legal/accounting review before treating them as binding,
  and verify the manual payment-error refund process can meet the displayed response
  timelines.

## Payments, cash, and audit

- **FW-PAY-003 — Complete Razorpay webhook-recovery evidence:** ADR-0006 and release
  `69eecf9` provide signed-event classification, append-only attempt evidence, and an
  owner-only provider-backed dry-run/apply workflow. The remaining work is:

  - [ ] Exercise one controlled review/dry-run/apply case in isolated Test mode.
  - [ ] Replay an already-processed Live capture from Razorpay and prove an
    `ALREADY_FINAL` attempt is appended without duplicate entitlement.
  - [ ] Alert on stale `RECEIVED` and unresolved `REVIEW_REQUIRED` events under
    `FW-PROD-002`.
  - [ ] Rehearse synchronized webhook-secret rotation under `FW-PROD-003`.

  Automatic refunds, background workers, and manual entitlement overrides remain out
  of scope.
- **FW-PAY-007 — Extend payment schedules only if required:** Current controls support
  one weekly window per day plus audited manual pause/resume. Define holiday
  exceptions, multiple daily windows, expiring force-open overrides, and a separate
  allocation-integrity hold before implementing any of them.
- **FW-AUDIT-002 — Define segregation of duties:** Decide who may initiate, approve,
  and review sensitive settlements, refunds, corrections, and exceptional cash
  operations. Implement dual approval only after those roles and thresholds are
  approved.
- **FW-AUDIT-003 — Expand external settlement reconciliation:** The existing queue
  covers paid-unallocated allocations and failed/mismatched webhooks. Add resolution
  workflows for delayed or provider-only payments, late captures, Razorpay refunds
  and disputes, chargebacks, and other provider/local differences.
- **FW-AUDIT-004 — Automate safe allocation recovery:** Add bounded retries and
  external alerts for `PAID_UNALLOCATED` metal contributions while preserving
  idempotency and owner visibility.
- **FW-AUDIT-005 — Define online-payment correction and void policy:** Specify
  compensating-event shape, evidence, customer disclosure, authorization, and
  provider reconciliation. Decide whether database-trigger protection against bulk
  updates is warranted. Never edit a historical payment or Scheme Rate.
- **FW-CASH-001 — Harden showroom cash operations:** Obtain legal/accounting review
  of cash acceptance and external bookkeeping; decide statutory receipt requirements,
  daily close ownership, corrections outside the configured 24-hour window, refunds,
  and dual approval. The deployed append-only reversal is a bookkeeping correction,
  not a refund.
- **FW-PRODUCT-002 — Resolve the empty legacy CASH account:** One inert production
  CASH account has no liability and no audited cancellation state. Decide with the
  customer and business owner whether a general no-liability cancellation workflow is
  required. Never delete it, relabel its mode, or mark it redeemed merely to hide it.

## Bonus, documents, pricing, and settlement

- **FW-BONUS-004 — Define richer bonus policy if CASH products return:** Specify caps,
  tiers, discretionary approval, forfeiture, cancellation, tax treatment, and whether
  projections may include expected future contributions. Current projections use
  paid principal only.
- **FW-BONUS-005 — Optimize bonus aggregation only when measured:** Retain the
  correctness-first per-account calculation until production volume demonstrates a
  material cost.
- **FW-DOC-004 — Define statutory receipt/invoice requirements:** Decide business and
  tax identity fields, jurisdictional numbering, signatures, retained rendered copies,
  delivery/reissue tracking, correction/cancellation treatment, date-filtered exports,
  and whether server-generated PDF/PDF-A is required. Current HTML documents are
  acknowledgements, not tax invoices.
- **FW-PRICE-002 — Model early-discontinuation terms:** Define the exact plan-specific
  wastage/value-addition discount schedule before advertising numeric benefits. Until
  then, the public policy promises no additional discount unless it exists in the
  customer's written enrolment terms.
- **FW-SETTLE-001 — Integrate fulfilment evidence if required:** Add actual payout,
  metal handover, or point-of-sale confirmation only if the application must execute
  rather than merely record settlement.
- **FW-SETTLE-002 — Define metal-to-cash conversion:** Approve authoritative rate
  timing, spread or fee, taxes, rounding, authorization, and customer disclosure
  before implementation.
- **FW-SETTLE-003 — Define partial-redemption policy:** Decide minimum amounts,
  maximum counts, reservations, expiry, and approval requirements.
- **FW-SETTLE-004 — Keep inventory and invoicing separate:** If introduced, validate
  jewellery invoice value, taxes, making charges, returns, and stock movement in a
  dedicated bounded workflow. Current redemption stores only external references and
  notes.

## Eligibility and customer communication

- **FW-ELIG-001 — Adopt exact-calendar eligibility:** ADR-0010 is accepted and the
  shared policy is implemented locally. Complete CI and the normal no-migration
  application rollout before closing the item. Eligibility is the scheme start date
  plus agreed calendar months with month-end clamping; no weekend/holiday shift,
  early grace, or post-eligibility expiry applies.
- **FW-ELIG-002 — Add reminders and delivery evidence:** Support configurable
  customer/owner reminders for upcoming eligibility, allocation exceptions, and
  completed redemptions, with delivery-state tracking.
- **FW-AUTH-002 — Design safe public signup before enabling it:** Add complete customer
  profile creation, email/mobile verification, duplicate handling, consent capture,
  abuse controls, and an explicit awaiting-owner-approval state.
- **FW-AUTH-003 — Keep login separate from enrolment:** Contribution access must remain
  disabled until an owner creates a valid `SchemeAccount`; a public login must never
  imply financial enrolment.

## Rates, media, and catalogue

- **FW-RATE-003 — Keep external rates informational:** If market data is later useful,
  add it only as owner-facing reference information. It must not control customer
  allocation without a new ADR and explicit pricing/disclosure rules.
- **FW-MEDIA-002 — Add independent media recovery and monitoring:** The owner accepted
  deferring the isolated copy/delete/restore/hash drill and ongoing usage monitoring.
  Until a separate backup target and periodic restore proof exist, retain approved
  source photographs outside R2 and never treat R2 as their only copy.
- **FW-CATALOG-005 — Add Scheme Plan marketing media without financial coupling:**
  Design optional Wagtail-managed imagery/editorial presentation linked to an
  authoritative `SchemePlan`. CMS state must not control or duplicate contribution
  amounts, duration, frequency, grade, bonus, eligibility, public-listing state, or
  enrolment terms. Define deletion/unpublish fallbacks, accessibility, approval, and
  historical-enrolment behavior first.

## Completed item index

Completed implementation and rollout details are intentionally not repeated here:

- **Foundation and production:** `FW-BETA-001`, `FW-BETA-002`, `FW-BETA-003`,
  `FW-PROD-001`, and `FW-PROD-004`.
- **Financial domain:** `FW-BONUS-001`, `FW-BONUS-002`, `FW-BONUS-003`,
  `FW-AUDIT-001`, `FW-DOC-001`, `FW-DOC-002`, `FW-DOC-003`, `FW-PRODUCT-001`,
  `FW-PAY-001`, `FW-PAY-002`, `FW-PAY-004`, `FW-PAY-005`, `FW-PAY-006`,
  `FW-PRICE-001`, `FW-RATE-001`, and `FW-RATE-002`.
- **Authentication:** `FW-AUTH-001`.
- **CMS, media, and catalogue:** `FW-CMS-001`, `FW-CMS-002`, `FW-CMS-003`,
  `FW-MEDIA-001`, `FW-CATALOG-001`, `FW-CATALOG-002`, `FW-CATALOG-003`, and
`FW-CATALOG-004`.

Use [Project status](STATUS.md) for the completed capability summary, the
[production runbook](PRODUCTION_DEPLOYMENT.md) for release evidence, and ADR-0003
through ADR-0010 for the corresponding durable architecture decisions.

## Historical milestone ledger

This compact ledger preserves limitations recorded at each checkpoint. “Resolved”
means later work implemented that capability; unresolved parts point to active items
above.

| Checkpoint | Limitation recorded then | Current disposition |
| --- | --- | --- |
| Milestones 0–1 | Contributions, rates, allocations, liabilities, and redemption were deferred. | Resolved by Milestones 2–8. |
| Milestone 2 | Real providers, rates, allocations, liabilities, and redemption were deferred. | Core financial flow and provider acceptance are resolved; operations remain `FW-PROD-002`, `FW-PROD-003`, and `FW-PAY-003`. |
| Milestone 3 | Paid-unallocated recovery, liabilities, providers, and redemption were deferred. | Manual recovery and the financial flow are resolved; automation remains `FW-AUDIT-004`. |
| Milestone 4 / MVP Alpha | Real providers, recovery, and redemption remained deferred. | Resolved except the active production/audit items above. |
| Milestone 5 | Provider rates, premium/tax policy, allocation automation, Razorpay, settlement, bonus, and audit were incomplete. | Manual Scheme Rates and core flows are resolved; open work remains `FW-RATE-003`, `FW-AUDIT-002`–`FW-AUDIT-005`, and `FW-BONUS-004`–`FW-BONUS-005`. |
| Milestone 6 | External Razorpay/webhook proof, live-key controls, and abandoned orders were incomplete. | Test/Live acceptance and order lifecycle are resolved; recovery evidence and operations remain `FW-PAY-003`, `FW-PROD-002`, and `FW-PROD-003`. |
| Milestone 7 | Eligibility did not initiate redemption and lacked reminders/business-day policy. | Redemption is resolved; exact-calendar rollout remains `FW-ELIG-001` and communication remains `FW-ELIG-002`. |
| Milestone 8 | No payout, handover, POS, inventory, invoice validation, metal-to-cash policy, bonus, corrections, or documents existed. | MVP bonus/audit/documents are resolved; remaining scope is `FW-SETTLE-001`–`FW-SETTLE-004`, `FW-AUDIT-002`–`FW-AUDIT-005`, and `FW-DOC-004`. |
| Milestone 9 | Bonus lacked caps, tiers, approval, forfeiture, tax policy, and optimized aggregation. | `FW-BONUS-004`–`FW-BONUS-005`. |
| Milestone 10 | No generic payment correction, refund/dispute reconciliation, dual approval, automated retry/alerts, or database-trigger protection existed. | `FW-AUDIT-002`–`FW-AUDIT-005`, `FW-PAY-003`, and `FW-PROD-002`. |
| Milestone 11 | Documents were printable HTML rather than archived statutory invoices, with no PDF, signature, delivery log, tax identity, formal numbering, or date-filtered export. | `FW-DOC-004`. |
