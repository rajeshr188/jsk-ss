# MVP Plan

## Owner builder v1 release contract (approved 24 October 2026)

Deliver one coherent owner-builder production activation, rather than activating
the currently supported subset first. Develop, review and test in small increments
behind `CONFIGURED_PLANS_ENABLED=False`; a completed development step or merged PR
is not production acceptance. Existing production workflows continue unchanged.
This supersedes earlier recommendations to release the subset after its next review.

The target is all explicitly agreed **compatible** combinations, not an arbitrary
rules engine. Scope approval does not approve an unspecified financial formula,
remove the separate INR/provider/business approval boundary, or make a family ready.
Use the existing FW-PLAN items; do not create further numbered micro-milestones.

### Approved acceptance matrix and remaining implementation

| Target family/capability | Existing foundation | Remaining decisions and implementation |
| --- | --- | --- |
| Exact-grade metal, optional contributions, duration eligibility | Local amount variants, duration rules and full settlement | Complete normal/early closure and provider-exception acceptance. Preserve historical agreements. |
| Exact-grade metal, required monthly contributions | Approved amount/count/duration variants; collection/review; gated full closure, full return and explicitly approved VA replacement | Complete presentation and lifecycle/provider-exception acceptance. |
| Flexible anytime metal (`FW-PLAN-007`) | Positive-verified-principal eligibility without invented maturity; gated full settlement, full return and approved VA replacement | Complete late-payment/lifecycle acceptance and consistent offers/reminders. No partial withdrawals. |
| INR purchase credit | Gated principal, collection, eligibility, benefit-aware disposition/return, approved-benefit replacement, principal statements and privacy retention | Complete consistent presentation and end-to-end acceptance. Obtain business/legal/accounting/provider approvals and usable refund routes before publication. Do not reuse legacy CASH promises by implication. |
| Defined benefits (`FW-PLAN-005`, `FW-PRICE-002`) | Immutable terms, qualification/calculation, retained award, invoice/return and explicit approval consumed atomically by a replacement invoice | Complete presentation and lifecycle acceptance without automatic re-spending or erasure of earned rights/principal. |
| Cross-family owner builder (`FW-PLAN-003/004/006`) | Approved compatibility matrix, versioned policies, gated collection, both application journeys and owner/outage review integration | Complete eligibility/benefit/reminder/closure paths and consistent public/owner presentation. Unsupported combinations remain unavailable; normal CI and one coherent activation are still pending. |

### Single completion checklist

