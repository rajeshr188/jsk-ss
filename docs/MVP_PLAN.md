# MVP Plan

## Workflow refinement and HTMX (owner approved 22 October 2026)

Follow the browser audit in `FUTURE_WORK.md` (`FW-UX-004`/`005`) in this order.
The earlier four conversion phases remain complete; this is their approved refinement.

- [x] **1. Scope, blockers and navigation.** Shared validated payment-list/export
  filters, clearly scoped totals and export exclusions; specific read-only cash-entry
  blockers before input; bounded applicant search and retained local return context;
  role-specific navigation and owner readiness links. Dependencies: current selectors,
  services and permission boundaries. Acceptance: list/export scope agrees, invalid
  filters fail closed, no GET creates financial records or calls a payment provider,
  and review navigation preserves filters without external redirects.
- [x] **2. Dashboard, forms and documents.** Compact actionable customer progress,
  clear plan/application/document destinations, owner customer sections and denser
  queues; input units/autofill, understandable stage/copy/formatting, document return
  paths and bounded history. Depends on the role navigation/scope above. Acceptance:
  no duplicated primary payment action for one plan, no mixed-grade balances, retained
  consent/snapshots and useful mobile/desktop/keyboard/error/empty-state behavior.
- [x] **3. Bounded HTMX pilot.** Enhance owner customer search/pagination using existing
  selector-backed HTML, then relevant read-only filters/status refresh where justified.
  Depends on stable full-page flows above. Acceptance: pinned local asset, normal GET
  fallback, unchanged authorization/CSRF, no private history snapshots, stale-response
  protection, visible loading/errors and session-expiry recovery. Never enhance
  consequential financial/approval/authentication actions into automatic retries.
- [x] Run appropriate focused and full serial regressions, Django/migration checks and
  inspect both roles at desktop/mobile sizes. Update architecture/domain/status/testing
  and deployment guidance. No production deployment, environment change or data change.

## Expired Checkout operations (FW-PAY-008, local candidate)

- [x] Add durable checkout submission/order identity and cross-tab coordination for
  existing monthly/flexible production agreements, with signed stale-form protection.
- [x] Retain uncertain create responses and audited exact owner identity recovery;
  preserve original financial terms and never renew recovered checkout.
- [ ] Complete new prevention/migration regression and combined release acceptance.
- [x] Shared expired-attempt queue/count projection and privacy-safe alert counts.
- [x] Owner exact-payment inspect/confirm with bounded signed review and fresh provider check.
- [x] Expiry-aware command with exact selection, bounded inspection and backlog/error alerts.
- [x] Five-minute systemd inspection and combined heartbeat wrapper, without financial writes.
- [ ] Complete isolated release regression/CI/image verification, existing Better Stack heartbeat verification/configuration,
  delivered failure/missed-run/recovery acceptance and approved production activation.

## Remaining audit work (22 October 2026)

The checked refinement batch above is not closure of the whole audit. Complete these
remaining implementation items, then record release/user acceptance separately.

- [x] Stage tabs/counts use the same scoped application selector and preserve query,
  customer and type across navigation. Count each linked plan/identity once.
- [x] Progress shows contact, verification/details, review, login and first-payment
  milestones from records. Test/practice/pending/failed/reversed records cannot complete
  a real first payment; legacy agreements must not gain invented intake history.
- [x] Owner Access/privacy shows bounded requests linked to the exact customer, with
  existing review links and unchanged privacy/permission/feature-switch boundaries.
- [x] Normalize customer document/request amounts, dates and return/cancel actions;
  retain full printable financial history and existing quantities/snapshot precision.
- [x] Extend read-only HTMX to repetitive owner application/exception/payment filters,
  keeping results, counts, customer context and CSV scope synchronized. Compare full/
  fragment payload, test authorization/privacy/fallback/invalid filters and error/focus.
  Dependencies: the existing pinned pilot and selector safeguards. No automatic POST.
- [x] Relevant regressions, full suite, checks and mobile/desktop browser inspection;
  update canonical status/backlog/architecture/testing/release notes.
- [ ] External acceptance: restored staging, actual customer/owner usability, reviewed
  Tamil/business copy where supplied and separately approved production rollout.
  Lazy-loaded history and bounded polling remain conditional follow-ups, not implicit
  requirements to close the first HTMX pilot.

## Release rehearsal and stakeholder acceptance (22 October 2026)

This follows the completed local UI work; it does not enable production deployment.

- [x] Add and execute an opt-in local synthetic dump/restore/upgrade drill. Dependencies:
  loopback PostgreSQL with CREATE DATABASE permission and pg_dump/pg_restore. Acceptance:
  fresh random targets only, existing application database untouched, no external providers,
  historical rows/snapshots/INR and exact-metal liabilities preserved, pending migrations
  applied, legacy access and new coordinated application/activation still work, cleanup verified.
