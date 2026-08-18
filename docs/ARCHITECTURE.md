# Architecture

## System context

This is a server-rendered, single-business Django application. Customers authenticate by email through django-allauth. Owners manage customers and enrolments; customers can view only their own scheme accounts.

## Django apps

- `accounts`: Lithium's custom user, allauth integration, and simple `OWNER`/`STAFF`/`CUSTOMER` application roles.
- `pages`: public landing and about pages.
- `schemes`: customer profiles, reusable plans, scheme agreements, contributions, payment boundary, services, selectors, forms, and owner/customer views.

## Model relationships

```mermaid
graph TD
  U[accounts.CustomUser] -->|one-to-one| C[Customer]
  C -->|one-to-many| A[SchemeAccount]
  P[SchemePlan] -->|one-to-many| A
  A -->|one-to-many| N[Contribution]
  N -->|zero-or-one| M[MetalAllocation]
  M -->|one-to-one| R[RateSnapshot]
```

`SchemeAccount` snapshots plan terms during enrolment so later plan edits do not change existing agreements.

## Layers

- Views authorize, validate forms, call services/selectors, and render or redirect.
- Services own transactional mutations such as customer creation and enrolment.
- Selectors own reusable reads such as customer scheme summaries.
- Models and database constraints protect structural invariants.

## Authentication and authorization

Lithium's `CustomUser` and django-allauth remain authoritative. Superusers and `OWNER` users have owner access. Customer queries are always scoped through the authenticated user's one-to-one `Customer` record.

Public customer signup is intentionally closed during the MVP. The owner creates a customer login and profile together, then explicitly enrols that customer into a scheme agreement. This prevents an allauth login from being mistaken for an active financial agreement.

### Future public customer signup

If public signup is introduced later, registration must create a complete customer profile transactionally and place it in an explicit not-yet-enrolled/awaiting-approval state. Email verification, duplicate email/mobile handling, terms and privacy consent, abuse controls, and clear status language are required. Owner approval must remain mandatory before a `SchemeAccount` is created or any payment is accepted. Prefer an email invitation/password-setup flow before open self-registration; do not merely reopen the default allauth signup form.

## Financial source of truth

Cash principal is derived by selectors from `PAID` contribution records; pending and failed attempts contribute zero. Gold and silver balances are derived from immutable `MetalAllocation` quantities attached one-to-one to paid contributions. Historical `RateSnapshot` and allocation records reject application-level edits. Future redemption balances must likewise be derived from redemptions and auditable corrections—not mutable balance fields.

`MockPaymentGateway` is the only payment adapter currently implemented. It can be resolved only when `DEBUG=True` and `PAYMENT_GATEWAY=mock`. A result must be verified before confirmation changes `PENDING` to `PAID`.

`MockMetalRateProvider` implements the separate rate boundary and can be resolved only when `DEBUG=True` and `METAL_RATE_PROVIDER=mock`. It returns provider/applied rates, provider timestamp, and purity metadata. The allocation service snapshots the quote and calculates grams in the same database transaction as the mock payment workflow. External payment and metal-rate providers remain deferred.

## Current request flows

Owner: login → dashboard → customers → add customer → customer detail → enrol customer.

Customer: login → My Schemes → account terms. Login routing is role-aware.

Cash contribution: customer account → Pay now → validate snapshotted amount/frequency rules → create pending contribution → verified mock result → idempotent confirmation → derived cash balance.

Metal contribution: customer account → Pay now → verified contribution → mock rate quote → immutable rate snapshot → one immutable six-decimal allocation → derived gold or silver gram balance.
