# MVP Plan

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
