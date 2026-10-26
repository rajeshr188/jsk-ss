# Domain Rules

This is the canonical source for stable business rules.

## Authentication and onboarding rules

- **AUTH-001:** A login account is not itself an active savings agreement; only a valid `SchemeAccount` represents enrolment.
- **AUTH-002:** Owners create customer login/profile records and issue a time-limited, one-time password-setup invitation; owners and staff must never choose or transmit a temporary customer password.
- **AUTH-003:** Public registration remains separate from closed allauth signup. Legacy access-only applications collect a complete profile. Plan-first applications (both registration and enrolment-request switches enabled) collect contact details, selected plan/grade/preferences and policy consent first, then postal address and current offer/start-date confirmation after email verification. Neither intake creates a user, customer, agreement, password or entitlement before owner review.
- **AUTH-004:** The applicant must verify control of the email address through a bounded one-time token and then remain `AWAITING_OWNER_APPROVAL`. An active owner must confirm the mobile number and record a reason before approval or rejection.
- **AUTH-005:** Only an active owner may issue or replace a customer invitation. Issuing a replacement revokes every older unused invitation for that customer; an account with a usable password must use password reset instead.
  A matching expired, unused, unsuperseded invitation secret can record one setup-help
  request through CSRF POST. It cannot issue/extend credentials, activate login or send
  replacement mail. Unknown, incorrect, ineligible and used links have the same generic
  response; inactive/erased logins are ineligible. Owner recovery uses existing services.
- **AUTH-006:** Invitation secrets are random, stored only as one-way digests, expire within the configured bounded lifetime, and are accepted at most once. Secret-bearing responses are not cacheable, their URL paths are withheld from Referer headers, and their request paths are excluded from edge access logs. The origin-only referrer policy must still permit Django to validate same-origin password submissions.
- **AUTH-007:** Email-provider acceptance is delivery evidence, not proof that the customer received or used the message. Invitation acceptance establishes login access only and never creates a `SchemeAccount`, contribution, or financial entitlement.
  Linked-plan activation chooses a server-derived customer-scoped agreement destination
  for subsequent password sign-in; it never auto-signs in or accepts a supplied external
  destination. Access-only invitations retain the existing login entry.
- **AUTH-008:** Nonblank login emails are unique case-insensitively. Historical duplicates must be investigated and resolved deliberately without automatically deleting, merging, or reassigning customer or financial records.
- **AUTH-009:** Public registration responses do not disclose existing email, mobile, application, or throttle state. Per-source and per-identity database-backed limits and a honeypot provide the baseline abuse boundary; retained attempt identifiers are one-way digests.
- **AUTH-010:** Legacy access-only approval creates identity/profile and invitation only. A linked `PlanApplication` must use coordinated approval: lock registration, application, plan and offering; recheck identity conflicts, verified email, completed address, unexpired application, exact grade and latest customer-confirmed terms/start date; atomically create identity, invitation and one separate `SchemeAccount` through existing services. Retries/concurrent approval return the same agreement. Identity decision fields and immutable financial audit/snapshots remain separate. Invitation delivery runs after commit, with recorded failure and existing owner resend recovery. Login activation still creates no financial records.
- **AUTH-011:** Public email-verification paths are direct and untracked, excluded from edge access logs, redacted from application logs, non-cacheable, and mutated only by a CSRF-protected confirmation POST.
- **AUTH-012:** Google is an optional credential for an already-approved customer. It never creates or approves a user, customer profile, scheme agreement, payment permission, or financial entitlement.
- **AUTH-013:** Only an active, non-privileged customer with a usable password and verified local email may explicitly connect Google after local authentication. The provider must assert the same verified email at connection time.
- **AUTH-014:** An unconnected provider identity is never authenticated or automatically linked by email. Subsequent Google login uses only the explicitly bound provider subject and still requires an active eligible customer.
- **AUTH-015:** Password login and reset remain available, provider tokens are not stored, and the fail-closed Google switch may disable social login independently. OAuth callback responses are non-cacheable and omitted from edge access logs.
- **AUTH-016:** Customer self-service unlink is unavailable until an append-oriented, authorized correction workflow is defined. A suspected compromise requires customer deactivation or the global Google kill switch while the binding is reviewed.
- **AUTH-017:** Account deletion is a feature-gated verified request, not `CustomUser`
  deletion. Public responses never disclose account existence; verification secrets
  are digest-only, one-time, bounded, direct, non-cacheable, CSRF-confirmed, and
  excluded from application and edge logs.
- **AUTH-018:** Verification contains the account by disabling customer login,
  revoking sessions, plan-progress access and the Google credential, superseding unused invitations, and
  blocking new customer-initiated actions. Containment never deletes a customer,
  scheme, contribution, rate lock, allocation, receipt, redemption, correction, or
  audit record and never blocks provider callbacks or financial reconciliation.
- **AUTH-019:** Only an active owner with recent authentication may append a deletion
  review decision. ADR-0015 permits owner-operated implementation without a blanket
  professional-sign-off prerequisite; execution still needs an explicit category/field
  disposition, justified retention and review dates. Owner completion removes eligible
  account identity and credentials while preserving financial history; retained
  records use `COMPLETED_WITH_RETENTION` and a review due date. Erased logins cannot
  be restored or reused for new agreements/contributions. Pending payments,
  unallocated entitlements and unresolved matched webhooks require review first.
  Zero balances/counts do not establish the absence of external obligations. Preview
  balances preserve separate agreements, INR principal/bonus and exact metal grades;
  financial facts are never changed by a privacy preview.
  The owner may enter shared retention start/condition/review terms once, with
  category-specific overrides. Every saved category still includes its own explicit
  treatment, purpose, minimum records and resolved terms; missing terms block completion.
- **AUTH-021:** Completion is atomic and idempotent. Its durable notice is retried
  separately; SMTP acceptance clears the temporary delivery address but does not
  prove receipt. Retention reviews may remove more eligible profile fields but
  never restore erased data or automatically purge financial evidence. Review
  notices require a still-retained contact route; backup recovery is not a source
  for restoring erased contact information.
- **AUTH-020:** Account deletion never forfeits an INR or exact-grade metal entitlement.
  A completed-with-retention outcome must identify the retained categories, purpose,
  next review date, and support route without claiming that provider, backup, or
  statutory transaction evidence was erased.
  INR purchase-credit principal is distinct from legacy cash principal/bonus and
  each exact metal grade. Retained benefit rights are separately inventoried; no
  review or return creates a cash-refund benefit balance. Unknown principal is shown
  as needing reconciliation, never zero. Invalid principal/disposition/benefit evidence
  blocks completion or further identity removal. Open principal or an unfulfilled
  recorded benefit requires showroom name/email retention with a stated purpose.
  Completed minimization preserves proposal, fulfilment, full-return, award, invoice,
  reversal and review evidence, including embedded identity requiring justified retention.

- **AUTH-022:** Plan progress is not a public identity lookup or a login credential. A
  separately minted, digest-only, expiring email secret grants a server-side session
  only on CSRF-protected POST. GET does not grant access or verify identity. Token-free
  progress URLs require that grant; replacement invalidates old links and sessions.
  Both paths are non-cacheable, origin-only referrers, excluded from edge logs,
  redacted in Django logs and never instrumented by funnel analytics. Deactivated or
  erased approved logins cannot use progress access. Existing owner recovery replaces
  progress access only for verified, unexpired applications; no expiry is extended.
- **AUTH-023:** Initial and final plan confirmations are append-only revisions with
  decimal-string offer snapshots, grade, preferences, policy/disclosure versions and
  timestamps. Final confirmation includes the requested start date. Material offer,
  policy, grade, duration or start-date changes require a new customer confirmation;
  a stale displayed offer cannot silently confirm current terms. Owners cannot alter
  the confirmed duration/start date on coordinated approval. A start date that passes
  before approval requires fresh customer confirmation of today or a future date.
  Historical records are not backfilled with inferred plan intent.

