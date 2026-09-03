# ADR-0007 — Use Grade-Specific Metal Contracts and Scheme Rates

## Context

The original metal architecture treated `GOLD` as 24K fineness `0.9999` and
`SILVER` as fineness `0.9990`. A single rate stream per base metal was sufficient
for that model, but customers generally enrol in 22K gold plans. Relabelling an
existing 24K account, rate, allocation, or redemption as 22K would falsify the
historical contract. Deriving one grade's customer rate from another grade would
also introduce an implicit pricing rule that the owner did not publish.

The application stores metal quantities to six decimal places. Showing all six on
customer pages creates visual noise, but reducing stored precision or rounding
financial mutations to three decimals can accumulate error and can strand a small
balance at final redemption.

## Decision

Introduce immutable `MetalGrade` reference records and identify each grade by a
stable code. The initial definitions are:

- `GOLD_22K_916` — Gold, fineness `0.916000`;
- `GOLD_24K_9999` — Gold, fineness `0.999900`;
- `SILVER_999` — Silver, fineness `0.999000`.

A `SchemePlanOffering` explicitly states which grades a plan offers for new
enrolment. Each metal `SchemeAccount` is permanently tied to exactly one grade.
`SchemeRate`, `MetalAllocation`, and metal `Redemption` records carry that grade,
and services require the account, locked rate, allocation, and redemption to match.
Base-metal fields remain as historical snapshots and for Gold/Silver operational
pauses, but they are not sufficient to select a rate or combine a liability.

An owner publishes a manual rate for each exact grade. Current-rate selection and
payment eligibility are grade-specific. No 22K rate is automatically derived from a
24K rate, and no grade falls back to another grade's rate. A new grade therefore
requires an explicit immutable definition, a plan offering, an owner-published rate,
and tests before it can accept payment.

Migration `schemes.0015_graded_metal_rates` maps every historical Gold account,
rate, allocation, and redemption to `GOLD_24K_9999`, and every historical Silver
record to `SILVER_999`; it performs no quantity or value conversion. It enables
22K Gold and 999 Silver offerings for new enrolment on existing plans while leaving
the legacy 24K offering disabled. Migration `schemes.0016` widens rate fineness
metadata to six decimals and updates base-metal display labels.

Financial quantities and calculations remain `Decimal` values stored and rounded to
six decimal places. Customer pages render grams to three decimal places. Owner
settlement entry, integrity checks, and CSV/source records retain six decimals so an
exact final redemption remains possible. Display rounding never changes the ledger.

## Consequences

22K and 24K Gold now have independent rates, liabilities, payment availability, and
history. Existing 24K customers continue using their original rate stream and are
not silently converted. Owners must publish every offered grade that should be open
for payment, and the payment-operations screen may show one Gold grade open while
another is unavailable because its rate is missing.

The schema keeps some deliberate redundancy (`metal`, `purity`, and `metal_grade`)
to make historical records self-describing. Model validation, service checks, a
deployment integrity command, and database constraints where cross-table rules
permit guard that redundancy. Adding automatic purity conversion remains out of
scope unless the business first defines rounding, premium, tax, effective-time, and
audit rules in a later ADR.
