# Project Status

## Current milestone

**30 October 2026 - FW-AUTH-006 owner expiry candidate; cleanup not yet executed.**
PR #80's required checks passed at head `106f7b9`; it remains open and mergeable.
Separate branch `agent/registration-expiry-review` adds a narrow, confirmed owner
decision for standalone unverified registrations whose verification deadline passed.
Existing review fields retain owner, reason and time. Row locking and a current-state
digest refuse stale forms, replaced links, verified identities and coordinated plan
journeys. Exact retries preserve the original decision; no email, account, agreement,
financial change or deletion is produced. Migration `accounts.0010` preserves existing
automatic-expiry rows and extends the lifecycle constraint for reviewed expiry.
Its reverse guard refuses to discard reviewed-expiry evidence.

Local registration/application/deletion regression passed 123 tests; 36 final
expiry/inbox/workspace checks also pass. Hosted CI/release remain pending. No production application has
been expired, rejected or approved. The verified September application still needs
the owner's genuine-applicant versus obsolete/test decision. Deletion work follows
the completed-with-retention review first, then the two contained/open legacy cases;
actual external provider/log/backup/offline-obligation findings and recent owner
authentication are required before recording a disposition. Do not invent completed
checks, erase history or mark zero-balance legacy agreements redeemed.

**30 October 2026 - read-only production application/deletion backlog audit.**
The Applications inbox has four attention records, all standalone registrations:
one email-verified request awaiting an owner decision, and three unverified requests
from September with expired verification links. None is linked to an approved login
or a plan journey/agreement. Fourteen other intake records have recorded decisions.
The current owner UI can approve/reject the verified request or resend verification;
it lacks an explicit audited expiry action for the three stale unverified requests.
Rejection is deliberately restricted to verified applications. Do not invent new
applications, send unnecessary email, delete rows or directly relabel statuses to
clear the badge. Follow-up is tracked as FW-AUTH-006.

Three deletion reviews are overdue: one AWAITING_SETTLEMENT with two open legacy
agreements/one contribution record; one CONTAINED with one open legacy agreement
and no contributions; one COMPLETED_WITH_RETENTION with no agreements/contributions
and an already-minimized login. Recorded balances are zero; no pending provider
payments, financial/allocation exceptions, unresolved webhooks, pending enrolments
or ambiguous email-matched registrations were found. Logins remain disabled.
The completed case needs retained-record review, not another deletion. The two
open cases need a real category/external-obligation review, then justified hold or
completion with necessary financial/contact retention. Open agreements require
showroom name/email retention with a stated purpose; privacy minimization does not
require pretending those agreements were redeemed. The unused-cancellation service
supports configured agreements only; these legacy agreements must not be forced
through it or rewritten. No request, deadline, identity or financial record changed.

**30 October 2026 - requested four-offer range is prepared, all unpublished.**
Owner requested generating the recommended range for independent review/publication.
Reused plan **4 / Flexible Gold Savings (22K)** and configuration **2/v1** unchanged.
Existing validated services created three new configurations and three drafts:

| Review draft | Code / configuration | Proposed rules |
| --- | --- | --- |
| **5 — Monthly Gold Savings (22K) - Choose Your Amount** | MC22K-CHOICE-12M / 3/v1 | Customer-selected fixed amount, 22K grams, 12 calendar months AND 12 qualifying monthly payments, three replacement periods then review, no bonus. |
| **6 — Jewellery Purchase Savings** | INR-MONTHLY-12M / 4/v1 | Customer-selected fixed monthly amount; INR principal, not grams; same 12-month/12-count schedule; proposed 5% purchase-only bonus capped at INR 3,000 after required-schedule qualification. Completion within allowed replacements preserves qualification; early discontinuation does not qualify. |
| **7 — Flexible Silver Savings** | SILVER-FLEX-ANYTIME / 5/v1 | Optional variable payments, SILVER_999 grams, anytime full settlement with positive verified entitlement, no bonus. |

All four use proposed INR **150-100,000 per contribution**, without an additional
step, copied from the existing flexible draft. Gold/silver flexible offers permit
continued contributions before closure; monthly offers stop at qualification.
All use one final full showroom settlement. INR unused principal uses the agreed
original-source return process; its benefit is purchase-only and never cashable.
Amounts, the new monthly variants and especially the 5%/INR 3,000 benefit remain
review proposals, not new public promises or implied legal/accounting approvals.

All four are inactive/unlisted, with null publication revision and zero linked
agreements. Existing public offers 1/2/3 and all existing rows across 53 scheme
models match; only 3 configurations/plans/revisions/audits and 6 offering rows
were appended. Liabilities and 14 agreements are unchanged; INR principal is zero.
Exact preparation/repeat/cap/amount-bound rehearsal passed locally; production
configuration/agreement/financial/INR checks pass. See TESTING.md and runbook.
No code deployment, publication, retirement, customer message or payment ran.
Owner can review/publish each draft through existing forms without waiting for
the new owner workspace in PR #80. Review withdrawing the fixed-INR-5,000 offer
when adopting its customer-choice replacement; do not silently migrate agreements.
Evidence is retained privately on the host; local documentation is kept on
`agent/offer-range-drafts-evidence` to avoid interrupting PR #80's CI.

**30 October 2026 - approved clearer names applied; owner plan workspace prepared.**
Owner explicitly selected **Flexible Gold Savings (22K)** and **Monthly Gold
Savings (22K)**. On production `b20241a`, existing validated services renamed
draft plan 4 (still inactive/unlisted) and transactionally withdrew/renamed/
republished plan 3. Monthly publication revision is now **5 / ID 7**. No economic
term or final visibility state changed; all other 49 scheme-model snapshots,
including existing agreement name/term snapshots, match. No pending monthly
applications existed. Configuration/agreement checks pass. Host-only evidence:
`/home/deploy/jsk-rollouts/20261030-plan-names/renamed.json` (700 directory/600 file).

Legacy plan 1 has 10 agreements / 9 customers; legacy plan 2 has 3 agreements /
3 customers. Both currently have zero pending requests/in-progress applications.
Neither was retired: recommended cutover is review/publish the replacement
flexible offer, then explicitly retire superseded offers. Retirement stops new
intake, not payments or settlement under existing agreement terms.

Local feature `agent/owner-plan-details` adds an owner-only GET workspace linked
from each plan row. Overview shows recorded rules, configuration and actual public/
enrolment availability. Paginated sections show separate agreements, distinct
enrolled customers with plan-scoped counts, both application sources and immutable
revision history. Archived/retired plans remain accessible. Names in agreement
rows come from accepted snapshots; stored status is not presented as effective
eligibility. Private responses are non-cacheable; GET appends no audit/revision
or financial record. Existing mutation/retirement services are unchanged. Regression
passed 51 tests; final workspace/manual checks passed 20 tests. Native Chrome
reviewed desktop light/dark and 390x844 light-mode synthetic layouts; the temporary
server/tab and database were cleaned up. See TESTING.md. Owner acceptance and
hosted CI/deployment remain; the new page is not deployed yet.
The branch includes the documentation-only parent changes from open PR #79.

**30 October 2026 - Flexible 22K offer prepared for owner review, unpublished.**
Owner authorized the next recommendation. Used the existing explicit services on
the deployed `b20241a` application to create configuration **2/v1** and plan **4**,
**FLEX22K-ANYTIME / Flexible 22K Jewellery Savings**. The audit records delegated
operator preparation, not an owner-interface submission or publication approval.
Proposed bounds copy existing legacy offer `fsp`: **INR 150-100,000 per contribution**,
no additional increment. These remain review choices, not approved new public terms.

Rules: variable optional contributions, **GOLD_22K_916 only**, no compulsory
instalments/duration/qualifying count, no bonus, flexible payment timing, and
positive verified entitlement permits requesting one final full showroom jewellery
settlement. Review, customer authorization, reconciliation and actual fulfilment
remain required; no voluntary metal-to-cash conversion. Further contributions may
continue before closure under the normal payment guards. Existing agreements are
not converted. Plan is inactive/unlisted, has no publication revision or agreement.

All existing rows across 53 scheme models match before/after. Only one configuration,
plan, revision and audit plus offering rows were appended; only the 22K offering is
active. Existing public offer IDs 3/2/1 and liabilities are unchanged. Configuration,
agreement and financial checks pass; public plan-detail access returns 404.
Host evidence: `/home/deploy/jsk-rollouts/20261030-flex22k-draft/prepared.json`
(directory 700/file 600). Next: owner reviews the actual draft, especially bounds
and anytime full-only eligibility, before separately authorizing publication.

**30 October 2026 - owner accepted the deployed Savings Plans presentation.**
After the requested production review, the owner reported "reviewed looks great".
The reviewed deployed presentation under FW-UX-006 is accepted; do not infer a
specific device/browser matrix, conversion improvement or approval of a new offer.
Next recommended product step is preparing one differentiated supported offer,
preferably flexible 22K, for review of its actual amount limits, eligibility and
full-only settlement terms before publication. This requires no new builder or
VA-waiver formula. Existing first-offer observation continues; its suggested
5 November review date is not a technical gate. Rollout evidence remains local
on `agent/denomination-offers-rollout-evidence` until pushed through review.

**29 October 2026 - FW-UX-006 presentation deployed and verified.**
Main CI `40884955268` passed and published release
`b20241ab961b24a6d7ca98e94cbf1c6ed1e67c3e`, digest
`c8f60b76ef601889b9ee10d440b00721556451a6194acc21a9f98a8f7f3cd86b`.
The exact image passed an isolated PostgreSQL 18.6 rehearsal covering synthetic
metal/INR offers, public pages, GET examples, POST refusal and unchanged scheme
records after illustration requests. The isolated containers and volume were removed.

Deployed to the authorized `172.235.9.77` host by pulling the digest, preserving
the compatible prior image and changing only APP_IMAGE/APP_RELEASE. No build,
migration, flag change, offer publication, enrolment, payment or refund occurred.
The first immediate Caddy probe encountered connection refusal and the safeguard
restored the prior release. Confirmed healthy rollback; bounded connection-refused
retries resolved the probe startup race and the second rollout passed.

Web is healthy; certificate-validated origin/public live/ready and all six public
page probes pass, including the existing plan 3 detail/example. All 14 financial,
contract, instalment, benefit and closure integrity commands pass. Fifty compared
scheme-model snapshots, 15 customers, 14 agreements and separate liabilities match;
pending orders remain zero. Both reminder/reconciliation timers are active and their
services report success. Final available RAM is 369 MiB; disk has 7.8 GB free (67%).
Private host evidence and the environment backup are retained in
`/home/deploy/jsk-rollouts/20261029-b20241a-presentation` (directory 700, files 600).
Engineering rollout is accepted. Owner commercial-copy/CMS follow-up and operating
observation remain distinct; this does not approve additional INR/benefit offers.

**29 October 2026 - FW-UX-006 PR #78 merged after successful full CI.**
Run `40875176430` passed on `216ba565b2a5bba0e9c6b6e665d861ef6919f33d`:
all four test shards, checks, required Django inventory gate and container job.
Final review found no blocking issue or unresolved review thread. The automated
security review completed on application-code commit `25f0b3b`; the later delta
was the reproduced governance-test correction and validation documentation.
Owner authorized proceeding; merged as `b20241ab961b24a6d7ca98e94cbf1c6ed1e67c3e`.
Fetched main and verified its complete tree matches the tested PR head.

Main run `40884955268` is in progress. Wait for its required checks and successful
digest publication before preparing an exact-image production rollout. No image
digest, production change, new offer launch or owner commercial-copy/CMS acceptance
is inferred from this merge. Production remains on the previously accepted release.

**29 October 2026 - PR #78 CI policy-copy regression identified and corrected.**
Hosted run `40865018323` on `25f0b3b` failed one of the 376 tests in shard 3:
the governance policy test still required date-only early-discontinuation wording.
The other three test shards, application checks and container job passed; the
required aggregate failed as a consequence of shard 3. Reproduced the exact
failure locally before changing the test. The corrected assertion covers normal
eligibility conditions, agreements longer than twelve months and rejection of a
blanket twelve-month cutoff on both terms and refund pages. Financial services,
policy copy and CI coverage are unchanged. Local verification and a fresh hosted
run are tracked in TESTING.md; this does not mark hosted CI or release accepted.

**29 October 2026 - FW-UX-006 local visual and copy review completed.**
The user authorized local desktop/mobile review. The in-app browser host was
unavailable, but a fresh native Chrome observation established the current URL.
Opened the synthetic loopback preview in a separate tab, preserving the production
edit tab. No safety setting was changed and no production form was submitted.

Reviewed desktop comparison/details at the 1600px browser width, mobile layouts at
390px (including 390x844) and narrow 320px, light/dark themes, opaque theme dropdown,
mobile navigation, keyboard focus/Tab/Enter, valid metal/INR examples, invalid
amount messaging and the final application action. Corrected findings: precise
offered-grade labels, aligned card actions, visible duration/missed-payment facts
in the detail summary, dark outline-button state colours and narrow-header overlap.
The mobile illustration anchor also clears the sticky header. Changes are display
projections/CSS only; accepted configurations and financial services are unchanged.

Observed INR example: principal INR 5,000.25, separately illustrated capped 5%
purchase-only benefit INR 250.01. Observed metal example: INR 3,333.33 / assumed
INR 14,667 per gram displays 0.227 g with the six-decimal/three-decimal explanation.
Invalid INR zero shows an error and suppresses results. A read-only database check
confirmed zero preview agreements, contributions, allocations, rates, principal
receipts and webhooks after the browser interactions. These are fictional offers,
not approved additions to the live catalogue or observed customer conversion.

The combined **99-test** local regression passed in **76.500s**, with Django checks
and no migration drift. Final **15 offer tests** passed in **7.421s**. The preview
tab/server were closed and its disposable database removed; see TESTING.md.
This completes the engineering visual/copy audit, superseding the earlier failed
automation attempt below. It is browser emulation, not a new physical Android
acceptance or formal accessibility certification. Owner commercial-copy/CMS
acceptance, hosted CI and reviewed deployment remain open; production is unchanged.

**29 October 2026 - FW-UX-006 presentation implementation prepared locally.**
Owner selected denomination-aware presentation as the next engineering item while
the accepted first offer remains under observation. Work is isolated on
`agent/denomination-aware-offers`; completed research/activation/enrolment evidence
was saved separately as `ed6e5c8`. No production change or additional offer launch.

Public home/comparison/how-it-works, About fallback/CMS wrapper, terms/refund/privacy
copy now distinguish exact-grade grams from INR principal and purchase-only benefits.
Removed blanket date-only eligibility and universal minimum-duration assertions;
legacy rights remain explicit. Shared About enrolment prose no longer claims signup
is closed. Cards expose comparable structured facts and link to a gated public
`/plans/<id>/` explanation with complete policy, exclusions and one application CTA.

Illustrations are GET-only, policy-bounded Decimal reads: one contribution, an
explicitly hypothetical rate/allowed grade for metal, or INR principal with no rate
or grams. Six-decimal quantity arithmetic/three-decimal display and existing capped
purchase-bonus/percentage-of-charges calculations are reused. Examples confer no
eligibility, award, payment authority, rate lock or spendable cash. Charges/taxes,
qualification and original-source final refunds are explained separately. No new
VA-waiver formula, model, migration, dependency or financial workflow was added.

Final regression passed **89 tests in 63.132s**, including silver/legacy/canonical
cases; **10 handbook tests** passed in 0.197s. Django checks and migration drift
checks pass. A stale fixture was corrected before the successful runs; see TESTING.md.
Desktop/mobile visual acceptance is **not complete**: Computer Use stopped because
it could not establish Chrome's current URL confidently enough to enforce policy.
No further app input was issued. The synthetic GET-only loopback preview was
stopped and its disposable database removed. Owner copy/visual approval, hosted CI
and reviewed deployment remain pending; INR/publication readiness is not marked
accepted by this engineering change alone. Review CMS-authored marketing content
alongside these shared templates before listing an INR offer.

**29 October 2026 - first configured enrolment verified; controlled acceptance complete.**
The owner reported successfully enrolling as the test customer. Read-only production
verification finds exactly one configured agreement: **JSK-958ABDE4 / ID 14**, ACTIVE,
plan **MC22K-5000-12M**, immutable offer revision **2**, configuration **1/v1**,
agreement schema **2**. Fixed amount **INR 5,000**, exact grade **GOLD_22K_916**,
required count **12**, duration **12 months**, calendar-month/once-per-period rule,
no post-cutoff collection and the frozen independent contract all validate.

The existing-customer request is ENROLLED, with matching schema-2/revision evidence,
disclosure version `2026-09-04`, retained customer acceptance at **15:42:20 IST**,
owner decision at **15:43:28 IST**, and exactly one enrolment audit. No identity,
email address, secret or raw consent payload is copied into this documentation.
The customer's receipt/approval email inbox was not independently rechecked here.

Start date is **29 October 2026**. There are **15** valid immutable periods:
12 original qualifying windows plus three ordinary replacement windows, all at
INR 5,000. The first is **29 October through 31 October 2026** (exclusive end
1 November); the twelfth ends before **1 October 2027**. The duration floor is
**29 October 2027**, so twelve payments alone do not permit earlier normal closure.
If missed payments require replacements, the final qualifying period and other
eligibility/authorization checks still apply. Current progress is NO_ENTITLEMENT,
zero qualified payments, not eligible; dates do not create an entitlement.

Comparison with publication baseline shows only **one new SchemeAccount**, **one
new SchemeEnrolmentRequest** and **15 new SchemeInstalmentPeriod** records. All
other 43 compared scheme-model snapshots, legacy offers and liabilities are
unchanged. Total agreements **14** (13 legacy, one configured); the new agreement
has zero contributions, metal allocations, provider webhooks, principal/cash
receipts or redemptions. Plan configuration/agreement, schedule/payment ledger,
enrolment request, financial exception, graded-rate and live Razorpay checks pass.
Evidence is retained under the existing protected host directory as
`first-enrolment.json`, `first-enrolment-baseline-comparison.json` and eight check
outputs. No production mutation was performed by this verification.

**Next is bounded operating observation**, not another enrolment/payment ceremony.
Recommend seven calendar days (29 October-5 November) before reviewing friction
and choosing the next single improvement; this is an observation recommendation,
not a new financial rule or a scheduled automation. Real payments are optional
customer decisions handled through existing verified workflows. `FW-UX-006` remains
the next presentation improvement before public INR offers. Separate overdue
deletion reviews still require owner attention. This completes the initial
activation/enrolment checkpoint, not every deferred backlog or future variant.

**29 October 2026 - approved configured intake enabled; first offer published.**
The owner approved the prepared offer unchanged ("i approve it as it is"), including
controlled intake activation and publication. On the existing release `8f3ba5a` /
digest `e9c126344938846b0e991644958265804317417636305447e364d99d10b75834`,
set only `CONFIGURED_PLANS_ENABLED=True` in the Linode production environment,
recreated web without building/pulling, waited for healthy, validated/recreated
Caddy and checked certificate-validated origin/public live/ready responses.

Published plan **3 / MC22K-5000-12M / 22K Monthly Jewellery Savings** through the
authenticated owner's existing publication form. Immutable offer revision **2**
(ID **2**) and `SCHEME_CHANGE` audit **118** record publication at **29 October
2026 15:32:25 IST**. Configuration **1/v1** and all approved terms remain unchanged:
INR 5,000 fixed; GOLD_22K_916 only; 12 months AND 12 qualifying calendar-month
payments; joining month counts; no extra grace/advance/bulk catch-up; three ordinary
replacements then review; separate acknowledged outage relief; no benefit;
full-only settlement and no post-cutoff collection. Public `/plans/` returns 200
and includes this offer, monthly terms and its application CTA.

All **46** compared scheme-model record snapshots, legacy offer fields and separate
liabilities match before activation and after publication. Existing plans remain
active/listed with 10 and 3 agreements; total agreements **13**, configured
agreements **0**. Gold remains **2.576623 g 22K / 0.329272 g 24K**; silver and
INR purchase-credit/legacy cash liabilities remain zero. Plan configuration,
agreement, financial exception, graded-rate, live Razorpay, INR principal and payment
operation checks pass. All grades remain OPEN with zero pending orders. Both
checkout-reconciliation and scheme-reminder timers remain active; their services
report Result=success / ExecMainStatus=0. One Python-client public TLS handshake
timed out; subsequent certificate-validated IPv4 curl live/ready probes passed,
without changing TLS, DNS or application security settings.

Protected host evidence: `/home/deploy/jsk-rollouts/20261029T100052Z-configured-intake`
(mode 700; environment backup mode 600). No application code/migration, real
customer enrolment, payment, refund or customer message was created by activation.
**Next: one genuine customer application and owner-approved enrolment**, checking
the frozen revision/configuration, amount, grade, monthly periods/count/dates and
consent without requiring payment. No customer has been selected or enrolled by
automation. The earlier disabled/draft checkpoints below are historical.

**29 October 2026 - first real configured offer prepared, inactive and unlisted.**
Using the authenticated production owner interface, inspected the empty configuration
catalogue, reviewed the server-generated independent-policy preview and saved
configuration **1 / v1** (family `2fdc420f-6129-423a-926f-191a38ae3e48`). Created
draft plan **3**, **22K Monthly Jewellery Savings**, code `MC22K-5000-12M`, offering
only `GOLD_22K_916`. The owner plans screen confirms preparation-only/unlisted,
zero agreements for the draft, and existing plans still active/listed with their
10 and 3 agreements. No existing offer was edited or retired.

Proposed review terms: showroom-fixed INR 5,000; 12-month duration AND 12 qualifying
calendar-month payments, including the joining month; at most one qualifying
payment per period; zero extra grace/no bulk catch-up or advance payments; three
ordinary replacement periods then review, preserving paid entitlement. Outage
compensation stays separate and customer-acknowledged. No bonus/VA discount or
post-cutoff contributions. Full-only exact-grade jewellery settlement; early exit
needs authorization/reconciliation, with no voluntary metal-to-cash payout.
These are proposed draft terms, not owner publication/activation approval. Internal
notes and both audit reasons explicitly retain that boundary.

The live owner guide confirmed configured intake disabled. No environment change,
publication, enrolment, payment, refund, rate publication or customer message was
performed. Next is owner acceptance/amendment of the concrete offer and its
customer-facing terms, followed by separately approved controlled activation.
Policy changes require a successor immutable configuration, not an edit to v1.

Read-only host verification confirms release `8f3ba5a`, configured intake false,
plan 3 inactive/unlisted, only GOLD_22K_916 offered, zero draft agreements and 13
total agreements. The publication selector reports only the disabled release gate.
Financial exceptions pass with paid/unallocated, failed/mismatched webhooks,
expired checkouts, unresolved optional orders and refund-disposition errors all zero.
Origin certificate-validated live/ready probes pass; public apex readiness returns
200 and www returns its existing 301 redirect. Containers remain healthy, with
394 MiB available RAM during diagnosis.

The browser briefly showed HTTP 502 and then 525 while opening the read-only
publication page. No corresponding web crash/error was found; Caddy recorded a
successful 200 review response in 0.266s. After one safe GET reload, the actual
owner publication page loaded successfully and showed only the disabled intake
gate, with Publish disabled. Root cause of the transient transport failure is
unproven; recurrence needs investigation, not an assumed application fix. No TLS,
proxy, DNS, restart or security-setting change was made.

**29 October 2026 - competitor research documented; controlled activation stays next.**
Owner requested preserving the public-market audit and reconciling it with the
deployed builder rather than starting every suggested improvement. MVP_PLAN.md now
records official sources/limits, core-versus-exact compatibility, benefit-basis
arithmetic, presentation/onboarding observations and the recommended sequence.
FUTURE_WORK.md tracks denomination-aware presentation as `FW-UX-006` and selected
financial-policy extensions as conditional `FW-PLAN-009`, reusing `FW-PRICE-002`
for early-exit tiers. No new ADR: this is research/sequencing, not an accepted new
financial contract or architecture change.

Next remains one owner-reviewed supported configuration/inactive draft, explicit
activation approval, publication of only that offer and one genuine enrolment
without requiring payment. Recommend a 22K exact-metal/no-new-benefit offer for the
first operating sample; owner must confirm actual terms. INR/benefit engineering
is not removed from scope or labelled unfinished. Shared metal-only public copy
must be corrected before public INR listing; another benefit formula must be
implemented before its promise is advertised. These conditional gates do not
reopen completed CI/device/image acceptance for accurate supported metal offers.
Three overdue deletion reviews remain prompt, separate owner operations. The
research produced no competitor account/payment, code, database, environment or
production change. Configured intake remains disabled per the deployment record.

**29 October 2026 - builder release deployed; configured intake remains disabled.**
Normal CI `40799459905` passed on `46c7fd8`: all **1,492 tests** exactly once,
four successful 373-case PostgreSQL shards, complete inventory verification,
migration/drift/application/deployment/static checks and container build/critical
scan. Downloaded reports were independently reverified. Total hosted job span was
62m39s (06:46:57-07:49:36 IST); the previous serial base suite was about four hours.
Different application revisions/runner conditions mean this is an operational
comparison, not a controlled benchmark. Profiles retain the observed shard imbalance
for later tuning without dropping tests.

