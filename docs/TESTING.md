# Testing

## Independent owner review and outage amendments (26 October 2026; no migration)

`test_independent_instalment_reviews` covers COUNT, duration-AND-count and benefit-only
duration schedules, each in INR/exact-metal and calendar/anniversary variants. The
12 amendment combinations preserve account snapshots, original periods and financial
records while appending one acknowledged future period after only the applicable
ordinary replacements. Tests retain the separate three-period cap, reject duplicate
affected periods, completed counts, stale proposals, invalid acknowledgement and
already-started windows. Benefit-only compensation cannot override a disallowed
post-duration contribution boundary or move principal maturity.

Actual cash/online service tests verify current-rate compensation payments, separate
INR principal, signed-timing acceptance without double credit, missing/conflicting
timing and unresolved webhook containment, current-window restoration, principal
source-drift refusal and atomic rollback of amendment insertion. Concurrent retries
produce one amendment; a simultaneous INR cash receipt is serialized against hold
resolution. Owner UI renders required count rather than duration, retains authorization,
CSRF and no-store checks, and describes zero ordinary replacements for benefit-only
schedules. Existing form-label/help/error accessibility tests also pass.

The combined independent entry/ledger/review, legacy review/outage and calendar run
passed **80 tests in 287.759s**. The final focused independent-review and form-accessibility
run passed **19 tests in 62.422s**, including the new duration cutoff, completed-count,
release-gate and cash-race cases. Unique disposable localhost PostgreSQL databases
were destroyed afterward; no global fast-hasher override was added. Django checks,
migration consistency and whitespace checks pass. Schema-2 review mutations remain
rejected with the release flag either off or on; only future-path tests mock readiness.
No normal-database migration, deployment, benefit award or activation occurred. This
is not full normal CI, eligibility implementation or complete lifecycle acceptance.

## Independent registration-first applications (accounts 0009, 26 October 2026)

`accounts.test_independent_applications` exercises all five approved families in
both denominations through contact, verification, completion and atomic identity/
agreement approval. It covers frozen revisions and confirmation history, no-duration
preferences, plan-fixed amounts, strict owner attestations, stale offers/consent,
changed-denomination reconfirmation, expired private grants, disabled updates,
tampered provenance, audit rollback and concurrent/idempotent approval. A browser
journey verifies forms, owner review and invitation delivery; the progress email
retains independent terms with link/open tracking disabled. Contact/verification/
completion never create an agreement, contribution, principal receipt or allocation.
Migration tests preserve legacy rows/JSON, refuse invented independent consent and
refuse reversal over schema-2 evidence. Readiness mocks are confined to future-path
fixtures; unpatched gates still reject schema 2 with the release flag off and on.

The combined registration-first, legacy application, public registration, activation
continuation and independent-request run passed **103 tests in 111.077s**. The final
**15-test focused rerun passed in 38.138s**, including the additional offer-change
and forward-migration guards. Unique disposable localhost PostgreSQL databases were
destroyed after testing. New tests use normal hashing; older modules retain their
own overrides. Django checks/migration consistency pass. No normal-database migration,
production change or activation; full normal CI and visual/mobile acceptance remain
release requirements. An initial browser fixture incorrectly expected the plan entry
redirect to render a form; it was corrected to exercise the actual registration URL.

## Independent existing-customer requests (0045, 26 October 2026)

`test_independent_requests` exercises the five accepted families with both exact-metal
and INR denomination through non-financial submission and exact owner conversion.
It covers separate duration/count, signed stale-offer/disclosure rejection, exact
confirmation and owner authority, snapshot substitution, null-grade pending uniqueness,
idempotent retries, concurrent submission/conversion, audit-failure rollback (including
the final conversion audit), frozen text/HTML email facts and escaping, and a browser
request/review/approval/email journey. The migrated legacy row round-trips unchanged;
forward migration refuses unversioned schema-2 requests and reversal refuses to erase
new confirmed evidence. Readiness is mocked only in synthetic future-path fixtures;
unpatched gate tests still reject schema 2 with the release flag off and on.

The combined request, existing request, independent owner-enrolment, publication,
plan-governance, configured-agreement and owner-workspace suites passed **111 tests
in 176.352s**. The final **16-test focused rerun passed in 56.571s**, covering explicit
non-null row-lock preservation and the added forward-guard regression. Tests ran in unique disposable
localhost PostgreSQL databases. Existing test modules retain their own hasher overrides;
no global fast-hasher override was introduced. Django checks/migration consistency
and whitespace checks pass. This is not full normal CI, visual/mobile acceptance,
registration-first PlanApplication integration or permission to activate the builder.
No normal-database migration or production mutation was performed.

## Independent collection matrix (26 October 2026; no migration)

`test_collection_matrix` adds eight tests. Its 120 first-payment subcases span all
five approved rule families, both principal denominations (22K exact-metal fixture
and INR purchase credit), permitted fixed/variable amount policies, flexible or
calendar/anniversary ceilings, and actual cash/online creation services. Optional
ceilings create no obligations; required schedules retain their independent count.
Additional cases exercise INR bonus/VA terms without awarding benefits, missing a
benefit-only month without extending maturity, count replacement windows, full cash
correction and retained history, duplicate capture delivery, and delayed delivery
across India-local boundaries. The last whole provider second remains ambiguous and
requires review; paid principal is preserved even when timing cannot qualify.

Fixtures simulate readiness and provider responses, not principal/attribution writes.
Webhook cases enter the post-authentication service; signature validation is covered
separately by adapter/view tests. Unpatched readiness tests reject every family with
the release flag both off and on. Benefit percentages/caps here are synthetic test
parameters, not published business promises. No runtime guards were changed.

The combined run of `test_collection_matrix`, `test_independent_payment_entry`,
`test_independent_instalment_ledger`, `test_independent_enrolment` and
`test_inr_api_payments` passed all **70 tests in 231.179s**, including concurrency
and migration cases, with normal hashing and a unique disposable localhost PostgreSQL
database, subsequently destroyed. Initial fixture mistakes used a nonexistent snapshot
attribute and moved the clock backwards after recording future payments; both were
corrected. A subsequent eight-test run (110.731s) passed the 120-case matrix but failed
two boundary expectations that incorrectly treated last-second provider precision as
conclusive. Corrected tests explicitly retain that review safeguard; the final combined
run is clean. Django checks, migration consistency and whitespace checks also passed.
This is a local collection checkpoint, not full normal CI, benefit lifecycle acceptance
or permission to activate configured plans. No normal database migration was run.

## INR callback/API capture evidence (0044, 26 October 2026)

`test_inr_api_payments` exercises the real HMAC/API adapter with synthetic responses:
exact Live payment/order/amount/currency/captured matching; malformed or uncaptured
responses; provider failure; callback/webhook ordering; concurrent deliveries;
owner preview/fresh apply; cross-linked events; verified sources missing principal;
interrupted confirmation/evidence/principal/schedule writes; immutable/database
source shapes; evidence drift; source-first refund proof; late-disposition holds;
runtime rejection with either release flag; and empty migration roundtrip/retained
evidence reversal refusal. API observation alone must leave monthly timing awaiting;
original signed timing can qualify it or require review without erasing principal.
No browser fields, provider creation timestamp or owner checkbox can qualify timing.

