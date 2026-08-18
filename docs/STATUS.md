# Project Status

## Current milestone

Milestone 8 — Redemption (complete)

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

## In progress

- None.

## Known limitations

- External Razorpay and GoldAPI flows have deterministic boundary coverage but still
  require private-credential verification before the MVP Beta checkpoint.
- The application records redemptions but does not execute payouts, move inventory,
  create invoices, or convert metal to cash.
- Bonus, compensating correction events, operational reconciliation, automated
  alerts/retries, receipts, and statements remain scheduled work.
- Pricing policy, shared provider caching, payment-order expiry, eligibility
  reminders, public onboarding, and partial-settlement policy are not yet defined.
- The detailed, prioritized backlog is maintained in [Future work](FUTURE_WORK.md).

## Deferred

- See [Future work](FUTURE_WORK.md) for deployment gates and work mapped to Milestones 9–11.

## Verification

- PostgreSQL 16 migrations applied successfully.
- 95 tests pass, including redemption precision, over-redemption protection,
  idempotency, partial/full closure, denomination separation, access control,
  PostgreSQL constraints, and all prior regressions.
- Migration `schemes.0006_redemption` is applied to PostgreSQL.
- Migration drift check reports no changes.
- Django system check and migration drift check pass.
- Production static collection and deployment check pass with preload explicitly enabled.
- Live-server checkpoint passes for owner and customer login, UI-created plan/customer/CASH-GOLD-SILVER enrolments, three mock payments, customer entitlements, owner contribution visibility, and exact liability/activity deltas.
- Live GoldAPI HTTP behavior is verified at the adapter boundary with deterministic mocked responses; no real provider request was made because no API key is stored in the repository.
- Live-server recovery smoke passes across a rate-failure/server-restart/rate-restoration sequence: verified payment remains unallocated, owner retry creates exactly one 0.800000 g allocation, and all disposable records are removed.
- Milestone 7 live-HTTP smoke passes for owner forecast/detail views and customer redemption-eligible guidance; the database status remains `ACTIVE`, and all disposable records are removed.
- Milestone 8 authenticated request smoke passes with CSRF enforcement: an owner
  records partial cash and final jewellery settlement, the customer sees both
  records and no payment action, liabilities reconcile, and disposable data is removed.

## Next recommended step

MVP Beta checkpoint — verify the complete enrolment-to-redemption journey with an
external Razorpay test transaction and signed webhook on a public HTTPS endpoint.