Final release review found no additional merge-blocking issue in the reviewed
publication/default-off intake, owner/customer scoping, frozen-contract/source
confirmation, full-only settlement and original-source refund/actual-fulfilment
boundaries. Branch protection remained enforced, required checks were green and no
review thread was unresolved. Marked ready and merged the exact tested head as
**8f3ba5ad0000a3645f69eddf63607436f91720a8**. The merge tree matches `46c7fd8`;
no new application change was inserted after CI. Local main was fast-forwarded.
The PR review/body and merge message retain the green CI and separate rollout boundary.

Main run **40818256991** passed all four shards, aggregate inventory verification,
checks, publication and the published-image critical scan. The approved-tree image is
`ghcr.io/rajeshr188/jsk-savings@sha256:e9c126344938846b0e991644958265804317417636305447e364d99d10b75834`.
Its revision label matches `8f3ba5a`. Isolated PostgreSQL 18.6 exact-image upgrade,
complete retained-history dump/restore, history-loss downgrade refusal, forward
reapplication and Gunicorn live/ready checks passed. The upgrade regression passed
one test in 60.027s. See TESTING.md for liabilities, hashes and latency limits.

The owner confirmed **29 October 2026 10:00 AM IST** recovery-point availability
and approved the exact digest rollout with configured intake disabled. On
`172.235.9.77`, the operator stopped both timers/services, automation recorded an
audited payment pause, stopped web and captured the baseline. All **39 migrations**
through schemes.0057 applied successfully, including the deployed-checkout merge.
Hashes of all original fields/rows across **20 existing scheme models** matched
before migration, afterward and again on the running release. Counts remain
**15 customers, 13 agreements, zero pending Razorpay orders**. Liabilities remain
**22K gold 2.576623 g; 24K gold 0.329272 g; silver 0.000000 g; legacy cash principal
and earned bonus INR 0.00**. New INR purchase-credit liability is zero.

Web is healthy on `8f3ba5a`; Caddy validated/recreated, public live/ready and homepage
returned 200, private owner plans/configuration/manual routes redirect anonymous
visitors to login. All builder, financial, grade, live-payment, cash, authentication,
registration/enrolment and Google integrity checks passed. No pending migrations or
recent web error markers were found. Prior payment controls were restored through
the audited service; all grades are OPEN. **CONFIGURED_PLANS_ENABLED=False** and
zero configured offers/agreements remain. Existing registration/enrolment flags
were preserved. Capacity: 358 MiB available RAM, 8.2 GB free disk (65% used).

The deletion diagnostic reports **three overdue owner reviews**, with structural
error counters zero. The previous image produces the identical result against the
same retained records: existing operational backlog, not a migration regression.
Do not silently clear these reviews. The initial Python HTTP client received a
Cloudflare 403; normal-browser-user-agent public checks and origin checks passed.
Existing HSTS scope/preload warnings remain unchanged.

The operator restarted both timers; both are active with future runs scheduled and
service result/exit status success/0. New configured intake activation remains a
separate decision. Recovery is forward with compatible code and retained
history; the pre-builder image is not approved over new configured records.
Protected host evidence is under `/home/deploy/jsk-rollouts/20261029-8f3ba5a`;
environment backup is mode 600 inside a mode-700 directory; the temporary candidate
environment copy was removed after deployment. Synthetic rehearsal
containers/database volume were removed; ignored local logs remain.
This separate evidence branch collects the final image/rollout record without
changing the merged application candidate. Separate staging remains deferred under
FW-PROD-009; the accepted isolated exact-image rehearsal remains required.

**29 October 2026 - first optimized CI failures reproduced and locally fixed.**
Run `40786013227` on `fb59370` completed all four 373-case shards. Shards 0/3,
application/migration/deployment/static checks and the container build/scan passed.
Shard 1 had one INR recovery assertion failure; shard 2 had seven missing-table
errors. All 1,492 discovered test IDs started exactly once, and the required Django
gate correctly refused approval. This is not a passed release candidate.

The exact nine-case local reproduction matched **one failure/seven errors in
52.070s**. The independent-draft rollback-refusal test reversed newer additive
migrations before 0050 correctly refused, but left the test database downgraded.
It now restores current graph leaves even after assertion failure and verifies
the full current table set plus retained plan/revision. The INR classification
assertion still expected the foundation's closed runtime gate. Its replacement
checks eligible read-only preview, principal-save failure rolling back payment/API
evidence/event status, and successful idempotent owner recovery creating exactly
one principal receipt. Production services, migrations and financial guards are
unchanged. The exact failing-order regression now passes **9 tests in 168.798s**
(206.720s including database setup/cleanup); the broader API/integration regression
passes **31 tests in 49.649s** (96.559s total). Native CI-runner profiles verify
complete planned/executed identity and successful results. Django system and
migration-drift checks passed; disposable databases were removed.
A fresh complete optimized CI run remains required before merge/deployment.

**29 October 2026 - CI optimization prioritized before the next release run.**
The owner requested FW-CI-001 now. Cancelled both duplicate `e27f820` CI runs
(`40783890107` PR / `40783885495` push). Four isolated runner/PostgreSQL jobs now
execute complete test classes serially. Normal discovery finds all 1,483 previous
tests plus nine infrastructure checks: 1,492 total, 373 per shard. The required
`django` gate verifies complete execution reports and all validation jobs; required
`container` build/scan and main publication gating remain. Superseded PRs cancel,
feature push duplication is removed, and main publication is not interrupted.
All-test timing artifacts and slowest-case output support measured later rebalance.
Nine pure infrastructure checks passed in 0.103s; native CLI inventory and checksum-
verified Actionlint passed. Native CLI validation passed **12 tests in 75.701s** (115.862s total,
including 39.459s database setup), exercising a real migration round trip, threaded
checkout race, exact-grade metric and infrastructure cases. The complete profile
matched all executed/planned IDs. The migration took 65.135s, metric case 1.546s
and concurrency case 0.968s; this is representative local profiling, not a full
suite speed claim. The extended four-shard execution/gate test passed in the
final nine-case native-CLI infrastructure rerun (0.096s).
Current optimized hosted CI remains required; no speedup is claimed before its
measurement. No application financial rule, production settings or host changed.

**29 October 2026 - bounded builder readiness implementation and regression.**
Validated schema-2 policies now reach the actual publication, enrolment, collection,
eligibility and full-settlement workflows. Schema-1 interpretation stays restricted
to its existing families; agreement/configuration encoding and denomination must
match. New intake remains default off. Existing agreement rights and notices no
longer depend on that intake switch; reminder-specific switches and fresh evidence
checks remain. Legacy schedule/eligibility helpers reject independent policies
explicitly. An INR cash source missing its principal receipt refuses correction
with a ValidationError and transaction rollback. No source, fulfilment or database
financial invariant was relaxed. Migration 0057 changes only the INR display label.

The 156-test affected regression passed in 899.413s, including 20 unmocked complete
journeys (five families x both denominations x cash/verified online). A further
47-test proof/eligibility/metric batch passed in 315.044s, and all 10 updated handbook
HTTP/access checks passed in 0.188s. Final boundary/reminder regression: **64 tests in 679.930s, OK**, including
migration round trips, retained-notification guards and concurrent dispatch checks.
Django system checks, migration drift and syntax/diff checks passed; each disposable
test database was destroyed.
These are isolated local PostgreSQL tests using Python 3.13 / Django 6.0.4, not a
current-head hosted CI or final production-image result. The earlier full 1,473-case
CI remains evidence only for 6c5034b. The acquisition-cost metric is committed as
de52665. Final current-head CI, image/recovery review and explicit production rollout
approval remain; no production environment or customer record changed.

**29 October 2026 - customer metal acquisition-cost metric implemented and locally verified.**
The metal agreement page now shows historical average acquisition cost per gram:
paid INR divided by exact-grade grams across completed recorded allocations. It
uses the same PAID allocation basis as the balance, full stored precision and Decimal
rounding to two INR decimals. It excludes reversed/unallocated/unsuccessful payments;
redemptions affect remaining grams but not this historical average. Empty allocation
sets show Not available. INR purchase credit and legacy cash have no metal metric.
The read is one aggregate query and creates no rate, balance or financial record.
Seven new metric cases plus owner-manual and existing cash regressions passed:
**31 tests in 70.949s**, with Django/drift checks passing. An initial fixture gave
pending attempts paid-confirmation fields; the database correctly refused it, and
the fixture was corrected without relaxing the constraint. Imports were then scoped
through their modules to avoid collecting existing fixture TestCase classes twice.
The illustrated handbook is Edition 5. Readiness activation regression remains in
progress; the earlier full CI does not cover these later application changes.
No production change.

**29 October 2026 - Android customer acceptance confirmed; light dropdown visibility corrected.**
The owner answered "All checked and usable" for the physical Android customer
review: amounts/units, pending versus completed history, receipt/statement,
navigation/back, theme switching and logout without clipped content. This completes
the agreed representative browser check on model 24090RA29I / Android 16 / Chrome
156.0.8078.47 against the `6c5034b` runtime. It is not a real-payment or production
TWA test. The final retained-history assertion passed, the review process exited
successfully, its exact disposable database was verified absent, and only USB
forward tcp:8767 was removed.
The owner subsequently reported translucent light-mode dropdowns. Removed the
mobile navbar's translucent/pale-text overrides; Account and Appearance menus now
use the solid theme surface, explicit text colours and readable selected/focus
states at every width. Actual header/style preview in Chrome at 390/1280 px verified
opaque light RGB(255,253,249), text RGB(36,25,20), and opaque dark RGB(37,33,29)
with text RGB(243,236,226). Keyboard focus remained visible. No financial workflow,
framework or production setting changed. This CSS follow-up is locally verified;
the prior full-CI pass still applies to `6c5034b`, not later runtime changes.
Next is the bounded readiness activation implementation/tests and final release
image/recovery approval. Production remains unchanged.

**29 October 2026 - physical Android customer review prepared; result pending.**
The authorized USB-connected device is model 24090RA29I. A fresh loopback-only review
database serves the `6c5034b` application runtime; later local changes are excluded
tests/Markdown. USB reverse forwarding exposes localhost:8767 on the phone without
a LAN listener or production deployment. Synthetic cases cover active 22K metal,
completed INR full settlement, pending INR disposition and an uncertain order.
All eight real customer GETs passed private-response assertions; an owner route
refused customer access and retained scheme row hashes stayed unchanged. Only login
and logout POSTs are permitted by this review harness; external provider/storage/SMTP
calls are blocked. The phone opened the review page, and the owner has been asked to
check readability, units/status/history, receipt/statement, theme, back navigation
and logout. No physical acceptance is inferred from these technical checks.
The temporary server has a three-hour cleanup lease. Backend readiness review is
recorded in MVP_PLAN.md; runtime gates and production remain unchanged.

**28 October 2026 - normal combined CI passed on the release-validation application candidate.**
Run `40670193738` on `6c5034bb50d5097d8e4dad1817999a239b3e77b5` completed
successfully: **1,473 tests in 14,359.871s** (about four hours), with zero failures
or errors. Initial migrations, migration drift, application checks, production
deployment checks, collectstatic and the separate image build/critical scan passed.
The CI-only loopback PostgreSQL connection produced the expected non-blocking TLS
warning; this is not approval to weaken managed production database TLS. Image
publication was skipped because this was a PR run. The full-CI blocker for this
application source is cleared. The local recovery evidence/harness follow-up
`182a1fe` is separate and changes only excluded tests/Markdown; this pass must not
be attributed to an untested later application or activation change. Laptop operator
and four-email acceptance remain complete. Next: the deferred physical Android
customer smoke test, coherent readiness activation with its affected checks/CI,
then final published image/recovery evidence and explicit rollout approval.
No merge, publication activation or production deployment follows automatically.
CI duration profiling and safe test-group parallelization are now tracked as
deferred `FW-CI-001` in FUTURE_WORK.md, preserving full coverage and isolated
migration/concurrency checks; this adds no new current-release gate.

**28 October 2026 - current local image recovery rehearsal passed, including catalogue history.**
Application source `6c5034bb50d5097d8e4dad1817999a239b3e77b5` built with the normal
Dockerfile as local image
`sha256:282eaac8cee2d2ab18a852b515c07af9d12808f3d36eb7684216dcb83e1dcec3`.
The read-only mounted harness now seeds archived draft/configuration and retired-plan
evidence through real services. On isolated PostgreSQL 18.6, dump/restore preserved
every schemes row/column hash, including three catalogue closures. Separate outstanding
liabilities stayed INR 500.00 and GOLD_22K_916 0.050000 g; returned benefits retained
their expected review holds. Whole-graph 0056 downgrade refusal, eight retained-history
guards and forward recovery passed. The deployed-checkout upgrade test passed inside
the image: **1 test in 67.801s**, with Django checks passing. Final snapshot/liability
comparison passed and only the identified disposable container and volumes were removed.
Three-sample owner-page medians at 1.5 ms added per query were 1.742s INR / 0.860s
metal; at 10 ms, 5.854s / 3.168s. Read-only assertions passed; substantial read overhead
remains a documented limitation, not a production latency SLA. Exact harness/manifest
identities and initial fixture correction are in TESTING.md. Normal CI run `40670193738`
on `6c5034b` remains in progress; its container build/critical scan passed. This local
image is not a published or approved production recovery digest. Laptop operator
acceptance remains complete; Android customer smoke, coherent readiness activation
and final release/recovery approval remain pending. No production change.

**28 October 2026 - five CI issues reproduced and affected regressions pass.**
An isolated six-test run reproduced the exact one failure/four errors in 48.259s.
The reminder reverse-guard test allowed newer migrations to unapply before 0051
correctly refused history loss, then left the test schema downgraded. This caused the
following legacy reminder setup and three INR correction tests to query absent tables.
The test now restores current migration leaves after the refusal, asserts the full
table set is restored and registers cleanup for both migration journeys. Production
migrations and their retained-history protections are unchanged. The owner plan-table
redesign also omitted the legacy bonus disclosure; its percentage/minimum duration
is restored within the existing Plan cell, labelled for historical cash agreements.
The exact original assertion is retained and now also checks the historical scope.
Django and migration-drift checks passed. All **53 related reminder/correction/bonus/
catalogue tests passed in 287.446s**, including the five original cases and the
predecessor that exposed the test-schema leak. The isolated test database was
destroyed. Normal combined CI on the resulting candidate remains required.

**28 October 2026 - completed full CI reports five issues requiring diagnosis.**
Run `40650621396` on `b2a9d62` finished: **1,473 tests in 6,829.483s,
one failure and four errors**. The container build/critical scan, initial migrations,
drift and application checks passed; deployment checks, collectstatic and image
publication were skipped after test failure. The errors report missing catalogue/
refund-resolution tables during historical reminder-migration and INR correction
transaction fixtures; the failure expects the legacy cash bonus percentage on the
owner plan list. These are traceback observations, not a completed root-cause analysis.
Next engineering action: reproduce these five cases in isolation, correct their
underlying causes and obtain normal current-candidate CI. Laptop operator acceptance
below remains valid for its agreed scope; this CI run does not authorize release.

**28 October 2026 - laptop operational acceptance confirmed by the owner.**
After the guided review of source `b2a9d62`, the owner explicitly answered:
"Yes—the operator can follow these decisions" for holding/escalating uncertain or
duplicate payments, using original-source refund routes, retaining completion and
customer receipt evidence, and closing only after zero outstanding with no unresolved
payment issues. Together with the recorded synthetic technical/browser evidence, this
completes the agreed four-case laptop operational acceptance. Basic keyboard control
reachability and readable labelled forms were technically checked. It is acceptance
of the demonstrated procedure, not an assertion that real funds were refunded.
The physical Android customer smoke test is explicitly deferred until later and
remains pending before activation. Full CI, coherent readiness activation, final-image
recovery and production approval remain separate; no production setting was changed.

**28 October 2026 - guided laptop explanation; Android check deferred.**
The owner requested a guided explanation instead of confirming operator acceptance,
and explicitly chose to complete the laptop review now with Android later. Chrome
revisited the actual held-payment queue, completed cash case and pending original-
method refund case. Explained containment/escalation, INR 500 = 360 principal applied
to jewellery + 140 cash return, and INR 1,000 = 500 applied + 500 original-method refund
still owed. Recorded principal remains history; outstanding principal determines what
remains owed. Explained completion/reference/customer-receipt evidence and the final
zero-outstanding/no-unresolved-issues closure decision. No new financial actions were
performed during this explanation. Operator understanding is awaiting the owner's
response; the physical Android customer smoke test remains required before activation,
with its timing deferred rather than recorded as passed.

**28 October 2026 - lean operational acceptance prepared; technical cases reviewed.**
The owner accepted the short acceptance scope: four laptop cases, recognition and
escalation for provider exceptions, one representative Android customer smoke test
and basic critical-screen keyboard/usability checks. The handbook and release plan
now distinguish required safeguards from deferred device matrices, specialist audits,
automated refunds and advanced recovery training. Four-email readability and the
owner's Android premature-completion refusal are carried forward as completed evidence.
On source `b2a9d62`, 24 manual/capture/refund/changed-source acceptance checks passed
in 65.086s; Django checks passed and their isolated database was destroyed.
A separate host-loopback review database seeded real lost-response, late-timing and
different-duplicate cases with external payment/storage/SMTP blocked. Startup checks
proved no uncertain credit, retained late review and one principal receipt for the
duplicate order. Chrome reviewed the visible queue and disabled unsafe recovery.
The cash example moved INR 500 -> 140 -> 0 outstanding, then explicit completion
retained its INR 360 jewellery and INR 140 simulated cash-return evidence. The online
example retains INR 500 original-method refund outstanding after simulated handover;
completion is disabled. Keyboard navigation reached the recovery confirmation and
Check provider controls. The reviewer has been asked for operator observations; no
physical Android device was connected at preparation time. These remain pending,
not inferred from the agent's technical results. The temporary review has a three-hour
cleanup lease. No production change, real refund or external customer message.

**28 October 2026 - independent customer payment/status integration verified.**
On `agent/independent-customer-workflows`, customer availability now uses the existing
independent admission/resume checks behind the unchanged runtime readiness guard.
It reloads the agreement and checks closure, customer containment, live gateway,
uncertain/expired orders, frozen terms, periods and denomination-aware operations.
INR entry and checkout no longer demand a metal rate; checkout names INR principal
correctly. Existing checked checkout links can resume; stale creation forms cannot
create another order. Independent effective status uses its own read-only eligibility
projection, and the legacy metal/duration preview explicitly rejects schema 2.
All **137 affected tests passed in 242.760s**; Django and migration-drift checks passed.
Tests include all five families in both denominations, actual HTTP creation/checkout
with synthetic provider responses, unchanged stored status and read-only GETs.
Operational readiness is simulated only in integration tests; real publication and
payment gates still refuse activation. No new migration or production change.
Full CI on prior head `321c32e` (run `40648920451`) is still testing; its container
build/security scan passed. Final integrated CI, remaining operator/device evidence,
coherent readiness activation and final-image recovery/rollout remain outstanding.

**28 October 2026 - denomination-aware publication integration verified locally.**
Handbook/catalogue commit `698dff1` is integrated into draft PR #77; its normal CI
run `40647586082` is in progress, with container build/security scan passed.
On `agent/builder-publication-activation`, publication now requires exact grades for
metal offers and prohibits them for INR purchase credit. The review page lists actual
service blockers instead of an unconditional schema-2 button restriction; POST still
revalidates. All 46 affected publication/draft/catalogue tests passed in 86.496s.
The five-family, two-denomination integration cases simulate workflow acceptance
only in tests, retaining real policy validation, revisions, enrolment and audit.
They do not establish operational activation: real schema/payment guards remain
closed. The remaining customer availability, effective-status and legacy-preview
integration points are tracked in MVP_PLAN.md before any coherent activation change.
No production change or release approval is implied.

**28 October 2026 - owner reviews preparation; manual explains the complete matrix.**
The owner reviewed configuration and inactive draft-plan creation and requests the
remaining release sequence. The handbook now includes the five-family eligibility
table, compatible denomination/amount/schedule/benefit choices, immutable-rule versus
offer distinction, and the scoped 268 categorical combinations (104 exact-metal,
164 INR). A reproducible validator enumeration holds numeric values constant and
does not imply a product-count limit or publication acceptance. All 22 policy/manual
tests passed; Django checks passed. Publication remains blocked by the disposable
sandbox, default-off release setting and unreconciled operational/schema guards.
The publication service's metal-only offering check is addressed by the subsequent
local integration above. This review does not approve the remaining provider-exception/refund
operations, final-image recovery or production activation.

**28 October 2026 - catalogue archive/retirement implemented and locally verified.**
The owner requested production housekeeping and flagged the configured-plan table's
spanning-row layout. Work is isolated on `agent/plan-archive-retirement`; existing
integration CI remains on `8f18263`. Migration 0056 adds retained one-way catalogue
closure evidence with constrained target/action/actor/reason and a downgrade refusal.
Owner confirmation/reason, fresh usage review and row locks protect archive/retire;
new drafts/intake/republishing are blocked for closed items. Existing agreements and
pending requests remain intact. Default lists hide closed items, with explicit history
filters; each plan now aligns with eight table columns. The illustrated handbook
documents the workflow. All 84 affected tests passed in 144.706s; Django checks and
migration drift checks passed. Chrome verified inactive draft creation, archive,
default-list removal and retained history. At a 390px viewport, all eight cells remain
inside a horizontally scrollable table without page overflow. The laptop harness now
allows draft creation and catalogue housekeeping; publication/enrolment remain blocked
and external calls remain disabled. This supersedes its earlier plan-creation refusal.
Integration run `40638199541` on `8f18263` is still running its full test suite; its
container job passed. That run does not cover this later feature. No production
deployment or activation occurred.

**28 October 2026 - owner confirms test-email delivery and readability.**
The owner confirms that all four authorized synthetic messages (request acknowledgement,
agreement approval, eligibility reminder and final settlement) arrived and are readable.
This closes the pending inbox observation; no further email was sent. It does not
constitute complete operator/device or activation acceptance. The reported preparation
POST refusal came from the disposable review harness, whose write allowlist covered
only login and the two seeded settlements, not an application policy-validation failure.
The ignored local harness now permits only the additional independent-policy create
route (preview/save), binds directly to laptop loopback, and uses fresh synthetic data
from `8f18263`. Its real middleware/view checks passed: preview creates no version,
save creates one preparation version, plan creation returns 403, and plan/account/
contribution/allocation/INR receipt counts remain unchanged. External calls remain
blocked and the three-hour database cleanup lease remains. Production is untouched.

**28 October 2026 - full-CI failure diagnosis and isolated payment fixtures.**
All six failures from run `40511542243` were reproduced locally in 37.268s
after removing ambient `RAZORPAY_*` variables. The monthly-eligibility and
scheme-closure test classes configured fake API credentials but omitted the webhook
secret, depending on developer environment settings. Both fixtures now explicitly
provide a synthetic webhook secret. New negative cases retain the real missing-secret
payment-availability and checkout guards; production code and CI credentials are unchanged.
All 63 tests across both affected classes, Razorpay gateway and deployment checks
passed in 140.134s with ambient Razorpay settings removed; Django checks passed and
the disposable database was destroyed. This includes all six original failures and
both new missing-secret regressions. A fresh normal full-CI pass remains required
before release acceptance; no production or activation change was made.

**28 October 2026 - owner handbook Edition 4 and INR status wording.**
The canonical illustrated handbook now starts with the full offer-to-closure journey,
uses the independent builder as the current preparation path, and explicitly scopes
the earlier editor/screenshots. It separates INR principal from metal grams, explains
unused cancellation, authorization, actual fulfilment and final closure, and includes
a five-step INR 500 / 360 / 140 worked example plus field-by-field receipt guidance.
Phone practice instructions distinguish the full metal rehearsal from seeded INR
mid-workflow cases. Owner training remains separate from engineering test acceptance.
INR settlement, closure review/history and queue now use denomination-correct display
wording; stored statuses, events, financial services and release controls are unchanged.
All 14 affected manual, presentation and actual partial-fulfilment HTTP tests passed
in 11.080s; Django checks passed and the disposable test database was destroyed.
Chrome manual checks at 320/390 CSS pixels found no page-wide horizontal overflow;
the cramped new three-column example was replaced by readable stacked steps.
No migration, production change, new message or activation was performed.

The completed remote CI run `40511542243` for `d12e18b` is **not passing**:
1438 tests ran in 8870.990s with six failures in monthly eligibility and closure
payment-availability/checkout tests. Deployment checks/collectstatic were skipped.
The next engineering step is to reproduce and fix these failures, then obtain clean
current-head CI; the focused pass above does not replace that requirement.