- [x] Approve one coherent owner-builder v1 activation with incremental gated development.
- [x] Draft a concrete compatibility matrix, timing defaults, INR settlement and benefit vocabulary for owner review in ADR-0017 (24 October; proposal, not contract approval).
- [x] Owner approved the detailed matrix/timing, INR settlement approach and benefit types in ADR-0017, including one manual final settlement with unused-principal refund, no partial redemption and no replacement credit. External publication approvals and usable refund-route evidence remain required.
- [x] Implement typed compatibility validation and fail-closed operational support checks without altering existing persisted configuration evidence. This is the contract foundation, not new financial-workflow completion.
- [x] Persist independent duration/count/benefit fields under policy schema 2 (0036), preserving schema-1 evidence, append-only version semantics and preparation-only runtime gates. Legacy editor stays schema 1; schema-2 inspection is read-only. Verification is recorded in STATUS.md/TESTING.md.
- [x] Scope-review/checkpoint accumulated local work before widening financial implementation (`84115be`, 24 October). Separate dropdown styling and nested worktrees remain outside the checkpoint. This is a local WIP checkpoint, not exhaustive code review, clean CI or release acceptance.
- [ ] Implement separate INR entitlement/full-settlement primitives under the approved manual-fulfilment contract, without enabling public INR offers prematurely.
  - Local principal foundation (0037): distinct `INR_CREDIT` denomination, immutable source-linked receipts, full evidenced cash-entry corrections, separate principal reads and fail-closed diagnostics. Pure invoice/refund/top-up arithmetic is covered; it does not fulfil or close anything.
  - Local manual disposition foundation (0038): one immutable full-principal proposal, source-specific manual refund legs, jewellery handover/top-up evidence, remaining liability and completion-linked closure. Supports optional/calendar/no-benefit synthetic INR contracts only; actual fulfilment is owner-attested evidence, not an API-verified refund. No public workflow is enabled.
  - Local correction foundation (0039): void an entirely unfulfilled proposal, or record all fulfilled portions returned in full atomically. Retain original proposals/fulfilments/completions; restore only principal, keep the agreement contained and require fresh customer authorization/signed preview for a replacement full disposition. Partial/staged returns are not enabled. Verification is tracked in STATUS.md/TESTING.md.
  - Schema-2 contract integration: read-only resolution retains independent duration/count, amount choices, exact metal or INR denomination and benefit terms. Migration 0040 adds versioned account storage with explicit eligibility/count snapshots, nullable duration/date for count-only/anytime, and database shape constraints. Frozen-contract diagnostics use the pinned revision, not the current offer. Legacy rows keep their old dates/minimum duration and receive no invented count. This is not enrolment/payment activation; schedule, eligibility and benefit execution remain unfinished.
  - Independent schedule prerequisite: read-only construction uses required count, not duration, for original periods; preserves calendar/anniversary anchors; adds only approved ordinary replacements; and creates no obligations for optional ceilings. Benefit-only schedules do not extend principal maturity.
  - Internal schema-2 schedule/attribution integration (25 October): complete periods can be persisted atomically/idempotently before any contribution. Verified receipt/capture attribution uses the frozen required count independently of duration, with existing timing, review and correction evidence. This is tested on synthetic contracts, not accepted-enrolment or payment-entry activation. Owner investigation/outage amendment services explicitly remain closed for schema 2 until integrated; eligibility and benefit execution remain pending.
  - Gated owner-enrolment orchestration (25 October): the existing enrolment service now resolves schema-2 denomination and frozen independent terms from the locked offer, retains its publication revision, and commits account/schedule/audit together. Duration overrides are refused; count-only/anytime retain null maturity. Tests simulate only operational readiness to exercise the future path; real readiness/publication/model gates still reject schema 2. This is not public request/form/email integration or activation.
  - Verified-source INR integration (0041, 25 October): atomic captured-event principal/instalment hooks with constrained system provenance, owner cash-receipt hooks and full source-correction integration. Duplicate captures cannot create duplicate principal; timing review never discards verified funds. Collection and new-payment eligibility remain gated; callback-only principal and INR API recovery are not enabled.
  - Gated independent payment entry (0042, 25 October): server-date/amount/count/duration checks, optional calendar/anniversary cash ceilings, rate-free INR global payment controls, atomic actual cash receipt/principal/audit and required-monthly online creation/resumption. The contribution frequency retains ONCE_PER_PERIOD rather than pretending it is a calendar month. Existing metal flows remain separate. Optional online creation is explicitly blocked pending durable order-intent/recovery support; callback/API recovery remains pending. This is not collection activation or full policy-family acceptance.
  - Optional online order integration (0043, 26 October): separate immutable pre-I/O request and response/recovery binding, same-attempt resumption, unresolved-attempt containment and owner-authenticated exact identity recovery. No artificial instalments, financial credit, refreshed deadline or automatic refund; recovered orders are reconciliation-only. Runtime readiness stays closed. This is service-level integration, not owner/customer recovery-interface or full collection acceptance.
  - Callback/API principal integration (0044, 26 October): immutable minimal authenticated capture observations, separate from signed webhook timing. Callback HMAC plus exact Live API capture and owner preview/apply recovery commit source confirmation/principal together. Retries retain the original receipt source; later signed capture can supply monthly timing without double credit. Migration reversal preserves retained API evidence. Runtime gates stay closed; verification is tracked in STATUS.md/TESTING.md.
  - Collection-matrix regression checkpoint (26 October): eight new service-level tests cover 120 first-payment combinations across the five approved families, plus benefit-schedule misses, replacements, correction and delayed/ambiguous capture timing. The combined 70-test collection/entry/ledger/enrolment/API run passed. This validates collection behaviour on synthetic contracts, not benefit awards, completed settlement, full normal CI or activation. No runtime/schema change was needed.
  - Gated request/form/email integration (0045, 26 October): versioned requests pin the reviewed configuration, publication revision and offer digest. Duration/count and INR/exact-grade denomination remain independent. Signed forms reject stale terms; owner conversion preserves the requested contract atomically, and messages render frozen rules rather than legacy twelve-month/metal assumptions. Existing requests stay schema 1; rollback refuses to discard version-2 evidence. Operational publication/model gates remain closed. Local verification is recorded in STATUS.md/TESTING.md; this is not release acceptance.
  - Gated registration-first application integration (accounts 0009, 26 October): versioned append-only confirmations retain the published revision and independent terms. INR has no grade; count-only/anytime have no invented duration. Contact/verification/completion create no financial account; owner approval creates identity, exact agreement, required schedule and invitation atomically. Stale or changed-denomination offers require fresh consent. Legacy confirmation JSON remains untouched; migration guards refuse unversioned independent consent or reversal over new evidence. Local verification is recorded in STATUS.md/TESTING.md; publication/readiness gates remain closed.
  - Gated owner review/outage integration (26 October; no migration): exact verified timing, notes and holds retain existing evidence semantics. Acknowledged compensation uses frozen required count, original period basis and the policy's ordinary replacement allowance, not duration. INR reconciliation checks its own source ledger. Benefit schedules retain principal maturity and cannot override a post-duration payment cutoff. The three-period cap, future-window requirement, reconciliation, idempotency and account-lock serialization remain. Readiness still blocks writes; no benefit or eligibility is granted.
  - Independent eligibility progress (26 October; no migration): all five approved families have a current-evidence read. Count-only completes on final verification/attribution; duration-AND-count retains the later duration/final-period boundary; anytime needs verified positive principal. Missed benefit-only instalments do not postpone principal maturity or imply an award. Real-source INR/metal checks, reversals, unresolved exposure and outage holds remain separate. Accepted dispositions are not fresh spendable rights; reads do not mutate account dates/status. Legacy reminders explicitly exclude schema 2. This is not settlement authorization, completed presentation or activation.
  - Benefit qualification/calculation (26 October; no migration): unawarded progress distinguishes normal eligibility from required benefit schedules, ordinary replacement preservation from explicit loss-of-unearned-benefit rules, and acknowledged compensation from free credit. INR previews use verified net qualifying receipts, never grams/top-ups/legacy CASH bonus. VA monetary value requires invoice-charge evidence. Pure capped percentage formulas return versioned once-to-paise HALF_UP calculations. This creates no award or fulfilment and cannot remove previously earned benefits; uncertain and accepted-disposition histories remain review-only.
  - Retained benefit award foundation (0046, 26 October): one immutable purchase-bonus amount or VA right retains the pinned contract, exact source/qualification/outage evidence and calculation version. Owner-only signed previews, locked revalidation, idempotency and database uniqueness prevent stale/duplicate awards. Current-offer changes cannot rewrite history; subsequent source/correction/closure changes require review, not revocation or principal deduction. No automatic trigger, invoice spending or settlement activation is enabled. Rollback refuses existing award evidence.
  - Invoice benefit foundation (0047, 26 October): one immutable invoice application links the retained award to actual full-principal jewellery handover, with explicit gross/net invoice and VA-charge evidence. Owner-bound short-lived previews, locked source revalidation and database uniqueness prevent stale/duplicate consumption. Linked full-return evidence permits only a complete append-only benefit reversal; original records survive and returned benefits remain review-only. These records never alter principal, grams or refunds. An insufficient invoice cannot silently forfeit the unused bonus. Existing benefit-bearing settlement entry points remain blocked: atomic orchestration and lifecycle acceptance are still required. No owner/public UI or activation is supplied.
  - Independent metal settlement integration (26 October; no migration): closure-scoped evaluation preserves the public closure-pending barrier and independently determines normal/early first full disposition. Exact principal, retained/reused VA right, actual invoice benefit and closure commit together. Linked complete returns reverse principal/benefit together and contain the agreement. Missing unearned benefits do not forfeit principal; stale sources and payment/outage holds reject settlement. Existing schema-1 paths remain separate; returned/replacement histories stay blocked. Operational gates remain closed; synthetic real-service verification is tracked in TESTING.md.
  - Independent INR settlement integration (26 October; no migration): separate gated first-disposition preview uses closure-scoped eligibility across the five approved families. Proposal retains/reuses an award but reduces no liability; its split uses the exact net invoice after bonus/VA. Actual jewellery handover and benefit consumption commit together, original-source refund legs remain separate, and completion waits for all principal. Full return atomically restores principal and reverses invoice benefit; void retains unconsumed rights. Existing narrow foundation proofs remain separate; new independent replacement histories remain blocked. Read-only INR/closure diagnostics check the linked lifecycle. Synthetic service verification is recorded in TESTING.md, not release acceptance.
  - Gated replacement integration (26 October; no migration): complete predecessor void/full-return evidence and unchanged original source/qualification proof permit a linked replacement when no benefit has been consumed. Supports principal-only INR/metal and retained unconsumed INR awards. Fresh signed previews, customer authorization and invoice references are required; normal/early basis does not improve merely through time spent correcting. Original gross provider refunds still limit refund capacity. Account containment and one-successor serialization remain. Consumed/reversed benefit invoices stay blocked pending explicit reapplication history; the one-invoice constraint is not weakened.
  - Returned-benefit review foundation (0048, 26 October): owner-bound signed previews retain complete original return/award/closure evidence and append-only APPROVE/HOLD decisions. Approval needs fresh customer authorization; a later hold supersedes it without rewriting history. Account-lock serialization, predecessor/sequence constraints and rollback refusal protect the evidence. Review status never authorizes invoice consumption; the one-invoice invariant and consumed-benefit replacement barrier remain. No monetary or principal mutation is supplied by this checkpoint.
  - Approved-benefit replacement integration (0049, 26 October): a retained current approval is bound into signed replacement evidence and consumed only with the actual jewellery invoice. Original invoices remain version 1; linked successors use version 2 and preserve the award's amount/right/cap. One original invoice, one successor per predecessor and one consumption per approval prevent forks. INR proposal/handovers/refunds remain distinct; superseding holds block new fulfilment without blocking evidenced void/full-return correction. Historical review/return prefixes remain valid after later settlements. Rollback refuses replacement bindings/consumption. Operational/publication gates remain closed; verification is tracked in TESTING.md.
  - Read-only statements/privacy integration (26 October; no migration): purchase-credit receipts and statements separate principal, proposals, actual fulfilments, returns and historical closure. A separate benefit history retains award/application/reversal/review facts without treating them as cash or grams. Documents omit private authority/reason fields and fail closed on invalid principal/disposition proofs. Privacy inventories retain INR/benefit chains; unknown balances are not zero, invalid evidence blocks completion, and open principal/unfulfilled rights retain support identity. Completed minimization preserves financial history/readability. Verification is tracked in TESTING.md.
  - Shared family presentation and gated date reminders (26 October; no migration): offer preparation, owner policy inspection, pinned agreements and statements reuse independent policy facts. Customer/owner agreement cards separate duration/count and INR/metal; no invented maturity or zero-gram INR balance. Duration-based reminders recheck real principal, qualifying count where required, holds and lifecycle under the account lock with both release/readiness gates intact. Count-only/anytime receive no scheduled date forecast. The owner manual distinguishes earlier editor screenshots from broader independent families. Verification is tracked in TESTING.md.
  - Independent owner preparation editor (26 October; no migration): a separate grouped schema-2 form exposes compatible accumulation/amount/obligation/period/count/duration/missed-payment/benefit choices. Preview writes nothing; explicit save reruns model and compatibility validation through the existing owner service. Earlier editor semantics stay unchanged; successors append without rewriting history. Forged schema/provenance/grace/settlement controls are rejected. Offer creation/publication and financial activation remain blocked. Verification is tracked in TESTING.md.
  - Independent draft-offer preparation (0050, 26 October): a separate storage projection preserves true duration/null and period ceilings. Owner draft creation/identity edits retain immutable configuration and revision evidence; INR has no grade offerings. Invalid policy/activation overrides and stale edits are rejected. Existing rows/revisions remain unchanged and rollback refuses independent drafts. Publication/enrolment stay blocked; verification is tracked in TESTING.md.
  - Owner metal settlement screen (27 October; no migration): explicit invoice-benefit preview, exact-quantity/benefit confirmation and atomic full-return evidence now use the existing gated services. INR accounts no longer reach a gram-based mutation form; their route is read-only pending the dedicated interface. Verification is tracked in TESTING.md.
  - Still required: owner INR proposal/fulfilment/completion/correction and benefit reapplication review interfaces; complete owner operational-screen acceptance, full lifecycle/provider-exception and notification coverage review, query/latency and mobile/keyboard acceptance, normal CI and coherent release rehearsal. No public INR offer is enabled by these foundations.
