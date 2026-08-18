# Domain Rules

This is the canonical source for stable business rules.

## Scheme and contribution rules

- **SCH-001:** Savings modes are separate `CASH`, `GOLD`, and `SILVER` liability dimensions.
- **SCH-002:** An account snapshots the plan's economic terms at enrolment; later plan edits do not rewrite the agreement.
- **SCH-003:** Minimum and default durations are at least 12 months; the agreed duration cannot be below the plan minimum.
- **SCH-004:** Eligibility is the account start date plus agreed calendar months. Eligibility does not itself redeem or close an account.
- **CON-001:** Amount rules (`FIXED`/`VARIABLE`) and frequency rules (`ONCE_PER_MONTH`/`FLEXIBLE`) are independent.
- **CON-002:** Monthly periods use deterministic calendar keys such as `2026-08`, never rolling 30-day windows.

## Payment and metal rules

- **PAY-001 / FIN-001:** One successful payment benefits a customer at most once; server verification and idempotency are mandatory.
- **PAY-002 / FIN-005:** Failed payments create no entitlement.
- **METAL-001 / FIN-002:** A metal contribution creates at most one successful allocation.
- **METAL-002 / FIN-003:** A rate snapshot used by an allocation is immutable.
- **METAL-003 / FIN-004:** Historical allocated grams never change with current market rates.
- **METAL-004:** A successful metal payment with no valid rate becomes clearly paid-but-unallocated; no rate may be invented.

## Redemption and financial invariants

- **RED-001 / FIN-006:** A customer cannot redeem more than the outstanding entitlement.
- **FIN-007:** Gold, silver, and INR liabilities are never combined into a single balance.
- **FIN-008:** All financial calculations use `Decimal` with explicit rounding.
- **FIN-009:** Editing a plan does not rewrite existing account economic terms.
- **FIN-010:** Owner liability aggregates reconcile with underlying customer obligations.
- **FIN-011:** Payment success is verified server-side.
- **FIN-012:** Corrections preserve audit history rather than silently rewriting financial records.

## Precision

Money uses 2 decimal places, metal quantities 6 decimal places, and rates per gram 4 decimal places. Exact rounding rules will be fixed alongside the first contribution/allocation implementation.

