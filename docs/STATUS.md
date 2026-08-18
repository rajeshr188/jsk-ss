# Project Status

## Current milestone

Milestone 3 — Gold and silver allocation with mock rates (complete)

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
- Future public-signup requirements documented under `AUTH-*` domain rules.

## In progress

- None.

## Known issues

- None currently identified in implemented scope.

## Deferred

- Real payment/rate providers, paid-unallocated retry handling, liability reporting, and redemption.

## Verification

- PostgreSQL 16 migrations applied successfully.
- 38 tests pass, including exact metal calculations, historical-rate stability, payment/allocation idempotency, database constraints, authorization, and isolation.
- Django system check and migration drift check pass.
- Production static collection and deployment check pass with preload explicitly enabled.
- Live-server smoke flow passes for gold and silver mock payments, immutable rate snapshots, derived gram balances/history, and owner visibility.

## Next recommended step

Milestone 4 — Owner liability dashboard across separate INR, gold, and silver dimensions.
