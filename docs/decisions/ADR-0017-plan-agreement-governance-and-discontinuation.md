# ADR-0017: Plan governance and explicit agreement discontinuation

## Status

Direction approved by the owner on 22 October 2026, then expanded to an owner-led
configurable plan builder and **full-only redemption**. Preserve A's revision and
agreement foundation; implement policy/instalment support before completing B.
Phase A is local on `agent/plan-agreement-governance`. Builder and closure rules below
are approved architecture, not available in production. P1a's preparation-only catalogue
and P1b's gated contract integration are now local. B1's configured-only closure-request
lifecycle, B2 unused cancellation and B3 configured full-settlement services are local;
B3 automated verification passed; owner/mobile and broader release acceptance remain open. Track execution
in MVP_PLAN.md and FUTURE_WORK.md. Customer-authored configurations are explicitly later.

## Context

### 24 October 2026 - coherent builder-v1 release boundary

Owner approved completing a bounded owner-builder v1 before production activation,
rather than releasing the currently implemented subset first. Incremental development,
review and CI remain required behind the disabled configured-plans gate; they are not
separate business releases. The acceptance matrix and completion checklist are tracked
at the top of MVP_PLAN.md and supersede earlier subset-first release sequencing.

Remaining targets include INR purchase credit, count-only/anytime eligibility and
defined benefits. This decision approves sequencing and scope preparation, not an
unspecified bonus formula, invoice remainder policy, cash payout or permission to
bypass the existing INR business/legal/accounting/provider boundary. Finalise explicit
compatible terms before implementing those financial workflows. Any reduction of the
agreed release scope requires owner approval, not silent exclusion to meet a release.
Customer-authored configurations remain later; all new supported plans remain full-only.
Existing immutable agreements and their liabilities are not converted by this decision.

### 24 October 2026 — independent dimensions and calendar-month obligations

Owner approved: enrolment month is the first required calendar month, including a
short first period (30 January enrolment owes January before 1 February); an
enrolment-day payment qualifies when otherwise valid. February is not silently
substituted as the first obligation. Retain anniversary schedules as a separate choice.

Recommended policy adopted for this implementation:

- Required count equals agreed months. Normal eligibility is the later of the
  original `start_date + agreed_months` date and the last qualifying period end.
  Twelve timely January–December payments after a 30 January 2026 start therefore
  wait until 30 January 2027, not 1 January. Once the count is complete, no extra
  payment is accepted merely because the minimum-duration date has not arrived.
- Calendar periods are half-open India-local windows: first `[enrolment, next month)`;
  thereafter whole calendar months. Midnight belongs to the new month. Required
  payments cannot be prepaid or bulk caught up; three ordinary extension periods
  use the same basis. Separately acknowledged outage compensation is still capped
  at three additional periods and does not rewrite original dates or payment count.
- Cash uses the service-recorded receipt instant, not an owner-selected historical
  date. Online qualification uses the existing verified provider timing envelope,
  never webhook-arrival/local confirmation time. A wholly in-window late-delivered
  event may qualify; uncertain, deadline-crossing or month-crossing evidence stays
  in review with money/metal evidence retained. Do not silently move a reserved
  January payment into February or invent an exact capture instant from `created_at`.
- Obligation, period basis, payment limit, eligibility and missed-payment consequence
  are distinct owner controls and typed policy dimensions. A compatibility matrix,
  backed by service/model/database validation, still rejects unsupported combinations.
  Optional contributions use duration eligibility, with flexible or calendar-month
  limits. Required customer-fixed instalments use calendar/anniversary periods,
  one qualifying payment per period, duration AND count, and extension then review.
- All currently supported families remain exact-grade metal, no benefit, full-only
  jewellery settlement. INR purchase-credit, count-only/anytime normal eligibility,
  arbitrary grace/catch-up, and defined benefit qualification/loss/fulfilment need
  separate complete financial workflows and decisions; exposing dropdown values
  alone would not implement them. Paid principal/metal is never forfeited.

Migration 0035 expands only the permitted new configuration basis and display labels;
it does not convert agreements, backfill periods, change existing digests or activate
the release gate. Existing immutable configuration versions keep their original basis.
The documented earlier anniversary-only restriction below describes the first preset,
not a permanent architectural dependency. Framework changes are not required.

23 October 2026 B3 boundary: both normal and early configured settlement require an
accepted closure plus separate evidence of customer confirmation and actual jewellery
fulfilment. A signed, owner-bound ten-minute financial preview is rederived under the
agreement lock; all six stored gram decimals are settled, with no submitted amount,
bonus, fee or cash conversion. Normal eligibility is derived from the recorded calendar
or monthly-count/final-period-end policy. Immutable proof binds the existing financial
redemption to the closure sequence. A reasoned, evidence-backed reversal restores the
full entitlement but retains accepted closure and payment containment; it is not a new
saving cycle. Existing legacy redemptions are not converted or given invented consent.

V1 deliberately cannot settle agreements containing failed/abandoned provider attempts,
Test/mock activity or unresolved payment/timing/outage evidence. Local timeout is not
provider cancellation. Resolving that exposure needs a separate verified-disposition
workflow; do not create an owner checkbox or delete attempts to bypass the hold. This
limitation remains part of B4/P4 activation review, not permission to publish all plans.

A reusable plan is a current offer, not a mutable replacement for every customer's
agreement. Existing accounts already snapshot economic terms, duration, eligibility
and exact grade, but displayed the current plan name. Generic admin edits bypassed
the owner change audit. Calendar eligibility was also easily mistaken for proof of
twelve paid instalments. Finally, early discontinuation policy described a fixed
twelve-month window while agreements may last longer; the application has neither
early-settlement nor cancellation of unused agreements.

## Decision A: Govern offers and preserve agreement evidence

1. Keep plans in Django, not CMS. An explicit owner service validates and locks the
   plan, applies offerings, appends the audit and records immutable plan revisions in
   one transaction. Stale edit forms fail rather than overwrite intervening changes.
   Generic Django admin becomes read-only for plans.
2. New enrolment locks/reloads the current plan and records its revision and name/code,
   alongside existing individual economic/date/grade snapshots. Revision metadata
   supports provenance; account snapshots remain the operational agreement. Existing
   customer confirmation records remain evidence of consent, not replaced by revision
   creation. No new financial source of truth or generic repository is introduced.
3. Migration freezes currently observed names/codes for old agreements, leaves their
   revision null, and labels them legacy display identity. It must not infer original
   consent, recreate a historical revision, change economic snapshots, shift dates,
   convert grades or rewrite payments/allocations/redemptions.
4. Active means available for new enrolments; publicly listed additionally controls
   public discovery. Offered grades restrict new enrolments only. None of these flags
   pauses contributions on existing agreements. Use existing payment operations
   controls for operational pauses. Existing pending-offer confirmation rules remain.