## Scheme and contribution rules

- **UX-001:** Public offer amounts, contribution rules, available grades and durations
  come from active/listed `SchemePlan` records and offerings. Unreviewed free-text plan
  descriptions are not public marketing authority. A selected-plan entry never creates
  an agreement, promises a rate/benefit or permits payment.
- **UX-002:** Customer Pay visibility derives initiation availability and agreement
  date/frequency/status rules from server reads. Every financial mutation still rechecks
  its own authoritative rules. Abandoned attempts must not be labelled pending or
  provider-cancelled. Browser cancellation, expiry or lost confirmation cannot establish
  a financial outcome; protected status pages read the stored contribution only.
- **MEASURE-001:** Optional public navigation measurement stores only India-local day,
  allowlisted stage and aggregate count. No visitor/customer identifiers, request URLs,
  query strings, verification links, contact details or payment references enter this
  measurement. It does not instrument token-bearing routes or add third-party scripts.
- **UX-003:** Owner Today and Applications are read-only projections of existing
  registration, request and financial-exception records. Only active owners or active
  superusers may access them; CMS/staff access alone grants no financial/customer
  permission. Verified identity reviews precede plan reviews and email recovery;
  unresolved expired plan requests remain visible until explicitly closed. Customer
  context uses approved-user/customer/agreement foreign keys, never an unverified
  applicant email match. Lists/search have fixed bounds and stable pagination. A
  shared review coordinates identity and agreement only for linked plan applications;
  legacy identity/request flows retain their own services. Verified applicants missing
  details wait for the customer unless progress delivery needs recovery. Existing
  services still recheck identity, offer, confirmation and financial rules.
- **MEASURE-002:** Outcome totals are read-only aggregates of authoritative records;
  live online and showroom-cash first payments are separate, test/mock/pending/failed
  payments are excluded, and later payments cannot become first merely because the
  report date range changes. Navigation totals include repeat/automated requests and
  are not unique people. Period throughput is not a joined conversion cohort.
- **UX-004:** Customer dashboard application progress appears before balances, scoped
  by explicit approved-user/customer/agreement links with bounded application previews.
  First-payment and continuation actions derive recorded contributions and snapshotted
  agreement rules/current operational availability. Pending confirmation/allocation
  directs to protected recorded status, never another first payment. Test/practice
  records are labelled separately and do not establish a live first payment. A saved
  variable amount may prefill the first-payment form; authoritative agreement validation
  still governs submission. Application/activation/payment details never enter analytics.
- **UX-005:** Tamil customer testing is prepared using English scenarios and an approved
  terminology/translation review process. Unreviewed translations are not published and
  recorded financial terms, consent versions and support contacts are not invented.

- **UX-006:** Payment-list totals and exports share validated customer, exact-payment,
  query, status, method, mode and creation-date filters. Invalid filters fail closed.
  Received Live/cash amounts remain separate from Test/practice. Export exclusions are
  explicit; pending/failed/closed attempts never become recorded money through UI copy.
- **UX-007:** Cash-entry GET may explain blockers but cannot create a record or call
  the provider. Final preview/commit services recheck all financial rules independently.
  No frontend state or fragment response can establish payment receipt or entitlement.
- **UX-008:** Read-only fragments preserve existing authentication and scope. Private
  HTML/history snapshots are never cached by HTMX; expired sessions navigate to login.
  Normal URLs/forms remain usable. No auto-retry of consequential POSTs, optimistic
  financial result, private-token enhancement, mixed-grade total or client financial calculation.
- **UX-009:** Owner review return destinations are bounded, allowlisted local inbox
  URLs, not arbitrary next URLs. Customer applications use explicit approved identity
  links; histories/documents use the authenticated customer's FK. Navigation does not
  confer permissions. Search terms, private URLs and HX-Current-URL are not analytics
  events and must be redacted from prepared access/application logging.

- **UX-010:** Application milestones derive from saved verification, current unapproved terms,
  coordinated agreement, usable login and successful real-method payment records. Approved
  snapshots are not invalidated by later offer edits. Test/practice/pending/failed/abandoned
  or reversed attempts cannot complete real first payment; print documents label Test/practice.
  Exact-customer privacy history remains bounded, feature-gated and owner-only. Counts and
  enhanced filters retain the same scoped selector as ordinary GET.

- **SCH-001:** Historical liabilities remain separated into `CASH` and exact Gold or
  Silver grade dimensions; new production enrolments are limited to explicitly
  offered metal grades.
- **SCH-002:** An account snapshots the plan's economic terms at enrolment; later plan edits do not rewrite the agreement.
- **SCH-002A:** New enrolments also preserve plan name/code and an observed immutable
  plan revision. Legacy accounts retain migration-time display identity with no
  invented accepted revision. Individual account snapshots, not the latest offer,
  remain authoritative for dates, contribution rules and exact-grade entitlement.
- **SCH-002B:** Owner plan edits require a reason, lock the plan, reject stale edits
  and atomically append revision/audit evidence. Generic admin cannot edit plans.
  Availability changes do not pause or close existing agreements.
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
- **SCH-010:** An authenticated customer may submit a non-binding interest request
  only for an active, publicly listed plan and active exact-grade offering. A request
  creates no scheme account, payment permission, rate lock, allocation, eligibility,
  or liability.
- **SCH-011:** Plan name/code and material public offer terms are snapshotted as request evidence. If
  those terms or the selected offering change before review, the request cannot be
  silently converted; the customer must review the current offer and submit again.
- **SCH-012:** Only an active owner may convert a pending request after recording that
  the current terms were reviewed with the customer. Conversion atomically calls the
  existing enrolment service, links exactly one `SchemeAccount`, and is idempotent.
- **SCH-013:** Only one pending request may exist per customer, plan, and exact metal
  grade. Customers may withdraw; owners may decline or expire with a reason; terminal
  request and decision evidence is retained.
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
- **PAY-029:** Expired pending Razorpay attempts remain financial exceptions until
  verified provider reconciliation or confirmed payment resolves them. Owner review
  and aggregate monitoring share the same expiry projection across all modes. A
  scheduled inspection may not change payment status; closing a verified untouched
  order requires an explicit audited apply. Owner apply needs a current owner/order/
  state-bound review and a fresh provider inspection. Expiry alone never establishes
  failure, refunds, release of entitlement or provider cancellation.
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
- **ELIG-005:** Metal redemption eligibility is not conditional on twelve successful
  monthly instalments. ONCE_PER_MONTH is a frequency limit, not compliance tracking
  or benefit qualification. Redemption still requires positive entitlement. Early
  discontinuation and unused cancellation are planned separately under ADR-0017;
  Phase A does not permit bypassing the current date gate.
- **REM-001:** Scheme reminders are transactional communication derived from existing
  records. Building or delivering a reminder must never change eligibility, account
  status, a contribution, an allocation, a redemption, or any liability.
- **REM-002:** Upcoming-eligibility reminders use only the contractual
  `eligible_from` date and configured positive calendar-day lead times. They do not
  create grace, expiry, business-day adjustment, or automatic redemption behavior.
- **REM-003:** Allocation-exception reminders are owner-only and derive from
  `PAID_UNALLOCATED` contributions. A reminder neither resolves the exception nor
  replaces the controlled idempotent allocation-retry workflow.
- **REM-004:** Completed-redemption reminders identify one immutable completed
  redemption. A redemption reversed before candidate selection is excluded; later
  reversal does not rewrite or delete already retained communication evidence.
- **REM-005:** Each event, audience, and normalized recipient has one deterministic
  reminder identity. An email already accepted by the backend is not sent again;
  failed attempts may be retried only to the configured bounded limit.
