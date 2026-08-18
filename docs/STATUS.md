# Project Status

## Current milestone

Milestone 2 — Cash contributions with mock payment (complete)

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

## In progress

- None.

## Known issues

- None currently identified in implemented scope.

## Deferred

- Real payment providers, rates, metal allocations, liability reporting, and redemption.

## Verification

- PostgreSQL 16 migrations applied successfully.
- 26 tests pass, including payment rules, idempotency, database constraints, authorization, and isolation.
- Django system check and migration drift check pass.
- Production static collection and deployment check pass with preload explicitly enabled.
- Live-server smoke flow passes: customer mock payment, derived cash balance/history, monthly duplicate rejection, and owner visibility.

## Next recommended step

Milestone 3 — Gold and silver allocation using immutable mock rate snapshots.