- [ ] Implement count-only and anytime eligibility and the agreed additional amount/schedule combinations, including consistent UI, reminders and full closure.
- [ ] Implement only defined benefit policies, including qualification, actual fulfilment and append-only corrections/reversal.
- [ ] Complete verified provider-history disposition needed for closure; ambiguous payments must not be cleared by an owner checkbox.
- [ ] Verify every approved matrix row through enrolment, online/cash payment, missed/late/duplicate payment, correction, normal/early full settlement, unused cancellation and reversal. Test concurrent/idempotent paths and preserved legacy history.
- [ ] Update generated agreements, public disclosures and owner manual; complete owner/mobile/keyboard acceptance and clean normal CI.
- [ ] Rehearse exact-image migrations, rollback/forward-recovery and financial invariants; obtain explicit approval for the single production activation.

Excluded from v1: customer-authored configurations (`FW-PLAN-008`), partial redemption,
arbitrary executable rules, unapproved cash-payout products and silent legacy conversion.
Arbitrary grace/catch-up choices are not automatically included; enumerate any required
variants in the accepted matrix first. No production date is promised before that scope
and its dependencies are resolved.

### Next implementation boundary after contract approval

The approved detailed matrix is in ADR-0017 under "Builder-v1 compatibility contract".
Keep the release gate disabled; approved disposition does not supply INR publication
or fulfilment evidence. Schema 2 now persists the approved independent policy dimensions
but remains preparation-only. Operational schema-1 required instalments still require
customer-fixed amounts and duration AND count. `build_instalment_windows` still derives count from agreed months;
`get_monthly_eligibility` and full-settlement proofs depend on those frozen contracts.
Changing a form choice alone is therefore insufficient.