- **REM-006:** Reminder records and delivery attempts are append-oriented and
  immutable. Backend acceptance is evidence only that the configured email backend
  accepted the message; it is not evidence of inbox delivery, opening, or reading.
- **REM-007:** Customer reminders require an active login whose normalized email
  exactly matches the customer record. Owner reminders go only to active application
  owners or superusers with a nonblank email. Invalid or missing recipients are an
  operational alert and are never silently substituted.
- **REM-008:** Scheduled delivery is disabled by default and runs through an explicit
  externally scheduled management command. Dry-run is read-only, historical-date
  apply requires explicit confirmation, output is aggregate rather than recipient-
  identifying, and each audience may be independently disabled.
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
- **RED-008 (current implementation; retirement planned):** Partial redemption leaves
  an eligible account open. Redeeming the exact remaining entitlement changes its
  stored status to `REDEEMED`. The owner has now approved full-only settlement under
  ADR-0017 / `FW-PLAN-002`; this rule describes existing code, not a new configurable
  product option. Historical settlements must remain intact during transition.
- **RED-009:** Every redemption submission has a unique idempotency key. Replaying the same key and details returns the existing event; changing details with a used key is rejected.
- **RED-010:** Jewellery-purchase redemption requires an external invoice or sales reference. The MVP records the reference, entitlement settled, and notes but does not manage inventory or invoices.
- **RED-011:** A redemption correction appends one immutable `RedemptionReversal`; it never edits or deletes the original redemption. Reversed settlements are excluded from outstanding-balance and liability subtraction.
- **RED-012:** A legacy settlement reversal restores that denomination's entitlement;
  a fully redeemed legacy account reopens to `ACTIVE` with date-derived eligibility.
  Configured B3 reversals instead retain accepted closure and `CLOSURE_PENDING`;
  payment collection never reopens implicitly.
- **FIN-007:** INR and each exact metal-grade liability are never combined into a
  single balance.
- **FIN-008:** All financial calculations use `Decimal` with explicit rounding.
- **FIN-009:** Editing a plan does not rewrite existing account economic terms.
- **FIN-010:** Owner liability aggregates reconcile with underlying customer obligations.
- **FIN-011:** Payment success is verified server-side.
- **FIN-012:** Corrections preserve audit history rather than silently rewriting financial records.

## Approved plan-builder target (preparation foundation only implemented)

**24 October calendar-period extension (local, release-gated):** new immutable
monthly-completion configurations may use `CALENDAR_MONTH` or `ANNIVERSARY`.
For calendar months, the enrolment month is compulsory even when short; an
enrolment-day payment can qualify. Periods use Asia/Kolkata and exclude their end:
30 January to before 1 February, then 1 February to before 1 March. Normal
eligibility requires both the original agreed duration and required count, and
cannot precede the final qualifying period end. Preview, forecast, reminder and
settlement must agree on `max(original_date, final_qualified_period_end)`.
Count completion blocks extra payments while waiting for duration. Ordinary
extensions and separately acknowledged outage amendments follow the frozen basis.
The existing verified timing/deadline review rules still apply: delivery time is
not payment time, and crossing a boundary does not move a reservation or lose funds.
Owner controls distinguish obligation, period basis, payment limit, eligibility
and missed consequence; unsupported combinations remain rejected, not defaulted
into new financial promises. Migration 0035 leaves all existing agreements and
configuration evidence unchanged. Earlier anniversary-only notes below record the
initial implementation sequence; they do not restrict this explicitly approved extension.

