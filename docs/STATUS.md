# Project Status

## Current milestone

**24 October 2026 — expired Checkout operations hotfix (local candidate).**
Expired pending Razorpay attempts now participate in the owner Today/exception queue,
category pagination and aggregate financial alerts across all provider modes. The
owner can inspect an exact attempt via CSRF-protected POST, review its order and
payments, and confirm closure using a ten-minute signed owner/payment/state-bound
review. Apply performs a fresh provider read and uses the existing locked/audited
service. Unexpired, changed, cross-mode, attempted or uncertain records remain held;
expiry alone never fails a payment or creates/removes entitlement.

The command defaults to the stored Checkout deadline plus five minutes of grace,
with optional legacy hour filtering and exact contribution selection. Monitoring
gets aggregate-only output and a failure exit for the entire unresolved expired
backlog, including other modes, missing provider IDs and rows outside the inspection
batch. The five-minute systemd job combines allocation/webhook and expired-checkout
checks in one heartbeat. Its three-order provider batch fits the four-minute service
timeout at the gateway's maximum request timeout; later rows remain visible/alerted.
The unit requires configured external heartbeat delivery and cannot report success
when it is absent. Neither the timer nor GET requests mutate financial records.

An isolated `fix/expired-checkout-operations` checkout contains only this hotfix;
unrelated local plan-governance and account-deletion development is excluded.
Initial 104 affected tests passed. Final isolated focused verification passed all
73 expired-checkout/Razorpay tests (67.458 seconds, normal hashing), with Django
system/migration-consistency checks clean. A 558-test initial isolated broad run
had only the Windows curl-stub test failures; the executable boundary fixture was
corrected and its combined routing, required configuration and delivery-error tests
pass. The final configured-instalment/expiry run passed all 62 tests (141.495
seconds, normal hashing). Both push and pull-request Django/container checks passed
for implementation commit `80f43b1a90676e2746b3666ac706a31439d73cf9` in draft PR #76;
the full hosted suite passed all 558 tests (push run 40065410966: 212.533 seconds).
No image was published because this is not protected main. Systemd verified both units on the production OS
using temporary files, without installation. Synthetic desktop and 390px mobile
layout/form order were inspected with database access forbidden; no overflow was
found and the viewport/preview were closed afterward. No schema change, production
deployment, new timer activation or external notification is claimed.
The owner clarified that Better Stack is already in use, as the canonical production
runbook specifies. The missing financial-heartbeat timer/configuration on the inspected
host did not establish that external monitoring was absent. The initial recommendation
to create Healthchecks.io was mistaken and is withdrawn; no new monitoring account is
required. Verify/reuse or add the financial-exception heartbeat in the existing Better
Stack account and exercise delivered failure/missed-heartbeat/recovery before activation.
On 24 October, the JSK Better Stack account (`admin@jaishrikrishnajewellery.com`,
team `t585600`) was verified and its empty heartbeat list confirmed. Created
`JSK financial exceptions` (heartbeat `516408`) with a five-minute period,
six-minute grace and email notifications. The Free account reports that all team
members receive incident notifications; no plan upgrade was made. Saved settings
were read back. Its secret URL was transferred over SSH into
`/opt/jsk/secrets/observability.env`, verified root-owned with mode 0600 and LF
line endings, and the temporary local secret was removed without printing it.
The heartbeat remains Pending, awaiting its first ping. No test alert, production
timer activation or hotfix deployment occurred; failure delivery, missed-run and
recovery acceptance remain pending activation of the reviewed release. Both push
and pull-request Django/container checks also passed for documentation commit
`c32ddc5c3ab71d2cb209969c9280c849e5bfc915` (runs 40070788281 and 40070791358).
These alerts concern unconfirmed expired provider checkout attempts and go to the
owner/operator. Customer emails about scheduled unpaid contributions are a separate
reminder policy and are not implemented by this hotfix; flexible agreements must not
be assigned invented overdue instalment obligations.