**28 October 2026 - guided owner review and technical walkthrough.**
The owner reached the isolated Android review and confirmed that completion before
fulfilment was refused. They requested an agent-led technical review because the
operator workflow is not yet familiar; this is not blanket operational acceptance.
The disposable review was restarted after its three-hour expiry and USB forwarding
restored. Browser review of the cash-origin case confirmed INR 500 outstanding
before fulfilment, INR 140 remaining after the simulated INR 360 jewellery handover,
and closure still blocked until the simulated INR 140 cash return. At zero outstanding,
explicit full closure succeeded and retained both fulfilment records. All references
are labelled synthetic; external provider/mail calls remain blocked. Production and
publication gates are unchanged. Owner training and inbox observations remain pending.
The online case likewise retained INR 500 outstanding after jewellery handover and
blocked closure. Future-dated refund evidence was rejected; corrected simulated
original-method refund evidence reduced the balance to zero and explicit full closure
succeeded. Both seeded cases passed the technical browser walkthrough. The generic
"Full jewellery settlement completed" INR heading needs clearer wording; the test
begins after proposal preparation and does not replace a full owner training journey.

**27 October 2026 - isolated owner/device acceptance environment prepared.**
The owner confirmed an Android device and development computer are available on the
same network. A temporary review server for source `1705199` now uses a fresh random
localhost PostgreSQL database with synthetic cash-origin and online-origin INR
settlement cases. Only fixture readiness is simulated; source, authorization and
fulfilment checks remain real. External HTTP/provider and SMTP calls are blocked,
mail is in-memory, and write routes are restricted to login and the two settlement
workspaces. Authenticated fixture GETs and LAN review/login HTTP 200 checks passed.
Physical-device/owner results remain pending. The helper and temporary credentials
are ignored local artifacts; the server expires after three hours and drops only its
own database. No normal local or production records/configuration were changed.
The phone reached the listener using TLS against its HTTP-only port; this explains
the reported connection failure without a firewall change. The owner authorized and
connected USB debugging; a loopback relay and device reverse mapping now expose the
review as localhost:8767. The temporary listener was made threaded with 15-second
socket timeouts after an incomplete connection stalled its single-threaded version.
The first synthetic database was cleanly removed before restarting fresh fixtures;
desktop browser login and the pending-settlement page now work. The full-closure
button is disabled while principal remains outstanding. Android acceptance is
still pending. Four clearly labelled synthetic inbox samples were captured by three
passing workflow tests (23.797s). The owner then explicitly authorized the four TEST
messages to the developer inbox; Postmark SMTP accepted all four with tracking off.
Arrival and Android readability confirmation remain pending. The send used the
existing SMTP connection without application data, configuration or service changes.

**27 October 2026 - INR business confirmation and refund-route approval.**
The owner now confirms that the offered terms, accounting treatment and provider
arrangements support the INR purchase-credit product. The subsequent explicit
refund decision is cash return for cash-origin contributions and manual Razorpay
dashboard refunds to the original payment method for Razorpay-origin contributions.
No automated refund API or blanket online-to-cash substitution is authorized.
ADR-0017 records the procedure and evidence boundary. This supersedes the earlier
pending business-confirmation status below; it is owner-supplied confirmation, not
an independent legal/accounting audit or a completed operational rehearsal.
Current code already implements source-specific fulfilment evidence and full-only
closure, so this decision needs no financial-code change. Actual owner/device/inbox
acceptance, clean exact-head CI, recovery-digest approval and coherent activation
remain outstanding. Production and configured-plan gates remain unchanged.
The authenticated owner reference manual now includes the approved source-by-source
refund procedure, required receipt evidence and pending/unavailable-route handling.
Its existing 10 HTTP/privacy/markup tests passed in 0.110s; Django checks passed.
This is documentation verification, not operational fulfilment acceptance.

**27 October 2026 - current-candidate visual acceptance preparation.**
The `6038277` candidate rendered 16 real owner/customer pages and two captured
completion emails from an isolated synthetic test database (one export test,
32.436s; database destroyed, no external mail). Chrome review at 320, 390 and
1280 pixels found no page-level horizontal overflow. Labels and sampled error
associations passed. Review found missing Bootstrap button keyboard outlines and
contrast gaps in theme buttons, secondary status badges, light-mode links and
validation text; the stylesheet follow-up corrects these. Both themes now pass
the sampled solid-background text checks, with 3px button focus outlines.
This is engineering preparation, not owner/device/screen-reader/inbox approval.
Current-head CI is still required after the styling follow-up. Production and
configured-plan gates remain unchanged; see the later approval record above.

**27 October 2026 - ordered builder-release goal in progress.**
Work continues in the isolated `integration/builder-release-validation` worktree,
draft PR #77. The 703-case diagnostic continuation finished: 692 unique tests passed;
the 11 affected tests produced nine failure events and three errors, all covered by
the already-corrected migration fixtures/guards and Account-button regression.
This split run is not a passing full-suite result. Normal CI remains required.

The exact `fcc5cd7` image passed the configured-history PostgreSQL 16 restore and
retained-evidence downgrade-refusal drill. Read-only SSH then verified production
release `d0e5dd1` and PostgreSQL **18.6**; 30 warmed SELECT 1 samples measured median
0.422 ms / p95 1.292 ms from the serving container. No production settings, records
or services changed. CI now targets PostgreSQL 18.6, and the same-version isolated
rehearsal passed as recorded below. The latency probe is a point sample, not an application SLA.

Owner history reads now reuse successfully validated historical
closure/disposition traversal within one read-only invocation. Current-source checks,
fresh mutation authority and complete retained-history checks remain in place.
The exact `232284f` image passed PostgreSQL 18.6 configured-history restore, retained
rollback refusal/forward recovery and the deployed-checkout upgrade regression.
The earlier `fcc5cd7` image also read this restored history without a downgrade;
published recovery-digest approval is still required. At an injected 1.5 ms/query,
two-return page medians were 1.868s INR / 0.811s metal (one CPU, 768 MB); all financial
hashes stayed unchanged. TESTING.md records scope, higher-latency results and family
coverage. Rehearsal containers/volumes were removed. The **31-case** history, benefit,
concurrency and migration regression passed in **1253.741s**; normal CI remains
running. Remaining order: current-head CI, owner/device/inbox acceptance,
approved recovery digest, documented INR publication
and usable refund-route evidence, then coherent activation and approved rollout.
The earlier pending business confirmation is superseded by the approval record above;
operational evidence remains required and no gate has been opened.

**27 October 2026 - consolidated migration-test follow-up.**
Seven focused migration cases now pass across independent agreement storage,
enrolment requests, INR principal and benefit reapplication. Older tests expected
0040/0045 refusal even though 0050 now protects retained independent-plan evidence
first, or tried to create current-service fixtures after removing required tables.
Tests now assert the whole-graph refusal plus the earlier guard, construct invalid
historical fixtures only at the relevant schema, and restore the complete graph
before invoking current financial services. Original benefit proof is preserved.
No production guard, migration or financial service was weakened or changed.

The 703-case continuation started before these corrections and has now completed;
its failures and the older remote CI are not a passing current-candidate result.
The next checkpoint is updated draft PR #77 with fresh CI, followed by the remaining
performance, operator/device/inbox, recovery-image and INR publication evidence in
MVP_PLAN.md. Configured-plan activation and production deployment remain pending.

**27 October 2026 - light, dark and system appearance modes.**
Public, customer and owner navigation now includes a Bootstrap color-mode selector.
The device-local choice is applied before styles load, follows OS changes in System
mode, synchronizes between tabs and tolerates unavailable browser storage. Custom
showroom surfaces, forms, alerts, tables and workspace navigation have dark palettes;
print overrides retain light document colors. No financial behavior or gate changed.
Desktop/mobile synthetic browser review, persistence/keyboard checks, isolated
JavaScript behavior checks and Django system checks passed (details in TESTING.md).
Physical Android/TWA acceptance remains part of release review. The work remains in
the isolated release-validation worktree; the original worktree's edits are untouched.
Next: finish consolidated regression/CI and resolve remaining failures before release.

The validation follow-up also carried the already-requested solid Account button
into this isolated candidate: its presentation test was present but the template
still used an outline button. The existing three-header test now passes locally.
The original worktree's pending Account styling edits remain untouched.

**27 October 2026 - configured-history image restore rehearsal passed.**
The candidate image built from `6f6e5f6` preserved all retained schemes rows/columns
and separate liabilities through an isolated PostgreSQL 16 dump/restore. The fixture
contains original/replacement INR bonus and metal VA invoices, complete returns,
customer-authorized reapplication decisions, and four refunded-order retirements
covering both denominations and optional/monthly collection. Outstanding principal
remained INR 500.00 and GOLD_22K_916 0.050000 g; retired orders granted no entitlement.
Returned awards correctly remain review-required, with two consumed reviews and two
approved-but-unconsumed reviews. Financial, closure, grade and principal checks passed.

Migration 0054 refused downgrade; forward graph recovery preserved the complete
snapshot. Six earlier benefit/policy/refund guards also refused retained evidence.
The repeatable synthetic-only harness is `schemes/tests/builder_restore_rehearsal.py`.
Two-return owner GETs measured 654 queries/4.234s for INR and 339/0.473s for metal in
this local image run. This is not production-scale/managed-DB latency acceptance.
The isolated database container/volume were removed. Full regression/normal CI on
PR #77 remain running; operator/device/inbox, compatible recovery-image and INR
publication approvals remain open. No production or release gate changed.

**27 October 2026 - consolidated builder candidate integration (validation in progress).**
The isolated `integration/builder-release-validation` worktree combines builder
`261424c` with the prepared checkout-prevention integration from deployed `main`
`d0e5dd1`. It retains legacy durable checkout identity/recovery alongside configured
reservations, optional-order investigation and refund review. Migration 0055 joins
the two migration leaves without data operations. No production change or configured
activation is included; the original worktree's unrelated edits remain untouched.

Django system and migration-drift checks passed. The first serial consolidated run
stopped after 735 cases: 734 passed and one INR recovery test supplied no webhook,
so it hit the newer exact-event refusal before its intended readiness assertion.
The corrected test supplies matching evidence; a separate test retains the missing/
mismatched-event refusal. Focused payment/checkout coverage passed 68 of 70 cases;
the two failures expected older rollback guards instead of the earlier 0050 refusal.
Those expectations, plus the same issue in two settlement tests, now check both the
complete graph's stronger guard and the older guard directly, preserving evidence.
The four targeted rollback cases now have passing coverage (three passed together;
the fourth passed after restoring the graph before its runtime balance assertion).
The remaining consolidated cases are still running in a disposable localhost
database. This is not yet a clean full-suite result. The deployed-schema
regression passed locally and inside the built candidate image.
Candidate `14af2f2` is pushed with draft PR #77; GitHub's image build/critical scan,
migrations, drift and application checks passed, with the full Django suite pending.

The candidate-image synthetic dump/restore drill preserved original checkout and
financial columns across 37 forward migrations, separate legacy INR/gold/silver
liabilities and legacy contracts. Downgrade refused retained checkout evidence;
reapplying the two pending merge nodes restored the complete graph. The isolated
database container and its volume were removed. TESTING.md records the exact image,
fixture and limits: this is not complete configured-history/latency or production
recovery acceptance. The older UI rehearsal script remains unsuitable as builder
upgrade evidence without reconciling its targets and current-model fixture creation.

**27 October 2026 - refund workspace browser review.**
Synthetic responses from the real owner HTTP/service workflows were reviewed in
local Chrome. The comparison tables hid important answers behind horizontal
scrolling on narrow screens; payment checks and each order attempt now use stacked
Bootstrap definition lists. No financial service, permission or release gate changed.
Keyboard error focus and the separation of payment resolution from order retirement
were checked. TESTING.md records the final viewport/test evidence and its limits.
Showroom-owner, physical Android/TWA and assistive-technology acceptance remain open;
the next engineering step is consolidated candidate CI and exact-image rehearsal.
Production and the ordinary local database were not changed.

**27 October 2026 - private owner payment-refund and order-retirement review.**
The exception workspace now links to an owner-only payment refund comparison and a
separate all-attempt order review. Owners inspect, compare and explicitly confirm
fresh evidence; signed reviews bind the owner and exact route. Apply independently
rechecks provider facts through the existing financial services. GET performs no
provider I/O or mutation. Payment resolution alone does not release an order;
retirement alone creates no entitlement, qualification or agreement closure.

Retained review history stays accessible after an exception leaves the queue.
Credited payments, partial/contradictory refunds and incomplete/non-terminal order
attempts have no override. The Bootstrap forms explain these boundaries and mask
provider errors. The owner manual and release/runbook documentation now describe
both confirmations. No new migration, refund API, configured-plan activation or
production change is included. Existing unrelated working-tree changes are preserved.
Verification details are recorded in TESTING.md. Next: candidate operator/device
acceptance, consolidated normal CI and exact-image recovery/latency rehearsal under
the remaining release-evidence checklist; INR publication approvals remain separate.

**27 October 2026 - refund hold interpretation and explicit order retirement.**
Shared predicates now distinguish exact resolved capture evidence from unresolved or
contradictory events across collection, eligibility, exception checks, closure and
privacy review. Original webhook history is preserved. Payment resolution alone leaves
a pending contribution/reservation held; it never grants money, metal or qualification.

Migration 0054 adds immutable all-attempt order-retirement evidence and a protected
monthly release source. The separate internal service requires owner-bound review,
explicit confirmation and fresh read-only provider inspection outside database locks.
Only a stable paid order with every attempt terminal, all paid funds fully refunded,
validated exact-payment resolutions and no historical entitlement may be retired.
Account-locked application preserves order/rate/deadline evidence and appends RELEASED
for the original reservation without disturbing a replacement's credit or qualification.
An exact capture replay cannot reopen that reservation; contradictory captures still hold.

Settlement and benefit proofs retain additive refund references; older proofs without
these records keep their shape. Financial diagnostics report malformed disposition
proof. No refund API, owner clearance screen, automatic agreement closure or release
activation is introduced. The next implementation is the private owner comparison and
confirmation workflow for payment resolution and separate order retirement, followed
by candidate operator acceptance and the remaining release-evidence checklist.
Verification: 76 broader regressions passed, plus the expanded 12-case provider/
lifecycle suite, 18 diagnostics/privacy/corruption cases and three final release-source
checks. Django and migration-drift checks passed. Unique disposable localhost databases
were destroyed; TESTING.md records overlapping run scope and timings.
Production and the ordinary local application database remain untouched.

**27 October 2026 - exact-payment refund resolution and credit replay guard.**
Migration 0053 adds immutable, uniquely scoped payment-error refund resolutions that
link the owner's reviewed observation to a fresh authenticated inspection. The internal
service requires explicit confirmation, an owner/evidence-bound signed review no older
than ten minutes, unchanged provider/local facts and no historical entitlement. It
rechecks persisted authority and source facts under the agreement lock; repeated
application returns the same retained resolution. Database update/delete and unsafe
migration reversal are refused.

Contribution confirmation and new INR principal creation refuse credit from the
resolved payment. A delayed signed capture stays in review; a legitimate different
payment on the same order keeps its principal. The focused nine-case run passed,
including capture/resolution concurrency and migration preservation. The broader
80-case observation/resolution/Razorpay/API-principal/capture run passed in 331.447s.
Django and migration-drift checks passed. Unique disposable localhost databases were
destroyed; TESTING.md records scope. No real provider request was made.

This is an internal payment-resolution prerequisite, not agreement/order clearance.
Shared hold predicates, explicit attempt/reservation transitions and the owner screen
remain pending and must ship together. Existing holds/statuses are intentionally
unchanged; a refunded payment alone does not prove every order attempt is settled.
Production and configured-plan activation remain unchanged.

**27 October 2026 - payment-error refund inspection foundation.**
The Live adapter now reads an exact payment, bounded complete refund pagination and
a second payment snapshot. Strict type/identity/currency/amount checks and processed
refund totals reject inconsistent evidence. Partial/pending/failed refunds never
qualify as fully refunded. Retained evidence excludes raw payloads and bank/contact
details; provider completion is not represented as independent bank-credit proof.

An internal owner service rechecks persisted authority and exact local bindings
before and after provider I/O, which must run outside a transaction. It records
minimal immutable observations and historical entitlement presence without changing
any payment, allocation, instalment or hold. Migration 0052 adds observation storage,
database update/delete protection and a reverse guard when evidence exists.
No public/owner action or hold-clear operation is exposed by this prerequisite.

Verification: 57 combined observation/adapter/API-principal/capture-boundary tests
passed in 198.088s on a unique disposable localhost PostgreSQL database, destroyed
afterward. Django and migration-drift checks passed; TESTING.md records scope and
the corrected initial fixture failure. No real provider request was made.

Next implement the atomic resolution record/service, shared hold interpretation,
callback/webhook/API replay protection and explicit attempt/reservation transitions
together; only then expose the owner confirmation workflow. The remaining candidate
CI, device/inbox, business/provider, performance/recovery and coherent activation
evidence remains tracked in MVP_PLAN.md. Production and activation gates are unchanged.

**27 October 2026 - payment-error refund resolution design and progress checkpoint.**
ADR-0017 now defines the next bounded workflow: manually refund an exact erroneous,
never-credited Live payment through the provider, then independently verify its full
refund and retain an append-only, payment-scoped resolution. This is read-only provider
verification, not automated refund execution or the existing INR final disposition.
The design requires shared hold interpretation, replay/concurrency protection and
explicit attempt/reservation handling before any owner clearance action is exposed.
It is documented design, not runtime implementation or production acceptance.

The principal builder foundations, independent policy/versioned agreement terms,
collection, eligibility, full-only closure, INR disposition/corrections, defined
benefit lifecycle and owner/customer presentation have local implementations.
Recent work completed optional-order identity recovery, fresh captured-payment review
and invocation-local history-read reuse. Previous test evidence remains scoped to
the commits/runs recorded in TESTING.md; this documentation checkpoint adds no new
runtime test claim.

Remaining in order: implement/test the bounded refund-resolution integration;
consolidate approved-family candidate CI and operator acceptance; complete device,
accessibility/inbox and INR business/provider evidence; rehearse exact-image upgrade,
recovery and representative performance; review coherent activation and approve a
digest-pinned rollout. Parallel acceptance is permitted, but none is presumed done.
MVP_PLAN.md's remaining-release-evidence table is the current checklist.
Configured-plan gates and production remain unchanged.

**27 October 2026 - captured-payment comparison and explicit confirmation.**
The owner recovery page now shows the latest retained provider/local comparison.
Apply requires a signed owner/event/attempt-bound review, unchanged payment facts,
an explicit confirmation and an inspection no older than ten minutes. A newer
unsafe attempt invalidates the earlier web review. GET is private/non-cacheable and
performs no provider call or writes; Apply still independently fetches provider state
and revalidates through the existing financial service and locks.

The service reloads persisted owner authority before I/O and credit, refuses
cross-linked metal events as well as INR events, and retains safe provider-error
descriptions. All 55 affected regressions passed, including the seven new workspace
cases, legacy/INR recovery, late/duplicate/concurrent captures and source-specific
INR refund presentation. Django and migration-drift checks passed; unique disposable
localhost databases were destroyed. TESTING.md records the evidence and limits.
No migration, refund API, financial-clear action or
activation change is introduced.

The manual/runbook now separate exact capture recovery, duplicate/late-payment
investigation, no-entitlement payment-error refunds and full INR settlement refunds.
External payment-error refund completion still has no verified local clearance
workflow; it remains an explicit release gap, not something an owner note resolves.
Next address that bounded resolution contract, then candidate operator/device
acceptance, consolidated CI and exact-image rehearsal. Production remains unchanged.

**27 October 2026 - owner optional-order identity investigation.**
The exception queue now exposes durable optional-contribution requests without a
provider binding, before expiry and after a local FAILED status. An owner-only,
CSRF-protected, non-cacheable form invokes the existing exact Live identity recovery
service. GET performs no provider I/O or writes. Recovery preserves the original
amount/rate/deadline, creates no principal/metal and cannot resume checkout.
Persisted owner authority is rechecked before provider lookup and before binding;
exact retries retain one binding. Provider failures are displayed without raw payloads.

Headline and diagnostic counts now include unresolved optional requests without
double-counting expired attempts. The owner manual and production guide describe
the investigation, reconciliation handoff and support escalation when no exact
identity exists. No schema, activation or production configuration changed.
Verification: 64 broader cases passed; one stale rollback-test expectation was
corrected to check both the newer draft-policy guard and the original order-evidence
guard without weakening either. All three targeted transactional tests then passed,
as did Django and migration-drift checks. TESTING.md records exact runs and limits.
Unique disposable localhost databases were destroyed; production was untouched.

Next complete candidate operator acceptance for late/duplicate captures and refunds,
then consolidated CI and exact-image rehearsal with representative latency. This
closes the local optional-identity interface gap, not the full provider-exception,
device/inbox or INR publication acceptance boundary.

**27 October 2026 - owner history traversal reused within one read.**
The returned-benefit workspace now shares successfully validated decision histories
within that invocation, scoped to its agreement and database. Earlier decisions
and complete principal/benefit returns still validate; circular/foreign traversal
fails. The read object never leaves the workspace and is not retained on models,
sessions or global state. Each new page starts fresh. Mutation services keep their
independent validation, and current binding/fulfilment/reversal checks explicitly
discard any supplied historical read object.

Four-return INR queries fell from 6,278 to 1,840 while original-authorization
tampering still blocks review. TESTING.md records the full profile and regression
evidence, including fresh consent-drift detection and rejection of an old approval
after a superseding hold. This is a local read-cost improvement, not production
latency or complete release acceptance. No schema, policy, lock, financial amount,
provider operation or activation gate changed.

Verification passed: the final two deep-history profile tests, 35 broader affected
regressions, Django system checks and migration-drift checks. Disposable localhost
PostgreSQL test databases were destroyed; ordinary and production data were untouched.

Next complete operator acceptance for uncertain-order recovery and provider
exceptions, then consolidated candidate CI and exact-image rehearsal, including
representative latency. Device/inbox and INR publication approval remain open.

**27 October 2026 - consolidated builder release checklist and deeper-history review.**
MVP_PLAN.md now distinguishes completed local implementation (INR primitives,
independent eligibility and defined benefit lifecycles) from outstanding release
acceptance. TESTING.md maps 31 existing executable modules to the remaining
boundaries. Earlier incremental notes are historical sequencing, not instructions
to reimplement those completed paths. Readiness flags and family/schema barriers
remain closed; their older NOT_IMPLEMENTED names are not the current progress list.

The owner history regression now follows four real full settlement/return generations
for INR purchase bonus and metal VA. Every generation must retain its predecessors,
offer only the latest returned invoice for review and render without writes; original
authorization tampering must still block the fourth-generation review. The deeper
profile exposed cumulative query-log truncation; measurements now reset the bounded
log and reject incomplete captures. Fourth-generation GETs make 6,278 INR / 2,931
metal queries; performance acceptance remains blocked. Both corrected regression
tests passed (168.407s), including original-evidence tampering checks. Django and
migration-drift checks pass. Disposable test databases were destroyed; TESTING.md
records the measurements and invalid initial sample explicitly.

Next reduce the measured repeated-history validation/read growth without removing
source checks or caching spending authority. Then resolve operator recovery/exception
acceptance, candidate CI and exact-image rehearsal. Device/inbox and INR publication
approvals remain explicit separate evidence. No runtime financial logic, migration,
production configuration or activation was changed by this checkpoint.

**27 October 2026 - sampled owner mobile/keyboard and message review.**
Read-only browser snapshots of real synthetic Django responses were reviewed at
320px/390px and desktop width. The review found that a fresh INR fulfilment form
still selected an already completed jewellery portion while a refund remained.
Fresh forms now offer only outstanding portions; submitted retries retain their
original identity and still pass the service's locked idempotency/source checks.
Routes and history use readable labels, and confirmation follows the evidence.

Sampled labels, help/error references, error focus, mobile-menu Escape/focus return
and narrow-screen fit were checked. Captured completion-email wording was reviewed
locally; no message was sent. TESTING.md records coverage and remaining limits.
This is not stakeholder sign-off, inbox/device acceptance or production activation.
Next reconcile the remaining release checklist, including delivered messages,
history-depth performance, normal CI and exact-image rehearsal. Gates remain closed.

**27 October 2026 - repeated-return history loading review.**
Owner benefit review now has measured one- and two-return INR/metal fixtures built
through real settlement services. Closure event sources, INR return fulfilment
links and metal reversal links load together using the ORM. Validation, explicit
fresh reads and mutation locks remain intact; consumed predecessors are still
checked. A changed authorization in the original settled event must block review
after a replacement has also been returned.

Two-return query counts fell from 2,194 to 1,732 for INR and 883 to 779 for metal.
These remain high and are not production performance acceptance. TESTING.md records
fixture budgets and affected regression results. No schema, financial policy,
release gate or production setting changes are included. Next complete owner
mobile/keyboard and delivered-message acceptance, with remaining history-depth
performance review, normal CI and exact-image rehearsal tracked before activation.

**27 October 2026 - owner query review and lifecycle regression.**
Local profiling identified repeated full-history validation in returned-benefit
and INR settlement workspaces. Page builds now reuse their own freshly validated
decision/history and balance reads. Financial services still revalidate under
their locks; no trusted caller proof or cross-request cache was added. Real GET
profiles check private, write-free responses, and fresh reads must still detect
holds, later approvals and source drift. Measurements and affected regression
results are recorded in TESTING.md.

This is a measured reduction, not production performance acceptance. Next review
longer correction histories and remaining read amplification, then complete
browser/mobile/keyboard and delivered-message acceptance, normal CI and exact-image
rehearsal. Gates remain closed; no migration, production action or activation is
included in this checkpoint.