5. Existing metal eligibility remains start date plus agreed calendar months. Once-per-month
   is a frequency ceiling, not a requirement to complete twelve instalments or earn
   a benefit. The builder described below introduces explicitly versioned alternatives
   for future agreements, never a silent retroactive restriction.
6. Clarify public policy against the recorded eligibility date, not a fixed twelve
   months. Do not assert regulatory reasons, cash conversion, automatic early
   redemption, numeric penalties or discounts that the application does not implement.

## Decision A+: A bounded, owner-led plan builder

### Policy catalogue

#### Builder-v1 compatibility contract (approved 24 October 2026)

The owner approved all three decision groups: the rule matrix/timing, INR settlement
approach and parameterised benefit types, and authorised implementation. These are
design contracts, not a claim of implemented capabilities or published promises.
They supersede neither existing immutable terms nor the separate INR approval gate.
The subsequent owner-approved remainder decision is a single final settlement with
manual showroom fulfilment and an unused-paid-principal refund where applicable.
It resolves the business-policy choice, not the separate provider/business approvals
or the need to implement and verify the financial workflows below.

**Common dimensions:** each agreement accumulates either one exact metal grade or
INR jewellery purchase credit, never both principal denominations. Contributions may
be plan-fixed, customer-fixed at enrolment or variable within disclosed bounds.
Separate `required_count` from duration: count-only has no minimum-duration field;
duration-only has no redemption count; both requires each independently. Do not relax
the old twelve-month constraints globally or rewrite existing versions to achieve this.

| Proposed rule family | Amount choices | Obligation and limit | Normal eligibility | Missed-payment result |
| --- | --- | --- | --- | --- |
| Optional / duration | Plan-fixed, customer-fixed, variable | No obligations; flexible payments or one per selected calendar/anniversary period | Agreed duration reached | None; an unused payment window is not a missed instalment |
| Optional / anytime | Plan-fixed, customer-fixed, variable | No obligations; flexible payments or one per selected calendar/anniversary period | Positive verified entitlement; no maturity wait | None |
| Required / count-only | Plan-fixed or customer-fixed | Required calendar/anniversary months; one qualifying contribution per period | Required count achieved | Three ordinary replacement periods, then review |
| Required / duration AND count | Plan-fixed or customer-fixed | Same monthly obligation and limit | Both duration and count achieved | Three ordinary replacement periods, then review |
| Required for benefit / duration | Plan-fixed or customer-fixed | Monthly schedule qualifies the named benefit, not principal redemption | Agreed duration reached, independent of missed count | An ordinary missed period disqualifies the named unearned benefit; principal remains redeemable at duration or through early closure |

Each row is a target for both denominations, subject to separate implementation and
INR publication approval. A benefit is optional on the first four rows only where its
explicit qualification policy is supported; the fifth requires a non-NONE benefit.
No implicit combination is admitted just because its dropdown values exist.
For optional plans the period basis describes a payment ceiling only, not an obligation.
This deliberately extends the current optional calendar-only ceiling to anniversary
periods without pretending that change already exists.

**Recommended timing and compliance defaults:**

- Count-only becomes normally eligible once the final required payment is verified
  and conclusively attributed, not at the end of its month. A late-delivered webhook
  may establish historical qualification but never permits a settlement before funds
  are verified. Do not infer count-only eligibility from the number of attempts.
- Duration AND count retains the already approved later-of-duration-and-final-period-
  end rule; these two families intentionally differ. Required count and duration
  are independently frozen, with a preview showing their earliest possible completion.
- Keep the approved short first calendar month, India-time half-open boundaries,
  enrolment-day attribution, zero extra grace and no bulk catch-up/advance instalments.
  Keep three separately acknowledged outage compensation periods, independent of
  three ordinary replacement periods. Do not invent customer lateness during an
  unresolved provider/showroom incident; apply the existing evidence/hold workflow.
- Payment extensions and benefit loss are separate policies. For count-based plans,
  missing a month may extend completion and, only if explicitly chosen, remove a
  named unearned benefit. Exhausting replacements triggers review/early full closure,
  not forfeiture or permanently inaccessible principal. Duration-only benefit plans
  do not silently extend principal maturity when a benefit is lost.
- Required variable-amount instalments, multiple qualifying payments per month,
  count eligibility without obligations, mandatory count with anytime redemption,
  arbitrary catch-up/grace and mixed-grade principal are rejected in this proposed v1.
  Required variable amounts would need minimum qualifying amount/top-up semantics;
  adding them later requires explicit scope approval, not an accidental dropdown path.
- Count-based plans stop taking further contributions after their count is complete.
  Optional plans may disclose continued contributions before full closure; the limit
  still applies. Accepted closure blocks new payments and requires pending/late funds
  to be reconciled before the agreement can be finally closed.

**Approved INR purchase-credit settlement contract (remainder decision updated 24 October):**

- Receipt credits INR principal; it neither locks a metal rate nor allocates grams.
  Record append-only receipts, verified corrections and full settlement applications,
  with INR paise precision and protected immutable source references.
- One final full closure disposes of all available principal through a customer-approved
  jewellery purchase, a permitted principal refund, or both. No general partial redemption.
  Jewellery valuation is the agreed invoice value at fulfilment, not an enrolment-time
  metal promise. Record item/amount evidence, adjustments, invoice identity, actual
  handover and customer confirmation; this is not a new tax/inventory/POS engine.
- Any invoice shortfall is paid separately with verified evidence; do not treat it as
  a further scheme instalment or count it twice. If the invoice is below principal,
  refund the unused paid principal within the same final settlement. For example,
  INR 12,000 principal may close with INR 10,000 applied to jewellery and INR 2,000
  actually refunded. Do not create a replacement voucher, wallet or untracked debt.
- The showroom performs fulfilment manually; the app records the invoice application,
  refund amount/method/reference, actor, date and customer-authorisation/receipt evidence.
  No automated Razorpay refund integration in this scope. This is not permission to
  ignore source-routing obligations: manually use the provider dashboard where required,
  and obtain an approved fallback before publishing a product whose older payments
  cannot use that route. A blanket physical-cash refund is not approved.
- Until every leg is actually fulfilled and reconciled, keep settlement pending with
  the remaining liability visible and new contributions/redemptions blocked. Neither
  an owner checkbox nor an agreement to refund later is proof of payment. Close only
  once the complete principal is accounted for. No forced purchase or forfeiture.
- Benefits remain separately qualified and invoice-fulfilled; do not cash out unearned
  benefits or deduct arbitrary fees from principal. This INR policy does not authorise
  converting exact-grade metal entitlement into cash.
- Early closure preserves all paid principal; an unearned completion benefit is not
  automatically awarded. Never implement a fee/deduction without accepted terms.
- A verified full reversal restores principal through linked append-only evidence,
  reverses associated benefit fulfilment and leaves the agreement contained for
  resolution. A record correction alone is not proof jewellery or money was returned.

**Recommended initial benefit vocabulary (one policy per configuration):**

