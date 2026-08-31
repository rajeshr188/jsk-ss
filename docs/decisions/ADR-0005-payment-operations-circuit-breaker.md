# ADR-0005 — Use a Domain-Specific Payment Operations Circuit Breaker

## Context

Extreme metal-price volatility, non-office hours, holidays, or an operational
incident may require Jai Sri Krishna Jewellery to stop creating new payment exposure
immediately. The application must distinguish that action from processing money
already in flight. A Razorpay order can be attempted after local creation, Razorpay's
published Orders API provides no cancellation operation, and callbacks or webhooks
may arrive after an owner closes the customer-facing Checkout.

The application locks an immutable `SchemeRate` before creating a Razorpay order.
Once the corresponding payment is captured, delaying allocation does not remove the
economic commitment; the customer's quantity must still use that original lock.
Disabling `PAYMENT_GATEWAY`, changing credentials, or rejecting the webhook endpoint
would instead hide captured funds and weaken reconciliation.

django-waffle was considered because it supplies database-backed feature switches.
Its switches are global booleans intended for feature rollout. They do not model a
timezone-aware weekly calendar, per-metal financial state, current-rate approval,
mandatory operator reasons, immutable audit evidence, or safe precedence between
scheduled and emergency controls.

## Decision

Introduce a domain-specific, single-business `PaymentOperationsControl` with one
weekly `PaymentScheduleWindow` per India-local weekday. Migration `schemes.0013`
creates the singleton and seeds the reviewed showroom schedule: Monday through
Saturday 09:00–21:00 and Sunday 09:00–13:00. The recurring schedule is default-off,
so applying the migration cannot unexpectedly change production availability. An
owner must review and enable it explicitly.

The effective new-payment decision uses this precedence:

1. `PAYMENT_INITIATION_KILL_SWITCH=True` closes new payment exposure.
2. An audited global manual pause closes both metals.
3. An audited Gold or Silver pause closes that metal.
4. When enabled, the weekly schedule closes payments outside the half-open local
   interval `[opens_at, closes_at)`.
5. A current applicable `SchemeRate` must exist. When scheduled daily-rate review is
   enabled, its publication date must equal the current Asia/Kolkata date.

The decision is enforced in the financial service before a local contribution is
created and again while the singleton control is row-locked immediately before an
existing order is returned or a provider order is created. Customer views use the
same policy to remove Pay/Resume actions and explain temporary closure, but the
service remains authoritative. A pause and order creation therefore have a defined
database-lock order; an order that completed creation first is treated as in flight.

Callbacks, signed webhooks, server-side captured-payment verification, idempotent
confirmation, and allocation from the locked Scheme Rate never consult this
new-payment gate. They remain operational at all hours. Routine business-hours or
volatility closure does not create `PAID_UNALLOCATED` records deliberately. A future
allocation-integrity hold may be designed separately for a confirmed software/data
incident, but it must not be presented as protection from market exposure.

Every owner change requires a reason and appends one immutable
`PAYMENT_OPERATIONS_CHANGE` audit event containing the complete before/after policy.
The environment kill switch is a secondary deployment-level fail-safe; it cannot be
cleared through the owner UI and requires web-service recreation.

## Consequences

Owners can close new Gold, Silver, or all online contributions immediately and can
apply predictable non-office-hour closure without redeploying. Customers retain
read-only access to their schemes and see the next known scheduled opening. Pending
locked Razorpay orders remain visible as contingent exposure, while a captured
payment continues to become exactly one entitlement at its original rate.

The database gains one mutable operational-policy row and seven mutable schedule
rows. They are not financial source-of-truth records; immutable `AuditEvent` records
preserve every owner transition. Schedule changes and manual resumes require owner
training because an incorrect opening window can make Checkout unavailable or open
at an unintended time. The default-off migration and dashboard status reduce rollout
risk.

The first implementation supports one opening window per weekday and no separately
modeled holiday exceptions or temporary force-open expiry. Add those only when the
business defines their approval and audit semantics. django-waffle remains suitable
for unrelated feature rollout but is not a financial authorization dependency.