**27 October 2026 - gated INR final-completion notices.**
The existing reminder job now supports a distinct immutable INR completion event.
Proposals, partial fulfilment and all legs without final closure do not qualify.
Selection and locked dispatch validate current principal, fulfilment, benefit and
closure history, account/date scope, recipient eligibility and audience switches.
Full returns suppress unsent/retried messages while preserving earlier attempts.
Emails distinguish paid principal applied to jewellery from principal refunded;
benefits and invoice top-ups remain separate. No transfer or financial mutation is
triggered by notification.

Migration 0051 preserves legacy reminder identities and protects the new completion
link; reversal refuses retained INR notification evidence. Configured-plan and
per-family readiness gates remain closed. No normal-database migration, provider
action or production deployment occurred. TESTING.md records validation.

Next: consolidated lifecycle/provider-exception acceptance and query/latency review,
then browser/mobile/keyboard and delivered-message review, normal CI and exact-image
release rehearsal. The complete builder remains unactivated.

**27 October 2026 - cross-family event notification review.**
The acceptance map now identifies existing request, collection/provider-exception,
eligibility and full-disposition suites and their remaining release checks.
Allocation-exception and completed-redemption dispatch re-read the current event,
account/date/shape and audience setting before creating delivery evidence or SMTP.
Resolved exceptions, reversed full settlements and stale/unsupported candidates
are skipped; retained attempts are preserved. No financial mutation, migration,
release-gate change or deployment is included.

Next: add source-aware INR final-completion notifications, which the existing
metal redemption job does not cover. A proposal or individual fulfilment leg is
not full completion. Then finish consolidated lifecycle/notification acceptance,
query/latency and browser/mobile/keyboard review, normal CI and exact-image release
rehearsal. The complete builder remains unactivated; TESTING.md records validation.

**27 October 2026 - owner returned-benefit review workspace.**
Both INR and exact-metal settlement screens now link to a private owner review of
completed benefit returns. Owners preview APPROVE or HOLD, then explicitly confirm
an owner-bound, short-lived signed decision with a retained reason. Approval needs
fresh customer authorization; a hold must not claim consent. The existing services
recheck return, qualification, source and closure history under lock. No balances,
awards, invoices or payment availability change merely by recording a decision.

The screen retains earlier decisions and distinguishes current approval, hold,
stale evidence, consumed approval and investigation. Old retries cannot override a
later hold. A hold after an unconsumed INR proposal blocks handover; recovery uses
the separate void/full-return workflow and a fresh review. Used approvals require
the replacement invoice's own full return. Release/readiness gates stay unchanged.
No migration, normal database change, provider action or deployment is included.
Validation is recorded in TESTING.md; the existing owner manual includes the steps.

Next: cross-family operational/lifecycle/provider-exception and notification coverage
review, then query/latency and browser/mobile/keyboard acceptance, normal CI and the
coherent release rehearsal. The complete builder is not yet activated.

**27 October 2026 - owner INR settlement workspace.**
Independent INR agreements now have a dedicated owner interface for signed no-write
split preview, customer-authorized proposal, actual source-specific jewellery/refund
fulfilment, full completion and signed void/full-return correction. Amounts and refund
routes come from retained proposals, never editable POST amounts. Saving a proposal
leaves principal outstanding. Every actual portion must be fulfilled before closure;
full-return evidence restores principal and consumed benefits atomically through the
existing services, retaining history and blocking payments.

Owner authorization, CSRF, private responses, signed expiry/current-evidence checks,
idempotency and operational readiness remain enforced. Older agreements and foundation
proofs are read-only here, including foundation proofs on schema-2 accounts.
No financial formula, gate or migration changed. Test results are
recorded in TESTING.md. Normal databases, providers and production are untouched.

Next: benefit reapplication review interface, then remaining operational/lifecycle/
notification coverage, query/latency and browser/mobile/keyboard acceptance before
normal CI and a coherent release rehearsal. This is not builder activation.

**27 October 2026 - owner metal settlement/benefit workspace acceptance.**
Operational-screen review found the metal form still described a no-benefit-only
workflow although the gated services support contracted VA. Owners can now submit
invoice/eligible-charge/customer-receipt evidence for a no-write signed preview,
then separately confirm the exact full quantity and server-calculated benefit.
Forged posted quantities/discounts do not replace signed evidence. Full-return forms
require corrected-invoice, customer confirmation and actual return time when a benefit
was consumed; principal and benefit reversal remain atomic in the existing services.

The INR route no longer presents a gram-based settlement form: it shows a private
read-only boundary and links to the principal statement, rejecting mutation POSTs.
Closure history uses denomination-appropriate wording. No financial service, policy
formula, readiness gate or migration was changed. Verification is in TESTING.md;
normal databases, external providers, activation and deployment are untouched.

Still required: the dedicated owner INR proposal/fulfilment/completion/correction
interface, benefit reapplication review interface, remaining operational/lifecycle/
notification acceptance, mobile/keyboard and performance checks, normal CI and the
coherent release rehearsal. This checkpoint is not complete-builder acceptance.

**26 October 2026 - independent draft-offer preparation (0050).**
Owners can reuse a schema-2 configuration in an inactive, unlisted named draft.
Duration columns now retain the actual independent duration or null for count-only/
anytime, and the period ceiling retains ONCE_PER_PERIOD. Existing rows/revisions are
not converted. Exact-metal drafts require offered grades; INR purchase-credit drafts
have no grade offerings. Preparation uses a separate validated storage projection;
operational publication/enrolment gates remain closed even with the release flag on.

The owner draft editor permits name, code, internal notes and applicable grades only.
Policy/activation inputs are rejected, stale edits fail under the plan lock, and each
actual change retains an audited immutable revision. Draft creation, offering changes
and audit commit atomically. Owner screens/manual distinguish preparation from public
offers, without invented duration or legacy cash-bonus promises. Read-only diagnostics
check independent projections, grades and complete latest revision evidence.

Migration 0050 retains legacy duration constraints for unconfigured plans and refuses
reversal over independent drafts. Verification is recorded in TESTING.md. No normal
local/production migration, activation, push or deployment was performed. Next is
owner operational-screen acceptance and full cross-family lifecycle/provider/notification
review, followed by performance/mobile checks, normal CI and the coherent rehearsal.

**26 October 2026 - owner independent-policy preparation editor.**
Owners can now open Configuration catalogue > Prepare independent policy and choose
the accepted independent dimensions in grouped Bootstrap fields. Amount, accumulation,
obligation, payment ceiling, period basis, duration/count, missed-payment consequences
and conditional benefits remain separate. The shared compatibility/model validators
reject incomplete or contradictory terms; unsupported controls cannot be forged.

Review configuration saves nothing. Save immutable version revalidates through the
existing owner service and retains actor/reason evidence. Create next version appends
to a locked predecessor and rejects an already-replaced version. Existing policy,
plan and agreement history is untouched; the earlier editor retains its semantics.
The owner manual includes the new preparation path and the boundary between review
and activation. Permission, CSRF, safe-method and non-cacheable form checks are covered.

No migration, offer publication, enrolment, financial mutation, normal-database change,
push or deployment is included. Verification is recorded in TESTING.md. Next:
schema-2 draft-offer preparation and owner operational-screen acceptance, followed
by full lifecycle/CI and the single release rehearsal. Unrelated edits are preserved.

**26 October 2026 - independent plan presentation and gated date reminders.**
Shared policy facts now describe accumulation, obligation, period basis, payment
limit, duration/count, missed-payment consequences and benefits consistently in
prepared offers, owner inspection, accepted agreements and statements. Agreement
reads validate the pinned version; current offer edits never replace its terms.
Invalid contracts show reconciliation. Customer/owner cards avoid invented maturity
dates, and INR agreement pages link to validated principal statements without a
metal rate or a misleading zero-gram balance. Status labels are read-only progress.

The gated duration-reminder integration uses current verified evidence and checks
again under the account lock at dispatch. Duration-and-count notices use the actual
required count, not months. Count-only/anytime have no scheduled maturity forecast;
benefit-only schedules do not silently postpone principal maturity or imply awards.
Both release/readiness gates stay closed. The owner manual distinguishes the earlier
editor walkthrough from the broader independent-policy families. Verification and
remaining acceptance boundaries are recorded in TESTING.md/MVP_PLAN.md.

No migration, normal-database change, activation, push or deployment is included.
Next: complete cross-family owner editing/operational-screen and lifecycle acceptance,
then normal CI and the single release rehearsal. Existing UI/production-note edits
remain outside this checkpoint.

**26 October 2026 - settlement statements and privacy disposition integration.**
Read-only INR purchase-credit statements now separate recorded principal, corrections,
proposals, actual jewellery/refund fulfilments, complete returns and historical closure.
Pending proposals discharge nothing. Receipts describe INR principal without inventing
metal allocation. Independent agreement statements retain the pinned eligibility rule
without inventing a maturity date for count-only/anytime contracts.

Purchase benefit documents show retained rights, invoice applications, full reversals
and replacement-review history separately from principal/grams. Customer documents omit
private authorization and review-reason evidence. Invalid principal/disposition proofs
produce a non-cacheable review response, rather than a misleading balance.
Privacy inventories now include INR and benefit chains; purchase-credit principal is
separate from legacy cash/bonus and exact grades. Unknown liability is never zero.
Invalid financial evidence blocks completion/further identity removal, while open
principal or unfulfilled benefit rights require retained showroom contact identity.
Financial history remains protected through completed-profile minimization.

No new migration or activation is included. Verification is recorded in TESTING.md;
normal local/production databases remain unchanged. Next: consistent family-specific
offers, agreements, reminders and owner presentation, then full lifecycle/CI and the
single coherent release acceptance. Unrelated UI and production-note edits are preserved.

**26 October 2026 - atomic approved-benefit replacement integration (0049).**
Returned invoice rights now enter the gated replacement workflow only with the latest
valid owner/customer reapplication approval. A new invoice retains its predecessor
and consumes that approval atomically with principal jewellery handover. Database
constraints enforce one original invoice per award, one successor per invoice and one
consumption per approval. Historical awards, invoice proofs and reversals are retained.
Purchase bonuses keep their original amount; VA uses the new evidenced invoice charges
under the original percentage/cap. No benefit becomes refundable principal or grams.

INR proposals bind approval but debit nothing. A later hold blocks new fulfilment;
void/full-return recovery remains possible and requires fresh review when evidence
changes. A consumed review cannot be reopened; any further correction must evidence
the new invoice's own full return. Exact-grade metal settlement and benefit consumption
remain one transaction. Historical validation distinguishes old returns from current
spendability, and diagnostics inspect the full invoice chain.

Migration 0049 preserves version-1 invoice proofs and refuses reversal once replacement
bindings or consumptions exist. Verification is tracked in TESTING.md. Only disposable
local databases are migrated; no normal-database migration, production activation,
push or deployment is included. Next: consistent statements/privacy, offers/agreements,
reminders and owner presentation, followed by full lifecycle/CI/release acceptance.
The coherent builder remains gated; unrelated production notes/UI edits are preserved.

**26 October 2026 - returned-benefit review authorization/history (0048).**
The next ordered foundation retains append-only owner APPROVE/HOLD decisions for
an evidenced full principal/benefit return. Owner-bound ten-minute previews bind the
original award, qualification, complete return, closure prefix and prior decision.
Approvals require fresh customer authorization; holds supersede approval without
erasing it. Concurrent submissions serialize under the agreement lock. Changed
closure/source evidence requires a fresh review or investigation, not silent reuse.

These decisions do not spend the benefit, change its amount/cap, create principal,
reopen contributions or authorize a replacement invoice. The existing one-invoice
constraint and consumed-benefit settlement barrier remain. Atomic consumption of a
reviewed returned right in a replacement settlement is the next implementation step.
Read-only review diagnostics and migration rollback protection preserve this boundary.
Verification is recorded in TESTING.md; only disposable local PostgreSQL databases
are used. No normal-database migration, activation, push or deployment is included.
Presentation/statements/privacy/reminders and full coherent release acceptance remain
pending. Unrelated production notes and dropdown styling are preserved.

**26 October 2026 - gated replacement dispositions with unconsumed rights.**
The next ordered recovery step permits a linked independent replacement after all
predecessors have an evidenced void/full return, provided no benefit invoice has ever
been consumed. This includes principal-only INR/metal returns and an unconsumed INR
award retained through voids or refund-only returns. Original sources, qualification
and normal/early basis are retained; passing time does not re-earn a benefit during
correction. New previews, fresh customer authorization and new invoice references
are required. Agreements remain contained against contributions throughout recovery.

The chain preserves original proposals, redemptions, returns and any award. Existing
original-source refund-capacity checks apply cumulatively; receiving refunded money
back does not reset an online capture's capacity. Diagnostics validate predecessor
links and retained qualification. Concurrent retries cannot create two successors.

Consumed-and-returned benefits are still deliberately held: their existing one-invoice
invariant is not removed by this checkpoint. Next is explicit, append-oriented benefit
reapplication authorization/history and its atomic replacement integration, followed
by presentation/statements/privacy/reminders and full lifecycle/CI/release acceptance.
The complete builder is not activated. No new migration, normal-database change,
push or deployment is included; unrelated production notes/UI edits are preserved.
Verification and limitations are recorded in TESTING.md and MVP_PLAN.md.

**26 October 2026 - gated independent INR final disposition and benefit integration.**
The first independent INR disposition now uses closure-scoped eligibility and benefit
qualification across the five approved families. A signed owner preview retains the
net invoice and original-source refund split. Proposal creation can retain/reuse the
qualified immutable award, but does not reduce principal liability or claim handover.
Actual jewellery fulfilment and invoice-benefit consumption commit atomically; each
manual refund needs its own completed-source/customer receipt evidence. Closure waits
for every principal leg. Early exit and missed unearned benefits cannot forfeit principal.

Complete physical-return correction links principal and benefit reversals atomically,
retains original evidence and contains the agreement. Voiding an unfulfilled proposal
retains the unconsumed right. Neither path authorizes automatic replacement or benefit
re-spending. Existing optional/calendar/no-benefit foundation proofs remain separate;
the new independent entry and subsequent mutations require operational readiness.
INR and closure diagnostics detect missing linked benefit evidence.

Verification is recorded in TESTING.md. This is service integration on disposable
future contracts, not owner UI, publication or production acceptance. No new migration,
normal-database mutation, activation, push or deployment is included. Existing unrelated
production notes and dropdown styling are preserved outside this checkpoint.

Next in order: replacement-disposition handling after void/full return, preserving
customer authorization, original-source refund capacity and retained benefit rights.
Then complete statements/privacy, offers/agreements/reminders/owner presentation,
full lifecycle/provider-exception acceptance, normal CI and exact-image release rehearsal.
The coherent builder is not finished; all operational/publication gates remain closed.

**26 October 2026 - gated independent metal settlement and benefit integration.**
The first exact-grade full disposition now evaluates the accepted independent contract
through a closure-specific read. Public progress still reports closure pending; no
account is temporarily reopened and count-only/anytime receive no invented maturity.
Normal and early closure retain all verified principal, subject to payment/outage
review. Missing benefit-only instalments cannot forfeit date-eligible principal.

Owner-bound expiring previews include current qualification, source evidence and any
actual VA invoice. Apply locks the agreement and commits retained award/right, full
metal redemption, invoice benefit consumption, audit and closure together. A prior
unchanged award is reused, never stacked. Complete return records linked principal
and benefit reversals in one transaction and leaves the agreement contained; returned
rights cannot automatically fund another settlement. Diagnostics check both lifecycles.

Verification is recorded in TESTING.md. This is service-level integration on synthetic
future contracts, not owner UI or release acceptance. No new migration, normal-database
mutation, activation, push or deployment is included. Unrelated production notes and
UI edits are preserved outside this checkpoint.

Next in order: integrate independent INR final-disposition eligibility and benefits
with its separate manual invoice/refund fulfilment and correction workflow, then
resolve replacement-disposition handling without automatic benefit re-spending.
Presentation, reminders, privacy and full lifecycle/CI/release acceptance still follow.
The coherent builder is not finished; operational/publication gates remain closed.

**26 October 2026 - gated invoice benefit fulfilment and full-return evidence (0047).**
The next ordered dependency records one immutable invoice application per retained
award, linked to the actual INR jewellery fulfilment or full exact-grade metal
settlement. It retains gross/net invoice values, eligible-charge evidence for VA,
calculated benefit, customer receipt and source proof. Owner-bound expiring previews,
account locking, source revalidation and database uniqueness prevent stale or repeated
consumption. Invoice arithmetic never increases principal, grams or refundable credit.

Append-only benefit reversal requires the matching recorded full principal return,
corrected invoice, customer confirmation and actual return time. Original awards and
invoice evidence survive. Returned benefits stay in review; there is no automatic
re-spending, cash payout, partial reversal or replacement-credit wallet. An invoice
unable to consume the full purchase bonus plus a positive principal handover remains
blocked rather than silently forfeiting a remainder. Metal invoice amounts/charges
and physical handover/return references are owner-attested, not an inventory or invoice
system; INR net invoice must match its retained principal-disposition split.

Migration 0047 preserves existing rows and refuses rollback over new benefit invoice
or return evidence. The read-only check_benefit_awards diagnostic now distinguishes
awards, invoice fulfilments, reversals and review. Verification is recorded in
TESTING.md; only disposable localhost PostgreSQL test databases were migrated.

Next: integrate independent eligibility, award timing, benefit fulfilment and complete
principal settlement/return atomically, then presentation/reminders/privacy and full
lifecycle acceptance. Existing settlement entry points still reject benefit-bearing
contracts. No owner UI, normal-database migration, activation, push or deployment is
included; the coherent builder release remains unfinished. Unrelated production notes
and UI edits are preserved outside this checkpoint.
**26 October 2026 - checkout prevention/recovery and monitoring deployed and verified.**
PR #76 merged as `d0e5dd1897debb054d99647d6ea16575d08b1a48`. Protected-main
CI run `40283793237` passed all 591 tests, deployment/static/migration gates and
the published-digest critical-vulnerability scan. Production now runs
`ghcr.io/rajeshr188/jsk-savings@sha256:00caf93dfa3933cc662f39745c4a3bd823768b523a73163d71bb60c474e0ec6d`.
That exact image repeated the synthetic PostgreSQL 18.6 dump/restore/upgrade,
duplicate/stale-submission, HMAC capture and owner-recovery rehearsal before cutover.

The owner approved 25 October 2026 at 13:37:12 IST as the recovery checkpoint.
This was Linode's reported `updated` timestamp, not an independently verified latest
WAL timestamp; managed daily backup/continuous PITR availability was inspected.
No production restore was performed. Any future restore must reconcile every
financial event after the chosen checkpoint; application rollback retains the schema.

An audited global initiation pause found zero unresolved Razorpay contributions.
The reviewed migration plan contained only `schemes.0021_checkout_idempotency`,
which applied successfully. Nine financial-source projections and separate cash/
exact-grade liabilities matched before migration, after migration and after image
replacement. Live/readiness returned the new release. Integrity commands passed,
and read-only transactions rendered seven real customer/owner GET pages with provider
calls forbidden. Original payment controls were restored exactly through the audited
service; all three metal grades reopened. The signed payment form renders correctly,
and no checkout evidence, payment or entitlement was created by acceptance.

The root-owned Better Stack configuration was verified without disclosing its URL.
The five-minute inspection-only systemd service/timer passed verification and a real
successful run; Better Stack showed Up. A controlled missing-container failure
exercised the real wrapper, raised incident `1038686832`, and delivered both failure
and recovery emails to the existing business inbox. With only the new timer stopped,
the five-minute period plus six-minute grace raised missed-heartbeat incident
`1038693817`; the missed-run and recovery emails also arrived in that inbox. A real
successful inspection restored health at 13:14 IST. The next natural scheduled run
succeeded at 13:19:33-13:19:40 IST; the timer remains enabled/active and the temporary
automatic-resume safeguard was stopped. The old
application image remains present; no database reversal or historical edit occurred.
Local builder/UI development remains separate.

**Isolated builder integration (local only).**
Branch `integration/checkout-prevention-builder` combines builder checkpoint
`372580e4fe39664d82dd9b4a9caa4b4162d47fcf` with production release `d0e5dd1`.
The empty 0047 merge migration joins the independent 0021/0046 histories. Legacy
agreements use durable signed checkout identity; configured optional/monthly flows
retain their existing reservation services, with a guard against using the legacy
service for configured agreements. Provider identity validation now supports each
retained request family through one strict adapter. Historical migration tests
restore all current schema leaves, and invalid-payment fixtures are isolated so
they respect the one-unresolved-checkout constraint.

Validation used unique disposable localhost PostgreSQL databases. The full
1,226-test snapshot run completed in 2221.301s with four failed assertions and six
errors. Checkout compatibility corrections preserve configured monthly status
actions and accepted-closure errors; invalid pending fixtures are independent.
Historical migration checks now use matching historical models/applied migration
state and restore the current schema after rollback refusal, avoiding a cascading
missing-column error in concurrent INR crediting.

The combined 231-case payment run passed 230 cases; its remaining historical closure
test passed after correction (43.288s, normal hashing). The final six schema and
concurrency cases passed together (190.256s, normal hashing), as did the earlier five
correction cases, invalid-mode fixture and two configured-boundary cases. JavaScript,
Django checks and migration consistency pass. The full suite was not repeated after
these corrections. Two account-menu style subtest failures remain in the unchanged
builder snapshot; their corresponding UI edit is uncommitted in the active worktree
and is deliberately preserved there. No wholly green builder release is claimed.
The local merge is not activation approval; configuration gates remain closed.
The active builder/UI worktree and its uncommitted edits are preserved. This
integration branch remains local and must not be published as a production release.

**26 October 2026 - gated retained benefit awards implemented locally (0046).**
The next ordered benefit dependency now retains one immutable award per agreement:
an INR purchase-bonus amount/base or a VA-discount right with no invented monetary
amount before invoice-charge evidence. Frozen configuration/revision, accepted terms,
source receipts/payments, qualification decisions, outage history and calculation/
rounding identifiers survive current-offer edits and later source changes.

The owner-only service reloads authority, locks the agreement, checks the existing
operational gate and requires a short-lived actor/account-bound signed preview.
Apply recomputes evidence under the same lock; retries retain the same award and
conflicting requests cannot stack it. Source corrections/new payments/closure
changes trigger read-only review while preserving the recorded award and principal;
this is not automatic revocation, re-award, spending or a principal deduction.

Migration 0046 creates the retained award with database uniqueness/value/shape
constraints and refuses reversal when award evidence exists. It was exercised only
in disposable localhost PostgreSQL test databases, not the normal local/production
database. Verification is recorded in TESTING.md. The read-only
check_benefit_awards diagnostic is not activation or settlement readiness.

Invoice fulfilment, linked benefit corrections/reversal and complete settlement
integration remain next. Existing settlement services still reject benefit-bearing
contracts; no public/owner award UI, automatic award trigger or release-gate bypass
was added. Post-award changes stay review-only until the linked lifecycle exists.
The coherent builder release remains unfinished; no push or deployment occurred.
Unrelated production notes, UI edits and worktrees remain outside this checkpoint.

**26 October 2026 - unawarded benefit qualification and calculations implemented locally.**
Schema-2 progress now evaluates the accepted benefit policy separately from principal
eligibility. Required schedules must qualify even when principal is duration-only.
Ordinary replacements preserve benefits only where the contract says so; explicit
loss-of-unearned-benefit rules inspect original periods and acknowledged compensation.
Unresolved timing/outages remain review, not automatic customer lateness. Compensation
requires a real qualifying payment; count completion with an unpaid specifically
compensating benefit window stays review without demanding an extra contribution.

INR purchase-bonus previews use verified net qualifying source receipts, not metal,
top-ups or legacy CASH bonuses. VA qualification has no monetary value until evidenced
eligible invoice charges are supplied. Pure calculations apply explicit percentage/
INR cap and once-to-paise ROUND_HALF_UP, returning version/rounding metadata for future
retained records. Invalid types, precision, ranges and invoice bases are rejected.
Current-offer edits cannot replace the agreement's pinned configuration/revision.

This is a non-mutating qualification/calculation checkpoint, not an earned-benefit
ledger. It cannot create or erase awards, consume an invoice, refund funds or authorize
settlement. Accepted/closed histories require lifecycle review. No runtime activation
or model/publication gate is removed. Verification is recorded in TESTING.md; tests
use unique disposable localhost PostgreSQL databases, not the normal database.

Next: retained benefit awards, one-time evidenced invoice fulfilment and append-only
corrections/reversal, then complete settlement/presentation/reminder/privacy integration
and lifecycle acceptance. The coherent builder release remains unfinished. No migration,
push or deployment; unrelated production notes, UI edits and worktrees are preserved.

**26 October 2026 - independent eligibility progress implemented locally (no migration).**
All five approved schema-2 families now have a shared current-evidence selector.
Count-only completes on the final verified and conclusively attributed payment;
duration-AND-count waits for its independent duration floor and final qualifying
period end. Anytime requires positive verified principal without inventing a date.
Benefit-only schedule misses do not move principal maturity or grant a benefit.