Typed compatibility checks and backward-compatible schema-2 persistence now exist.
The 0037 principal foundation records only verified real-source receipts and
evidenced full cash-entry corrections. The 0041 integration adds atomic captured-event
and cash/correction hooks; synthetic future contracts exercise these paths in disposable
tests while actual collection and enrolment remain blocked. The 0038 manual proposal/fulfilment foundation retains pending
refund liability until recorded evidence permits one full closure, without vouchers
or automated provider refunds. The 0039 correction foundation now distinguishes an
unfulfilled void from evidenced full physical return; neither reopens contributions.
Replacement full dispositions retain their retired predecessors and require fresh authorization.
Read-only independent contract resolution and stronger INR snapshot validation are now
shared. Versioned account storage now supports independent duration/count and no-duration
agreements (0040); structural validation still neither grants eligibility nor enables
account creation. The accumulated foundation is checkpointed at `84115be`; its combined
179-test regression rerun passed after the historical-model test correction. Complete
gated schema-2 enrolment/payment integration and follow the eligibility/benefit checklist.
Inspection identified legacy count-from-duration schedule construction as an enrolment
prerequisite. Schema-2 schedule construction, atomic persistence and internal payment
attribution now exist independently. Gated owner-enrolment orchestration uses those
terms/periods atomically. Verified-source INR receipt integration now exists, and new-payment
validation, actual cash entry and required-monthly online creation are integrated behind
readiness gates. Optional online durable order creation/exact recovery now has a
separate obligation-free evidence path (0043). Callback/API-recovery principal now
has distinct immutable API evidence (0044), not fabricated signed capture timing.
Collection/benefit-schedule service-level regression now covers the approved families;
existing-customer requests and separate registration-first applications now retain
frozen independent terms through forms, confirmation, messages and exact approval.
Schema-2 owner instalment/outage review is now integrated behind readiness gates.
Independent eligibility, retained benefits and first metal full-settlement/return
orchestration now exist behind those gates. Next integrate INR final disposition and
benefits, then replacement handling and presentation/reminder/privacy acceptance.
Do not open publication or remove readiness gates as a shortcut to those workflows.
Required regression examples: January 30 short month; final qualifying payment before
period end (count-only versus both); missed payment with retained versus lost unearned
benefit; optional monthly ceiling without any debt; invoice below/equal/above full INR
credit; correction after a benefit is fulfilled; late capture during accepted closure.
Complete only the relevant checkbox with evidence; local persistence and INR primitives
do not complete the builder or permit activation of a future family.

## Plan builder and agreement lifecycle (owner approved 22 October 2026)

Decision: [ADR-0017](decisions/ADR-0017-plan-agreement-governance-and-discontinuation.md).
Expanded scope: owner-configured plans first, customer-authored proposals later;
full-only redemption, including anytime plans. Do not bundle early financial closure
into an unreviewed plan-editor change. The checklist below distinguishes completed
governance from the partially implemented, not-yet-released builder.

### Progress checkpoint — 23 October 2026

**24 October approved extension — FW-PLAN-003/004:** calendar-month required
instalments and separate owner-facing obligation/period/payment-limit/eligibility/
missed-outcome controls. Preserve legacy/anniversary contracts and the release gate.
This is a supported compatibility-matrix expansion, not unrestricted combinations.

- [x] Record short-first-month, enrolment-day, India-midnight and duration-floor decisions in ADR-0017.
- [x] Implement new calendar schedules, period-aligned compensation, consistent preview/forecast/reminder dates, and explicit owner controls (migration 0035; local only).
- [x] Verify calendar cash/online attribution, delayed/boundary captures, reminders, full settlement and immutable migration; review broad regression. 844/845 broad cases passed; the sole logging-disabled runner failure passed in the final 35-test normal-logging/hashing rerun. Clean normal CI is still a release gate; see STATUS.md.
- [ ] Owner/mobile acceptance of calendar terms, short-month disclosure and new controls; CI and exact-image release rehearsal before activation.
- [ ] Remaining builder-v1 families: INR purchase-credit accounting/settlement; count-only or anytime normal eligibility; agreed additional amount/schedule combinations; defined benefit qualification, loss and fulfilment. Follow the release contract above; these are not deferred to an automatic post-subset release.