1. `NONE`.
2. INR jewellery-purchase bonus: a configured percentage of verified net qualifying
   principal, capped in INR. Only for INR principal in this proposed v1; no undisclosed
   metal valuation is introduced to calculate it. The amount becomes an earned,
   separately tracked purchase benefit only when its accepted qualification rule is
   satisfied, and is fulfilled against the final invoice, not paid out as cash.
3. Value-addition discount: a configured percentage of evidenced eligible VA/making
   charges on the final invoice, with an INR cap. Available to either denomination;
   it never discounts principal, metal weight or the whole invoice by implication.
   Qualification grants the contractual discount right; its exact monetary amount
   depends on evidenced eligible charges at fulfilment. No negative invoice amounts.

The owner supplies percentages, caps, eligible charge definitions and whether normal
extended completion preserves the benefit before publishing a plan. No percentage
or cap is pre-approved by this proposal. No stacking, extra-metal bonuses, compound
returns or cash-payout bonuses in the proposed v1. Financial formulas use Decimal
and an explicit snapshotted rounding rule; recommend paise ROUND_HALF_UP once at
award/fulfilment, not a succession of floating-point intermediate calculations.
Qualifying principal excludes test payments, reversals, unresolved receipts and invoice
top-ups. A reused invoice/benefit must not be consumed twice. An already earned benefit
cannot disappear merely because the owner edits a plan: correction requires linked
evidence and approved reversal treatment. If a fulfilled benefit is invalidated by a
later receipt correction, contain for review; do not silently deduct it from principal.

**Approval recorded:** (a) the rule matrix and immediate count-only trigger, (b) INR
invoice/shortfall/remainder and full-reversal approach, and (c) the two benefit types
with owner-supplied published parameters. The manual full-settlement/remainder policy
above is now approved. INR external approvals, usable refund routes and tested actual
fulfilment evidence remain prerequisites before that family can publish.
Acceptance of this design is not that external evidence.

**Implementation checkpoint:** `schemes.plan_policies.PlanPolicy` is an immutable,
typed schema-v1 compatibility contract with strict validation and a separate
operational-blocker check. Migration 0036 introduces persisted policy schema 2 with
independent duration, required count and benefit parameters. Schema 1 retains its
old duration fields, evidence serialization and revision digests exactly. Schema 2
uses null legacy duration fields rather than pretending count-only/anytime means
twelve months; edits append a new immutable family version, never downgrade schema.
Valid schema-2 records can be prepared through the owner-authorised service and
inspected read-only. All schema-2 plan projection, agreement preview/enrolment and
publication remain blocked even with the release flag enabled. The old editor cannot
edit these records. Reverse migration refuses to discard existing schema-2 evidence.
INR accounting/settlement, benefit lifecycle and new eligibility/schedule workflows
are still to implement; persistence does not calculate, award or fulfil anything.

**Principal implementation checkpoint (0037):** `INR_CREDIT` is a distinct future
account denomination, requiring a pinned configuration/revision and no metal grade
or legacy cash bonus. No existing account is relabelled. `InrPrincipalReceipt` pins
the contribution, configuration, exact amount, verification time and live captured
webhook or actual cash receipt. `InrPrincipalCorrection` retains a completed full
cash-entry reversal; it cannot become an arbitrary deduction or online refund.
Services reload owner authority, lock account before source, validate evidence and
reject conflicting retries/duplicate sources. Selectors retain ledger amounts during
source drift, surface reconciliation needs and keep them out of cash bonuses/grams.
`check_inr_principal` is read-only and explicitly reports `workflow=not_activated`.

The principal split calculator conserves the full principal across invoice application
and unused-principal refund, and identifies an external invoice top-up. It is arithmetic
only, not eligibility, benefit calculation, a completed refund or full closure.
At the 0037 checkpoint no settlement debits/fulfilment records existed (0038 below adds
that foundation). The financial service tests construct
synthetic future contracts directly in disposable PostgreSQL because ordinary schema-2
account creation is intentionally blocked; this is not a production bypass or setting.
Public enrolment/payment, legacy redemption and closure paths remain blocked for INR
credit. Payment integration, new agreement snapshots and the manual settlement journey
must be completed before any activation. Reversal of 0037 refuses to drop INR evidence.

**Agreement integration checkpoint (24 October 2026):** read-only independent terms
now resolve customer-fixed versus variable amounts, exact denomination, independent
duration/count and explicit benefit policy from the persisted configuration. A duration
floor is not a redemption-eligibility decision; count-only/anytime have no invented
duration. Existing schema-1 projection/evidence remains unchanged. Current account
columns can validate only the optional-duration (at least twelve months), no-benefit
subset with flexible/calendar limits. INR principal and common agreement diagnostics
now use that frozen-contract validation, including amounts, frequency and date, without
consulting the current mutable plan. Model creation, enrolment, payment and publication
guards remain closed for schema 2. No new migration or production activation is part
of this checkpoint; wider account persistence/runtime integration remains required.

**Independent account storage checkpoint (0040):** account storage version 1 retains
the old mandatory duration/date and twelve-month minimum. Version 2 adds explicit
eligibility-policy and required-count snapshots; agreed_months is duration only and
eligible_from is the duration floor, not a completed eligibility decision. Count-only
and anytime have null duration/date. Required-for-benefit duration policies can retain
a count without making it a redemption condition. Versioned database constraints
and frozen-policy validation reject mixed or invented facts. Source/schedule/benefit
runtime gates remain closed. Forward preflight refuses pre-existing unversioned
schema-2 accounts; reverse migration refuses any retained independent agreement.
No historical agreement is converted or given an invented instalment obligation.

**Manual disposition implementation checkpoint (0038):** one immutable proposal pins
the complete principal, invoice application, original-source refund legs and external
top-up, with a signed ten-minute owner-bound preview and customer authorization.
Invoice consumption follows earliest verified uncorrected receipts (then receipt ID).
Separate append-only jewellery/refund fulfilment records discharge exact legs only;
the proposal itself discharges nothing. One invoice cannot be reused across proposals.
Remaining principal/refund liability is projected until every leg has actual recorded
handover/payment and customer receipt evidence. Completion links one SETTLE event and
closes the agreement; it does not create a legacy cash/metal Redemption.

Manual source routes currently supported are original cash return and provider-dashboard
refund of original live payments. No arbitrary cash fallback or provider refund API.
The owner records fulfilment evidence; the app cannot independently verify the physical
handover or bank credit. Stale source/closure facts and late payments require reconciliation.
This internal foundation supports optional calendar no-benefit future INR contracts only;
actual enrolment/payment/UI remain blocked. Full physical-return reversal is described
in the following correction checkpoint, not a mutable correction or permission to reopen.
Both ordinary creation and activation remain gated pending the complete builder journey.