These planned rules do not change today's SCH/ELIG/RED behaviour through documentation
alone. Track the rollout in MVP_PLAN.md; migration 0021 is governance metadata only.
Migration 0022 adds immutable preparation configurations and nullable pinned draft-plan
references, with no legacy conversion. New configured plans must remain inactive and
unlisted; the enrolment service rejects them. Migration 0023 adds nullable configuration
and increment snapshots plus service wiring for individually fixed amounts. Those rules
are exercised with synthetic agreements, not enabled through public/owner enrolment. Calendar-metal
and approved monthly-completion/no-benefit configurations can be prepared. Migration
0024 adds nullable schedule-policy fields and an empty immutable period table; it does
not backfill obligations or change historical evidence. Monthly completion means
customer-fixed amounts, anniversary windows in Asia/Kolkata, zero additional grace,
no advance/bulk catch-up, and three possible extension periods. Required count equals
agreed months, with calendar AND count eligibility at the final qualifying period end.
Uncompleted agreements go to discontinuation review, never forfeiture. Payment
attribution and real policy eligibility remain unreleased; scenarios grant no rights.
Migration 0025 adds an empty reservation/evidence ledger, without attributing historical
payments. Its internal primitives do not collect funds, allocate grams or grant eligibility;
payment entry-point integration is now wired locally (migration 0026), but configured
publication/enrolment remains blocked. Synthetic service tests do not authorize activation.
An occupied period cannot be reused merely because its checkout expires. Verified
cash reversal appends correction evidence rather than deleting the original credit.
Razorpay Test/mock activity cannot qualify. Provider creation/event timestamps are a
conservative timing envelope, not an invented exact capture timestamp; missing,
inconsistent, expired-deadline or boundary-crossing evidence goes to REVIEW, not a
missed-payment verdict. Owner investigation is locally implemented, still unreleased;
bounded contractual outage remedies and exact ambiguous-order identity recovery are
implemented locally; late/duplicate-capture containment is now wired into new-payment
guards and owner review. Overall exception acceptance remains unfinished.
PAID_UNALLOCATED can evidence payment qualification, but never settlement readiness.
P3's current read-only projection uses validated current evidence, not historical
ledger replay. It preserves `eligible_from` as the original date and derives a
completion date only after the required qualifying count; eligibility also waits
until the final qualifying period ends in Asia/Kolkata. Conditional forecasts assume
one qualifying payment in each needed remaining window and include only recorded,
acknowledged outage amendments. A held/uncertain payment does not become a miss.
Exhaustion produces discontinuation review without forfeiture or automatic closure.
The projection is not a transactional settlement authorization. Configured agreements
remain unenrollable and unsettled through public services. Their original dates are
excluded from legacy redemption buckets and legacy eligibility reminders. P3's
separate monthly-completion notice uses only a confirmed count and upcoming final
qualifying-period end, never a forecast. It explicitly promises no redemption,
closure or benefit, and reports that configured full-only settlement is unavailable.
Pending allocation, review/hold or uncertain capture evidence suppresses the notice.
Original dates and retained reminder history never change when completion changes.
Migration 0030 adds the reminder kind/shape without a financial or historical backfill.
Delivery refreshes and locks the agreement, rechecks current eligibility, enabled
audience, lead date and recipient, then appends normal SMTP attempt evidence. A stale
candidate is skipped without an invented delivery attempt; retries are rechecked.
Legacy explicit date replay remains supported, but current monthly evidence cannot
authorize historical monthly dispatch. A correction after an already-sent notice
cannot retract that email: the notice directs recipients to current agreement status.
Account locking serializes against financial services; SMTP acceptance and database
commit are not atomic, so a crash after acceptance can still require duplicate-mail
investigation. This is not exactly-once delivery and never grants financial authority.
The owner Today calendar-review count also excludes configured agreements. Direct
legacy redemption-form GET/POST requests for configured agreements return 404; the
independent financial-service gate remains in force. A configured calendar date or
monthly qualifying count is not a promise that settlement is available. Monthly
extension windows remain distinct from the original date and stop taking additional
payments once the required count is complete, subject to existing review controls.
Callback/API recovery without signed timing evidence records AWAITING, not QUALIFIED.
Before provider order I/O, a durable ORDERING decision commits independently; a lost
response or local write failure cannot trigger blind order recreation. Success records
the provider ID and returns the claim to RESERVED atomically. Uncertain intent requires
explicit review, not a free replacement. Callers must respect the service-owned durable
transaction boundary rather than enclosing this network workflow in another transaction.
Migration 0029 records a unique UUID on new ORDERING evidence before provider I/O;
the same value is sent in the provider receipt and notes. Do not backfill identities
for old requests. An owner may supply a candidate order ID, but only an authenticated
Live order read matching UUID, receipt, contribution, amount, INR and creation time
can bind it to the original contribution. The append-only recovery records the owner,
reason, evidence reference and provider facts under the agreement lock. A recovered
checkout cannot resume, even if its original deadline has not passed. This is not
provider-side cancellation and cannot close an already-open modal. Binding is not
payment confirmation: capture verification/timing and untouched-order abandonment
remain separate existing workflows. No extra order, rate/deadline change, money,
metal, qualification or claim release is created by recovery. A timeout, missing
match, old intent without correlation, or owner assertion leaves investigation open.
An already-reviewed unknown-order webhook is not silently retried when identity is
bound; use explicit provider payment reconciliation and original signed timing evidence.
The current anniversary period, exact agreed amount and one shared reservation are
enforced across channels. Approved extension periods remain payable after the original
calendar date; this is not a new eligibility determination. Reservation deadlines cap
checkout at the period boundary. RELEASED requires the existing owner/system provider
reconciliation audit proving an expired untouched order; a later capture becomes
RELEASED_REVIEW without occupying a replacement's period. It blocks further initiation
and remains in the provider exception workflow. Failed/ambiguous order creation never
automatically frees a claim. Owner review cannot manufacture verification or release.
Every unresolved Live captured webhook for a monthly agreement (including one linked
by recovered order ID before its contribution link is set) blocks new online/cash
initiation and owner timing acceptance. The original paid instalment is not erased
when a second payment arrives. Same-payment redelivery is idempotent; a different
captured payment for an already-confirmed order is retained as DUPLICATE_CAPTURE_REVIEW,
without a second credit. Existing in-flight verified captures still reconcile during
the hold/global pause. Captures after expiry but before abandonment retain the existing
verified money/metal evidence at the original locked rate, with timing in REVIEW;
they do not automatically qualify. Abandoned-order captures never overwrite or credit
the replacement. Owner notes do not certify a refund or clear exceptions. Automated
refunds/verified refund closure are outside this step; unresolved cases remain held.
Do not confuse zero ledger-integrity errors with zero unresolved provider events.
Migration 0027 adds append-only owner notes/outage holds and a typed link from a
qualification decision to its owner review and original signed timing source. Only
previously verified same-payment timing wholly inside the original window/deadline
may resolve missing evidence; contradictory timing cannot be overridden. An outage
hold blocks new initiation for that agreement, not in-flight capture processing,
allocation recovery or authorized cash reversal. It awards no payment credit and
changes no financial record, rate, date or eligibility. Migration 0028 adds explicit
`OUTAGE_COMPENSATION_V1` amendments, not edits to the original agreement. The separate
allowance is at most three compensating months per agreement, one per proven
outage-caused unpaid ended period. These append future original-anchor anniversary
windows after the three ordinary extension months. Required count, amount, grade,
original dates and evidence remain unchanged. A 12-month agreement has at most an
18-month outer payment window, not 18 required instalments or guaranteed eligibility.
Exceptional incident/restoration evidence, owner reason, and a reference/timestamp
for actual customer acknowledgement of the exact proposal are mandatory. Routine
published closing hours do not qualify. No automatic amendment, free credit, bulk
catch-up, historical rate choice or retroactive legacy obligations are allowed.
An ended or already-started proposed extra window, exhausted cap, or unresolved funds
keeps the agreement in review without forfeiture. A hold may otherwise close only
while its original unpaid window remains open after restoration, or after existing
qualification for that period. Every closure preserves its hold and requires
reconciled payment/allocation/webhook state; other holds remain effective. The V1
owner form records externally retained customer acknowledgement evidence, not online
customer acceptance or email delivery. P3 eligibility and B settlement remain gated.
For schema-2 agreements, gated owner review/outage integration uses the validated
frozen required count, not agreed duration. Compensation appends after the original
required windows plus only the policy's ordinary replacements: three for count-based
plans, zero for duration-only benefit schedules. The separate three-period outage
cap, original calendar/anniversary anchor, exact amount and denomination survive.
INR reconciliation requires matching principal receipts/corrections; a metal allocation
is neither required nor permitted in their place. Pending/ambiguous provider evidence
still prevents hold closure. Timing acceptance does not credit principal twice.
Benefit-only compensation does not move principal maturity or award/restore a benefit;
its incident and replacement evidence must feed the later benefit workflow. If the
frozen policy disallows post-duration contributions, an extra window starting at or
after that cutoff is refused and the hold remains for separate review. No unusable
month is promised and no payment right is silently extended. Pure schedule preview
is not mutation authority: operational readiness still blocks schema-2 review writes.
An optional amount
step means integer increments from the configured minimum, not rounding user input.
This boundary remains until B's full-only settlement and the full configured journey are accepted.
For configured agreements, the selected amount and operational terms are immutable;
variable amount increments are measured from the snapshotted minimum. Legacy variable
preferences do not become fixed, and no old agreement receives a configuration in migration.

- **PLAN-001:** Only an owner can author/reuse a configuration in the initial builder.
  A published plan pins a validated immutable configuration version. A new version
  cannot rewrite existing accepted agreements; pending changed offers require confirmation.
- **PLAN-002:** Plan-fixed, customer-fixed-at-enrolment and variable amounts are distinct.
  A customer-fixed choice must satisfy the plan's bounds/step and becomes an enforced
  agreement amount, independent of Razorpay versus in-store cash payment channel.
- **PLAN-003:** An agreement accumulates one authoritative denomination/grade. Production
  INR/cash payout variants remain disabled pending separate approval; no mixing of
  principal, metal, discounts and benefit liabilities.
- **PLAN-004:** Required instalments are scheduled obligations, not counts of checkout
  attempts. Due-window/grace/catch-up/extension semantics must be complete before
  publication. Duplicate callbacks and Test activity cannot fulfil extra real obligations.
- **PLAN-005:** Calendar, instalment count, both and anytime are distinct policies.
  Original dates remain evidence; completion forecasts and missed-period consequences
  are derived from the accepted policy. All payment, status, reminder and settlement
  paths must agree. Existing accounts gain no invented historical payment obligation.