| Work item | Implemented locally | Still required before completion |
| --- | --- | --- |
| FW-PLAN-003 / P1 | Versioned validated configurations; owner create/reuse and draft plans; customer-selected amount and agreement snapshots; shared payment validation; activation gates (P1a/P1b). | B/P4 owner/mobile review, complete configured enrolment-to-settlement acceptance, CI and exact-image release rehearsal. Not production-ready. |
| FW-PLAN-004 / P2 | Anniversary schedule; exclusive online/cash reservations; payment evidence and corrections; callback/webhook/recovery integration; owner investigation and verified timing; bounded outage amendments; exact lost-order identity recovery; late/duplicate-capture containment and owner provider-exception links; accumulated code/migration checkpoint review; owner-form help-text correction and synthetic desktop/mobile rendering smoke. | Final owner exception-scenario acceptance, CI and exact-image release acceptance. Automated refund/verified refund closure is not supplied by this step. Not complete. |
| FW-PLAN-005 / P3 | Shared monthly eligibility/progress projection; guarded customer payment actions; distinct monthly-completion reminders and locked delivery revalidation; checkpoint correction of owner date-only counts, configured redemption-form access and extension/settlement wording. | Complete B/P4 owner/mobile/email review, CI and exact-image acceptance. Benefits remain NONE; no production activation. |
| FW-PLAN-002 / B1–B3 | Configured closure/payment guards (0031), strict unused cancellation (0032) and full exact-grade jewellery settlement with contained reversal (0033), locally implemented and regression-tested. | Held provider-history disposition, legacy cutover and B4 owner/mobile/release acceptance. Publication/enrolment remains blocked. |
| FW-PLAN-006 / P4 | Controlled audited publication/withdrawal (0034), offer revision confirmation and atomic configured enrolment/schedule integration, locally implemented. | Default-off release gate remains off. Complete owner/mobile/keyboard offer-to-closure acceptance, exceptions, CI and exact-image release rehearsal. |

**Direction:** on track with the approved Django/service/append-only architecture.
Payment attribution and outage protection were already P2 requirements, not unrelated
features. However, the many subdivisions and accumulated uncommitted changes create
delivery/review risk. Use the existing P2b.3b closure checklist below instead of adding
new product scope. A checked local substep does not mean its parent milestone is done.
Validation evidence is recorded in STATUS.md. Migrations 0021–0034 remain local
development work; no release/production acceptance is implied.

**Policy decision received:** the owner delegated the outage allowance/cap choice.
ADR-0017 now selects three separate compensation months, at most one per affected
period, through explicit customer-acknowledged amendments. Continue P2b.3b within the
same fixed acceptance boundary (no new numbered subphase):

1. Preserve original contractual dates/count/amount/grade; implement only the approved
   outage remedy with evidence, customer acknowledgement, duplicate protection and
   safe hold closure. No invented grace, free credit or silent three-month-limit change.
   **Implemented locally:** migration 0028, bounded append-only amendments, owner
   acknowledgement-evidence form, reconciled-state guards, schedule/payment integrity
   checks and customer-visible amended windows. No original snapshot/hash is rewritten.
2. Recover an ambiguous provider order only from conclusive matching provider evidence;
   an empty search or owner assertion is not proof that no order/payment exists.
   **Implemented locally:** migration 0029, durable pre-request UUID/receipt, authenticated
   exact-order lookup and immutable owner binding proof. Recovered checkout stays
   reconciliation-only. No match or a legacy intent without a UUID stays held; no
   replacement, payment credit, deadline change or automatic qualification is created.
3. Reconcile late/duplicate captures without double qualification, lost funds or an
   unsafe replacement order; uncertain cases remain explicitly unresolved.
   **Implemented locally:** same-payment idempotency, different-payment review without
   overwriting the original credit, account-scoped captured-event initiation/timing
   guards, owner provider-reconciliation links and original/replacement isolation.
   Existing in-flight confirmation continues; no automatic refund or manual clear.
4. Run affected/race/full tests and integrity checks; review the accumulated local
   changes as a checkpoint before widening development. Do not claim PR/CI or commit
   acceptance until those actions actually occur.
   **Checkpoint reviewed locally:** no additional financial mutation defect identified
   in the inspected paths. Synthetic rendered-HTML probes found dangling help-text
   references in the three owner exception forms. **Corrected locally:** matching
   help IDs with five database-free regression tests; synthetic Chrome form checks
   at 390x844 and 1440x1000. Technical rendering checks do not replace the remaining
   owner exception-scenario and assistive-technology acceptance. Continue local P3
   development with configured activation still blocked; parent P2 remains incomplete.

Then proceed to P3 eligibility, B full-only settlement/closure and P4 publishable builder
acceptance, in that order. INR purchase-credit/bonus families, anytime variants and
customer-authored configurations remain deferred. New configured plans remain inactive,
unlisted and unenrollable. Existing legacy redemption behaviour is not changed by P1/P2.

### Detailed execution checklist

- [x] Preserve pending deployment documentation and user notes; start a clean feature
  branch (`agent/plan-agreement-governance`).
- [x] **A1 — Offer governance:** locked owner mutation service, reason/audit/revisions,
  stale-edit rejection, read-only admin and explicit visibility/impact explanations.
- [x] **A2 — Agreement provenance:** stable name/code and revision for new enrolments;
  legacy observed-name migration without invented historical consent or financial changes.
