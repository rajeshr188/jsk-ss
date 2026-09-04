# Domain Rules

This is the canonical source for stable business rules.

## Authentication and onboarding rules

- **AUTH-001:** A login account is not itself an active savings agreement; only a valid `SchemeAccount` represents enrolment.
- **AUTH-002:** Owners create customer login/profile records and issue a time-limited, one-time password-setup invitation; owners and staff must never choose or transmit a temporary customer password.
- **AUTH-003:** Future public registration must create a complete customer profile, verify identity/contact data as configured, and remain awaiting owner approval until enrolment.
- **AUTH-004:** No publicly registered but unenrolled customer may contribute. Reopening allauth signup alone is insufficient.
- **AUTH-005:** Only an active owner may issue or replace a customer invitation. Issuing a replacement revokes every older unused invitation for that customer; an account with a usable password must use password reset instead.
- **AUTH-006:** Invitation secrets are random, stored only as one-way digests, expire within the configured bounded lifetime, and are accepted at most once. Secret-bearing responses are not cacheable, their URL paths are withheld from Referer headers, and their request paths are excluded from edge access logs. The origin-only referrer policy must still permit Django to validate same-origin password submissions.
- **AUTH-007:** Email-provider acceptance is delivery evidence, not proof that the customer received or used the message. Invitation acceptance establishes login access only and never creates a `SchemeAccount`, contribution, or financial entitlement.
- **AUTH-008:** Nonblank login emails are unique case-insensitively. Historical duplicates must be investigated and resolved deliberately without automatically deleting, merging, or reassigning customer or financial records.

## Scheme and contribution rules

- **SCH-001:** Historical liabilities remain separated into `CASH` and exact Gold or
  Silver grade dimensions; new production enrolments are limited to explicitly
  offered metal grades.
- **SCH-002:** An account snapshots the plan's economic terms at enrolment; later plan edits do not rewrite the agreement.
- **SCH-003:** Minimum and default durations are at least 12 months; the agreed duration cannot be below the plan minimum.
- **SCH-004:** Eligibility is the account start date plus agreed calendar months. Eligibility does not itself redeem or close an account.
- **SCH-005:** A plan appears on the public savings plans page only when it is both active and explicitly marked publicly listed. New and migrated plans default to not publicly listed.
- **SCH-006:** Public plan edits affect the current offer for future enrolments only; existing scheme accounts retain their snapshotted economic terms.
- **SCH-007:** CASH enrolment and contribution initiation are development-only
  compatibility paths used to retain historical financial regression coverage.
  With `DEBUG=False`, the service layer rejects both operations, the owner cannot
  select CASH during enrolment, and direct payment URLs for historical CASH accounts
  are blocked. Existing CASH records remain readable and are never rewritten.
- **SCH-008:** Every metal account is permanently tied at enrolment to one immutable
  `MetalGrade`. A plan offering controls future enrolment only; disabling an offering
  never changes an existing agreement.
- **SCH-009:** Existing pre-grade Gold contracts remain `GOLD_24K_9999` and existing
  Silver contracts remain `SILVER_999`. They are never numerically converted or
  relabelled as `GOLD_22K_916`.
- **CON-001:** Amount rules (`FIXED`/`VARIABLE`) and frequency rules (`ONCE_PER_MONTH`/`FLEXIBLE`) are independent.
- **CON-002:** Monthly periods use deterministic calendar keys such as `2026-08`, never rolling 30-day windows.
- **CON-003:** `ONCE_PER_MONTH` permits one successfully paid contribution per scheme account and calendar month. Both `PAID` and `PAID_UNALLOCATED` consume the opportunity; `PENDING`, `FAILED`, `ABANDONED`, and corrected `REVERSED` records do not.
- **CON-004:** `FLEXIBLE` permits multiple successful contributions in the same calendar month.
- **CON-005:** Fixed contributions must exactly equal the snapshotted fixed amount. Variable contributions must remain within snapshotted minimum/maximum boundaries.
- **CON-006:** Contributions are rejected before the account start date, after redemption, and after eligibility unless the agreement snapshot explicitly permits them.

## Payment and metal rules

