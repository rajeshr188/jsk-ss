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
- **CON-003:** `ONCE_PER_MONTH` permits one successfully paid contribution per scheme account and calendar month. Both `PAID` and `PAID_UNALLOCATED` consume the opportunity; `PENDING` and `FAILED` attempts do not.
- **CON-004:** `FLEXIBLE` permits multiple successful contributions in the same calendar month.
- **CON-005:** Fixed contributions must exactly equal the snapshotted fixed amount. Variable contributions must remain within snapshotted minimum/maximum boundaries.
- **CON-006:** Contributions are rejected before the account start date, after redemption, and after eligibility unless the agreement snapshot explicitly permits them.

## Payment and metal rules

- **PAY-001 / FIN-001:** One successful payment benefits a customer at most once; server verification and idempotency are mandatory.
- **PAY-002 / FIN-005:** Failed payments create no entitlement.
- **PAY-003:** The mock gateway is available only with `DEBUG=True` and `PAYMENT_GATEWAY=mock`; it never represents a real transfer.
- **PAY-004:** Milestone 6 permits only Razorpay test keys. Browser success is not entitlement until HMAC verification and a server-side captured-payment check match the locally stored order, amount, and INR currency.
- **PAY-005:** Only a signed `payment.captured` webhook may independently confirm a Razorpay contribution. Signature verification uses the untouched request body.
- **PAY-006:** Razorpay order IDs, payment IDs, and webhook event IDs are unique at their respective database boundaries. Duplicate callbacks or webhook deliveries return the existing result and create no additional entitlement.
- **PAY-007:** A once-per-month account may have at most one pending Razorpay contribution for a calendar period. Reopening the payment flow resumes the existing order.
- **PAY-008:** Provider callbacks are matched to a customer-owned local contribution; the browser-supplied order ID is never trusted in place of the database value.
- **METAL-001 / FIN-002:** A metal contribution creates at most one successful allocation.
- **METAL-002 / FIN-003:** A rate snapshot used by an allocation is immutable.
- **METAL-003 / FIN-004:** Historical allocated grams never change with current market rates.
- **METAL-004:** A successful metal payment with no valid rate becomes `PAID_UNALLOCATED`; it retains payment confirmation, creates no snapshot/allocation, and no rate may be invented.
- **METAL-005:** Mock rates are available only with `DEBUG=True` and `METAL_RATE_PROVIDER=mock`.
- **METAL-006:** Allocation quantity equals INR contribution divided by the snapshotted applied rate per gram, rounded to 6 decimal places using `ROUND_HALF_UP`.
- **METAL-007:** Provider rate, applied rate, provider timestamp, fetched timestamp, purity, and metal are stored with each rate snapshot. Changing configured rates affects only future allocations.
- **METAL-008:** `METAL_RATE_PROVIDER=goldapi` uses authenticated HTTPS XAU/XAG-to-INR requests. The API key is sent in a header and must remain outside source control.
- **METAL-009:** Live responses must match the requested metal and INR currency and contain a positive per-gram rate and valid provider timestamp before allocation.
- **METAL-010:** Provider, network, or configuration failure after payment confirmation is recoverable only through the owner-controlled, idempotent allocation retry workflow.
- **METAL-011:** A successful retry changes `PAID_UNALLOCATED` to `PAID`, clears the current allocation error, and still permits at most one `RateSnapshot` and `MetalAllocation` for the contribution.

## Cash bonus rules

- **BON-001:** A scheme plan may define a cash bonus percentage from 0% through 100%
  and a minimum qualifying duration of at least 12 months. Zero percent disables bonus.
- **BON-002 / FIN-009:** Enrolment snapshots the bonus policy version, percentage, and
  qualifying months. Later plan edits never change an existing agreement.
- **BON-003:** Cash bonus applies only to `CASH` accounts whose agreed duration meets
  the snapshotted minimum. Gold and silver entitlements never receive cash bonus.
- **BON-004:** Before `eligible_from`, projected bonus is the snapshotted percentage of
  cash principal paid so far, rounded to money precision. It is an estimate only: it
  is not redeemable and is not an actual owner liability.
- **BON-005:** On and after `eligible_from`, earned bonus is calculated from successful
  cash principal paid no later than the end of the eligibility date. Contributions
  made after that cutoff remain principal but do not retroactively earn bonus.
- **BON-006:** Cash redeemable amount equals outstanding principal plus outstanding
  earned bonus. Partial cash redemptions consume principal first and then earned
  bonus; both immutable components must sum to the redemption's cash total.
- **BON-007:** Bonus calculation uses the policy-version service and `Decimal` with
  `ROUND_HALF_UP` to two decimal places.

## Redemption and financial invariants

