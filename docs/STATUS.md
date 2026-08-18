# Project Status

## Current milestone

Milestone 5 — Live metal-rate provider (complete)

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

## Deferred

- Razorpay payment integration, redemption, bonus, and formal audit/correction workflows.

## Verification

- PostgreSQL 16 migrations applied successfully.
- 58 tests pass, including GoldAPI request security/parsing/cache/failures, live-provider allocation integration, paid-unallocated recovery, owner-only retry, liability reconciliation, authorization, and prior regressions.
- Migration `schemes.0004` is applied to PostgreSQL.
- Django system check and migration drift check pass.
- Production static collection and deployment check pass with preload explicitly enabled.
- Live-server checkpoint passes for owner and customer login, UI-created plan/customer/CASH-GOLD-SILVER enrolments, three mock payments, customer entitlements, owner contribution visibility, and exact liability/activity deltas.
- Live GoldAPI HTTP behavior is verified at the adapter boundary with deterministic mocked responses; no real provider request was made because no API key is stored in the repository.
- Live-server recovery smoke passes across a rate-failure/server-restart/rate-restoration sequence: verified payment remains unallocated, owner retry creates exactly one 0.800000 g allocation, and all disposable records are removed.

## Next recommended step

Milestone 6 — Razorpay test mode with verified, idempotent callbacks/webhooks.