- **PAY-001 / FIN-001:** One successful payment benefits a customer at most once; server verification and idempotency are mandatory.
- **PAY-002 / FIN-005:** Failed payments create no entitlement.
- **PAY-003:** The mock gateway is available only with `DEBUG=True` and `PAYMENT_GATEWAY=mock`; it never represents a real transfer.
- **PAY-004:** Razorpay requires an explicit `test` or `live` mode whose key-ID prefix matches. Every order and webhook records that mode, and a reference from one mode may never be resumed, verified, or reconciled through the other. Browser success is not entitlement until HMAC verification and a server-side captured-payment check match the locally stored order, amount, and INR currency.
- **PAY-005:** Only a signed `payment.captured` webhook may independently confirm a Razorpay contribution. Signature verification uses the untouched request body.
- **PAY-006:** Razorpay order IDs, payment IDs, and webhook event IDs are unique at their respective database boundaries. Duplicate callbacks or webhook deliveries return the existing result and create no additional entitlement.
- **PAY-007:** A once-per-month account may have at most one pending Razorpay contribution for a calendar period. Reopening the payment flow resumes the existing order.
- **PAY-008:** Provider callbacks are matched to a customer-owned local contribution; the browser-supplied order ID is never trusted in place of the database value.
- **PAY-009:** A Razorpay order becomes application-side `ABANDONED` only after it
  exceeds the operator-selected age and a mode-matched provider inspection reports
  `created`, zero attempts, zero payments, zero paid amount, and the full amount due.
  Dry-run is the default. An applied decision retains the provider order and locked
  Scheme Rate and appends an immutable audit event containing the provider snapshot.
- **PAY-010:** Razorpay's Orders API does not cancel or invalidate an order. Therefore
  `ABANDONED` never means provider-cancelled. The application stops offering that
  checkout and may create a replacement attempt, but a later capture is rejected from
  automatic entitlement and becomes a failed-webhook exception for immediate manual
  provider reconciliation and refund handling.
- **PAY-011:** Pending mode-matched orders remain resumable until paid, failed, or
  reconciled as abandoned. Abandonment is evaluated per order for both monthly and
  flexible-frequency accounts; closing one flexible attempt never changes another.
- **PAY-012:** New Gold or Silver payment exposure is allowed only when the
  environment emergency kill switch, audited global/per-metal manual controls, and
  optional Asia/Kolkata weekly schedule all permit it. The same decision blocks both
  local contribution/provider-order creation and customer Checkout resumption.
- **PAY-013:** The weekly payment schedule uses half-open local intervals: opening is
  inclusive and closing is exclusive. Its migration is default-off, and an owner must
  explicitly activate the reviewed hours. When current-day rate review is required,
  a metal remains closed until its current Scheme Rate was published on that India-
  local date.
- **PAY-014:** A new-payment pause never disables Razorpay callback or signed-webhook
  verification and never rejects a captured payment merely because the schedule or an
  owner pause is now closed. Any in-flight capture is confirmed idempotently and its
  entitlement uses the contribution's original locked Scheme Rate.
- **PAY-015:** An invalid or conflicting webhook request returns `400`. A signed event
  that is durably processed, ignored, or classified for owner review returns `200`;
  review acceptance never creates entitlement. A signed event interrupted by a
  transient application failure remains retryable and returns `503` without exposing
  internal exception details.
- **PAY-016:** Webhook processing and recovery attempts are append-only evidence. They
  retain a source, outcome, actor label, mandatory reason, bounded safe detail, and
  compact provider identifiers/state, but never credentials, signatures, customer
  contact data, or a full webhook body.
- **PAY-017:** Owner webhook recovery is dry-run first and mode-matched. Automatic
  application requires a fresh provider read whose payment ID, order ID, INR amount,
  currency, captured status, and local contribution all match exactly. It must use
  the existing idempotent confirmation and original locked-rate allocation services.
  Abandoned or failed contributions and any mismatch remain manual refund/
  reconciliation cases with no override in the recovery UI.
- **PAY-018:** Every new Razorpay contribution snapshots an application Checkout
  deadline from the configured 3–15 minute policy when its pending record is created.
  The default is 10 minutes, and later configuration changes never rewrite an
  existing deadline or locked Scheme Rate.
- **PAY-019:** The application must not render or resume Checkout after that deadline.
  A rendered page passes the remaining seconds to Razorpay and disables its local
  action at expiry, but browser timing is advisory and is not provider cancellation.
- **PAY-020:** Checkout expiry alone never changes payment status, releases a monthly
  attempt, or creates/removes entitlement. Provider-backed, dry-run-first
  reconciliation remains required before an untouched order becomes application-side
  `ABANDONED`.
- **PAY-021:** A valid captured callback or signed webhook received after Checkout
  expiry but before provider-verified abandonment is confirmed idempotently from its
  original locked Scheme Rate. A capture after `ABANDONED` remains a financial
  exception; expiry is never a reason to ignore received money.
- **PAY-022:** In-store cash is an owner-recorded payment channel for an existing
  Gold or Silver scheme contribution. It creates exact-grade metal entitlement and
  never creates a legacy CASH-mode INR balance, cash redemption right, or customer
  self-service payment path.