- [x] **A3 — Presentation:** recorded agreement/statement terms, calendar-versus-instalment
  explanation, longer-agreement policy wording and current-offer confirmation boundaries.
- [x] **A4a — Local verification:** focused/full tests, actual disposable-database
  migration and concurrency checks. See STATUS.md for evidence and scope.
- [ ] **A4b — Release acceptance:** owner visual review, PR/CI, exact-image rehearsal
  against production's PostgreSQL major version and separate approved release.
  No production mutation in development.
- [x] **Design checkpoint:** define the six policy dimensions, compatibility/publication
  boundaries, full-only settlement and deferred customer proposals in ADR-0017.
- [ ] **P1 — Configuration foundation / customer-fixed amounts (`FW-PLAN-003`):**
  typed server-validated configuration versions, owner create/reuse semantics and
  frozen selected amount at enrolment. Keep legacy behaviour explicit. Start with
  no-benefit metal configurations; do not enable incomplete families. Acceptance:
  supported amounts enforced in every payment channel, incompatible submissions fail,
  version edits never mutate existing plans/agreements, stale offers require confirmation.
  - [x] **P1a — Preparation foundation (local):** typed immutable configuration families,
    owner append/reuse, exact amount previews, audited pinned draft plans and database/
    service activation gates. Existing plans remain unconfigured. Migration 0022.
  - [x] **P1b — Individual agreement integration (local, gated):** pass the customer's confirmed fixed
    amount through every intake/owner approval path, persist configuration and operational
    snapshots, enforce in every payment channel, preserve consent/stale-offer checks and
    update integrity checks/copy. Preview-only terms are not accepted agreements.
    Activation remains blocked until B supplies full-only settlement and closure; do
    not add a DEBUG/environment bypass to offer unfinished contractual terms.
  - [ ] **P1 release acceptance:** after B/P4, rehearse the complete configured offer →
    confirmation → enrolment → both payment channels → full settlement journey. Current
    tests use synthetic configured agreements, not an enabled enrolment path. Migrations
    0021–0023, owner/mobile visual review, CI and exact-image upgrade remain unreleased.
- [ ] **P2 — Instalment obligations (`FW-PLAN-004`):** explicit period/due-window/count,
  grace/catch-up/extension policy, payment attribution and append-only corrections.
  Acceptance: one qualifying obligation credit per verified payment as configured;
  failed attempts, duplicate webhooks and Test payments do not qualify; on-time capture
  is not penalized for delayed delivery; pauses and paid-unallocated cases are explicit.
  - [x] **P2a — Approved schedule foundation (local, gated):** owner approved anniversary
    windows, zero extra grace, no bulk catch-up, three extension months, customer-fixed
    amounts, calendar AND count, no benefits, full-only settlement. Typed definitions,
    immutable period snapshots and read-only on-time/missed scenarios; migration 0024.
  - [ ] **P2b — Payment attribution and exceptions:** reserve anniversary periods across
    channels; independently verified payment-time evidence, one credit per qualifying
    payment/period, duplicate/late/reversal/outage handling and append-only corrections.
    Local confirmation time is not provider capture time. No automatic penalty or
    fabricated attribution, and no new family activation before this is accepted.
    - [x] **P2b.1 — Internal ledger foundation (local, gated):** migration 0025;
      exclusive cross-channel period claims, append-only evidence decisions, idempotent
      cash/captured-event attribution, conservative timing review, cash reversal links
      and read-only integrity check. Payment entry-point integration follows in P2b.2.
    - [x] **P2b.2 — Atomic payment-path integration (local, gated):** reserve before provider order/cash
      mutation; integrate callbacks, signed webhooks, recovery, cash and corrections;
      enforce expiry/resumption/extension rules. Release only after documented provider
      reconciliation; handle late captures without duplicating credits or losing funds.
      Migration 0026 adds durable ORDERING and AWAITING/RELEASED/RELEASED_REVIEW evidence. Actual service
      tests use synthetic agreements; this does not authorize configured enrolment.
    - [ ] **P2b.3 — Exception acceptance:** auditable outage/review resolution, owner UI,
      cross-path races and complete payment regression. A review is not a missed payment.
      - [x] **P2b.3a — Owner investigation and bounded timing resolution (local):**
        migration 0027, append-only owner evidence/reason/reference, private paginated
        workspace, stale/idempotent submissions; only already-verified same-payment
        timing within original boundaries may resolve missing evidence. Outage holds
        stop new initiation without rejecting existing captures or awarding credit.
      - [ ] **P2b.3b — Remaining exception remedies:** outage policy approved and its
        bounded acknowledged remedy/hold closure (0028) and conclusive provider-backed
        ambiguous-order identity recovery (0029) implemented locally; late/duplicate
        capture containment now guards both payment channels and owner timing acceptance.
        Final owner/mobile/checkpoint/CI/release acceptance remains open. No manual
        qualification, grace, refund-completion assertion or release bypass.
