# Future Work Register

This is the actionable backlog for known limitations that remain unresolved, with
completed foundations distinguished from outstanding acceptance. It does not relax
the financial invariants in [Domain rules](DOMAIN_RULES.md).

Detailed completed-work evidence belongs in [Project status](STATUS.md), the
[production runbook](PRODUCTION_DEPLOYMENT.md), and the applicable
[architecture decisions](decisions/README.md). A compact completed-item index and the
historical milestone ledger remain here so stable `FW-*` identifiers and previously
recorded limitations are not lost.

## Current priority override — 29 October 2026

Builder v1 is deployed on `8f3ba5a`; reviewed-head/main CI, exact-image upgrade,
restore/forward recovery, operator/device/email acceptance and disabled-first
production verification are complete. The owner accepted the first offer unchanged;
`CONFIGURED_PLANS_ENABLED=True` is live and plan 3 `MC22K-5000-12M` is published
with immutable revision 2 / audit 118. Health and integrity checks pass, all 46
compared scheme-model snapshots and liabilities match, legacy offers are unchanged.
This supersedes older "local/in development/release pending" wording for the
delivered builder below. Dated notes remain history, not instructions to repeat
completed work. Evidence is in STATUS.md, TESTING.md and PRODUCTION_DEPLOYMENT.md.

**Current acceptance:** first enrolment is verified: JSK-958ABDE4, revision 2,
configuration 1/v1, correct 22K/INR 5,000/12-count/12-month/calendar rules, consent,
one audit and 15 periods. No contribution, order, allocation or receipt was created;
other compared financial history and liabilities remain unchanged. Total agreements
are 14, with one configured. Inbox delivery was not independently rechecked.

**Next:** bounded observation before another delivery item. Recommend seven calendar
days (29 October-5 November), then review actual friction and choose one improvement;
no automation or additional payment is scheduled/required. This does not reduce the delivered INR/benefit
scope. Triage three overdue deletion reviews separately as owner operations;
retain balances/holds and review individually, never bulk-complete.

The owner subsequently authorized **FW-UX-006 as the next engineering item during
observation**. Its local presentation candidate does not launch another offer or
alter production. Engineering visual/copy review and 99 local tests now pass;
owner commercial-copy/CMS acceptance, hosted CI and deployment remain open.

First offer is now published: plan 3 `MC22K-5000-12M`, configuration 1/v1, 22K only,
INR 5,000 fixed, 12 months AND 12 qualifying calendar-month payments, no benefit,
full-only settlement. Active/listed with one verified agreement; financial checks pass.
Owner terms/activation/publication approval is recorded. See the current
MVP_PLAN.md checklist; do not create another pilot draft or repeat completed gates.