The read validates frozen terms, real-source INR/exact-grade principal, qualification
history and corrections. Outstanding payments, ambiguous provider exposure and outage
holds prevent an eligible result; exhausted windows preserve principal for review.
Accepted dispositions and closed accounts are not presented as new spendable rights.
Dates/statuses are never mutated, and future/historical as-of dates cannot manufacture
verification. An explicit model progress property exposes this read without removing
existing payment, effective-status, publication or settlement activation gates.
Schema-2 agreements are excluded from legacy duration-and-count reminder wording.

Verification results are recorded in TESTING.md. Tests use unique disposable localhost
PostgreSQL databases; no normal-database migration or production mutation is required.

Next in order: benefit qualification/award/fulfilment and append-only corrections,
then complete eligibility-to-settlement, customer/owner presentation, reminders and
privacy integration, full lifecycle acceptance, CI and exact-image rehearsal. The
builder is not activated or finished; this checkpoint does not authorize settlement.
No push or deployment. Pre-existing production notes, unrelated UI edits and nested
worktrees remain outside this checkpoint.

**26 October 2026 - gated independent owner review/outage integration completed locally.**
Notes, outage holds and acceptance of existing signed timing now reuse the proven
review service for schema-2 contracts behind unchanged operational readiness gates.
Acknowledged compensation reads frozen required count, not duration, and appends
calendar/anniversary windows after only the policy's ordinary replacements. Original
count, amount, denomination, account dates and financial records remain unchanged.
The separate three-period cap, future-window rule, reconciliation, acknowledgement,
append-only evidence, idempotency and agreement-lock serialization are retained.

INR hold closure validates its own principal receipts/corrections rather than requiring
metal allocation. Benefit-only schedules have no ordinary replacements; compensation
does not move principal maturity or award a benefit. An extra window outside a frozen
no-post-duration contribution boundary is refused, leaving explicit review rather
than inventing payment rights. Owner forms now show independent count/denomination
and distinguish conditional benefit schedules from principal redemption.

The combined entry/ledger/review, legacy outage and calendar regression run passed
80 tests (287.759s). The final independent-review and accessibility run passed 19 tests
(62.422s), including duration-cutoff protection, completed-count refusal, readiness
with the flag off/on, and concurrent INR cash versus hold resolution. Django checks,
migration consistency and whitespace checks pass. Tests used unique disposable
localhost PostgreSQL databases; no global fast-hasher override was added.

No new migration, normal-database change, push, deployment or configured activation.
Next in order is independent count/anytime/duration-and-count eligibility, then benefit
qualification/fulfilment/corrections and complete settlement/presentation/privacy
acceptance, followed by normal CI and exact-image rehearsal. FW-PLAN-003/004 and the
coherent builder release remain unfinished. Existing production notes, unrelated UI
edits and nested worktrees remain outside this checkpoint.

**26 October 2026 - independent registration-first applications completed locally (accounts 0009).**
The separate PlanApplication journey now retains schema-2 confirmation history,
publication revision, INR/exact-grade denomination and independent duration/count/
benefit rules. Forms, progress email, customer inbox and owner review use recorded
terms. Changed offers, including a changed denomination, require fresh confirmation;
old consent remains untouched. Owner approval atomically creates identity, exact
agreement, required schedule, audit and invitation, with idempotent/concurrent
approval protection. Contact/verification/completion create no financial state.

Migration 0009 preserves legacy application/confirmation data, adds explicit version
and nullable INR/no-duration storage, refuses unversioned independent consent and
blocks reversal while new evidence exists. Diagnostics validate independent terms
and nullable agreement links. No model/publication/readiness gate has been removed.

The combined registration-first, legacy application, public registration, activation
continuation and independent-request regression run passed 103 tests (111.077s).
The final 15-test focused suite passed (38.138s), including changed-denomination
reconfirmation, forward/reverse migration guards, identity rollback and concurrent
approval. Tests ran on unique disposable localhost PostgreSQL databases; no global
fast-hasher override was added. Django checks and migration consistency pass.

Next in order: schema-2 owner instalment/outage review; count/anytime eligibility;
benefit qualification/fulfilment/corrections; cross-family full settlement,
presentation/privacy acceptance; then normal CI and exact-image release rehearsal.
This completes another gated integration, not FW-PLAN-003/004 or the entire builder.
No production changes, normal-database migration, push or activation. Existing
production notes, unrelated UI edits and nested worktrees are outside this checkpoint.

**26 October 2026 - independent existing-customer request integration completed locally (0045).**
The builder remains on the approved coherent-release track, not ready for activation.
Version-2 enrolment requests now pin the publication revision, configuration and
reviewed offer digest; INR purchase credit has no grade, count-only/anytime have no
invented duration, and required count remains separate. Signed request forms bind
offer/disclosure versions. Owner conversion retains exact requested terms and commits
account/schedule/decision/audit together. Customer/owner details, inbox and emails
describe frozen rules and conditional benefits without awarding anything.

Migration 0045 preserves schema-1 request history, supports null-grade pending
uniqueness, refuses unversioned independent requests and blocks reversal while
version-2 evidence exists. Diagnostics accept matching null INR grades and validate
independent provenance. Current-offer comparison reloads persisted terms rather than
trusting a cached plan. Row locks retain customer/login protection while excluding
the nullable grade join. Submission itself creates no financial state.

The 111-test combined request, owner-enrolment, publication, governance, configured
agreement and owner-workspace regression run passed (176.352s). The final 16-test
focused rerun passed (56.571s), including the latest locking and migration guards.
Django checks, migration consistency and whitespace checks pass. Tests use unique
disposable localhost PostgreSQL databases, not the normal application database.
Initial runs exposed stale cached-offer display and a null-grade diagnostic mismatch;
both were corrected rather than bypassing the checks.

No production changes, normal-database migration, push or configured activation.
Operational readiness still rejects schema 2 even with the release flag enabled.
Next finish the separate registration-first PlanApplication/confirmation journey
with the same frozen independent terms; do not confuse it with the existing-customer
SchemeEnrolmentRequest completed here. Then integrate owner instalment/outage review,
count/anytime eligibility, benefit qualification/fulfilment/corrections and complete
settlement/presentation/privacy acceptance, followed by normal CI and exact-image
rehearsal. The prior collection/accounting/settlement primitives remain foundations,
not evidence that these end-to-end workflows are all finished. Existing production
notes, unrelated UI edits and nested worktrees are preserved outside this checkpoint.

**26 October 2026 - gated collection-matrix regression checkpoint completed locally.**
Added eight service-level tests covering 120 first-payment combinations across the
five approved families: optional duration/anytime, required count/duration-and-count,
and required-for-benefit duration. They exercise both principal denominations,
supported amount policies, calendar/anniversary ceilings and cash/online entry.
Additional cases cover both defined benefit vocabularies, missed benefit windows
without maturity extension, count replacements, full cash corrections, duplicate
captures and delayed/boundary timing. Benefit terms never inflate collected principal
or grams; payment qualification does not grant benefit or settlement eligibility.
Whole-second provider evidence in the last second remains REVIEW, not assumed on time.

All 70 tests in the combined collection, independent payment-entry, instalment-ledger,
owner-enrolment and INR API suites passed (231.179s, normal hashing), including
concurrency/migration cases, on a unique disposable localhost PostgreSQL database
which was destroyed. Initial fixture failures were corrected (snapshot field and
clock chronology); boundary expectations were aligned with the existing conservative
timestamp precision rule without weakening it. Django checks, migration consistency
and whitespace checks pass. This is not full normal CI or complete lifecycle acceptance.

No runtime code, schema, release gate, normal database or production change.
Configured activation remains blocked. Next integrate the public enrolment request,
form and email journey with frozen independent terms; owner review/outage handling,
eligibility, benefit execution, settlement and final cross-family acceptance remain
explicit unfinished work. Existing production notes, UI edits and nested worktrees
are outside this checkpoint.

**26 October 2026 - gated INR callback/API principal integration completed locally (0044).**
Building on `fa9340d`, callbacks now retain minimal authenticated Live capture
observations after HMAC verification. Owner recovery retains actor/reason/event
correlation and requires preview plus a fresh provider inspection on apply. Source
confirmation, immutable evidence and principal commit atomically; an existing receipt
retains its original source. API observations cannot qualify monthly timing; a later
original signed capture may supply that evidence without adding principal again.
Migration 0044 changes no historical receipt and refuses reversal with retained API
evidence. Refund proofs retain API identity without rewriting older source proofs.
Runtime gates remain closed; no normal database migration, push or deployment.

Verification: expanded 23-test focused suite passed (103.439s); final 34-test
focused/adapter rerun passed (100.303s), including Live-only rejection and actual
optional/required order entry followed by capture during a pause. The combined
292-test financial run (932.275s) had 290 passes and two test-harness errors:
a bound model-default clock in the new settlement fixture, and a historical rollback
test querying current models before restoring the latest schema after an expected
guard refusal. Both were corrected without weakening financial guards. The corrected
settlement test passed in the focused reruns; all four principal migration/concurrency
tests passed separately (89.865s). Earlier fixture fixes covered cached relations and
capture/receipt timing. These runs overlap; no clean combined rerun or full normal CI
is claimed. Django checks, migration consistency and whitespace checks pass.
Disposable localhost PostgreSQL databases were destroyed. Separate dropdown UI edits
and nested worktrees remain untouched; this increment is saved as a local checkpoint.
Next after this increment: complete collection/benefit-schedule acceptance, then
remaining enrolment/presentation, eligibility/benefit and full-builder release gates.

**26 October 2026 - optional independent online orders integrated locally (0043).**
Checkpointed the preceding financial work through 0042 as `7be2be1`, excluding the
separate dropdown UI changes and nested worktrees. Optional schema-2 online payments
now use immutable, obligation-free request/binding evidence. The intent commits before
provider I/O; uncertainty prevents new online/cash attempts. Successful unchanged
checkout can resume, but authenticated exact lost-response recovery is reconciliation-
only and never creates funds, resets the original deadline/rate, or reopens checkout.
Optional calendar/anniversary ceilings cap deadlines. Pauses, expiry or containment
during network I/O retain provider identity but refuse checkout. The existing verified
untouched-order abandonment remains the only supported replacement route.

Migration 0043 adds two evidence models, no historical backfill. Reversal refuses
retained requests. `check_optional_payment_orders` distinguishes uncertain/unstarted
requests from identity-integrity errors without network calls/writes. Recovery remains
an internal owner-authorized service; UI and full collection acceptance are pending.
Actual publication/runtime gates remain closed with either release-flag value.

Verification: existing 19 entry tests passed (101.623s). The first optional
suite exposed test-fixture mistakes (NULL versus empty provider ID and a misspelled
pause field); corrected these without weakening invariants. Expanded 19-case optional
suite passed (87.814s). The final 39-test optional/entry rerun, including the additional
untracked-source guard, passed (186.933s). All 269 combined financial regression tests
passed (916.401s), including principal/settlement/correction, instalment recovery,
Razorpay, cash, operations, contribution and storage coverage. Suites overlap; the
final 39-case rerun covers the additional admission guard. Django checks, migration
consistency and whitespace checks passed. Disposable localhost PostgreSQL databases
were destroyed. This is not full normal CI or production acceptance. No normal database
migration, environment edit, push or deployment. The tested increment is a separate
local commit; unrelated UI edits/worktrees remain excluded. Next:
callback/API-recovery principal evidence and collection acceptance, then the remaining
eligibility/benefit and complete-builder acceptance gates.

**26 October 2026 - scoped local financial checkpoint before optional order recovery.**
Reviewed the accumulated schema-2 schedule/enrolment, verified-source principal and
payment-entry changes through 0042, including their fail-closed boundaries and prior
test evidence. Checkpoint includes the associated tests and canonical documentation;
the separate dropdown UI edits and nested worktrees are excluded. Whitespace checks
passed. This is a local development checkpoint, not exhaustive independent review,
normal CI, production acceptance or activation. Continue optional online durable
order creation/recovery next; callback/API principal reconciliation follows.

**25 October 2026 - independent payment admission and cash entry integrated locally (0042).**
Schema-2 new-payment selectors validate the pinned contract, server date, independent
count/duration, fixed/bounded amounts and optional calendar/anniversary ceilings.
Cash ceilings use the server receipt instant, not insertion time; optional ceilings
create no obligations. Closed/contained agreements and unreconciled principal/capture
evidence are blocked. INR now observes kill switch, global pause and business hours
without requiring a metal grade/rate; metal-specific pauses remain metal-specific.
Actual cash services support principal-only receipt/credit/audit transactions, retain
full-entry correction semantics, and preserve existing exact-grade allocation behavior.
Required-monthly online creation uses existing durable order intent/resumption and
verified-capture integration. Migration 0042 adds the independent contribution-frequency
choice without rewriting rows or changing legacy monthly constraints.

Runtime/publication gates remain closed with either release-flag value. Optional
schema-2 online order creation is explicitly blocked until equivalent durable
lost-response recovery exists. Callback/API-recovery principal evidence, eligibility,
benefit workflows and complete matrix acceptance are still pending. Tests simulate
only readiness on synthetic contracts; no production bypass is added. Focused runs
exposed two fixture issues (a stale related object and a nonexistent February date),
corrected without weakening financial rules. All 249 combined payment-entry, principal,
settlement/correction, instalment, Razorpay, cash, operations, contribution and storage
tests passed (553.975s); the additional missing-principal/allocation entry-guard test
passed separately (1 test, 2.254s). Django checks, migration consistency and whitespace
checks passed. Tests used disposable localhost PostgreSQL databases. Full normal CI
and production acceptance remain outstanding. No normal database migration,
environment edit, commit, push or deployment. Next: optional online durable order
creation/recovery, then callback/API-recovery principal evidence and collection acceptance.

**25 October 2026 - verified-source INR principal integration implemented locally (0041).**
Captured-webhook processing now has an atomic INR source-confirmation/event/principal/
monthly-attribution branch. Exact processed Live payload identity, hash, INR amount
and capture state are rechecked using shared evidence validation. Duplicate/concurrent
consumers retain one receipt. Principal and instalment timing remain separate: a late
capture retains principal while timing is REVIEW. Cash source hooks record owner-linked
principal and full corrections; correction failure rolls back the source reversal too.
Migration 0041 permits a null human actor only for an explicitly labelled captured-
webhook receipt, with a database shape constraint and reversal refusal once such
receipts exist. No fabricated owner/service user or automated refund is introduced.

Collection remains closed: the existing INR readiness and cash-entry restrictions
are unchanged. Generic callback success alone creates no principal. INR API recovery
is explicitly manual-review-only until its principal evidence is integrated. These
hooks are tested with synthetic contracts/sources and test-only readiness simulation,
not production acceptance. Initial focused run exposed a reversed-at test default
using the real clock against a frozen test clock; corrected the fixture, not the rule.
Verification: the initial 68-test regression passed (146.676s), followed by a fresh
200-test combined principal, settlement/correction, instalment, Razorpay/recovery and
cash regression (368.179s), including all 12 new integration tests. Suites overlap;
disposable localhost PostgreSQL databases were destroyed. Django checks, migration
consistency and whitespace checks passed. No normal database migration, deployment,
environment changes, commit or push. Next: complete new-payment validation/creation,
callback/API-recovery reconciliation and collection acceptance; then eligibility,
benefits and the complete builder acceptance matrix.

**25 October 2026 - gated independent owner-enrolment orchestration implemented locally.**
The existing owner enrolment service now handles the independent contract behind its
unchanged readiness/publication/model gates. It reloads and locks the offer, resolves
exact metal versus INR purchase credit, requires current revision/configuration and
explicit customer-term confirmation, rejects duration overrides, and persists account,
required schedule and audit in one transaction. Count-only/anytime retain null duration
and date; variable preferences remain variable. The audit retains the independent
count/eligibility basis. New schema-2 revision evidence no longer labels count/anytime
as calendar eligibility; schema-1 evidence and legacy enrolment behavior are preserved.

This is service orchestration, not activation: schema-2 actual enrolment is still
rejected with either release-flag value. Tests simulate only readiness to exercise
the future path while leaving publication, consent, models, constraints and writes
real. Initial tests exposed a synthetic-offer fixture that set active before its
required publication revision; fixed the fixture to set both together. All ten focused
tests passed (5.403s), followed by all 98 combined enrolment/publication/governance,
request, independent storage and ledger tests (132.966s). The suites overlap. Unique
disposable localhost PostgreSQL databases were destroyed. Django checks, migration
consistency and whitespace checks passed; full normal CI remains outstanding.
No migration, normal database/environment edit, commit, push or
deployment. Source-payment/INR receipt integration comes next; public request/forms,
emails, independent eligibility, benefits and full-closure acceptance remain open.

**25 October 2026 - independent schedule persistence/attribution integrated locally.**
Schema-2 required schedules now reuse the account-locked, atomic, idempotent period
service. The full frozen snapshot is validated; optional ceilings create no debt,
partial/corrupt schedules are never repaired, and initial persistence refuses any
existing contribution or non-active account. Required count, not duration, limits
internal reservation capacity for both exact-metal and INR contracts. Existing
cash/capture evidence, conservative timing, duplicate handling and append-only cash
correction semantics are retained. Attribution does not create principal/metal,
grant eligibility, award benefits or change agreement status.

Shared readers do not open unsupported workflows: schema-2 normal/model enrolment,
payment entry, monthly eligibility, owner investigation and outage resolution remain
explicitly closed. Synthetic account/source fixtures exercise the internal boundary
only. Accepted-enrolment orchestration, real source-payment/INR receipt integration,
independent eligibility, benefits and full-closure acceptance remain unfinished.
The single coherent builder release contract is unchanged.

Verification: after correcting one invalid February-date test fixture and adding
explicit owner-review/outage refusal coverage, all 86 schedule/storage/terms/payment
regression tests passed (192.320s). The separate 42-test ledger/review/outage run also
passed (116.031s). Suites overlap; these are not 128 distinct tests or full normal CI.
Both disposable localhost PostgreSQL databases were destroyed. Django checks,
migration consistency and whitespace checks passed. No new migration, ordinary local
or production database changes, environment edits, commit, push or deployment.
Next: complete accepted-enrolment and source-payment integration without opening the
release gate, then independent eligibility/benefit/closure acceptance.

**24 October 2026 - independent schedule construction prepared locally.**
Inspection of the next enrolment/payment boundary found that the schema-1 schedule
builder still derives original period count from duration. Added a separate read-only
schema-2 schedule resolver using the shared frozen-term resolver: required count
determines original periods; duration remains a separate floor. Both metal and INR,
plan-fixed/customer-fixed amounts and calendar/anniversary periods are covered.
Count-completion policies add only the three agreed ordinary replacement periods;
benefit-only duration schedules add none. Optional ceilings create no required periods.
India-local half-open attribution reuses the existing timestamp helper. No schedule
end is asserted to be eligibility, and no outage compensation or benefit is invented.
Calendar overflow fails before schedule creation. The 25 October follow-up corrects
the earlier period-number assumption: the field is PositiveInteger, so 32767 required
periods plus three replacements fit without imposing a false small-integer limit.

The 17 focused schedule/contract tests passed in 7.442s on disposable local PostgreSQL.
The checkpoint's combined regression rerun passed all 179 tests in 708.807s, including
the corrected historical reminder migration test. Django checks, migration consistency
and whitespace checks passed; disposable databases were destroyed. These suites overlap
and are not full normal CI or builder acceptance. This is an
enrolment prerequisite, not completed enrolment/payment integration: no account/period
rows are written and schema-2 publication/model/payment gates remain closed. No new
migration, environment change, commit, push or deployment. Next: integrate independent
schedule persistence and payment attribution atomically with accepted enrolment; retain
the single builder activation boundary until eligibility/benefit/closure acceptance.

**24 October 2026 - accumulated builder checkpoint created locally.**
Commit `84115be` on `agent/plan-agreement-governance` records the accumulated work
through 0040. No push, PR, normal database migration or deployment was performed.
Reviewed the worktree scope through migration 0040 before further financial changes.
The checkpoint is work-in-progress, not activation or production acceptance. Preserve
the separate account-dropdown styling edits and nested `.worktrees/` outside it;
include only the accumulated builder, closure, INR, policy/manual and associated
integration/test/deployment documentation changes. Private environment files are
excluded. Existing verification remains as recorded below: the final historical-model
test fix passed its focused rerun, not a fresh full-suite run. Normal CI, complete
builder acceptance and deployment rehearsal remain outstanding. Do not widen enrolment
or payment support merely to make checkpointed configurations operational.
Next: rerun the combined regression suite from this checkpoint after its historical-
model test correction, then implement gated schema-2 enrolment/payment integration.
This scope review/checkpoint is not an exhaustive financial-code or release audit.

**24 October 2026 - independent agreement storage implemented locally (0040).**
Added agreement storage version, eligibility-policy snapshot and required-count snapshot.
Legacy rows retain their exact duration/date, twelve-month minimum and old frequency
semantics; they receive no count or policy reinterpretation. New version-2 agreements
can store short durations, independent duration/count, and null duration/date for
COUNT/ANYTIME. Database checks reject mixed version, missing count, invented maturity
and invalid frequency shapes. Frozen terms remain immutable and validated against the
pinned configuration/revision, not today's plan. Full schema-2 policy storage is not
an eligibility decision, benefit award, enrolment or payment activation.

Added migration preflight refusal for existing unversioned schema-2 accounts and
reverse refusal for retained independent agreements. Old INR preservation guards
remain covered directly, while reversal through the new chain stops at 0040 first.
Model creation/payment/publication gates stay closed. The old monthly evaluator and
schedule builder reject independent policies explicitly rather than guessing from
duration or using null dates. Customer payment availability remains blocked for v2.

Verification: the 179-test PostgreSQL run passed 178 tests; its only error was an older
reminder migration test using the runtime account model at historical schema 0029.
Corrected it to use migration-state models. All eight focused reminder-migration and
independent-storage tests then passed (58.183s); the full combined suite was not rerun
after that test-only fix. An earlier missing seeded-grade fixture was also corrected
without weakening constraints. Django checks, migration consistency and whitespace
checks passed. Disposable databases were destroyed. No ordinary local/production migration,
environment edit, commit, push or deployment. Existing worktree changes are preserved.
Next: checkpoint accumulated work, then implement gated schema-2 enrolment and payment
integration using these snapshots; complete independent schedule/eligibility/benefit
workflows and the single builder acceptance matrix before activation.

**24 October 2026 - schema-2 agreement-term resolution integrated locally.**
Added a shared read-only resolver for pinned independent policy, selected fixed amount
or variable bounds, exact metal/INR denomination and duration floor. Required count
remains independent; count-only/anytime never acquire an invented maturity date.
Benefits remain policy facts, not awards. Common agreement diagnostics and INR principal
validation now reject amount, frequency, denomination and date drift against immutable
revision/configuration evidence. Current offer edits and newer configuration versions
cannot rewrite an existing agreement. Schema-1 contract serialization is unchanged.

The currently representable account subset is still optional duration (at least twelve
months), no benefit, flexible/calendar ceiling. Other resolved policies need account
persistence/schedule/eligibility integration. Structural integrity is not runtime
permission: model creation, enrolment, payment and publication gates remain closed for
schema 2, including with CONFIGURED_PLANS_ENABLED=True. No migration was added; no normal
database migration, environment change, production action, commit or push was performed.
Accumulated and unrelated worktree changes are preserved on agent/plan-agreement-governance.

Verification: 105 affected PostgreSQL tests passed in 274.002s, covering independent
contract resolution, principal, settlement/correction, configured agreements and policy
persistence/migrations. The initial run exposed six subcase errors in one new plan-fixed
fixture; correcting its minimum/maximum/fixed amounts resolved them without weakening
production constraints. Django checks, migration consistency and scoped whitespace
checks passed. Unique disposable localhost test databases were destroyed afterwards;
normal CI and complete builder acceptance remain outstanding.
Next: checkpoint accumulated work, extend account persistence for independent/no-duration
contracts, then integrate gated enrolment and verified payment-to-principal recording.
Full builder activation, remaining eligibility/benefit and acceptance work stay open.

**24 October 2026 - controlled INR disposition correction foundation implemented locally (0039).**
Added owner-bound signed previews for VOID of wholly unfulfilled proposals and
FULL_RETURN with exact evidence for every fulfilled portion, recorded atomically.
Original proposals, fulfilments and completions survive unchanged. Jewellery returns
require invoice correction and any separate top-up refund evidence; returned refunds
require actual money received back. No partial/staged-return path, automatic provider
refund or replacement-credit wallet is introduced. These are owner-attested records,
not independent verification of physical returns/bank credits.

The linked resolution restores discharged principal only, keeps the agreement
CLOSURE_PENDING and the accepted closure blocks contributions. A linear replacement
full-disposition chain requires fresh preview/customer authorization and new invoice/
transaction evidence. Retirement is a checked projection, not the source of financial
truth. Historical completion validation uses original gross fulfilment; diagnostics
check the complete chain and separate outstanding principal from discharged amounts.
Reverse migration refuses to discard correction/replacement evidence.
Customer returns never reset original online-payment refund capacity: cumulative
recorded provider refunds are capped by the original receipt, with exhausted routes
held for separate approved-route reconciliation rather than silent cash substitution.