- **PLAN-006:** Eligibility, benefit qualification and benefit fulfilment are separate.
  Missing payments may change completion or disqualify a specified unearned benefit,
  never erase paid entitlement. Showroom/provider failures require explicit treatment;
  delayed confirmation is not automatically customer lateness.
  Schema-2 benefit qualification is a current, unawarded projection of the pinned
  configuration/revision, reconciled principal and required schedule. Normal principal
  eligibility alone does not satisfy REQUIRED_SCHEDULE. PRESERVE_ON_COMPLETION allows
  agreed ordinary replacements; DISQUALIFY_UNEARNED checks original required windows,
  following only explicitly acknowledged outage-compensation links. An unresolved
  incident produces review before any missed-payment verdict. Extra windows are not
  free payments. If the count is complete but a specifically compensating benefit
  window is unpaid, retain review rather than demand an extra payment or invent credit.
  A missed benefit does not reduce principal or move a duration-only principal date.
  Purchase-bonus previews use only uncorrected, verified qualifying INR receipts;
  they never value metal, include invoice top-ups, compound or call legacy CASH bonus
  logic. VA qualification supplies no monetary amount without eligible invoice-charge
  evidence. Pure arithmetic caps the explicit percentage calculation in INR and rounds
  once to paise with ROUND_HALF_UP; calculation version and rounding identifier are
  returned for future retained award/fulfilment evidence. Inputs reject floats, invalid
  precision, negatives and non-finite values; eligible charges cannot exceed the invoice.
  These reads/calculations create no earned award, discount consumption or financial
  liability. Closed/accepted-disposition histories require retained lifecycle review;
  a later changed projection must never erase an already recorded benefit. Award,
  one-time invoice fulfilment and append-only correction remain separate gated work.
  The gated retained award foundation (0046) stores one immutable purchase-bonus
  amount or VA-discount right per agreement with its pinned revision, exact terms,
  source/qualification/outage proof and calculation/rounding identifiers. A VA right
  has no monetary amount before invoice-charge evidence. Owner authority is reloaded;
  signed short-lived previews bind owner/account and apply recomputes under the account
  lock. Idempotent retries do not stack awards. Records and database uniqueness are
  retained; reverse migration refuses to discard existing awards. Later source changes,
  corrections or accepted/closed disposition history flag review while preserving the
  recorded award, not silently recomputing it, reducing principal or authorizing spend.
  The standalone award foundation is not automatic awarding or invoice consumption;
  actual use requires the linked settlement lifecycle below and operational readiness.
  The gated invoice foundation (0047) links one immutable award consumption to the
  agreement's actual normal full-principal jewellery handover, never just an unlinked
  invoice number. Purchase bonus uses its retained amount; VA uses evidenced eligible
  charges, percentage/cap and the retained rounding rule. Invoice-before-benefit equals
  benefit plus invoice-after-benefit; INR net invoice must match the principal proposal.
  Benefits do not create principal, additional grams, top-ups or refundable credit.
  A purchase-bonus invoice too small for the full benefit and positive principal
  handover requires review, not forfeiture of an earned remainder or benefit cashout.
  A complete linked principal return plus corrected invoice/customer/time evidence
  permits one append-only full benefit reversal. It never erases the award or invoice,
  restores principal itself, allows partial reversal or automatically makes the award
  spendable again. Returned rights require review. Owner-attested invoice/charge and
  physical return evidence is not an inventory system or provider-confirmed refund.
  The review foundation (0048) retains append-only APPROVE/HOLD decisions for an
  independent full return, bound to the unchanged award, original qualification,
  full disposition/return evidence and closure prefix. Approval requires fresh customer
  authorization; a hold must not claim customer approval. Later decisions supersede
  rather than erase earlier ones. Fresh owner-bound short-lived previews and locked
  revalidation reject concurrent/stale decisions. Review neither changes monetary
  rights/caps nor reopens contributions, grants principal or consumes an invoice.
  A new closure note makes the latest review stale; source drift requires reconciliation.
  Atomic replacement integration (0049) replaces the single-invoice-per-award storage
  restriction with one original invoice and a linear chain: each successor requires
  the predecessor's complete return and one current approved decision, consumed once.
  Original invoice evidence stays version 1; version 2 additionally binds predecessor,
  reversal and approval. A signed replacement preview retains that exact approval.
  INR proposal creation consumes no approval or principal; actual jewellery handover
  and invoice benefit consumption are atomic. A superseding hold prevents new
  fulfilment but permits evidenced void/full-return recovery. A consumed review cannot
  be reused or superseded; the new invoice needs its own full return and fresh review.
  Purchase bonus reuses its original amount. VA is calculated from the new invoice's
  eligible charges under the unchanged right/percentage/cap, not an extra accrued bonus.
  No benefit is refunded as principal or converted into grams. Historical reviews and
  returns are validated against retained prefixes; current spending rechecks present
  sources, closure state and latest approval. All workflow gates remain in force.
  Rollback must not discard recorded decisions. No standalone public spend path exists.
  The gated first independent exact-metal settlement now uses closure-scoped eligibility
  and qualification under the agreement lock. Accepted closure history/customer authority
  must match; ordinary progress still reports closure pending. It creates or reuses the
  unchanged qualified VA right and commits full principal, invoice consumption and closure
  atomically. Early closure grants no unearned completion benefit; benefit-only misses
  cannot remove principal. Complete return requires linked customer/invoice/time evidence
  and reverses consumed benefit with principal atomically, leaving the account contained.
  Prior returned dispositions are not automatically spendable or replacement-ready.
  The gated independent INR entry separately retains the qualified award/right with
  the first disposition proposal. Its invoice/refund split uses the invoice after the
  exact benefit; the proposal reduces no liability and claims no actual handover.
  Jewellery handover and invoice benefit consumption commit atomically. Refund legs
  require their own completed-source/customer evidence, and every principal leg must
  be fulfilled before closure. Complete physical returns link principal and consumed
  benefit reversals atomically; void retains an unconsumed right. Returned/voided
  independent dispositions may enter the gated replacement path only with complete
  return/void evidence, retaining original sources, qualification and normal/early
  basis. Previously consumed benefits additionally require the explicit approved
  reapplication chain above; an unconsumed award is retained, not duplicated.
  Existing optional/calendar/no-benefit foundation proofs remain readable and separate.
  Both INR and closure diagnostics validate the linked benefit lifecycle. Replacement
  handling and lifecycle acceptance remain required before release; operational gates
  stay closed. No separate public spending path or automated provider refund is added.
