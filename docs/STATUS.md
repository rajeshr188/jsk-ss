# Project Status

## Current milestone

MVP Alpha checkpoint (complete)

## Completed

- Lithium authentication, Bootstrap/crispy forms, WhiteNoise, and custom user preserved.
- PostgreSQL-only environment configuration and India time zone.
- Jai Shri Krishna Jewellery branding and canonical documentation.
- Owner/customer roles, customer records, reusable plans, and snapshotted enrolments.
- Owner customer-management flow and isolated customer scheme view.
- Append-oriented cash contributions with pending/paid/failed states.
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
- Future public-signup requirements documented under `AUTH-*` domain rules.

## In progress

- None.

## Known issues

- None currently identified in implemented scope.

## Deferred

- Real payment/rate providers, paid-unallocated retry handling, and redemption.

## Verification

- PostgreSQL 16 migrations applied successfully.
- 44 tests pass, including liability reconciliation, current-exposure rounding, independently unavailable rates, India-local activity periods, authorization, and prior financial regressions.
- Django system check and migration drift check pass.
- Production static collection and deployment check pass with preload explicitly enabled.
- Live-server checkpoint passes for owner and customer login, UI-created plan/customer/CASH-GOLD-SILVER enrolments, three mock payments, customer entitlements, owner contribution visibility, and exact liability/activity deltas.

## Next recommended step

Milestone 5 — integrate a live metal-rate provider behind the existing provider boundary.