Protocol reference: [Razorpay Fetch a Payment](https://razorpay.com/docs/api/payments/fetch-with-id/).
Only minimal capture identity/state is retained, not the full response containing
contact or instrument data. Tests use no real provider calls. Fixtures were corrected
for cached relations, capture/receipt chronology and bound model-default clocks;
financial timing checks were not relaxed. Actual optional/required order entry and
capture during a new-payment pause are covered. The 23-test focused suite passed
(103.439s), followed by the final 34-test focused/adapter rerun (100.303s).

Combined financial regression: 292 tests (932.275s), 290 passes and two test-harness
errors. The new full-disposition test needed its model-default clock aligned; it
passed in the focused reruns. The existing principal rollback test needed to restore
the migration leaf before current-model reads, because an expected earlier refusal
can follow reversal of empty later migrations. All four principal migration/concurrency
tests passed after that correction (89.865s). Suites overlap; do not report the combined
run as clean or add their counts together. No full normal CI or activation acceptance
is claimed. Django checks, migration consistency and whitespace checks passed.
All test databases were disposable localhost PostgreSQL and were destroyed.

## Optional independent online order evidence (0043, 26 October 2026)

`test_optional_orders` exercises actual creation/resumption and exact recovery on
synthetic optional contracts, simulating only runtime readiness and provider I/O.
Cover INR/exact-grade separation; no artificial periods/reservations; period-capped
deadlines; fixed amount/rate on resume; concurrent starts; timeout/provider/local-write
failure; malformed/duplicate order responses; exact UUID/receipt/amount/currency/time
recovery; owner and Live-mode checks; stale evidence; pause/expiry/containment during
I/O; reconciliation-only recovered checkout; evidenced abandonment before replacement;
captured principal idempotency; model/database evidence guards and reverse-migration
refusal. Outer application transactions must refuse provider I/O before sending an
order. Diagnostic checks distinguish uncertain/unstarted attempts from integrity errors.
An untracked FAILED source cannot authorize another payment merely by its status.

The existing 19 entry tests passed (101.623s); after fixture corrections the expanded
19-case optional suite passed (87.814s). The final 39-test optional/entry suite,
including the added untracked-source guard, passed (186.933s). All 269 combined
financial regression tests passed (916.401s). Suites overlap, not 308 unique tests;
the final 39-case rerun covers the last added admission guard. Django checks,
migration consistency and whitespace checks passed. Disposable localhost PostgreSQL
databases were destroyed; no normal database was migrated. Full normal CI,
owner/customer acceptance and exact-image release rehearsal remain separate gates.

## Independent payment admission/entry (0042, 25 October 2026)

`test_independent_payment_entry` exercises actual cash preview/record/correction and
required-monthly online creation/resumption/capture on synthetic accepted contracts.
Only runtime readiness is simulated; normal paths must reject schema 2 with either
release-flag value. Cover both denominations, exact units, amount/step bounds, frozen
snapshot drift, no backdating, duration/count separation, optional short-calendar and
original-anniversary boundaries, explicit anytime continued payments, server receipt
time versus insertion time, principal failure rollback, duplicate submissions and
concurrent optional ceiling enforcement. INR must respect global/kill/schedule controls
without needing a metal rate. Mock/Test sources and optional independent online
creation remain rejected. Run existing payment operations, contribution, instalment,
INR source integration, cash and Razorpay regressions. Focused runs exposed a stale
related-object assertion and an invalid February fixture date; both were corrected.
All 249 combined entry/principal/settlement/correction/instalment/Razorpay/cash/
operations/contribution/storage tests passed (553.975s). The additional missing
principal/allocation admission test passed separately (1 test, 2.254s), covering
all 19 new entry tests across these runs. Django checks, migration consistency and
whitespace checks passed. Disposable localhost PostgreSQL only; no normal database
migration, CI claim or release activation. Optional online and callback/API-recovery
acceptance remain explicitly outstanding.

## INR verified-source integration (0041, 25 October 2026)

`test_inr_payment_integration` covers processed Live source-to-principal integration,
optional/required schedules, truthful system provenance, same/different-event retries,
concurrent consumers, body/amount/mode mismatch rejection, late timing with retained
principal, and atomic rollback of confirmation/credit/qualification. Cash tests cover
owner receipt linkage, full source-correction service integration and rollback of
source/instalment reversal if the principal correction fails. Database constraints
reject unattributed cash and wrong system labels. Empty 0041 reversal/reapply works;
retained system principal refuses reversal before schema changes. Test-only clocks
must include bound model defaults, not only timezone.now calls. Runtime collection
gates remain closed and INR API recovery explicitly requires review.

Verification: after correcting the focused fixture clock mismatch, the initial
68-test regression passed (146.676s). A fresh combined run passed all 200 tests
(368.179s), including the 12 integration tests, principal, settlement/correction,
independent ledger, legacy instalment, order recovery, Razorpay and in-store cash
modules. Suites overlap; disposable localhost PostgreSQL databases were destroyed.
Django checks, migration consistency and whitespace checks passed. No normal local
or production migration was performed; this is not normal CI or activation acceptance.

## Gated independent owner enrolment (25 October 2026)

`test_independent_enrolment` exercises the existing owner service with synthetic
published offers and test-only simulation of the two operational-readiness lookups.
Do not patch model save/validation, publication evidence, release gate, transaction,
snapshot or audit services in successful-path tests. Separately verify unpatched
runtime rejects every new denomination with either release-flag value. The matrix
covers exact metal/INR, calendar/anniversary, count-only and independent count/duration,
optional anytime, fixed benefit-only schedule without extension, null maturity,
variable preference, and no principal/allocation/payment created by enrolment.
Assert current digest/configuration/boolean consent, owner authority, exact duration,
denomination, pinned publication revision, and rollback of account plus periods on
schedule/audit failure. Existing legacy/configured/publication/governance and customer
enrolment-request regressions must remain green. No production gate is patched.

Verification: after correcting the synthetic publication fixture to respect the
active-offer/revision database constraint, all ten focused tests passed (5.403s).
All 98 combined independent enrolment, configured agreements, publication, governance,
enrolment requests, independent storage and ledger tests then passed (132.966s).
These suites overlap; disposable localhost PostgreSQL databases were destroyed.
Django checks, migration consistency and whitespace checks passed; no new migration
is needed. This is not public schema-2 form/request/email
or payment-flow acceptance, and is not normal CI or permission to activate.

## Independent schedule persistence and attribution (25 October 2026)

`test_independent_instalment_ledger` uses synthetic version-2 accounts and upstream
source records only in disposable local PostgreSQL. Check metal/INR and both period
bases, count separate from duration, exact idempotent schedule reads, concurrent
initial preparation, atomic insertion rollback, pinned-revision independence, owner
permissions, no optional obligations/backfill/non-active initial preparation, and
refusal of corrupted schedules. Verify source-bound cash and processed-live-capture
attribution, delayed receipt versus original evidenced payment time, deadline review,
duplicate delivery, body-integrity refusal, Test exclusion, full cash correction and
replacement count capacity. Attribution must not create principal/allocations or
change agreement status. Normal payment/model gates remain closed with either flag
value. All owner-review actions and outage-resolution outcomes refuse schema 2 without
adding decisions or periods; those services require separate integration.

Run alongside independent schedule/storage/terms, existing payment/integration,
calendar/anniversary schedule, owner-review and outage suites. The initial 85-test
run passed 84 with one invalid February-date test fixture. After correction and the
additional owner-review/outage guard test, all 86 schedule/storage/terms/payment
regressions passed in 192.320s. The separate 42-test ledger/review/outage suite passed
in 116.031s. These suites overlap; do not add them as distinct tests. Both unique
disposable localhost PostgreSQL databases were destroyed. Django checks, migration
consistency and whitespace checks passed. No new
migration is needed. This is not full normal CI or owner-builder activation acceptance.

## Independent schedule construction (24 October 2026)

`test_independent_agreement_schedules` covers the metal/INR, plan-fixed/customer-fixed,
calendar/anniversary and count/both matrix using ten required periods independently
of an eighteen-month duration. Assert exactly three ordinary replacements, no
replacements for duration-only benefit schedules, and no obligations for optional
ceilings. Check the short first calendar month, India-midnight half-open boundaries,
leap-year original-anchor clamping, finite fixed amounts, invalid dates/overflow and
the required-count bound plus its three replacements (32770 total periods fit the
existing PositiveInteger period-number field). The resolver is read-only and its result is
immutable; account/period/payment/principal/allocation/audit records remain unchanged.
Existing runtime gates reject schema 2 with either release-flag value. The shared
timestamp mapping does not itself verify a provider timestamp or qualify an instalment.

Verification: all 17 schedule/contract tests passed in 7.442s on a unique disposable
localhost PostgreSQL database, subsequently destroyed. Separate combined checkpoint
regression passed all 179 tests in 708.807s, including the corrected historical reminder
migration test; its disposable database was destroyed. The suites overlap, so do not
add their counts as unique tests. Django checks, migration consistency and whitespace
checks passed. No normal database migration or real
payment occurred; this is not full builder or normal CI acceptance.

## Independent agreement storage (0040, 24 October 2026)

`schemes.tests.test_independent_agreement_storage` exercises synthetic persisted
contracts for both denominations: duration, count-only, both, anytime and required
schedule solely for a defined benefit. Verify independent duration/count, no fabricated
date, short duration, calendar/anniversary ceilings, pinned-policy drift detection,
immutability and SQL shape constraints. Legacy rows must retain all values through
migration roundtrip and reject short/null durations and new frequency semantics.
Forward migration refuses unversioned schema-2 rows; rollback refuses even an unused
independent agreement or a forged legacy storage tag on a schema-2 policy.
Explicitly test that payment availability, model writes and old monthly evaluation
stay blocked for v2, even with the release flag enabled. As of 25 October, expected
required schedules can be read; optional ceilings still refuse required-period construction.

Existing INR migration tests now assert the earlier 0040 chain refusal and also invoke
the original 0037/0038/0039 preservation guards directly, retaining their coverage.
An older empty-settlement/correction roundtrip over a version-2 agreement is no longer
permitted; tests assert preserved evidence and refusal instead. Run the INR suites,
schema-1 configured agreements, monthly eligibility/reminders, calendar/anniversary
schedules, liability and policy-persistence regression suites together. Use unique
disposable local PostgreSQL only; synthetic account insertion is not a runtime bypass.

Verification: the combined 179-test run finished in 794.761s with 178 passing and one
error in the existing monthly-reminder migration test: it queried the runtime account
model while the database was at 0029. That test now uses historical migration-state
models on both sides of 0030. A focused rerun of that test plus all seven independent
storage tests passed (8 tests, 58.183s). The broad run had already loaded the old test;
the full combined suite was not rerun after the test-only correction. Earlier runs
also exposed a missing seeded MetalGrade after TransactionTestCase flush; the synthetic
fixture now creates its own exact grade. No production constraint was relaxed.
Django checks, migration consistency and whitespace checks passed. These overlapping
runs used unique disposable localhost databases, which were destroyed afterwards;
they are not a claim of full builder acceptance or clean normal CI.

## Independent agreement-term integration (24 October 2026)

`schemes.tests.test_independent_agreement_terms` covers read-only resolution across
metal/INR, fixed/customer-fixed/variable amounts and flexible/calendar/anniversary
limits. Duration and count remain independent; count-only/anytime have no fabricated
duration floor. Cover month-end clamping, date overflow, invalid amounts/grades,
immutable resolved terms, no implicit benefits, unchanged records and release gates.
Frozen account checks cover current-plan/new-version independence, cached-object and
persisted evidence drift, amount/frequency/date mismatches, atomic rejection before
principal recording, and matching read-only diagnostics. Synthetic INR fixtures now
include the exact pinned maximum amount, not an incomplete snapshot. They remain
disposable-test fixtures, not a runtime enrolment bypass.

Run alongside `test_inr_principal`, `test_inr_settlements`, `test_inr_corrections`,
`test_configured_agreements` and `test_independent_policy_fields`. All use unique
disposable localhost PostgreSQL databases with normal hashing/logging. This does
not replace the remaining full builder acceptance matrix or production rehearsal.

Verification: all 105 tests across those six modules passed in 274.002s after fixing
the new plan-fixed fixture's min/max/fixed shape. The initial run's six failing
subcases were fixture errors; no database constraint was relaxed. Django checks,
migration consistency and scoped whitespace checks passed. Databases were destroyed.

## Controlled INR disposition corrections (24 October 2026)

`schemes.tests.test_inr_corrections` covers unfulfilled voids, pending and completed
full-return resolutions, exact restoration of principal, no top-up credit, mixed
cash/live source retention, repeated full replacement, fresh authorization/previews,
atomic rollback, duplicate/concurrent requests, owner permissions, timestamp/IST
normalization, immutable history, projection/source tampering, SQL finite-value and
single-current/root constraints, migration roundtrip and reversal-history refusal.
Also verify that restored principal does not reset the original provider refund cap.
All fixtures are synthetic future contracts in disposable localhost PostgreSQL; no
normal enrolment bypass, real refund or production mutation. Partial/staged returns
are deliberately rejected. A fresh corrected invoice/transaction reference is needed
for replacement; old fulfilments/completions remain historical evidence.

Verification: 174 cross-workflow tests passed in 587.309s, including timestamp,
atomicity, repeated-return, closure, liability, policy and privacy completion cases.
After the final provider-cap safeguard, 46 focused correction/settlement tests passed
in 166.628s; an additional cumulative-cap/exact-boundary test passed in 11.957s.
Earlier 19-case (91.935s) and 43-case (142.631s) runs also passed. These suites overlap;
do not sum them as distinct tests. All used normal hashing/logging and destroyed their
unique disposable databases. Django checks, migration consistency and scoped whitespace
checks passed. Normal CI and full builder release acceptance remain open.

## Manual INR final-disposition foundation (24 October 2026)

`schemes.tests.test_inr_settlements` uses synthetic future contracts/accepted closures
in disposable localhost PostgreSQL, never a runtime enrolment bypass or real provider
payment. Cover invoice below/equal/above principal, all-refund closure, source-specific
cash/live refunds, pending liability after either leg, external top-ups, full completion,
unchanged contribution/metal/legacy-redemption records, signed-preview staleness/expiry,
owner/customer boundaries, evidence reuse, duplicate/concurrent requests, finite Decimal
SQL constraints, late/source-drift holds and migration-history preservation. Runtime
schema-2 creation remains gated. The 135-case broader regression passed in 563.311s;
the final 48-case settlement/contribution/cash run passed in 121.892s. These overlapping
suites used normal hashing/logging and unique disposable PostgreSQL databases,
destroyed afterwards. Django checks, migration consistency and scoped whitespace
checks passed. Normal CI and complete release acceptance remain open; see STATUS.md
for the initial fixture corrections and the exact implementation boundary.

## INR principal foundation (24 October 2026)

`schemes.tests.test_inr_principal` tests real-source-only receipts, source/contract
matching, immutable amounts, replay/conflict handling, reloaded owner permissions,
source drift and missing credits, separate liabilities, append-only full cash-entry
corrections, SQL constraints (including NaN), concurrent receipts/corrections, ordinary
workflow refusal even with the release flag enabled, no false settlement on late funds,
full principal invoice/refund/top-up arithmetic, and preservation/reversal guards.
The initial 19-case run passed in 34.124s. The broader 145-case regression passed in
492.196s; 65 Razorpay/policy tests passed in 80.086s; the final 41-case principal and
deletion-completion run passed in 78.744s. These suites overlap and are not a full-CI
run. They used disposable localhost PostgreSQL databases with normal logging/hashing,
destroyed afterwards. Django checks and migration consistency passed; ordinary
local/production data was not used or migrated by these tests.

Tests explicitly bulk-create synthetic future contracts in a disposable localhost
PostgreSQL database: the normal agreement service/model save intentionally cannot
enrol schema-2 contracts yet. Sources are synthetic retained payment evidence, not real
provider charges/refunds. Test fixture creation is not a runtime bypass or deployment
instruction. Source-correction fixtures likewise simulate completed upstream evidence;
the new service records it but does not perform or verify a physical refund.
Regression must cover existing contributions, cash receipts, instalment capture,
liability reporting, configured settlements/closure and the older migration chain.

## Independent policy persistence (24 October 2026)

`schemes.tests.test_independent_policy_fields` covers schema-2 family round trips,
independent duration/count, Decimal benefit parameters, owner-only preparation,
append-only versioning/no schema downgrade, invalid/null/NaN SQL bypasses, legacy
form required fields/forged dimensions, correct read-only owner presentation and
runtime refusal even with the release flag on. Migration tests verify exact preservation
of schema-1 rows/evidence and refusal to reverse 0036 with schema-2 contracts present.
Configuration creation produces no plan, agreement, contribution or allocation.
Run alongside configuration/publication/agreement/settlement/calendar/eligibility/
schedule/manual regressions on disposable localhost PostgreSQL, preserving normal
logging and hashing. No ordinary database migration or production write is required.

Evidence: 159 cases across eleven affected modules ran in 486.383s; 158 passed and
one historical migration fixture errored because it used the current serializer on
a pre-0036 model lacking `policy_schema_version`. The fixture now uses a frozen 0023
calendar-evidence serializer while historical, and compares the current serializer
after upgrading to the latest schema. The final 24-case rerun (independent fields,
typed policies and the corrected migration chain) passed in 38.291s, also covering
the final read-only template. Both temporary databases were destroyed. Django checks,
migration consistency and scoped whitespace passed. This is affected regression and
corrected-test evidence, not a clean full-suite/CI run or production acceptance.

## Builder-v1 typed compatibility foundation (24 October 2026)

`schemes.tests.test_plan_policies` validates the approved optional/required, amount,
denomination, calendar/anniversary, duration/count/both/anytime combinations; named
benefit parameters and strict Decimal inputs; rejected contradictory policies; immutable
objects; unchanged historical evidence; and operational blockers with the release flag
both on and off. The 11 tests use SimpleTestCase: no database or financial mutations.
Manual refund fulfilment and external INR approval remain publication blockers after
the remainder-policy decision. Design-valid policies
are not a claim of implemented financial workflows or legal/provider approval.

Regression must include configuration creation/reuse, configured agreements, calendar
instalments, publication/enrolment, configured settlement, monthly eligibility and
instalment schedules on disposable localhost PostgreSQL. Do not migrate the ordinary
database or enable future families for a validation-only change. This step adds no
database migration and does not change immutable serialized revision evidence.

Evidence: the combined eight-module affected run passed **136 tests in 362.111s**,
using normal logging/hashing configuration and a uniquely named disposable localhost
PostgreSQL database, destroyed after the run. An initial test-runner setup overwrote
Django's TEST defaults and failed on missing MIRROR before creating a database;
preserving those defaults and changing only NAME corrected the runner. Django system
checks, makemigrations --check --dry-run and scoped whitespace checks passed. No new
migration, ordinary database changes or production activation; full CI remains required.

## Calendar-month compulsory instalments (24 October 2026)

`schemes.tests.test_calendar_instalments` covers the short enrolment month, Jan 30/31,
leap-day/year-end boundaries, enrolment-day cash qualification, cross-channel timing,
late-delivered versus month-crossing provider evidence, minimum-duration forecasts,
completion reminders, normal versus early full settlement, calendar-aligned outage
compensation, explicit owner controls, publication/enrolment and immutable 0035 upgrade.
All provider activity is synthetic; no production funds, SMTP or ordinary database
migrations are involved. Existing anniversary regression remains required.

Evidence: 844 of 845 broad schemes/accounts/pages cases passed (657.641 seconds,
process-only MD5 hasher). The only failure was the funnel warning-log assertion,
caused by globally disabling logging in that test invocation, not an application
change. Final calendar/funnel/manual/accessibility verification passed all 35 tests
in 32.026 seconds with normal logging and password hashing. System, migration-
consistency and whitespace checks passed. Run normal CI before release; do not
record the earlier broad invocation as an entirely green run.

Owner acceptance must review a 30 January / twelve-month calendar configuration:
first window ends before 1 February, twelve original payments finish by December,
but normal completion waits until 30 January next year. One missed original month
replaced in January moves normal completion to 1 February. Inspect the separate
controls and the short-month disclosure on mobile and customer offers before release.

## Illustrated owner learning guide

[Plan configuration — illustrated owner guide](guides/plan-configuration/index.html)
is the browser-readable, print-styled handbook for the current local P4 builder.
It covers the actual field labels, supported recipes, read-only previews, publication,
individual enrolment, monthly timing, versioning and unused/funded full closure.
Its four screenshots use the isolated synthetic review, not production customer data.
Keep its adjacent `assets` folder when copying it. This is training documentation,
not owner acceptance or permission to enable `CONFIGURED_PLANS_ENABLED` in production.
The executable review protocol and evidence remain below.

The same source is also served at `/scheme/owner/plan-manual/`, reachable through
**Plan reference manual** on the owner Scheme plans/catalogue/detail screens.
Only active owners/superusers can read its HTML or allowlisted JPEG illustrations.
Reading is available with `CONFIGURED_PLANS_ENABLED=False` and does not activate intake.
The endpoint is GET/HEAD-only, private/no-store and noindex; it does not expose arbitrary
repository documents or public static copies. The image build includes only the manual
and four explicitly allowlisted illustrations from `docs/`.

`schemes.tests.test_plan_manual` runs without database access and covers role boundaries,
anonymous redirects, inactive users, safe methods, all asset signatures/headers,
traversal/unknown-file rejection, intact anchors/authenticated links and both gate states.
Together with existing owner-form accessibility tests, 15 tests passed in 0.339 seconds;
Django checks passed. On the next planned review-server restart/release rehearsal,
verify the navigation, authenticated image loading, mobile/print layout and anonymous/
customer rejection in the browser/exact image. Do not restart a user's unfinished
synthetic journey merely to load this documentation route.

## P4 controlled publication and enrolment (23 October 2026)

`schemes.tests.test_plan_publication` exercises owner-only, CSRF-protected audited
publication/withdrawal, the default-off release gate, stale offer forms and confirmations,
immutable revision provenance, confirmed individual amounts, atomic monthly schedules,
customer registration/application approval, existing-customer request conversion,
publication/withdrawal races and cash/simulated-live-provider full-settlement journeys.
The journey fixture replaces synthetic account insertion with the actual publication
and enrolment services. Provider calls remain fake; no real payment/email is sent.
The migration rehearsal verifies 0034 leaves legacy terms, accounts and contributions
unchanged. The integrity command rejects agreements referencing unpublished draft terms.

Evidence: initial 14 focused tests passed (22.912 seconds). After correcting the
draft-agreement diagnostic, a 797-test schemes/accounts/pages run had four migration-
fixture errors, not application assertion failures. Current-model factory setup now
precedes historical-schema downgrade, and checkout-expiry fixtures reuse the seeded
grade with denomination/fineness assertions. All 20 P4 tests plus those four fixtures,
the configuration/publication upgrade and draft-agreement diagnostic passed together:
26 tests, 183.184 seconds. The broad run used a process-only fast hasher; the final run
used normal defaults apart from existing application-fixture overrides. Full clean CI
remains required; do not describe the 797-test run as passed.

Subsequent clean checkpoint: the complete Django discovery run passed **839 tests in
725.719 seconds** on a new disposable localhost PostgreSQL database, with a process-only
fast password hasher. This includes the corrected migration fixtures and new walkthrough
tests. It does not establish hosted CI/container/production acceptance. A later
reporting-only change replaces hard-coded activation-disabled labels in the closure
and instalment checks with the actual `configured_intake_enabled` flag; targeted
on/off reporting and walkthrough tests verified that correction separately: eight
tests passed with normal hashing in 13.779 seconds. No financial logic changed after
the 839-test run. Django system, migration-consistency and whitespace checks passed.

Owner acceptance still required: review a calendar and a monthly offer on mobile and
keyboard; publish in an isolated test environment; submit/confirm/approve a customer
application; verify the exact fixed amount and schedule; withdraw/edit/republish and
verify old agreements unchanged; complete unused cancellation and funded full closure.
Disabling the release gate must hide new offers without disabling existing payments or
settlement. This is not permission to enable the ordinary local or production environment.

### Isolated P4 publication-to-closure walkthrough

Use the existing review helper's separate P4 mode:

```powershell
uv --cache-dir .uv-cache run --no-sync --env-file .env python -m schemes.review_closure_locally --synthetic-local --publication-journey
```

This creates a fresh random `jsk_p4_review_*` localhost database and enables configured
offers/enrolment requests **only in that review process**. It does not edit `.env`,
migrate the ordinary database, publish production offers or enable online payments.
It starts on `http://127.0.0.1:8767/accounts/login/`, separate from B4's port/cookies.
The printed owner/customer credentials are temporary synthetic identities. Both start
with working passwords; public identity verification/email delivery is not simulated
in this browser review (its service regression coverage is described above).

Seeded state: one calendar-only and one monthly-completion draft, GOLD_22K_916,
customer-fixed amount bounded INR 500–10,000 in steps of INR 100, and a clearly
synthetic INR 10,000/g rate for today. No agreement, enrolment request, contribution,
allocation or redemption is seeded. Both configurations have no benefits and full-only
settlement. Browser/static/CDN access and server isolation/cleanup follow the B4 rules
below; emails stay in process memory and no external SMTP or payment API is available.

Review in this order, using separate browser profiles/private windows for the two roles:

1. **Owner:** open the printed monthly publication link. Review its policy and publish
   with confirmation/reason. Also review the calendar draft; its eligibility must be
   date-based, not dependent on twelve paid instalments.
2. **Customer:** open Savings Plans, choose the published monthly offer, select INR
   1,000 and 12 months, confirm its disclosures and submit. Submission must create
   only a request, with no agreement or payment yet.
3. **Owner:** open the printed request queue and approve/enrol with today's start date,
   the customer's confirmed amount/duration and an audit reason. Inspect the accepted
   agreement: fixed INR 1,000, GOLD_22K_916, twelve required anniversary instalments
   and at most three ordinary extension periods. No money or metal is created yet.
4. **Owner:** record one **synthetic** showroom-cash contribution of INR 1,000 using
   the seeded current-day rate. Expect 0.100000 g internally (0.100 g customer display).
   Do not use real money or customer information. If reviewing on a later date,
   restart this disposable review or explicitly publish a new synthetic current-day rate.
5. **Customer:** request closure. **Owner:** accept, inspect the EARLY/full quantity
   preview and simulate fulfilment with `DEMO-P4-INVOICE` / `DEMO-P4-FULFILMENT`.
   Expect the entire 0.100000 g settled, agreement REDEEMED, zero remaining entitlement,
   no maturity benefit, and the customer login intact. These consent/fulfilment
   confirmations may be simulated only in this disposable review.
6. Review withdrawal/edit/republish: old agreement snapshots and settlement evidence
   must remain unchanged; new customer submissions must see the new offer revision.
   Use a second enrolled-but-never-funded agreement for unused cancellation if desired.

Inspect desktop and 390px responsive layout, Tab/focus/form errors and statement print
preview. Record results rather than inferring viewport/accessibility acceptance from
automated tests. An actual browser close/reopen, stale form or rejected owner action
must not create duplicate records. Provider exceptions, production activation and
exact-image CI/release acceptance remain separate gates.

Append `--check-only` to migrate, seed, check role boundaries/integrity and clean up
without serving. That check deliberately leaves offers unpublished; automated helper
tests separately exercise both seeded offers through actual publication, request,
enrolment, cash contribution and full settlement. Ctrl+C/four-hour timeout drops only
this run's exact generated database; the same abrupt-termination caution as B4 applies.

Local smoke evidence (23 October 2026): six helper tests passed with normal hashing
(13.108 seconds); standalone check-only seed/role/integrity checks and exact-database
cleanup passed. Chrome owner login and the unpublished monthly offer rendered. At the
390px viewport override, document client/scroll widths both measured 375px (scrollbar
excluded), with no horizontal overflow. Tab moves from confirmation to reason to
publication button. The viewport was reset and the draft left unpublished for the owner.
This is a limited rendering/keyboard smoke check, not full customer journey, focus-style,
screen-reader, print, exception or user-acceptance evidence.

## B4 closure acceptance checkpoint (23 October 2026)

`schemes.tests.test_closure_acceptance` exercises customer request and owner acceptance,
unused cancellation, early full settlement after three of twelve actual instalments,
invoice/basis/exact quantity on the customer statement, reversal/restoration and old
submission replay through CSRF-protected Django forms. It also checks cross-customer
isolation, form IDs/labels, escaped references, same-payment webhook redelivery,
unexpected second capture after settlement and duplicate settlement/reversal races.
Fake providers and synthetic configured contracts only; activation is not bypassed.
The nine focused tests passed with normal password hashing in 30.945 seconds on a
disposable local PostgreSQL test database. All 201 affected regression tests passed in
225.996 seconds with a test-process-only fast password hasher. This is not a new
full-suite run; the earlier 803-test full regression belongs to the B3 checkpoint.
Django check, migration consistency and whitespace checks passed.

Owner acceptance recorded on 23 October 2026: the user reviewed the three supplied
local cases (unused cancellation, three-of-twelve early full settlement/closure,
and settlement correction) and confirmed they are acceptable. This is user-reported
scenario acceptance. No specific mobile viewport, keyboard, print, exception-case
or production coverage was confirmed. Remaining release checks stay open.

Manual B4 acceptance matrix (the three cases above accepted; remaining coverage open):

| Scenario | Expected owner/customer result |
| --- | --- |
| Never-used agreement | Request → accept → separately confirm cancellation; CANCELLED, no fabricated financial event, login and other agreements unchanged |
| Three paid instalments of twelve | Request → accept → resolve exposure → confirm full exact quantity/invoice/customer fulfilment; EARLY settlement, zero remaining entitlement, REDEEMED |
| Failed/abandoned or unresolved attempt | Held for disposition; neither “unused” nor silently settleable, no delete/status-edit workaround |
| Settlement correction | Original retained, exact entitlement restored, closure remains accepted and payments blocked; new settlement needs fresh preview/confirmation |
| Duplicate/stale submission | No duplicate liability mutation; changed evidence requires reload and confirmation |
| Late unexpected capture | Retained provider exception and investigation, no duplicate allocation or silent financial rewrite |

Use 390px and desktop layouts, keyboard-only focus and print view on isolated synthetic
data. Check invoice and six-decimal quantities, long references, readable labels/errors,
absence of horizontal page overflow, and no customer access to owner-only evidence.
HTML response tests are not a real viewport or screen-reader acceptance claim. Exact
image/migration rehearsal and production rollout require separate approval and evidence.

### Run the isolated owner walkthrough

Helper validation: 15 closure/helper/isolation tests passed with normal password
hashing in 29.140 seconds. Check-only migration/seed/private-page/integrity/cleanup
passed, and Chrome owner login plus the unused-agreement screen were verified on
the threaded review server. The owner subsequently accepted the three scenarios above;
this does not establish complete mobile/accessibility or release acceptance.

From the repository in a local terminal:

```powershell
uv --cache-dir .uv-cache run --no-sync --env-file .env python -m schemes.review_closure_locally --synthetic-local
```

This is a standalone opt-in review helper, not a production management command. It
requires explicit loopback PostgreSQL with no connection-option overrides and database
creation permission. It creates/migrates only a fresh random `jsk_b4_review_*` database;
it does not migrate or seed the database named in `.env`. Do not enable configured
plans in your ordinary database to perform this review. Existing activation guards
remain unchanged; the helper creates explicitly synthetic agreement fixtures.

Open the printed `http://127.0.0.1:8766/accounts/login/` URL. Use
`owner@example.invalid` or `customer@example.invalid` with the temporary password
printed for this run (do not reuse a real password or save it in the browser). Every
HTML page has a synthetic-review banner. The server binds to loopback only, uses
separate session/CSRF cookies, memory-only email, disabled online checkout/Google
login/PWA/reminders and local temporary media. Outbound Python socket connections
other than local PostgreSQL are rejected. Browser static assets can still use the
application's existing public CDNs. No real money, jewellery delivery or email occurs.

The three printed agreement links belong to one synthetic customer:

| Link label | Starting state | Owner walkthrough |
| --- | --- | --- |
| `unused` | Active, no payment or financial history | Create an owner-assisted closure request with `DEMO-CONSENT-001`, accept it, then separately confirm unused cancellation. Expect CANCELLED, no redemption and customer login unchanged. |
| `three-paid` | Three payments of INR 1,000 out of twelve; 0.300000 g GOLD_22K_916 at a **synthetic** INR 10,000/g rate | Request/accept closure, follow the full-settlement link, review EARLY and the whole quantity, use `DEMO-INVOICE-002` / `DEMO-FULFILMENT-002`, and confirm the simulated fulfilment. Expect REDEEMED, zero remaining metal, no unpaid-instalment credit or benefit. |
| `correction` | Already settled for 0.300000 g with DEMO-INVOICE-001 | Open the printed settlement URL, record `DEMO-CORRECTION-001` and confirm reversal. Expect the original retained, 0.300000 g restored, CLOSURE_PENDING and payments still blocked. A new full settlement needs a fresh preview and confirmation. |

Only in this disposable demonstration may you simulate the consent/delivery checks.
In production those checkboxes require actual retained evidence. To review the direct
customer journey instead, sign in as the sample customer first and submit the closure
request, then switch to the owner to accept it. Use a separate private browser window
for the customer, or explicitly log out between roles. Inspect statements and verify
that closing one agreement leaves the other agreements and login intact.

Check desktop and 390px browser responsive mode (a physical phone cannot reach the
PC's loopback address; do not expose this server on the LAN). Tab through forms and
errors, inspect print preview and long invoice references. Report each scenario as
pass/fail with the screen and wording that needs correction. This review cannot prove
publication/enrolment activation, real-provider disposition, legacy cutover or release
readiness.

The server automatically stops after four hours; Ctrl+C in the launching terminal
normally stops it earlier and removes its synthetic database/temp media. Each run is
fresh and has new links/password. Abrupt process termination may leave its random
database behind: use the exact printed name and a separate read-only target check
before approved cleanup, never a wildcard or the ordinary application database.
`--synthetic-local --check-only` seeds, runs integrity/private-page checks and cleans
up immediately without starting a server. The helper does not reset an existing run.

## B3 configured full settlement (23 October 2026)

`schemes.tests.test_configured_settlements` uses synthetic gated contracts and actual
financial services with local fake provider events. It covers full gold/silver precision,
calendar/monthly normal versus early eligibility, customer/owner/CSRF boundaries,
required invoice/confirmation, stale/expired/altered signed previews, duplicate requests,
pending/abandoned/Test-mode/timing/outage holds, correction and re-settlement without
reopening, source immutability/integrity and a PostgreSQL concurrent-settlement race.
A disposable-database 0032–0033 rehearsal preserves existing financial sources.
No ordinary/production migration, real payment or email is part of these tests.
**28 focused tests passed with normal password hashing in 109.561 seconds.** The final
**803-test full regression passed in 644.246 seconds**, using a test-process-only fast
password hasher. Initial fixture errors were corrected without relaxing settlement
rules. Django check, migration consistency and whitespace checks passed. Owner/mobile,
legacy-cutover and exact-image acceptance remain open; configured activation stays blocked.

## B2 unused-agreement cancellation (23 October 2026)

`schemes.tests.test_unused_agreement_cancellation` adds 15 synthetic configured-agreement
tests. Coverage includes monthly/calendar cancellation, retained terms/periods/login,
no fabricated financial rows, role/ownership/active-user checks, accepted-only/stale and
idempotent decisions, required owner confirmation and CSRF, zero-balance reversed and
failed/abandoned histories, instalment investigations, direct-model/legacy database
guards, terminal integrity checks and exclusion from active/payment/eligibility displays.
PostgreSQL races cover duplicate cancellation and cancellation competing with cash after
acceptance. A real disposable-database 0031-to-0032 migration preserves legacy records
without creating cancellation evidence. No ordinary or production database is migrated.

The 42 combined B1/B2 tests passed with normal password hashing in **133.518 seconds**.
The first run's sole error was a duplicated customer email in the legacy-guard fixture;
reuse of the fixture customer corrected it. The owner workspace now uses distinct HTML
field IDs for review and cancellation forms; a regression assertion covers that detail.
The final **775-test full regression passed in 624.048 seconds**, using only a
test-process fast password hasher (no production hashing/configuration change).
It includes the final form-ID, terminal next-action and review-queue presentation
updates. Django check, migration consistency and whitespace checks passed.
These automated checks do not replace owner/mobile review, legacy cutover or release
acceptance. All providers are fake and no real email is sent. Full-only settlement and
configured-plan activation are deliberately not enabled.

## B1 configured-agreement closure lifecycle (23 October 2026)

`schemes.tests.test_scheme_closures` uses synthetic configured monthly/calendar
agreements and local fake providers. Coverage: direct/owner-assisted authorization,
active customer/owner scoping, request/decision idempotency and stale sequences,
one-open-request and action-shape constraints, append-only history, pending-only
withdrawal/rejection, accepted payment/resumption guards, unaffected other agreements,
cash retry/correction, in-flight capture/allocation recovery, integrity reporting,
CSRF/private UI, legacy exclusion and no automatic unused cancellation.

PostgreSQL races cover duplicate creation, accept versus withdraw, acceptance winning
the account lock before cash, and concurrent accepted closure/captured payment. A
0030-to-0031 rehearsal preserves existing agreement/contribution values and creates
no closure requests/events. All schema work is in disposable local test databases.
**26 tests passed with normal hashing** in 73.388 seconds. Initial fast checks exposed
a duplicated fixture plan code and a test expecting the closure error while an older
pending-order guard fired first; fixture reuse and the explicit post-idempotency cash
closure guard resolved these. The final normal run was green. An additional test
uses a genuinely count-complete reminder candidate, then accepts closure and verifies
selection/locked-delivery suppression with no SMTP attempt. The final **760-test full
regression passed** in 630.569 seconds with a test-process-only fast password hasher,
including this additional test and all existing migration/financial/race coverage.
Django checks, migration consistency and whitespace checks passed. This is not
production, owner/mobile or release acceptance.

## P3 local checkpoint corrections (23 October 2026)

**79 focused tests passed** in 172.663 seconds across `test_monthly_eligibility`,
`test_configured_agreements`, `test_owner_workspace`, `test_redemptions` and
`test_eligibility`, against disposable local PostgreSQL. No new password-hasher
override was added (existing per-class test settings remain). New coverage checks
that monthly original dates and completed configured contracts never enter the
legacy Today settlement count, and that configured calendar/monthly GET and POST
requests cannot open the partial-redemption form. Legacy date boundaries remain,
with wording that requests eligibility review rather than promising settlement.
Extension copy and configured-calendar payment/status messages are asserted too.

The initial run's two failures were expired test sessions after a year-forward clock
jump, corrected by logging in inside the simulated date. The complete focused rerun
includes the final calendar status/action changes. Django checks, migration consistency
and whitespace checks pass; no new migration or ordinary database changes. The previous
729-test full regression below predates these checkpoint corrections. This is not
owner/mobile/email approval, CI evidence or permission to activate configured plans.

## P3 monthly completion reminders (23 October 2026, local and gated)

`schemes.tests.test_monthly_reminders` covers count-complete versus forecast-only
selection, extensions/original-date distinction, text/HTML and tracking headers,
no financial changes, reversal/outage/allocation suppression, refreshed recipients
and switches, date rollover, no monthly historical replay, forged candidates,
retry revalidation, changed completion identities, immutable previous evidence,
database/model shape checks and dry-run/apply idempotency. PostgreSQL concurrency
tests prove one accepted attempt for two dispatchers and suppression when a committed
cash reversal wins the account lock. A 0029-to-0030 rehearsal preserves legacy
reminders, attempts and agreements. Legacy reminder tests also cover closure and
recipient changes after planning. Mail uses the in-memory backend, never Postmark.
The final focused suite also treats a deliberately corrupted PAID row with no metal
allocation as unresolved, preserving its qualification count but suppressing mail.

**27 focused reminder tests passed with normal hashing** (138.207 seconds), using
disposable local PostgreSQL test databases. An initial full run found an isolation
error: an earlier migration rehearsal left the accounts schema historical. The new
0030 preservation test now restores all migration leaves before downgrading only
the schemes app to 0029, and restores leaves again on exit. No application workaround
or ordinary database migration was needed. Django checks, migration consistency and
whitespace checks passed.
The final complete rerun passed **729 tests** in 544.258 seconds with a process-only
fast password hasher, including the corrected migration setup and final corruption
case. The earlier 728-test run had one test-isolation error; it is superseded by this
green rerun. No production database, Postmark or real payment provider was contacted.

These tests do not prove exactly-once SMTP delivery across a crash, owner approval,
mobile/email-client visual acceptance, or production deployment readiness.

## P3 monthly eligibility projection (23 October 2026, local and gated)

`schemes.tests.test_monthly_eligibility` uses synthetic configured agreements and
the existing cash/provider-fixture services, never a real provider. Coverage includes
12 qualifying payments plus the final India-time period boundary, missed-period
extension payment/forecast, count completion blocking further initiation, exhaustion
without forfeiture, acknowledged compensation, cash reversal, resumable/expired
checkout, ambiguous creation, duplicate capture, missing timing, allocation failure,
corrupt/partial schedules, Test Mode rejection, read-only evaluation, template wording
and suppression of misleading original-date reminders. Legacy eligibility tests
remain separate. The shared projection is current evidence, not historical replay.

Full regression: **708 tests passed** with a process-only fast password hasher on
disposable local PostgreSQL test databases. A subsequent focused run passed all
**18 monthly-eligibility tests with normal password hashing** (60.283 seconds),
including the two ambiguous-order/duplicate-capture cases added after full-suite
discovery; the 708-test count does not include those two additions. Django checks, migration consistency
and whitespace checks passed. No ordinary/production database migrations were run.

No configured publication/enrolment or settlement gate is removed. At this earlier
checkpoint reminder integration remained pending; see the subsequent checkpoint above.

## Owner exception-form accessibility correction (23 October 2026)

`schemes.tests.test_instalment_form_accessibility`: five database-free tests first
failed against the missing help IDs and passed after the three template corrections.
Coverage includes unbound/invalid forms, default and period/claim-specific IDs,
multiple forms on one page, help/error target existence, unique IDs, label targets,
checkbox labeling, non-field errors and escaping. No service or policy change.

Combined regression: **53 tests passed with normal password hashing** across the
new rendering tests and existing owner-review, outage and order-recovery suites.
Database-backed cases used disposable local PostgreSQL test databases. Django checks,
migration consistency and whitespace checks passed; no full-suite rerun in this step.

A transient read-only localhost preview rendered synthetic objects with database
execution explicitly prohibited and no POST action available. Chrome inspection
at 390x844 and 1440x1000 covered period review, recovery and outage forms, invalid
input/help presentation and keyboard field traversal. Mobile document width was
375 CSS pixels within the 390-pixel viewport (scrollbar accounted for); help/error
references resolved. The server/tab were closed and viewport reset afterwards.
This limited form-rendering smoke did not exercise a real customer, a provider,
the complete owner queue/decision journey, or a screen reader. Those acceptance
items remain pending; do not describe the entire P2 owner workflow as approved.

## Accumulated P2 checkpoint review (23 October 2026)

Code review covered configured activation gates, migrations 0021–0029, account-locked
payment attribution/recovery, outage evidence and owner exception rendering. This
does not replace CI, exact-image rehearsal or owner/mobile acceptance.

Checkpoint rerun: **149 tests passed** across plan governance/configuration (including
migration tests), configured agreements, schedules, payment ledger/integration,
owner reviews, outage amendments, order recovery and capture containment. This used
a test-process-only fast password hasher and disposable local PostgreSQL test
databases. Django checks and `makemigrations --check --dry-run` passed. The previous
687-test full regression and 26-test normal-hashing run were not rerun in this review.

Historical finding, subsequently fixed by the correction above: render the three owner
forms with synthetic objects and parse each widget's `aria-describedby` ID references
against the rendered IDs. Period review is missing `period_reason_helptext`;
order recovery is missing `id_order_id_helptext`; outage resolution is missing
`id_reason_helptext`, `id_incident_started_at_helptext`,
`id_service_restored_at_helptext`, `id_customer_acknowledged_at_helptext` and
`id_acknowledgement_reference_helptext`. The custom help-text wrappers need matching
IDs. Add regression coverage for unbound and invalid forms, unique IDs when multiple
claim forms appear, and links to actual help/error elements. These HTML-only probes
made no database writes or provider requests; they are not a visual browser test.

The next owner rehearsal must use an isolated synthetic database, not enable drafts
or manufacture duplicate payments in production. Check desktop/narrow mobile widths,
keyboard focus, labels/help/errors, long provider/evidence references, empty and
review states, stale submissions and unchanged financial evidence. Owner acceptance
is still pending. P3 must separately reconcile customer payment prompts and reminders
with monthly ledger/hold/count/extension state before configured activation.

## Late/duplicate-capture containment (P2b.3b, gated)

`schemes.tests.test_instalment_capture_boundaries` tests same-payment redelivery versus
different-payment capture, retained original credit/rate/allocation, account-scoped
online/cash/timing guards, delayed on-time delivery, expired timing review, late capture
after cash replacement, confirmation of an in-flight replacement during review/pause,
transient-event retry, mode/order isolation, owner queue/provider links and customer
availability. A two-capture race must yield one credit and one retained provider review.
The order-recovery suite also checks the hold/owner queue for captures that arrived
before their order identity was linked. These use synthetic gated agreements and no
provider network. Schema remains at 0029; no historical backfill or real refund.

See STATUS.md for final validation evidence. Tests establish local containment, not
owner/mobile approval, verified refund completion, configured activation, CI or release
acceptance. Unresolved captures and structural integrity are separate checks.

Owner acceptance, using synthetic fixtures in an isolated rehearsal database only:

- Confirm the period queue/detail shows retained additional-payment identity and the
  existing provider-reconciliation link on desktop and narrow mobile widths.
- Confirm original receipt/rate/allocation is unchanged; the customer sees a review
  hold, not a new payment prompt or a second instalment credit.
- Confirm an investigation note cannot clear a capture exception or assert a refund;
  late abandoned-order evidence remains separate from any legitimate replacement.
- Confirm ordinary same-payment redelivery is not displayed as an additional debit.

Do not create duplicate real payments, edit event status or enable configured plans
in production to rehearse these scenarios. CI and exact-image PostgreSQL 18.6
rehearsal still follow the accumulated checkpoint review.

23 October 2026: **687 full serial regression tests passed** using a test-process-only
fast password hasher; **26 focused capture/recovery tests passed with normal hashing**.
Django checks, migration consistency and whitespace checks passed. No new migration
was generated; existing migrations were exercised only in disposable local PostgreSQL
test databases. No normal local/production migration, environment edit, commit, push
or deployment was performed.

## Exact ambiguous-order identity recovery (P2b.3b partial, gated)

`schemes.tests.test_instalment_order_recovery` covers durable provider receipt/UUID
correlation, authenticated fixed-endpoint reads, mismatched/absent/provider-error
evidence, historical uncorrelated requests, response/write failures, stale evidence,
idempotent and concurrent binding, immutable/database guards and integrity checks.
Owner-only CSRF-protected UI does not expose a resumable customer checkout. Tests
distinguish identity binding from verified capture/qualification, including a capture
received before binding, explicit payment reconciliation, signed timing redelivery,
expired untouched-order abandonment and late-capture review. No provider network or
real funds are used. Forward migration preservation now extends through 0029 without
financial backfill; configured publication/enrolment remains blocked.

See STATUS.md for current validation results. Owner/mobile review, CI, exact-image
PostgreSQL 18.6 rehearsal and remaining exception acceptance are still required.

23 October 2026: **677 full serial regression tests passed** with a test-process-only
fast password hasher. **27 final focused tests passed with normal hashing** across
order recovery, payment presentation and customer contribution views, including final
desktop/mobile history link suppression and malformed provider-status handling.
Django checks, migration consistency and whitespace checks passed. Migration 0029
was exercised only on disposable local PostgreSQL test databases; no ordinary local
or production database, environment, commit, push or deployment changed.

## Bounded outage amendments (P2b.3b partial, gated)

`schemes.tests.test_instalment_outages` covers separate three-month compensation caps,
one grant per affected period, original-anchor month-end dates, preservation of original
agreements/periods/finances, current-rate payment in an appended window, strict evidence/
acknowledgement timestamps, stale submissions, idempotency, immutable/database guards,
restored/qualified-only closure and rejection of uncertain orders, missing timing,
unresolved webhooks or allocation failure. Private owner UI retains CSRF protection.
Race tests cover same-submission replay, competing proposals requiring refreshed
acknowledgement, and capture versus compensation without invented payment credit.
Actual forward-migration preservation extends through 0028, with no legacy amendment
or configuration-evidence hash change. Configured enrolment/publication remains blocked.
See STATUS.md for final run results; owner mobile/visual review and exact-image
PostgreSQL 18.6 acceptance remain pending.

23 October 2026: **661 full serial tests passed** with a test-process-only fast
password hasher; **49 final focused tests passed with normal hashing**, including the
latest selector/UI edits, outage/review/integration races and actual forward migration
through 0028. Django checks, migration consistency and whitespace checks passed.
Only disposable local PostgreSQL test databases were migrated; no ordinary local or
production database, environment, commit or push changed.

## Owner instalment investigation (P2b.3a, gated)

`schemes.tests.test_instalment_reviews` covers owner-only review, required references,
append-only/stale/idempotent evidence, stored signed timing acceptance, rejection of
conflicting/expired/missing or cross-account evidence, no financial mutation, outage
initiation holds with continued in-flight capture handling, uncertain-order notes
without release, database constraints, integrity corruption detection, private/CSRF
UI routes, duplicate owner races and outage-versus-cash serialization. Configuration
migration preservation now rehearses through 0029 without historical qualification.
No provider network or production mutation is used. Owner mobile/visual acceptance
and final exception acceptance remain pending; bounded outage remedies and exact
ambiguous-order identity recovery are now covered by the sections above.

23 October 2026: 643 full serial regression tests passed with a test-process-only fast
password hasher. The final 32-test review/integration/migration run passed with normal
hashing, including the added India-time boundary and malformed reservation-input
checks. Django checks, migration consistency and diff checks passed. Migrations ran
only on disposable local PostgreSQL databases, not the ordinary local or production DB.

## Monthly payment-service integration (P2b.2, gated)

`schemes.tests.test_instalment_payment_integration` exercises the existing service
entry points with synthetic agreements and a fake provider: reserve-before-order,
same-order resume, expired claims, callback awaiting timing, delayed webhook during
pause, duplicates, missing timing review, paid-unallocated, cash idempotency/correction/
replacement and rollback, provider-backed abandonment and late-capture review, ambiguous
order errors, interruption after a provider response, Test/mock/backdate rejection, extension-period payment and owner API
recovery followed by signed-payload replay. Separate-connection tests cover simultaneous
online requests and online-versus-showroom-cash creation. No provider network requests
or production mutations are used. An HTTP test verifies a signed captured webhook and
rejects an invalid signature without creating an event. The migration rehearsal also covers 0025-to-0026
without assigning new historical payment qualification.

Configured enrolment/publication gates remain. Outage/review-resolution UI and final
exception acceptance belong to P2b.3; policy eligibility and full settlement are not
claimed by these payment-service tests.

23 October 2026 validation: all 629 serial regression tests passed with a
test-process-only fast password hasher. A final 18-test run with normal hashing
passed the integration/race module, historical configuration migration rehearsal
through 0026 and the legacy signed-webhook transient-failure retry test. Django
system checks, migration consistency and whitespace checks passed. Only disposable
local PostgreSQL test databases were migrated; exact-image PostgreSQL 18.6 release
acceptance and production rollout remain pending.

## Instalment payment ledger foundation (P2b.1, gated)

`schemes.tests.test_instalment_payments` tests current-period reservation exclusivity
across online/cash, separate-connection races, idempotence, India-boundary deadline
capping, delayed captured-event evidence, malformed/unverified payload rejection,
missing/contradictory timing review, Test/mock exclusion, cash reversal/replacement,
database constraints, immutable model writes and projection-corruption detection.
Synthetic agreements/payments exercise internal primitives only. No real payment or
enabled configured enrolment is used. Qualification neither allocates metal nor grants
eligibility; paid-unallocated is reported separately. The configuration migration
rehearsal now also applies 0024 to 0025, preserving old agreements/contributions and
proving empty new tables. The read-only check is `check_instalment_payments`.

At the P2b.1 checkpoint, payment-path integration and exception acceptance remained
open. P2b.2 service coverage is now recorded above; P2b.3 outage/review resolution
remains open. These are separate from internal-ledger acceptance.

23 October 2026 validation: 611 full serial regression tests passed with a test-process-only
fast password hasher; 13 final focused tests passed with normal hashing, including two
additional timestamp/backfill tests and the actual schema preservation rehearsal.
The initial combined ledger/schedule run passed 24 tests. Django checks, migration-drift
and diff checks passed. All migration execution was on disposable local PostgreSQL
test databases; no ordinary local/production migration or exact-image PG18.6 acceptance.

## Monthly schedule foundation (P2a, gated)

`schemes.tests.test_instalment_schedules` covers approved policy compatibility and DB
NULL guards, anniversary/month-end/leap-day boundaries, fixed India-time half-open
windows, no-miss/two-miss/extension-limit scenarios, read-only owner previews, frozen
periods, idempotent concurrent preparation, corruption detection and preserved gates.
Fixtures create synthetic agreements directly; no real enrolment gate is patched and
no payment is sent. `check_instalment_schedules` is read-only and checks definitions
against snapshots, not payment compliance. The configuration migration test rehearses
0023→0024 preserving all old fields and calendar-configuration evidence, with no
period backfill. Monetary/metal ledgers remain unchanged by previews/preparation.

P2b.1 internal-ledger coverage is recorded above; payment integration and outage tests
remain pending. Never treat successful schedule tests as a released monthly-payment
journey or full-settlement acceptance. Browser/mobile visual acceptance is separate.

23 October 2026 evidence: 601 full serial tests passed with a test-process-only fast
password hasher; 15 final focused schedule/migration tests passed with normal hashing.
Django system, migration-drift and diff checks passed. No ordinary local or production
database migration was run. Exact-image PostgreSQL 18.6 and CI acceptance remain open.

## Configured individual terms (P1b, gated)

Run `schemes.tests.test_configured_agreements`, the configuration/governance migration
tests, `accounts.test_plan_applications` and `schemes.tests.test_enrolment_requests`,
then the full serial suite. Tests create synthetic configured accounts directly on the
disposable test database without patching publication/enrolment gates. This is not an
enabled end-to-end offer/approval test. Cover different customer-selected amounts under
one version, exact fixed/variable/step validation, every payment channel, locked reloads,
no provider order on invalid input, snapshot immutability, corrupted-term checks,
legacy-preference preservation and configured redemption refusal. Approval tests assert
the reviewed selection is passed onward without altering legacy variable agreements.
The configuration migration test also runs 0022→0023 and compares all old agreement/
plan fields, with null new references/steps. Existing financial rows are not rewritten.

P4 now adds actual publication/confirmation/enrolment/settlement service tests and
migration 0034 replaces the unconditional preparation constraint with publication proof.
Normal production/local databases and external gateways are not used by these tests.

## Preparation-only configuration foundation (P1a)

Run `schemes.tests.test_plan_configuration` and
`schemes.tests.test_plan_configuration_migration` alongside the governance tests, then
the full serial suite. Coverage includes owner/CSRF boundaries, immutable version reuse,
two-connection successor races, unknown/incompatible policies, Decimal bounds/steps,
fixed-versus-variable previews, no financial writes from previews, transactional draft
audit failure, server and database activation blocks and legacy enrolment preservation.
The actual 0021-to-0022 upgrade test compares all existing plan and agreement fields,
leaves the plan unconfigured and creates no configuration versions automatically.
`check_plan_configurations` is read-only and fails on invalid definitions, projection or
revision-evidence drift. P4 permits valid publication and agreements while still rejecting
configured agreements linked to unpublished draft terms.

These P1 tests are **not** tests of a live customer-fixed plan. Subsequent B/P4 tests
cover full-only settlement and controlled enrolment, with fake external providers.
The default-off release gate never substitutes for owner publication evidence. Before release, visually
review catalogue/create/version/preview/reuse and pinned-plan edit screens on mobile,
desktop and keyboard, and rehearse the exact image on production's PostgreSQL major.

## Owner plan builder / full-only settlement acceptance (planned)

The approved ADR-0017 policy catalogue is not implemented by current Phase A tests.
Each slice in MVP_PLAN.md must add relevant service, database, permission, template
and migration coverage before publication; these are acceptance requirements, not
claims of existing passing tests:

- Validate each permitted configuration and reject incompatible combinations in the
  service, not just the owner UI. Unknown enums/unsupported policies, incomplete numeric
  rules, cross-grade/cash conversion and a forged partial option fail closed.
- Owner-created/reused versions are immutable; no-op edits, concurrent edits, changed
  pending offers and historical snapshots remain correct. A customer cannot create or
  publish a configuration by direct POST. Deferred proposal features are absent.
- Two customers can select different bounded monthly amounts under one customer-fixed
  plan; enforce each frozen selection for Razorpay and cash. Plan-fixed and variable
  behaviour remain distinct. Test out-of-range/step/precision values and attempted edits.
- Scheduled periods cover month ends/leap years, agreed timezone, exact due/grace
  boundaries, missed periods, catch-up and extension limits. Include fully on-time,
  skipped middle month, fewer payments than required, retries, duplicate webhooks,
  late captures, reversals, paid-unallocated recovery and Test/Live separation.
- Calendar/count/both results match across selectors, payment permission, reminders,
  statements and settlement; original dates never shift silently. Required extension
  payments remain possible after the original calendar date. No accidental twelve-
  payments-in-one-week completion. Showroom pauses/outages follow approved exception rules.
- Benefits without an approved policy remain unavailable. Test qualification separately
  from redemption, caps/exclusions/rounding, projection versus earned/fulfilled amounts,
  duplicate fulfilment, reversals and missed-payment loss of an unearned benefit. No
  invented gold grams, cash refund or principal forfeiture.
- Reject every smaller/larger settlement request server-side. Full six-decimal gram
  entitlement settles despite three-decimal presentation; no residual dust. Lock and
  revalidate previews; test concurrent cash entry, provider capture, duplicate settlement
  and late payment after apparent abandonment. A full settlement closes only its agreement.
- Full-only cutover preserves prior partial-redemption records and remaining liabilities;
  contractual conflicts are identified, not silently amended. Unused cancellation is
  not a zero-quantity redemption; a zero balance after financial activity is not unused.
- Exact-image migration/rollback rehearsal and separate owner release approval remain
  necessary. Current local test totals must not be reused as acceptance for these rules.

## Plan governance and agreement provenance (A)

Run `schemes.tests.test_plan_governance` and
`schemes.tests.test_plan_governance_migration`, then the complete serial suite.
The migration test actually moves a disposable PostgreSQL test database from schemes
0020 to 0021 and compares every pre-existing agreement field, including deliberately
different historic/offer amounts; only observed display identity is added and no
accepted revision is invented. A separate-connection test serializes enrolment with
an audited edit. Verify stale-form rejection, creation audit, immutable snapshots,
admin restrictions, atomic audit failure, no-op edits, legacy labels and exact decimal
normalization. `check_plan_agreements` is a read-only rollout integrity check.

Before release, visually inspect owner plan list/add/edit and customer agreement,
statement and approved-application screens on desktop/mobile. Confirm current-offer
changes cannot rewrite old agreement names or amounts, and legacy identity is not
presented as original customer consent. Rehearse the exact CI image on the production
PostgreSQL major version; local PostgreSQL 16.1 tests are not that image rehearsal.
Early discontinuation/unused cancellation (B) still require separate implementation
and their own race, authorization, settlement and correction acceptance.

## Release rehearsal and stakeholder task protocol (22 October 2026)

Run the opt-in synthetic local drill described in PRODUCTION_DEPLOYMENT.md:

```powershell
uv --cache-dir .uv-cache run --no-sync --env-file .env python -m schemes.rehearse_workflow_release --synthetic-local
```

The drill creates a pre-conversion synthetic baseline at accounts.0006 / the current
schemes leaf / pages.0001, dumps it, restores a fresh database and applies the current
pending accounts/pages migrations. The accepted 22 October release used schemes.0020;
with configured-agreement code the seed uses schemes.0023. This older conversion drill is
not evidence of a schemes.0020-to-0021 upgrade; use the governance migration test and
an exact-image upgrade rehearsal for that change.
It compares every legacy identity/registration/enrolment and financial row before/after the
upgrade, checks INR/gold/silver separately, reads restored owner/customer/history pages and
four owner fragments, and verifies permissions/no financial writes on reads. It then exercises
changed-term rejection, renewed confirmation, idempotent coordinated approval, failed-mail
recovery, replacement invitation, activation and continuation without inventing first payment.
Five existing integrity commands must pass. CLI guards reject non-local/option-overridden
connections and unsupported arguments before creating any database. Run the guards and relevant
application/activation/audit regressions with schemes.tests.test_release_rehearsal.

This is a synthetic schema-upgrade rehearsal, not a restored production-backup exercise. It
uses Django HTTPS test-client requests with DEBUG=False and local static storage; it does not
prove the built production image, collected manifest, Caddy/edge/log-sink behavior, delivery
through Postmark, Google OAuth, sandbox capture, JS-disabled browser use or participant usability.
The earlier responsive browser evidence remains in STATUS.md; no UI changed in this drill.

A preliminary local feedback session is prepared at http://127.0.0.1:8100/ on the owner's
computer, with fictional owner/customer accounts supplied in the session hand-off. It uses the
current uncommitted source, not a released image. Record preliminary observations separately
from exact-image staging acceptance. Source fingerprint and lifecycle details are in the ignored
.uv-cache/usability-session.json, with no credentials added to canonical documentation. The
preview remains active for participant review until its stop file or eight-hour limit; emails
stay in memory, server-side external connections are blocked and Google sign-in is disabled.
Use the existing customer tasks first, then sign out and use the owner tasks. Record completed /
help needed / not completed plus confusion. On 22 October 2026 the owner reported testing
both owner and customer roles locally and being satisfied. Task-level timings, device details,
wrong-turn counts and independent customer/Tamil observations were not supplied and are not
inferred. This records local stakeholder acceptance; external staging/provider checks remain open.

To stop this session and allow its normal cleanup, run from the project directory:

```powershell
.\.venv\Scripts\python.exe -c "import json; from pathlib import Path; s=json.loads(Path('.uv-cache/usability-session.json').read_text(encoding='utf-8')); Path(s['stop_file']).write_text('stop',encoding='utf-8')"
```

Confirm PREVIEW_DATABASE_REMOVED in .uv-cache/usability-preview.log before considering cleanup
complete. This local exploratory session does not close external staging/provider acceptance.

Before participant testing, record the staging hostname, exact candidate revision/image digest,
approved sanitized backup origin/time, migration baseline/result, reviewer/date, device/browser,
feature flags and Test/provider isolation. Use synthetic accounts and fixture receipts. Do not
use live money, real identity details, or send private tokens to notes/analytics. Keep any setup
credential hand-off outside shared notes. The owner supplies approved business copy and any
Tamil reviewer; no response window, benefit or unreviewed translation may be invented.

Give these tasks without describing the menu path. Observe rather than coach; record help
needed and confusion even when the final task is completed. Sandbox workflow steps requiring
terms, credentials or financial actions are performed by the participant under the applicable
confirmation policy, not automatically by a browser agent.

| Role | Task | Acceptance evidence to record |
| --- | --- | --- |
| Prospective customer | Compare plans on a phone and choose one | Explains amount rule, exact grade and duration from the shown offer; understands application versus approval; selected preferences survive continuation. |
| Applicant | Verify email, resume progress and finish required details | Finds the current stage, next action and supplied support details; explains renewed confirmation after a material offer change. |
| Approved customer | Activate, sign in and find the approved plan | Continues to that plan; distinguishes Test checkout, future/paused availability and pending confirmation from received payment. Uses recovery guidance for expired setup access. |
| Existing customer | Find a receipt/statement, return to the plan and apply again | Finds recorded evidence and Test/practice labels; navigates back without losing customer context; held profile details are reused appropriately. |
| Customer | Explain one unresolved payment | Finds recorded status/support and understands why another payment must not be assumed necessary while confirmation is pending. |
| Owner | Start the day and find a customer/application | Uses Today readiness/exceptions, scoped search and stage counts; can return from review with the same search/filter context. |
| Owner | Review an application and changed terms | Identifies contact verification, identity evidence, agreement snapshot and need for renewed confirmation; sees one coordinated action without losing separate audit evidence. |
| Owner | Inspect financial exceptions and export payment records | Distinguishes exception records from unique payments; selected customer/method/mode/date and exported scope agree; separates real received, Test/practice and corrections. |
| Owner | Review customer privacy and documents | Finds exact-customer privacy history, review and return; understands that viewing does not contain/delete an account or change financial history. |
| Both | Recover from empty/invalid filters, a failed read and expired session | Retains usable controls and correct scope; sees readable guidance; normal navigation works with JavaScript disabled on staging. |

Use one row per observed task in the acceptance record: scenario code, role, device/browser,
completed / completed with help / not completed, elapsed time if observed, wrong turns,
misunderstanding, severity, follow-up issue and retest result. Use aggregate counts and scenario
codes, not names, emails, customer IDs, private links or payment references. Do not fill these
fields with automated-test results. Customer/owner tasks and staging-specific checks remain
unaccepted until actual observations are recorded and material confusion is resolved.

## Exact local image verification (22 October 2026)

Release CI exposed dependencies that the local environment had not scanned and one flag-
dependent fallback display assertion. The release branch fixes only certifi/Pillow/PyJWT via
uv constraints/lockfile, then reruns media/CMS/Google-auth/storage regressions (116 passed in
64.247 seconds) and funnel/public-registration/plan-application regressions (64 passed in
17.688 seconds). The funnel case explicitly runs enrolment requests off/on; the legacy access
form shares INR grouping with the plan-first form. Keep CI's full 536-test and fixable-critical
scan gates intact; use the current PR head's checks, not an earlier local result, for release.

After the owner accepted both local roles, the unchanged production Dockerfile/lockfile built
from the accepted source fingerprint. The local candidate passed the synthetic predecessor
schema seed, actual PostgreSQL dump/restore and pending upgrade in containers. The app used
its default app user with read-only root, dropped capabilities, no-new-privileges and a /tmp
tmpfs. The network was internal-only and no ports were published; all resources were removed.
Existing rehearsal selectors/services checked historical rows, independent cash/gold/silver
liabilities, old customer access, owner fragment/permission behavior, new application terms,
retry-safe approval and recoverable activation/continuation. Production static manifest lookup,
Gunicorn health/ready, health/live and hashed static HTTP responses passed. Provider journeys
used in-memory mail; a separate dummy SMTP/R2 config check is not external-provider acceptance.
See STATUS.md for source/image identity and the final full-suite result. No customer/owner UI
changed after the accepted preview, and no additional participant results are inferred.

## Workflow refinement and HTMX acceptance (22 October 2026)

Run the serial full suite, schemes.tests.test_workflow_refinement and
schemes.tests.test_audit_completion. Relevant existing
coverage includes owner_workspace, payment_presentation, in_store_cash_contributions,
metal_only_boundary, metal_views, redemptions, documents, views, reminders and accounts
activation_continuation / plan_applications / public registration and logging protections.
New regressions verify shared list/CSV scope and export exclusions, fail-closed invalid
filters, separate Live/Test totals, exact-payment/customer intersection, pending cash GET
without financial/provider effects, combined applicant search, allowlisted review return,
fragment authorization/cache/history-restore/login behavior, customer document/application
isolation, bounded histories, one primary pending-payment action and private-query redaction.
INR grouping retains two-place money/four-place rates and stored financial precision.
Remaining-audit tests cover stage counts with search/customer/type scope and linked-record
deduplication; application/payment/exception full-page/fragment parity and fallback; CSV/totals/
errors; category/order and fixed-page exceptions; scoped privacy history/review context; six
milestones, changed terms, approved snapshots, Test/live separation and a showroom-cash
correction through financial services; role-aware print navigation and Test/practice labels.
Provider/audit/financial writes are checked absent on reads.

Inspect desktop 1440x1000/mobile 390x844 in an isolated synthetic preview. Check drawer,
role links, customer sections/documents, applicant filters/review return, clear payment scope,
blocked cash entry, contact tel/autofill/month units, optional message, error focus, protected
progress, Home vs Plans, receipts/statements and status check time vs payment receipt time.
Use invalid empty forms for error inspection; do not submit terms/approvals/payments or
new credentials/Google connections. Normal full-page/GET regression requests verify fallback
without executing JavaScript. Browser checks cover partial search/pagination, focus after
replacement and status refresh. A preview-only 503 responder verifies prior-result retention
and visible retry guidance, without changing application production code or contacting a
provider. Full login recovery must replace the page, not appear inside a results panel.

Node syntax checks and Django checks/migration consistency/static dry-run are required.
The official HTMX 2.0.11 SHA-384 matches the vendored bytes and the script SRI; license is
included. Caddy validation runs locally with networking disabled, then the exact prepared
filters are exercised with a loopback responder and synthetic query/Referer/HX-Current-URL.
The accepted access record retains a masked IP, /scheme/owner/customers/?[REDACTED] and
status 200, with no fixture query/header values. Production/external-sink validation still
belongs to approved staging/release. See STATUS.md for the final counts and screenshot proof.
No claim of actual screen-reader certification, participant testing or conversion lift.
Synthetic fixture full/fragment HTML sizes: Applications 12,058/5,422 bytes; Payments
12,782/6,152 bytes; Exceptions 8,266/1,634 bytes. This measures HTML transfer size, not latency
or task completion. See STATUS.md for final regression results.

## Customer conversion Phase 2

Run `schemes.tests.test_owner_workspace`, `schemes.tests.test_views`,
`schemes.tests.test_enrolment_requests`, `schemes.tests.test_audit_exceptions` and
`accounts.test_public_registration`, followed by the serial full suite. Workspace
tests cover guest/customer/CMS denial, explicit inactive-owner denial, no-store/read-only
Today, stage ordering, failed/expired verification, unresolved request expiry,
8-item Today bounds, mixed-source 25-item pagination, fixed customer search/pagination,
all supported search identifiers, duplicate-free agreement joins, approved-identity
linkage and customer-scoped payment context. Review tests retain CSRF and changed-offer
guards, historical decisions and inactive-login wording; exception tests cover exact
payment links, context on failed retry, supported recovery links and safe unsupported
event presentation. Queue GETs must create no agreement, payment, allocation or notice.
Shared identity-screen reason fields have distinct labels/IDs; pending request reviews
hide conversion when the customer login is no longer eligible and surface that next
action instead. Existing conversion POST services retain their independent rechecks.

Inspect owner landing, Today, inbox/filtering, both review types, search/page navigation,
customer-scoped payments, recovery and related documents at 390px and desktop. Inspect
the customer dashboard/document journey to confirm owner controls do not appear. Use
fictional fixtures in a separately named local preview test database with in-memory
email and no real provider operations. Keep visual financial forms unsubmitted;
service/POST behavior is covered by regression tests. Stop the preview and remove its
database after inspection. Phase 2 adds no migration.

## Customer conversion Phase 1

Relevant suites: `pages`, `accounts.test_public_registration`,
`schemes.tests.test_payment_presentation`, `schemes.tests.test_payment_operations`
and `schemes.tests.test_razorpay`; run the full suite before handoff. New tests cover
validated/disabled selected-plan entry, private offerings, exact decimal display,
removal of unreviewed description copy, anonymous allowlisted counter contents,
HEAD/owner exclusions, disabled/failing measurement, source-record verification and
full-history first Live payment counting. Payment presentation tests cover pause,
missing rates, monthly payment/expiry, abandoned desktop/mobile history, customer
isolation, no-store/read-only status, confirmed and paid-unallocated outcomes.
Node is used by one behavior test to execute the rendered checkout JavaScript with
fake DOM/provider/network objects for lost/rejected confirmation, cancellation,
provider failure and expiry. It adds no application runtime dependency. This test
skips if Node is unavailable; require its successful local execution for Phase 1.

Inspect home/plans/application entry at 390px and desktop, including details disclosure
and disabled features. Use fictional isolated local PostgreSQL fixtures for customer
pause/history/status and owner context inspection; never create real payments just
for visual QA. The normal `.env` application database and production data are not
preview fixtures.

Use the default serial runner for release verification. A Windows `--parallel 4`
run hit duplicate seeded metal-grade data in the existing
`CheckoutExpiryMigrationTests` fixture and then could not serialize its traceback;
that attempt is not a successful full-suite result. Do not change production
settings or financial migration behavior to work around test-runner isolation.

All commands require the environment variables documented in the README and a PostgreSQL role able to create a test database.

```powershell
uv run --env-file .env python manage.py test
uv run --env-file .env python manage.py test schemes
uv run --env-file .env python manage.py check
uv run --env-file .env python manage.py makemigrations --check --dry-run
```

Authentication regressions cover closed public signup, owner-only digest-backed
customer invitations, bounded expiry and one-time acceptance, resend supersession,
provider failure/retry, direct untracked email links, token-response privacy headers,
edge/access-log exclusion, Django warning/error token redaction, case-insensitive
login-email uniqueness, login/enrolment separation, closed social signup, exact-email
customer-initiated Google linking, privileged/inactive-user rejection, no email-based
auto-linking, feature-switch containment, password fallback, callback log exclusion,
zero provider-token retention, deletion-request enumeration resistance, digest-only
one-time deletion verification, CSRF/cache/referrer/log protection, session and Google
credential revocation, owner-only review, financial-record preservation, disabled-
flag hiding, and aggregate deletion-integrity reporting.

Current regressions cover amount/frequency enforcement, failed-payment entitlement, confirmation/allocation idempotency, Razorpay mode/key matching, mode history migration, cross-mode order/callback/webhook rejection, Live checkout disclosure, readiness blocking, order/API/HMAC boundaries, duplicate callbacks and webhooks, owner-only Scheme Rate publication, publication validation/warnings, GOLD/SILVER no-rate payment blocking with unaffected CASH orders, pre-order rate locking, durable verified-metal-payment recovery, exact metal calculation, historical-rate stability, paid-unallocated recovery from the original lock, production-shaped `schemes.0009` to `0010` history backfill and blocker behavior, customer isolation, owner liability reconciliation, current-exposure rounding, India-local activity periods, eligibility status and exact 30/60/90-day boundaries, versioned cash-bonus snapshots, projection-versus-earned boundaries, eligibility cutoff, half-up bonus rounding, principal/bonus redemption allocation, redemption idempotency and precision, partial/full settlement, over-redemption prevention, denomination separation, immutable audit/reversal history, exception classification, reversal liability restoration, stable receipt numbering, unallocated-document disclosure, statement source filtering, document/export access control, CSV denomination/formula safety, and database constraints.

Mock financial tests use `override_settings` only for payment configuration. For manual testing, put `DJANGO_DEBUG=True` and `PAYMENT_GATEWAY=mock` in the ignored `.env`, sign in as the owner, and publish gold and silver rates before testing metal payments.

Razorpay tests likewise replace the HTTPS boundary with deterministic order and payment responses. They verify raw-body webhook HMAC, invalid-callback rejection, captured-payment matching, duplicate callback/webhook idempotency, mode isolation, one metal allocation, customer isolation, snapshotted Checkout expiry, expired-resume blocking, captured-after-expiry confirmation, provider order inspection, dry-run/apply abandonment, flexible-attempt isolation, replacement resume, and late-capture exception routing without using provider credentials. Keep normal development and CI on `RAZORPAY_MODE=test`. Before a controlled production cutover, run `check_razorpay_live_readiness` with mode-matched synthetic or privately injected Live configuration; the command performs no provider request and prints no secret. For an external test-mode smoke, use private test keys, expose the webhook endpoint over HTTPS, subscribe to `payment.captured`, and confirm one test payment produces one contribution benefit and one processed webhook event. Use Razorpay's documented Test Mode instruments: select Netbanking and choose **Success**, enter `success@razorpay` for UPI, or use a documented domestic test card and complete the simulated OTP page. A payment left at provider status `created` has not been authorized and must not create entitlement. The abandoned-order command does call Razorpay: run it without `--apply` first, and never treat application-side abandonment as provider cancellation.

PWA regressions verify the disabled-by-default routes, installable manifest fields,
declared PNG dimensions, worker update headers, three-item static cache allowlist,
network-only navigation behavior, non-interception of mutations/subresources, absence
of runtime response caching/background sync/IndexedDB, generic dependency-free offline
copy, and enabled/disabled document wiring. Run the focused suite with:

```powershell
uv run --env-file .env python manage.py test pages.test_pwa
```

The same suite proves that Android Digital Asset Links is 404 while disabled and,
when enabled, returns a read-only JSON statement containing only the permanent
package and reviewed Play App Signing certificate keyset at the exact well-known
path. It rejects accidental inclusion of the separately controlled upload-key
certificate.

## Manual smoke test

- With `PWA_ENABLED=False`, confirm the manifest, worker, and offline routes return 404
  and an already-installed worker/cache is removed after one successful online load
- With `PWA_ENABLED=True` over HTTPS, inspect the manifest and maskable safe area in
  browser developer tools and confirm the app is installable with the reviewed name/icon
- Inspect Cache Storage and confirm only `/offline/` and the 192/512 app icons exist
- Take the browser offline, navigate to customer/auth/payment/owner URLs, and confirm
  only the generic connection-required page appears with no cached customer data
- Attempt a form submission while offline, restore connectivity, and prove no request,
  order, contribution, rate lock, allocation, redemption, or approval was created
- Restore connectivity and confirm current server state loads; exercise worker update
  and disable/re-enable behavior without stale pages
- With `ANDROID_TWA_ASSET_LINKS_ENABLED=False`, confirm
  `/.well-known/assetlinks.json` returns 404; when enabled, confirm a direct 200 JSON
  response with no redirect and compare the package and every fingerprint byte with
  Play Console before testing a Play-signed build

- Owner login and logout
- Password-reset request renders and sends through the configured backend
- With Google disabled, confirm no social action appears and password login still works
- With a controlled Google client, connect only from an approved customer session,
  then prove Google login and the original password/reset fallbacks independently
- Attempt an unconnected/mismatched Google identity and confirm no user is created or
  disclosed; run `check_customer_google_login` and confirm zero stored social tokens
- Create a customer as owner, verify the customer chooses their own password from the
  direct owned-domain invitation link, and confirm no scheme account was created
- Resend an unused invitation, verify the old link is unavailable, and confirm an
  activated customer is directed to password reset instead
- Admin opens for a superuser
- Create a plan and customer
- Enrol the customer
- Customer login shows only that customer's schemes
- Make a cash mock contribution and confirm the cash principal/history update
- Confirm a second monthly contribution is rejected while flexible contributions can repeat
- Confirm the owner contribution list shows the payment
- Publish gold and silver Scheme Rates as the owner and confirm the append-only history and audit entry
- Attempt a large rate change and confirm the extra warning/confirmation is required
- Make gold and silver contributions and confirm gram balances/history use their locked Scheme Rates
- Start a metal checkout, publish a new rate, complete the original payment, and confirm it uses the old lock while a new checkout uses the new rate
- Confirm the owner dashboard reconciles cash principal, gold grams, and silver grams separately
- Confirm current gold/silver Scheme Rates and indicative exposures update without changing historical allocations
- Confirm contribution-today/month counts include successful payments only
- Remove all applicable rates in a disposable database and confirm metal payment/order creation is blocked while cash remains available
- Simulate an unexpected allocation exception and confirm owner retry reuses the original locked rate
- Switch to private Razorpay test credentials, create an order, complete Standard Checkout, and confirm the callback and `payment.captured` webhook still produce exactly one benefit
- Repeat the same signed webhook and confirm the contribution, balance, and allocation counts remain unchanged
- Confirm the owner eligibility view groups accounts into eligible now, days 1–30, 31–60, 61–90, later, and redeemed without overlap
- Confirm an eligible customer sees the new status while the underlying account remains open
- Record a partial cash redemption and confirm the customer and owner balances decrease while the account remains redemption eligible
- Complete the remaining cash redemption and confirm the account becomes redeemed while all contribution/redemption history remains visible
- Record gold and silver redemptions and confirm only the matching gram liability decreases
- Confirm jewellery-purchase settlement requires an invoice/reference and records the supplied notes
- Repeat a redemption submission with the same idempotency key and confirm it creates no duplicate event
- Confirm customers cannot access owner redemption actions
- Create a cash-bonus plan and confirm enrolment snapshots its policy version, percentage, and minimum duration
- Before eligibility, confirm projected bonus is visible but excluded from redeemable amount and owner liability
- At eligibility, confirm earned bonus includes only principal paid by the cutoff and post-eligibility contributions do not alter it
- Redeem cash partially and fully; confirm principal is consumed before bonus and both immutable components reconcile
- Edit a plan with an audit reason and confirm existing enrolment snapshots remain unchanged
- Confirm owner enrolment, redemption, and allocation retry actions appear with actor, timestamp, and reason in the audit log
- Create a paid-unallocated contribution or failed webhook event and confirm the owner exception queue classifies it without changing entitlement
- Reverse a redemption and confirm the original remains visible, the restored liability reconciles, and the account reopens when necessary
- Print cash and metal receipts and confirm stable references, payment references, captured rates, and six-decimal allocations
- Confirm pending/failed attempts have no receipt and paid-unallocated receipts show no invented rate or quantity
- Print each customer scheme statement and reconcile its remaining entitlement with the customer detail view
- Download owner contribution/redemption CSV exports and confirm INR, gold grams, and silver grams remain separate

The complete checklist through owner liability reconciliation was exercised over live HTTP for the MVP Alpha checkpoint. The checkpoint created its plan, customer, three enrolments, and three payments through authenticated application forms, compared liability deltas against the pre-run dashboard, and removed all disposable records afterward.

Historical Milestone 5 testing exercised the former provider-recovery path. ADR-0003
supersedes that architecture; current tests instead cover owner publication,
pre-payment locking, no-rate blocking, and retry from an existing lock.

Milestone 7 exercised owner and customer sessions over live HTTP: the owner dashboard and grouped eligibility view showed the tagged account in eligible-now, the customer saw redemption-eligible guidance, and a direct database check confirmed the account remained stored as `ACTIVE`. The temporary server and tagged records were removed afterward.

Milestone 8 exercised authenticated owner and customer request flows with CSRF enforcement against the configured PostgreSQL database. The owner recorded a partial cash settlement followed by final jewellery-purchase settlement; the account moved from eligible/open to redeemed only at zero outstanding, the customer retained contribution and redemption history with no further payment action, owner cash liability returned to its baseline, and all tagged records were removed.

The MVP Beta checkpoint exercised a real Razorpay Test Mode order over a temporary public HTTPS endpoint. Razorpay reported the ₹100 payment as captured, the signed `payment.captured` webhook was stored and processed once, and Django created one paid cash contribution. The same eligible account was then fully redeemed through the CSRF-protected owner form; its outstanding cash and the owner cash-principal liability both returned to zero. Temporary quick tunnels are development-only and their URL and webhook secret must be synchronized in the Razorpay Test Mode dashboard for each run.

Milestone 9 exercised authenticated owner/customer forms inside a rollback-only PostgreSQL transaction. The owner created a 5%/12-month plan and enrolment, the customer completed a ₹100 mock payment before eligibility, the account aged into eligibility with ₹5 earned bonus, and the owner redeemed ₹105. The immutable redemption stored ₹100 principal plus ₹5 bonus, closed the account, and returned owner cash liability exactly to its baseline; no smoke records persisted.

Milestone 10 exercised an owner workflow inside a rollback-only PostgreSQL transaction. Audited enrolment, a ₹100 completed cash redemption, and its compensating reversal produced exactly three immutable audit events; the original redemption remained, the account reopened, and the ₹100 entitlement was restored. Authenticated owner audit and exception pages returned successfully, and no tagged smoke records persisted.

Milestone 11 exercised authenticated customer and owner document reads inside a rollback-only PostgreSQL transaction. A ₹1,000 mock gold contribution produced a stable printable receipt and a scheme statement showing the captured ₹12,500/g rate and 0.080000 g entitlement; owner contribution/redemption CSV exports returned successfully with separated denomination fields. No tagged smoke records persisted.


## Customer conversion Phase 3 regression and responsive acceptance

Local acceptance on 5 October 2026 passed 494 serial full-suite tests in 444.595
seconds, then 136 focused regressions in 104.440 seconds after final refinements.
Django checks and migration consistency checks passed. The responsive inspection
below was completed and its disposable preview database/server removed.

Use local/restored PostgreSQL and run tests serially. `accounts.test_plan_applications`
covers contact-first persisted preferences, digest-bound current offer confirmation,
separate one-use verification and resumable session-gated progress, CSRF/no-cache/log
redaction, owner permissions, changed/closed offers and policies, missed start dates,
identity conflicts, database expiry, distinct audit evidence, immutable linkage and
confirmations, rollback and recorded after-commit email failures. Its PostgreSQL threads
prove two simultaneous approvals create one identity/invitation/agreement/audit and
return the same agreement. An outer rollback proves activation is not delivered.
Existing customer request tests also reject substituted duration and changed disclosure.
Privacy regressions cover the retained identity/financial graph; containment now revokes
plan progress and completion minimizes the optional application message.

Run the migration regression before the application concurrency tests. The older
invitation migration test now restores all current leaf migrations at teardown, so it
cannot leave later transactional tests using its deliberately old schema. This is test
isolation, not a production migration change. Keep the known parallel migration-fixture
limitation in mind; full regression remains serial.

Desktop (1440x1000) and mobile (390x844) acceptance uses an isolated disposable preview
PostgreSQL database, synthetic customers and in-memory email. Inspect record-driven
intake, validation preserving values, email confirmation and retained preferences,
remaining address/consent form, private-link confirmation, completed showroom-review
stage/support, owner queue waiting/attention filters, coordinated identity/plan review
and confirmation history, and the existing customer's second-plan form without contact
or address fields. Inspect approval/rejection label targets and document width/long-text
wrapping. Do not submit financial approval/payment or change credentials through browser
inspection; service/HTTP regressions verify these outcomes. Remove the preview database
and close/reset the temporary browser surfaces after acceptance.

## Customer conversion Phase 4 acceptance

Local acceptance on 5 October 2026 passed all 514 serial full-suite tests in 469.374
seconds, then all 130 focused regressions in 72.856 seconds after final refinements.
Django checks, migration consistency and whitespace checks passed. The responsive
journeys below were inspected and the isolated preview database/server removed.

Run `accounts.test_activation_continuation` with invitation/social/application,
payment-presentation/operations, owner-workspace, existing-request and privacy
regressions, then the complete serial suite. Cover linked activation to a scoped
agreement through password login, no auto-login/financial write, external destination
rejection, legacy invitations, saved variable amount with fixed-amount compatibility,
non-cacheable dashboard and agreement pages, protected expired-token recovery/CSRF,
generic unknown/ineligible results, repeated help requests, owner resend failure,
latest-only recovery queue and customer isolation. Recorded Test/practice, pending,
unallocated, closed attempts, future dates and operational pauses must produce truthful
next actions. Simulate providers; never use live transactions for these regressions.

Responsive inspection uses isolated synthetic PostgreSQL and in-memory email. Inspect
valid setup (without entering new credentials), expired setup/help, password login with
the approved agreement destination, dashboard stages/next actions, first-payment form,
pending status and owner recovery queue/detail at 390x844 and 1440x1000. Verify document
width, long text and label targets. HTTP tests verify setup/financial outcomes; do not
submit a financial transaction or new password in browser inspection. Remove the
preview database/server, reset viewport and close temporary tabs.

### Prepared Tamil customer testing (English protocol; not published translations)

Dependencies: owner-reviewed Tamil terminology and translations of plan disclosures,
consent, identity/setup instructions, support copy and payment states; a Tamil-speaking
reviewer; synthetic accounts and sandbox payments. Keep amount/grade/duration/date and
policy versions synchronized with recorded offers. Do not infer benefits or an SLA.

Ask Tamil-speaking prospective and existing customers to complete these scenarios on
their phones using a reviewed prototype/staging build, without coaching:

1. Compare offers; explain the contribution amount, exact grade, duration and what the
   application does. Choose a plan and provide contact details.
2. Verify email, resume the private link, complete remaining details and explain the
   showroom review/next action. Reconfirm a changed offer without mistaking it for an
   approved agreement.
3. Set up an approved login and find that plan's first-payment action. Explain future
   start, paused payment, Test checkout and pending confirmation/allocation correctly.
4. Recover an expired setup link; explain that the showroom issues replacement access.
   Existing customers apply again without repeating held profile details.
5. Explain why an unconnected Google identity cannot sign in, and how to connect the
   matching verified email after password login.

Record task completion, wrong turns, misunderstood terms and requested help separately
from public funnel counters. Use no contact details, private URLs, passwords, payment
references or identifiable session recordings in analytics/test notes. Acceptance:
participants can identify stage/next action and distinguish application, approved
agreement, login and verified payment; the reviewer confirms accurate financial and
consent language, mobile fit and no untranslated essential steps. Resolve observed
confusion and obtain owner language review before any translation rollout. This phase
prepares the protocol; participant testing and translation publication remain follow-up.

## Customer and owner workflow audit — 22 October 2026

Qualitative browser inspection of the committed local candidate used Chrome at
1440x1000 and 390x844 with isolated synthetic PostgreSQL, in-memory email and dummy
Razorpay Test configuration. Scope/findings, proposed organization and the optional
HTMX pilot are recorded in
[Future work](FUTURE_WORK.md#browser-workflow-audit--22-october-2026), `FW-UX-004`/`005`.
Thirty customer fixtures exercised the existing 25-record pagination: search returned
26 matching records and page two retained the query. Recorded mobile document widths
for intake, customer dashboard and owner Today were 375/375px; long stacked content
remains a usability finding. No provider/browser timing is presented as performance
evidence and no participant or conversion results are claimed.

Inspection used existing synthetic password login, GET forms/navigation/search and
the existing protected progress-access POST. It did not submit approval, payment,
rate publication, cash recording/correction, invitation resend, account deletion or
new credentials. Service-created financial fixtures were confined to the disposable
audit database. Saved screenshots include `.uv-cache/audit-customer-desktop.png`,
`audit-customer-mobile.png`, `audit-owner-today-desktop.png`,
`audit-owner-today-mobile.png`, `audit-owner-payments-mobile.png` and
`audit-progress-mobile.png` (all under `.uv-cache`). The audit server/database was
removed, viewport reset and temporary tab closed. No application code or production
configuration changed; this does not replace regression tests for a future UI/HTMX
implementation or a complete keyboard/screen-reader/accessibility acceptance run.

Expired Checkout operations regressions live in `schemes.tests.test_expired_checkouts`.
They cover shared expiry boundaries, all-mode and missing-order visibility, queue
pagination, aggregate redaction, recent/exact/grace/age/limited provider inspection,
provider errors, owner/CSRF/method guards, signed review binding/tampering/expiry,
fresh changed-provider evidence, capture during inspection and unchanged balances.
`CheckoutTimerTests` execute the wrapper with deterministic Docker/curl boundaries,
including combined failure routing, secret-URL redaction, delivery errors and missing
required heartbeat configuration. No real provider or monitor is contacted by tests.