- **PLAN-007:** Redemption is full-only for every new supported configuration, including
  anytime. The server settles the complete available entitlement at internal precision
  and closes that agreement; customer login/other agreements remain. No reusable wallet.
  Pending/late/unallocated payments must be resolved or controlled before final closure.
  For new INR purchase-credit contracts, the approved target is one final settlement
  applying all principal to jewellery, a permitted principal refund, or both. Showroom
  fulfilment is manual but recorded and evidenced; no replacement-credit wallet and
  no automated refund API. Pending refunds remain liabilities and prevent final closure.
  Source-routing requirements still apply. Benefits are separate, never implicit cash
  refunds; this policy does not convert exact-grade metal entitlement to cash.
  INR purchase-credit principal uses a distinct `INR_CREDIT` denomination, never the
  legacy `CASH` bonus balance. One verified live-capture or actual cash-receipt source
  may credit principal once. Store its exact amount, reference, contract and verification
  time; no amount is supplied by an owner adjustment form. Test/mock payments, pending
  payments, jewellery top-ups and benefit promises do not credit this ledger.
  A full erroneous cash-entry correction needs its matching completed source reversal;
  it is not a refund. Neither source status changes nor unresolved source drift silently
  erase the retained principal/correction history. Reconcile discrepancies explicitly.
  Verified-capture integration records principal and instalment evidence in the source
  transaction. A principal receipt may use system:razorpay-capture with no human actor
  only for a captured-webhook source; cash and manual recording retain a human actor.
  Recheck the original processed Live body hash, payment/order IDs, exact INR amount
  and captured state. This consumer does not authenticate signatures; authenticated
  webhook processing remains upstream. A new event for the same payment adds no second
  principal receipt. Late/missing timing may require instalment review without losing
  verified principal. Full cash-entry correction atomically retains source reversal,
  principal correction and instalment reversal. A browser callback alone is never
  sufficient principal evidence. A valid callback HMAC plus authenticated exact Live
  API capture can create a separate immutable minimal observation and principal
  atomically (0044). Owner API recovery requires preview, fresh exact inspection,
  actor/reason and retained event identity. Neither path fabricates a signed webhook
  or uses API payment creation time to qualify an instalment: monthly timing remains
  awaiting evidence until an original signed capture supplies it. Later callbacks,
  recovery or webhooks retain the first valid receipt source without double credit.
  Closed/disposed agreements and failed/abandoned sources require review, not an
  automatic credit. API source evidence participates in INR settlement proofs without
  rewriting older proofs. This is gross captured principal, not refund availability
  or settlement reconciliation. Normal collection/readiness gates remain closed.
  One immutable INR disposition assigns all recorded principal to an evidenced invoice
  and/or original-source refund legs. Invoice application consumes earliest verified
  uncorrected receipts first (verification time, then receipt ID); remaining amounts
  retain their source identities. One invoice cannot serve two such dispositions.
  Proposals reserve disposition but reduce no liability. Append-only jewellery handover
  and refund fulfilments reduce only their exact leg amounts, not arbitrary partial
  withdrawals. External invoice top-ups are receipt evidence, never scheme principal.
  Online-source refunds require manual provider-dashboard completion references and
  customer receipt evidence; original cash receipts may use evidenced cash return.
  No unapproved fallback refund route is inferred. These records attest showroom
  fulfilment; the app does not independently verify a bank credit or call refund APIs.
  Full closure requires every leg fulfilled and unchanged reconciled source/closure
  evidence. Late payments or changed evidence hold completion for review. Proposal,
  fulfilment and completion terms cannot be edited/deleted. A proposal may be retired
  only by linked immutable resolution evidence: VOID before any fulfilment, or FULL_RETURN
  covering every fulfilled portion, in one transaction. A partial/pending disposition
  needs returns of every portion actually fulfilled, not invented returns for unpaid legs.
  Completed dispositions require a linked REVERSE event; pending dispositions use a NOTE.
  Jewellery return needs customer confirmation and invoice correction evidence; any
  separately paid top-up must have its external refund evidenced, never credited as
  scheme principal. Returned refunds require actual cash received/bank credit evidence.
  Mere promises, cancellation notes or edited receipt amounts restore no liability.
  Original gross fulfilment/completion history survives; full returns restore precisely
  the discharged principal. The agreement remains CLOSURE_PENDING and closure ACCEPTED,
  blocking contributions. A replacement full disposition requires a fresh signed preview,
  customer authorization and new invoice/transaction references, linked to its retired
  predecessor. Only one current disposition is permitted; the retirement flag is a
  checked projection, not financial source evidence. No partial redemption, staged-return
  operation, replacement-credit wallet or provider refund API is introduced.
  Independent replacement evidence retains the exact resolved predecessor chain.
  Original sources/reviews must be unchanged; correction does not reopen contributions
  or re-earn a previously unearned benefit as dates pass. Fresh customer authorization
  must not recycle a prior settlement/return authorization; invoice references must
  be new. Principal-only returns and unconsumed INR rights are supported internally.
  Any consumed benefit invoice, even with a full reversal, requires explicit current
  reapplication approval and atomic consumption in its one linked successor invoice.
  Customer returns do not reset original online-payment refund capacity. Retain all
  gross provider refunds across generations; a proposed further refund must fit the
  original captured amount after those refunds. Otherwise hold the disposition for
  separately approved route reconciliation, never silently substitute cash. This
  recorded-history cap is not verification of provider-side availability.
- **PLAN-008:** Historical partial events remain immutable. Before full-only cutover,
  inventory remaining balances and any existing contractual partial-redemption promises;
  resolve conflicts explicitly without invented consent or deleting financial history.
- **PLAN-009:** Only complete, implemented, compatible configurations can publish. A
  draft/preset is not automatically an approved public offer. Future customer proposals
  remain nonfinancial and owner-reviewed; customer rule authoring is deferred.
  Builder-v1 design compatibility is validated separately from operational readiness
  (`plan_policies.py`). A design-valid typed contract does not create financial rights
  or override missing workflow/INR approval blockers, even with the release flag on.
  Existing persisted configuration evidence is projected read-only, never rewritten.
  Policy schema 2 persists independent duration/count/benefit terms but is preparation-
  only even when the release flag is on. Schema 1 keeps its exact historical evidence;
  new immutable versions do not reinterpret agreements or downgrade their schema.
  Independent agreement-term resolution reloads the pinned policy and exact grade;
  a variable amount preference does not become a fixed instalment. Duration and
  required count stay independent. A duration floor is not completed eligibility;
  count-only/anytime never receive an invented twelve-month date. Read-only integrity
  validation is separate from runtime permission. INR principal recording must reject
  frozen amount/frequency/date/denomination drift as well as mismatched revision evidence.
  Agreement storage version 1 preserves the legacy twelve-month minimum and non-null
  eligibility date. Version 2 pins an explicit eligibility policy and independent
  required count. Its agreed_months means duration only; eligible_from is its duration
  floor, not proof of completed count or benefit qualification. COUNT and ANYTIME have
  null duration/date; ANYTIME has no required count. Required-for-benefit DURATION may
  retain a schedule count without making that count a principal-redemption condition.
  ONCE_PER_PERIOD records the independent policy ceiling; it is never silently stored
  as FLEXIBLE. Model/service activation guards stay closed until integrated workflows
  exist. Migration does not infer consent or convert pre-existing schema-2 agreements.
  Prospective schema-2 required windows use required_count, never duration_months.
  Calendar windows start on enrolment day then month boundaries; anniversary windows
  always clamp from the original start anchor. Ordinary replacement windows apply
  only to EXTEND_THEN_REVIEW. Benefit-only duration schedules have no replacements;
  optional monthly ceilings have no required windows. Constructing these windows is
  not persisted obligation, verified attribution, eligibility or benefit qualification.
  Outage compensation remains separate acknowledged evidence, never automatic padding.
  Internal schema-2 schedule persistence validates the entire frozen contract, locks
  the account, inserts all periods atomically and returns an exact existing schedule
  unchanged. It refuses optional obligations, partial/corrupt repairs and first-time
  creation after any contribution or on a non-active account. Reservation capacity
  uses the frozen required count, not duration. Receipt/capture attribution retains
  source, timing, idempotency and reversal evidence; it creates neither INR principal
  nor metal allocation and does not grant redemption or benefit qualification.
  Independent eligibility progress is a current-time read of the frozen contract,
  real-source principal and append-only qualification evidence. COUNT completes
  immediately when its final payment is verified and conclusively attributed;
  DURATION_AND_COUNT waits for both its duration floor and the final qualifying
  period end. ANYTIME requires positive verified principal, not an invented date.
  DURATION with a benefit schedule does not require that count for principal
  eligibility or postpone its date after a missed benefit instalment. Rule progress,
  positive principal, financial/outage holds and pending benefit review are separate.
  Source corrections remove qualification/credit without deleting evidence; exhausted
  windows lead to review, never principal forfeiture. Future/historical as-of dates
  cannot manufacture verification rights. Closed/accepted-disposition histories are
  not fresh spendable entitlements. This read changes no dates, statuses or benefits
  and does not replace locked settlement proof or operational readiness. Schema-2
  accounts are excluded from legacy maturity reminders until their family-specific
  content and lifecycle integration are ready.
  Public/model enrolment, payment entry, owner instalment review and outage resolution
  remain blocked for schema 2 pending complete release acceptance. Gated integrations
  and synthetic regression tests do not activate these workflows. Tests use synthetic
  stored contracts; they are not permission to bypass model/service activation guards.
  The 0037 INR principal services are internal foundations, not activated payment or
  settlement workflows. Existing contribution confirmation, redemption and closure
  entry points reject the future denomination; no legacy cash workflow is reused.