Scope remains optional/calendar/no-benefit future INR contracts, exercised through
synthetic fixtures only. No ordinary local/production migration, feature activation,
environment change, commit or push. Existing unrelated worktree changes preserved.
Next: review/checkpoint accumulated local work, then schema-2 agreement/enrolment and
payment integration under the same disabled builder release gate; complete remaining
eligibility/benefit, statement/privacy, UI and release acceptance work in MVP_PLAN.md.

Verification: 174 cross-workflow tests passed in 587.309s (correction, principal,
settlement, closure, cancellation, liability, independent policy and privacy completion).
After adding the provider-cap safeguard, 46 focused correction/settlement tests passed
in 166.628s; the additional cumulative-cap/exact-boundary test passed in 11.957s.
Earlier 19-case and 43-case runs also passed. These overlapping runs used unique
disposable localhost PostgreSQL databases with normal hashing/logging and destroyed
them afterwards. Django checks, migration consistency and scoped whitespace checks
passed. Review also corrected IST-to-UTC evidence normalization before its regression
test passed. This is affected regression evidence, not production acceptance or full CI.

**24 October 2026 - manual INR final-disposition foundation implemented locally (0038).**
Added one immutable full-principal proposal per agreement, signed owner-bound previews,
customer authorization, source-specific refund legs and actual manual fulfilment records.
Jewellery handover requires invoice/top-up evidence; online refunds require a manual
provider-dashboard reference, original cash refunds a cash-return reference, both with
customer receipt evidence. No provider API or replacement-credit wallet is added.
Earliest verified uncorrected receipts fund the invoice first; the remainder retains
its original sources. A proposal reduces no liability. Each exact fulfilled leg reduces
remaining principal, while unpaid refunds remain visible and full closure stays blocked.
Completion appends a closure event only after all principal is fulfilled and current
payment/closure evidence still matches. Replays/duplicates, late payments and altered
source facts are guarded; completion does not manufacture legacy Redemption rows.

This internal foundation is limited to optional/calendar/no-benefit future INR contracts;
schema-2 enrolment, payment and legacy closure entry points remain blocked. No owner or
customer screen is activated. Synthetic future fixtures exercise the service boundary
only in disposable localhost PostgreSQL. Fulfilment records are owner-attested evidence,
not independent bank-credit verification. Actual physical-return reversal, other policy
families, statement/privacy integration and full runtime journey remain unimplemented.
The new reverse migration refuses to delete any disposition history. No ordinary
local/production migration, environment change, commit or push. Existing dirty worktree
changes preserved. Next: contained full-return reversal, then schema-2 contract/payment
integration and the remaining builder-v1 acceptance checklist in MVP_PLAN.md.

Verification: 135 principal/settlement/closure/liability/policy/privacy regression tests
passed in 563.311s. The final 48-case settlement/contribution/cash run passed in 121.892s,
including the completed diagnostic integration and concurrent completion coverage.
These overlapping suites used unique disposable localhost PostgreSQL databases,
normal password hashing/logging, and destroyed their databases afterwards. Django
checks, migration consistency and scoped whitespace checks passed. Initial 37-case
testing exposed fixture errors (pending payments retained paid-only fields, ORM NaN
validation intercepted an intended SQL test, and a reverse-migration test used current
services before restoring later tables); fixtures were corrected before these passing
runs. This is affected regression evidence, not full CI or production acceptance.

**24 October 2026 - SES setup in progress; Postmark remains live.**
The owner authorised migration and accepted a brief interruption for the final
single-web-container replacement. Read-only SSH confirmed healthy release
`4d92b57588d0714eb2e9b48661df1878824953d0`, standard SMTP to Postmark on port 587,
STARTTLS and sender/server address `admin@jaishrikrishnajewellery.com`. Existing
Cloudflare web records, Google root MX/SPF, strict DMARC and Postmark DNS were preserved.

Created the Mumbai SES domain identity, RSA-2048 Easy DKIM, three DNS-only CNAMEs
and separate `ses-bounce` MX/SPF records. SES reports verified identity and successful
DKIM/custom MAIL FROM. Created and assigned `jsk-transactional`; VDM engagement
tracking is disabled, no open/click destination is configured, archiving and Auto
Validation are disabled, and account suppression covers bounces and complaints.
After explicit owner confirmation, submitted the transactional production-access
request with the admin contact; AWS shows **Under review**, still in sandbox.

Created the approved SMTP-only IAM user with console access disabled. Its group
contains only that user, and SendRawEmail is restricted to the Mumbai domain identity
and exact transactional configuration set with FromAddress restricted to the admin
address. The first identity-only send was rejected before acceptance because the
configuration-set ARN also needed permission; the precise resource was added, not a
wildcard. Credentials were staged mode 0600 outside the server application repository;
both temporary browser downloads were removed. No credential value entered chat or Git.

Production-container TLS 1.3 and SMTP authentication (235) passed. One explicitly
overridden SES connection sent a controlled synthetic multipart message; Gmail shows
inbox delivery after three seconds, SPF/DKIM/DMARC pass, the custom bounce Return-Path,
direct login link and no tracking image. Marker `8702d39138c1` identifies this test.
Simulator bounce/complaint marker `392bbf08b2ca` produced both feedback messages;
the bounce landed in Spam. Added Standard SNS topic `jsk-ses-failures`, a confirmed
admin email subscription, and enabled `jsk-failure-alerts` for bounce, complaint,
delay, reject and rendering-failure events only. Publishing is limited to the exact
SES configuration set and source account. Marker `f113e40c4751` verified both Bounce
and Complaint notifications in the admin Inbox; no spam-bypass rule was installed.
An alternate From address was rejected with 554. Production EMAIL_HOST remained
Postmark throughout; no customer/financial workflow was used to manufacture evidence.

Isolated `chore/ses-email-migration` from deployed main contains only owner privacy
wording for SES plus historical Postmark copies, with read-only preview assertions.
All **176 accounts/reminder/enrolment-notification regressions passed in 212.946s**
on a uniquely named disposable localhost PostgreSQL database, destroyed afterwards,
with normal logging/hashing. A standalone system check passed using process-only
synthetic settings; initial invocations lacked required environment settings before
the corrected check. No ordinary/production migration, app deployment, SMTP cutover,
Postmark retirement or unrelated plan-builder release occurred. The canonical deployment
runbook now records the bounded interruption, preflight, protected rollback and recovery.
Read-only Postmark API inspection found zero suppressions in the default outbound
stream; recheck immediately before cutover and preserve any newly suppressed contacts.
A protected SMTP-only Postmark rollback snapshot was saved outside the application
repository. Production deployment checks passed at ERROR level with the existing
HSTS-subdomain/preload warnings; financial exceptions were all zero. The active
fifteen-minute reminder timer was inspected and left running.
Next: finish privacy/release review, obtain AWS production access, recheck suppressions
and baseline state, then controlled cutover and operational acceptance.

AWS follow-up: after explicit owner approval, the complete reply to case
`179283496400032` was submitted on 24 October at **15:52:29 IST**. The posted
correspondence was verified, and the case status is **Customer action completed**.
It supplies the URL, transactional purposes, recipient verification, failure handling
and sample content description. Its initial estimate is 100 emails/month, typically
0-10/day; actual Postmark outbound statistics for 25 September-24 October show 11
sends, peak five/day. No customer record, credential or live verification link was
included. SES still reports sandbox access, 200 emails/day and one email/second;
its setup page still displays More information needed while the support reply awaits
AWS review. Production access has not been granted, so no cutover occurred.

The owner instructed that isolated commit `c444b3c` (seven SES-only files) remain
local. No push or PR was created, and no publication is planned under the current
instruction. The earlier automatic approval rejection of the push caused no remote
change. Postmark remains the production transport; the local privacy wording is
not deployed. Await AWS's decision before the remaining release and cutover gates.

**24 October 2026 - INR principal-accounting foundation implemented locally (0037).**
Added a distinct future `INR_CREDIT` account denomination with immutable source-linked
principal receipts and full evidenced cash-entry corrections. Services derive amounts
from stored verified live-capture/cash evidence, reload owner authority, lock account
then source, and reject duplicate/conflicting writes. Read selectors retain principal
history under source drift, flag missing/inconsistent credits and report purchase-credit
principal separately from legacy CASH bonuses and metal. `check_inr_principal` is
read-only. A pure full-settlement calculator splits invoice application, principal
refund and external top-up; it creates no refund, debit or closure.

Schema-2 enrolment and INR payment/legacy redemption/closure entry points remain blocked.
INR statements and deletion-disposition completion are also blocked rather than
misclassifying purchase credit as a zero-balance metal/legacy-cash account.
No UI offers, payment wiring, actual refund workflow, benefits or final settlement are
activated. New ledger tests use explicit synthetic future contracts in disposable local
PostgreSQL; no runtime enrolment bypass was added. Reverse migration refuses to drop
INR contracts/evidence. Verification passed: 145 affected contribution, cash, liability,
instalment, settlement/closure and policy/migration tests in 492.196s; 65 Razorpay and
policy-boundary tests in 80.086s; and the final 41 principal/privacy-boundary tests in
78.744s (including concurrent correction and deletion guards). These overlapping
suites used disposable localhost PostgreSQL databases, normal logging/hashing and
destroyed their databases afterwards. Django checks, migration consistency and scoped
whitespace checks passed. This is targeted regression evidence, not full CI or release
acceptance; the accumulated-work checkpoint remains required.
No ordinary local/production migration, environment edit, commit or push. The existing
dirty worktree was preserved. This is a bounded source-ledger slice, not completion of
the full INR or owner-builder checklist. Next: persisted manual final-settlement and
fulfilment records, then complete contract/payment integration and release acceptance.

**24 October 2026 - independent policy persistence implemented locally (0036).**
The owner approved one final manual INR settlement with unused-paid-principal refund,
no partial redemption, no replacement credit and no automated refund API. ADR-0017,
DOMAIN_RULES and the builder checklist record that decision; external approvals,
usable refund routes and actual fulfilment evidence remain publication requirements.

Added policy schema 2 to immutable configuration versions: separate duration/count,
INR versus exact-metal accumulation, eligibility, missed-benefit and parameterised
benefit terms. Schema 1 retains its old fields/serialization/digests; no historical
agreement is reinterpreted. New versions cannot downgrade the schema. Database checks
reject inconsistent/null policy shapes and nonfinite benefit caps; reverse migration
refuses to discard schema-2 records. Old owner forms remain schema 1 and reject forged
advanced fields; schema-2 owner views are read-only and show the correct denomination.
All schema-2 plan projection/publication/agreement paths remain preparation-only even
with the release flag on. This adds no INR ledger, benefit award or financial settlement.

Migration 0036 was exercised only in disposable localhost PostgreSQL tests. No ordinary
local/production migration, environment, commit or push changes. Existing unrelated
worktree changes were preserved. The 159-test affected regression run passed 158 cases
and exposed one historical migration-test fixture using today's serializer before
the schema-version column existed. The fixture now freezes the historical format and
compares today's serializer after upgrade; the final 24-test policy/migration rerun
passed in 38.291s. The broad run took 486.383s. Both used disposable localhost PostgreSQL
with normal logging/hashing, and destroyed their databases afterwards. Django checks,
migration consistency and scoped whitespace checks passed. Full normal CI and the
broader accumulated-work checkpoint remain required; no clean full-CI claim is made.
Next: review/checkpoint accumulated work, then separate INR principal accounting and
manual final-settlement evidence, followed by eligibility variants and benefit workflows.
The complete owner builder is not finished or activated.

**24 October 2026 - builder-v1 contract approved; compatibility foundation implemented locally.**
Owner approved the matrix, INR settlement approach and benefit types and authorised
implementation. The residual-credit alternative and external INR publication approvals
remain explicit dependencies, not implied refunds or permission to lose principal.
Added immutable typed `PlanPolicy`, strict independent-dimension/Decimal validation,
and operational blockers for valid but unimplemented families. Existing configuration
creation and plan projection now use the compatibility adapter. Configuration evidence,
revision digests, old agreement terms and persisted schemas are unchanged; this is
not a new eligibility calculator, INR ledger, benefit award or settlement service.
No new owner choices are enabled. No environment, production, commit or push changes.
Verification: all **136 affected tests passed in 362.111 seconds**, including the
11 new policy cases plus configuration, agreements, calendar schedules, publication,
full settlement and eligibility regressions. The runner used a unique disposable
localhost PostgreSQL database (destroyed afterwards), normal logging and no process
password-hasher override. An initial runner setup error (`TEST.MIRROR` omitted) was
corrected before database creation. Django checks, migration-consistency (`No changes
detected`) and scoped whitespace checks passed. No ordinary database migration ran;
this is targeted regression evidence, not full CI or production acceptance.
Next implementation work is versioned persistence of the approved independent fields
with backward-compatible evidence, followed by the remaining financial workflows in
MVP_PLAN.md. The broad accumulated-work checkpoint and release acceptance remain open.

**24 October 2026 - concrete builder-v1 contract proposal prepared.**
Inspected the configuration constraints, schedule/eligibility and full-closure service
boundaries. ADR-0017 now proposes five compatible rule families, independent duration/
count fields, immediate verified-count eligibility, INR full-invoice settlement and
two parameterised benefit types. The matrix includes calendar/anniversary payment
ceilings separately from obligations; unresolved benefit/formula and INR disposition
choices are labelled as recommendations requiring approval, not implemented promises.
MVP_PLAN.md tracks this proposal as drafted while contract acceptance remains unchecked.
Next: owner accepts/amends the three decision groups, then checkpoint accumulated work
and implement typed policy contracts without changing legacy versions. Documentation
only; no code, migrations, production, commit or push. Whitespace validation is the
appropriate check for this step; prior application test evidence is not a new test run.

**24 October 2026 - owner-builder v1 completion before activation (approved).**
The owner accepted a coherent builder-v1 production release instead of activating
the supported subset now. MVP_PLAN.md now tracks the target family matrix, outstanding
contract decisions and one completion checklist using the existing FW-PLAN items.
Incremental implementation/review remains gated; PR completion is not a release.
INR credit, count-only/anytime eligibility and defined benefits remain unimplemented;
this sequencing approval does not invent their financial terms or override existing
business/legal/accounting/provider approval requirements. Customer-authored plans and
partial redemption remain excluded. Next: finalise the matrix and contract decisions,
and checkpoint the accumulated work before further financial implementation.
This update changes canonical documentation only; no code, migrations, environment,
production, commit or push actions. Earlier verification evidence below is unchanged.

**24 October 2026 — calendar-month instalments and explicit builder dimensions (local).**
Added `CALENDAR_MONTH` alongside immutable anniversary schedules. The enrolment
month is compulsory even when short, and an enrolment-day payment can qualify.
Normal completion uses the later of original agreed duration and final qualifying
period end; completing the count early does not allow extra payments or shorten
duration. Calendar extensions and separately acknowledged outage compensation use
the frozen basis. Existing verified provider-timing/deadline review and cash receipt
attribution remain in force; no webhook-arrival attribution or automatic reassignment.

The owner editor now separates obligation, period basis, payment limit, eligibility
and missed-payment outcome, with explicit compatibility validation. Customer offers,
agreement summaries, forecasts and completion notices disclose the same rules.
Reminder candidate selection now includes the original duration date as well as
period ends. Migration 0035 expands the new-configuration constraint and labels,
without converting existing agreements or changing their evidence. ADR-0017,
domain rules, roadmap, deployment guidance and the owner manual document the policy.
The manual's older screenshots are labelled as preceding the new controls.

Verification used disposable localhost PostgreSQL databases. The first calendar
run exposed a test-fixture argument error; the next exposed the reminder candidate-
query gap and an outage-fixture method collision, corrected before rerun. The
nine-test calendar run passed (28.295 seconds, normal hashing), then the added
publication/enrolment case passed separately (2.527 seconds). The broad 845-test
schemes/accounts/pages run passed 844 cases in 657.641 seconds; its sole failure
was an `assertLogs` test because that invocation globally disabled logging. That
invocation also used a process-only MD5 hasher; neither setting changed application
configuration. The final **35-test** calendar/funnel/manual/accessibility rerun
passed in **32.026 seconds with normal logging and password hashing**, including
the previously affected warning-log case. Django system, migration-consistency
and whitespace checks passed. This is not a claim of a single clean 845-test run;
normal CI remains required before release.

A mechanical wording edit was corrected before testing; recovered Python service
semantics were checked against pre-edit bytecode. No ordinary database migration,
production change, gate activation, commit or push. Existing unrelated local work
is preserved. Calendar controls and updated disclosures still need owner/mobile
acceptance; 0035 has only been applied to disposable test databases in this task.

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
The owner chose dashboard plus monitoring-webhook alerts. Later investigation
confirmed the existing Better Stack heartbeat. Its five-minute period, six-minute
grace and business email delivery passed reported-failure, missed-run and recovery
acceptance on 26 October, as recorded above; no Healthchecks.io setup is required.

**24 October 2026 — expired Razorpay checkout incident resolved (production).**
Owner-authorized reconciliation of contribution 20 on JSK-52C44D66 used the deployed
service on release `4d92b57588d0714eb2e9b48661df1878824953d0`. A mode-matched Live
provider dry-run returned `created`, INR 500.00, zero attempts/payments/amount paid,
and the full amount due. The apply pass performed a fresh provider inspection and
recorded `ABANDONED` with immutable reconciliation audit 104 at 10:19:35 IST.
Contribution 21 remains PAID for INR 500.00 and exact 22K entitlement remains
0.037169 g. No payment, allocation, rate lock or provider reference was deleted.

Verification: the deployed customer view rendered HTTP 200 with its contribution
link in a database-enforced read-only transaction, without a customer login/session
or a new order; `get_customer_plan_next_action` returned `can_pay=True` and the cash
entry blocker cleared. The live owner record displays “Checkout closed after review”.
Financial-exception and payment-operations checks passed with all grades OPEN and
zero remaining pending Razorpay contributions across production, including other modes.

Investigation: every unresolved pending Razorpay contribution can suppress the
customer's primary payment action, including flexible agreements with a later paid
order and attempts from earlier months. Monthly services additionally protect the
current period; cash entry blocks on any pending online attempt. Checkout expiry
does not prove non-payment or reconcile the order. Expired pending attempts are
missing from the existing financial-exception counts/queue, and the inspected active
systemd timers had no Razorpay reconciliation job. The default reconciliation command
waits 24 hours from creation; this incident was about 22 hours old, so that default
would have skipped it. The explicit single-order service used a one-hour age cutoff.

Local verification: all 19 Razorpay service/reconciliation-command tests passed
(16.102 seconds, normal hashing) on a fresh disposable localhost PostgreSQL test
database. Two added cases reproduce the flexible-plan/later-paid-order suppression
and verify provider-backed recovery without changing paid entitlement, and retain
the monthly hold when the provider reports an attempted payment. Django system and
whitespace checks passed. The operational follow-up is `FW-PAY-008` in FUTURE_WORK.md.
No application-code deployment, migration, automatic
cleanup job, financial-policy relaxation, new payment or refund was part of this
incident. Unrelated local development remains separate from the production image.

**24 October 2026 — account-deletion workflow simplification (local).**
Customer request pages now lead with the action, timing and preserved savings;
the existing detailed retention explanation is available in a native expandable
section. Signed-in confirmation explicitly says the customer will be signed out.
The owner form collects shared retention start, duration/release condition and
review date once, with optional per-category exceptions: 18 fewer repeated entries
when terms match. Category names replace disabled visible selectors, confirmation
comes after the decisions, and financial/inventory reference tables are expandable.
All seven explicit treatment/purpose/minimum-record decisions still resolve to the
existing full audit/notice format and service validation. No automatic retention
schedule, new deletion state or financial-history disposal was introduced.

Regression coverage includes shared terms and category exceptions, missing/invalid
terms, confirmation, full category coverage, retained-entitlement preservation,
idempotent completion, and retention reviews without identity restoration.
Verification: all **215 accounts/pages tests passed** (130.711 seconds), including
the 42 deletion/completion tests, in a fresh disposable localhost PostgreSQL test
database with no test-process-wide fast hasher. Django system, migration-consistency
and whitespace checks passed. The first 41-test deletion run had one page-wording
assertion failure, corrected before the final run. No schema change,
ordinary/production data mutation, policy-version change, commit, push or deployment.
Browser/mobile layout acceptance and existing production release gates remain separate.

**23 October 2026 — owner-only on-site plan reference manual (local).**
Added `/scheme/owner/plan-manual/`, linked from Scheme plans, Configuration catalogue
and configuration details. The page uses the same version-controlled illustrated HTML
as the standalone guide, with authenticated illustration URLs, return navigation and
the current configured-intake flag. It is readable even when new intake is disabled;
it never enables a feature or changes financial/agreement records. Existing owner and
active-superuser permission rules apply to both HTML and all four illustrations;
customers, ordinary staff and inactive users cannot access them. GET/HEAD only,
private/no-store, Vary: Cookie, noindex and a script-free CSP are applied.
Only the guide and its four images are allowlisted back into the Docker build context;
the rest of repository documentation stays excluded and is not served by a generic
document endpoint. Source Markdown links become labelled repository references on-site.
Screenshot signatures revealed JPEG data under PNG extensions; the four files and
references were renamed to `.jpg` without changing their image content.
Verification: 15 database-free manual/accessibility tests passed (0.339 seconds),
including authorization, method restrictions, asset types, cache headers, URL/anchor
integrity and gate-off access; Django check and whitespace checks passed. The first
run caught the screenshot MIME mismatch and was corrected before the clean rerun.
No new migration, database mutation, environment change, commit, push or deployment.
This entry does not claim live-site availability, container or browser-layout acceptance;
the running synthetic helper needs a planned restart to load the new URL configuration.

**23 October 2026 — illustrated plan-configuration owner guide.**
Added `docs/guides/plan-configuration/index.html`, linked from TESTING.md, with four
actual synthetic local screenshots, lifecycle/versioning diagrams, a field-by-field
monthly recipe, calendar/monthly comparison, enrolment/payment explanation and
unused/early-full-settlement instructions. It distinguishes current local support
from deferred INR-credit/benefit/anytime families and production activation. The
shared edit form's legacy date-only helper wording is explicitly identified as a
remaining UI caveat, not treated as the configured monthly policy.
Documentation and screenshot assets only; no application change, saved plan, publication,
agreement, ordinary migration, environment change, commit, push or deployment.
The existing review offers remain unpublished. Owner/release acceptance is unchanged.
Guide QA: all 15 section anchors, four image files/alt descriptions and relative source
references validated, with no duplicate IDs or scripts. Actual screenshots were visually
inspected. Browser opening of the local HTML was blocked by its file-URL security policy;
no workaround was attempted, and responsive/print rendering of the guide is not claimed
as visually verified. Application tests were not rerun for this documentation-only change.

**23 October 2026 — P4 isolated complete-journey review prepared.**
Extended the existing local helper with `--publication-journey`: two draft offers
(calendar and monthly completion), a verified synthetic customer/owner and today's
synthetic exact-grade rate, but no pre-created requests, agreements or financial
records. Only the fresh `jsk_p4_review_*` database/process enables publication and
enrolment intake; the ordinary local environment/database and production are unchanged.
Online payments, external email and outbound application traffic remain disabled.
The separate port 8767/cookies preserve the earlier B4 review. No ordinary migration,
commit, push or deployment. The owner protocol is in `docs/TESTING.md`.

Six helper tests passed with normal hashing (13.108 seconds), including both actual
publication → request → enrolment → synthetic cash → early full-settlement paths.
The standalone check-only migration/seed/role/integrity/cleanup check also passed and
removed only its generated database. The complete local Django suite then passed:
**839 tests, 725.719 seconds**, using a fresh disposable localhost PostgreSQL database
and a test-process-only fast hasher. This supersedes the earlier incomplete broad-run
checkpoint below; it is not hosted CI or production acceptance. Django system and
migration-consistency checks passed and the ordinary environment's release gate is false.
Chrome owner login and the unpublished monthly screen passed a limited 390px no-overflow
and confirmation → reason → publish keyboard-order smoke check; viewport reset afterward.
The draft is left for owner review, not published by the browser check.

Two old diagnostics' hard-coded activation-disabled labels are corrected to report
`configured_intake_enabled` from the actual release flag. This reports new-offer intake,
not whether existing agreements may accept payments or settle. Financial rules are
unchanged. After this reporting-only correction, eight focused helper/diagnostic tests
passed with normal hashing (13.779 seconds), including both flag states. The full-suite
result above precedes that wording-only correction; no financial code changed afterward.
Next: owner review of the documented complete journey, remaining exception/accessibility
checks, then commit/CI and approved exact-image release preparation. No new plan families.

**23 October 2026 — P4 controlled publication/enrolment integration (local).**
Added an owner-reviewed publication revision, audited publish/withdraw, stale-offer
protection and the default-off `CONFIGURED_PLANS_ENABLED` release gate. Configured
enrolment now freezes the reviewed revision/individual amount and creates monthly
periods atomically. Registration applications, existing-customer requests and owner
enrolment use the same gate. Published identity/grade edits require withdrawal;
existing accepted agreements are not rewritten. Customer copy now distinguishes
calendar eligibility from required monthly completion and describes full-only early exit.

