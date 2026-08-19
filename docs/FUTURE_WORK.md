# Future Work Register

This document converts known MVP limitations into explicit follow-up work. Items
here are not implemented behavior and do not relax the financial invariants in
[Domain rules](DOMAIN_RULES.md).

## MVP Beta deployment gate

- **FW-BETA-001 — External Razorpay test journey (completed 2026-08-18):** Enrolment
  through redemption was exercised with a captured Razorpay Test Mode payment and a
  signed `payment.captured` webhook delivered to a public HTTPS endpoint.
- **FW-BETA-002 — Live GoldAPI smoke:** Validate one authenticated XAU/INR and one
  XAG/INR quote with a privately managed provider key, without logging the secret.
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
- **FW-PROD-002 — Stable edge and observability (Linode configuration prepared):**
  Deploy Caddy to the owned `jaishrikrishnajewellery.com` host, validate automatic
  HTTPS/proxy trust and staged HSTS, then select durable log retention and exercise
  external alerts for 5xx/readiness, webhook failures, allocation exceptions,
  database capacity, certificate renewal, and backup failure.
- **FW-PROD-003 — Delivery and rotation drill:** Verify real password-reset email
  delivery and rehearse separate Django, database, email, GoldAPI, Razorpay API, and
  Razorpay webhook secret rotations without exposing credentials.
- **FW-PROD-004 — Image-build confirmation (completed locally 2026-08-18):** The
  hardened image builds with production static assets and runs as the unprivileged
  `app` user. The same build is an independent CI gate on the next GitHub run.
- **FW-PROD-005 — Public-policy approval and live review:** Public business,
  contact, privacy, terms, cancellation/refund, fulfilment, and database-backed
  pricing pages are implemented. Before submitting them as binding business terms,
  obtain appropriate Indian legal/accounting review, verify the displayed contact
  channels, publish at least one reviewed active plan, and confirm the manual
  payment-error refund process can meet the stated response timelines.

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
- **FW-AUDIT-005:** Define and implement manual payment correction, payment void,
  and manual rate override policies, including compensating-event shape, required
  evidence, pricing/customer disclosure, and authorization. Reserved audit action
  names do not currently enable these financial mutations.

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
- **FW-PAY-003:** Replace development quick tunnels with a stable owned HTTPS endpoint;
  document webhook-secret synchronization and rotation, retry behavior, monitoring,
  and recovery for invalid or delayed webhook deliveries.
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
- **FW-RATE-001:** Define how store premium, margin, tax, and manual rate approval
  affect the applied rate while retaining the provider quote as immutable evidence.
- **FW-RATE-002:** Replace the process-local GoldAPI cache with shared quota
  protection when multiple application workers are deployed.
- **FW-RATE-003:** Add provider fallback and stale-quote policy only after explicit
  maximum-age and customer-disclosure rules are approved; never invent a rate.

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
| Milestone 2 | Real payment providers, rates, metal allocations, liability reporting, and redemption were deferred. | Mock/live rates, allocations, liabilities, redemption, and the external Razorpay test journey are resolved. The production-operations baseline is complete; environment proof and live-mode readiness remain `FW-PROD-001`–`FW-PROD-003`, `FW-PAY-001`, and `FW-PAY-003`. |
| Milestone 3 | Real payment/rate providers, paid-unallocated retry handling, liability reporting, and redemption were deferred. | Manual allocation recovery, liabilities, redemption, and external Razorpay Test Mode validation are resolved. Live GoldAPI validation and automated recovery remain `FW-BETA-002` and `FW-AUDIT-004`. |
| Milestone 4 / MVP Alpha | Real providers, paid-unallocated retry handling, and redemption remained deferred. | External test-mode payment, live-rate adapter, manual recovery, redemption, and the production-operations baseline are resolved. Deployment proof, live GoldAPI validation, and automated recovery remain in the production, Beta, and audit items above. |
| Milestone 5 | GoldAPI had deterministic boundary tests but no private-key live smoke; applied rate had no premium/margin/tax/approval policy; cache was process-local; allocation retry and alerts were manual. Razorpay, redemption, bonus, and audit/corrections were deferred. | Redemption, Razorpay Test Mode, and the initial cash-bonus policy are resolved. Remaining work is tracked by `FW-BETA-002`, `FW-RATE-001`, `FW-RATE-002`, `FW-AUDIT-004`, `FW-PAY-001`, `FW-BONUS-004`–`FW-BONUS-005`, and the Milestone 10 audit items. |
| Milestone 6 | No external Razorpay transaction/webhook had been exercised; live keys were rejected pending live operations; abandoned monthly orders had no expiry/cancellation. Earlier Milestone 5 limitations remained. | The external Test Mode transaction, signed webhook, and production-operations baseline are resolved. Environment proof, live operations, stable HTTPS/webhook operations, abandoned-order handling, and carried-forward rate/recovery work remain `FW-PROD-001`–`FW-PROD-003`, `FW-PAY-001`–`FW-PAY-003`, and the related items above. |
| Milestone 7 | Eligibility had no reminders and did not initiate/complete redemption. The later review also noted exact-calendar behavior with no business-day or grace-period policy. | Redemption execution was resolved by Milestone 8. Communication and calendar policy remain `FW-ELIG-001` and `FW-ELIG-002`. |
| Milestone 8 | Redemption only recorded settlement; no payout, metal handover, POS, inventory, invoice validation, or metal-to-cash policy existed. Bonus, correction/reversal/approval, and configurable partial-settlement policies remained deferred. Receipts/statements were also deferred. | Initial bonus, audit/reversal, and MVP documents are resolved by Milestones 9–11. Remaining settlement, bonus, approval, and statutory-document work is tracked by the corresponding open items. |
| Milestone 9 | The initial cash bonus has one plan-configured percentage, a minimum qualifying duration, a paid-principal eligibility cutoff, and principal-first redemption. It has no caps, tiers, approval/forfeiture/tax policy, future-contribution projection, or optimized aggregate read model. | Tracked by `FW-BONUS-004` and `FW-BONUS-005`; initial audit/reversal is resolved by Milestone 10 while dual approval remains `FW-AUDIT-002`. |
| Milestone 10 | Immutable audit events cover supported sensitive actions; redemption reversal is append-only; the exception queue covers current paid-unallocated and failed webhook records. There is no manual payment/rate correction, void, refund/dispute reconciliation, dual approval, automated retry/alerting, or immutable database trigger protection against bulk ORM updates. | Tracked by `FW-AUDIT-002` through `FW-AUDIT-005`, `FW-PAY-001` through `FW-PAY-003`, and the production operations gate. |
| Milestone 11 | Receipts and statements are on-demand printable HTML, not archived rendered files or statutory tax invoices. There is no server-side PDF, email delivery/reissue log, signature, statutory business/tax identity, formal invoice numbering, or export date filtering. | MVP scope is complete; production/legal document requirements remain `FW-DOC-004`. |