- **PLAN-010:** Configured publication requires an immutable reviewed revision matching
  the current offer and an enabled release gate. Withdraw before editing a published
  offer; policy changes use a new version/draft. Neither withdrawal nor disabling
  `CONFIGURED_PLANS_ENABLED` changes existing agreements, payments or closure rights.
  New configured enrolment requires current offer confirmation and freezes that revision;
  monthly instalment periods are created in the same transaction. No contribution,
  rate lock, allocation or eligibility credit is created by publication/enrolment.
  Schema-2 owner-enrolment orchestration uses the locked offer's exact published
  revision and typed configuration, not the legacy plan duration/frequency columns.
  INR purchase credit rejects a metal grade or legacy CASH denomination. Required
  count and duration remain distinct; an explicit duration must match the policy,
  and count-only/anytime have no invented date. Owner authority, exact current offer
  digest/configuration and explicit boolean confirmation remain required. Account,
  full required schedule and enrolment audit commit or roll back together. This
  internal integration does not remove operational publication/model gates.
  Version-2 existing-customer interest requests pin configuration, publication revision and reviewed
  offer digest, separately retaining duration, required count and denomination.
  They create no account, contribution, rate lock, principal receipt or allocation.
  Signed forms bind the displayed offer/disclosure version; conversion rechecks the
  persisted current offer under lock and rejects substitution. INR requests have no
  metal grade; count-only/anytime requests have no invented duration. Duplicate
  pending INR requests are excluded even with a null grade. Conversion, schedule,
  linked decision and audit are atomic/idempotent. Messages use frozen terms, not
  current-plan defaults. Schema-1 requests retain their old rules. Migration 0045
  refuses unversioned independent requests and refuses reversal while version-2
  evidence exists. These gated form/service paths still require full release acceptance.
  Separate registration-first PlanApplication confirmations also carry an explicit
  schema version. Each version-2 confirmation pins its publication revision and
  independent configuration/denomination/amount/duration/count/benefit evidence.
  Old confirmations are never rewritten when an applicant reviews a changed offer;
  explicit reconfirmation appends a new record, including a change of denomination.
  Contact, email verification and completion create no identity or financial account.
  Owner approval rechecks the persisted current offer and latest confirmed terms,
  then commits identity, exact agreement, schedule, audit and invitation together.
  Strict owner attestations, verified private progress access and the existing
  identity/financial release gates still apply. Messages and review history use
  recorded terms, not current-plan defaults. Accounts migration 0009 preserves
  schema-1 JSON and refuses unversioned independent consent or reversal while
  version-2 evidence exists. Diagnostics validate nullable INR/no-duration links and
  the confirmed agreement provenance; none of this grants payment or benefit rights.
  Schema-2 new-payment admission uses the frozen independent contract and server time,
  never a caller-selected historical month. Accounting month is not an anniversary
  window. Required counts remain independent of duration; optional ceilings create no
  obligations. Cash uses its server receipt instant within half-open India-local
  calendar/original-anniversary windows. Active payment claims and uncorrected paid
  sources consume the ceiling; a full evidenced correction retains history and frees
  only that payment opportunity. Cash mutations serialize on the agreement.
  INR payment initiation respects the environment kill switch, global pause and
  business-hour schedule without requiring a metal rate or obeying a gold-only pause.
  Actual INR cash source, receipt, principal, schedule evidence and audit commit
  atomically; no grams or legacy cash bonus are created. Required-monthly online
  initiation retains durable order intent and cannot blindly retry a lost response.
  Optional schema-2 online initiation uses separate immutable request/binding records,
  never artificial instalment obligations. Commit the UUID/amount/rate/deadline intent
  before provider I/O. A lost, invalid or locally unrecorded response blocks retries
  and cash; elapsed time or FAILED alone cannot release it. At most one outstanding
  optional checkout is admitted per agreement, including flexible plans. A normally
  bound checkout can resume only with the same amount and unchanged deadline/rate,
  while current payment/closure/privacy controls permit it. Optional period ceilings
  and a disallow-post-duration boundary cap the original checkout deadline.
  Exact recovery requires an active owner and authenticated Live order identity
  matching request UUID/receipt, contribution, exact INR amount and creation time.
  Recovery records immutable actor/reason/evidence, retains the old deadline/rate,
  creates no principal or metal and is reconciliation-only, never resumed checkout.
  Only existing provider-backed untouched-order abandonment can permit replacement;
  later captured funds remain in the exception workflow. Pauses/expiry during order I/O
  retain the returned identity but refuse checkout. No automatic retry, cancellation,
  refund or absence inference is introduced. All paths still require operational
  readiness; service integration does not activate configured plans. Callback/API
  principal reconciliation and complete matrix acceptance remain separate gates.

P4 supersedes the earlier unconditional preparation-only gate with the above default-off
controlled gate. Earlier B/P checkpoints describe their implementation boundaries, not
permission to bypass the new publication workflow or to activate production.

## Audit and exception rules

### Configured closure lifecycle — B1/B2/B3 local preparation

Operational distinction: the owner closes a customer's **agreement**, not the reusable
plan or customer login. A genuinely never-used agreement is cancelled without redemption.
An agreement with some, but not all, required instalments paid can undergo customer-
authorized **early full jewellery settlement** of its entire actual accumulated metal.
For example, three paid instalments of twelve do not grant the unpaid nine instalments
or a maturity benefit. They also do not require a partial redemption: all three payments'
available metal is settled and the agreement closes. These are local configured-contract
capabilities, not a retroactive change to existing production/legacy agreements.

- **B3 full settlement:** configured exact-grade, no-benefit contracts only. Both normal
  and early closure require accepted closure, resolved verified/allocated real payments,
  a positive server-derived full balance, invoice, reason and actual customer
  confirmation/fulfilment evidence. Preserve all six internal decimals. A signed preview
  is owner/request-bound, expires after ten minutes for new mutations and is invalidated
  by changed financial/review facts. Replay cannot change the original details.
- Normal calendar settlement uses the recorded date; normal monthly settlement requires
  the required qualifying payment count and final qualifying period end as well. Early
  closure preserves paid entitlement without inventing qualification, discounts or fees.
  Pending/unallocated, Test/mock, failed/abandoned attempts and unresolved provider,
  monthly-timing or outage evidence block settlement. Expiry is not provider cancellation.
- Immutable configured proof links closure events to existing Redemption/Reversal financial
  sources. Settlement marks SETTLED/REDEEMED; controlled reversal restores the full exact
  grade to ACCEPTED/CLOSURE_PENDING. It never reopens payments or changes customer login.
  Re-settlement requires fresh proof. No legacy cutover or publication/enrolment bypass.

- B1 supports configured agreements only. Legacy agreements require the separate
  contractual/history cutover before gaining closure rights. Configured publication
  and enrolment remain blocked; these services do not activate a plan.
- A direct request belongs to the authenticated active customer. Owner-assisted
  requests require a reason and retained reference to actual customer authorization.
  Source, actor label, reason, reference and request time are retained unchanged.
- The lifecycle is PENDING -> ACCEPTED, WITHDRAWN or REJECTED. Owner review notes
  append evidence without changing state. Customer withdrawal and owner rejection
  are allowed only while pending; owner-assisted withdrawal requires authorization.
  ACCEPTED permits further owner notes, not silent withdrawal/rejection/reopening.
- Pending intent alone leaves existing contribution rules in force. Acceptance
  blocks new online/cash initiation, provider-order creation and checkout resumption
  under the shared agreement lock. It changes no agreement date, amount, grade,
  payment, allocation, redemption or liability. Replaying an existing cash receipt
  is recovery/idempotency, not a new cash contribution.
- Existing captures, provider reconciliation, allocation recovery and authorized
  cash corrections continue after acceptance. Already-open provider modals cannot
  be recalled by a local request. Expired/abandoned orders can still capture; their
  history must not be deleted or treated as proof that no future funds can arrive.
- Request state is a checked projection of append-only sequenced closure events.
  One open request per agreement, idempotency keys and valid state/action shapes
  have database constraints. Services lock the agreement before request rows and
  reject stale decisions. Accepted evidence continues blocking initiation if the
  projection is corrupted; integrity errors require investigation, not manual edits.
