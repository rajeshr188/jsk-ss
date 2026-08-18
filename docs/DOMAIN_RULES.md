# Domain Rules

This is the canonical source for stable business rules.

## Authentication and onboarding rules

- **AUTH-001:** A login account is not itself an active savings agreement; only a valid `SchemeAccount` represents enrolment.
- **AUTH-002:** During the MVP, owners create customer credentials and profiles together; public signup remains closed.
- **AUTH-003:** Future public registration must create a complete customer profile, verify identity/contact data as configured, and remain awaiting owner approval until enrolment.
- **AUTH-004:** No publicly registered but unenrolled customer may contribute. Reopening allauth signup alone is insufficient.

## Scheme and contribution rules

- **SCH-001:** Savings modes are separate `CASH`, `GOLD`, and `SILVER` liability dimensions.
- **SCH-002:** An account snapshots the plan's economic terms at enrolment; later plan edits do not rewrite the agreement.
- **SCH-003:** Minimum and default durations are at least 12 months; the agreed duration cannot be below the plan minimum.
- **SCH-004:** Eligibility is the account start date plus agreed calendar months. Eligibility does not itself redeem or close an account.
- **CON-001:** Amount rules (`FIXED`/`VARIABLE`) and frequency rules (`ONCE_PER_MONTH`/`FLEXIBLE`) are independent.
- **CON-002:** Monthly periods use deterministic calendar keys such as `2026-08`, never rolling 30-day windows.
- **CON-003:** `ONCE_PER_MONTH` permits one `PAID` contribution per scheme account and calendar month. `PENDING` and `FAILED` attempts do not consume the opportunity.
- **CON-004:** `FLEXIBLE` permits multiple successful contributions in the same calendar month.
- **CON-005:** Fixed contributions must exactly equal the snapshotted fixed amount. Variable contributions must remain within snapshotted minimum/maximum boundaries.
- **CON-006:** Contributions are rejected before the account start date, after redemption, and after eligibility unless the agreement snapshot explicitly permits them.

## Payment and metal rules

- **PAY-001 / FIN-001:** One successful payment benefits a customer at most once; server verification and idempotency are mandatory.
- **PAY-002 / FIN-005:** Failed payments create no entitlement.
- **PAY-003:** The mock gateway is available only with `DEBUG=True` and `PAYMENT_GATEWAY=mock`; it never represents a real transfer.
- **METAL-001 / FIN-002:** A metal contribution creates at most one successful allocation.
- **METAL-002 / FIN-003:** A rate snapshot used by an allocation is immutable.
- **METAL-003 / FIN-004:** Historical allocated grams never change with current market rates.
- **METAL-004:** A successful metal payment with no valid rate becomes clearly paid-but-unallocated; no rate may be invented.
- **METAL-005:** Mock rates are available only with `DEBUG=True` and `METAL_RATE_PROVIDER=mock`.
- **METAL-006:** Allocation quantity equals INR contribution divided by the snapshotted applied rate per gram, rounded to 6 decimal places using `ROUND_HALF_UP`.
- **METAL-007:** Provider rate, applied rate, provider timestamp, fetched timestamp, purity, and metal are stored with each rate snapshot. Changing configured rates affects only future allocations.

## Redemption and financial invariants

- **RED-001 / FIN-006:** A customer cannot redeem more than the outstanding entitlement.
- **FIN-007:** Gold, silver, and INR liabilities are never combined into a single balance.
- **FIN-008:** All financial calculations use `Decimal` with explicit rounding.
- **FIN-009:** Editing a plan does not rewrite existing account economic terms.
- **FIN-010:** Owner liability aggregates reconcile with underlying customer obligations.
- **FIN-011:** Payment success is verified server-side.
- **FIN-012:** Corrections preserve audit history rather than silently rewriting financial records.

## Precision

Money uses 2 decimal places. Contribution input with more than 2 decimal places is rejected rather than silently rounded. Metal quantities use 6 decimal places and `ROUND_HALF_UP`. Rates and purity metadata use 4 decimal places; mock configuration is normalized with `ROUND_HALF_UP`.