- [ ] **P3 — Eligibility and benefits (`FW-PLAN-005`):** policy-specific calendar/count/
  combined evaluation, original versus forecast dates, benefit qualification versus
  fulfilment. Require complete approved numeric benefit terms before publication.
  Acceptance: no forfeiture of paid entitlement; no unearned/duplicate awards; extension
  payments work after the original date; UI/reminders/settlement use the same policy.
  Checkpoint handoff: customer availability/next-action presentation must also respect
  monthly outage holds, occupied/reviewed periods and completed counts, and must not
  declare contributions complete solely at the original calendar date while approved
  extension payments remain due. Preserve legacy agreement behaviour explicitly.
  Local progress (23 October): shared read-only monthly count/date/forecast evaluation
  and customer availability implemented, with original dates retained. Reversal,
  pending timing/order, outage, allocation and exhaustion states remain distinct.
  Configured agreements are separated from legacy redemption buckets; legacy
  original-date reminders are suppressed for them. A distinct monthly-completion
  notice and account-locked delivery revalidation are now implemented locally (0030):
  only count-complete, allocated, review-free upcoming period ends qualify. Forecasts
  never trigger mail. Legacy semantics are preserved; stale monthly dates cannot
  replay historical qualification. Local checkpoint review found and corrected a
  date-only owner Today count and direct access to the legacy redemption form for
  configured agreements. Monthly extension wording and configured calendar status
  now distinguish progress from available settlement. Owner/mobile/email, B integration,
  CI and exact-image acceptance remain required before checking P3 off.
  Continue the B lifecycle sequence, not another policy family.
  No benefit award, configured activation or full-settlement release in this step.
- [ ] **B1 — Closure lifecycle (`FW-PLAN-002`):** explicit request, owner authorization/reason, review,
  withdrawal/rejection, contribution blocking and pending-payment resolution boundaries.
  Implemented locally for configured agreements: migration 0031, customer/owner-assisted
  requests, append-only sequenced review events, one-open/idempotent/stale-decision guards,
  private customer/owner screens and owner queue, read-only admin and integrity command.
  Acceptance blocks initiation/resumption while preserving in-flight capture, allocation
  recovery, corrections and history. Pending intent does not change payment rights.
  Only pending requests can withdraw/reject; accepted requests cannot reopen payments.
  This is not B2 cancellation or B3 settlement and does not change legacy agreements.
  Local validation is recorded in STATUS.md; owner/mobile review and release acceptance
  remain open. B2/B3 are implemented locally below; B4 acceptance remains open.
- [ ] **B2 — Unused cancellation:** prove no financial entitlement/history needing
  settlement, append cancellation evidence, retain login and records; no fake redemption.
  **Implemented locally (0032):** an active owner confirms an accepted configured
  closure with a reason, idempotency key and current sequence. Under the shared account
  lock, reject any contribution (including failed/abandoned/test/reversed), redemption,
  reservation or instalment-review/outage-resolution history. Empty scheduled periods
  are allowed. Append CANCEL and atomically mark request/agreement CANCELLED; no
  payment/redemption/refund, deletion, login change or reopening. Owner/customer UI,
  payment/progress/active-count projections and integrity checks distinguish cancellation
  from redemption. Legacy behaviour and configured activation gates remain unchanged.
  Owner/mobile and release acceptance are still open; local test evidence is in STATUS.md.
- [ ] **B3 — Full-only normal and early settlement:** server-derived full exact-grade
  balance and supported benefit fulfilment, invoice reference, idempotency, concurrent
  payment/webhook handling and controlled reversal. Close the agreement, not the login.
  Inventory existing partial redemptions/contractual promises before cutover; preserve
  history and resolve conflicts without fabricated consent. No partial product option.
  **Implemented and verified locally (0033):** configured-only, exact-metal,
  no-benefit jewellery fulfilment after accepted closure. Owner-bound signed preview,
  full six-decimal balance, invoice, actual customer confirmation, atomic source/event
  records and duplicate/stale guards. Monthly normal eligibility requires payment count
  plus final period end; otherwise supported closure is explicitly EARLY. Reversal
  restores entitlement to CLOSURE_PENDING, not payment collection, and a fresh reviewed
  settlement is possible. Legacy partials/rights are unchanged. Failed/abandoned/Test/mock
  histories and unresolved payment/outage evidence remain held for separate disposition;
  expiry alone cannot clear provider exposure. Publication/enrolment stays blocked.
  28 focused tests passed with normal password hashing; the final 803-test regression
  passed with a test-process fast hasher. Migration preservation and concurrent full
  settlement are covered. This is not owner/mobile, legacy-cutover or release acceptance.
- [ ] **B4 — Acceptance:** customer/owner/statement presentation, financial invariants,
  access/late-capture/race tests, migration rehearsal and disabled-first approved rollout.
  Local automated checkpoint verified: nine focused tests and 201 affected regression
  tests passed. Coverage includes CSRF-protected customer request,
  owner acceptance, unused cancellation and three-of-twelve early full settlement;
  statement/invoice/basis disclosure, correction/replay and customer isolation; late
  duplicate capture retention and identical submission/reversal races. Presentation
  now distinguishes retained terms from permission to continue paying. This does not
  replace real viewport/keyboard/owner review, legacy cutover or exact-image release
  rehearsal, and does not open configured publication/enrolment.
  An isolated, loopback-only synthetic walkthrough helper and owner task protocol
  are available in TESTING.md.
  - [x] Owner confirmed the three local scenarios acceptable on 23 October 2026:
    unused cancellation, three-of-twelve early full redemption/closure, and correction
    restoring entitlement without reopening payments.
  - [ ] Additional explicit viewport/keyboard/print and exception acceptance,
    legacy/provider-history disposition and exact-image release evidence. No device
    coverage or production acceptance is inferred from the three-scenario confirmation.
  This advances local acceptance but does not complete B4 or enable configured plans.