**Controlled correction checkpoint (0039):** distinguish VOID before any fulfilment
from FULL_RETURN of every actual fulfilled portion. Record a full set of owner-attested
physical-return evidence atomically; partial/staged returns are outside this foundation.
The latter includes jewellery return, corrected invoice, any separate top-up refund,
and actual receipt back of any already-refunded principal. If evidence is incomplete,
do not post a fictitious full return; retain the original disposition for investigation.
The app cannot independently verify a physical return or bank credit.

Append a linked resolution and return records without rewriting original terms or
gross fulfilments/completions. Restore only the original discharged principal, not
external top-up. A completed settlement appends REVERSE; a pending disposition appends
NOTE. Both retain an accepted closure and CLOSURE_PENDING agreement: no new payments.
A checked retired projection permits a single linear chain of replacement full
dispositions, each with fresh preview/customer authorization and new invoice/reference
evidence. This is correction of one final settlement, not recurring partial redemption.
Returning a prior online refund does not restore the provider's refund capacity on
its original capture. Cumulative gross recorded provider refunds plus the proposed
new refund cannot exceed that receipt's amount. Exceeding cases remain held for
separate approved-route reconciliation; no cash substitution is inferred, and a
passing recorded-history cap does not independently verify provider availability.
Provider reference: [Razorpay normal-refund documentation](https://razorpay.com/docs/api/refunds/create-normal/)
(reviewed 24 October 2026) rejects over-capture and already-fully-refunded payments;
it also lists age, method, balance and dispute restrictions. The recorded-history cap
is therefore necessary but insufficient for a usable refund route. Before activation,
verify actual routes across the entire agreement duration; unresolved cases remain
liabilities and cannot be closed by an owner assurance alone.
Migration reversal is refused once correction/replacement evidence exists. Runtime
enrolment, payment, statements, privacy disposition and UI acceptance remain separate gates.

**Independent replacement checkpoint (26 October 2026; no migration):** a correction
generation retains the original disposition's normal/early basis and benefit decision,
not a newly elapsed eligibility date. This corrects one final settlement; it does not
restart the agreement or earn a benefit during a closure hold. Verify unchanged source,
schedule and review evidence, complete predecessor returns/voids, and fresh owner-bound
preview/customer authorization/new invoice references. Bind each successor to the full
resolved predecessor chain; preserve source-first refund caps across generations.
Principal-only INR/metal returns and INR awards that have never been consumed are now
supported internally behind the unchanged readiness gate. An unconsumed award survives
void/refund-only returns unchanged and can fund its one actual jewellery invoice.

A consumed-and-returned invoice remains held. Its full reversal does not itself approve
another application, reset its amount/cap, or erase the award. Separate append-oriented
reapplication authorization/history and atomic integration are the next dependency;
do not remove the one-invoice constraint just to pass a replacement. No public workflow
or production acceptance is supplied by this recovery checkpoint.

**Returned-benefit review checkpoint (0048, 26 October 2026):** retain an immutable
sequence of owner APPROVE/HOLD decisions against the original full benefit reversal.
Approval records fresh customer authorization for reviewing reuse of the existing
right; it does not award another benefit or fulfil a replacement invoice. Retain the
original qualification/cap and complete principal/benefit return proof. A hold appends
a superseding decision, so an old approval/retry cannot silently override it.
Signed previews bind the owner, return, closure prefix and predecessor decision.
New closure evidence invalidates the current review until re-reviewed; changed
financial sources remain held for reconciliation. Database uniqueness and agreement
locking prevent forks. Rollback refuses existing decisions. The next atomic replacement
step must require a current approval and record its consumption with the new invoice;
until then the single-invoice constraint and all activation barriers remain intact.

**Atomic reapplication checkpoint (0049, 26 October 2026):** retain one original
invoice and explicit predecessor/approval links for each replacement application.
One successor per predecessor and one consumption per approval replace the old
one-invoice-per-award restriction without permitting parallel or automatic spending.
Original proof JSON is unchanged. The replacement proof binds the current approved
review, complete return history and exact invoice; a new invoice consumes it only
when actual principal handover commits. INR proposals alone neither consume review
nor discharge liability. A hold after proposal prevents new fulfilment while still
allowing an evidenced void/full return and fresh review. A consumed approval remains
historical; further correction requires the successor's own full return and review.
Purchase bonus retains its original amount; VA is recalculated for the new invoice
using the same contracted percentage/cap and charge definition. This changes no paid
principal or metal and creates no refundable benefit balance. All prior invoices,
reviews and reversals remain readable after subsequent closure states. Reverse migration
refuses new bindings even before invoice consumption. Full release gates stay closed.

The owner may create a validated configuration or reuse an existing approved one,
then use its immutable version in one or more offered plans. A reusable configuration
is not a live pointer that can rewrite every plan/agreement using it. Editing means a
new version; a saved configuration is not automatically published or offered.

| Dimension | Supported design choices | Required boundaries |
| --- | --- | --- |
| Contribution amount | Plan-fixed; customer-selected fixed at enrolment; variable within limits | Customer-fixed selection must satisfy configured minimum/maximum and any explicit amount step; it is frozen on the agreement and enforced, not merely a preference. |
| Accumulation | One exact metal grade; separately gated INR purchase-credit family | Grade is selected from owner-approved offerings and fixed at enrolment. INR and each grade stay separate. Razorpay/in-store cash is a payment channel, not an accumulation policy. New production INR/cash-payout offerings remain disabled pending separate approval. |
| Instalments | No mandatory schedule; required monthly instalments | Required schedule has an explicit period convention, due window, count, grace/catch-up rules and fulfilment conditions. A monthly frequency ceiling alone creates no payment obligation. |
| Redemption eligibility | Calendar duration; qualifying instalment count; both; anytime | Count-based options require a schedule. Anytime has no maturity waiting period, but still requires verified, available entitlement and settlement checks. |
| Missed payments | Extend completion; explicitly allowed catch-up; disqualify a named unearned benefit; discontinuation review | Specify trigger, recovery and limits. Never destroy paid principal/metal or permanently trap it without a settlement route. No silent penalty for a showroom/provider outage. |
| Benefits | None; a supported versioned purchase-credit or discount policy | Formula, unit, qualifying conditions, cap, fulfilment event, early-exit and reversal treatment are mandatory. No arbitrary Python/expressions or unapproved bonus formula. |

These are supported *design capabilities*, not a claim that every cross-product is
valid or that a particular numeric benefit/due-day rule has already been approved.
Publication must reject incomplete or incompatible configurations. Keep one explicit
typed policy schema, enum choices and validation/services in Django; no generic rules
language, arbitrary executable JSON, separate policy microservice or hidden signals.
JSON revisions retain evidence, not executable user-supplied rules.

### Publication and agreement evidence

1. Owner creates or selects a configuration version, supplies plan name/visibility and
   offered grades, and reviews generated agreement text and scenario examples.
2. Validate the whole combination server-side. Show normal payment, missed payment,
   early exit and full settlement outcomes before publication. Unsupported policy
   types stay unavailable even if manually submitted in a request.
3. A published plan pins a configuration version. New enrolment records that version,
   the customer's selected fixed amount/grade/duration, original contractual dates,
   applicable policy/consent versions and the accepted terms. Store evidence of actual
   confirmation separately; creating a revision is not customer consent.
4. Later edits affect future offers only; pending applications must reconfirm material
   changes. Existing agreements use their own version. Existing calendar-only agreements
   gain no invented instalment obligations, missed payments or earned benefits.
5. All screens, reminders, selectors, contribution services and redemption services
   use the same agreed policy. The current universal date-based copy must become
   policy-specific before any alternative is published. Do not just add editor fields.

### Initial configuration families and dependencies

| Family | Amount / accumulation | Eligibility / consequence | Release condition |
| --- | --- | --- | --- |
| Calendar metal | Plan-fixed, customer-fixed or variable / one grade | Calendar duration; no mandatory instalment compliance; no benefit by default | Preserve the existing family; add customer-fixed enforcement and full-only settlement. |
| Completion metal | Customer-fixed / one grade / required monthly schedule | Calendar AND qualifying instalment completion; missed periods extend completion under the selected policy | Instalment records, schedule semantics and extension limits must be implemented and validated first. |
| Disciplined metal with benefit | Customer-fixed / one grade / required monthly schedule | Redemption and benefit qualification evaluated separately; missed payments may disqualify an unearned benefit | Exact approved benefit formula, missed-period rules and fulfilment/reversal handling required; no sample percentage is treated as a promise. |
| Flexible anytime metal | Variable / one grade / no mandatory schedule | Anytime, full-only settlement; no benefit by default | Later separate acceptance for full settlement/closure and late-payment handling. |
| INR purchase credit / cash bonus | Separate INR family | Not inferred from a metal plan or in-store cash payment | Deferred business/legal/accounting/provider approval and implementation; existing production block remains. |

Paid-instalment-only eligibility is part of the catalogue design but cannot be offered
until its schedule prevents unintended accelerated completion (for example twelve
payments in one week). Do not assume every plan must last twelve months forever:
existing minimum-duration constraints remain for existing families; any shorter or
anytime family needs explicit policy-specific validation/migration, not a global zeroing
of duration or invented backdated eligibility.

### Instalment and benefit evidence

#### First monthly-completion policy approved 23 October 2026

The owner approved customer-fixed monthly contributions, agreement-anniversary periods
in Asia/Kolkata, one qualifying payment per period, no extra grace (0 days), no advance
instalments or bulk catch-up, and at most 3 extension months. Required payment count is
the agreed month count. Normal eligibility needs both calendar duration and qualifying
payment completion, at the end of the final qualifying period. Incomplete agreements
at the extension limit require owner-led discontinuation review; paid entitlement is
not forfeited. Benefits are NONE. Settlement is FULL_ONLY and closes only the agreement.

Each window is [original start plus n months, original start plus n+1 months), with
month-end clamping always calculated from the original start date (not chained from
the previous shortened month). Twelve months with two missed periods normally projects
completion after fourteen months, assuming all other required payments occur. This
scenario is not an eligibility grant, a guarantee or evidence that payments occurred.

The first family accumulates an exact metal grade. INR purchase credit is a distinct
denomination/settlement family, not cash payment-channel terminology; it remains gated.
The date-window engine is denomination-independent, but cannot create an INR offer.

P2a implements explicit typed preparation rules, owner scenario previews and frozen
period snapshots. P2b must still implement reservations, verified payment attribution,
append-only corrections and auditable outage/late-capture review before any activation.
Current `Contribution.paid_at` is local confirmation time; neither it nor a payment's
creation timestamp may be assumed to be provider capture time. Do not infer lateness
from delayed webhook delivery. Outage exceptions have no invented automatic grace or
free payment credit: until their workflow is implemented, no affected monthly family
may be published. All existing publication/enrolment and settlement gates remain.

P2b.3a adds an owner investigation workspace, immutable notes/outage holds and narrowly
verified timing resolution. Owner acceptance must link a stored signed evidence
decision for the same independently verified Live payment and original deadline;
missing/contradictory timing cannot be replaced by an owner-entered timestamp. Review
never creates money, grams or a new contractual right. An outage hold stops new
initiation, not processing already-started verified captures. P2b.3b now implements
the bounded contractual outage remedy below and exact ambiguous-order identity
recovery and late/duplicate-capture containment boundaries; final exception acceptance remains open.
No automatic grace, waiver or penalty is permitted; the bounded amendment below
provides the only approved outage-extension/hold-closure route.

#### Capture-disposition boundary — 23 October 2026

Use the existing payment/webhook exception workflow, not a new refund engine, override
button or second financial ledger. Apply these rules to configured monthly agreements:

| Evidence | Financial treatment | Instalment / initiation treatment |
| --- | --- | --- |
| On-time verified capture delivered later | Record/reconcile once using the original payment/rate evidence. | Original signed timing may qualify once; delivery time alone does not make it late. |
| Same captured payment delivered again | No second contribution or allocation. | No second qualifying instalment; contradictory timing still requires review. |
| Different captured payment for an already-confirmed order | Preserve the first receipt/allocation; retain the additional payment ID in a `DUPLICATE_CAPTURE_REVIEW` event and processing history. | Do not add credit or erase the first qualification; block further initiation and owner timing acceptance pending provider disposition. |
| Verified capture after local expiry, order not abandoned | Preserve the existing verified-funds/allocation behaviour and original locked rate; no silent repricing, deletion or invented refund. | Keep timing in REVIEW; no automatic qualification/eligibility and no owner-entered late-payment override. |
| Capture after provider-reconciled abandonment | Keep the abandoned attempt and any legitimate replacement untouched; retain the capture in provider exception history, not a replacement credit. | Non-occupying RELEASED_REVIEW; further initiation is held. An already-started legitimate replacement can still confirm. |

All unresolved Live `payment.captured` events linked by contribution or recovered
order identity block new monthly online/cash initiation and owner timing acceptance.
Include RECEIVED/FAILED events, not only final review events. Test-mode or unrelated
order events do not hold another agreement. Confirmation of independently verified
in-flight funds is never rejected merely because this hold or a global pause exists.
The agreement lock serializes its financial mutations. A request already in flight
before an exception became observable cannot be recalled; reconcile its evidence.

`check_instalment_payments` reports unresolved captures separately from structural
integrity. A zero-integrity-error result is not disposition acceptance. The owner
period workspace links to existing provider reconciliation. Notes, reported refunds
or a checkbox cannot clear the hold. Automated refunds, refund-confirmed financial
corrections and external refund-completion verification are not implemented here;
unresolved duplicate/abandoned captures stay held for the established manual provider
process and subsequent separately reviewed closure capability. Do not mark a retained
event PROCESSED/IGNORED by database edit to make the agreement payable again.

This completes the local containment boundary, not business/visual/release acceptance,
P3 eligibility or full settlement. Configured publication/enrolment remains disabled.

#### Payment-error refund resolution design — 27 October 2026

Design for the bounded implementation; **resolution is not implemented or activated**.
The read-only inspection/immutable observation prerequisite is now local (0052),
including strict provider validation and owner/binding rechecks. No resolution record,
hold clearance or operator action is available yet. The integration sequence below
remains required; an observation alone supplies no financial authority.
This extends the containment boundary above without changing the approved manual
refund execution or full-only agreement settlement policy.

The supported case is an exact Live Razorpay payment that was captured in error,
never supplied local metal/INR entitlement, and has subsequently been fully refunded
through the original provider route. The owner executes that refund in the provider
dashboard. The app will only read provider evidence and record a scoped resolution.
It must not initiate a refund, accept an owner-entered refund status, or expose a
generic "clear exception" action. This is not the already-implemented INR final
disposition: that workflow discharges recorded principal using source-specific
manual fulfilment evidence and cannot clear an unrelated provider exception.

**Required evidence and exclusions:**

- Bind merchant context, Live mode, exact payment/order and linked local attempt.
  Recover an uncertain order identity first. Amount/customer resemblance is not
  identity proof; unmatched or cross-linked payments stay in investigation.
- Use authenticated read-only payment/refund inspection. Require the payment's full
  refund state and refunded amount to agree with a complete, deduplicated collection
  of processed refunds linked to that payment and currency, totalling its full amount
  in integer paise. Reject partial, pending, failed, malformed, inconsistent or
  incomplete evidence. Pagination/timeouts/inspection limits must fail closed, not
  interpret a partial list as complete. Never use float or coerce booleans to money.
- Prove absence of entitlement from this **payment**, including historical metal
  allocation, INR principal, API capture and corrected/settled source links. A zero
  balance, FAILED/ABANDONED status or a later reversal is insufficient. A legitimate
  first payment on the same order retains its credit and qualification when an
  additional uncredited payment is refunded.
- Already-credited payments, partial refunds, disputes/chargebacks and unsupported
  refund routes remain separate correction/incident work. Do not manufacture a
  source reversal or refund capacity to bring them into this boundary.
- Provider `processed` is evidence of provider refund processing, not independent
  proof of the customer's bank statement. Present that distinction, retain support
  references and escalate a reported non-receipt; do not promise a bank-credit date.

**Recording and race safety:**

Retain minimal immutable provider observations and a separate append-only resolution
with actor, reason, time, payment/order/mode identity, refund IDs/amounts and a binding
to the exact reviewed local evidence. Preserve original events and processing
attempts; never rewrite an event to PROCESSED/IGNORED merely to reduce a counter.
Do not retain raw provider payloads, credentials or unnecessary bank/customer data.

Use the existing owner preview/confirmation pattern with a ten-minute maximum review
age. Recheck persisted owner authority, independently inspect again on apply outside
database locks, then lock/revalidate the agreement and affected source/event evidence
before recording. Repeated application is idempotent. Concurrent callback/webhook/API
recovery must either establish entitlement first (refusing this resolution) or observe
the resolution and refuse new credit from the refunded payment. No database lock is
held across provider I/O. Contradictory later evidence creates a new review hold;
there is no editable resolution or override that restores spending authority.

Introduce one shared interpretation of **resolved exact payment evidence**, used by
exception queues/checks, monthly and optional payment admission, eligibility/timing
review, closure/settlement proofs and applicable privacy containment. Keep existing
scope differences: a resolution cannot suppress another payment on the same order,
another mode, unrelated event types or structural errors. Exact historical capture
redelivery must not create entitlement; new or contradictory evidence stays visible.
All confirmation entry points need this protection before any hold-clear action ships.

Resolution alone grants no instalment qualification, rate/deadline extension, benefit,
agreement closure or replacement contribution. Local pending-attempt and reservation
states still need explicit evidence-backed lifecycle handling. Do not reuse the
"untouched order" abandonment rule for an order that captured and was refunded.

**Execution order and acceptance:**

1. Add strictly validated read-only provider inspection and immutable, uniquely
   scoped observation/resolution storage, preserving migrations and historical data.
2. Implement the atomic owner service and common evidence predicates together with
   callback/webhook/API replay protection and explicit attempt/reservation handling.
   Keep operator actions unavailable until those integrations pass together.
3. Add the private owner review/confirmation screen, diagnostics and runbook; then
   exercise full-refund resolution of an uncredited duplicate and abandoned capture.
4. Test wrong mode/order/payment/currency/amount, partial/pending/failed refunds,
   incomplete pagination, stale/revoked-owner confirmations, credited-but-reversed
   sources, concurrent credit/resolution, replay, independent payments on the same
   order, remaining unrelated holds and migration preservation. Verify every approved
   family retains unchanged principal/grams/benefits and historical audit evidence.

This sequence belongs to the existing owner-operations release row in MVP_PLAN.md;
it is not a new product family or approval to activate configured plans.

Provider field references, checked 27 October 2026:
[payment entity](https://razorpay.com/docs/api/payments/entity/),
[refund entity](https://razorpay.com/docs/api/refunds/entity/) and
[refunds for a payment](https://razorpay.com/docs/api/refunds/fetch-multiple-refund-payment/).
The stricter clearance and concurrency rules above are application design choices.

#### Lost-order identity recovery — 23 October 2026

Before sending a new configured monthly order, commit a random request UUID with
the ORDERING decision. Send `inst_<UUID hex>` as the provider receipt (37 characters)
and the UUID/contribution identity in notes. Legacy non-monthly payloads are unchanged.
Never synthesize correlation for an already-sent request.

An owner supplies a candidate order ID from the correct merchant dashboard/support
investigation. The backend uses its configured Live credentials to read that exact
order and verifies all request facts and a plausible creation time. This uses
[Razorpay's authenticated fetch-order endpoint](https://razorpay.com/docs/api/orders/fetch-with-id/).
No order-search completeness or absence guarantee is assumed.

Record immutable typed evidence and atomically bind only the original unresolved
contribution, rechecking the account-locked payment sequence after the network read.
Identical submissions are idempotent; competing or changed evidence requires review.
Recovered orders are reconciliation-only: never resume checkout, extend expiry,
create a replacement, or infer payment/qualification from an order's `paid` status.
Captured payments still need the existing verified payment and signed timing paths;
expired untouched orders still need provider-backed abandonment. Previously reviewed
unknown-order captures retain their review status until explicit reconciliation.
No match, network failure, conflicting facts and pre-existing intents without a UUID
remain held for provider investigation. This intentionally favours a visible unresolved
case over fabricated absence evidence or double collection. Rejected lookup attempts
make no binding; the owner can retain investigation notes in the existing review ledger.

#### Outage-remedy decision — owner-delegated recommendation, 23 October 2026

The owner explicitly delegated selection of a separate outage allowance and its cap.
Decision: **at most three compensating months per agreement**, separate from the three
ordinary extension months. A 12-month agreement therefore has an outer boundary of
18 anniversary months, not 18 required payments. This is not a guaranteed completion
date or automatic additional time. The required count remains twelve.

- Already-on-time verified payment uses timing resolution, not outage compensation.
- If service is restored before the original window closes and no window was lost,
  resume only after payment/order reconciliation; no automatic compensating month.
- Where evidenced business/provider unavailability caused an unpaid period to be
  missed, allow one owner-authorized additional anniversary month per affected period,
  separate from the three ordinary extension months. Keep original dates and evidence;
  expose the revised completion outlook, not an overwritten original agreement.
- Keep the full required payment count, agreed amount and exact grade. No waived/free
  instalments or bulk catch-up. A new payment uses its legitimately current locked
  rate and a fresh valid checkout, never an expired checkout/historical chosen rate.
- Require incident evidence, owner reason and customer acknowledgement; compensate an
  affected period at most once. Routine published non-office hours are not an exceptional
  outage. An outage report alone does not establish causation or entitlement.
- Hold closure must be an audited operation with reconciled payment state, not deletion
  of the hold. Unknown orders and late captures cannot be cleared by an owner checkbox.

Implementation uses an immutable, individually acknowledged `OUTAGE_COMPENSATION_V1`
amendment, not a change to a frozen configuration or agreement snapshot. Original
offer hashes, dates, ordinary windows and required count survive unchanged. No
production/historical agreement is automatically opted in; the workflow only supports
configured monthly agreements (which remain unenrollable pending dependent work).

Compensation requires the affected unpaid window to have ended, an incomplete required
count, overlapping exceptional incident evidence, restoration and subsequent customer
acknowledgement of the precise proposed outcome/dates. The appended window must be
wholly future and anchored to the original start day. Each affected period may receive
one compensating month; the agreement may receive three in total, including any later
outage in an extension period. Exhaustion, prolonged outages or a proposed window that
has already begun remain held for separate agreement/discontinuation review; they never
forfeit paid entitlement or silently roll the deadline forward.

Hold closure without an extra month is limited to restoration while the original
unpaid window is still open, or an already-qualified payment for that period. The owner
records the actual customer acknowledgement timestamp and a retained evidence reference;
an owner checkbox is not customer consent or provider reconciliation. V1 does not send
or capture customer acceptance online. Any other unresolved hold remains effective.
All pending/uncertain claims, allocation failures and matched unresolved webhooks must
be reconciled before closure. New payments use normal period/rate/payment services.
No amendment changes payment verification, balances, rates, benefits or eligibility.

- Keep obligations/periods distinct from payment attempts. Record an explicit link
  between a verified payment and the obligation it satisfies; retries must not count
  twice. Reversals append evidence and adjust qualification deterministically.
- The exact period basis (calendar month versus agreement anniversary), due dates,
  grace length, catch-up attribution and extension ceiling are explicit configuration
  choices. Initially enable only fully implemented choices. Do not invent business
  defaults to make a draft publishable; a missing required value is a validation error.
- Payment confirmation time/delivery delay must not falsely penalize an on-time provider
  capture. Verified paid-but-unallocated funds remain a payment fact, while allocation
  failures block settlement and go to recovery. Test/practice payments cannot fulfil a
  new Live agreement's obligations or earn real benefits.
- A late contribution uses the rate legitimately locked for that payment, not a
  retrospectively selected historical rate. Period attribution must not rewrite rate
  locks, allocations or payment history.
- Preserve original contractual dates. A derived expected completion date may change
  with missed periods; if future payments are unknown, label it a forecast, not a
  guaranteed date. The old original date must not accidentally prevent valid extension
  payments under a new completion policy.
- Define showroom pauses, provider failures and permitted catch-up explicitly before
  applying missed-payment consequences; do not record customers as noncompliant solely
  because initiation was unavailable. Such exceptions need auditable evidence.
- Separate eligibility, benefit qualification and actual benefit fulfilment. Prevent
  duplicate awards, retain the calculation/version/qualifying facts, and reverse through
  linked append-only records. A making-charge discount is not additional gold grams.
  Projected benefits are not earned liability. Reaching an eligibility date earns a
  benefit only when the accepted benefit policy explicitly says so.

## Decision B: Full-only settlement and explicit discontinuation

This follows the policy/instalment foundations, not a bypass of today's service.
The owner's latest decision supersedes the earlier proposal to retain partial
redemption as a separate product option: **no new builder configuration may permit
partial redemption, including anytime configurations**.

- Normal and early settlement consume the full authoritative remaining entitlement
  for the agreement and close it. There is no customer/owner-selected smaller quantity
  and no reusable zero-balance wallet. A future new saving cycle requires a new agreement.
  Closing one agreement does not close the customer's other agreements or login.
- Derive the full amount server-side under a lock and confirm it with the customer;
  do not trust a browser amount. Settle all six internal decimal places for grams even
  when customer display is three decimals, with an exact settlement explanation rather
  than silently dropping dust. Preserve idempotency and reject stale settlement previews.
- Existing code still allows eligible partial redemption. Inventory historical partial
  redemptions and written contractual promises before rollout. Preserve all historical
  events and remaining entitlement; do not fabricate retrospective acceptance or rewrite
  old settlements. Any conflict with existing agreed rights requires explicit resolution
  before switching that agreement to full-only processing, not an undocumented exception.

- Introduce an explicit customer discontinuation request and an owner-assisted path
  that records customer authorization/reference and mandatory reason. Closing one
  scheme must never delete its financial history or deactivate the customer's login.
- A request alone does not erase liability. Once accepted for closure, prevent new
  contributions and resolve pending provider orders, paid-unallocated funds and other
  unresolved payment exceptions before completing settlement. Late verified captures
  must remain visible/recoverable; a local abandoned/expired order is not proof that
  the provider can never capture it. Locking/idempotency and webhook races require tests.
- Funded early closure is an explicit full remaining exact-grade jewellery settlement
  with invoice/reference and immutable audit. Do not enable partial redemption
  or convert a gold/silver obligation into cash. Do not deduct an invented cancellation fee
  or award an undefined benefit.
- A genuinely unused agreement gets a separate audited cancellation transition with
  no redemption or payment event. Zero *current balance* is not enough to prove unused:
  paid/reversed/refunded/redeemed histories and pending orders require separate review.
- Retain append-only correction evidence. A settlement reversal must restore the
  correct grade liability and a controlled closure-pending state, not silently reopen
  payments. Define which request states can be withdrawn/rejected before mutation.
- Customer/owner screens and statements must explain request, pending settlement,
  completed settlement and unused cancellation distinctly. Owner-on-behalf actions
  require authorization evidence; a request is not itself proof of jewellery delivery.

23 October 2026 B1 implementation boundary: configured agreements only; no legacy
cutover or activation. A request starts PENDING and is distinct from owner ACCEPTED
closure. Pending requests may be withdrawn by the customer (or owner with actual
authorization reference) or rejected by the owner. Accepted closure may receive
investigation notes but cannot be withdrawn/rejected to silently reopen contributions.
Request/event evidence is retained with idempotency and stale-sequence checks under
the account lock. Acceptance blocks initiation/resumption, not existing captures,
allocation recovery or authorized cash corrections. A request is never a delivery,
refund, cancellation or settlement event; B2/B3 remain separate. Private screens and
`check_scheme_closures` expose review state; zero counts are not closure authorization.

23 October 2026 B2 implementation boundary: configured-only unused cancellation is
now a separate owner-confirmed action after ACCEPTED closure. CANCEL is the immutable
V1 event proving the conservative no-history predicate; request/account CANCELLED are
atomic projections under the account lock. Any contribution attempt of any status or
mode, redemption, reservation, instalment investigation or outage resolution prevents
this operation. Empty scheduled periods and closure notes are permitted. No financial
rows, deletion, login change or reopening are created. Migration 0032 adds status/action
shapes and a configured-only cancellation constraint, with no backfill. Full settlement,
legacy cutover, privacy-retention changes and actual plan activation remain separate.

## Deferred: Customer-authored configurations

The initial builder is owner-only. Customers may choose an offered plan and permitted
enrolment values, but cannot author rules. Later, a customer may propose a configuration
from the same server-validated catalogue for owner approval. That proposal must create
no agreement, payment permission, rate lock, allocation, benefit or entitlement. Owner
approval of a proposal is not permission to rewrite an existing agreement; customer
confirmation and the normal enrolment service remain necessary. No customer builder
UI, API, permissions or approval shortcut is included in the immediate work.

## Delivery and acceptance

Implementation boundary recorded 22 October 2026: split P1 into preparation (P1a) and
agreement integration (P1b). P1a can save/reuse immutable typed configurations and
preview selected amounts, but new pinned plans must remain inactive/unlisted and cannot
be enrolled. Enforce that in the database and enrolment service, without a feature-flag
bypass. This resolves the dependency on B: a FULL_ONLY configuration must never become
a live promise while the settlement service still allows partial redemption. The legacy
plan columns on a pinned draft are a validated compatibility projection, not an executable
customer-fixed policy. P1b must persist/use explicit agreement policy and customer selections;
it must not mistake the draft's VARIABLE projection for the customer's selected fixed rule.
Existing plans remain unconfigured, so P1a changes no existing contract or payment behavior.

23 October 2026 implementation note: P1b adds explicit agreement/request configuration
references, immutable individual amount snapshots and optional variable increments.
Customer confirmation evidence and approval inputs carry the pinned configuration and
selected amount; payment channels use shared validation against frozen terms. Migration
0023 leaves old rows null, with no inferred acceptance. These paths are wired behind
the unchanged enrolment/publication gates; tests use synthetic configured agreements,
not a production activation bypass. Configured redemption fails until B is implemented.

A is a separately reviewable migration/service/UI change with regression evidence.
Next implement the policy/configuration foundation and customer-fixed amounts, then
instalment tracking, eligibility and benefits, then B's full-only settlement/closure.
The owner builder may publish only combinations supported end-to-end. Anytime variants
follow separately; customer-authored proposals remain deferred. Each stage needs its
own migration/state-machine review, financial/race tests and disabled-first acceptance.
No production deployment
is authorized by this ADR. Preserve backups, rollback images and all financial records;
never restore an older database merely to undo new plan metadata or a real settlement.

## Boundaries

23 October 2026 P4 integration decision: supported offers require an owner-reviewed,
immutable publication revision and the default-off `CONFIGURED_PLANS_ENABLED` release
gate. Migration 0034 adds that revision reference; it publishes nothing and changes no
agreement. Publish/withdraw serialize with offer editing and enrolment on the plan row.
Published identity/grade edits require withdrawal; policy changes require a separate
version/draft. Accepted agreements retain their revision, individual amount and grade.
Monthly periods are created atomically with enrolment. Disabling this gate stops new
configured intake/enrolment but is NOT a payment pause or cancellation of existing
agreements. Publication is not self-enrolment and grants no financial entitlement.
Customer application confirmation binds the publication revision; direct owner forms
bind the current offer digest. No new benefits, INR denomination, anytime or legacy
contract conversion is approved here. Local integration does not authorize activation.

23 October 2026 P2b.2 integration note: existing online/cash services now invoke the
ledger explicitly under agreement locks. Callback or API recovery without signed
timing evidence creates AWAITING; the subsequent signed event can qualify it. Before
provider order I/O, an independent durable ORDERING decision records intent; a lost
response or local write/commit failure leaves the attempt blocked, not blindly retried.
The service owns this transaction boundary (no enclosing caller transaction). Local
checkout expiry alone never releases a claim. The existing provider-backed untouched
order reconciliation creates a source-linked RELEASED decision; late capture is a
non-occupying RELEASED_REVIEW so a replacement claim is retained without counting the
old payment twice. The account is held against further initiation, and existing provider
exception handling owns the unresolved funds. Ambiguous order errors remain reserved
for explicit investigation. Migration 0026 changes lifecycle schema only. These are
service integrations behind unchanged publication/enrolment gates, not completion of
outage resolution, policy eligibility or settlement.

23 October 2026 P2b.1 implementation boundary: add exclusive per-period reservations
with append-only source-linked decisions, but leave all payment entry-point integration
and configured activation gates unchanged. Reservation state is a checked projection;
it is not a second money/metal ledger. A cash correction must reference an existing
authorized financial reversal. No generic manual credit, free instalment, timeout-based
release or retroactive legacy qualification is allowed.

Timing design: [Razorpay captured webhook payloads](https://razorpay.com/docs/webhooks/payments/)
contain payment creation and event creation timestamps. Our conservative inference is
to require both inside the reserved window/deadline, with a one-second uncertainty
margin for provider Unix-second precision. This does not claim either is an exact capture
timestamp. Verify the original processed payload hash, identities, currency and amount;
retain only source references and timing, not raw payload/customer data. Delivery time
does not define lateness. Missing, inconsistent or boundary-crossing evidence stays in
review; later duplicates cannot silently clear that review. Paid-unallocated payment
evidence is separate from allocatable/settleable entitlement. P2b.2/P2b.3 must integrate
all channels atomically and supply reconciliation release, late-capture and auditable
outage/review resolution before this family can activate. Tests of internal primitives
are not a completed configured checkout journey.

No new framework, CMS financial editing, background queue or accounting system.
Python model immutability and read-only admin are application protections; privileged
SQL/QuerySet writes can bypass them and remain restricted operational interventions.
This decision approves the configurable structure, not unspecified numeric discount
schedules, due/grace/extension values, a fulfilment/inventory system, legal approval
or a new regulatory interpretation. Draft configurations with missing business terms
cannot be published. Keep current cash restrictions until separately authorized.