- **RED-001 / FIN-006:** A customer cannot redeem more than the outstanding entitlement.
- **RED-002:** Before redemption, effective status is derived in the India-local calendar: before `eligible_from` is `ACTIVE / NOT YET ELIGIBLE`; on or after `eligible_from` is `REDEMPTION_ELIGIBLE`.
- **RED-003:** Reaching `eligible_from` never closes an account, mutates its stored status, or creates a redemption. Only a completed redemption may make it `REDEEMED`.
- **RED-004:** Owner forecast bands are exclusive: eligible now, days 1–30, days 31–60, and days 61–90. Redeemed accounts are excluded from every open-account band.
- **RED-005:** A completed redemption is an immutable, owner-recorded financial event. Contributions, allocations, and earlier redemptions remain visible.
- **RED-006:** Cash principal outstanding equals paid cash contributions minus the
  principal components of completed redemptions; cash redeemable amount adds only
  outstanding earned bonus. Gold and silver outstanding each equal paid allocated
  grams minus completed redemptions in the same metal.
- **RED-007:** Cash accounts may settle as `CASH` or `JEWELLERY_PURCHASE`; gold and silver accounts may settle as `METAL` or `JEWELLERY_PURCHASE`. Metal-to-cash conversion is undefined and rejected.
- **RED-008:** Partial redemption leaves an eligible account open. Redeeming the exact remaining entitlement changes its stored status to `REDEEMED`.
- **RED-009:** Every redemption submission has a unique idempotency key. Replaying the same key and details returns the existing event; changing details with a used key is rejected.
- **RED-010:** Jewellery-purchase redemption requires an external invoice or sales reference. The MVP records the reference, entitlement settled, and notes but does not manage inventory or invoices.
- **RED-011:** A redemption correction appends one immutable `RedemptionReversal`; it never edits or deletes the original redemption. Reversed settlements are excluded from outstanding-balance and liability subtraction.
- **RED-012:** Reversing any settlement restores that denomination's entitlement. If the account was fully redeemed, the stored account status reopens to `ACTIVE`; date-derived eligibility still presents it as redemption eligible.
- **FIN-007:** Gold, silver, and INR liabilities are never combined into a single balance.
- **FIN-008:** All financial calculations use `Decimal` with explicit rounding.
- **FIN-009:** Editing a plan does not rewrite existing account economic terms.
- **FIN-010:** Owner liability aggregates reconcile with underlying customer obligations.
- **FIN-011:** Payment success is verified server-side.
- **FIN-012:** Corrections preserve audit history rather than silently rewriting financial records.

## Audit and exception rules

- **AUD-001:** Customer enrolment, scheme-plan change, redemption, redemption reversal, and owner-triggered allocation retry retain an actor label, timestamp, reason, target, and action details in an immutable audit event.
- **AUD-002:** System-service actions may retain a stable system actor label when no authenticated user initiated them. Owner UI actions always reference the authenticated owner as actor.
- **AUD-003:** Audited plan changes affect only future enrolments; existing agreement snapshots remain unchanged.
- **AUD-004:** Manual payment correction and manual rate override must not be enabled until explicit accounting/pricing and approval rules exist. Reserved audit action names do not authorize those mutations.
- **EXC-001:** The owner exception queue derives unresolved paid-unallocated/failed-allocation contributions and failed or mismatched webhook reconciliation from their authoritative source records.
- **EXC-002:** Resolving an allocation exception uses the existing idempotent retry service. A queue display or acknowledgement must never itself create entitlement.

## Owner liability reporting

- **LIA-001:** Outstanding cash principal is paid cash contributions minus completed cash redemptions. Pending and failed attempts contribute zero.
- **LIA-002:** Outstanding gold and silver quantities are paid allocations minus completed redemptions in the matching metal. The primary metal liabilities remain grams.
- **LIA-003:** Indicative metal exposure equals outstanding grams multiplied by the current applied reference rate, rounded to 2 money decimal places with `ROUND_HALF_UP`. It does not rewrite historical allocations.
- **LIA-004:** Cash principal, gold exposure, and silver exposure are never added into a single headline liability total.
- **LIA-005:** If a current rate is unavailable, the dashboard must continue showing authoritative gram liabilities and explicitly mark reference rate and exposure as unavailable.
- **LIA-006:** Dashboard contribution counts include both `PAID` and `PAID_UNALLOCATED` verified payments and use `paid_at` within India-local calendar-day and calendar-month boundaries.
- **LIA-007:** Owner cash obligations show outstanding principal and earned bonus as
  actual redeemable liability. Projected bonus exposure is shown separately and is
  never added to actual cash liability.

## Precision

Money uses 2 decimal places. Contribution and cash-redemption input with more than 2 decimal places is rejected rather than silently rounded. Cash bonus calculations use `ROUND_HALF_UP` to 2 decimal places. Metal quantities and metal-redemption input use 6 decimal places; excess precision is rejected. Allocation calculations use `ROUND_HALF_UP`. Rates and purity metadata use 4 decimal places; mock configuration is normalized with `ROUND_HALF_UP`.