- **PAY-023:** An in-store cash receipt requires a server-retained review followed by
  explicit owner confirmation that cash was physically received. It uses server time,
  supports no backdating or split tender, and records one immutable idempotent receipt,
  actor label, internal reference, optional unique paper reference, and audit reason.
- **PAY-024:** Agreement amount/frequency/date rules, all payment-operation controls,
  and the current exact-grade Scheme Rate apply to in-store cash. A changed rate or
  changed preview must be reviewed again. Any pending Razorpay order on the account
  blocks cash recording until provider reconciliation removes the capture race.
- **PAY-025:** Cash receipt and its `PAID_UNALLOCATED` contribution commit before
  metal allocation. Allocation reuses the exact locked-rate workflow; a failure stays
  visible for owner retry and never loses evidence that the showroom received money.
- **PAY-026:** An erroneous in-store cash record is never edited or deleted. One
  immutable reversal changes the original to terminal `REVERSED`, preserves its
  receipt/rate/allocation, and removes that exact allocation from active entitlement.
  A corrected amount/account requires a separate newly reviewed receipt.
- **PAY-027:** Routine cash-entry reversal is owner-only, bounded by the configured
  correction window, and blocked after downstream unreversed redemption or when its
  exact allocation is no longer available. It is a bookkeeping correction, not a
  customer cancellation or cash-refund workflow.
- **PAY-028:** Daily showroom reconciliation separately reports cash received,
  corrections, and net recorded cash. Cross-record integrity must pass before and
  after deployment and during routine financial review.
- **METAL-001 / FIN-002:** A metal contribution creates at most one successful allocation.
- **METAL-002 / FIN-003:** A Scheme Rate used by an allocation is immutable.
- **METAL-003 / FIN-004:** Historical allocated grams never change when a newer Scheme Rate is published.
- **METAL-004:** Allocation quantity equals INR contribution divided by the locked
  Scheme Rate for the account's exact grade, rounded to 6 decimal places using
  `ROUND_HALF_UP`.
- **METAL-005:** A verified metal payment is durably recorded as `PAID_UNALLOCATED`
  until its allocation is stored, then transitions to `PAID`. This recovery state
  covers allocation exceptions and process interruption; it is not a missing-rate
  workflow. Retry must reuse the contribution's original lock.
- **METAL-006:** `GOLD_22K_916`, `GOLD_24K_9999`, and `SILVER_999`
  liabilities are independent. Account, rate, allocation, and redemption grades must
  match; base metal alone is not a sufficient financial key.
- **RATE-001:** Only a manually published Jai Sri Krishna Jewellery `SchemeRate` for
  the exact account grade may be used for a new allocation.
- **RATE-002:** A metal contribution must lock its current applicable grade-specific
  `SchemeRate` before mock payment initiation, Razorpay order creation, or final
  confirmation of an in-store cash receipt.
- **RATE-003:** Publishing a new `SchemeRate` never changes an already locked contribution.
- **RATE-004:** Publishing a new `SchemeRate` never changes historical `MetalAllocation` quantity.
- **RATE-005:** A metal payment cannot be initiated when no valid current
  `SchemeRate` exists for that exact grade; another grade's rate is never a fallback.
- **RATE-006:** Published Scheme Rates used by financial allocations are immutable and protected from deletion.
- **RATE-007:** Current rate means the latest applicable record for the exact grade
  ordered by `effective_from`, publication time, and ID. Publication appends a
  record; there is no mutable active flag.
- **RATE-008:** The initial immutable definitions are `GOLD_22K_916` fineness
  `0.916000`, `GOLD_24K_9999` fineness `0.999900`, and `SILVER_999` fineness
  `0.999000`. Publication accepts a positive `Decimal` rate only.
- **RATE-009:** Only an active owner or superuser may publish. Every publication records publisher, timestamp, optional note, and immutable audit event.
- **RATE-010:** Rates are recorded independently for each grade. The application does
  not derive a customer rate from another purity and does not silently convert,
  interpolate, or reuse one grade's rate.

## Historical cash bonus rules

These rules preserve existing CASH records and regression behavior. They do not
authorize new production CASH enrolments or contributions under `SCH-007`.

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

- **ELIG-001:** Contractual eligibility is `start_date + agreed_months` in exact
  calendar months. If the corresponding day does not exist in the destination month,
  the destination month's final day applies.
- **ELIG-002:** Eligibility begins on `eligible_from` in the India-local calendar.
  There is no early-redemption grace period and eligibility does not expire while an
  entitlement remains unredeemed.