The [market review](MVP_PLAN.md#jewellery-savings-market-review-29-october-2026)
records sources, compatibility, design observations and gaps. The
[execution sequence](MVP_PLAN.md#current-execution-priority--29-october-2026)
separates offer-specific prerequisites from later improvements. Competitor parity
is not required for the first supported offer. Correct shared denomination copy
before public INR listing; implement a new financial promise before advertising it.
Calculators, tiers, mandates and unrelated CMS/mobile work are not bundled into
activation. Existing incident response/checks continue; prior deferrals remain.

## Review checkpoint — 22 October 2026

Reviewed against the current repository, commit `7d07cf2`, the recorded Phase 1–4
regression/browser acceptance, and the production/mobile evidence in the canonical
documents. This is a repository reconciliation, not a fresh inspection of production,
Play Console, provider delivery, monitoring accounts or external backups. Missing
external evidence remains pending; an old unchecked box alone does not mean its
implementation is absent.

| Workstream | Completed evidence | Still pending |
| --- | --- | --- |
| Customer conversion redesign | Implemented, tested and deployed as `4d92b575` on 22 October 2026; integrity/smoke checks passed | Owner production visual acceptance and observed customer results (`FW-UX-001`); separate staging deferred to `FW-PROD-009` |
| Offer and language follow-up | Record-derived offers, factual copy and English Tamil-testing protocol | Approved additional marketing descriptions/benefits and review window (`FW-UX-002`); reviewed Tamil translations and participant testing (`FW-UX-003`) |
| Account deletion | Completion/minimization and notices deployed; authenticated zero-history production completion accepted 15 September | Separate signed-out verification journey, provider follow-up and independent recovery reconciliation (`FW-PRIV-001B`) |
| Android distribution | PWA accepted; signed TWA accepted in Internal Testing; origin association and installed app verified | Remaining device/negative cases, reviewer access, declarations, store assets and submission (`FW-MOBILE-001`, `003`, `004`) |
| Production operations | Health endpoints, masked logs, financial heartbeat and operational runbooks | External alert exercises/retention, rotation and archive implementation (`FW-PROD-002`, `003`, `007`) |
| Financial recovery and reminders | Verified payments, manual recovery, payment controls and reminder implementation | Recovery/replay exercises, first genuine reminder delivery and separately defined audit improvements (`FW-PAY-003`, `FW-ELIG-002`, `FW-AUDIT-002`–`005`) |
| CMS and media | Catalogue and disabled-first journal foundation accepted | Genuine approved journal content/discovery and independent media recovery (`FW-CMS-004`, `FW-MEDIA-002`) |

Active entries below remain open unless explicitly marked as a completed subtask.
The B3 local configured-settlement implementation does not complete `FW-PLAN-002`:
failed/abandoned provider exposure disposition, Test/mock history separation, legacy
partial-rights inventory/cutover, owner/mobile acceptance and exact-image release review
remain pending. Do not delete history or use owner attestations to clear those holds.
Optional business-policy and architecture work is conditional; inclusion does not
authorize implementation, production changes, a financial transaction or a store release.

## Plan builder and agreement lifecycle

**24 October 2026 approved release boundary:** complete one coherent owner-builder
v1 before production activation; do not release the current subset first. Track the
matrix, unresolved business decisions and single completion checklist at the top of
MVP_PLAN.md. INR purchase credit, count-only/anytime eligibility and defined benefits
are completion targets, still subject to explicit compatible terms and the existing
INR approval boundary. Small reviewed increments remain behind the disabled gate.
Historical local-phase notes below do not authorise activation. FW-PLAN-008 remains
deferred; partial redemption remains excluded.

The owner subsequently approved ADR-0017's detailed matrix, INR settlement approach
and benefit types. Typed compatibility validation and operational blockers are now
local (`plan_policies.py`), and migration 0036 persists independent schema-2 fields
without rewriting schema-1 evidence. Financial workflows remain open. The owner
approved one final manually fulfilled settlement with unused-principal refund;
no partial redemption, replacement credit or automated refund API. Usable refund
routes, external approvals and verified fulfilment remain publication dependencies.
The 0037 INR principal foundation is local: separate denomination and source-linked
receipt/correction records, reconciliation reads, and pure full-settlement arithmetic.
0038 adds the local manual proposal/fulfilment and full-closure foundation, with pending
refund liability and original-source evidence. This does not complete the INR item:
0039 adds contained full-return/unused-void evidence and replacement full dispositions,
without reopening contributions or enabling partial/staged returns. Read-only schema-2
term resolution and frozen INR snapshot checks are now shared. Migration 0040 adds
versioned independent agreement storage, including null duration/date for count-only
and anytime while preserving legacy terms. Independent read-only schedule construction
now separates original required count from duration and ordinary replacements; optional
ceilings create no obligations. Internal persisted schedules and verified-payment
attribution now support independent required counts under synthetic-contract tests;
this does not activate enrolment/payment entry or owner review/outage amendments.
Gated owner-enrolment orchestration now freezes the accepted independent revision
and account/schedule/audit atomically, with runtime readiness still closed.
Verified-capture and cash/correction principal hooks now exist (0041 system provenance),
and gated independent admission/actual cash/required-monthly online entry now exists
(0042 frequency choice). Optional online durable order/exact identity recovery now
has a separate gated, obligation-free evidence path (0043); owner recovery-interface
integration and collection acceptance are still required. Callback/API principal now
has separate authenticated capture evidence (0044), retaining signed-timing separation.
Collection and benefit-schedule acceptance, request/form/email integration, eligibility/benefit
variants, statements/privacy handling and acceptance remain open in MVP_PLAN.md.
Optional recovery cannot infer provider absence from a failed lookup. Expired attempts
without a usable request/order identity remain held; no manual checkbox or blind
replacement clears them. A future verified never-sent/negative-evidence disposition
must be explicitly implemented and accepted, alongside the existing held-provider
closure boundary, before claiming complete attempt-lifecycle acceptance.
Replacement refunds exceeding a source's cumulative provider-refund capacity remain
held: customer returns do not replenish the provider limit. A separate approved-route
reconciliation workflow is needed for those cases; no silent cash substitution.
Also verify refund-route availability for agreement-age, method, provider-balance and
dispute restrictions before INR activation; a recorded amount cap is not route approval.

- **FW-PLAN-001 — Govern plans and preserve agreement terms (A):** In development on
  `agent/plan-agreement-governance`. Audited/locked owner edits, immutable revisions,
  stable agreement identity, legacy provenance and clear calendar eligibility. Local
  tests/migration checks passed; owner visual review, exact-image rehearsal and PR/CI
  remain before an approved release.
  See ADR-0017 and the A/B checklist in MVP_PLAN.md. Production remains unchanged.
- **FW-PLAN-002 — Controlled discontinuation and unused-agreement cancellation (B):**
  Follows the configuration/instalment/eligibility foundations below. Separate
  request/authorization from settlement; block new payments at
  accepted closure, resolve pending/late/unallocated funds, settle full exact-grade
  jewellery entitlement with invoice evidence, append corrections and cancel truly
  unused agreements without a fake redemption. Preserve history and customer login.
  Owner confirmed **no partial redemption**, including normal/anytime settlement;
  full settlement closes that agreement. Retire the existing smaller-amount path with
  historical/contractual review, server-derived exact balances and race/reversal tests.
  B1 lifecycle is implemented locally for configured agreements (0031): direct and
  authorized owner-assisted requests, append-only reviews, pre-acceptance withdrawal/
  rejection, acceptance payment guards, in-flight capture preservation and private UI.
  B2 unused cancellation is implemented locally (0032): accepted configured closure,
  strict no-attempt/no-financial-or-review-history proof, append-only CANCEL evidence,
  terminal agreement status and explicit owner confirmation; no fake redemption.
  B3 full exact-grade jewellery settlement and contained reversal are locally verified
  (0033; 28 focused and 803 full-suite tests). Provider-history disposition, legacy cutover,
  owner/mobile and release acceptance remain open. Existing legacy date-eligible
  partial redemption is unchanged; configured publication/enrolment remains gated.
  B4 has nine passing local HTTP/statement/late-capture/concurrency acceptance tests
  and 201 passing affected regression tests:
  unused cancellation and full early settlement after three of twelve instalments
  preserve sources, login and other agreements. On 23 October 2026 the owner accepted
  the isolated unused-cancellation, three-of-twelve early full redemption/closure and
  correction walkthroughs. Additional viewport/keyboard/print and exception acceptance,
  provider/legacy disposition and release evidence remain open; the parent item is
  not complete and configured publication/enrolment is not activated by this approval.
- **FW-PLAN-003 — Versioned configuration catalogue and customer-fixed amount:**
  **In progress: P1a/P1b local, activation acceptance pending.** Owner creates/reuses validated
  immutable configurations; plan publication pins a version, enrolment freezes permitted
  customer selections and all operational terms. Reject unsupported/incompatible rule
  combinations. A chosen monthly amount becomes enforced across payment channels, not
  merely a preference. Preserve old agreements and current production cash restrictions.
  P1a provides immutable typed versions, owner catalogue/new-version/reuse UI, selected
  amount previews, audited pinned preparation plans and migration 0022; no financial
  rights result. DB/service gates prevent configured plan activation/enrolment.
  P1b adds migration 0023, confirmation/approval selection propagation, immutable
  configuration/amount snapshots and shared cross-channel validation. Its tests use
  synthetic configured agreements; real enrolment stays blocked. Full-only settlement B
  and end-to-end activation acceptance are mandatory before marking this complete.
  Do not migrate legacy plans/agreements into configurations automatically.
- **FW-PLAN-004 — Scheduled instalments and missed-payment evidence:**
  **24 October local expansion:** new calendar-month configurations alongside
  anniversary schedules; compulsory short enrolment month, independent duration
  floor, consistent reminders/forecasts and period-aligned outage compensation
  (0035). Separate owner controls now expose obligation, basis, limit, eligibility
  and consequence. Existing agreements are not converted; release/owner acceptance
  and unsupported benefit/INR/count-only/anytime families remain separate work.
  Scope: explicit obligations, period/due/grace/catch-up rules, count, extension bounds and payment links.
  Handle duplicate/delayed callbacks, reversals, pauses and unallocated captures;
  exclude Test/practice payments from real qualification. No retroactive obligations.
  **In progress: P2a through P2b.3a and the P2b.3b outage remedy local; exception acceptance pending.** Approved anniversary schedule, zero extra
  grace/no catch-up, three extension months, immutable period snapshots and owner
  scenario previews are implemented behind the existing gates (migration 0024).
  Migration 0025 adds an internal exclusive-reservation/append-only attribution ledger
  and cash reversal evidence. P2b.2 wires both existing payment channels atomically,
  callback/recovery awaiting-timing evidence and provider-reconciled releases with
  non-occupying late-capture review (migration 0026). P2b.3a adds owner investigation,
  outage holds and narrowly verified timing resolution (migration 0027). P2b.3b now
  implements acknowledged outage amendments: three separate compensation months,
  one per affected period, with reconciled-state hold closure (migration 0028).
  Migration 0029 adds exact provider-backed ambiguous-order identity recovery using a
  durable pre-request UUID, owner evidence and a reconciliation-only binding. Empty
  lookup results and historical requests without a UUID remain unresolved, not released.
  Late/duplicate-capture containment now blocks new online/cash initiation and owner
  timing acceptance for unresolved Live capture events, preserving original credits
  and in-flight confirmation. Owner review links to existing provider reconciliation.
  No automatic refund or verified refund closure is implied; unresolved cases stay held.
  P2b.3b still requires final owner/mobile/checkpoint/CI and release acceptance.
  Enrolment stays disabled; payment
  qualification does not grant eligibility or full-settlement readiness.
- **FW-PLAN-005 — Policy-based eligibility and benefits:** Calendar/count/both policies,
  unchanged original dates plus derived completion forecasts, separate qualification
  and fulfilment, auditable awards/corrections. Exact numeric benefit rules remain
  business inputs (`FW-PRICE-002`); unknown values block publication. Missed payments
  may affect unearned benefits or completion, never erase paid entitlement.
  Monthly read-only eligibility/forecast and customer availability are implemented
  locally (23 October); legacy behaviour is preserved. Distinct monthly-completion
  reminders and delivery-time revalidation are implemented locally with migration 0030;
  forecasts do not trigger mail. Local P3 checkpoint review corrected the owner
  date-only count, configured legacy-redemption form access and misleading extension/
  settlement copy. B3 configured-only full settlement is now local; owner/mobile/email,
  provider-history disposition and CI/release acceptance remain open. Configured activation is still blocked. SMTP/database
  crash-window duplication remains a delivery limitation, not a financial credit.
- **FW-PLAN-006 — Owner guided builder and reusable valid configurations:** Create or
  choose approved versions, preview generated agreement and normal/missed/exit scenarios,
  publish only combinations supported through settlement. Customer choices remain within
  owner-authored offers. Bootstrap 5, existing Django services/selectors; no rules language.
  P4 publication/enrolment is now implemented locally behind the default-off
  `CONFIGURED_PLANS_ENABLED` gate with revision evidence, audited withdrawal and atomic
  monthly schedules (0034). Remaining: complete owner/mobile/keyboard journey review,
  exception acceptance, CI and exact-image release rehearsal. No activation is implied.
- **FW-PLAN-007 — Flexible anytime metal family:** Builder-v1 completion target,
  variable amounts, one fixed grade and full-only redemption/closure. No reusable wallet,
  partial withdrawals, cash conversion or blanket removal of legacy duration rules.
- **FW-PLAN-008 — Customer-authored configuration proposals (explicitly deferred):**
  Future proposals through the same validated catalogue, subject to owner review and
  customer confirmation before normal enrolment. Proposal submission creates no financial
  records or payment access. Not included in immediate owner-builder implementation.

- **FW-PLAN-009 — Selected market-derived policy extensions (conditional):**
  Research recorded in the 29 October MVP_PLAN.md market review. Not a blocker for
  existing supported offers. Select one actual commercial need rather than cloning
  every competitor or reopening builder-v1 completion. Prioritize explicit VA bases
  if JSK wants a waiver based on eligible gold value: percentage-of-charges differs.
  Other conditional dimensions: exact-day/due-day/grace/collection boundaries,
  tiered benefits, product exclusions and excess-purchase/offer-stacking scope.
  Early-exit tiers remain `FW-PRICE-002`, presentation `FW-UX-006` and customer-authored
  proposals `FW-PLAN-008`; avoid duplicate implementation.
  - [ ] Select one offer and agree complete anchors, benefit base/caps/qualification,
    payment and exit treatment. Competitor headlines do not authorize JSK terms or
    prove legal/accounting/provider suitability.
  - [ ] Approve bounded design preserving immutable old contracts, separate INR/grades,
    principal/benefits and actual source/fulfilment/refund evidence.
  - [ ] Implement the selected calculation/schedule/eligibility/settlement/correction
    paths with Decimal arithmetic, retained rounding, database and concurrency tests.
    Plain-text charge definitions cannot substitute for a new calculation formula.
  - [ ] Accept public examples, owner/customer journeys, notices and the exact-image
    release before offering the variant; no partial redemption or silent forfeiture.
  Single-advance presets require fit analysis first. Nominees, mandates, fees, gifts
  and online jewellery fulfilment remain later separate scope, not implied approval.

Execution/acceptance checklist: MVP_PLAN.md; policy compatibility, legacy handling and
scope: ADR-0017. These approved design items are not implemented by migration 0021.

## Customer conversion release and validation

- **FW-UX-001 — Release and validate the completed conversion redesign:** Implementation
  is complete in `7d07cf2`; do not schedule another implementation phase for the same
  scope. Release acceptance and evidence of improved conversion remain open.

  - [x] Complete Phases 1–4, relevant regressions and mobile/desktop inspection.
  - [x] Prepare architecture decisions, migration, deployment and rollback guidance.
  - [ ] Rehearse the combined release on restored staging, including `pages.0002`,
    `accounts.0007` and `accounts.0008` where not already applied; confirm reviewed
    policy versions, private-route log exclusions and independent feature switches.
    Deferred to `FW-PROD-009` by explicit owner decision on 22 October 2026; exact-image
    PostgreSQL 18.6 local rehearsal and guarded production checks passed instead.
  - [x] Obtain owner approval for the concrete production release/migration plan,
    deploy, and retain operational verification and rollback evidence under
    [the production guide](PRODUCTION_DEPLOYMENT.md#customer-conversion-phase-3-prepared-release-not-production-authorization).
    Release `4d92b575` deployed on 22 October 2026; see STATUS.md for evidence.
  - [ ] Obtain post-deployment owner/customer visual acceptance of the released UI;
    local acceptance and production integrity checks do not establish conversion uplift.
  - [ ] Separately approve/enable optional aggregate measurement and record a comparable
    reporting period with `report_customer_funnel`. Compare navigation and authoritative
    application/verified Live first-payment throughput; report showroom cash separately.
    Origin request counts include repeats/bots and omit edge-cached requests. They are
    neither Cloudflare unique visitors nor a joined conversion cohort. Synthetic records
    are not reliably excluded automatically; disclose their effect. Do not claim a
    conversion improvement from implementation or local tests alone.

- **FW-UX-002 — Supply approved offer messaging and review expectations:** Obtain
  business-approved descriptions/benefits beyond the existing record-derived terms
  and an achievable showroom response window. Until supplied, keep factual existing
  copy and support details; do not invent returns, benefits or response promises.
  Plan records and agreement snapshots remain authoritative. Numeric early-discontinuation
  benefits still depend on `FW-PRICE-002`; policy review remains `FW-PROD-005`.

- **FW-UX-003 — Run reviewed Tamil customer testing:** The English protocol is prepared
  in [Testing](TESTING.md#prepared-tamil-customer-testing-english-protocol-not-published-translations).
  Obtain reviewed terminology/translations and a Tamil-speaking reviewer, then run the
  defined mobile tasks with prospective and existing customers in staging. Record
  completion, wrong turns and misunderstood payment/application stages without personal
  details, private links or payment references. Resolve findings and obtain language
  approval before publication. No Tamil translations or participant results are complete.

- **FW-UX-006 — Denomination-aware offers and truthful illustrations:** Added from
  the 29 October market review. **Prerequisite for public INR listing:** shared
  homepage/plans/how-it-works/FAQ/refund content must distinguish purchase credit
  from exact-grade metal, and match accepted full-only terms/source refund routes.
  Current shared homepage lead/plans introduction assume all payments create grams.
  A correctly described metal offer does not require this broader INR-copy change.
  Existing configuration-specific facts are not proof all shared prose is correct.
  Local implementation prepared on `agent/denomination-aware-offers` (29 October).
  Published plan data and existing contract/payment services remain unchanged.
  - [x] Audit shared template copy against each denomination; eliminate metal-only assertions
    from INR paths and contradictory withdrawal/benefit promises before INR listing.
  - [x] After first-offer acceptance, standardize comparable facts: accumulation,
    amount, obligation/period, eligibility, conditional benefit, exclusions and early exit.
    Preserve plan-first application, protected progress and secure returning-customer pay.
  - [x] Add read-only worked illustrations using authoritative policy/Decimal reads;
    label hypothetical rate assumptions and separate principal, grams, benefit/cap,
    making charges and taxes. Do not value metal into spendable INR or create a lock.
  - [x] Verify family/role/flag/error/no-write paths and perform engineering
    desktop/mobile, keyboard and light/dark review. The fresh native Chrome review
    passed after correcting grade wording, action alignment, detail-summary facts,
    dark button colours and a 320px header overlap. No production changes.
  - [ ] Obtain owner commercial-copy/CMS acceptance through `FW-UX-002`. Measure
    actual outcomes through `FW-UX-001`, without treating visual polish, browser
    emulation or synthetic tests as physical-device proof or conversion uplift.
  - [ ] Obtain hosted CI and reviewed deployment acceptance; no production changes
    or INR-offer launch are part of the local implementation evidence.
  Keep existing Bootstrap/Django/services/selectors. Do not add product reservations,
  new benefit formulas (`FW-PLAN-009`), unrestricted signup or customer policy authoring.

## Browser workflow audit — 22 October 2026

The owner requested a fresh customer/owner browser review and an HTMX assessment.
This audits the committed local candidate, not the deployed production experience.
Chrome inspection used 1440x1000 desktop and 390x844 mobile viewports, synthetic
PostgreSQL fixtures, in-memory email and dummy Razorpay Test configuration. The
fixtures included approved/awaiting-review applications, three agreements for one
customer, pending payment, paid showroom-cash receipt, allocation/webhook exceptions,
expired setup and 30 customer profiles to inspect pagination. These are deliberately
constructed states, not evidence of actual customer behavior or conversion impact.

Inspected public home/comparison/contact-first intake, private progress entry/review
stage, login, dashboard, agreement detail, first-payment form, recorded pending status,
statement/receipt, another-plan request, activation instructions and account-deletion
entry; owner Today/Operations, overview, rates/payment controls, application filters/
coordinated review/history, search/page two, customer context, contributions/cash entry,
eligibility, login recovery and empty reminder/privacy queues. Consequential approval,
payment, rate, cash, resend, deletion and credential actions were not submitted in the
browser. Filled fields were limited to existing synthetic login and read-only search.
Private-progress access used its existing protected POST. Browser timing/automation
retries are not attributed to application performance. This is a qualitative audit,
not participant testing, a complete accessibility certification or a provider/device
acceptance test.

What already works: public plans derive authoritative terms; selected-plan intent is
retained; existing customers do not repeat contact/address fields; coordinated review
keeps separate identity/agreement evidence; customer payment states distinguish Test
and unresolved outcomes; owner search is bounded and retains its query on page two;
customer links, role boundaries and responsive labelled payment rows are in place.
Keep these gains. At the audit checkpoint, the recommended next work was presentation
and navigation refinement, rather than another
replacement of the completed application architecture.

Priority: **P1** affects task discovery, scope or customer understanding; **P2** improves
scanability and presentation. Observations below are from the synthetic candidate;
missing-rate/pending-payment examples do not assert production incidents.

| Priority / area | Observed gap | Recommended improvement |
| --- | --- | --- |
| P1 — Customer dashboard | The approved application and its agreement repeat the same payment action in separate sections. Another pending application and three similar-grade agreements create substantial vertical repetition. | A compact Needs your attention area for actionable application/payment states, then identifiable plan summaries. Keep progress prominent; collapse completed steps rather than repeating the full approved application. Never add quantities across grades or imply pending payment is paid. |
| P1 — Customer navigation | Signed-in navigation still leads with public Home/Plans/How/About/Contact; My schemes, enrolment requests, applications and plan terms use different labels. Documents require navigating through a plan/history. | Give signed-in customers Home, My plans, Applications, Documents and Help; keep account/security/privacy accessible. Apply consistent customer vocabulary while retaining exact legal/financial record distinctions internally. |
| P1 — Intake/progress | Mobile intake measured 2382px document height including footer. Duration lacks an explicit months unit in the field label; phone is a text input without inputmode/autocomplete hints. Progress shows one heading rather than the completed/current/next sequence. | Label duration in months; add name/email/tel autocomplete and telephone input hints. Keep plan selection/confirmation, disclosure and required contact fields; collapse the optional message and repeated explanatory detail. Show a clear sequence: Contact → Email/details → Showroom review → Login setup → First payment, derived from records. Do not autosave consent or expose an identity-lookup endpoint. |
| P1 — Customer documents and payment status | Receipts/statements have Print but no explicit return-to-plan link. Pending status requires full-page refresh; the customer has no dedicated cross-plan document list. | Add return links, plan/date context and a Documents destination; preserve full printable documents. Provide a read-only status refresh with an observed/checked timestamp distinct from payment confirmation, bounded refresh and visible recovery guidance. |
| P1 — Owner discovery/readiness | Ten Operations links mix daily tasks, configuration, communication and privacy. Today has three queues but does not surface the missing offered-grade rate shown on Payment operations; privacy review is elsewhere. | Use grouped persistent desktop navigation and a mobile drawer. Add a compact readiness summary with direct links for blocked grades/payment availability and due privacy/settlement work, derived from existing selectors. Preserve distinct payment exceptions and do not create new automatic actions. |
| P1 — Owner lookup/return context | Applications has stage/type filters but no applicant text search. Review's Applications inbox link drops the originating filters. Customer search itself already retains the query across pagination. | Add bounded applicant lookup by approved search fields, readable status tabs/counts and safe return-to-results state. Preserve stage/type/customer/page across review; only allow local return URLs. Do not count a plan application and its identity as two customer applications. |
| P1 — Payment scope/export | A customer-filtered Contributions screen displays business-wide daily totals; Download CSV points to the unfiltered successful/reversed-record export rather than the visible customer/attempt list. This is an owner scope/expectation problem, not a demonstrated permission breach. | Separate business overview from customer totals. Make export scope/status exclusions explicit or supply a correctly scoped export using validated selectors. Add bounded reference/date/status/method lookup and a payment-detail destination. |
| P1 — Owner cash entry | The customer page offers Record in-store cash for the pending-Razorpay agreement; its GET shows an entry form plus generic pending-order warning. Specific blocking is deferred to preview/service validation. | Show the recorded blocker before data entry and link to the relevant payment evidence. Recheck at preview/commit regardless; do not weaken pending-order, rate, pause or cash-confirmation safeguards. |
| P2 — Owner/customer context | Owner customer details repeat identity in the context strip, heading and profile, while agreements mainly link to statement/cash. Balances, payment exceptions and review/access history require other screens. | A customer workspace with Summary, Applications, Plans, Payments, Documents and Access/privacy sections; compact persistent identity context and contextual actions. Preserve standalone URLs and permission-scoped reads. |
| P2 — Density and list navigation | Marketing-style large headings, generous padding and stacked cards make routine owner scanning slow. Synthetic mobile Today measured 4545px; customer dashboard 3496px including footer. Customer pagination/results count is at the bottom of 25 cards. | Retain the brand on public pages; use compact operational typography, rows and short summaries for owner work. Put result counts/page controls above and below lists; keep mobile rows readable and touch targets usable. Page height is diagnostic, not a promised conversion metric. |
| P2 — Language and hierarchy | Customer copy includes Immutable allocations, outstanding entitlements and implementation details; owner approval says activation email is sent after commit. Amounts lack Indian digit grouping and status badges are visually similar. | Use plain-language customer explanations and outcome-based owner text; retain audit detail behind labelled disclosure. Consistent INR/date/rate formatting, semantic statuses and one primary action per task. Preserve exact grade, authoritative precision and explicit Test/practice disclosure; never hide Test mode to look live. |
| P2 — Empty states and forms | Settlement eligibility renders repeated empty tables; reminder/privacy empty states offer limited onward guidance. Long forms and document pages use inconsistent Back/Cancel placement. | Compact empty states, meaningful task guidance, consistent breadcrumbs/Back/Cancel and error summary/focus behavior. Keep full confirmation for consequential actions. |

### Approved screen organization

The owner approved this organization on 22 October 2026. It is implemented locally;
production rollout and measured task completion remain pending. Permissions are unchanged.

| Stakeholder | Main destinations | Contextual organization |
| --- | --- | --- |
| Prospective customer | Plans, How it works, Showroom help; customer login secondary | Selected plan → contact/preferences → protected email/details → showroom review → password setup/sign-in → correct first-payment state. Resume through the protected email link, never public identity search. |
| Existing customer | Home, My plans, Applications, Documents, Help; Account menu | Home shows actionable stages and compact balances. Each plan has Overview/Terms, Payments, Documents and eligibility information, with one state-derived next action. Security/Google/deletion remain discoverable in Account. |
| Owner | Today, Customers, Applications, Payments, Settlements, Administration | Payments groups contribution evidence/exceptions and cash entry through customer context; Settlements groups eligibility/history. Administration groups rates/plans/payment hours, communications, privacy and audit. Financial overview stays accessible as a report. Mobile uses a drawer; do not cram all destinations into a narrow top bar. |

- **FW-UX-004 — Refine customer and owner organization from browser findings:**
  Implementation complete locally, including the remaining-audit checklist in MVP_PLAN.md.
  Release and real-user acceptance remain open. Addresses the P1 findings, typography/density and
  empty-state polish. Keep Django/Bootstrap, existing authentication and scoped URLs,
  separate identity/agreement records and all financial safeguards. No React, internal
  REST API or general frontend rewrite is required. Missing business copy/Tamil input
  remains `FW-UX-002`/`003`; release evidence remains `FW-UX-001`.
  Acceptance: both roles find their common tasks through the proposed grouping;
  customer plans/progress do not duplicate primary actions; scope/export labels agree
  with actual rows; blocked cash/payment paths explain the recorded reason before
  entry; search/filter/page context survives review and Back. Regress scoping, consent,
  snapshots, changed offers, concurrent approval and server payment outcomes where
  affected, and inspect mobile/desktop plus keyboard/focus/error behavior. Validate
  task completion with users before claiming conversion or efficiency improvements.

Local implementation covers role navigation/drawer, Today rate/payment readiness and due
privacy/settlement links, bounded applicant search and safe inbox return, shared payment filters
and scoped CSV/totals, cash blockers before input, customer sections, compact actionable Home,
Applications/Documents, bounded histories, snapshot terms, document returns, contact autofill,
month units, optional message disclosure, stage tabs/counts, six milestones through login/real
first payment, exact-customer privacy history/review return, document/cancel navigation,
INR grouping, Test/practice print labels and simpler empty states.
The earlier audit table is historical evidence of the pre-change gaps. See STATUS.md for actual
verification. Missing business/Tamil inputs stay open. Real-user task completion and production
conversion outcomes are not proven by local implementation.

Implementation and acceptance are tracked separately:

- [x] FW-UX-004 local implementation, including stage counts, full milestones, privacy context
  and document consistency. See STATUS.md for regression/browser evidence.
- [x] FW-UX-005 approved read-only pilot and owner filter extension. Synthetic full/fragment
  comparisons show smaller HTML with identical scoped records, not measured task-time savings.
- [x] Synthetic local dump/restore and pending-migration rehearsal, with preserved legacy records,
  separated liabilities and new application/activation checks. See PRODUCTION_DEPLOYMENT.md.
- [x] Local owner acceptance: owner tested both roles and reported satisfaction on 22 October
  2026. This is stakeholder acceptance, not an independent customer study or conversion result.
- [ ] Exact-image staging checks and separately approved production rollout.
- [ ] Broader customer/Tamil research where required; no unobserved task metrics claimed.
- [ ] Measure production funnel/task outcomes after release; conversion uplift is not established.
- [ ] Reassess lazy history or bounded polling only when measured interactions warrant it.

### HTMX assessment and bounded pilot

The approved local refinement pins HTMX 2.0.11 for owner customer search/paging, application,
payment and exception filters, and manual customer recorded-status refresh. Lazy history,
polling and form-preview candidates below remain conditional. HTMX can request and swap
server-rendered HTML fragments, fitting the existing Django views, selectors and
template includes without an internal JSON API. It makes selected interactions less
disruptive; it does not organize navigation, improve wording or establish a payment
outcome by itself. Source: [official HTMX documentation](https://htmx.org/docs/).

| Fit / order | Candidate | Bounded behavior |
| --- | --- | --- |
| Best first | Owner customer search and pagination | Debounced input, loading/count feedback, replace only results/pagination and cancel stale requests. Keep query limits, fixed pages, explicit Search and ordinary GET fallback. See [active search](https://htmx.org/examples/active-search/) and [request synchronization](https://htmx.org/attributes/hx-sync/). |
| Implemented locally | Application/exception/payment filters | Swap current results and counts without replacing the page shell; preserve safe URL state, customer scope and result-return context. New filter/reference/date support is separate backend work, not something HTMX adds automatically. |
| Manual refresh implemented; polling conditional | Customer pending-payment status | Refresh only the protected recorded-status panel. Any later polling must pause when hidden and stop at a terminal state or bounded timeout; retain manual refresh/error guidance. GET must not call the provider, verify capture, reconcile, create an order or retry a financial mutation. |
| Useful later | Customer workspace/read-only history tabs | Lazy-load scoped applications/payments/documents and bound history pages. Ordinary URLs must render complete pages and work without JavaScript. |
| Conditional | Plan-dependent form help and cash review preview | Use server fragments where authoritative choices or snapshot previews require a server read; keep final confirmation/rechecks and unchanged consent. Existing rate-difference JavaScript and Bootstrap disclosures already work; do not replace simple local interactions merely to use HTMX. |
| Avoid initially | Login, Google OAuth, private verification/setup, approval, checkout, cash settlement/correction and deletion completion | Keep normal protected navigation/POST/redirect and explicit confirmations. Do not blanket-boost the site, put financial success in optimistic UI or automatically repeat a timed-out POST. |

- **FW-UX-005 — Pilot HTMX as progressive enhancement:** Approved pilot and owner filter extension implemented locally with
  customer search/pagination, application/payment/exception filters and manual status refresh, following
  `FW-UX-004`. The reviewed HTMX asset is pinned and served locally; the read-only pilot
  introduces no runtime service, framework migration or database change.
  Use the same selector-backed view for full HTML and an included results fragment;
  treat `HX-Request` only as a presentation hint, never authentication/authorization.
  Preserve normal forms/links, escaped templates, CSRF on any later POST and owner/
  customer scoping on every fragment request. Set appropriate `Vary: HX-Request`
  when representations differ and prevent private response caching.

  Disable HTMX history snapshots for private pages (`hx-history="false"` and a
  reviewed cache configuration); HTTP no-store alone does not control its localStorage
  history. Keep token-bearing routes outside the pilot and avoid capturing private
  URLs, query contents or `HX-Current-URL` in telemetry/logs. See [history privacy](https://htmx.org/attributes/hx-history/).
  Handle session expiry with full navigation to the existing login flow rather than
  inserting a login page into results; review [HX-Redirect](https://htmx.org/headers/hx-redirect/)
  and ordinary redirect semantics before implementation. Provide loading/empty/error/
  offline states, accessible result announcements and predictable focus. Abort older
  search responses so they cannot replace newer results. Do not fetch private HTML
  from external origins or enable dynamic script execution unnecessarily.

  Acceptance: full-page and fragment requests return the same bounded/scoped records;
  direct unauthenticated/other-role requests fail; normal GETs still work with JS off;
  rapid input/page changes, empty results, session expiry, network failure and Back
  preserve correct scope and usable controls; no private snapshots enter localStorage;
  keyboard/screen-reader feedback works at mobile/desktop sizes. Compare rendered
  payload, request counts and observed task usability before extending to more screens.
  A cancelled browser request is not proof that a server-side mutation was cancelled.
  The first implementation uses manual status refresh, not polling. Lazy history
  fragments and bounded visibility-aware polling remain conditional on measured need; retain
  full-page fallback. Compare payload/request counts and actual usability before expanding.

## Prioritization

Use the **29 October current priority override** above for active delivery order:
one reviewed supported offer through controlled activation, then observed feedback,
then one scoped improvement. The principles below govern risk; they do not reopen
every historic backlog item as a new prerequisite for this already-deployed builder.

1. Protect real funds: monitoring, recovery, rotation, webhook reconciliation, and
   correction controls.
2. Complete legal/accounting and statutory-document review for the live business
   flows.
3. Improve settlement, eligibility communication, and customer onboarding only after
   their business rules are approved.
4. Add catalogue and pricing enhancements without coupling CMS state to financial
   contracts.
5. Validate mobile demand through a policy-ready PWA/TWA pilot before accepting a
   native API, duplicated financial presentation, or cross-platform framework.

## Production operations

- **FW-CI-001 - Profile and safely parallelize the full test suite:** Owner
  prioritized implementation on 29 October 2026 before rerunning release CI.
  Baseline run `40670193738` passed 1,473 tests in 14,359.871s. The two duplicate
  runs on `e27f820` were cancelled intentionally; neither is a test failure.
  - [x] Remove duplicate feature push/PR runs; cancel superseded PR runs without
    interrupting main image publication.
  - [x] Partition complete discovered classes across four separate runner/PostgreSQL
    jobs, sequential within each job; preserve migration round trips, internal
    concurrency tests, normal hashing and every discovered test.
  - [x] Preserve required `django` and `container` checks. The Django gate requires
    checks/all shards and verifies exact complete inventory, executed IDs, revision
    and success; missing/stale/duplicate/failed reports refuse approval.
  - [x] Add all-test duration artifacts, slowest-test output and Django database/suite
    timings; start with deterministic transactional-first/class-size balancing, then use measured results
    for later rebalance. No performance improvement is asserted before measurement.
  - [x] Successful optimized full CI accepted: run `40799459905` on `46c7fd8`
    passed all 1,492 tests exactly once, with required checks/build/security gates.
    Hosted span 62m39s compared with the approximately four-hour earlier serial base
    suite; differing revisions/runner conditions prevent a controlled speedup claim.
    Initial schema-leak/obsolete-assertion failures were reproduced and fixed before
    this green result. PR #77 merged without changing the tested tree.
  - Optional follow-up: use retained all-case timings to rebalance the slowest classes
    (successful shard suites ranged 1,278-3,637s), repeat same-revision measurements
    and preserve complete inventory/database isolation. This tuning is deferred and
    does not add a new blocker to the builder's final image/release acceptance.

- **FW-PROD-009 — Optional isolated staging for higher-risk releases:** Deferred by
  owner decision on 22 October 2026 in favour of CI, an exact-image local PostgreSQL
  rehearsal and a controlled production rollout. Separate staging is not a blanket
  prerequisite for every release. Reconsider for payment/authentication architecture,
  destructive migrations, provider changes or substantial deployment changes.
  - [ ] Agree a budget and isolated temporary or persistent host, database, hostname,
    media and sandbox-provider credentials. Do not add a competing stack to the 1 GB
    serving host or reuse production data/secrets without an approved isolation and
    sanitization procedure.
  - [ ] Rehearse the same published digest, HTTPS/proxy/CSRF, normal and enhanced
    browser journeys, provider delivery, log redaction and recovery; retain evidence.
  - [ ] Define teardown/cost controls and a risk-based rule for when staging is needed.
  The 22 October release exception does not mark these external checks completed.

- **FW-PROD-007 — Budget-conscious security-log preservation:** Inventory and phased
  plan documented on 10 September 2026; implementation and production acceptance
  pending. Use the 180-day security-log planning baseline in the
  [production guide](PRODUCTION_DEPLOYMENT.md#budget-conscious-security-log-preservation-plan-fw-prod-007),
  not the withdrawn standalone 14-day journal proposal. This bounded preservation
  work does not close `FW-PROD-002` monitoring/alerts or certify legal compliance.

  - [x] Inspect repository logging and record owner-supplied Docker/journal/syslog/UFW evidence.
  - [ ] Resolve rotation/provider/event-coverage gaps and verify clock synchronization.
  - [ ] Measure daily compressed volume, choose private storage and approve cost/access/custodians.
  - [ ] Implement tested, bounded incremental capture, encrypted archives, checkpoints and failure reporting.
  - [ ] Exercise rotation/restart/outage recovery, independent retrieval, access denial and hold-aware expiry.
  - [ ] Accept production coverage without claiming unavailable historical logs; only then review shorter local retention.

- **FW-PROD-002 — Activate and exercise external observability:** Caddy already
  provides masked structured logs, release-labelled health endpoints, and the
  repository includes a five-minute financial-exception heartbeat. Configure the
  selected external monitoring/log-retention accounts and retain exercised evidence
  for readiness/5xx failures, webhook and allocation exceptions, database capacity,
  certificate renewal, backup failure, escalation, and retention. Paid monitoring
  remains explicitly deferred for budget reasons; local checks and provider consoles
  do not close this item.
- **FW-PROD-003 — Rehearse coordinated secret rotation:** Postmark delivery and the
  owned Django Site identity are verified. Rehearse Django signing-key, database,
  SMTP, Razorpay API, and webhook-secret changes with bounded overlap or coordinated
  cutover, rollback criteria, and retained evidence. SMTP token rotation remains
  explicitly deferred.
- **FW-PROD-005 — Obtain formal policy review:** Public business, contact, privacy,
  terms, cancellation/refund, fulfilment, and database-backed pricing pages are live.
  Obtain appropriate Indian legal/accounting review before treating them as binding,
  and verify the manual payment-error refund process can meet the displayed response
  timelines.
- **FW-PROD-008 — Migrate transactional email from Postmark to Amazon SES:** Added
  22 October 2026 at the owner's request. Setup/migration authorised 24 October;
  the owner accepts a brief interruption for the final web-container replacement.
  Execution is in progress; Postmark still serves production. Follow the staged
  sequence in [Production deployment](PRODUCTION_DEPLOYMENT.md#amazon-ses-migration-fw-prod-008-in-progress-24-october-2026).
  Retain Django's standard SMTP backend, existing templates and notification services.
  No database migration, AWS SDK or new runtime service is expected for SMTP sending.
  Keep Postmark current until SES verification, production access, operations and
  controlled delivery gates pass; retain it for rollback after the authorised switch.

  - [ ] Select the AWS account/region and verify sender identities, DKIM and DMARC
    alignment; configure custom MAIL FROM/SPF if used without disrupting existing
    mailbox delivery or Postmark DNS. Obtain SES production access and suitable
    sending quotas in that region before sending to unverified customer recipients.
  - [x] Create restricted, region-specific SES SMTP credentials and test TLS on port
    587 from the application host; keep secrets outside the repository. Prepare the
    environment change and credential rotation/rollback procedure (`FW-PROD-003`).
    Completed 24 October: console-disabled SMTP user, exact Mumbai identity plus
    configuration-set resources and admin FromAddress restriction; TLS 1.3/auth 235,
    controlled authenticated inbox delivery, and alternate-sender rejection verified.
    Candidate credentials are protected outside the server application repository;
    production still uses Postmark. Production-access review remains pending.
  - [x] Configure bounce/complaint handling, suppression, delivery/failure evidence
    and alerts (`FW-PROD-002`). Preserve the distinction between SMTP acceptance and
    inbox delivery; agree how owners review and recover delivery failures.
    Completed 24 October: account bounce/complaint suppression and feedback forwarding;
    exact-set/account-scoped SNS failure topic and confirmed admin email subscription.
    Both simulator event types reached the Inbox through SNS. Direct feedback's bounce
    went to Spam, retained as a secondary route without a spam-bypass rule. Controlled
    real-inbox transport evidence and manual owner recovery are in the runbook.
  - [ ] Review Postmark-specific tracking/tag headers across authentication,
    verification, application-progress, invitation, deletion, enrolment and reminder
    messages. Explicitly disable SES open/click tracking for private-link messages;
    verify received messages have direct, unmodified links and no tracking pixels.
    Postmark headers are not SES tracking controls.
  - [ ] Update provider references in owner privacy/disposition screens, runbooks and
    applicable privacy/Data Safety records. Record SES retention/access arrangements
    and remaining Postmark copies without rewriting historical deletion decisions or
    delivery evidence (`FW-PRIV-001B`).
  - [ ] Run affected email/privacy regressions and controlled recipient tests for
    registration, progress, activation/replacement, password reset, enrolment notices,
    reminders and deletion verification/completion. Exercise bounce/complaint handling
    and recoverable sending failure without duplicate agreements or financial writes.
  - [ ] Finish the reviewed cutover gates, execute the owner-authorised SMTP
    configuration switch and verify delivery. Retain Postmark temporarily for controlled
    rollback; do not automatically send each message through both providers. Retire
    old credentials/provider access only after acceptance and review of retained data.

  Setup references: [SES SMTP requirements](https://docs.aws.amazon.com/ses/latest/dg/send-email-smtp.html),
  [production access](https://docs.aws.amazon.com/ses/latest/dg/request-production-access.html),
  and [bounce/complaint notifications](https://docs.aws.amazon.com/ses/latest/dg/monitor-sending-activity-using-notifications.html).
  Recheck provider requirements and pricing when implementation begins; no cost or
  approval-time guarantee is part of this backlog entry.

## Payments, cash, and audit

- **FW-PAY-008 — Expired Checkout operations:** Deployed and verified on 26 October
  2026 through PR #76: shared expired-pending owner
  queue/counts, exact-payment POST inspect/confirm with signed bounded review and
  fresh provider verification, expiry-aware operator command, and five-minute
  bounded inspection with combined aggregate heartbeat delivery. The timer is
  inspection-only; owner apply still uses the existing audited financial service.

  The 26 October recurrence also requires checkout prevention in this same isolated
  release: durable submission aliases, signed displayed-history context, one unresolved
  online attempt per agreement, committed order intent before provider I/O, safe
  uncertainty holds, and owner/provider-backed identity recovery. Combined regression,
  exact-image rehearsal, production migration/rollout and delivered failure/missed-run/
  recovery monitoring acceptance passed. Recovery alone does not prevent a fresh
  duplicate checkout; the prevention guards are included in this deployed release.

  - [x] All-mode expired-attempt visibility and pagination/count parity, including
    missing provider identity and records beyond the inspection batch.
  - [x] Owner/CSRF/method guards, reason, owner/order/state-bound review and fresh
    provider inspection. Uncertain, attempted and cross-mode records remain held.
  - [x] Exact contribution selection, deadline-plus-grace default and redacted
    monitoring failures. No automatic refunds, entitlement overrides or timer writes.
  - [x] Hardened timer and combined financial/provider heartbeat wrapper; configured
    external delivery is required by the shipped unit and cannot silently downgrade.
  - [x] Complete final local/CI/exact-image release verification and production rollout.
  - [x] Verify/reuse or add the financial heartbeat in the existing Better Stack
    account, securely configure its URL, and prove delivered failure, missed-job and
    recovery alerts. A missing host-side financial timer/configuration does not imply
    the external monitoring service is absent; no Healthchecks.io account is needed.
    These are owner/operator alerts about expired provider checkouts, not customer
    overdue-contribution reminder emails. Any latter policy is separate and must
    respect actual agreed payment obligations, including flexible agreements.

- **FW-PAY-003 — Complete Razorpay webhook-recovery evidence:** ADR-0006 and release
  `69eecf9` provide signed-event classification, append-only attempt evidence, and an
  owner-only provider-backed dry-run/apply workflow. The remaining work is:

  - [ ] Exercise one controlled review/dry-run/apply case in isolated Test mode.
  - [ ] Replay an already-processed Live capture from Razorpay and prove an
    `ALREADY_FINAL` attempt is appended without duplicate entitlement.
  - [ ] Alert on stale `RECEIVED` and unresolved `REVIEW_REQUIRED` events under
    `FW-PROD-002`.
  - [ ] Rehearse synchronized webhook-secret rotation under `FW-PROD-003`.

  Automatic refunds, background workers, and manual entitlement overrides remain out
  of scope.
- **FW-PAY-007 — Extend payment schedules only if required:** Current controls support
  one weekly window per day plus audited manual pause/resume. Define holiday
  exceptions, multiple daily windows, expiring force-open overrides, and a separate
  allocation-integrity hold before implementing any of them.
- **FW-AUDIT-002 — Define segregation of duties:** Decide who may initiate, approve,
  and review sensitive settlements, refunds, corrections, and exceptional cash
  operations. Implement dual approval only after those roles and thresholds are
  approved.
- **FW-AUDIT-003 — Expand external settlement reconciliation:** The existing queue
  covers paid-unallocated allocations and failed/mismatched webhooks. Add resolution
  workflows for delayed or provider-only payments, late captures, Razorpay refunds
  and disputes, chargebacks, and other provider/local differences.
  Monthly-plan P2b.3b now contains these capture exceptions without extra credit, but
  does not certify refund completion or clear their holds. Define provider-verified
  disposition/closure evidence here alongside FW-AUDIT-005; never clear an event by
  editing its status or treating an investigation note as a completed refund.
- **FW-AUDIT-004 — Automate safe allocation recovery:** Add bounded retries and
  external alerts for `PAID_UNALLOCATED` metal contributions while preserving
  idempotency and owner visibility.
- **FW-AUDIT-005 — Define online-payment correction and void policy:** Specify
  compensating-event shape, evidence, customer disclosure, authorization, and
  provider reconciliation. Decide whether database-trigger protection against bulk
  updates is warranted. Never edit a historical payment or Scheme Rate.
- **FW-CASH-001 — Harden showroom cash operations:** Obtain legal/accounting review
  of cash acceptance and external bookkeeping; decide statutory receipt requirements,
  daily close ownership, corrections outside the configured 24-hour window, refunds,
  and dual approval. The deployed append-only reversal is a bookkeeping correction,
  not a refund.
- **FW-PRODUCT-002 — Resolve the empty legacy CASH account:** One inert production
  CASH account has no liability and no audited cancellation state. Decide with the
  customer and business owner whether a general no-liability cancellation workflow is
  required. Never delete it, relabel its mode, or mark it redeemed merely to hide it.

## Bonus, documents, pricing, and settlement

- **FW-BONUS-004 — Define richer bonus policy if CASH products return:** Specify caps,
  tiers, discretionary approval, forfeiture, cancellation, tax treatment, and whether
  projections may include expected future contributions. Current projections use
  paid principal only.
- **FW-BONUS-005 — Optimize bonus aggregation only when measured:** Retain the
  correctness-first per-account calculation until production volume demonstrates a
  material cost.
- **FW-DOC-004 — Define statutory receipt/invoice requirements:** Decide business and
  tax identity fields, jurisdictional numbering, signatures, retained rendered copies,
  delivery/reissue tracking, correction/cancellation treatment, date-filtered exports,
  and whether server-generated PDF/PDF-A is required. Current HTML documents are
  acknowledgements, not tax invoices.
- **FW-PRICE-002 — Model early-discontinuation terms:** Define the exact plan-specific
  wastage/value-addition discount schedule before advertising numeric benefits. Until
  then, the public policy promises no additional discount unless it exists in the
  customer's written enrolment terms.
- **FW-SETTLE-001 — Integrate fulfilment evidence if required:** Add actual payout,
  metal handover, or point-of-sale confirmation only if the application must execute
  rather than merely record settlement.
- **FW-SETTLE-002 — Define metal-to-cash conversion:** Approve authoritative rate
  timing, spread or fee, taxes, rounding, authorization, and customer disclosure
  before implementation.
- **FW-SETTLE-003 — Partial-redemption decision superseded by full-only settlement:**
  Owner explicitly rejected partial redemption on 22 October 2026. Do not implement
  partial minimums/counts or expose a partial option in the builder. Enforcement and
  legacy-contract/history review are tracked under `FW-PLAN-002`; the current partial
  service path still exists until that implementation is reviewed and deployed.
- **FW-SETTLE-004 — Keep inventory and invoicing separate:** If introduced, validate
  jewellery invoice value, taxes, making charges, returns, and stock movement in a
  dedicated bounded workflow. Current redemption stores only external references and
  notes.

## Privacy and identity lifecycle

- **FW-PRIV-001B — Complete verified customer account deletion:** ADR-0015 is accepted,
  and `FW-PRIV-001A` supplies a disabled public/authenticated request, one-time
  verification, immediate access containment, owner queue, reasoned hold, provider
  notice evidence, and aggregate integrity check. The owner accepted the
  24-hour/7-day/30-day service targets and entitlement-preserving communication.
  On 10 September the owner accepted the revised ADR-0015 owner-operated approach;
  professional sign-off is no longer a blanket development prerequisite. The
  read-only owner disposition preview is implemented with separated financial
  balances, related-record counts, local review flags and explicit external unknowns.
  Structured category/field decisions, atomic minimization/completion, retryable
  notices and retained-record reviews are deployed with migration `accounts.0006`.
  The disabled rollout is accepted on release `7819fd9552825c61ebc34a7844ba346c7ad92488`;
  deletion request intake is enabled. Authenticated zero-history completion was
  production-accepted on 15 September 2026: one immutable completion decision,
  minimized profile, unusable credentials, accepted/delivered notice and clean
  owner-confirmed integrity checks. The separate signed-out email-verification
  journey remains unaccepted; the last recorded dependency is an independently
  receiving owner-controlled Workspace alias. Independent Drive/USB access and the
  fictional decision sequence exercise passed; custody roles and the restore-isolation
  rule are accepted.
  Next complete that separate public-path acceptance without verification bypass,
  record provider follow-up and independent before/after recovery reconciliation,
  and retain per-case dispositions/review dates. Enablement and the authenticated
  completion are already done; do not repeat them as missing implementation. The separate
  `FW-PROD-007` archive implementation is not a Google Play-specific submission gate;
  applicable security obligations remain open. No automatic financial-evidence
  destruction or blanket statutory period is approved. Public Play release remains
  blocked on the remaining public-path, provider and recovery evidence recorded in
  [Mobile release readiness](MOBILE_RELEASE_READINESS.md#account-deletion-and-retention-design-gate).
  **29 October operational follow-up:** production's deletion check reports three
  overdue owner reviews; structural/containment/completion counters are clean.
  Both `d0e5dd1` and deployed builder `8f3ba5a` report the identical backlog.
  Review the retained cases through the owner workflow and record real dispositions
  or next-review dates; do not clear them merely to make the diagnostic pass.
  Never cascade-delete `CustomUser`, `Customer`, or
  financial records.
  Standalone/unapproved applicant minimization and ambiguous email-matched historical
  applications need a separately reviewed disposition path; this completion service
  stops instead of guessing ownership. Automatic external-copy disposal, financial
  purge and restore-suppression automation remain unimplemented. Retention due dates
  and failed notices require daily owner review, not a claim of automated disposal.

## Eligibility and customer communication

- **FW-AUTH-005 — Define audited Google credential recovery:** Customer self-service
  unlink, owner/staff social login, additional providers, and provider-assisted
  registration remain outside the accepted `FW-AUTH-004` boundary. If operational
  experience requires removal or replacement of a linked Google identity, first
  define an owner-authorized, append-oriented recovery workflow that preserves the
  binding history, verifies the customer through an independent channel, and cannot
  silently weaken password fallback. Until then, deactivating the affected customer
  and disabling Google login are the containment controls.

- **FW-ELIG-002 — Observe the first genuine reminder delivery:** The configurable
  email audiences, immutable reminder/attempt evidence, bounded retries, aggregate
  command, owner view, additive `schemes.0019` migration, and hardened systemd
  execution boundary are deployed. A zero-candidate production run correctly sent
  nothing. Formal closure now requires the first naturally occurring reminder to be
  accepted by Postmark and appear in the owner delivery view; do not manufacture a
  financial or redemption event for this observation. This does not block other
  isolated development.

## Rates, media, and catalogue

- **FW-CMS-004 — Complete the bounded Jewellery journal launch:** The separate
  Wagtail root/article model, dedicated staff groups/media/workflow, Bootstrap 5
  presentation, and disabled-first gate are deployed and production-accepted. Create
  and approve genuine business-authored articles, then verify direct routes, mobile,
  accessibility, metadata, pagination, and R2 renditions before separately enabling
  public discovery. Scheme Rates, plans, products, policies, customer advice, and
  financial records remain outside the journal.
- **FW-RATE-003 — Keep external rates informational:** If market data is later useful,
  add it only as owner-facing reference information. It must not control customer
  allocation without a new ADR and explicit pricing/disclosure rules.
- **FW-MEDIA-002 — Add independent media recovery and monitoring:** The owner accepted
  deferring the isolated copy/delete/restore/hash drill and ongoing usage monitoring.
  Until a separate backup target and periodic restore proof exist, retain approved
  source photographs outside R2 and never treat R2 as their only copy.
- **FW-CATALOG-005 — Add Scheme Plan marketing media without financial coupling:**
  Design optional Wagtail-managed imagery/editorial presentation linked to an
  authoritative `SchemePlan`. CMS state must not control or duplicate contribution
  amounts, duration, frequency, grade, bonus, eligibility, public-listing state, or
  enrolment terms. Define deletion/unpublish fallbacks, accessibility, approval, and
  historical-enrolment behavior first.

## Mobile distribution

- **FW-MOBILE-001 — Complete mobile product and store readiness:** ADR-0014 accepts a
  PWA/TWA-first, customer-only pilot without a new API. Confirm the initial customer
  journeys and success measures; reserve the permanent package identifier; establish
  the business-owned Google Play organization account and signing ownership; review
  the app name and savings-not-investment wording; classify the Financial features
  declaration; draft accurate Data Safety answers; and approve an account-deletion
  request/retention workflow that preserves justified financial history. Record the
  Android support floor, current target-API requirement, browser/device matrix, and
  store-review evidence before implementation is called release-ready. The canonical
  readiness record is `docs/MOBILE_RELEASE_READINESS.md`. Product, package, wording,
  declaration, data, deletion, reviewer-account, test-matrix, and pilot defaults are
  now drafted there. The owner approved the permanent package/store identity as
  `com.jaishrikrishnajewellery.savings` on 5 September 2026. On 8 September the
  verified Play organization created the draft app, registered that package, and
  obtained a Play App Signing SHA-256 identity. Release `1826afec` publishes the
  registered package and first Play certificate after a successful disabled-first
  rollout. A signed Internal Testing bundle was accepted on 9 September; the installed
  APK proved an additional Google-managed Play certificate that must be retained
  additively in the origin statement. Release `0c611f6` published both Play
  certificates; Google and Android verification passed and the installed app opened
  without browser chrome. Completion remains blocked on payments/recovery/role
  evidence, financial classification, per-category retention/provider/recovery review,
  the separate signed-out deletion acceptance, dedicated reviewer access, reviewed
  store assets/listing and release-candidate Data Safety review/Console submission.
  Deletion implementation, enablement and authenticated completion are already
  evidenced. Recheck current platform requirements at submission; the recorded API
  floor/target is a tested baseline, not a new external-policy verification.
  The organization D-U-N-S value remains
  intentionally outside the repository.
- **FW-MOBILE-003 — Finish acceptance of the customer-only Android TWA:** The Android
  repository/CI, permanent package/signing identity, signed Internal Testing bundle
  and exact Digital Asset Links are implemented; this is remaining acceptance work.
  Expose only the existing customer experience. Do not add a mobile API, owner tools,
  embedded WebView OAuth, application secrets, direct database access, or on-host
  Android builds. Validate browser fallback, App Links, Google OAuth, Razorpay/UPI
  handoff and return, process death, updates, accessibility, and release signing.
  Foundation state on 8 September 2026: the private organization repository
  `Jai-Sri-Krishna-Jewellery/jsk-savings-android` is initialized with the permanent
  package, API 29 floor/API 36 target, secret/permission invariants, and passing local
  and GitHub-hosted builds. The recoverable upload key has two verified encrypted
  backups; encrypted GitHub secrets produced a verified signed AAB that Play accepted
  for Internal Testing. Device inspection discovered the additive Play signing
  certificate keyset requirement; its production rollout and no-browser-chrome
  association now pass. The remaining device/journey matrix and final release
  evidence remain open. The canonical readiness guide now contains the bounded,
  evidence-safe Internal Testing customer-journey matrix; its unrun rows are not
  completion evidence.
  GitHub cannot enforce protection on this private organization repository under the
  current plan; retain procedural green-PR discipline until an upgrade or separately
  approved public-source decision resolves that gate.
- **FW-MOBILE-004 — Run a bounded Play and customer pilot:** Start with Play Internal
  Testing. As of 10 September 2026 the owner reports approximately five customers
  and confirms core authentication, registration, enrolment, payments, and documents
  through the Play-installed Android app. Record this as a pilot in progress, not
  completed negative-case or device-matrix acceptance. Continue with Play Internal
  Testing and approximately five to ten legitimate customers. Pass password and linked-
  Google login, unconnected-identity rejection, registration/enrolment boundaries,
  Razorpay Test checkout, one approved low-value Live reconciliation, cancellation,
  expiry, payment pause, receipt, statement, and no-secret log checks. Retain only
  aggregate activation, conversion, contribution completion, failure/cancellation,
  repeat-use, crash, and support evidence before broader distribution.
- **FW-MOBILE-005 — Decide whether a native/API client is justified:** After a stable
  pilot, compare observed limitations with native push, biometrics/passkeys, richer
  navigation, offline non-authoritative documents, and iOS demand. A positive decision
  requires a new ADR for a versioned customer API, mobile auth/revocation, native
  Razorpay, idempotency, rate limiting, secure storage, threat modeling, and client
  release operations. Evaluate Flutter only for a justified near-term shared Android/
  iOS client; otherwise evaluate Kotlin/Compose for an Android-only native phase.

## Completed item index

### Implemented and verified locally; production rollout pending

All four customer conversion phases are committed in `7d07cf2`. Their completed
scope must not be mistaken for production acceptance or measured business results.

| Phase | Completed scope | Acceptance evidence |
| --- | --- | --- |
| 1 — Offer clarity, measurement and payment correctness | Record-derived public offers and plan-first action; aggregate-only funnel report; truthful availability, abandoned and uncertain-payment states | 446 serial full-suite tests; focused follow-up and mobile/desktop inspection recorded in `STATUS.md` |
| 2 — Owner workflow | Today, unified inbox/review/context, customer search and bounded pagination | 460 serial full-suite tests, 68 focused regressions and mobile/desktop inspection |
| 3 — Continuous application | Durable plan/grade/preferences, protected verification/progress, renewed confirmation and transactional coordinated approval with separate records/audit | 494 serial full-suite tests, 136 focused regressions including concurrent approval, and mobile/desktop inspection |
| 4 — Activation and continuation | Scoped activation continuation, prominent progress, record-derived payment action, expired-link owner recovery and Google eligibility copy | 514 serial full-suite tests, 130 final focused regressions and mobile/desktop inspection; Tamil protocol prepared only |

These are the recorded 5 October implementation runs, not tests rerun for this
documentation review. Release/measurement work is `FW-UX-001`; business copy and
Tamil follow-ups are `FW-UX-002` and `FW-UX-003`.

### Previously completed foundations and accepted rollouts

Completed implementation and rollout details are intentionally not repeated here:

- **Foundation and production:** `FW-BETA-001`, `FW-BETA-002`, `FW-BETA-003`,
  `FW-PROD-001`, `FW-PROD-004`, and `FW-PROD-006`.
- **Financial domain:** `FW-BONUS-001`, `FW-BONUS-002`, `FW-BONUS-003`,
  `FW-AUDIT-001`, `FW-DOC-001`, `FW-DOC-002`, `FW-DOC-003`, `FW-PRODUCT-001`,
  `FW-PAY-001`, `FW-PAY-002`, `FW-PAY-004`, `FW-PAY-005`, `FW-PAY-006`,
  `FW-PRICE-001`, `FW-RATE-001`, and `FW-RATE-002`.
- **Authentication and eligibility:** `FW-AUTH-001`, `FW-AUTH-002`, `FW-AUTH-003`,
  `FW-AUTH-004`, `FW-ELIG-001`, and `FW-ENROL-001`.
- **CMS, media, and catalogue:** `FW-CMS-001`, `FW-CMS-002`, `FW-CMS-003`,
  `FW-MEDIA-001`, `FW-CATALOG-001`, `FW-CATALOG-002`, `FW-CATALOG-003`, and
  `FW-CATALOG-004`.
- **Mobile:** `FW-MOBILE-002`.
- **Privacy foundation:** `FW-PRIV-001A`. Completion implementation and authenticated
  production acceptance are also done, but the remaining `FW-PRIV-001B` evidence
  stays in the active register above.

Use [Project status](STATUS.md) for the completed capability summary, the
[production runbook](PRODUCTION_DEPLOYMENT.md) for release evidence, and ADR-0003
through ADR-0015 for the corresponding durable architecture decisions.

## Historical milestone ledger

This compact ledger preserves limitations recorded at each checkpoint. “Resolved”
means later work implemented that capability; unresolved parts point to active items
above.

| Checkpoint | Limitation recorded then | Current disposition |
| --- | --- | --- |
| Milestones 0–1 | Contributions, rates, allocations, liabilities, and redemption were deferred. | Resolved by Milestones 2–8. |
| Milestone 2 | Real providers, rates, allocations, liabilities, and redemption were deferred. | Core financial flow and provider acceptance are resolved; operations remain `FW-PROD-002`, `FW-PROD-003`, and `FW-PAY-003`. |
| Milestone 3 | Paid-unallocated recovery, liabilities, providers, and redemption were deferred. | Manual recovery and the financial flow are resolved; automation remains `FW-AUDIT-004`. |
| Milestone 4 / MVP Alpha | Real providers, recovery, and redemption remained deferred. | Resolved except the active production/audit items above. |
| Milestone 5 | Provider rates, premium/tax policy, allocation automation, Razorpay, settlement, bonus, and audit were incomplete. | Manual Scheme Rates and core flows are resolved; open work remains `FW-RATE-003`, `FW-AUDIT-002`–`FW-AUDIT-005`, and `FW-BONUS-004`–`FW-BONUS-005`. |
| Milestone 6 | External Razorpay/webhook proof, live-key controls, and abandoned orders were incomplete. | Test/Live acceptance and order lifecycle are resolved; recovery evidence and operations remain `FW-PAY-003`, `FW-PROD-002`, and `FW-PROD-003`. |
| Milestone 7 | Eligibility did not initiate redemption and lacked reminders/business-day policy. | Redemption and exact-calendar policy are resolved; reminders are deployed, with the first genuine delivery observation remaining under `FW-ELIG-002`. |
| Milestone 8 | No payout, handover, POS, inventory, invoice validation, metal-to-cash policy, bonus, corrections, or documents existed. | MVP bonus/audit/documents are resolved; remaining scope is `FW-SETTLE-001`–`FW-SETTLE-004`, `FW-AUDIT-002`–`FW-AUDIT-005`, and `FW-DOC-004`. |
| Milestone 9 | Bonus lacked caps, tiers, approval, forfeiture, tax policy, and optimized aggregation. | `FW-BONUS-004`–`FW-BONUS-005`. |
| Milestone 10 | No generic payment correction, refund/dispute reconciliation, dual approval, automated retry/alerts, or database-trigger protection existed. | `FW-AUDIT-002`–`FW-AUDIT-005`, `FW-PAY-003`, and `FW-PROD-002`. |
| Milestone 11 | Documents were printable HTML rather than archived statutory invoices, with no PDF, signature, delivery log, tax identity, formal numbering, or date-filtered export. | `FW-DOC-004`. |
| September deletion rollout | Completion/minimization and enablement were pending after the containment foundation. | Implemented/deployed; authenticated zero-history completion accepted 15 September. Separate public-path, provider and recovery evidence remains `FW-PRIV-001B`. |
| September Android foundation | Signed bundle, Play certificate association and customer device acceptance were incomplete. | Signed Internal Testing and origin association accepted. Remaining release/device/pilot evidence is `FW-MOBILE-001`, `003`, `004`; native/API decision stays conditional under `005`. |
| October conversion redesign | Public plan intent, coordinated owner review and activation/payment continuation were fragmented. | All four phases implemented and verified locally in `7d07cf2`; production/measurement, business copy and Tamil follow-ups are `FW-UX-001`–`003`. |
