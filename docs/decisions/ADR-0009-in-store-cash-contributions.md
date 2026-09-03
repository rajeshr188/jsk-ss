# ADR-0009: In-store cash contributions and append-only correction

## Status

Accepted for implementation under `FW-PAY-006`.

## Context

Customers may pay a scheduled scheme contribution in cash at the showroom. Cash is
the tender used to acquire the customer's exact-grade metal entitlement; it is not a
revival of the legacy `CASH` savings mode and never creates an INR balance or cash
redemption right. Unlike Razorpay, no external provider can prove receipt, so the
owner's deliberate acknowledgement and the preserved cash-desk evidence are the
authorization boundary.

A mistaken entry cannot safely be edited or deleted after it changes metal liability.
At the same time, forbidding every correction would leave known bookkeeping errors in
customer balances. The application therefore needs a narrow compensating workflow,
not a general cancellation or refund mechanism.

## Decision

- A contribution records an explicit payment channel. Existing history is backfilled
  as Razorpay or Mock; new showroom cash uses `IN_STORE_CASH` and the internal
  `in_store_cash` provider label.
- The production feature is disabled by default. Only an active owner may use it, and
  only for an existing Gold or Silver scheme. It cannot be used for legacy `CASH`
  accounts, backdated receipts, split tenders, or customer self-service.
- Recording uses a server-retained preview followed by an explicit confirmation that
  cash was physically received. The preview shows INR amount, calendar period,
  exact-grade Scheme Rate, and resulting grams. A changed form or changed current
  Scheme Rate invalidates confirmation and requires a fresh review.
- Existing agreement amount/frequency/date rules, the environment kill switch,
  audited payment controls, optional weekly schedule, and exact-grade current-rate
  requirement all apply. Any pending Razorpay order on the account must first be
  completed or provider-reconciled so one cash receipt cannot race an online capture.
- Confirmation appends an immutable `InStoreCashReceipt` with a unique internal
  reference, idempotency key, actor and actor label, server receipt time, optional
  unique paper-receipt number, bounded notes, and an audit event. The contribution and
  receipt commit first as `PAID_UNALLOCATED`; allocation then reuses the existing
  exact locked-rate service. Failure remains a visible financial exception.
- A bookkeeping error is corrected only by appending one immutable
  `InStoreCashContributionReversal` and moving the original contribution to terminal
  `REVERSED`. Amount, original receipt, locked rate, timestamp, actor, and allocation
  are retained. Active balance reads exclude the original allocation and the statement
  displays both the receipt and compensating removal.
- Routine correction is owner-only, limited to the configured window (24 hours by
  default), and blocked after a downstream unreversed redemption or when the exact
  allocation is no longer available. A wrong amount or account is corrected by fully
  reversing the original and recording a separate new receipt after a new preview.
- Reversal is explicitly not customer cancellation and does not represent returning
  cash. Actual refunds, tax-invoice treatment, dual approval, and corrections outside
  the bounded window remain incident/manual-accounting workflows.
- Owner history and CSV exports expose the channel, cashier label, paper reference,
  reversal metadata, and status. A daily summary reports cash received, reversals, and
  net recorded cash; `check_in_store_cash_contributions` validates cross-record
  integrity without mutation.

## Consequences

The same metal scheme can accept online or showroom cash while preserving one
authoritative allocation and statement model. Corrections are explainable and
recoverable without erasing history, but an owner must reconcile the application's
daily cash total with the physical drawer and accounting records. The optional paper
number is evidence, not a statutory tax invoice. Cash-acceptance limits, tax treatment,
and records outside this application require qualified accounting/legal policy; the
application does not claim that its plan amount validation alone proves compliance.

Migration `schemes.0018` introduces the new channel, receipt/reversal ledgers, and
constraints. Because an old image does not populate the non-null channel field, the
migration requires a controlled stop-the-old-web cutover. The feature remains off
until the migration, integrity check, and owner UI review pass.