- **ELIG-003:** Weekends, public holidays, showroom closures, store hours,
  contribution schedules, and manual or automatic payment pauses never shift
  `eligible_from`. They may delay in-person fulfilment until the showroom next opens.
- **ELIG-004:** Eligibility forecasts use ordinary calendar-day bands. Post-
  eligibility contributions remain governed only by the agreement's snapshotted
  contribution setting.
- **RED-001 / FIN-006:** A customer cannot redeem more than the outstanding entitlement.
- **RED-002:** Before redemption, effective status is derived under ELIG-001 through
  ELIG-004: before `eligible_from` is `ACTIVE / NOT YET ELIGIBLE`; on or after
  `eligible_from` is `REDEMPTION_ELIGIBLE`.
- **RED-003:** Reaching `eligible_from` never closes an account, mutates its stored status, or creates a redemption. Only a completed redemption may make it `REDEEMED`.
- **RED-004:** Owner forecast bands are exclusive: eligible now, days 1–30, days 31–60, and days 61–90. Redeemed accounts are excluded from every open-account band.
- **RED-005:** A completed redemption is an immutable, owner-recorded financial event. Contributions, allocations, and earlier redemptions remain visible.
- **RED-006:** Cash principal outstanding equals paid cash contributions minus the
  principal components of completed redemptions; cash redeemable amount adds only
  outstanding earned bonus. Gold and silver outstanding each equal paid allocated
  grams minus completed redemptions in the same exact grade.
- **RED-007:** A historical CASH account with an existing entitlement may settle as
  `CASH` or `JEWELLERY_PURCHASE`; gold and silver accounts may settle as `METAL` or
  `JEWELLERY_PURCHASE`. Preserving legacy settlement does not reopen CASH enrolment or
  contributions. Metal-to-cash conversion is undefined and rejected.
- **RED-008:** Partial redemption leaves an eligible account open. Redeeming the exact remaining entitlement changes its stored status to `REDEEMED`.
- **RED-009:** Every redemption submission has a unique idempotency key. Replaying the same key and details returns the existing event; changing details with a used key is rejected.
- **RED-010:** Jewellery-purchase redemption requires an external invoice or sales reference. The MVP records the reference, entitlement settled, and notes but does not manage inventory or invoices.
- **RED-011:** A redemption correction appends one immutable `RedemptionReversal`; it never edits or deletes the original redemption. Reversed settlements are excluded from outstanding-balance and liability subtraction.
- **RED-012:** Reversing any settlement restores that denomination's entitlement. If the account was fully redeemed, the stored account status reopens to `ACTIVE`; date-derived eligibility still presents it as redemption eligible.
- **FIN-007:** INR and each exact metal-grade liability are never combined into a
  single balance.
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
- **AUD-005:** Every owner change to the payment operations schedule or manual pause
  state requires a reason and appends the complete before/after policy. UI changes may
  not rewrite or delete earlier operations-control audit events.
- **EXC-001:** The owner exception queue derives unresolved paid-unallocated/failed-allocation contributions and failed or mismatched webhook reconciliation from their authoritative source records.
- **EXC-002:** Resolving an allocation exception uses the existing idempotent retry service. A queue display or acknowledgement must never itself create entitlement.
- **EXC-003:** A signed permanent webhook mismatch is an explicit
  `REVIEW_REQUIRED` exception. Owner inspection does not mutate entitlement; an
  applied recovery requires exact provider evidence, a mandatory reason, and an
  immutable `WEBHOOK_RECOVERY` audit event.

## Owner liability reporting

- **LIA-001:** Outstanding cash principal is paid cash contributions minus completed cash redemptions. Pending and failed attempts contribute zero.
- **LIA-002:** Outstanding quantity for each grade is paid allocations minus completed
  redemptions in that exact grade. The primary metal liabilities remain grams.
- **LIA-003:** Indicative metal exposure equals outstanding grams multiplied by the current Scheme Rate, rounded to 2 money decimal places with `ROUND_HALF_UP`. It does not rewrite historical allocations.
- **LIA-004:** Cash principal and the separate exposures for every metal grade are
  never added into a single headline liability total.
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
- **DOC-006:** INR amounts and each exact grade's grams remain separate in documents
  and exports. Indicative current metal exposure is not exported as booked cash
  liability.
- **DOC-007:** MVP documents are on-demand printable HTML acknowledgements, not tax invoices or archived legal snapshots.

## Catalogue boundaries

- **CAT-001:** Catalogue content supports product discovery and showroom enquiry only.
  It must not become an inventory, cart, checkout, invoice, tax, fulfilment, or payment
  system.
