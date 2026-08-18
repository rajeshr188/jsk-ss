# Architecture

## System context

This is a server-rendered, single-business Django application. Customers authenticate by email through django-allauth. Owners manage customers and enrolments; customers can view only their own scheme accounts.

## Django apps

- `accounts`: Lithium's custom user, allauth integration, and simple `OWNER`/`STAFF`/`CUSTOMER` application roles.
- `pages`: public landing and about pages.
- `schemes`: customer profiles, reusable plans, scheme agreements, enrolment services, selectors, forms, and owner/customer views.

## Model relationships

```mermaid
graph TD
  U[accounts.CustomUser] -->|one-to-one| C[Customer]
  C -->|one-to-many| A[SchemeAccount]
  P[SchemePlan] -->|one-to-many| A
```

`SchemeAccount` snapshots plan terms during enrolment so later plan edits do not change existing agreements.

## Layers

- Views authorize, validate forms, call services/selectors, and render or redirect.
- Services own transactional mutations such as customer creation and enrolment.
- Selectors own reusable reads such as customer scheme summaries.
- Models and database constraints protect structural invariants.

## Authentication and authorization

Lithium's `CustomUser` and django-allauth remain authoritative. Superusers and `OWNER` users have owner access. Customer queries are always scoped through the authenticated user's one-to-one `Customer` record.

## Financial source of truth

No balances exist yet. Future balances must be derived from successful contributions, metal allocations, redemptions, and auditable corrections—not mutable balance fields.

Payment and metal-rate provider boundaries are deferred until their milestones.

## Current request flows

Owner: login → dashboard → customers → add customer → customer detail → enrol customer.

Customer: login → My Schemes → account terms. Login routing is role-aware.