Migration 0034 adds the publication reference/constraint without activating or converting
data. The gate was verified false in the actual local environment. Ordinary local and
production databases are unchanged; tests use uniquely named disposable local databases.
Initial 14 focused tests passed with normal hashing (22.912 seconds), including actual
publication/enrolment followed by cash or fake-provider full settlement. The first
196-test affected run caught a diagnostic regression accepting unpublished synthetic
agreement terms; the integrity command was corrected to retain that rejection. The
broader schemes/accounts/pages run exercised 797 tests in 580.029 seconds: 793 passed,
with four migration-fixture errors (three current-model factories used after schema
downgrade, and one duplicate seeded grade). Those fixtures were corrected without
changing historical-data preservation assertions. A fresh 26-test rerun covering all
20 P4 cases, all four corrected fixtures, the publication upgrade and the draft-agreement
integrity rejection passed (183.184 seconds). No global fast hasher was used in that
rerun; existing application-fixture overrides remain. The wider run used a test-process-
only fast hasher. At that checkpoint a new all-green broad/CI run was still required;
the four-error run is not reported as clean. Django system, migration-consistency and
whitespace checks passed. No real provider/SMTP calls,
commit, push or deployment. P4 remains open for full owner/mobile/keyboard and release
acceptance; benefits, INR credit, anytime variants and legacy cutover are not added.
The isolated walkthrough and clean broad run requested at this checkpoint are now
recorded above; hosted CI, owner acceptance and release gates remain separate.

**23 October 2026 — B4 three-scenario owner acceptance recorded.**
The owner confirmed that the isolated walkthrough's unused-agreement cancellation,
three-of-twelve early full jewellery redemption/closure, and settlement correction
with restored entitlement and blocked payments are acceptable. This records the
owner's reported scenario acceptance, not an independently observed production run.
No additional device/viewport, keyboard or print coverage was specified. The Account
button correction remains covered by its local rendering test.

**Next recommended development:** P4 supported-configuration publication/enrolment
integration and complete offer-to-closure acceptance, retaining the existing holds
on unresolved provider histories and preserving legacy contractual rights. B4's
remaining accessibility/exception and exact-image release evidence is still open;
the parent milestone is not complete. This acceptance does not authorize activation,
ordinary/production migrations, commit, push or deployment. Only documentation was
updated for this confirmation; no tests were rerun or new test results claimed.

**23 October 2026 — Account dropdown visibility correction.**
Owner/customer workspace and public-header Account toggles now use solid buttons.
Scoped Bootstrap colour variables keep the background opaque with dark text in normal,
hover/focus and expanded states. A database-free rendering regression covers all three
header variants; it and Django checks passed. No financial or authentication behaviour,
migration, production deployment or configured-plan gate changed.

**23 October 2026 — B4 isolated owner walkthrough prepared.**
`schemes.review_closure_locally --synthetic-local` creates a fresh loopback-only
PostgreSQL review database with unused, three-of-twelve paid and correction-practice
agreements. Ordinary development/production databases and publication gates are
untouched. Simulated financial evidence uses existing services; online provider calls
and outbound email are disabled. The check-only seed, integrity/private-page checks
and synthetic cleanup passed. After an unresponsive first browser session, the helper
was hardened with bounded threaded connections to avoid preconnection stalls. Owner
login and the unused-agreement page were verified in Chrome on the restarted helper.
All 15 helper/isolation/closure tests passed with normal hashing (29.140 seconds);
Django, migration-consistency and whitespace checks passed. The stalled synthetic
database was removed and a fresh review session started; no ordinary data was removed.
The three owner scenarios were subsequently accepted above; additional mobile/keyboard
coverage remains unconfirmed. The runnable protocol is in
TESTING.md. No new schema,
product activation, commit, push or deployment is part of this step.

**23 October 2026 — B4 local automated acceptance checkpoint verified.**
Verified the customer/owner form journeys for unused cancellation and a monthly
agreement with only three of twelve instalments paid. Early settlement consumes all
actual accumulated exact-grade metal, not the unpaid target amount, and closes only
that agreement. Customer authorization and actual jewellery invoice/fulfilment evidence
remain required. Existing legacy agreements are not converted by this work.

Review corrections: retained agreement terms no longer invite cancelled/redeemed or
reversal-held accounts to contribute; accepted closure gets a dedicated next action;
configured settlement/restoration statement entries include invoice and normal/early
basis. The closure integrity command also flags new unresolved provider exposure after
settlement even if the recorded metal balance remains zero. No financial record is
automatically rewritten or deleted to resolve that exception. The nine focused tests
passed with normal password hashing (30.945 seconds); 201 affected regression tests
passed (225.996 seconds), using a test-process-only fast password hasher. These are
local HTTP/HTML, financial-service and PostgreSQL concurrency tests, not real browser
or owner acceptance. Django check, migration consistency and whitespace checks passed.

No new schema migration or activation. B4 remains open for remaining browser/mobile/keyboard
and exception acceptance, legacy inventory/disposition and an approved exact-image release
rehearsal. Production and ordinary development databases are unchanged. No external
provider call, email, commit, push or deployment occurred.

### Previous checkpoint: B3 local implementation

**23 October 2026 — B3 configured full settlement implemented and verified locally.**
The separate owner service derives the complete six-decimal exact-grade entitlement
under the agreement lock. Accepted closure, resolved real-payment evidence, a current
owner-bound ten-minute preview, invoice, customer fulfilment-confirmation reference,
reason and idempotency key are required. Normal versus early closure is server-derived:
calendar contracts use their date; monthly contracts also require the recorded payment
count and final qualifying period end. No bonus, fee, partial settlement or cash payout.

Immutable settlement proof links the existing Redemption to its closure event and
source snapshot. Controlled reversal appends evidence and restores the liability into
CLOSURE_PENDING, never reopening payments or changing login. Re-settlement needs a new
preview and confirmation. Direct terminal status edits and the legacy reversal path
cannot bypass this lifecycle. Existing legacy settlement rights/history are unchanged.

Conservative V1 boundary: pending/unallocated, Test/mock and failed/abandoned provider
histories remain blocked. Local expiry is not irrevocable provider cancellation. Monthly
timing/review/outage exceptions also block both normal and early settlement. The later
provider-disposition workflow and legacy inventory/cutover are still required; B3 does
not authorize owners to attest these blockers away. Configured publication/enrolment
remains blocked. Migration 0033 adds source-proof tables and lifecycle constraints,
with no backfill or financial rewrite. **28 B3-focused tests passed with normal
password hashing** (109.561 seconds). The final **803-test full regression passed**
(644.246 seconds), using a test-process-only fast password hasher, not a configuration
or production hashing change. Initial runs
found and corrected test-fixture mistakes (calendar helper-name collision, missing
fixture callback, future-outage fixture and deletion/null expectations), not relaxed
business rules. Django check, migration consistency and whitespace checks passed.
All schema rehearsals used disposable local PostgreSQL test databases. No ordinary or
production migration, external provider call, email, commit, push or deployment occurred.

**Next:** B4 owner/mobile, source-preservation and release
acceptance before P4 publication. No production changes or activation are authorized.

### Previous checkpoint: B2 local implementation

**23 October 2026 — B2 configured unused-agreement cancellation implemented locally.**
An active owner can separately cancel an ACCEPTED closure only after the account-locked
service proves there is no contribution of any status/mode, redemption, reservation,
instalment investigation or outage-resolution history. Failed, abandoned, test and reversed
payments are not treated as unused. Empty scheduled periods and closure notes are allowed.
The append-only CANCEL event and both CANCELLED projections are atomic, reasoned,
idempotent and stale-sequence guarded. No payment, redemption, refund, benefit, deletion,
login change or reopening is created. Other agreements remain unchanged.

Private Bootstrap owner confirmation, customer history/statement wording, active-count,
payment, next-action, eligibility and review-queue projections now distinguish cancelled
from redeemed. `check_scheme_closures` checks terminal evidence/status agreement and
rejects financial/review history after cancellation. Legacy cancellation and privacy-erasure
policy are not widened. Configured publication/enrolment remains blocked.

Migration **0032** only extends lifecycle choices/constraints; no data backfill. **42 focused
tests passed with normal password hashing** (133.518 seconds), including migration
preservation and PostgreSQL cancellation/retry/payment races. The first run exposed a
duplicate-customer fixture, corrected without changing application behaviour. The final
**775-test full regression passed** (624.048 seconds) using a test-process-only fast
password hasher, including distinct form-ID, terminal next-action and review-queue
presentation updates. Django check, migration consistency and whitespace checks passed.
All schema work used disposable local PostgreSQL test databases.
No ordinary/production migration, provider call, email, commit,
push or deployment. Owner/mobile and exact-image release acceptance remain outstanding.

**Next:** B3 full-only normal/early settlement and controlled reversal, preserving
all six internal decimal places and existing financial/history protections. This is
not permission to activate plans or change legacy contractual rights.

### Previous checkpoint: B1 local implementation

**23 October 2026 — B1 configured-agreement closure lifecycle implemented locally.**
Customer and authorized owner-assisted requests now retain immutable request facts
and append-only sequenced review events. Pending requests can be withdrawn/rejected;
owner acceptance blocks new online/cash payments and checkout resumption without
changing agreement status, financial history, entitlement or customer login. Accepted
requests permit investigation notes, not a silent return to payment collection.
Existing captures, allocation recovery and authorized cash corrections continue.

Private customer/owner Bootstrap forms, an owner queue, read-only admin and
`check_scheme_closures` expose the lifecycle. Review counters never assert unused
or settleable status. Accepted closure suppresses completion reminders, including
delivery of a candidate planned before acceptance. Configured activation remains
blocked; legacy agreements do not gain new closure rules in this step.

Migration **0031** adds empty closure request/event tables and database constraints;
no financial/history backfill. **26 focused tests passed with normal password hashing**
(73.388 seconds), including PostgreSQL races, migration preservation, in-flight capture,
cash retry/correction, permissions, CSRF and stale/idempotent decisions. A further
planned-reminder suppression test is included in the final **760-test full regression**,
which passed in 630.569 seconds with a test-process-only fast password hasher.
Django check, migration consistency and whitespace checks passed. All schema rehearsal
and payment evidence were confined to disposable local PostgreSQL test databases.
No ordinary/production migration, provider call, email, commit, push or deployment.

**Next at that checkpoint:** B2's proof-based unused cancellation, followed by B3 full-only settlement
and controlled reversal. B1 owner/mobile and release acceptance remain open; no request
or acceptance currently performs cancellation, refund, delivery or settlement.

### Previous checkpoint: P3 local review

**23 October 2026 — P3 local checkpoint reviewed; presentation gaps corrected.**
Reviewed shared evaluation, customer actions, reminder revalidation and activation
gates. The owner Today queue still used original dates for all agreements, and a
direct URL could show the legacy partial-redemption form for a configured agreement
although the financial service rejected it. The queue now excludes configured
agreements and describes calendar-date review, not settlement approval. Direct
configured redemption GET/POST requests return 404; the service guard is unchanged.
Monthly agreement copy now explicitly permits valid extension-window payments after
the original date, while configured calendar status/actions say settlement unavailable.

Validation: **79 focused regression tests passed** (172.663 seconds; no new fast-hasher
override), covering monthly eligibility, configured agreements, owner workspaces,
legacy eligibility and redemption. The first run had two fixture-only failures:
year-forward simulated clocks expired login sessions; logging in at the simulated
date corrected the tests. Django check, migration consistency and whitespace checks
passed. The earlier 729-test full run remains prior-checkpoint evidence, not a fresh
full-suite run for these corrections. Only disposable local PostgreSQL was used.

No financial mutation, new migration, production email, commit, push or deployment.
All configured activation gates remain. This local checkpoint permits moving to
**B1 closure lifecycle** next; it does not mark the parent P3 work item release-complete.
Owner/mobile/email review, settlement integration, CI and exact-image acceptance are
still required. B2 unused cancellation and B3 full-only settlement remain separate.

### Previous checkpoint: monthly reminder delivery

**23 October 2026 — P3 policy-aware reminder delivery implemented locally.**
Monthly plans now have a distinct `UPCOMING_MONTHLY_COMPLETION` notice, selected
only when the required count is qualified, the final period has not ended, and
allocation/review state is clear. Conditional forecasts never generate these emails.
The derived period-end date, reminder kind, agreement, lead time, audience and
recipient form the existing immutable reminder identity; original dates are retained.
Text/HTML distinguish payment progress from redemption, closure and benefit awards.

Delivery takes the agreement lock, refreshes the account/recipient, and re-evaluates
policy, date and eligibility switches before creating mail/attempt evidence. Stale
candidates are skipped and counted without a fictitious SMTP attempt. Failed-mail
retries undergo the same checks; previously accepted notices remain immutable.
Legacy date-only reminder semantics and explicit date replay remain; monthly replay
is refused because current ledger evaluation is not historical reconstruction.

Migration **0030** extends reminder kind/shape constraints without backfilling
agreements or modifying existing messages, attempts or financial records. It has
only been exercised in disposable local test databases. Configured publication,
enrolment and full-only settlement remain blocked. No commit, push or deployment.

Focused validation: **27 reminder tests passed with normal password hashing**,
including concurrent delivery/reversal, migration preservation and missing allocation
containment. Django checks, migration consistency and whitespace checks passed.
The initial broad run exposed a migration-test ordering issue (an unrelated accounts
schema left historical); the new test now restores all app leaves before its rehearsal.
The final **729-test full regression passed** with a test-process-only fast password
hasher (544.258 seconds), including the isolation fix and final allocation-gap test.
No production mail or provider calls were used. This is not owner/CI/release acceptance.

**Next:** P3 checkpoint review of evaluation, presentation, reminders and activation
gates, then B1 closure lifecycle in the recorded execution order. Owner/mobile and
exact-image/CI acceptance are not implied by local tests; benefits remain NONE.

### Previous checkpoint: shared eligibility projection

**23 October 2026 — P3 shared monthly eligibility projection implemented locally.**
Monthly completion now derives count, original date, conditional forecast and final
qualifying-period completion from the validated ledger/schedule. India-time period
boundaries, ordinary extensions and acknowledged outage amendments are respected;
reviews, uncertain orders and reversals cannot manufacture eligibility. Exhaustion
requests discontinuation review without changing entitlement or closing an account.
Allocation-pending payment qualification is reported separately from settlement.

Customer availability uses that projection and the existing payable/resumable-period
guard, rather than stopping at the original date. Detail/status/statement wording
distinguishes monthly requirements from legacy date-only eligibility. Configured
agreements are separated from legacy owner redemption buckets and excluded from
legacy original-date eligibility reminders. This is conservative suppression, not
completion of the monthly reminder workflow. No benefit, settlement or activation
permission is introduced; no schema or ordinary/production database change.

Validation: **708 full-regression tests passed** with a test-process-only fast
password hasher against disposable local PostgreSQL test databases. The final
**18 monthly-eligibility tests passed with normal hashing**, including two additional
ambiguous-order/duplicate-capture cases added after full-suite discovery. Django checks,
migration consistency and whitespace checks passed. This is local development
evidence, not CI, owner acceptance or production rollout approval.

**Next:** finish P3's policy-aware reminder identity, wording and delivery-time
revalidation, then its acceptance checkpoint before B full-only settlement and P4.
Benefits remain NONE for these approved families; additional numeric benefit terms
are not inferred. Owner/mobile acceptance, CI and exact-image rehearsal remain open.

### Previous checkpoint: owner-form accessibility

**23 October 2026 — P2 owner-form accessibility correction implemented locally.**
The period-review, order-recovery and outage-resolution templates now give each
help-text element the ID already referenced by Django's widget. Existing error-list
IDs, validation, CSRF, authorization and financial services are unchanged. Five new
database-free rendering tests reproduced the defect before the fix and now pass;
they cover unbound/invalid forms, multiple claim forms, labels, help/error targets,
checkboxes, non-field errors and escaped input.
The combined accessibility/owner-review/outage/order-recovery run passed **53 tests
with normal password hashing**, using disposable local PostgreSQL test databases.
Django checks, migration consistency and whitespace checks passed. No full-suite
rerun is claimed for this template-only correction.

Using the computer-use skill, a read-only localhost preview rendered synthetic
forms with database execution prohibited. Chrome checks at 390x844 and 1440x1000
covered these three form layouts, visible errors/help and keyboard field traversal;
the inspected mobile pages had no horizontal document overflow. The preview server
and tab were closed and the viewport reset. This is a technical form-rendering
smoke, not owner approval, an assistive-technology audit or the full exception journey.
Owner scenario acceptance and CI/exact-image release checks remain outstanding.

**Next development:** P3's shared monthly eligibility and customer availability
evaluation, preserving legacy date-based agreements and configured activation gates.
Then B full-only settlement and P4 acceptance, as already planned. No new policy,
financial mutation, schema migration, ordinary database change, commit, push or
deployment was made in this correction.

### Previous checkpoint: accumulated P2 review

**23 October 2026 — accumulated P2 checkpoint reviewed; not release acceptance.**
Reviewed the configuration/enrolment gates, additive migration boundaries, monthly
reservation/evidence services, outage amendments, order recovery and retained capture
exceptions. No new financial mutation defect was identified in the reviewed paths.
Configured activation/enrolment and settlement remain blocked; historical agreements
are not assigned new instalment obligations. This is not an independent audit or a
claim that all release scenarios have passed.

Review validation: **149 focused governance/configuration/P2 tests passed**, including
forward migration and concurrency cases, using a test-process-only fast password
hasher and disposable local PostgreSQL test databases. Django checks, migration
consistency and whitespace checks passed. The previous 687-test full regression
and 26-test normal-hashing capture/recovery run remain prior-checkpoint evidence;
they were not rerun or represented as a new full-suite result here.

One reproducible owner-form accessibility finding remains: the period-review,
order-recovery and outage-resolution templates render Django widgets with
`aria-describedby` help-text references but omit the matching help-element IDs.
Synthetic HTML probes confirmed the dangling references without a database write
or provider call. Correct these three renderers and add rendered-HTML regression
coverage before owner keyboard/screen-reader acceptance. No application fix was
made during this review.

P3 remains necessary: customer payment availability still uses legacy calendar
completion/frequency logic apart from the newly added capture hold. It must consume
monthly reservation/outage/count/extension state consistently with the services;
do not interpret this intentionally gated integration gap as permission to activate
configured plans. Owner/mobile visual acceptance, CI and exact-image PostgreSQL
18.6 rehearsal remain outstanding. No browser acceptance was claimed in this review.

**Next:** the bounded form-accessibility correction and owner/mobile checkpoint,
then P3, B full-only settlement and P4 in the existing order. No new phase, benefit
family, refund workflow, normal-database migration, commit, push or deployment.

### Previous checkpoint: late/duplicate-capture containment

**23 October 2026 — P2b.3b late/duplicate-capture containment implemented locally, not released.**
Review found that a different capture for an already-paid monthly order retained a
provider exception but did not block the next anniversary payment. Both online and
cash initiation now check account-scoped unresolved Live captures, including transient
events and unknown-order events whose order identity was subsequently recovered.
Owner timing acceptance uses the same guard; investigation notes cannot clear it.
The first receipt, allocation, rate and qualification remain intact. A different
payment is recorded as DUPLICATE_CAPTURE_REVIEW, not a second credit.

Owner period/queue pages expose captured-payment exceptions and link existing provider
reconciliation; customer payment availability explains the hold. Integrity output
includes `unresolved_capture_events` separately from corruption/errors. Delayed
on-time delivery still qualifies once; existing in-flight replacement confirmation
continues during a hold/global pause. Abandoned-order captures cannot replace the
legitimate contribution. Post-expiry non-abandoned captures retain existing verified
funds/metal evidence but remain in timing REVIEW, without eligibility or silent repricing.

ADR-0017 records the disposition matrix. This is containment, not automated refunds
or verified refund closure; unresolved cases stay held for the manual provider process
and separately reviewed closure work. No new schema migration is needed beyond 0029.
Validation: **687 full serial regression tests passed** with a test-process-only fast
password hasher; **26 focused capture/recovery tests passed with normal hashing**.
Coverage includes two different concurrent captures, original/replacement isolation,
transient retries, late versus delayed evidence, recovered-order matching, owner UI
and cross-channel holds. Django checks, migration consistency and whitespace checks
passed. Migrations ran only on disposable local PostgreSQL test databases.

**Next:** review the accumulated P2 checkpoint and owner/mobile exception scenarios
before widening work to P3 eligibility. P2b.3b and FW-PLAN-003/004 are not marked
complete: owner acceptance, CI/exact-image release acceptance and dependent P3/B/P4
remain outstanding. Configured publication/enrolment stays blocked. No ordinary local/
production migration, environment edit, commit, push or deployment has been performed.

### Previous checkpoint: ambiguous-order identity recovery

**23 October 2026 — P2b.3b exact ambiguous-order identity recovery implemented locally, not released.**
New configured monthly Razorpay requests now retain a unique request UUID before
provider I/O and send it in the provider receipt/notes. An owner can supply a candidate
Live order ID; an authenticated exact lookup must match the original UUID, receipt,
contribution, amount, currency and creation time. Migration `0029_instalment_order_recovery`
adds immutable binding evidence and nullable historical request identity, without
invented backfills. Account-locked sequence checks and idempotency protect concurrent
submissions. Old requests without correlation, missing matches and provider failures
stay held for investigation, not blind order recreation or manual release.

Binding does not mark payment paid, allocate metal, qualify an instalment, extend a
deadline or change the locked rate. Recovered checkout is reconciliation-only, never
resumable; this does not cancel a provider order or an already-open modal. Existing
verified-capture and expired untouched-order reconciliation remain separate. A capture
received before identity recovery retains its review status until explicit payment
reconciliation; original signed timing evidence is still needed for qualification.
The private owner workspace and `check_instalment_payments` expose recovery evidence.

**Next:** finish late/duplicate-capture disposition boundaries and the existing P2b.3b
exception acceptance checklist, then review this accumulated local checkpoint. No new
subphase. FW-PLAN-003/004 remain incomplete; configured publication/enrolment stays
blocked pending P3/B/P4. Owner/mobile review, CI and exact-image PostgreSQL 18.6
acceptance are pending. Full serial regression: **677 tests passed** with a
test-process-only fast password hasher, including actual forward migration through
0029 and recovery/payment/outage races. **27 final focused tests passed with normal
hashing**, covering recovery, legacy customer contributions and payment presentation,
including the final non-resumable desktop/mobile history links and malformed provider
status handling. Django checks, migration consistency and whitespace checks passed.
Only disposable local PostgreSQL test databases were migrated.
No ordinary local/production migration, environment edit, commit, push or deployment.

### Previous checkpoint: bounded outage remedy

**23 October 2026 — P2b.3b bounded outage remedy implemented locally, not released.**
The owner delegated the contractual allowance/cap choice: three compensating months
per agreement, separate from the three ordinary extension months, one per affected
period. ADR-0017 now records this decision. A 12-month agreement's outer payment
window is at most 18 months; the required payment count remains twelve.

Migration `0028_instalment_outage_resolutions` adds immutable acknowledged amendments
and hold-closure evidence. Original configuration hashes, agreement dates/count/amount/
grade, ordinary periods and all financial records remain unchanged. Compensation
appends one future original-anchor window only for an ended unpaid affected period.
The owner records incident/restoration evidence and a genuine customer-acceptance
reference/timestamp. No online customer-acceptance or notification workflow is implied.
Closure without compensation is limited to an original unpaid window still open after
restoration, or existing qualification with a direct evidence link. Uncertain orders,
pending payments, allocation failures, unresolved webhooks and other open holds cannot
be cleared by an acknowledgement checkbox. Exhausted/prolonged cases remain in review,
not forfeiture. Customer agreement displays distinguish the added window from original
terms and do not promise eligibility. Integrity checks validate the amended schedule.

**Next remains the same P2b.3b boundary:** conclusive provider-backed ambiguous-order
recovery, late-capture disposition and final exception acceptance. FW-PLAN-003 and
FW-PLAN-004 are not complete; configured publication/enrolment remains blocked until
dependent P3/B/P4 acceptance. No new numbered subphase or benefit/settlement scope.

Validation: **661 full serial regression tests passed** with a test-process-only fast
password hasher; **49 final focused tests passed with normal hashing**, covering the
final selector/UI edits, compensation and capture races, payment integration and actual
migration preservation through 0028. Django checks, migration-drift and whitespace
checks passed. Migrations ran only on disposable local PostgreSQL test databases.
Owner/mobile visual review, CI and exact-image PostgreSQL 18.6 acceptance remain pending.
No normal local/production migration, environment edit, commit, push or deploy.

### Previous checkpoint: roadmap audit

**23 October 2026 roadmap audit:** FW-PLAN-003 P1a/P1b are locally implemented but
await dependent settlement and release acceptance. FW-PLAN-004 is locally implemented
through P2b.3a, not complete. The architecture remains within the approved scope;
execution has become fragmented, with substantial uncommitted work. MVP_PLAN.md now
has a consolidated checkpoint and fixed P2b.3b closure checklist. ADR-0017 records the
compensating-month proposal as pending at that checkpoint; the owner subsequently
delegated the decision recorded above.
This audit changed documentation only; no new tests, migrations, commits, pushes or
production actions were performed. Last validation evidence is retained below.