- [x] Prepare the customer/owner task protocol and evidence fields in TESTING.md, with
  release/restore prerequisites in PRODUCTION_DEPLOYMENT.md. No invented business terms,
  support promises, participant results or translations.
- [ ] Confirm the non-production staging target, candidate image/revision and approved
  sanitized backup provenance; rehearse the exact immutable image and proxy on that target.
  Acceptance: scoped feature/configuration review, normal and enhanced browser journeys,
  disabled-JavaScript fallback, log-sink redaction, operational checks and recoverable rollback.
- [x] Prepare an isolated fictional local usability preview and verify both role logins and
  starting pages. Leave participant observations unaccepted until supplied; keep lifecycle/stop
  details in TESTING.md and the ignored session manifest.
- [x] Local stakeholder acceptance: on 22 October 2026 the owner reported testing both
  owner and customer roles and being satisfied. No task timings or independent participants
  are inferred from that report.
- [ ] Broader prospective/existing customer observations and reviewed Tamil testing remain
  follow-up research. Record completion, help/confusion and wrong turns when actually observed;
  Tamil work requires reviewed terminology and a Tamil-speaking reviewer.
- [ ] Obtain separate production deployment/data-change approval for the concrete candidate.
  After release, measure funnel outcomes using existing aggregate measurement; local tests
  cannot establish conversion uplift.

## Customer conversion redesign (approved 5 October 2026)

Implement and review each phase locally before proceeding to the next. Production
deployment and production data changes require the owner's separate approval.

- [x] **Phase 1 — Offer clarity, measurement and payment correctness.** Dependencies:
  current public-plan selectors, staged registration, payment operations and verified
  contribution records. Acceptance: compact mobile/desktop offers derive amounts,
  frequency, grades and durations from plans; selected-plan application is the primary
  public action; unreviewed investment/retirement descriptions are not public; anonymous
  aggregate measurement contains no identity, token URLs or provider references;
  first-payment counts come from server records; paused payments have no Pay/Resume
  action; abandoned attempts and uncertain checkout outcomes are truthful. Relevant
  regressions, Django checks, migration checks and desktop/mobile inspection pass.
- [x] **Phase 2 — Owner workflow.** Depends on Phase 1 measurement/status definitions.
  Acceptance: Today prioritizes verified applications and financial exceptions; customer
  search is bounded and paginated; application review and related customer screens
  retain consistent context and existing owner/CMS permissions. Test unauthorized access,
  queue ordering, search/pagination and customer isolation; inspect desktop/mobile.
  Implementation checklist:
  - [x] Today becomes the owner landing, with 8-record previews, queue counts/jump
    links, oldest financial exceptions and explicit application next actions.
  - [x] One Applications inbox combines record types with 25-record SQL pagination,
    stage/type filters and customer history through explicit approved identity links.
  - [x] Customer search is capped at 100 characters with fixed 25-record pages and
    aggregate agreement counts; historical review/payment/exception lists are bounded.
  - [x] Shared review/context displays snapshots, preferences, decisions and inline
    agreement creation; legacy URLs and service/permission/CSRF guards remain intact.
  - [x] Complete focused/full regressions, mobile/desktop inspection and release notes.
- [x] **Phase 3 — Continuous plan application.** Depends on Phase 2 workspace and revised
  ADR-0011/0012 contracts. Acceptance: plan/grade/preferences and offer evidence survive
  verification; contact details precede remaining required profile fields; protected
  verification and explicit showroom contact/terms review precede coordinated approval;
  one transactional service creates/links separate identity and agreement records with
  conflict/current-offer rechecks, renewed confirmation on material changes, concurrent
  retry safety and separate audit evidence. Notices run after commit with recoverable
  failures. Protected progress and existing-customer applications preserve historical
  records/access. Test concurrency, changed offers, retries, privacy and failure recovery;
  inspect customer and owner desktop/mobile journeys. Prepare additive migration guidance.
  Implementation checklist (in order):
  - [x] Add an additive application link and append-only offer confirmations; retain
    all historical registrations, requests and agreements without backfilling intent.
  - [x] Persist plan, exact grade and preferences at contact submission; after email
    verification collect address and explicit confirmation of current terms/start date.
  - [x] Provide expiring, session-protected progress with a separate digest-only email
    access credential, accurate stage/next action, existing showroom support and retry.
  - [x] Coordinate locked identity approval and agreement creation atomically; require
    explicit contact verification, current customer confirmation and separate evidence.
    Duplicate/concurrent approval returns one agreement; failures leave no partial login.
  - [x] Integrate owner review/queues and existing-customer requests; test legacy access,
    changed offers, permissions, privacy, rollback, concurrency and after-commit delivery.
  - [x] Run focused/full regressions, inspect mobile/desktop, update canonical decisions
    and prepare migration/deployment guidance without touching production.
