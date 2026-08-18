# Project Status

## Current milestone

Milestone 1 — Customer and scheme enrolment (complete)

## Completed

- Lithium authentication, Bootstrap/crispy forms, WhiteNoise, and custom user preserved.
- PostgreSQL-only environment configuration and India time zone.
- Jai Shri Krishna Jewellery branding and canonical documentation.
- Owner/customer roles, customer records, reusable plans, and snapshotted enrolments.
- Owner customer-management flow and isolated customer scheme view.

## In progress

- None.

## Known issues

- None currently identified in implemented scope.

## Deferred

- Contributions, payment providers, rates, metal allocations, liability reporting, and redemption.

## Verification

- PostgreSQL 16 migrations applied successfully.
- 12 tests pass, including authentication, snapshotting, authorization, and isolation.
- Django system check and migration drift check pass.
- Production static collection and deployment check pass with preload explicitly enabled.
- Live-server smoke flow passes: login/logout, reset request, admin, owner customer/enrolment flow, and customer scheme view.

## Next recommended step

Milestone 2 — Cash contributions using the debug-only mock payment adapter.