- Accepted closure suppresses completion reminders at selection and locked delivery,
  but leaves allocation-exception communication available. Historical mail survives.
- Payment-review counts are investigation aids, never an unused/settleable verdict.
  Even zero balance/history does not automatically invoke cancellation. B3 full-only
  settlement/reversal and legacy cutover remain separate from request acceptance.
  Customer login and other agreements remain active; no request claims jewellery
  delivery, refund, benefit, forfeiture or completed closure.

- **B2 unused cancellation:** an active owner separately confirms an ACCEPTED configured
  closure with a mandatory reason and stale-sequence/idempotency checks. The account lock
  serializes this operation with payment initiation and review. Any contribution record
  (all channels/modes/statuses), redemption, instalment reservation, period investigation
  or outage resolution prevents unused cancellation. Even reversed/failed/abandoned
  histories require separate disposition; zero current balance is insufficient. Empty
  scheduled periods and ordinary closure notes are not financial use.
- Append the typed CANCEL event with actor, timestamp, reason and original request link,
  then atomically project both request and agreement to CANCELLED. This is not REDEEMED
  and creates no financial rows, refund, entitlement, fee or benefit. No rows are deleted,
  original terms are retained, and customer login/other agreements are unchanged.
  No undo/reopen is supplied; another saving cycle needs a new agreement. Cancelled
  agreements are excluded from active/payment/reminder/eligibility projections and cannot
  acquire new instalment investigations. Integrity checks detect missing cancellation
  evidence, status disagreement and financial/review history after cancellation.
- B2 does not authorize personal-data erasure or change the separate privacy-retention
  workflow. That workflow remains conservative about agreement history; any future
  relaxation needs its own disposition review. No new legacy cancellation right or
  configured-plan activation is introduced by these local services.

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
- **DOC-008:** INR purchase-credit statements show original receipts/corrections,
  proposals, actual principal handover/refund, full returns and historical completion
  separately. A proposal discharges nothing; top-ups and purchase benefits are excluded
  from principal. Showroom refund evidence is not presented as API-verified delivery.
  Retained benefit history never adds to INR principal or exact-grade grams; full return
  and approval alone do not reapply it. Customer documents omit private review reasons
  and authority references. Invalid principal/disposition proofs produce a non-cacheable
  review response, not an invented balance. Reads cannot activate or settle a plan.

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
  rendered on the About or How It Works pages remain application-owned template
  content. Editorial rich text is limited to business background and must not become
  a source of financial or compliance terms.
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

## Jewellery journal boundaries

- **BLOG-001:** The Jewellery journal is business-authored educational and editorial
  content. It must not accept public submissions, comments, customer-specific advice,
  or user-generated content.
- **BLOG-002:** One `BlogIndexPage` at `/blog/` contains only `BlogPostPage` children.
  Public listings include only live, unrestricted descendants of that root and are
  bounded to nine articles per page.
- **BLOG-003:** Public blog access requires both live/public Wagtail state and
  `PUBLIC_BLOG_ENABLED=True`. When disabled, direct index and article routes return
  `404` and global navigation contains no journal link; CMS preview and revision
  history remain available to authorized staff.
- **BLOG-004:** A journal article is never authoritative for a Scheme Rate, plan term,
  product price or availability, policy, payment, allocation, balance, eligibility,
  redemption, or customer agreement. It links to the owning application surface
  instead of duplicating or controlling that data.
- **BLOG-005:** CMS access requires explicit active staff membership in a dedicated
  Blog group. Editors may draft and submit; Blog Publishers and Administrators may
  approve and publish. Blog authorization, pages, workflow, and media remain isolated
  from Catalogue and Editorial groups and from `CustomUser.role`.
- **BLOG-006:** Optional featured images require meaningful alt text and use the
  dedicated Blog media collection. R2 originals and renditions remain subject to the
  `FW-MEDIA-002` source-original retention and recovery limitation.
- **BLOG-007:** Public posts expose a factual date, byline, summary, canonical URL,
  and social metadata. Featured ordering is editorial presentation only and cannot
  alter financial or product records.
- **BLOG-008:** The application seeds no public or placeholder articles. The business
  must create and approve genuine content before enabling public discovery; categories,
  tags, feeds, comments, and cross-site search require measured need and separate scope.

## Mobile distribution boundaries

- **MOB-001:** The first mobile distribution is an installable PWA and customer-only
  Android Trusted Web Activity over the canonical HTTPS origin. It reuses Django
  sessions and CSRF and introduces no mobile API or authentication token.
- **MOB-002:** Django services and PostgreSQL remain the sole source of truth. A mobile
  surface may display server responses but never calculates, stores, or submits an
  authoritative rate lock, metal allocation, balance, eligibility result, payment
  result, redemption, or liability independently.
- **MOB-003:** The Android surface exposes no owner, staff, rate-publication,
  registration/enrolment approval, showroom-cash, redemption-recording, audit, or
  payment-operations control. Those remain web-only authorized workflows.
- **MOB-004:** Service-worker caching is allowlisted. Authentication, registration and
  invitation tokens, customer/scheme data, rates, contributions, payments, receipts,
  statements, eligibility, OAuth callbacks, health responses, and owner/admin content
  are network-only and are never served as cached truth.
- **MOB-005:** Razorpay secrets and confirmation authority remain server-side. Mobile
  browser or native callbacks never create entitlement; existing signature, captured-
  payment, signed-webhook, idempotency, expiry, pause, and exact-grade allocation rules
  apply unchanged.
- **MOB-006:** Google authorization may not run in a developer-controlled embedded
  WebView. TWA/browser login preserves the explicit approved-customer connection and
  stable-subject rules in `AUTH-012` through `AUTH-016`.
- **MOB-007:** Android code, signing, scanning, and release artifacts live in a separate
  repository and CI boundary and are never built on the production serving host. This
  repository owns the canonical web content and exact Digital Asset Links statement.
- **MOB-008:** Offline behavior may state that connectivity is required and display
  reviewed static public assets only. It never queues a financial mutation or labels
  a cached amount, rate, entitlement, payment, or eligibility decision as current.
- **MOB-009:** Public store release requires reviewed organization ownership, privacy
  and support identity, financial/Data Safety declarations, and discoverable in-app
  and external account-deletion requests. Deletion handling must disclose and justify
  any retained immutable financial records rather than silently erasing history.
- **MOB-010:** A native Android/iOS client or versioned customer API requires a new ADR
  covering authentication and revocation, authorization, idempotency, rate limiting,
  secure storage, provider SDKs, threat modeling, compatibility, and release operations.
- **MOB-011:** The PWA worker may precache only the generic connection-required page
  and reviewed application icons. Every navigation is network-first with HTTP-cache
  reuse disabled; no network response is written to Cache Storage, and non-GET or
  non-navigation requests are not intercepted. Disabling the PWA retires its worker
  and named static cache on the next successful online page load.
- **MOB-012:** The Digital Asset Links statement contains every Play App Signing
  certificate observed for supported Play-delivered builds and no upload or debug
  certificate. Signing-key rotation or Play delivery segmentation is handled by an
  additive certificate keyset; removing an established Play certificate requires
  separate installed-device evidence.

## Precision

Money uses 2 decimal places. Contribution and cash-redemption input with more than 2
decimal places is rejected rather than silently rounded. Cash bonus calculations use
`ROUND_HALF_UP` to 2 decimal places. Metal quantities, allocation calculations, and
owner metal-redemption entry use 6 decimal places; excess input precision is rejected.
Customer-facing gram values render to 3 decimal places without changing the stored
quantity. Full-settlement confirmation and its retained settlement evidence explicitly
show all 6 decimals so the customer-authorized full quantity does not hide a remainder.
Scheme Rates use 4 decimal places and grade fineness metadata uses 6.
