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
- **SCH-005:** A plan appears on the public plans and pricing page only when it is both active and explicitly marked publicly listed. New and migrated plans default to not publicly listed.
- **SCH-006:** Public plan edits affect the current offer for future enrolments only; existing scheme accounts retain their snapshotted economic terms.
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
- **METAL-002 / FIN-003:** A Scheme Rate used by an allocation is immutable.
- **METAL-003 / FIN-004:** Historical allocated grams never change when a newer Scheme Rate is published.
- **METAL-004:** Allocation quantity equals INR contribution divided by the locked Scheme Rate per gram, rounded to 6 decimal places using `ROUND_HALF_UP`.
- **METAL-005:** `PAID_UNALLOCATED` is reserved for an unexpected allocation exception after a verified payment; it is not a missing-rate workflow. Retry must reuse the contribution's original lock.
- **RATE-001:** Only a manually published Jai Shri Krishna Jewellery `SchemeRate` may be used for a new gold or silver allocation.
- **RATE-002:** A metal contribution must lock its current applicable `SchemeRate` before mock payment initiation or Razorpay order creation.
- **RATE-003:** Publishing a new `SchemeRate` never changes an already locked contribution.
- **RATE-004:** Publishing a new `SchemeRate` never changes historical `MetalAllocation` quantity.
- **RATE-005:** A gold or silver payment cannot be initiated when no valid current `SchemeRate` exists. Cash payment remains unaffected.
- **RATE-006:** Published Scheme Rates used by financial allocations are immutable and protected from deletion.
- **RATE-007:** Current rate means the latest applicable record for the metal ordered by `effective_from`, publication time, and ID. Publication appends a record; there is no mutable active flag.
- **RATE-008:** Gold uses the established 24K fineness `0.9999`; silver uses `0.9990`. Publication accepts a positive `Decimal` rate only.
- **RATE-009:** Only an active owner or superuser may publish. Every publication records publisher, timestamp, optional note, and immutable audit event.

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

- **AUD-001:** Customer enrolment, scheme-plan change, Scheme Rate publication, redemption, redemption reversal, and owner-triggered allocation retry retain an actor label, timestamp, reason, target, and action details in an immutable audit event.
- **AUD-002:** System-service actions may retain a stable system actor label when no authenticated user initiated them. Owner UI actions always reference the authenticated owner as actor.
- **AUD-003:** Audited plan changes affect only future enrolments; existing agreement snapshots remain unchanged.
- **AUD-004:** Manual payment correction must not be enabled until explicit accounting and approval rules exist. Scheme Rate publication is a supported append-only workflow, not a historical-rate override.
- **EXC-001:** The owner exception queue derives unresolved paid-unallocated/failed-allocation contributions and failed or mismatched webhook reconciliation from their authoritative source records.
- **EXC-002:** Resolving an allocation exception uses the existing idempotent retry service. A queue display or acknowledgement must never itself create entitlement.

## Owner liability reporting

- **LIA-001:** Outstanding cash principal is paid cash contributions minus completed cash redemptions. Pending and failed attempts contribute zero.
- **LIA-002:** Outstanding gold and silver quantities are paid allocations minus completed redemptions in the matching metal. The primary metal liabilities remain grams.
- **LIA-003:** Indicative metal exposure equals outstanding grams multiplied by the current Scheme Rate, rounded to 2 money decimal places with `ROUND_HALF_UP`. It does not rewrite historical allocations.
- **LIA-004:** Cash principal, gold exposure, and silver exposure are never added into a single headline liability total.
- **LIA-005:** If a current Scheme Rate is unavailable, the dashboard must continue showing authoritative gram liabilities and explicitly mark the rate and exposure as unavailable.
- **LIA-006:** Dashboard contribution counts include both `PAID` and `PAID_UNALLOCATED` verified payments and use `paid_at` within India-local calendar-day and calendar-month boundaries.
- **LIA-007:** Owner cash obligations show outstanding principal and earned bonus as
  actual redeemable liability. Projected bonus exposure is shown separately and is
  never added to actual cash liability.

## Receipt, statement, and export rules

- **DOC-001:** Only verified `PAID` or `PAID_UNALLOCATED` contributions receive a receipt. Pending and failed attempts are not acknowledged as received funds.
- **DOC-002:** A receipt reference is deterministic and stable as `JSK-RCT-<paid year>-<zero-padded contribution ID>`; reprinting does not create or renumber a financial event.
- **DOC-003:** Metal receipts and statements use the immutable allocation's Scheme Rate and quantity. A paid-unallocated record displays allocation pending with no invented rate or grams.
- **DOC-004:** A scheme statement includes verified payments, allocations, redemptions, and reversals and reports the current remaining entitlement in the scheme's denomination. Projected cash bonus remains separately labelled and non-redeemable.
- **DOC-005:** Customer documents are accessible only to that customer or an owner. Owner CSV exports require owner authorization and neutralize spreadsheet-formula text.
- **DOC-006:** INR amounts, gold grams, and silver grams remain separate in documents and exports. Indicative current metal exposure is not exported as booked cash liability.
- **DOC-007:** MVP documents are on-demand printable HTML acknowledgements, not tax invoices or archived legal snapshots.

## Precision

Money uses 2 decimal places. Contribution and cash-redemption input with more than 2 decimal places is rejected rather than silently rounded. Cash bonus calculations use `ROUND_HALF_UP` to 2 decimal places. Metal quantities and metal-redemption input use 6 decimal places; excess precision is rejected. Allocation calculations use `ROUND_HALF_UP`. Scheme Rates and purity metadata use 4 decimal places.