- [x] **Phase 4 — Activation and continuation.** Depends on Phase 3 approved application
  and progress read model. Acceptance: activation continues into the approved plan and
  correct first-payment state; dashboard foregrounds progress; expired-link recovery
  preserves account privacy; linked-Google eligibility is explicit. Test token/session
  boundaries, expired/replaced invitations and continuation; inspect desktop/mobile.
  Prepare Tamil customer-testing materials; translations require business review.
  Implementation checklist (in order):
  - [x] Continue linked-plan password setup through password sign-in to the scoped
    approved agreement; legacy invitations retain their existing login route.
  - [x] Derive first-payment/continuation guidance from agreement dates, recorded
    contributions and existing payment availability; distinguish Test/practice.
  - [x] Foreground bounded, customer-scoped application stages and next actions on
    the dashboard, including applications for another plan.
  - [x] Add CSRF-protected, repeat-safe expired-link help without disclosing account
    state; retain owner-only replacement and expose bounded owner recovery queues.
  - [x] Explain activated/linked Google eligibility with matching verified email,
    preserve all authentication guards and prepare English Tamil-testing scenarios.
  - [x] Verify relevant/full regressions and desktop/mobile journeys; update decisions,
    domain/architecture/status and additive migration/deployment guidance. No rollout.

All four implementation phases passed local acceptance. Production rollout still
requires separate approval; reviewed translations and Tamil participant testing are
follow-up release/language work, not another automatically authorized implementation phase.

Backlog reconciliation on 22 October 2026: committed implementation is `7d07cf2`.
Remaining rollout/measurement is `FW-UX-001`, approved copy/review expectations are
`FW-UX-002`, and reviewed Tamil testing is `FW-UX-003` in
[Future work](FUTURE_WORK.md#customer-conversion-release-and-validation).

Business inputs still required: approved descriptions/any benefits beyond recorded
financial terms and an achievable showroom response window. Do not invent these.
Phase 1 retained the existing staged approval process; Phase 3 now implements durable
cross-email plan intent and one coordinated approval for newly linked applications.

- [x] Milestone 0 — Lithium adaptation
- [x] Milestone 1 — Customer and scheme enrolment
- [x] Milestone 2 — Cash contributions with mock payment
- [x] Milestone 3 — Gold/silver allocation foundation
- [x] Milestone 4 — Owner liability dashboard
- [x] MVP Alpha checkpoint
- [x] Milestone 5 — Metal-rate provider (superseded by ADR-0003)
- [x] Milestone 6 — Razorpay test mode and idempotent webhooks
- [x] Milestone 7 — Redemption eligibility views
- [x] Milestone 8 — Redemption
- [x] MVP Beta checkpoint
- [x] Milestone 9 — Cash bonus
- [x] Milestone 10 — Audit and exceptions
- [x] Milestone 11 — Receipts and statements
- [x] Post-MVP simplification — Manually published Scheme Rates locked before payment
- [x] Post-MVP modularity — Exact-grade metal contracts, rates, allocations, and redemptions

- [x] `FW-AUTH-002` — Staged public customer registration with owner approval
- [x] `FW-ENROL-001` — Non-binding customer enrolment requests with owner conversion
- [x] `FW-AUTH-004` — Google as an explicitly linked approved-customer credential

- [x] `FW-PRIV-001A` — Disabled verified-request, containment, owner-hold, and integrity foundation
- [ ] `FW-PRIV-001B` — Owner-operated data disposition, minimization and completion (authenticated zero-history production completion accepted 15 September 2026; signed-out email-verification completion, provider evidence, and recovery reconciliation acceptance pending)
- [ ] `FW-PROD-007` — Budget-conscious security-log preservation (inventory/plan documented; measured sizing, archive implementation and recovery acceptance pending)

- [ ] `FW-MOBILE-001` — Mobile product, policy, account, and release readiness
- [x] `FW-MOBILE-002` — Network-safe installable PWA foundation
- [ ] `FW-MOBILE-003` — Customer-only Android Trusted Web Activity
- [ ] `FW-MOBILE-004` — Play internal-test and controlled customer pilot
- [ ] `FW-MOBILE-005` — Evidence-based native Android/iOS and API decision

Milestones are vertical increments. Each must leave migrations, tests, system checks, user flows, and canonical documentation coherent before the next begins.

Known limitations and their acceptance targets are tracked in [Future work](FUTURE_WORK.md).