**FW-PLAN-004 P2b.3a owner review workspace implemented locally (23 October 2026),
still gated; P2b.3 is not complete.** Owners can record append-only investigation
notes and outage holds with an actor, reason, evidence reference, optimistic sequence
checks and idempotent submission keys. The paginated Bootstrap workspace is linked
from financial exceptions. Customers/staff without owner authority cannot access it;
POSTs retain CSRF protection and responses are not cacheable.

Narrow timing resolution accepts only an existing independently verified Live
captured-event decision for the same reserved payment, whose stored timing envelope
fits its original period and checkout deadline. Missing evidence, conflicting timing,
uncertain orders and late captures cannot be overridden. The new owner decision links
its source and qualification result without rewriting previous evidence or financial
records. An outage hold blocks new online/cash initiation, but not incoming verified
captures, allocation recovery or authorized corrections. It neither qualifies payment
nor marks a customer late; no arbitrary hold removal, grace or waived instalment exists.

Migration `0027_instalment_owner_reviews` adds an empty review table and typed decision
source link. No legacy agreement/payment backfill. Validation: 643 full serial tests
passed with a test-process-only fast password hasher, then 32 focused tests passed
with normal hashing, including the final India-time boundary, owner UI/retry handling,
cross-account rejection, concurrent submissions/outage-versus-cash, payment integration
and actual migration preservation through 0027. Django checks, migration consistency
and whitespace checks passed. Only disposable local PostgreSQL test databases were
migrated. No ordinary local/production migration, commit or push performed. Owner
visual review, CI and exact-image PostgreSQL 18.6 rehearsal remain pending.

**Next at this previous checkpoint: P2b.3b contract-safe outage remedies and ambiguous-order recovery.**
The outage policy decision and local implementation are now recorded above. A lost order response still needs conclusive
provider identity/reconciliation, not an owner checkbox. Final exception acceptance,
P3 eligibility and B full settlement remain open. Configured enrolment/publication
remain blocked. No benefit, eligibility, settlement or general plan-builder work added.

### Previous checkpoint: P2b.2

**FW-PLAN-004 P2b.2 payment-service integration implemented locally (23 October 2026),
still gated from configured enrolment and publication.** Razorpay initiation reserves
the current anniversary period before provider order creation, caps checkout expiry
at its end, and resumes the same unexpired claim. A durable ORDERING decision commits
before provider I/O; interruption or a lost/local-unsaved response blocks blind retries.
The service therefore owns that transaction boundary and must not be wrapped in a
caller transaction. Showroom cash records its receipt,
reservation and qualification atomically; authorized cash reversal appends its linked
correction in the same transaction. Cross-channel competing payments serialize on
the agreement. Test/mock initiation is rejected for this monthly family.

Callback/API recovery records AWAITING timing evidence, not a qualifying instalment.
Signed captured-event handling attaches exact-body/hash-checked timing evidence;
late delivery alone does not make a customer late. Paid-unallocated is distinct from
settlement readiness. Expired orders retain their claim until explicit provider-backed
abandonment reconciliation appends RELEASED with its audit. A subsequent late capture
records non-occupying RELEASED_REVIEW, preserving any replacement claim and blocking
further initiation while existing provider exception handling retains the funds issue.
Ambiguous order-creation failures keep their claim for review; no timeout auto-release.

Migration `0026_instalment_payment_integration` adds typed order/qualification lifecycle states and the
reconciliation-audit reference, without rewriting historical financial records. The
integrity command reports awaiting/review/released/unreserved payments and still labels
activation disabled. Service tests use synthetic configured agreements only: the
database publication and enrolment-service gates were not relaxed. Legacy payment
confirmation/retry transaction boundaries are preserved.

**Next remains P2b.3 exception acceptance:** owner-authorized outage/timing/ambiguous
order resolution and final cross-path acceptance. No eligibility/benefit, settlement,
plan-publication or UI scope was added. P3 and B remain later dependencies.

23 October 2026 validation: 629 full serial regression tests passed with a
test-process-only fast password hasher; 18 final focused tests passed with normal
hashing, including service races, actual schema preservation and the legacy transient
webhook retry regression. Django checks, migration-drift and diff checks passed.
Migrations ran only on disposable local PostgreSQL test databases; exact-image
PostgreSQL 18.6 release acceptance remains pending. No normal local DB migration,
environment change, commit, push or production action occurred.

### Previous checkpoint: P2b.1

**FW-PLAN-004 P2b.1 internal payment-ledger foundation implemented locally
(23 October 2026), not deployed or integrated into payment entry points.**
Migration `schemes.0025_instalment_payment_ledger` adds exclusive per-period reservations
and append-only source-linked decisions. Agreement locking serializes online/cash
claims; the database enforces one occupied claim per period. Timeouts do not release
claims. Live captured-event evidence and showroom receipts can qualify payments;
Test/mock activity cannot. Missing/uncertain/boundary timing stays in review without
marking the customer late. Cash correction links an existing authorized reversal,
preserving the original decision and allowing a replacement claim. This ledger does
not change money, grams, rates, eligibility or settlement readiness.

`check_instalment_payments` reports projection/evidence integrity, qualification,
review and paid-unallocated counts, explicitly labelled `integration=not_released`.
The migration adds empty tables, with no historical attribution or agreement rewrite.
Configured publication/enrolment and monthly payment-initiation gates remain unchanged.

**P2b is not complete. Next: P2b.2 atomic payment-path integration**, including reserve
before online/cash mutation, callback/webhook/recovery handling, cash corrections,
checkout resumption and reconciliation-based release. P2b.3 still needs auditable
outage/review resolution and end-to-end acceptance. P3 eligibility and B full-only
settlement remain subsequent dependencies. No owner/manual credit override, generic
release, backdated online qualification or feature-flag bypass was introduced.

Validation: **611 full serial regression tests passed** with a test-process-only fast
password hasher, followed by **13 final focused tests passed** with normal hashing
(including two added timestamp/backfill tests, concurrency and actual 0024-to-0025
preservation). Initial schedule/ledger focus also passed 24 tests. Django system,
migration-drift and diff checks passed. These used disposable local PostgreSQL test
databases; exact-image PG18.6, CI and activation acceptance remain pending.
No normal local DB migration, environment change, commit, push or production action
was performed. The existing branch/worktree and separately stashed user notes were preserved.

### Previous checkpoint: P2a

**FW-PLAN-004 P2a monthly schedule foundation implemented locally (23 October 2026),
not deployed or enabled.** The owner approved customer-fixed monthly completion:
agreement-anniversary windows in Asia/Kolkata, zero extra grace, no advance/bulk
catch-up, three extension months, calendar AND required-count completion, no benefits,
and full-only settlement. The initial family accumulates exact-grade metal; INR
purchase credit remains a separate gated family, not an in-store cash channel.

Migration `schemes.0024_monthly_completion_schedule` adds explicit nullable policy
fields and frozen `SchemeInstalmentPeriod` snapshots. Existing configurations retain
their prior evidence/digests; no historical agreement gains obligations. Owner draft
creation and read-only previews show month-end-safe windows, on-time/missed scenarios
and review at the extension limit. Internal schedule preparation locks the agreement,
is idempotent and refuses silent repair; it is not exposed as an enrolment bypass.
`check_instalment_schedules` checks snapshots without writing or judging payment compliance.

**FW-PLAN-004 remains in progress.** P2b must add cross-channel reservations, verified
payment attribution, corrections and auditable outage/late-capture handling. Existing
`paid_at` records local confirmation, not necessarily provider capture; no inferred
payment-time evidence is used. Monthly initiation stays explicitly blocked, including
for synthetic configured agreements. P3 eligibility, B full-only settlement and P4
publication acceptance remain incomplete. Preview forecasts do not grant eligibility.
Existing-style enrolment/payment behaviour is unchanged. No normal local DB migration,
environment change, commit, push or production operation occurred in this turn.

Validation: **601 full serial regression tests passed** with a test-process-only fast
password hasher; **15 final focused tests passed** with normal password hashing,
including separate-connection schedule preparation and actual 0023→0024 preservation.
Django checks, migration-drift and diff checks passed. These used disposable local
PostgreSQL test databases, not production. Exact-image PostgreSQL 18.6, CI and browser/
mobile visual acceptance remain pending. Changes remain uncommitted on
`agent/plan-agreement-governance`.

**FW-PLAN-003 P1b contract integration implemented locally (23 October 2026), still gated.**
Migration `schemes.0023_configured_agreement_terms` adds nullable configuration evidence
to agreements/requests and an optional agreement amount increment. Existing rows remain
unconfigured with no new restrictions or inferred customer consent. Customer-fixed
selection resolves to exact FIXED individual snapshots, while legacy variable preferences
remain variable. Both application approval routes now pass their reviewed selection and
configuration evidence; the owner form carries an attestation/version token for future
configured offers. Revision/confirmation evidence includes the configuration version.

Shared amount validation enforces fixed amounts and variable increments for online and
in-store cash; configured snapshots/dates are immutable through model saves and checked
against their recorded configuration, not today's plan. Integrity checks distinguish a
legitimate individual fixed selection from the draft's variable compatibility projection.
Configured redemption explicitly fails closed until B implements full-only settlement.

**No configured offer is enabled.** The database publication gate and enrolment-service
gate remain, without a DEBUG/environment bypass. Tests persist synthetic configured
agreements directly on disposable test databases to exercise these contract rules; they
do not claim a released end-to-end configured customer journey. P1 activation acceptance
remains open until B and the owner publishing workflow are ready. No normal local DB
migration, environment change, commit, push or production deployment occurred.

At the P1b handoff, explicit period/due/grace/catch-up/extension choices awaited owner
approval. The approved first policy and P2a progress are recorded above. Keep
PR/visual/exact-image release acceptance separate from local implementation.

Validation: **587 full serial tests passed** with a test-process-only fast password
hasher. The initial **97 focused tests** passed; the final **18 focused tests** passed
without a process-wide hasher override, covering contract/payment rules, approval
selection propagation and actual 0022→0023 migration preservation. Django checks,
migration-drift and diff checks passed. Test databases were disposable local PostgreSQL
16.1 databases. No production-equivalent image/PG18.6 rehearsal or mobile visual
acceptance is claimed. Changes remain uncommitted on `agent/plan-agreement-governance`.

**FW-PLAN-003 P1a implemented locally (22 October 2026), not deployed.** Owner-only
configuration catalogue, immutable family versions, locked successor creation,
validated amount policies/limits/increments, read-only selected-amount previews and
reuse in audited preparation-only plans are implemented on the existing
`agent/plan-agreement-governance` worktree. No user work was discarded or stashed again.
Migration `schemes.0022_plan_configuration_foundation` is additive: existing plans have
no configuration assigned and existing agreement/financial records are not rewritten.

At the P1a handoff, **P1 was not complete.** P1a previewed the exact terms for a
customer-fixed amount; it does not persist that selection into a customer agreement or
enable a new payment path. P1b integration is recorded above. New configured plans remain blocked from activation/publication
by a database constraint and from enrolment by the service until full-only settlement
and agreement integration are implemented. There is no environment toggle to bypass
this boundary. Existing-style plans still work as before, including the currently
implemented date-based eligibility/partial-redemption behavior. Scheduled obligations,
benefits, full-only/early settlement and customer-authored proposals are not delivered here.

Owner entry point: **Scheme plans → Configuration catalogue**. The catalogue supports
calendar-metal/no-benefit preparation only; unsupported policy values fail validation.
`check_plan_configurations` checks definitions, draft projections/revision evidence and
the no-activation/no-configured-agreements boundary without changing records.
Validation: **34 focused tests passed** with normal password hashing, including actual
0020→0021 and 0021→0022 schema rehearsals and separate-connection version/enrolment
serialization. **570 full serial tests passed** with a test-process-only fast password
hasher. Django checks, migration-drift and diff checks passed. These ran on disposable
local PostgreSQL 16.1 test databases, not production; exact-image PostgreSQL 18.6 and
desktop/mobile visual acceptance remain pending. No normal local database migration,
environment edit, commit, push or production change occurred in this implementation turn.

**Owner-led configurable plan builder design approved (22 October 2026).** The owner
confirmed the six dimensions (amount, accumulation, schedule, eligibility, missed-payment
consequences and benefits) and **no partial redemption**. Owner creation/reuse of valid
configurations is immediate scope; customer-authored proposals are explicitly deferred.
ADR-0017 and the canonical roadmap now specify compatibility/publication gates,
agreement snapshots, scheduled obligations, separate benefit qualification/fulfilment,
full-only settlement and closure, historical protections and acceptance scenarios.

The preceding design follow-up changed documentation only. It preserved the local Phase A
implementation below. No builder, paid-instalment eligibility, benefit formula or
full-only enforcement was added; current code still permits date-eligible partial
redemptions. Migration 0021 does not implement those policies. Plan/configuration
foundation and customer-fixed amounts (`FW-PLAN-003`) were the next implementation slice,
followed by instalments/eligibility/benefits, full closure B, owner publication UI and
separately accepted anytime variants. No production/database/environment changes,
commit or push in this design follow-up; prior test evidence below belongs to Phase A,
not to unimplemented builder rules.
Documentation consistency/diff checks and Django system checks passed for this
follow-up. The financial regression suite was not rerun for documentation-only edits;
future implementation acceptance is specified in TESTING.md, not claimed complete.

**Plan/agreement governance A implemented locally (22 October 2026), not deployed.**
Branch: `agent/plan-agreement-governance`. The owner approved A before B after the
plan/agreement audit. A now includes locked audited plan mutations, stale-form
rejection, immutable revision evidence, read-only plan admin, stable agreement
name/code, recorded-term explanations and corrected longer-agreement discontinuation
copy. Existing date-based eligibility, financial snapshots and redemption restrictions
remain unchanged. No twelve-paid-instalment requirement or new benefit is introduced.

Migration `schemes.0021_plan_agreement_governance` adds metadata only. Old agreement
names/codes are frozen as currently observed legacy display identity, with no invented
historical accepted revision. New enrolments reload/lock the plan and record its
revision alongside existing individual snapshots. `check_plan_agreements` provides a
read-only integrity check. Phase B (requests, unused cancellation, full early jewellery
settlement and correction safeguards) is planned, **not implemented**; track A/B under
`FW-PLAN-001` / `FW-PLAN-002`, MVP_PLAN.md and ADR-0017.

Validation: full serial suite **552 tests passed** using a test-process-only fast
password hasher; Django checks, migration-drift and diff checks passed. Actual 0020-to-
0021 migration and separate-connection edit/enrolment serialization are covered on
disposable local PostgreSQL 16.1 databases. The initial 46 focused regressions also
passed with the normal password hasher. The final **16 focused governance/migration
tests passed** with the normal hasher after the decimal-normalization review.
Owner mobile/desktop visual acceptance, PR/CI and
exact-image rehearsal against production's PostgreSQL version remain release gates.
No normal development database migration, production mutation, outbound email/payment,
GitHub push or new release occurred in this work.

Clean-start preservation: prior deployment documentation was saved separately in local
commit `ec9b15d` on `agent/ui-rollout-evidence-20261022`. Seven user-authored untracked
reference documents were saved in named stash
`2a8e2a333510baab37355fbf1fd0f46d9444f229` (initially `stash@{0}`), not deleted.
The feature branch began with an empty porcelain status. Retain that stash until the
owner chooses to restore the notes; none of their content was included in feature work.

**Bounded production image cleanup completed (22 October 2026).** Owner-authorized
housekeeping removed only 13 explicitly inventoried obsolete GHCR image downloads
from `172.235.9.77`, using exact references without force. Each was unused by any
container and its immutable manifest was available in GHCR before removal. Disk use
fell from **80% to 60%**, with available space rising from **4.7 GiB to 9.3 GiB**
(approximately 4.6 GiB reclaimed). Docker image count fell from 36 to 23.

Retained current digest `5aa95b72...`, designated rollback `d40c2875...`, and an
additional previous registry image `4f07a2b4...`; also retained Caddy and all older
locally built images. Both existing containers and both Caddy volumes remained in
place without restart. No database, environment, credentials, media, logs or backup
was removed. Public live/readiness still return healthy release `4d92b575`; the
production worktree is clean. Removed digest references are recorded in the host's
restricted `/home/deploy/jsk-rollout-4d92b575-20261022/image-cleanup.json` and can be
pulled again while GHCR retains them. No blanket prune or automatic cleanup job was
introduced; the production guide now documents bounded image housekeeping.

**Production rollout completed (22 October 2026).** Deployed approved release
`4d92b57588d0714eb2e9b48661df1878824953d0` to `172.235.9.77`, using
`ghcr.io/rajeshr188/jsk-savings@sha256:5aa95b72241952740f4d787808b1a448b4d075d98d8824c1d8f443e49b4d2074`.
Both www/apex health checks return the new release; web is healthy and Caddy is
running. No build ran on the serving host. Accounts 0007/0008 and pages 0002 applied
successfully. A temporary proxy mutation guard blocked user submissions while
exempting Razorpay webhook/confirmation routes; it was removed after verification.
Normal operations are restored. The production Git checkout is clean at the approved
merge commit. Existing reminder/background jobs were not reconfigured.

Preflight and deployed auth, payment operations, financial exceptions, Razorpay live
readiness, graded metal, in-store cash, registration, enrolment-request and Google-login
checks passed. The pre/post financial-record digest is identical:
`ce358a1b50c7e8e3c22db2ddaa77167b0325002fb7459dfe2c157745d8babc78`.
The compared snapshot includes agreements, contributions, allocations, rates,
redemptions/reversals, cash receipts/reversals, audits, webhook events and payment
controls/schedules. Counts remained 13 customers, 12 agreements, 19 contributions,
9 allocations, 28 rates and 23 webhook events; pending Razorpay remained zero.
Recorded allocations remained GOLD_22K_916 2.361172 g and GOLD_24K_9999 0.329272 g.
These are preserved allocation totals, not a claim that all historical test balances
are live liabilities. No real payment, customer approval, invitation or email was
created as a deployment test.

Homepage/plans/login, manifest, assetlinks and six homepage static assets returned
200; signed-out owner/customer pages redirected to login. Synthetic probes confirmed
query/Referer/Hx-Current-Url redaction and private application-path exclusion in the
actual Caddy logs, plus application secret-path redaction. This does not certify an
external log archive or new provider delivery. Authenticated production visual and
business acceptance remains an owner follow-up; earlier local role acceptance stands.

Environment edits were limited to APP_IMAGE, APP_RELEASE, keeping
PUBLIC_FUNNEL_MEASUREMENT_ENABLED=False, and setting
PUBLIC_REGISTRATION_PRIVACY_VERSION=2026-10-05 to match the released notice.
Terms version and provider credentials/settings were preserved. Existing HSTS
include-subdomains/preload warnings were intentionally not changed. Legacy expired
registration/enrolment requests remain operator review work, not deployment-created
integrity errors. Post-rollout capacity: 348 MiB available RAM, 417 MiB free swap,
4.7 GiB free disk (80% used); bounded old-image housekeeping is a follow-up, not an
automatic destructive prune.

Rollback image remains
`ghcr.io/rajeshr188/jsk-savings@sha256:d40c2875fd9ac6b42fb9f21528b392456151232ce0d0f5ecd3f40dd040ddc543`
(release `b349a84fdc716a87e85110386868923fad95326e`). Restricted rollback configuration
and baseline evidence are retained on the host in
`/home/deploy/jsk-rollout-4d92b575-20261022/`; its environment backup is secret material,
must not be committed, and was not downloaded. Keep additive migrations and financial
history; do not restore an old database or resume old approval code for linked new
applications. The owner-nominated recovery point remains 22 October 2026 13:00 IST.

**Controlled production rollout approved (22 October 2026).** The owner explicitly
accepted the simpler CI + exact-image local rehearsal + controlled-production
approach, including production deployment, and deferred separate staging to
`FW-PROD-009`. External staging is not falsely marked passed. Rollout is completed above;
the previous staging/approval gates below describe earlier checkpoints.

**Exact published-image PostgreSQL 18.6 rehearsal passed (22 October 2026).**
The owner explicitly pinned the deployment destination to Linode
`ubuntu-in-maa-jsk`, IP `172.235.9.77`, serving
`www.jaishrikrishnajewellery.com` (the prepared proxy redirects www to the apex).
Read-only SSH to that IP reports OS hostname `localhost`; this is not independent
verification of the Cloud Manager instance label. The www readiness check and
running containers still report healthy release `b349a84fdc716a87e85110386868923fad95326e`.
The owner nominated **22 October 2026, 13:00 IST / 07:30 UTC** as the managed
PostgreSQL recovery point. This is owner-supplied evidence, not an independently
verified latest PITR timestamp or a new completed restore drill.

Locally pulled the exact CI-published application digest
`sha256:5aa95b72241952740f4d787808b1a448b4d075d98d8824c1d8f443e49b4d2074`;
its OCI revision matches `4d92b57588d0714eb2e9b48661df1878824953d0`.
The disposable PostgreSQL image was
`postgres@sha256:edb0c08dc33befd0262ab3b5cf1c4f3f8cfd8b09e88c05b45adee29d6761ddb6`,
and SQL reported **18.6**, matching the inspected production server version.
The database used network-none and temporary memory-backed storage. Application
containers shared only that isolated namespace, ran read-only/non-root with dropped
capabilities, and used fictional fixtures, in-memory email and synthetic payment
credentials. No production environment file, data or credentials were used.

Dump/restore baseline hashes matched. The only pending migrations were
accounts.0007, accounts.0008 and pages.0002; all applied without changing historical
identity/financial rows. Eight owner pages, historical customer statements, four
owner fragments, permission checks, separate INR/gold/silver entitlements, changed-offer
reconfirmation, repeat-safe approval, mail-failure recovery and activation continuation
passed. Activation created no payment; five integrity commands and Django checks passed.
The prepared Caddyfile also validates in the exact deployed Caddy 2.11.4 digest with
networking disabled. Temporary databases, dump and container were removed successfully;
ignored rehearsal helpers remain in `.uv-cache/release-pg18-20261022/`.

Production remains unchanged. Separate staging, sanitized-backup rehearsal,
external provider/log-sink acceptance have **not** been completed by this local test.
Before cutover, resolve the runbook's external-staging gate explicitly: provision an
agreed isolated target, or obtain an owner-accepted, documented release-specific
exception with a controlled production rollout. Deployment authorization is not
being treated as implicit acceptance of unperformed checks.

**Approved release merges completed (22 October 2026).** PR #74 merged as
`dc029fcc164942002795b46df742ce0453b44e3d`. PR #75 was retargeted to `main`, marked
ready, and updated with the new base using a merge commit. Its updated head
`6c287ab75667ac31aaeabed19b78449978350913` has exactly the same source tree as the
reviewed `b61d324` candidate. Both fresh CI runs passed Django and container/security
checks before the protected merge; no administrator bypass was used. PR #75 merged as
`4d92b57588d0714eb2e9b48661df1878824953d0`.

The merge-readiness review reran 104 focused application, activation, workspace,
payment-presentation and funnel regressions locally: all passed in 27.759 seconds.
Django checks, migration drift and diff whitespace checks passed. Post-merge CI run
[`39766104681`](https://github.com/rajeshr188/jsk-ss/actions/runs/39766104681)
passed Django tests/checks, image publication and the fixable-critical scan of the
published digest. The immutable staging candidate for release
`4d92b57588d0714eb2e9b48661df1878824953d0` is
`ghcr.io/rajeshr188/jsk-savings@sha256:5aa95b72241952740f4d787808b1a448b4d075d98d8824c1d8f443e49b4d2074`.
Production is unchanged. The staging target,
target-specific rehearsal and separate production approval
remain open; approval to merge did not authorize deployment or production data changes.

**Read-only Linode discovery (22 October 2026).** Owner-authorized SSH checks verified
the running release is `b349a84fdc716a87e85110386868923fad95326e`, on image
`ghcr.io/rajeshr188/jsk-savings@sha256:d40c2875fd9ac6b42fb9f21528b392456151232ce0d0f5ecd3f40dd040ddc543`.
The web container and both public health endpoints are healthy on that release;
financial exceptions report zero paid-unallocated, failed-webhook and mismatched-webhook
records. `SHOW server_version` returned **18.6**; the Linode
`postgres-jsk` console independently displays PostgreSQL v18.6. Previous CI/local
PostgreSQL 16 rehearsal evidence is not a same-major-version rehearsal. Production
has accounts through 0006, pages through 0001 and schemes through 0020 applied.
Only the production web/Caddy containers are running on the inspected host; no
separate staging environment was established by these checks. Capacity at inspection:
349 MiB available RAM, 353 MiB free swap, 5.2 GiB free disk (78% used).
The managed database Backups UI offers newest-full-plus-incremental recovery and
describes a 14-day PITR window, but shows no exact latest recovery timestamp. No
timestamp or completed restore is inferred from that option. No production files,
credentials, migrations, services, backups or infrastructure were changed.

**Pre-merge release candidate record (22 October 2026).** Draft UI PR
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