- [ ] **P4 — Owner plan builder (`FW-PLAN-006`):** guided create/reuse, reviewable agreement
  summary and on-time/missed/early-exit scenarios, versioned publish/unpublish and audit.
  Acceptance: only end-to-end supported combinations publish; customer-fixed selection
  is distinct from free rule authoring. Verify Bootstrap/mobile/keyboard/error states.
  - [x] Local controlled publication/enrolment integration: immutable publication revision,
    default-off release flag, audited publish/withdraw, stale-offer protection, frozen
    customer-fixed amount and atomic monthly schedule. Customer copy distinguishes date
    and monthly-completion eligibility. No production activation.
  - [x] Isolated publication-to-closure review helper: two unpublished calendar/monthly
    offers, no pre-created agreement or financial history, process-only release gate,
    existing-customer request/owner enrolment journey and synthetic cash-only settlement.
    The ordinary database/environment stays unchanged; owner acceptance remains below.
  - [ ] Owner/mobile/keyboard review of the complete publication → customer confirmation
    → enrolment → payment → full closure journey; remaining B4 exceptions, CI and
    approved exact-image migration/release rehearsal. Benefits/anytime/legacy cutover stay separate.
- [ ] **P5 — Anytime variants (`FW-PLAN-007`):** separately validate variable-amount
  exact-grade plans with no minimum holding period and full-only closure. No global
  removal of existing minimum-duration constraints, no reusable wallet or cash conversion.
- [ ] **Later — Customer configuration proposals (`FW-PLAN-008`, deferred):** propose
  within the supported catalogue; owner review plus customer confirmation and normal
  enrolment. No agreement or financial effect from proposal submission. Not immediate scope.

Execution order: preserve/review A, P1, P2, P3, B, P4, then P5. Draft UI work may follow
its foundation, but publishing cannot bypass an unfinished settlement/qualification
dependency. No new business numeric grace/benefit/extension defaults are assumed;
incomplete configurations stay draft. New production INR/cash bonus families remain
separately gated. Existing date-based agreements gain no retroactive instalment duties.

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

- [x] Shared expired-attempt queue/count projection and privacy-safe alert counts.
- [x] Owner exact-payment inspect/confirm with bounded signed review and fresh provider check.
- [x] Expiry-aware command with exact selection, bounded inspection and backlog/error alerts.
- [x] Five-minute systemd inspection and combined heartbeat wrapper, without financial writes.
- [ ] Complete isolated release regression/CI/image verification, monitoring account setup,
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

This follows the completed local UI work. Production approval and the explicit
separate-staging exception were subsequently given on 22 October 2026; see STATUS.md.

- [x] Add and execute an opt-in local synthetic dump/restore/upgrade drill. Dependencies:
  loopback PostgreSQL with CREATE DATABASE permission and pg_dump/pg_restore. Acceptance:
  fresh random targets only, existing application database untouched, no external providers,
  historical rows/snapshots/INR and exact-metal liabilities preserved, pending migrations
  applied, legacy access and new coordinated application/activation still work, cleanup verified.
- [x] Prepare the customer/owner task protocol and evidence fields in TESTING.md, with
  release/restore prerequisites in PRODUCTION_DEPLOYMENT.md. No invented business terms,
  support promises, participant results or translations.
- [x] Rehearse the exact CI-published merged image locally on PostgreSQL 18.6,
  matching inspected production: synthetic dump/restore, additive upgrade, historical
  invariants and owner/customer workflows passed on 22 October 2026. Validate the
  prepared proxy with the deployed Caddy digest. This does not close external staging.
- [ ] Confirm the non-production staging target, candidate image/revision and approved
  sanitized backup provenance; rehearse the exact immutable image and proxy on that target.
  Acceptance: scoped feature/configuration review, normal and enhanced browser journeys,
  disabled-JavaScript fallback, log-sink redaction, operational checks and recoverable rollback.
  Deferred to `FW-PROD-009`: owner explicitly accepted the local-rehearsal/controlled
  production alternative for release `4d92b575` on 22 October 2026; not a staging pass.
- [x] Prepare an isolated fictional local usability preview and verify both role logins and
  starting pages. Leave participant observations unaccepted until supplied; keep lifecycle/stop
  details in TESTING.md and the ignored session manifest.
- [x] Local stakeholder acceptance: on 22 October 2026 the owner reported testing both
  owner and customer roles and being satisfied. No task timings or independent participants
  are inferred from that report.
- [ ] Broader prospective/existing customer observations and reviewed Tamil testing remain
  follow-up research. Record completion, help/confusion and wrong turns when actually observed;
  Tamil work requires reviewed terminology and a Tamil-speaking reviewer.
- [x] Obtain separate production deployment/data-change approval for the concrete candidate
  `4d92b57588d0714eb2e9b48661df1878824953d0` (owner approval 22 October 2026).
  After release, measure funnel outcomes using existing aggregate measurement; local tests
  cannot establish conversion uplift.
- [x] Deploy that exact published digest to the approved Linode, apply the three reviewed
  migrations, preserve financial snapshots, verify health/access/static/redaction/integrity,
  and remove the temporary submission guard. Optional measurement remains disabled;
  subsequent owner/customer production visual acceptance is still a follow-up.

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
  Local 24 October simplification: concise customer request pages with expandable
  retention details; shared owner retention terms with per-category exceptions and
  expandable reference tables. Existing category decisions and financial safeguards remain.
- [ ] `FW-PROD-007` — Budget-conscious security-log preservation (inventory/plan documented; measured sizing, archive implementation and recovery acceptance pending)

- [ ] `FW-MOBILE-001` — Mobile product, policy, account, and release readiness
- [x] `FW-MOBILE-002` — Network-safe installable PWA foundation
- [ ] `FW-MOBILE-003` — Customer-only Android Trusted Web Activity
- [ ] `FW-MOBILE-004` — Play internal-test and controlled customer pilot
- [ ] `FW-MOBILE-005` — Evidence-based native Android/iOS and API decision

Milestones are vertical increments. Each must leave migrations, tests, system checks, user flows, and canonical documentation coherent before the next begins.

Known limitations and their acceptance targets are tracked in [Future work](FUTURE_WORK.md).
