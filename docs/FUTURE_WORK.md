# Future Work Register

This document converts known MVP limitations into explicit follow-up work. Items
here are not implemented behavior and do not relax the financial invariants in
[Domain rules](DOMAIN_RULES.md).

## MVP Beta deployment gate

- **FW-BETA-001 — External Razorpay test journey:** Exercise enrolment through
  redemption with a real Razorpay test payment, server verification, and a signed
  `payment.captured` webhook delivered to a public HTTPS endpoint.
- **FW-BETA-002 — Live GoldAPI smoke:** Validate one authenticated XAU/INR and one
  XAG/INR quote with a privately managed provider key, without logging the secret.
- **FW-BETA-003 — Production operations:** Define secret rotation, PostgreSQL
  backup/restore drills, HTTPS and HSTS ownership, health checks, error monitoring,
  and deployment rollback procedures before handling real customer funds.

## Milestone 9 — cash bonus

- **FW-BONUS-001:** Add a dedicated, versioned bonus-policy service with percentage
  and minimum qualifying-duration rules.
- **FW-BONUS-002:** Distinguish principal, earned bonus, projected bonus, and total
  redeemable amount without rewriting historical contributions.
- **FW-BONUS-003:** Snapshot the policy used for a granted bonus and cover boundary,
  rounding, and redemption tests.

## Milestone 10 — audit and exceptions

- **FW-AUDIT-001:** Add owner-controlled correction, reversal, and void workflows
  that append compensating events instead of editing completed redemptions.
- **FW-AUDIT-002:** Define approval and segregation-of-duties rules for sensitive
  settlements, including who may initiate, approve, and review them.
- **FW-AUDIT-003:** Add exception queues and operational reconciliation for payment
  failures, Razorpay refunds/disputes, and unmatched or delayed webhooks.
- **FW-AUDIT-004:** Automate safe retries and external alerts for
  `PAID_UNALLOCATED` metal contributions while preserving idempotency.

## Milestone 11 — receipts and statements

- **FW-DOC-001:** Generate customer contribution, allocation, and redemption
  statements with stable references and denomination-specific totals.
- **FW-DOC-002:** Generate downloadable/printable receipts and define numbering,
  retention, and reissue rules.
- **FW-DOC-003:** Add owner exports suitable for accounting reconciliation without
  presenting indicative metal exposure as a booked cash liability.

## Payments and settlement operations

- **FW-PAY-001:** Plan Razorpay live-mode onboarding. Live keys remain rejected until
  production verification, reconciliation, refund, dispute, and incident procedures
  are approved and tested.
- **FW-PAY-002:** Add expiry/cancellation handling for abandoned once-per-month
  Razorpay orders while retaining a safe resume path.
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

Complete the MVP Beta deployment gate before Milestone 9. Then follow the milestone
order in the [MVP plan](MVP_PLAN.md). Any production use involving real funds should
prioritize the operational and audit items above feature expansion.

## Historical milestone ledger

This ledger preserves what was documented at each checkpoint. “Resolved” means a
later milestone implemented the deferred capability; it remains here for provenance
and is not current work.

| Checkpoint | Limitations or deferred scope recorded then | Current disposition |
| --- | --- | --- |
| Milestones 0–1 | No issue was identified inside the implemented foundation/enrolment slice. Contributions, providers, rates, allocations, liabilities, and redemption were deferred. | Resolved by Milestones 2–8. |
| Milestone 2 | Real payment providers, rates, metal allocations, liability reporting, and redemption were deferred. | Mock/live rates, allocations, liabilities, and redemption are resolved. Razorpay test mode is resolved; live-mode readiness remains `FW-BETA-001`, `FW-BETA-003`, and `FW-PAY-001`. |
| Milestone 3 | Real payment/rate providers, paid-unallocated retry handling, liability reporting, and redemption were deferred. | Manual allocation recovery, liabilities, and redemption are resolved. External-provider validation and automated recovery remain `FW-BETA-001`, `FW-BETA-002`, and `FW-AUDIT-004`. |
| Milestone 4 / MVP Alpha | Real providers, paid-unallocated retry handling, and redemption remained deferred. | Test-mode payment, live-rate adapter, manual recovery, and redemption are resolved. Production validation and automated recovery remain in the Beta and audit items above. |
| Milestone 5 | GoldAPI had deterministic boundary tests but no private-key live smoke; applied rate had no premium/margin/tax/approval policy; cache was process-local; allocation retry and alerts were manual. Razorpay, redemption, bonus, and audit/corrections were deferred. | Tracked by `FW-BETA-002`, `FW-RATE-001`, `FW-RATE-002`, `FW-AUDIT-004`, `FW-PAY-001`, the Milestone 9 bonus items, and the Milestone 10 audit items. Redemption was resolved by Milestone 8. |
| Milestone 6 | No external Razorpay transaction/webhook had been exercised; live keys were rejected pending live operations; abandoned monthly orders had no expiry/cancellation. Earlier Milestone 5 limitations remained. | Tracked by `FW-BETA-001`, `FW-BETA-003`, `FW-PAY-001`, and `FW-PAY-002`, plus the carried-forward rate and recovery items. |
| Milestone 7 | Eligibility had no reminders and did not initiate/complete redemption. The later review also noted exact-calendar behavior with no business-day or grace-period policy. | Redemption execution was resolved by Milestone 8. Communication and calendar policy remain `FW-ELIG-001` and `FW-ELIG-002`. |
| Milestone 8 | Redemption only recorded settlement; no payout, metal handover, POS, inventory, invoice validation, or metal-to-cash policy existed. Bonus, correction/reversal/approval, and configurable partial-settlement policies remained deferred. Receipts/statements were also deferred. | Tracked by `FW-SETTLE-001` through `FW-SETTLE-004`, all Milestone 9 bonus items, all Milestone 10 audit items, and all Milestone 11 document items. |