- **CAT-002:** An optional product display price is informational INR catalogue
  content. It must be positive when present and must never be sourced from or treated
  as a Scheme Rate, contribution amount, customer entitlement, or final invoice price.
- **CAT-003:** Every product has a stable case-insensitively unique product code and
  one reusable category; optional reusable marketing collections do not determine
  financial or fulfilment behavior.
- **CAT-004:** Product gallery ordering and image alt text are editorial content kept
  with Wagtail revisions. Public pages may use generated renditions, while approved
  source photographs remain subject to the separate media-recovery policy.
- **CAT-005:** Draft, preview, publish, and unpublish state remains Wagtail-owned.
  Public catalogue reads must expose only live public pages, and CMS access always
  requires explicit Wagtail authorization independent of application owner/customer
  roles.
- **CAT-006:** Catalogue Editors may prepare and submit content but cannot publish.
  Catalogue Publishers and Catalogue Administrators may approve, publish, and
  unpublish within the catalogue subtree. Catalogue Administrators additionally hold
  destructive catalogue-content/media permissions but no financial, user-management,
  or document-library authority.
- **CAT-007:** Catalogue images are restricted to the dedicated catalogue media
  collection. Every submission, approval, publication, and unpublication retains its
  Wagtail workflow/audit actor; group assignment is a separate explicit administrator
  action and is never derived from `CustomUser.role`. `wagtailadmin.access_admin`
  additionally requires `is_staff=True`, including for users assigned to a catalogue
  group by mistake.
- **CAT-008:** Public discovery exposes only live, unrestricted products beneath the
  single live catalogue root. Search, category/collection filtering, result counts,
  structured data, and pagination must never disclose drafts or pages outside that
  subtree; result pages are bounded to 12 products.
- **CAT-009:** Catalogue photographs use Wagtail-generated responsive renditions with
  editorial alt text and intrinsic dimensions. Product metadata may describe a
  discoverable product but must not publish an online offer, stock status, checkout,
  or final-price promise.
- **CAT-010:** Global catalogue navigation requires both a live/public catalogue root
  and the explicit `PUBLIC_CATALOGUE_ENABLED` rollout flag. Keep the flag disabled
  until reviewed content and its direct public URLs pass rollout checks; disabling it
  removes discovery links without changing Wagtail revision or publication history.
- **CAT-011:** `SchemePlan` and its audited Django workflows remain authoritative for
  all savings-plan and financial terms. Any future Wagtail-managed Scheme Plan image
  or marketing copy is presentation-only: it must link to rather than replace the
  plan, must not duplicate or control financial fields, and its deletion, unpublishing,
  or media failure must not change enrolment terms or historical financial records.

## Editorial content boundaries

- **EDIT-001:** Wagtail may own only the About and Our Story editorial fields in this
  phase. The homepage, contact identity, policies, public `SchemePlan` terms, and every
  authenticated or financial workflow remain Django-owned.
- **EDIT-002:** `/about/` and `/our-story/` remain stable Django named routes. A route
  serves its single live/public Wagtail page only when
  `PUBLIC_EDITORIAL_PAGES_ENABLED=True`; a missing, draft, restricted, or unpublished
  CMS page falls back to the reviewed Django template.
- **EDIT-003:** Plan, rate, payment, eligibility, fulfilment, and policy explanations
  rendered on the About page remain application-owned template content. Editorial
  rich text is limited to business background and must not become a source of
  financial or compliance terms.
- **EDIT-004:** Editorial CMS access requires explicit active staff membership in a
  dedicated Editorial group. Editors may revise and submit; Publishers and Editorial
  Administrators may approve and publish. Editorial permissions and media are
  isolated from Catalogue groups and from `CustomUser.role`.
- **EDIT-005:** Our Story remains absent from public navigation until a separate
  display decision. Publishing its Wagtail revision may replace the directly
  accessible static page, but cannot add a navigation link by itself.
- **EDIT-006:** Optional editorial images require meaningful alt text, use the
  dedicated Editorial media collection, and remain subject to `FW-MEDIA-002` source-
  original retention until isolated media backup and restore proof exists.

## Precision

Money uses 2 decimal places. Contribution and cash-redemption input with more than 2
decimal places is rejected rather than silently rounded. Cash bonus calculations use
`ROUND_HALF_UP` to 2 decimal places. Metal quantities, allocation calculations, and
owner metal-redemption entry use 6 decimal places; excess input precision is rejected.
Customer-facing gram values render to 3 decimal places without changing the stored
quantity. Scheme Rates use 4 decimal places and grade fineness metadata uses 6.