**Release candidate in draft PR #75 (22 October 2026).** Draft UI PR
[#75](https://github.com/rajeshr188/jsk-ss/pull/75) is isolated on
agent/customer-owner-ux-release, stacked on the existing Google Play foundation (#74),
which is unchanged. Implementation commit 7aeb3e3 includes the accepted workspace refinements;
7d07cf2 contains the earlier plan-first conversion phases. No PR has been merged.

Initial PR CI run 39761162836 built the image but rejected five fixable critical findings:
PyJWT 2.10.0 (CVE-2026-102268), certifi 2024.8.30 (GHSA-6q48-6c7w-9gw2), and Pillow 12.3.0
(CVE-2026-112393, CVE-2026-112403, CVE-2026-112900). The initial local image below is
superseded and must not be promoted. Targeted lock resolution changes only certifi to
2026.10.19, Pillow to 13.0.0 and PyJWT to 2.15.1; explicit uv security floors prevent fresh
resolution from selecting older vulnerable versions. Django, Wagtail, allauth and the
financial architecture are unchanged. All **116 media/CMS/Google-auth/storage regressions pass
in 64.247 seconds** with the patched dependencies. CI also exposed a preserved legacy-form
amount that still lacked grouping when enrolment requests were disabled. The legacy template
now uses the same INR formatter; the funnel test explicitly covers both switch states, instead
of inheriting local .env behavior. All **64 funnel/legacy-registration/plan-application regressions
pass in 17.688 seconds**. The dependency-only image passed the internal restore/upgrade and
Gunicorn/static checks; a final image includes the legacy-format correction. Follow PR #75's
current-head checks for the authoritative full regression/security result. No scan bypass or
severity suppression was added.

Replacement local image: jsk-savings:ui-release-20261022-rc-f57a8bb44665, local image ID
sha256:4052110e1e50d1ad674a79e027bc91d832a6da1c66095a975f50ffd39e2a743a. Its uv.lock SHA-256 is
2dc3fbeadd82 (prefix); full source/lock/package fingerprints and container evidence are retained
in .uv-cache/ui-release-security-20261022/. The old b1607523 image is not a deploy candidate.
Fix commit 71eb8c6 contains only the three dependency floors/lock changes, legacy offer grouping,
explicit flag-state test coverage and release evidence. PR checks remain authoritative for its
current head; neither a local image ID nor a passing synthetic config check is a published digest
or approval for production. No merge, production migration/deployment or provider change occurred.

Maintainer references: [certifi advisory](https://github.com/certifi/python-certifi/security/advisories/GHSA-6q48-6c7w-9gw2),
[Pillow 13.0.0](https://github.com/python-pillow/Pillow/releases/tag/13.0.0),
[PyJWT 2.15.1](https://github.com/jpadilla/pyjwt/releases/tag/2.15.1).

**Owner/customer local acceptance recorded; local release candidate verified
(22 October 2026).** The owner reported testing both owner and customer roles locally and
being satisfied. This closes local stakeholder acceptance; no independent customer study,
Tamil review, task timing or conversion uplift is inferred. The source fingerprint still
matches the accepted preview: 03ece8a68849506f012217c2ccfe2a95f982b0a27d251760586966b905814c40.
The disposable usability preview was stopped and its fixture database removal confirmed.

A curated source snapshot excludes local secrets and unrelated untracked notes. The existing
Dockerfile and unchanged uv.lock build successfully with production collectstatic (229 files,
659 post-processed). Local image: jsk-savings:ui-release-20261022-03ece8a68849; local image ID:
sha256:b160752354552a928b4d0a0e3e017a146b3807e9f624a0ebc32b0b6eb5404ddb.
This is a local image ID, not a published registry manifest digest or production authorization.

The exact image passed a synthetic PostgreSQL 16 dump/restore and pending-migration upgrade
on an internal-only Docker network, with no published ports. It ran as app with a read-only
root filesystem, dropped capabilities and no-new-privileges. Historical records/liabilities,
legacy access, scoped owner fragments and permissions, changed-term reconfirmation, repeat-safe
approval, activation-mail recovery and approved-plan continuation all passed. Hashed static
manifest lookup and actual Gunicorn HTTP readiness, liveness and static serving passed.
Deployment configuration checks passed with synthetic settings; email stayed in memory during
journeys. The separate config-only check substitutes a dummy SMTP/R2 configuration and does
not establish real delivery or storage access. Temporary containers, PostgreSQL volume,
internal network and fixture environment file were removed. No production endpoint, database,
provider configuration or feature switch was changed.

Caddy configuration validates in the locally cached 2.11.4 image with networking disabled.
All **536 serial full-suite regressions pass in 512.591 seconds**, with process exit code 0.
Django checks, migration consistency, JavaScript syntax and whitespace checks pass. Earlier
full/targeted evidence remains below; the latest run includes the rehearsal isolation guards.

The existing Google Play PR #74 is left unchanged. The UI release will use a separate stacked
branch based on its existing foundation, including the earlier local plan-first implementation
commit 7d07cf2, so the Google Play review is not repurposed. CI/critical vulnerability scan,
published digest, actual staging/log-sink/provider acceptance and separate production approval
remain release gates. Broader customer/Tamil research remains a follow-up, not claimed complete.

## Previous milestone: local restore rehearsal

**Local workflow restore/upgrade rehearsal passed (22 October 2026).**
The owner selected isolated local rehearsal first. The UI implementation below remains
complete locally; this step adds a repeatable release-verification tool and acceptance protocol,
not a runtime feature, schema change, deployment or production authorization.

Run `python -m schemes.rehearse_workflow_release --synthetic-local` with the documented local
environment. The final run completed in **29.840 seconds** with exit code 0. It created two
fresh random loopback PostgreSQL databases, built a synthetic pre-conversion schema baseline
(accounts.0006, schemes.0020, pages.0001), seeded historical identities/registration/invitation/
enrolment and financial evidence, performed actual pg_dump/pg_restore, then applied:

- accounts.0007_planapplication_planapplicationconfirmation_and_more
- accounts.0008_customerinvitation_recovery_requested_at
- pages.0002_publicfunneldailycount

Every legacy identity/registration/invitation/enrolment and financial row remained unchanged
through restore/upgrade. Legacy invitation recovery starts null, and no application history was
fabricated. INR 500.00, 0.100000 g gold and 10.000000 g silver remained separate fixture
liabilities. Eight owner page reads, customer Home/Applications/Documents, all three historical
statements, four owner fragments, customer denial and expired-fragment login recovery passed.
Reads changed no financial evidence. Existing application database was not copied or migrated.

The restored candidate then blocked changed-term approval, accepted renewed confirmation,
returned the same agreement on approval retry, retained failed-email evidence after commit,
recovered using a replacement in-memory invitation, activated the synthetic login and continued
to its approved plan. Activation did not create a payment. Historical financial rows remained
exact after new evidence was appended. Five existing integrity commands passed: public
registrations, enrolment requests, graded rates, showroom cash and auth-email uniqueness.

All **64 targeted regression tests pass in 15.971 seconds** with process exit code 0, including
application/concurrent-approval, activation, audit-completion and new rehearsal isolation guards.
Both guard tests pass again after the final fixture/snapshot polish. Non-local hosts, connection
option overrides, missing opt-in and custom database arguments are rejected. Django checks,
migration consistency and whitespace checks pass. The previous 534-test full UI suite remains
the latest full-suite result; this tooling-only step did not rerun it. No customer/owner UI changed,
so prior desktop/mobile evidence below remains applicable rather than being reported as a new
browser run. Two final temporary databases and synthetic dump files were removed; no server or
scheduled job was started. Outbound email stayed in memory and external network access was blocked.

MVP_PLAN, TESTING, FUTURE_WORK and PRODUCTION_DEPLOYMENT now contain the rehearsal procedure,
explicit dependencies and a customer/owner task/evidence protocol. Remaining external acceptance:
exact candidate image/CI/static manifest and proxy on isolated staging, approved sanitized backup
provenance, JavaScript-disabled browser rehearsal, actual log-sink redaction, provider acceptance,
real customer/owner observations and reviewed Tamil/business copy. No participant results or
conversion lift are claimed. No production/environment/provider change, feature activation,
production restore/migration or financial backfill occurred. Postmark is unchanged.

## Previous milestone: remaining UI audit implementation

**Remaining approved UI audit implementation completed locally (22 October 2026).**
FW-UX-004/005 now distinguish completed local implementation from outstanding staging,
real-user acceptance and production rollout. The remaining-audit checklist in MVP_PLAN.md
records the boundaries; lazy history and automatic polling remain conditional follow-ups.

Applications have scoped stage tabs/counts (attention, waiting, decisions, all) using the
existing bounded union selector; linked identity/plan applications count once. Private
progress shows contact, email, details/terms, showroom review, login and first real payment.
Only successful Live online or showroom-cash records complete payment; Test/practice,
pending/failed/closed and reversed attempts do not. Approved agreement snapshots remain
valid after public offer edits; legacy agreements gain no invented application history.
The approved private-progress path also fixes a missing reverse import exposed by regression.

Owner Access & privacy shows exact-customer privacy requests, 25 per page, and review now
retains shared customer context with a direct return. Money/rate formatting and document/
request return/cancel paths are consistent. Full printable financial history and quantity
precision remain intact; Test/practice acknowledgements and statement entries explicitly
separate those records from live money without changing balances or historical records.

Read-only HTMX now covers owner Customers, Applications, Contributions and Exceptions plus
manual customer payment-status refresh. Filters replace results, counts, totals, customer
context and CSV links together; category/order exceptions retain bounded SQL pagination.
Normal GET fallback, authorization, private no-store/history restrictions, stale-request
replacement and full-login recovery remain intact. Approval, payment, verification, setup
and privacy mutations retain ordinary protected flows; no polling, provider reads or automatic
mutation retries are introduced. Invalid filter guidance uses readable field errors and
shows no records until corrected, without exposing Django's internal non-field error key.

Verification: all **534 serial full-suite tests pass in 462.660 seconds**. The preceding
533-test run found two display assertions expecting ungrouped amounts; expectations were
updated for the intended grouped presentation before this clean run. No financial safeguard
was weakened. All **55 final targeted regressions pass in 26.146 seconds** after the last
filter-error copy change, covering audit completion, workspaces, documents and public funnel.
Django system checks, migration consistency, JavaScript syntax, static collection dry-run and
whitespace checks pass; all 33 canonical local Markdown links resolve. There is no new
schema migration or financial backfill.

Synthetic full/fragment HTML payloads were Applications 12,058/5,422 bytes, Contributions
12,782/6,152 bytes and Exceptions 8,266/1,634 bytes with the same scoped fixture rows. This
measures payload, not actual latency, task completion or conversion improvement.

Browser inspection at 1440x1000 and 390x844 used fictional fixtures, isolated PostgreSQL,
in-memory mail and dummy Test keys. Checked owner stage navigation/counts, applicant search
and review return, exception category/order, customer-scoped payment filters with synchronized
CSV/totals/focus, invalid dates, retained results and visible retry guidance after a synthetic
503, privacy history/review return, protected pending/approved progress, customer Home and
statement/receipt formatting and navigation. Mobile Applications and documents have 375px
content/viewport widths without page overflow. Financial/approval/credential/Google/deletion
actions were not submitted through the browser. This is not participant or screen-reader
certification. Proof is in .uv-cache/audit-completion-applications-desktop-final.png,
audit-completion-applications-mobile-final.png, audit-completion-progress-desktop.png and
audit-completion-receipt-mobile.png. Temporary preview databases were removed, the browser
tab closed and the viewport reset.

ARCHITECTURE, DOMAIN_RULES, ADR-0011/0012, plan, backlog, testing and deployment guidance
are updated. No production deployment/data/environment/provider change or feature activation
was performed. Postmark remains unchanged. Next: restored-staging rehearsal and real customer/
owner task testing, followed by separately approved production rollout and funnel measurement.
Missing approved business copy/response window and reviewed Tamil testing stay FW-UX-002/003.

## Previous milestone: initial workflow refinement

**Approved customer/owner workflow refinement implemented locally (22 October 2026).**
The work follows FW-UX-004/005 and the ordered checklist in MVP_PLAN.md. Owner navigation
now groups Today, Customers, Applications, Payments, Settlements and Administration, with a
persistent desktop rail and mobile drawer. Today links current rate/payment blockers and due
privacy/settlement work. Applicant search is bounded; review links/POST returns retain an
allowlisted local inbox query. Customer context groups Summary, Applications, Plans, Payments,
Documents and Access, with bounded agreements/receipts and fewer repeated identity fields.

Payment lists and recorded-payment CSV share validated scope; invalid filters fail closed.
Selected-record Live/cash, Test/practice and correction totals are explicit and whole-business
cards are disclosed separately. Cash GET explains pending online attempts and other blockers
before amount entry; original preview/commit/recovery safeguards remain authoritative.
Customers have task-specific navigation, actionable Home stages without duplicate payment
buttons, Applications/Documents, bounded history and agreement snapshot terms, document return
links, contact autofill/tel inputs, month units, optional-message disclosure and stage guidance.
Legacy cash history and its unavailable-payment explanation remain visible.

HTMX 2.0.11 is pinned locally (upstream license/official integrity hash) for owner customer
search/paging and manual recorded-payment status refresh only. It debounces/cancels stale
reads, retains normal GET fallback and provides loading/error/empty/focus feedback. Existing
authentication/permissions apply to every fragment. Private responses are no-store with Vary;
private history snapshots and dynamic script execution are disabled. Lost fragment sessions
navigate to full login. No automatic polling, optimistic financial result or mutation retry is
introduced. Prepared Caddy query/Referer/Hx-Current-Url stripping and Django private-query
redaction avoid logging new search/return details; no analytics events or personal fields added.

Verification: all **524 serial full-suite tests pass in 516.091 seconds**. Initial display
assertions were updated for grouping/menu/filter copy, and missing legacy-cash guidance was
restored before this clean run. The earlier 143-test affected run exposed one extra label-count
assertion, corrected to check the actual payment badge rather than the new filter option.
All **65 targeted workspace/application/reminder regressions pass in 25.499 seconds**
after presentation polish. Final payment search also covers plan name/code alongside
agreement/provider references; all **24 final selector/workspace regressions pass in
4.550 seconds** after that addition.
Django checks, migration consistency, JavaScript syntax and static collection dry-run pass.
The prepared Caddy file validates in the existing local image with networking disabled; a
separate loopback-only synthetic request confirms masked query, removed Referer/HX current URL
and preserved status/path. No production configuration was loaded or changed.

Browser inspection uses fictional fixtures in disposable local PostgreSQL, in-memory email
and dummy Test keys. Desktop 1440x1000/mobile 390x844 cover role navigation, queues, applicant
search/review return, customer context, scoped payment records/cash blocker, contact/error
focus and protected progress, actionable Home, documents/returns and manual status refresh.
HTMX search/paging/focus and a synthetic 503 preserve the previous result with visible guidance;
lost-session navigation goes to full login and resumes the selected search after sign-in.
Financial/approval/resend/new-credential/Google/deletion actions are not submitted through the browser.
Final customer document widths match the viewport (375/375px mobile, 1425/1425px desktop);
all five mobile customer navigation links fit without a horizontal scrollbar. Proof is retained
in .uv-cache/refinement-owner-desktop.png, refinement-customer-desktop.png and
refinement-customer-mobile.png. Both disposable preview databases/servers were removed,
the temporary browser tab closed and the viewport reset. All 31 canonical local Markdown
file links resolve and whitespace checks pass.

ARCHITECTURE, DOMAIN_RULES, ADR-0011/0012, testing, plan, backlog and deployment guidance are
updated. No new migration, production deployment, normal-database migration, financial backfill,
environment/provider change or feature activation. Postmark remains unchanged. Next is restored
staging rehearsal and real-user task testing followed by separately approved production rollout.
Tamil review/testing and missing approved business copy/response window remain FW-UX-002/003;
additional HTMX filter/history/polling expansion remains conditional on measured need.

## Previous milestone: customer conversion redesign

**Customer conversion redesign, Phase 4 implemented and verified locally
(5 October 2026).** Linked-plan activation now continues through password sign-in to
the scoped agreement. Dashboard application updates precede agreement balances;
payment next actions use server records and availability, with Test/practice labels.
Expired setup links can request owner help through a CSRF-protected, idempotent POST;
owner-only invitation replacement is preserved and Today has bounded recovery queues.
Additive `accounts.0008` adds one nullable recovery-request timestamp. Google eligibility
copy is clarified and Tamil testing is prepared in English without publishing translations.
All **514 serial full-suite tests** passed in 469.374 seconds, followed by all **130
focused regressions** in 72.856 seconds after final dashboard/copy refinements. This
includes invitation replay/CSRF/expiry, scoped activation-to-password-login continuity,
owner recovery/failure/pagination, social eligibility, legacy access, plan approval
concurrency and financial/payment operations. Django checks, migration consistency
and whitespace checks pass. Fixed contribution form defaults remain intact; only
linked variable first-payment preferences are prefilled, with normal validation.

Desktop (1440x1000) and mobile (390x844) inspection covered approved-plan setup without
entering new credentials, expired-link/help confirmation, password login with its
approved agreement destination, prominent dashboard review/payment stages, the saved
first-payment amount, Test/pending status, Google connection instructions and owner
Today/recovery queue/customer resend evidence. Document widths match the viewport
(mobile 375/375px and desktop 1425/1425px). Final dashboard proof is retained in
`.uv-cache/phase4-dashboard-desktop.jpg` and `.uv-cache/phase4-dashboard-mobile.jpg`.
Financial actions, new credentials and provider/Google connection were not submitted
in browser inspection; service/HTTP regressions verify outcomes. All fixtures were
synthetic in separately named local preview PostgreSQL with in-memory mail. The preview
database/server was removed, viewport reset and temporary tab closed.

ADR-0011/0012, domain rules, architecture, testing and deployment guidance are updated.
`accounts.0008` is additive metadata only; no historical or financial backfill is
performed. No production deployment, normal-database migration, actual environment
configuration change or feature enablement is made. The earlier Phase 1/3 pending
migrations remain combined release dependencies where not yet deployed.

All four approved implementation phases are now complete locally. Remaining release
work is owner review and separately approved staging/production rollout. The prepared
Tamil protocol in `TESTING.md` still needs reviewed terminology/translations and actual
participant testing; no unreviewed translation is published. Approved marketing
descriptions/benefits and a showroom response window remain missing business inputs;
none were invented. No additional implementation phase is prescribed by this plan.

Backlog reconciled on **22 October 2026** against committed implementation
`7d07cf2`, recorded regression/browser results and canonical release evidence.
[Future work](FUTURE_WORK.md#review-checkpoint--22-october-2026) now separates local
completion, accepted production foundations and outstanding external acceptance.
`FW-UX-001` tracks conversion rollout/measurement, `FW-UX-002` missing approved copy
and review-window input, and `FW-UX-003` reviewed Tamil testing. Deletion implementation,
enablement and authenticated zero-history completion are recorded as done; the
signed-out path/provider/recovery evidence remains open. Android Internal Testing
and verified origin association are recorded as done, with public release/pilot
acceptance still pending. No live provider/Console/production state was rechecked,
application behavior changed, migration applied or deployment performed by this review.
All 69 prior backlog identifiers are preserved; 37 active/conditional entries now
include the conversion follow-ups, SES migration and UI/HTMX proposals below. All 19 local Markdown links in the five
affected documents resolve, Django system checks report no issues and whitespace
checks pass. Application regressions were not rerun for this documentation-only change;
the implementation acceptance figures above remain their original recorded runs.
Earlier checkpoint evidence below remains historical unless explicitly superseded.

At the owner's request on 22 October, `FW-PROD-008` records a planned Postmark-to-SES
SMTP migration: domain/region/production-access setup, restricted credentials,
bounce/complaint and delivery operations, untracked private links, provider/privacy
wording, email regression/smoke tests and an approved cutover with Postmark rollback.
Postmark remains the current provider; no credentials, DNS, SMTP settings or production
services were changed. This backlog addition does not authorize migration execution.

Customer/owner browser workflow audit completed on **22 October 2026** against the
local candidate in isolated synthetic PostgreSQL, in-memory email and dummy Test
configuration. Chrome desktop 1440x1000 and mobile 390x844 inspection covered public
plan application/progress, customer login/dashboard/agreement/payment status/documents/
another-plan entry and owner Today, navigation, review/filtering, customer search/page
two, payments/cash entry, operational controls/rates, eligibility and recovery queues.
The application intake, customer dashboard and owner Today had no document-width
overflow at mobile size (375/375px); long stacked layouts and repeated primary actions
remain usability findings, not conversion measurements. Recorded issues include
missing applicant lookup, lost filtered-review return context, global payment totals/
CSV under customer scope, late cash-blocker explanation, document return paths and
technical terminology. Existing search pagination, financial/status safeguards and
profile reuse remain strengths.

The detailed findings, proposed navigation and acceptance criteria are in
[Future work](FUTURE_WORK.md#browser-workflow-audit--22-october-2026): `FW-UX-004`
for organization/presentation, `FW-UX-005` for a bounded HTMX search/filter pilot.
Official HTMX documentation was reviewed; it is not installed or implemented.
Read-only fragments fit the current Django architecture, but private history caching,
session expiry, response races, accessible feedback and normal-page fallbacks need
explicit handling. No consequential financial, approval, resend, deletion or credential
action was submitted through browser inspection. Screenshots remain in `.uv-cache/audit-*`.
The audit server/database was removed and the browser viewport reset/tab closed.
No production state/configuration or application source was changed. This review is
not user testing, measured performance, a complete accessibility audit or an HTMX
architecture acceptance decision; implementation proposals remain pending.

### Phase 3 baseline (completed locally)

**Customer conversion redesign, Phase 3 implemented and verified locally
(5 October 2026).** Contact-first intake now persists selected plan/grade/preferences,
remaining address and current-offer/start-date confirmation follow email verification,
and protected progress uses a separate expiring credential/session. Coordinated owner
approval links separate identity and agreement records transactionally, with retained
confirmations, after-commit activation delivery and legacy/existing-customer access.
Additive migration `accounts.0007` creates the application/confirmation tables only;
no historical intent backfill, production deployment or production data change is made.
All **494 serial full-suite tests** passed in 444.595 seconds, including PostgreSQL
concurrent approval and rollback checks. After the final copy, cache and expiry
refinements, all **136 focused regressions** passed in 104.440 seconds. Django checks,
migration consistency and whitespace checks pass. The older invitation migration
test now restores all current schema leaves at teardown; this fixes test isolation,
not production data or migrations.

Desktop (1440x1000) and mobile (390x844) inspection covered contact intake and retained
validation values, protected email verification, remaining details, private progress
access, completed review/support, owner queue and coordinated review/confirmation
history, and existing-customer requests without repeated profile fields. The affected
pages fit their viewport without document overflow. Financial approval/payment and
new credentials were not submitted in the browser; service/HTTP regressions verify
those outcomes. Synthetic records and in-memory email used a separate local preview
database, removed with the preview server after inspection. Review screenshots remain
in `.uv-cache/phase3-owner-review-desktop.jpg` and the Phase 3 mobile preview images.

`MVP_PLAN.md` records completed acceptance criteria; ADR-0011/0012, domain rules,
architecture, testing and `PRODUCTION_DEPLOYMENT.md` describe the new boundaries and
additive migration/rollback precautions. The existing feature flags were not enabled
in production; the normal database and actual environment configuration are unchanged.
Material offer/policy changes or a missed requested start date require renewed customer
confirmation. Expired applications cannot receive unusable replacement links or be
approved, and progress replacement never extends expiry. Notification failures remain
visible and recoverable; provider acceptance is not claimed as customer receipt.

At the Phase 3 checkpoint, the next scope was Phase 4: activation continuation into the approved plan and first-payment
state, prominent dashboard progress, expired activation recovery, linked-Google
eligibility and preparation for reviewed Tamil testing, now implemented above. Approved offer descriptions/
benefits and an achievable showroom response window remain missing business inputs;
none were invented. Production deployment and production data changes await approval.

### Phase 2 baseline (completed locally)

**Customer conversion redesign, Phase 2 — owner workflow implemented and verified
locally (5 October 2026).** The owner authorized this phase after Phase 1.
The implementation checklist and acceptance
criteria are in `MVP_PLAN.md`; production rollout remains separately approved.

Owner sign-in now opens Today. It shows financial exceptions and applications needing
attention, with counts, jump links and at most 8 records per queue. Verified identity
reviews precede plan reviews and verification delivery/expiry recovery; unresolved
expired plan requests remain visible until explicitly closed. The unified Applications
inbox supports stage/type filters and fixed 25-record pages across both record types.
Financial exceptions also paginate in SQL before loading evidence and link directly
to the affected contribution or supported recovery screen. Unsupported webhook types
remain visible without a broken recovery action; Test/method labels remain explicit.

Customer search covers name, email, mobile, customer number and scheme number, capped
at 100 characters with 25-record pages and stable ordering. Agreement counts use an
aggregate; the customer list/detail no longer loads every contribution. Historical
registration/request lists remain available and paginated. Registration and agreement
review share one layout/next action; plan snapshots, preferences, confirmation and
conversion form are on one page. Current offer, expiry and customer-login eligibility
govern action visibility, with all authoritative service guards retained. Approval
and rejection reason labels have distinct targets on the shared identity screen.

Customer context links related reviews, payments, recovery, cash recording/correction,
redemption and statements/receipts. Applicant linkage uses the explicit approved-user
relationship, never an unverified email match. Inactive customer login is labelled
accurately and has no resend invitation action. Owner access explicitly requires an
active owner/superuser; CMS/staff access alone grants no permission. Owner navigation
is Today, Applications, Overview, Customers and Operations; public/customer navigation
and existing customer access remain supported. Mobile payment/history tables render
as labelled rows; no duplicate financial forms or financial history changes are added.

Verification: the 54 existing focused regressions and 14 new workspace tests passed,
followed by all **460 serial full-suite tests** in 484.288 seconds. After the final
distinct-label and customer-login eligibility refinements, all **68 focused tests**
passed again in 33.019 seconds. Django checks, migration consistency and whitespace
checks pass. Desktop (1440×1000) and mobile (390×844) inspection covered owner landing,
queue jumps, inbox/filtering, identity/inline agreement review, customer search with
retained-query page navigation, customer records, exact-payment review, receipts,
statements and recovery controls. Both owner payment table dimensions fit their
containers (mobile 351/351px, desktop 1154/1154px) after overriding the inherited
table minimum width. Customer dashboard/history/documents have no owner context;
direct customer access to the Applications inbox returns 403. Financial forms were
not submitted in the browser and no provider operation or real email was performed.
Fictional fixtures lived only in a separately named local preview database, removed
with the preview server after inspection. Screenshots are retained in
`.uv-cache/phase2-review-desktop.jpg` and `.uv-cache/phase2-today-mobile.jpg`.
Printable statement/recovery evidence tables retain their existing inner horizontal
scrolling on mobile; owner payment and historical review rows use the new mobile layout.
No Phase 2 migration, new architecture component or feature enablement is required.
The normal application database and production configuration/data were not changed. The
Phase 1 aggregate migration remains pending for a combined release; release/rollback
guidance is in `PRODUCTION_DEPLOYMENT.md`.

At the Phase 2 checkpoint, the next scope was Phase 3: durable plan/grade/preferences through verification, contact-first
intake, coordinated transactional identity/agreement approval, material-offer
reconfirmation and protected progress, now implemented above. Phase 2 shared the workspace while retaining
separate approval services and historical records. Activation continuation/recovery
and Tamil testing remain Phase 4. Approved offer benefits/descriptions and an achievable
review window remain business inputs; none were invented. Production deployment and
production data changes await separate approval.

## Phase 1 baseline and verification

**Customer conversion redesign, Phase 1 — implemented and verified locally
(5 October 2026).** The owner approved the four-phase product direction
and requested Phase 1 as a reviewable change. Acceptance criteria and dependencies
are in `docs/MVP_PLAN.md`. This supersedes the previous immediate implementation
priority; the historical mobile/deletion release evidence below remains valid.

Review against current code confirmed separate registration and enrolment reviews,
public links that lost selected-plan context, unreviewed free-text offer descriptions,
and payment-operation gating on agreement detail but not dashboard cards. Phase 1
adds a shared compact offer card using live plan amounts, frequency, duration and
active grades, plan-specific entry with a truthful registration summary, and factual
jewellery copy. Existing account/registration/enrolment routes remain supported.
Stored plan descriptions and agreement snapshots are not rewritten.

Daily public GET counters store only day/stage/count, default off behind
`PUBLIC_FUNNEL_MEASUREMENT_ENABLED`. `report_customer_funnel` combines these totals
with source-record period throughput, separating verified Live online payments from
Test payments and showroom cash. It reports first payments against full history and
current allocation backlog. Counts are origin requests (including repeats/bots), not
unique visitors or a joined conversion cohort; cached traffic is not counted. Known
synthetic application records cannot yet be reliably excluded automatically.

Customer dashboard/detail use one read-only payment-availability selector. Customer
and owner history explicitly label `ABANDONED` attempts as closed after review.
Lost/rejected callback responses, checkout cancellation/failure and expiry lead to
recorded-status guidance without claiming financial success/failure from browser
events. The private no-store status page reads existing records and never verifies,
retries or mutates payments on GET; history links support later recovery. Financial
confirmation/allocation services, immutable evidence and permission boundaries stay
unchanged.

Verification: 106 focused tests passed, followed by all **446 serial full-suite
tests** in 499.708 seconds. The obsolete sign-in-primary copy assertion was updated
for the approved direction. After the final factual pending-credit wording and
privacy-version amendment, all 29 payment-presentation/registration regressions
passed, including the rendered JavaScript behavior test and closed-attempt status.
The parallel attempt could not complete because of an
existing migration-test isolation issue; serial results are the release evidence.
Django checks, migration consistency, migration SQL inspection and whitespace checks
pass. Browser inspection at 390×844 and 1440×1000 covered home/plan comparison,
expanded terms, selected-plan registration entry, customer pause/history/status and
owner dashboard/contributions. Preview fixtures were fictional and isolated; the
preview server and its database, plus the parallel test clones, were removed. A
mobile screenshot is retained in `.uv-cache/phase1-plan-mobile.jpg` for review.
The normal application database and production configuration/data were not changed.
The new privacy notice/default consent version is `2026-10-05`; release guidance
requires matching the explicit environment version without rewriting old evidence.

At the Phase 1 checkpoint, Phase 2 was next: Today queue, bounded customer search/
pagination and a unified owner review workspace. Cross-verification plan/grade/preferences, contact-first intake,
coordinated transactional approval, changed-offer reconfirmation and protected
progress remain Phase 3; activation continuation/recovery and Tamil testing remain
Phase 4. Owner mobile contribution tables still require horizontal scrolling.
No new benefits, support contacts, response promises or translations were invented.
Approved offer descriptions/benefits and an achievable review window remain business
inputs. The only new migration creates an empty aggregate table; rollout/rollback
guidance is in `docs/PRODUCTION_DEPLOYMENT.md`. Production deployment, migrations,
measurement activation and production data edits await separate owner approval.

## Previous milestone and deployment evidence

Immediate priority: **Google Play release preparation**, not implementation of
`FW-PROD-007`. The owner accepted the recovery-isolation rule after clarification:
restored systems remain private with payment/email/jobs disabled until latest
deletion decisions and newer financial facts are reconciled; missing evidence keeps
the restore isolated. This approves the procedure, not a production restore.
Next: the bounded deletion acceptance pilot, reviewer access and final Console
declarations in `docs/MOBILE_RELEASE_READINESS.md`. Any irreversible deletion
completion still requires explicit approval. After the reauthentication UI regression
was added, all 38 account-deletion/final-completion tests passed locally on
10 September; Django system checks found no issues.
The test runner recreated and removed its local `test_jsk_ss` database; no production
database or application configuration was changed.
Production activation preflight then passed on release
`7819fd9552825c61ebc34a7844ba346c7ad92488`: deletion is enabled with deletion and
registration-privacy policy versions `2026-09-10`; the public deletion route returns
200; account-deletion integrity reports zero requests and zero errors; financial
exceptions remain zero. At activation this exposed request intake but was not deletion
acceptance: no request, containment or completion had yet been exercised.
The first Play-installed authenticated deletion request subsequently reached
`CONTAINED` with the expected requested/verified/session-revocation/Google-removal/
containment/notice actions; login is inactive and integrity remains clean. Completion
is deliberately paused: contrary to the disposable zero-history assumption, its
customer owns two active `GOLD_24K_9999` agreements and one failed Test-mode Razorpay
contribution of INR 15,200 (zero allocations and redemptions). No completion decision
exists. The owner placed it under reviewed hold because the history is intentional
synthetic/test data; never erase or reactivate the login by ad-hoc database editing.
This containment result is partial pilot evidence, not end-to-end deletion acceptance.

The owner also reported that django-allauth's reauthentication page appeared as an
unstyled fallback during that review. Root cause: the project customized ordinary
account templates but had no `account/reauthenticate.html` override. PR #73 merged
the Bootstrap 5 project-layout override and regression test as release
`b349a84fdc716a87e85110386868923fad95326e`; protected-main CI, container publication
and the fixable-critical vulnerability scan passed. Production now runs immutable
image
`ghcr.io/rajeshr188/jsk-savings@sha256:d40c2875fd9ac6b42fb9f21528b392456151232ce0d0f5ecd3f40dd040ddc543`.
There was no migration. Both health endpoints, account-deletion integrity,
authentication-email integrity and financial exceptions passed, and the owner
confirmed the reauthentication page is styled correctly. Security semantics remain
unchanged.

The intended second zero-history deletion identity also proved to have one scheme
account and one enrolment request; it is not eligible as zero-history evidence and no
completion decision exists. Both inspected requests used the authenticated path, so
the public email-verification path still requires a fresh identity. Two
owner-controlled Workspace aliases were created and are awaiting mail propagation.
On 15 September the new authenticated-path candidate completed its seven-category
owner disposition with zero scheme accounts, enrolment requests, contributions,
allocations and redemptions. Production displayed one completed-with-retention
decision, no retained profile fields, accepted outcome notice with cleared recipient,
and the expected minimization/completion actions. The owner confirmed inbox delivery,
unusable password, failed Google recovery and clean deletion, authentication, Google,
financial and graded-metal checks. This accepts the authenticated zero-history path;
it does not prove the signed-out email-verification path.
No verification bypass or database marking is permitted. In parallel, the canonical
mobile-readiness guide now contains copy-ready Play listing text, store-asset and
screenshot specifications, a Play Console worksheet, reviewer instructions and a
manual-owner task boundary. This is submission preparation, not authorization to
upload assets, complete a deletion or submit the app for production review.

`FW-PRIV-001B` **disabled-stage production rollout accepted** on 10 September 2026
from owner-supplied Linode output and explicit smoke-test confirmation. PR #72 merged
as `7819fd9552825c61ebc34a7844ba346c7ad92488`; main CI and the published-image
fixable-critical vulnerability gate passed. Production runs
`ghcr.io/rajeshr188/jsk-savings@sha256:4f07a2b4a274130cca8bd079d6ffba60547cb2d49e3e9bf4aff39cfdbccaa806`.
Migration `accounts.0006_customer_deletion_completion` applied; web is healthy,
deletion integrity and financial exception checks pass with zero reported errors.
Caddy validation passed; both public health endpoints report the new release;
`/accounts/deletion/` returns 404; login, customer dashboard and Savings Plans work.
Deletion remains disabled with no completed requests. Confirmed recovery point:
10 September 2026 at **13:00 IST**, superseding the proposed 15:00 timestamp.
Rollback identity and detailed evidence are in `docs/PRODUCTION_DEPLOYMENT.md`.
The owner subsequently confirmed restricted business Workspace Drive storage and
a privately identified backup custodian: the encrypted synthetic Drive and USB
copies both decrypted successfully, and unauthorized Drive access was denied.
That closes the storage/access test only, not before/after decision reconciliation.
Three fictional JSON stages (intent/completion/latest review) have been prepared
outside the repository for the custodian's encrypted-copy recordkeeping exercise;
JSON validation passed. The owner confirmed the sequence-recognition exercise:
version 3 is latest, version 1 does not prove execution, and version 2 must not
restore fields removed by version 3. This is a tabletop exercise, not a production
decision reconciliation. Responsibility split accepted: the showroom owner reviews
obligations and approves decisions; Rajesh maintains the technical recovery record
and verifies Drive/USB copies after each decision change; the identified backup
custodian provides recovery cover. Review the request queue daily; no daily USB
recopy is required when decisions have not changed.
Both running containers use Docker's local log driver with `max-size=20m` and
`max-file=5` (owner output). Subsequent inspection shows journald forwarding to
active local rsyslog; syslog/UFW rotate weekly with four archives and a daily timer.
Rotation-service success and cloud-init/mail.err coverage remain unverified.
Website Logpush is unavailable on the reported Cloudflare Free plan; other export
mechanisms/provider-held data are not ruled out.
`FW-PROD-007` now tracks a budget-conscious security-log preservation plan, using
180 days as the CERT-In planning baseline for this sole proprietorship. The earlier
standalone 14-day/256-MB proposal is withdrawn. Repository inspection confirms
privacy filters and Docker size caps, not durable archival or complete security-event
coverage. Measure volume and approve a private destination before implementing;
no paid service, log upload, host change or cleanup was performed. Restore-isolation
procedure acceptance is recorded above; production restore execution remains untested.
This accepts deployment only: production recovery-record operation,
production restore handling, effective log/provider retention procedures, applicant
disposal and enabled Play-app acceptance remain open. Earlier local-only notes below
describe the preparation history, not the current deployment state.

ADR-0014 accepts a PWA and customer-only Android Trusted Web Activity as the first
mobile distribution path. `FW-MOBILE-002` is production-accepted in release
`049944412aa09668d6b04e45cabee2bc58dadc42`: the installable PWA uses reviewed
192/512 icons, a root-scoped network-first service worker, a generic offline response,
and safe disable/unregister behavior. Its cache contains only that offline response
and icons; no customer, authentication, financial, health, owner, or CMS response is
cached or queued. Offline submission and disable/re-enable cleanup passed without a
server mutation. The no-code
`FW-MOBILE-001` records the verified Play organization, registered permanent package,
and existing Play App Signing identity without storing private account data or the
D-U-N-S number. The originally recorded Play fingerprint is published on the
canonical origin in release `1826afec8628d4f9288c1625091974687af7aba0`. A signed
Internal Testing bundle was accepted by Play on 9 September 2026, and read-only
device inspection found that Play delivered it under an additional Google-managed
app-signing certificate. Release `0c611f6e51434aa7f0a3faa8ddba8ef492910af3`
now publishes both Play certificates; Google linked both, Android reported the
installed certificate and domain as verified, and the app reopened without browser
chrome. Account/recovery role evidence, qualified
policy/retention, deletion implementation, and final Data Safety gates remain open.
The private business-owned Android TWA repository now has an API
29-to-36 customer shell and a successful unsigned GitHub-hosted build; it adds no
mobile API, native provider integration, financial authority, or application secret.
The canonical mobile-readiness guide now contains the bounded Internal Testing
customer-journey matrix. On 10 September the owner confirmed authentication,
registration, enrolment, payments, and documents through the Play-installed app,
with approximately five pilot customers. These core journeys are owner-reported
passes; exact build/device metadata and individual negative-case evidence remain
unrecorded. Lifecycle, network, update/fallback, accessibility, checkout edge cases,
and privacy/log acceptance remain open. `FW-MOBILE-004` is underway.
The production-accepted `FW-AUTH-004`, `FW-ENROL-001`, and all financial boundaries
remain unchanged. ADR-0015 is accepted for staged implementation. `FW-PRIV-001A` is deployed
in production as a disabled verified-request, access-containment, owner-hold, and
integrity foundation without any anonymization/completion mutation. On 10 September
the owner accepted ADR-0015's revised owner-operated implementation boundary; a
qualified written retention matrix is no longer a blanket development prerequisite.
Local `FW-PRIV-001B` now includes the non-cacheable owner preview, structured
category dispositions, atomic/idempotent completion, erased-login/profile guards,
durable retryable outcome notices and retained-record reviews. New additive migration
`accounts.0006_customer_deletion_completion` is required; it performs no customer
erasure on migration. Completion itself requires recent owner authentication, exact
request confirmation and current obligation checks. Financial history is preserved,
and every supported completion discloses retained records. The production deletion
flag remains disabled; policy/procedure review, synthetic rollout acceptance and the
public-store deletion claim remain open. No production customer has been erased.
Verification on 10 September: the full 421-test regression run passed. After final
concurrent-edit guards and additional identity-minimization cases, all 95 accounts
tests passed again. Django checks, migration-drift checks and `git diff --check`
passed. A subsequent local rollout rehearsal on 10 September confirmed the default
database is `localhost:5432/jsk_ss` and applied only accounts migrations `0005` and
`0006`; unrelated pending Wagtail/blog migrations were left untouched. All 16 targeted
completion tests passed again, including the synthetic owner form, duplicate POST,
notice retry, retained-field review and financial-preservation journeys, using the
isolated test database and in-memory email backend. Local deletion integrity, Django
checks and migration-drift checks passed; the local deletion flag remains disabled.
The production guide now records the owner procedure checklist and isolated-restore
acceptance requirements. Actual provider settings, owner retention decisions and
restore suppression have not been verified by these tests. No production migration,
feature enablement, real-customer deletion, commit or push was performed.
Release preparation now includes an implementation-aligned disposition baseline in
ADR-0015 and revised Privacy/feature-gated deletion-entry wording. It distinguishes
the GST record baseline from unrelated personal data, review dates from disposal,
and application minimization from external-copy handling. Production policy-version
changes, provider settings, applicant disposal and restore suppression remain open;
this is not a completed retention schedule or Play acceptance.
The combined 68-test pages/deletion/completion regression run passed, including
enabled/disabled policy links and both public/authenticated retention disclosures.
Django checks, migration-drift checks and patch whitespace checks passed. This
wording increment adds no migration. The branch is being prepared for PR/CI review;
this does not authorize merge, production deployment or deletion enablement.
The 10 September synthetic local PostgreSQL dump/restore rehearsal also passed:
two fresh temporary databases, two synthetic customers, restored identity detected,
latest retention-review disposition reapplied, exact financial rows unchanged and
missing-request/financial-mismatch guards enforced. All temporary databases and
artifacts were removed. This proves only post-containment local recovery, not
production recovery-register durability or pre-request restore handling. The guide
records owner-confirmed 45-day Postmark activity retention, absence of retained
customer exports/paper/R2 documents, and the latest reported recovery point. Oldest
available backup and effective time-based log retention remain unconfirmed.

Wagtail 8.0 is production-accepted in release
`65eff0d80a2e23f5f7df1da9d610d7ae1ef26038`. Its isolated rollout applied only
Wagtail's additive `wagtailcore.0098_apitoken` vendor migration and preserved the
existing catalogue and editorial boundaries. The disabled-first `FW-CMS-004`
Jewellery journal foundation is now production-accepted in release
`6396371fa71cc4b53c2e4a92ee31b329a5c9419b`, using immutable image
`ghcr.io/rajeshr188/jsk-savings@sha256:55c8f840cb023ff8760bdbb0f602472787cfac2186c01bbc7d608c630d32db7c`.
The additive `blog.0001_initial` migration and isolated Blog groups, media collection,
draft root, publisher task, and approval workflow are installed and valid. At rollout
acceptance the public flag was disabled: `/blog/` returned `404`, no Journal
navigation was exposed, and no staff membership or article had been created.
Existing content/financial authority is unchanged. CMS authorization, R2 media, authentication, payment-operation, financial,
exact-grade, in-store-cash, Live Razorpay, and reconciliation checks passed before
payments reopened. Subsequently, the user assigned staff roles and reviewed the five
initial articles (hallmarking/HUID, savings in grams, family occasions, jewellery care,
and 22K/24K gold); the root and articles were published through Blog approval.
On 10 September 2026 the root title was changed to **Articles** through the same
workflow, retaining `/blog/`. Five newly generated featured illustrations were
uploaded to Blog media and saved with descriptive alternative text; all five revised
articles are verified **In Moderation**, leaving their previously published revisions
intact. Replacement-image approval remains pending; original images were retained.
Local navigation, footer, article eyebrow, accessibility labels, app display name,
and new-root default now use Articles, pending code release. Blog regression tests,
Django checks, and migration-drift checks pass; no migration is required. Public
feature-flag activation has not been independently verified in this content refresh.

Website-side Google Business Profile support is implemented locally, not deployed.
`pages/business.py` centralizes reviewed showroom identity for Contact/home/footer
display and home/Contact `JewelryStore` JSON-LD. Contact provides address-based Maps
directions; optional `GOOGLE_BUSINESS_PROFILE_URL` enables homepage/footer listing
links, the Contact review link, and schema identity/map references. The user supplied
`https://maps.app.goo.gl/TKpjGNXgNYpiFzDM7`; browser inspection on 10 September matched
the business name, phone, and 155 Azad Road address. The local environment and both
templates now include that public URL; production configuration/deployment remains
pending. Stakeholder consistency review remains for Google's Ramset Nagar locality
versus the site's Thorapadi wording, and its delivery attribute versus the website's
showroom-only scheme fulfilment. Existing approved website details are unchanged.
No Google credentials, embedded maps/reviews, tracking scripts, ratings, financial
authority, or migration are added. Updating Google's Website field remains a separate
stakeholder action. Prior Articles refresh changes are preserved on the working branch.
The 61-test pages/blog/environment-template regression run passes, including optional
link visibility, shared identity/hours, fixed canonical origin, safe JSON-LD escaping,
and rejection of unsafe/non-Google URLs. Django checks and migration-drift checks pass.

## Completed

- Lithium authentication, Bootstrap/crispy forms, WhiteNoise, and custom user preserved.
- PostgreSQL-only environment configuration and India time zone.
- Local and production environment templates cover every application setting, with
  production-only Compose inputs documented separately and an automated coverage
  test preventing newly referenced settings from silently going undocumented.
- Jai Sri Krishna Jewellery branding and canonical documentation.
- Bootstrap 5-only responsive interface modernization with a simplified owner
  navigation, wider financial data surfaces, consistent cards/forms/tables,
  refreshed public and authenticated journeys, and keyboard/reduced-motion
  accessibility improvements; no new frontend framework or dependency was added.
- Mobile/TWA presentation refinement with safe-area-aware page chrome, a sticky and
  bounded mobile navigation menu, compact conversion-page hierarchy, single-column
  thumb-sized action groups, readable stacked plan facts, a condensed journey
  timeline, touch-friendly tables/forms, and a two-column mobile footer. Financial,
  authentication, enrolment, and offline behavior are unchanged.
- Figma-principle refinement pass with WCAG-AA small-text contrast, structured
  financial form fieldsets, progressively disclosed owner records, consistent
  account-recovery and owner-list surfaces, explicit table-header semantics, and
  mobile customer contribution/redemption cards; gold-label, Bootstrap secondary-
  text, and warm-gradient homepage colors meet axe/WCAG AA normal-text contrast
  thresholds against their lightest-risk theme surfaces.
- Conversion-focused public homepage with a concise jewellery-goal proposition,
  role- and feature-aware customer-access/enrolment actions, up to three live
  published-plan previews, distinct existing-customer access, local business details,
  BIS hallmark/HUID trust cues, embedded Bootstrap Icons, and one optimized,
  self-hosted Pexels jewellery photograph clearly labelled as illustrative. The
  detailed registration-to-redemption explanation now lives on a dedicated,
  Django-owned How It Works page; the homepage links there while preserving the
  non-binding request and showroom-confirmed agreement boundary.
- Owner/customer roles, customer records, reusable plans, and snapshotted enrolments.
- Owner customer-management flow and isolated customer scheme view.
- Owner-only, one-time customer password-setup invitations with digest-only secrets,
  bounded expiry, safe resend/supersession, delivery state, and explicit separation
  between login activation and financial enrolment. Public signup remains closed.
- Production release `f9081c1a52a3ce3dc99e1d816cce9846a5b31f92` corrected the
  token-page CSRF/referrer policy; controlled invitation password setup and subsequent
  forgot-password reset both passed on 2026-08-26.
- Direct untracked authentication links, non-cacheable token responses that disclose
  only their origin and not the secret-bearing path,
  Caddy token-path log exclusion, removal of the redundant Gunicorn full-path access
  log, Django error/warning path redaction, and case-insensitive login-email
  uniqueness with a stop-before-migration integrity check.
- Append-oriented contributions with pending/paid/paid-unallocated/failed states.
- Fixed/variable amount validation and once-per-month/flexible frequency rules.
- Debug-only mock payment adapter with verified, idempotent confirmation.
- Customer cash balance/history and owner contribution visibility.
- Owner-published, append-only, exact-grade Scheme Rates with immutable fineness,
  effective timestamps, optional notes, publication identity, and immutable audit records.
- Immutable reference grades `GOLD_22K_916`, `GOLD_24K_9999`, and `SILVER_999`,
  plan-to-grade offerings, exact-grade enrolment contracts, and no cross-grade rate
  derivation or fallback.
- Additive legacy-history mapping from generic Gold to `GOLD_24K_9999` and generic
  Silver to `SILVER_999`, with no rewriting or conversion of stored grams.
- Current-rate selection from the database with a 5% large-change confirmation safeguard.
- Scheme Rate locking before mock payment or Razorpay order creation; no rate means no
  metal payment/order, while cash contributions remain available.
- Immutable Scheme Rates and one six-decimal metal allocation per paid contribution.
- Customer gold/silver gram balances and historical locked-rate visibility.
- Owner dashboard with separately reconciled cash principal, gold grams, and silver grams.
- Current gold/silver Scheme Rates and separately rounded indicative INR exposures.
- India-local successful-contribution counts for today and the current calendar month.
- MVP Alpha live workflow verified across owner setup, all three savings modes, customer payments and entitlements, and owner liability reconciliation.
- External metal-rate providers, API credentials, provider settings, quote caching, and
  provider-failure allocation paths removed from the authoritative workflow.
- Verified metal payments are durably `PAID_UNALLOCATED` until allocation succeeds,
  so exceptions or process interruption remain visible; owner retry is idempotent
  and reuses the original locked Scheme Rate.
- Owner alerts, diagnostics, and an authorized idempotent allocation-retry action.
- Configurable email reminders for upcoming exact-calendar eligibility, owner-only
  paid-unallocated exceptions, and completed redemptions, with deterministic per-
  recipient idempotency, immutable backend-acceptance/failure attempts, bounded
  retries, Postmark tracking disabled, aggregate cron-safe command output, and an
  owner-only delivery-evidence view. The production execution boundary is deployed;
  the first naturally occurring provider acceptance remains to be observed under
  `FW-ELIG-002`.
- Future public-signup requirements documented under `AUTH-*` domain rules.
- A disabled-by-default Google linked-credential foundation under ADR-0013: explicit
  connection by a locally authenticated approved customer, exact provider-verified
  email match, stable-subject login only after binding, privileged/inactive-user and
  social-signup rejection, password fallback, no OAuth token retention, callback log
  exclusion, configuration/integrity checks, and reviewed privacy/terms disclosures.
- Razorpay test-mode order creation and customer Standard Checkout flow.
- Explicit fail-closed Razorpay `test`/`live` configuration: the declared mode must
  match the API key prefix, and missing, unknown, or mixed-mode settings are rejected.
- Mode-stamped Razorpay contributions and webhook events with database constraints,
  cross-mode callback/order/webhook isolation, historical Test backfill, mode-aware
  event uniqueness, owner/admin visibility, and reconciliation-export coverage.
- A no-secret `check_razorpay_live_readiness` activation gate that rejects pending
  contributions from another mode, missing historical labels, failed Live webhooks,
  and unsafe Live configuration before a web-service cutover.
- Mode-accurate customer checkout wording that explicitly distinguishes simulated
  Test payment from a real Live charge and never offers a cross-mode resume action.
- Browser callback verification using the local order ID, HMAC, and a captured-payment server lookup.
- Signed raw-body `payment.captured` webhooks with a unique event ledger and idempotent financial processing.
- Razorpay webhook recovery under ADR-0006: signed permanent mismatches become
  durable owner-review exceptions with HTTP 200, transient failures return a
  sanitized retryable 503, each delivery/recovery appends bounded evidence, and an
  owner can dry-run then apply only an exact mode-matched provider payment through
  the existing idempotent confirmation and locked-rate allocation services.
- Unique Razorpay order/payment identifiers and one resumable pending order for once-per-month accounts.
- Dry-run-first reconciliation for aged Razorpay orders, with mode-matched provider
  inspection, an explicit application-side `ABANDONED` status, retained order/rate
  references, immutable provider evidence, independent flexible-attempt handling,
  monthly replacement/resume behavior, and late-capture escalation through the
  financial-exception workflow. Razorpay provider orders are never described as
  cancelled because its Orders API exposes no cancellation operation.
- Shared callback/webhook confirmation services that create at most one cash or metal benefit.
- India-local, date-derived active/not-yet-eligible, redemption-eligible, and redeemed display states.
- Owner dashboard counts for eligible now and exclusive 1–30, 31–60, and 61–90-day forecast windows.
- Owner-only grouped eligibility review and customer-facing eligibility guidance without automatic account closure.
- Immutable, idempotent owner-recorded cash, metal, and jewellery-purchase redemptions.
- Partial/full settlement with denomination-specific outstanding balances and exact final account closure.
- Customer redemption history, owner redemption ledger, and liability reconciliation after settlement.
- External Razorpay Test Mode payment captured through Standard Checkout on a public
  HTTPS endpoint, with the signed `payment.captured` webhook processed exactly once.
- Razorpay Live Mode acceptance completed on release `5fa726b` with two real captured
  contributions (INR `150.00` and INR `200.00`), two processed signed
  `payment.captured` webhooks, and exactly one immutable gold allocation per payment
  (`0.008973` g and `0.012229` g). Two unused Live orders with no attempts or payments
  were reconciled against Razorpay and retired through the contribution service. The
  final state has zero pending Live contributions, `0.021202` g allocated from Live
  payments, `0.329272` g total outstanding gold, and zero financial exceptions.
- The external-payment account completed owner-recorded redemption and reconciled
  customer outstanding cash and owner cash principal from ₹100.00 to ₹0.00.
- Owner-configurable cash bonus percentage and minimum qualifying duration with a
  safe zero-percent default and versioned terms snapshotted at enrolment.
- Separate principal paid/outstanding, earned bonus, projected bonus, and redeemable
  cash amounts on customer and owner views.
- Eligibility-cutoff bonus calculation using `Decimal` and `ROUND_HALF_UP`; projected
  bonus remains outside actual liability and redemption.
- Immutable cash-redemption principal/bonus components with deterministic
  principal-first allocation and exact owner-liability reconciliation.
- Immutable audit events with stable actor labels, timestamps, reasons, targets,
  and outcome/change details for supported sensitive owner workflows.
- Audited plan editing that affects future enrolments without rewriting agreement
  snapshots; enrolment, redemption, and allocation retry now retain owner reasons.
- Immutable one-to-one redemption reversals that restore the matching entitlement,
  reopen fully redeemed accounts, and preserve the original settlement record.
- Owner-only audit log and a derived exception queue for paid-unallocated/failed
  allocations plus failed or mismatched Razorpay webhook reconciliation.
- Customer/owner printable HTML contribution acknowledgements with stable receipt
  references and captured metal-rate/allocation details where applicable.
- Lifetime customer scheme statements showing verified payments, allocations,
  redemptions, reversals, and current denomination-specific entitlement.
- Owner contribution and redemption CSV exports with separated INR/gold/silver
  fields and spreadsheet-formula neutralization.
- Owner daily contribution reporting separates physical in-store cash, cash
  corrections/net cash, captured Live Razorpay payments, and the combined active
  verified total. Test/Mock and unsuccessful or reversed records do not inflate the
  real-funds cards.
- Strict namespaced production settings with bounded numeric/boolean parsing,
  signing-key fallback rotation, persistent database health checks, SMTP settings,
  secure cookie/header defaults, proxy trust opt-in, and timestamped stdout logging.
- Uncached liveness and PostgreSQL-readiness endpoints that expose the immutable
  application release without returning database error details.
- Deploy-only checks reject mock/unsupported payment gateways, missing selected-payment
  credentials, non-delivering email, wildcard hosts, and insecure CSRF origins.
- A non-root production image with build-time static collection and bounded Gunicorn
  worker recycling/timeouts, plus PostgreSQL-backed CI, deploy-check, and image-build gates.
- Canonical rollout, backup/restore drill, rollback, TLS/HSTS, monitoring, and
  coordinated secret-rotation procedures.
- A detailed platform-neutral production runbook covering the deployment contract,
  environment, immutable-image promotion, staged rollout, smoke tests, capacity,
  alerts, provider incidents, recovery, rotations, and financial go-live gates.
- A Linode-specific deployment profile for `jaishrikrishnajewellery.com`: pinned
  Caddy TLS proxy, private/read-only Django service, restricted Docker capabilities,
  CA-verified Managed PostgreSQL, bounded local logs, and production environment template.
- The canonical runbook now preserves the exact Ubuntu/Docker/CA bootstrap procedure
  and the reviewed branch-to-PR/CI-to-immutable-image-to-Linode deployment, verification,
  configuration-reload, and rollback workflow for future releases.
- The runbook also records post-merge local checkout hygiene: distinguish deployed
  SHA from branch names, preserve unrelated work, fast-forward local `main`, retire
  merged branches only after stabilization, and start each change on a fresh branch.
- The Linode observability profile now defines privacy-reduced structured Caddy access
  logs, Better Stack off-host retention and independent live/ready/5xx checks, Linode
  capacity/backup notifications, and an aggregate financial-exception command driven
  by a hardened five-minute systemd heartbeat timer.
- `FW-PROD-001` completed on 2026-08-27 with an isolated Linode Managed PostgreSQL
  newest-full-plus-incremental restore. The fork became ready in 15 minutes, retained
  every migration through `schemes.0011`, exactly matched the five-customer,
  six-account and denomination-specific liability baseline, passed authentication and
  financial-exception checks, and left the original production release healthy. The
  restored cluster and temporary environment/CA files were removed after verification.
- Public About, Contact, Terms, Privacy, Cancellation and Refund, and showroom-only
  Shipping and Delivery pages expose consistent business identity and support details.
- Public plans and INR pricing come from structured `SchemePlan` terms only when a
  plan is active and explicitly marked `publicly_listed`; all existing plans migrate
  as private, and publishing changes are included in the immutable plan-change audit.
- Customer-facing navigation and page headings call these offers "Savings plans"
  rather than "Plans & pricing"; displayed INR values are identified as contribution
  amounts, while the stable `/plans/` route and internal URL name remain unchanged.
- Public product and policy wording consistently describes the currently marketed
  gold/silver journey, distinguishes voluntary early discontinuation from payment-
  error refunds, and explains showroom-only metal or jewellery fulfilment.
- A public Our Story page credits owner Dilip Kumar and developer Rajesh Rathod H,
  explains their family partnership, and uses accessible monogram portraits until
  approved photographs are supplied. Its route is retained for later publication,
  but links to it are currently hidden from public navigation and page calls to action.
- Wagtail feasibility is accepted in ADR-0004 as a bounded catalogue CMS. Wagtail
  7.4.3 now runs additively with PostgreSQL search, `accounts.CustomUser`, `/cms/`,
  the existing `/admin/` and `/scheme/` routes, and unchanged Bootstrap 5 public
  pages. CMS entry requires the explicit `wagtailadmin.access_admin` permission;
  customer and application-owner roles alone do not grant it.
- The `FW-MEDIA-001` repository foundation uses environment-selected
  `django-storages` R2 storage while retaining WhiteNoise for static files. Wagtail
  originals and documents use short-lived signed S3 URLs; generated image renditions
  use a separate public custom-domain storage alias. Production checks reject local
  media, `r2.dev`, missing owned media domains, and non-view document serving. A
  no-residue command exercises real upload, read, rendition, and cleanup behavior.
- The isolated non-production R2 smoke passed on 2026-08-24: Django uploaded and read
  the original, generated and read a Wagtail rendition, and removed the temporary
  database and object-storage records without printing credentials or signed URLs.
- The complete Linode DNS record set was reproduced in Cloudflare, including the
  initially missed GoDaddy and Postmark DKIM records. Authority changed to Cloudflare
  without a stale DNSSEC delegation; both authoritative servers agree, and apex,
  `www`, live, and ready HTTPS checks return `200` while web and mail records remain
  DNS-only during stabilization.
- Inbound and outbound GoDaddy-hosted mail both passed after the Cloudflare DNS
  cutover. The public-rendition cache rule is deployed, and a fresh production smoke
  proved its 24-hour public cache header and a real Cloudflare cache `HIT` while WAF
  and cleanup behavior remained correct.
- The production R2 credential-rotation rehearsal passed on 2026-08-24: a new token
  scoped to the production bucket passed the complete smoke, the old token was
  deleted, and the new token passed again. A transient local DNS/TLS failure during a
  WAF probe recovered through bounded retries without weakening any access control.
- `FW-CATALOG-001` adds a bounded `catalog` application with one catalogue index,
  focused product pages, reusable category and marketing-collection snippets, ordered
  Wagtail image galleries with required alt text, revision-safe content, and an
  optional positive informational INR display price. The model and preview templates
  support product discovery and showroom enquiry only; they do not introduce
  inventory, carts, checkout, invoices, fulfilment, payments, or Scheme Rate coupling.
- `FW-CATALOG-002` adds an explicit, idempotent catalogue authorization bootstrap.
  It creates a draft catalogue root, dedicated media collection, subtree-scoped
  Catalogue Editors/Publishers/Administrators groups, collection-scoped image access,
  and a publisher approval workflow. Editors can prepare and submit drafts;
  publishers or catalogue administrators approve publication. Application roles do
  not grant group membership, non-staff users remain denied even if assigned by
  mistake, and every workflow, publish, and unpublish action stays in Wagtail's
  actor-attributed audit history.
- `FW-CATALOG-003` provides accessible Bootstrap 5 catalogue and product pages with
  live-only search and category/collection filters, featured-first 12-item pagination,
  responsive Wagtail/R2 renditions, image-free and no-result states, canonical/Open
  Graph/JSON-LD metadata, and explicit phone, email, and Vellore-showroom enquiry
  paths. Global navigation remains default-off for safe rollout and appears only when
  the flag is enabled and the catalogue root is independently live/public.
- `FW-CATALOG-004` completed production rollout on 2026-08-25. Release `2311ccf`
  applied the additive Wagtail, taggit, and `catalog.0001` migrations; reconciled and
  validated the bounded catalogue authorization; passed the production R2
  upload/read/rendition/cleanup smoke; assigned explicit staff publishing access;
  published reviewed catalogue content; passed direct mobile/desktop browser checks;
  and enabled public catalogue navigation only after those gates succeeded.
- The accepted long-term shape is hybrid: Wagtail owns catalogue/editorial content,
  while Django and the `SchemePlan` domain remain authoritative for savings-plan and
  financial behavior. Future Scheme Plan images or richer marketing copy may be
  Wagtail-managed presentation linked to a plan, but must not duplicate or control
  contribution, duration, metal, bonus, eligibility, publication, or enrolment terms.
- `FW-CMS-003` completed production rollout on 2026-08-25 in release
  `71f3e9cea5376cfb0a362ee13510a1162015649f`. The additive `pages.0001_initial`
  migration and editorial authorization configuration completed; About and Our Story
  remain bounded Wagtail editorial types, and Our Story stays outside global navigation.
- `FW-PRODUCT-001` completed production rollout on 2026-08-25 in release
  `93ba4273c976cd427d86a79a58454e2b7e58c55f`. The release used the recorded
  2026-08-24 12:00 PM IST managed recovery point, passed deployment and migration-plan
  gates with no schema changes, and preserved the one empty historical CASH account.
  Production now rejects new CASH enrolments and contributions, exposes only gold and
  silver during enrolment, retains the historical account and statement without a Pay
  action, and returns `403` from its direct contribution route. Post-release live and
  ready checks returned `200`; the CASH boundary and financial-exception checks both
  reported `status=ok` with zero CASH exposure and zero exceptions.
- `FW-PAY-004` completed production rollout and acceptance on 2026-08-31 in release
  `e027b9ae1550c314584c551eb3da31d5529ea544`. Production retains the reviewed
  seven-day Asia/Kolkata schedule. Current-day Gold and Silver Scheme Rates were
  published, the schedule was enabled with an audit reason, and its exact closing and
  reopening boundary worked as expected after the manual pause/resume exercise.
- Grade-specific metal rates completed production rollout and acceptance on
  2026-09-03 in release `df5a7506bfa3c5b255faf284d3f90ef2ac7d7b28`.
  The controlled migration applied `schemes.0015` and `schemes.0016` from a
  recorded 2026-09-03 11:00 AM IST PostgreSQL recovery point after proving zero
  pending Razorpay orders. Legacy Gold remained `GOLD_24K_9999` at the unchanged
  `0.329272` g baseline, new enrolment moved to independently priced
  `GOLD_22K_916`, and exact-grade integrity, financial-exception, Razorpay Live
  readiness, health, and readiness gates all passed. A controlled INR `150.00`
  Live contribution locked the `GOLD_22K_916` rate of INR `14667.0000`/g,
  processed one signed `payment.captured` webhook, and created exactly one
  `GOLD_22K_916` allocation of `0.010227` g with no financial exception.
- `FW-PAY-005` completed production rollout and acceptance on 2026-09-03 in release
  `51c931a9de5b27349f781cd44670c41307479dfa`. From the recorded 2026-09-03
  1:00 PM IST PostgreSQL recovery point, the controlled global pause covered every
  offered grade, provider reconciliation found zero candidates, and migration
  `schemes.0017_contribution_checkout_expiry` applied as the only planned operation.
  The candidate reported the configured 10-minute deadline, zero pending Razorpay
  contributions, zero pending rows missing expiry, and green payment-operations,
  financial-exception, Live-readiness, exact-grade, container-health, liveness, and
  readiness gates before a separately audited reopening of all three grades.
- `FW-PAY-006` completed production rollout and acceptance on 2026-09-03 in release
  `315f836ac0717fbaaf2d8d90268471ac1670e5b1`. From the recorded 2026-09-03
  4:00 PM IST PostgreSQL recovery point, migration
  `schemes.0018_in_store_cash_contributions` applied as the only planned operation
  after every grade was paused and the pending Razorpay count was zero. The feature
  remained disabled through migration, integrity, health, and owner-path review,
  then was enabled before a separately audited reopening. The first legitimate
  showroom receipt, `CASH-150E7205`, recorded INR `1000.00` on contribution `15`,
  locked the `GOLD_22K_916` rate of INR `14667.0000`/g, and allocated exactly
  `0.068180` g. The immutable receipt, one audit event, statement, owner ledger, and
  CSV reconciled; cash, financial-exception, exact-grade, and Razorpay Live-readiness
  checks remained green.
- `FW-ELIG-001` completed production rollout and acceptance on 2026-09-04 in release
  `50bfd3673c57dff51b46238094bcad899a36c8fa`. Its no-op migration plan, exact-calendar
  production probes, public Terms wording, unchanged eight-account financial
  baseline, and all financial/provider gates passed. The on-host build caused a
  recoverable OOM origin outage before cutover on the 1 GiB Compute Instance; no
  environment, release, schema, or database mutation had occurred. Reboot restored
  the old release, and the retained candidate was then deployed sequentially without
  rebuilding. Future serving-host builds are prohibited under `FW-PROD-006`.
- `FW-AUTH-002` completed production rollout and controlled acceptance on 2026-09-04
  in release `613e2f7363a67ea6d588273f54bcddb628f9549a`. Direct allauth signup remains
  closed; the public route creates only a staged application. Email confirmation,
  replacement-token invalidation, owner rejection without account creation, manual
  mobile confirmation, approval/invitation, customer password setup, login with zero
  schemes, and Caddy/application token-log exclusions were exercised successfully.
- `FW-ENROL-001` and `FW-AUTH-003` completed production rollout and controlled
  acceptance on 2026-09-04 in release
  `bfbdad86c49855ffc5c9965d0848a657a62cf938`. Migration
  `schemes.0020_scheme_enrolment_requests` was the only planned operation and was
  applied from the recorded 8:00 PM IST recovery point with the feature disabled.
  After activation, one legitimate request recorded one submission audit and no
  agreement, contribution, Razorpay order, rate lock, allocation, or liability. Owner
  confirmation created exactly one linked `GOLD_22K_916` agreement
  (`JSK-311D2A62`), retained zero contributions, sent the customer completion email,
  and remained idempotent at nine total accounts and one enrolment audit. Enrolment,
  financial-exception, Live-readiness, and exact-grade checks stayed green.
- `FW-AUTH-004` completed disabled-first production rollout and controlled acceptance
  on 2026-09-05 in release `77141d0caa447028802ff1ec7166fad4fd198d8c` from the
  recorded 10:00 AM IST PostgreSQL recovery point. All six additive `socialaccount`
  migrations applied before activation. One approved active non-staff customer linked
  a matching verified Google identity and retained Google, password, and reset access;
  owner/administrator connection remained unavailable. The aggregate baseline stayed
  at eight users, seven customers, nine accounts, fifteen contributions, and six
  allocations; exactly one `SocialAccount` and zero `SocialToken` records existed.
  Authentication, financial-exception, and exact-grade integrity checks and both
  HTTPS health endpoints passed.
- `FW-PRIV-001A` completed its disabled-first production rollout on 2026-09-07 in
  release `e6a8ee0f20fe2324276fb75dad6bda9df64baf9d`, published as
  `ghcr.io/rajeshr188/jsk-savings@sha256:6b65308d74165d6ca19b298dd507f45f8bb51416bd14c69f406a782810cccd18`.
  Additive migration `accounts.0005_customer_account_deletion_foundation` applied
  from the recorded 4:00 PM IST PostgreSQL recovery point. The feature remained
  disabled with no policy version, all deletion workflow counts stayed zero, and the
  public deletion route returned 404. Live/readiness, authentication, payment,
  financial-exception, Live-mode, exact-grade, in-store-cash, and Google-link checks
  passed. Customer, agreement, pending-order, INR, and exact-grade metal liabilities
  matched the pre-migration baseline exactly.

## In progress

- `FW-MOBILE-001` has completed its repository-side no-code audit. The proposed
  package is `com.jaishrikrishnajewellery.savings`; the initial product support floor
  is Android 10/API 29 with a current TWA-capable browser, while new Play submissions
  currently target Android 16/API 36. The owner approved that package and store
  identity on 5 September 2026 and confirmed the D-U-N-S prerequisite on 7 September.
  On 8 September the verified organization successfully created the draft app,
  registered the package, and obtained its Play App Signing SHA-256 identity. The
  private `Jai-Sri-Krishna-Jewellery/jsk-savings-android` repository was then
  initialized at commits `983226f` and `7317a51`; Android CI run `34235149531`
  passed release invariants, release lint, and an unsigned API 36 AAB build. On 9
  September the owner created the distinct upload key outside both repositories and
  Linode, verified two encrypted backups, configured encrypted GitHub secrets, and
  workflow run `34263042974` built and verified the signed AAB. Play accepted that
  bundle for Internal Testing and displayed the expected upload-certificate
  fingerprint. Play Billing,
  location, notification permission, application secrets, and a mobile API are
  absent. Server-enforced branch protection remains unavailable for this private
  organization repository on the current GitHub plan, so an upgrade or an explicitly
  approved public-source decision is still required for that enforcement. The
  owner supplied the first Play App Signing SHA-256 fingerprint, and production
  release `1826afec8628d4f9288c1625091974687af7aba0` serves the Digital Asset Links
  response for that certificate and registered package. Disabled-first, direct-200,
  JSON content-type, exact-value, cache, and health checks passed. Read-only inspection
  of the Play-installed APK independently proved Google signer
  `B8:A3:25:32:0B:80:2C:2A:E1:9B:EA:F7:30:27:C4:89:E5:2D:D6:1F:E4:60:F2:99:2F:6E:C6:54:14:24:17:B4`;
  Android and Google's verification API initially rejected that installed certificate
  because the origin listed only the first certificate. Release
  `0c611f6e51434aa7f0a3faa8ddba8ef492910af3`, image
  `ghcr.io/rajeshr188/jsk-savings@sha256:7a9cd29e01f1cd9240098622c11e869e43fb953e554d94dc97ed75e55203d374`,
  additively published both Play certificates and explicitly excluded the upload key.
  Both Google association checks returned linked, Android changed the canonical
  domain to verified with link handling enabled, Chrome was the default browser, and
  the relaunched app had no address bar. The remaining gates are the bounded
  payments/recovery/role device matrix, Financial features classification,
  category/provider/recovery retention review, separate signed-out deletion acceptance,
  reviewer access, store assets/Console submission and final dependency-level Data
  Safety review. Deletion implementation/enablement and authenticated completion are
  already evidenced. The first release remains customer-only and adds no mobile API.
- ADR-0015 was owner-accepted on 7 September 2026 with 24-hour verification,
  seven-day owner-review, and 30-day removable-data service targets; owner-only review;
  and entitlement-preserving retained-record communication. The `FW-PRIV-001A`
  foundation, `FW-PRIV-001B` completion implementation, request enablement and
  authenticated zero-history production completion are accepted as recorded above.
  The separate signed-out email-verification journey, provider follow-up and
  recovery-record reconciliation remain open. The 10 September ADR revision permits
  owner-operated development without a blanket professional-sign-off prerequisite;
  each execution still requires justified category/field dispositions and evidence.
- `FW-ELIG-002` awaits only the first naturally occurring reminder-specific Postmark
  acceptance and matching owner delivery record. Its deployed zero-candidate run is
  correct evidence that no message is invented merely to satisfy a rollout smoke.
- `FW-PAY-003` retains two no-mutation recovery evidence exercises: an isolated
  Test-mode review/dry-run/apply case and an idempotent replay of an already-processed
  Live capture. External alerting and coordinated secret rotation remain separately
  deferred under `FW-PROD-002` and `FW-PROD-003`.
- `FW-MEDIA-002` tracks the accepted backup/recovery and usage-monitoring deferral.
  It does not block catalogue use, but approved source photographs must
  remain outside R2 until an isolated backup target and restore proof exist.
- Environment-specific production proof: isolated database restoration, external
  alert routing/exercises, and coordinated secret-rotation drills. Postmark SMTP and
  real password-reset delivery passed on 2026-08-26, production Site 1 now uses
  `jaishrikrishnajewellery.com`, and direct invitation/password-reset credential setup
  passed after the CSRF-policy hotfix. The owner deferred SMTP token rotation. The stable owned domain/TLS/proxy
  path and repository observability foundation are operational; Better Stack and
  Linode alert activation still require account-side configuration and retained test
  evidence.
- The Ubuntu 24.04 Compute Instance and three-node Managed PostgreSQL 16 cluster are
  provisioned in one region. Database/Cloud Firewall access controls and the database
  CA are in place, SSH access is verified, Docker is installed, and the owned domain
  returns liveness and PostgreSQL readiness `200` through Caddy-managed HTTPS;
  paid external alert exercises remain deferred.
- Historical 7 September production checkpoint (superseded by later release evidence
  above): release `049944412aa09668d6b04e45cabee2bc58dadc42` was healthy from
  immutable image
  `ghcr.io/rajeshr188/jsk-savings@sha256:4f5d10d014c3f516c4194fe192a01df57387c5353c232aa80a88ad18a99bce02`
  with
  migrations through `schemes.0020_scheme_enrolment_requests`,
  `catalog.0001_initial`, `pages.0001_initial`,
  `accounts.0005_customer_account_deletion_foundation`, and
  `socialaccount.0006_alter_socialaccount_extra_data`
  applied, zero reported financial exceptions, successful live/ready checks, valid
  catalogue authorization, working R2 media, published reviewed products, and public
  Jewellery links in the primary and footer navigation. Its production metal-only
  boundary, payment-operations manual pause/resume, and audited in-store cash receipt
  path passed owner/customer smoke. Its PWA install, strict three-asset cache,
  generic offline behavior, no-mutation test, and flag-driven retirement/re-enable
  sequence passed production owner acceptance on 7 September 2026.

## Known limitations

- The installable PWA/service-worker foundation is production-accepted. The Android
  TWA has a signed Play Internal Testing build and verified origin association;
  public-store release and the remaining device/pilot evidence are pending. There is
  no mobile API, native push/biometric credential or iOS App Store client. ADR-0014
  requires pilot evidence before a native/API commitment; the TWA uses the existing
  server-rendered customer website.
- Google sign-in is limited to explicitly linked approved customers. Owners, staff,
  and superusers retain password authentication, and provider-assisted registration,
  additional social providers, and customer self-service unlink are intentionally
  unavailable. A suspected compromised binding requires customer deactivation or
  global Google-login disablement until the separately tracked audited recovery design
  is implemented under `FW-AUTH-005`.
- The application intentionally does not derive one grade's Scheme Rate from another.
  Every offered grade needs its own owner-published current rate; that fail-closed
  behavior can temporarily block contributions for only the missing grade.
- Three-decimal customer gram values are rounded display values, not a reduction in
  accounting precision. Exact settlement entry and all authoritative quantities
  remain six-decimal; customer wording must not imply the displayed value is the
  complete source record.
- Razorpay exposes no order-cancellation operation. A reconciled `ABANDONED`
  contribution therefore retains its locked Scheme Rate and provider reference for
  evidence; a replacement locks the then-current rate, while any late capture is a
  financial exception requiring manual provider reconciliation and refund handling.
- Public prospect and policy pages market only gold/silver jewellery purchase plans.
  Production enforces that boundary for new enrolments and contributions while
  preserving the one empty historical CASH record. Qualified legal, accounting, and
  provider review of the marketed flow still remains necessary.
- Temporary quick-tunnel URLs have no uptime guarantee; deployment requires a stable,
  owned HTTPS endpoint and synchronized webhook-secret configuration.
- Repository health checks, privacy-reduced edge access logs, and a financial-
  exception heartbeat now exist, but Better Stack/Linode must still be configured to
  retain logs and exercise uptime, 5xx, capacity, backup, TLS, and financial alerts.
- The application records redemptions but does not execute payouts, move inventory,
  create invoices, or convert metal to cash.
- Generic online-payment correction, voids, refunds/disputes, dual approval, provider
  settlement import, and automated retries remain. In-store cash bookkeeping errors
  now have a bounded append-only reversal, but this is not a refund. The Live runbook permits only a
  tightly bounded manual Dashboard refund for a captured payment that created no
  local entitlement; any credited-payment refund or chargeback remains an incident.
- Public policy pages require business/legal approval before they are treated as
  binding terms. The exact plan-specific 6+ month wastage/value-addition discount
  schedule is not modeled and no numeric partial discount is advertised.
- Documents are on-demand HTML acknowledgements, not archived statutory tax invoices;
  PDF generation, signatures, tax identity, delivery/reissue logs, and date-filtered
  exports remain future production/legal work.
- Cash bonus has one percentage policy with no caps, tiers, discretionary approval,
  forfeiture, tax treatment, or expected-future-contribution projection.
- Bonus liability reads are calculated per cash account; aggregate optimization is
  deferred until measured account volume requires it.
- Plan-specific early-discontinuation pricing and partial-settlement policy are not
  defined; automatic signup/approval remains outside the accepted boundary. The
  committed redesign coordinates identity and agreement approval for newly linked
  plan applications while retaining separate records and legacy access-only flows.
  It is locally verified, with production rollout still pending (`FW-UX-001`); do not
  infer production enablement from the local preview. Email reminders are deployed,
  but the first genuine delivery observation remains pending; SMS/WhatsApp, inbox-delivery/read proof,
  automatic multi-day catch-up, and end-to-end exactly-once SMTP delivery are not
  claimed. Owner-invitation onboarding remains available alongside the staged public
  application.
- The production catalogue is active and its deployment, authorization, content,
  browser, and R2 smoke gates pass. There is still no isolated media backup/restore
  proof. Retain approved source photographs outside R2; production must not rely on
  R2 as their only copy. This accepted limitation remains `FW-MEDIA-002`.
- The detailed, prioritized backlog and milestone-by-milestone limitation history
  are maintained in [Future work](FUTURE_WORK.md).

## Deferred

- See [Future work](FUTURE_WORK.md) for deployment gates and post-MVP operations.

## Verification

- The production-accepted Wagtail 8.0 and Django 6.0.4 baseline passed system checks,
  migration detection, 66 focused catalogue/editorial/media tests, and all 380
  project tests. Its sole migration was additive vendor migration
  `wagtailcore.0098_apitoken`. The in-development blog candidate passes 69 combined
  CMS/environment tests and all 391 project tests, including hierarchy, preview,
  rollout gating, public discovery, pagination, validation, permission isolation, and
  publisher-workflow coverage.
- Local and production PostgreSQL 16 migrations are applied through
  `schemes.0020_scheme_enrolment_requests` and
  `socialaccount.0006_alter_socialaccount_extra_data`.
- Environment-template coverage verifies every setting referenced by Django plus the
  media-storage environment contract, and verifies production-only Compose inputs.
- 380 tests pass, including the disabled-first PWA manifest, declared icon dimensions,
  network-only navigation worker, strict three-asset cache allowlist, generic offline
  response, mutation non-interception, and rollback cleanup, plus controlled Google
  credential linking, social-signup and
  privileged-user rejection, stable-subject login, verified-email matching, password
  fallback, zero token retention, callback log protection, exact-calendar eligibility
  month-end clamping,
  weekend/calendar-marker non-adjustment, exact-day activation without early grace,
  non-expiring eligibility, calendar-day forecast distance, in-store cash
  preview/confirmation, owner authorization,
  payment-control and pending-Razorpay blocking, exact-rate locking, idempotency,
  durable allocation, bounded append-only correction, active-balance removal, daily
  reconciliation, receipt/statement visibility, and provider-channel migration,
  plus Razorpay Checkout expiry/backfill, expired-resume
  blocking, capture-after-expiry confirmation, exact 22K/24K rate separation,
  six-decimal allocation,
  immutable enrolment grade, legacy old-schema preflight, history mapping, default
  plan offerings, Razorpay webhook response classification, append-only
  processing-attempt evidence, provider-backed owner dry-run/apply recovery,
  mismatch/abandoned safeguards, recovery authorization and idempotency,
  payment-operations schedule/manual/kill-switch precedence,
  owner authorization and immutable before/after audit, blocked new order/Checkout
  behavior, uninterrupted callback/webhook confirmation and locked-rate allocation,
  the no-secret deployment check, Razorpay Live/Test configuration and history migration,
  cross-mode order/callback/webhook isolation, Live checkout disclosure, readiness
  blocking, mode-aware reconciliation export, the production metal-only boundary
  and CASH preflight,
  public catalogue search/category/collection filtering,
  bounded pagination, responsive renditions, canonical/Open Graph/JSON-LD metadata,
  accessible discovery and empty states, rollout-gated navigation, direct draft/live
  visibility, catalogue authorization drift repair, exact role/media scope, editor
  submission, publisher approval, publish/unpublish audit history, hierarchy,
  validation, case-insensitive uniqueness, preview, revision, gallery and rendition
  coverage; R2 configuration and signed/private-original versus
  public-rendition URL isolation, no-residue upload/read/rendition/cleanup behavior,
  production media deployment gates, explicit Wagtail permission and route-precedence checks,
  public INR-contribution/metal-to-jewellery copy coverage,
  owner-only Scheme Rate publication, large-change
  confirmation, no-rate payment blocking, pre-order locking, rate-change race
  behavior, durable verified-payment/allocation transition, production-shaped
  `0009` to `0010` history backfill and blocker checks, historical immutability,
  aggregate financial-exception monitoring with
  redacted output, public-policy route/link coverage, explicit active-plan
  publishing and INR pricing visibility, health/readiness failure sanitization,
  deploy-configuration gates, document access, receipt stability, unallocated disclosure, CSV
  denomination/formula safety, audit immutability, exception classification,
  reversal reconciliation, cash-bonus boundaries/rounding, Razorpay failure handling,
  redemption precision, over-redemption protection,
  idempotency, partial/full closure, denomination separation, access control,
  PostgreSQL constraints, exact-date reminder candidate selection, audience and
  recipient safety, dry-run non-mutation, accepted-message idempotency, sanitized
  bounded retry evidence, fail-closed disablement, record immutability, and owner-
  only delivery review, plus all prior regressions.
- Migration drift check reports no changes.
- Django system check and migration drift check pass.
- The rendered anonymous homepage passes Deque axe-core 4.13's WCAG AA
  `color-contrast` rule with zero violations; the referenced axe 4.12 rule uses
  the same 4.5:1 normal-text and 3:1 qualifying-large-text thresholds.
- Production deployment checks pass with a synthetic secure configuration and no
  issues; the real deployment must supply equivalent secrets, hosts, TLS, and email.
- Production image `jsk-savings:hardening-check` builds successfully, collects 137
  static files (403 post-processed), and is configured to run as user `app`.
- A disposable container smoke returned HTTP 200 from `/health/live/`, reported
  release `hardening-smoke`, and confirmed the running process user is `app`.
- The corrected `jsk-savings:deployment-guide-check` image builds successfully and a
  disposable liveness smoke returns `200` with the expected release; Gunicorn 25.3
  starts without attempting a control socket on the read-only application filesystem.
- GitHub Actions CI is defined with SHA-pinned checkout, Node-24-compatible Docker,
  and scanner actions, PostgreSQL 16, migrations, drift/system/deploy checks, the
  349-test regression suite, static collection, unprivileged review-image builds,
  and a GHCR publisher restricted to protected `main`, with an immutable digest
  output. Actionlint 1.7.12 validates
  the workflow locally. The first protected-`main` run `33848413888` built merge
  `e78c2b20f013298186b7c742a18ba4d99658d164`, passed the published-digest critical-
  vulnerability gate, and produced
  `ghcr.io/rajeshr188/jsk-ss@sha256:9778089354d7110c8ea04f8ba2d8b4f6098e7d771e24329d0aeac441ae8faf3d`.
  The publisher now targets the repository-linked public `jsk-savings` package. Main
  run `33850511585` built merge `db577e19d015615972347f3546247a4b32df0369`,
  passed the published-digest critical-vulnerability gate, and produced
  `ghcr.io/rajeshr188/jsk-savings@sha256:30df12ac108ce90504c9c33e18e79d2c1c3d304e77e2d8cc9f64339bd5c86c54`.
  On 2026-09-04 the Linode pulled and inspected that digest with an empty temporary
  Docker configuration, proving anonymous access; production remained healthy and
  unchanged on release `50bfd3673c57dff51b46238094bcad899a36c8fa`.
  PR `#41` then merged the public-GHCR boundary as
  `b3d94c9deed8ebd6c78ed096d541620057535093`; protected-`main` run `33851821679`
  passed and published
  `ghcr.io/rajeshr188/jsk-savings@sha256:5dbd8de9ad5493c2c87de08e244e1350c6f774a5ba335996c3f65e3816b8ae61`.
  PR `#42` merged FW-ELIG-002 as
  `94cf3927a7138cf735da733c6ae68a8cce785cff`; protected-`main` run
  `33862547971` passed the 293-test, deploy, static, publish, and critical-
  vulnerability gates and produced
  `ghcr.io/rajeshr188/jsk-savings@sha256:8270e175b9f4789dc12f83b9b41f504b0b3dcd5814a1b82f904aa61116623a7e`.
  PR `#43` merged the reminder service hotfix as
  `c889ee6906a8bddd4c7852955025efe42ffa5752`; protected-`main` run
  `33865158341` passed the 294-test, deploy, static, publish, and critical-
  vulnerability gates and produced
  `ghcr.io/rajeshr188/jsk-savings@sha256:88eea68169da2ea04f9f104358ecb69ec929989b15f5e447825ab0f0bd806c33`.
  PR `#49` merged `FW-AUTH-004` as
  `77141d0caa447028802ff1ec7166fad4fd198d8c`; protected-`main` run
  `33948122224` passed the 349-test, deploy, static, publish, and fixable-critical-
  vulnerability gates and produced
  `ghcr.io/rajeshr188/jsk-savings@sha256:7e2f95e53333791ede60007f0a059377938574e63d574a55fb4da7fe48c63681`.
  PR `#53` merged the accepted account-deletion containment foundation as
  `e6a8ee0f20fe2324276fb75dad6bda9df64baf9d`; protected-`main` run
  `34111584454` passed the 362-test, deploy, static, publish, and fixable-critical-
  vulnerability gates and produced
  `ghcr.io/rajeshr188/jsk-savings@sha256:6b65308d74165d6ca19b298dd507f45f8bb51416bd14c69f406a782810cccd18`.
- The Linode production Compose model passes `docker compose config --quiet`, and
  Caddy 2.11.4 validates the exact apex-domain, `www` redirect, masked JSON access
  log, and release-label configuration. The financial heartbeat shell script passes
  a non-executing syntax check.
- The deployed Linode application returns `200` from both liveness and PostgreSQL
  readiness over `https://jaishrikrishnajewellery.com`; the valid ACME contact and
  Caddy-managed certificate corrected the initial placeholder-contact failure.
- Production release `93ba4273c976cd427d86a79a58454e2b7e58c55f` passed immutable
  image identity, no-op migration, live/readiness, CASH-boundary, financial-exception,
  log review, and manual metal-only UI checks on 2026-08-25. The retained CASH account
  has no pending or verified payments, INR liability, redemption, or enabled Pay path.
- Live-server checkpoint passes for owner and customer login, UI-created plan/customer/CASH-GOLD-SILVER enrolments, three mock payments, customer entitlements, owner contribution visibility, and exact liability/activity deltas.
- Manual Scheme Rate regressions verify owner-only gold/silver publication, validation,
  append-only history, latest-applicable selection, large-change confirmation,
  GOLD/SILVER no-rate payment blocking with unaffected CASH orders, pre-order locking,
  old-lock/new-rate race behavior, legacy history preservation, and deployment blockers.
- Milestone 7 live-HTTP smoke passes for owner forecast/detail views and customer redemption-eligible guidance; the database status remains `ACTIVE`, and all disposable records are removed.
- Milestone 8 authenticated request smoke passes with CSRF enforcement: an owner
  records partial cash and final jewellery settlement, the customer sees both
  records and no payment action, liabilities reconcile, and disposable data is removed.
- MVP Beta external smoke passes with private Razorpay Test Mode credentials: a ₹100
  payment is captured, one signed `payment.captured` webhook is processed, one cash
  entitlement is created, an owner completes the full redemption through a
  CSRF-protected form, and customer/owner outstanding cash reconciles to zero.
- Production release `049944412aa09668d6b04e45cabee2bc58dadc42` passed the
  disabled-first and enabled PWA route gates, installation, exact offline-plus-two-icon
  cache inspection, offline no-disclosure/no-mutation checks, and automatic worker/
  cache retirement when disabled. Re-enabling restored the three endpoints and root
  worker scope. Live/readiness, financial-exception, and Razorpay Live checks remained
  clean; the web container was healthy with 377 MiB available memory, 422 MiB free
  swap, and 9.6 GiB free disk. The recovery point was recorded as 6:00 PM IST on
  7 September 2026, and the previous release/image pair remains the rollback target.
- Milestone 9 rollback-only authenticated smoke passes through owner plan creation and
  enrolment, customer mock payment, eligibility transition, and owner redemption:
  ₹100 principal earns ₹5, the immutable redemption stores both components, the
  account closes, and owner liability returns exactly to baseline.
- Milestone 10 rollback-only owner smoke passes through audited enrolment, ₹100 cash
  redemption, compensating reversal, restored ₹100 liability, reopened account, and
  owner audit/exception views; exactly three audit events were created and all tagged
  smoke records were rolled back.
- Milestone 11 rollback-only authenticated smoke passes for a gold mock payment,
  stable printable receipt, statement showing 0.080000 g gold, and both owner CSV
  exports; all tagged records were rolled back.
- Production release `9fa12943b9719e1c14d1894c4cfceb753b54376c` was accepted on
  9 September 2026 from immutable image
  `ghcr.io/rajeshr188/jsk-savings@sha256:4e8abb514e2ac33a757c3abfc545d414a9430edbcf4c085157fe2ce4a941616e`.
  A 10:00 PM IST managed-PostgreSQL recovery point and the previous
  `0c611f6e51434aa7f0a3faa8ddba8ef492910af3` release/image pair were retained.
  An expired Live Razorpay order was provider-verified as untouched, abandoned through
  the dry-run/apply workflow, and left zero pending exposure before cutover. There was
  no migration. Live/readiness, payment, financial-exception, Live-mode, exact-grade,
  and in-store-cash checks passed; all grades reopened after the maintenance pause.
  The owner Contributions page displayed INR 0.00 physical cash, INR 4,000.00 captured
  Live Razorpay, and INR 4,000.00 total verified for the India-local day. Cloudflare
  Web Analytics was confirmed enabled independently; this does not complete deferred
  external operational alerting under `FW-PROD-002`.

## Next recommended step

Review the local conversion preview and prepare the combined staging rehearsal and
concrete release plan under `FW-UX-001`; production deployment/migrations still need
separate owner approval. After approved rollout, observe comparable aggregate funnel
and server-confirmed payment throughput without claiming a unique-visitor conversion
rate. Supply approved additional offer copy/review expectations (`FW-UX-002`) and run
reviewed Tamil participant testing (`FW-UX-003`) as independent follow-ups. Production
monitoring, recovery/rotation and financial safeguards remain open in `FUTURE_WORK.md`.

For the separate Play release workstream:

Complete the separate signed-out public email-verification deletion journey once an
owner-controlled Workspace alias reliably receives mail. Use another genuinely
zero-history disposable customer, never bypass verification, and repeat the same
owner preview, completion, notice, credential and integrity evidence. In parallel,
enter the copy-ready store listing and App-content answers as Play Console drafts,
prepare a stable non-privileged reviewer account, capture privacy-safe screenshots,
and finish the release-candidate Data Safety/provider review. Do not submit the app
for production review until these remaining gates are reconciled in
`docs/MOBILE_RELEASE_READINESS.md`. Keep the existing financial, recovery-isolation
and no-secret boundaries; no additional real payment is required merely to complete
store preparation.
