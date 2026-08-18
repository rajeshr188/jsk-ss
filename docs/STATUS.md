# Project Status

## Current milestone

Milestone 7 — Redemption eligibility views (complete)

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

## In progress

- None.

## Known limitations

- GoldAPI behavior is covered with deterministic HTTP-boundary tests, but a real
  request has not been verified because no private provider key is stored here.
- The applied metal rate currently equals the provider rate; store premiums,
  margins, taxes, and manual rate approval are not implemented.
- The short GoldAPI cache is process-local, so separate production workers do not
  share quota protection.
- Paid metal contributions that cannot obtain a valid rate require an owner to
  retry allocation manually; automated retrying and external alert delivery are
  deferred.
- No external Razorpay transaction/webhook was exercised because private test
  credentials and a public HTTPS callback endpoint are not stored in the project.
- Razorpay live keys are intentionally rejected. Live-mode onboarding, operational
  reconciliation, refunds, disputes, and failure-event handling remain future work.
- An abandoned once-per-month Razorpay order can be resumed, but it has no automatic
  expiry/cancellation workflow yet.
- Eligibility is visible but does not yet send reminders or initiate/complete a
  redemption; those financial mutations belong to Milestone 8.

## Deferred

- Redemption execution, bonus, and formal audit/correction workflows.

## Verification

- PostgreSQL 16 migrations applied successfully.
- 81 tests pass, including exact eligibility boundaries, derived-status non-mutation, owner authorization, Razorpay idempotency, GoldAPI behavior, allocation recovery, liability reconciliation, and prior regressions.
- Migration `schemes.0005` is applied to PostgreSQL.
- Milestone 7 requires no migration; migration drift check reports no changes.
- Django system check and migration drift check pass.
- Production static collection and deployment check pass with preload explicitly enabled.
- Live-server checkpoint passes for owner and customer login, UI-created plan/customer/CASH-GOLD-SILVER enrolments, three mock payments, customer entitlements, owner contribution visibility, and exact liability/activity deltas.
- Live GoldAPI HTTP behavior is verified at the adapter boundary with deterministic mocked responses; no real provider request was made because no API key is stored in the repository.
- Live-server recovery smoke passes across a rate-failure/server-restart/rate-restoration sequence: verified payment remains unallocated, owner retry creates exactly one 0.800000 g allocation, and all disposable records are removed.
- Milestone 7 live-HTTP smoke passes for owner forecast/detail views and customer redemption-eligible guidance; the database status remains `ACTIVE`, and all disposable records are removed.

## Next recommended step

Milestone 8 — redemption.
