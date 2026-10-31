# Production and Deployment Guide

This is the canonical production runbook for the Jai Sri Krishna Jewellery
Savings Scheme. It covers the current Django 6, PostgreSQL, Gunicorn, WhiteNoise,
explicit Razorpay Test/Live modes, and manually published Scheme Rate build. Development setup remains in the
[README](../README.md); business invariants remain in [Domain rules](DOMAIN_RULES.md).

## Production-readiness boundary

### First configured enrolment acceptance - 29 October 2026

After the owner completed the customer journey, read-only checks verified agreement
**JSK-958ABDE4 / ID 14**, ACTIVE, against plan **MC22K-5000-12M**, immutable offer
revision **2** and configuration **1/v1**, agreement schema 2. The accepted contract
has fixed **INR 5,000**, **GOLD_22K_916**, **12** qualifying calendar-month payments
AND **12** months minimum. Matching disclosure consent (`2026-09-04`), retained owner
decision and one enrolment audit validate. This records retained consent, not a claim
that every public policy revision date was changed by this release.

All **15** frozen periods validate: 12 originals plus three ordinary replacements.
First period **29 October-31 October 2026**, exclusive end 1 November. Duration
floor **29 October 2027**; completing the original payment windows earlier does
not override that floor. Current progress is NO_ENTITLEMENT, zero qualifying
payments, not eligible. Enrolment itself is not a rate lock, payment or allocation.

Compared with the publication baseline, only SchemeAccount (13 to 14),
SchemeEnrolmentRequest (4 to 5) and SchemeInstalmentPeriod (0 to 15) changed. The
other **43** compared model snapshots, legacy offers and separate liabilities
match. The new agreement has zero contributions, allocations, payment webhooks,
INR/cash receipts and redemptions. Configuration/agreement, instalment schedule/
payment ledger, enrolment request, financial exception, graded-rate and live
Razorpay commands all pass. The schedule command's historical
`payment_attribution=not_released` label is not an activation verdict: its scope is
period integrity; the separate payment-ledger command reports the live intake
flag and zero integrity errors. No feature flag or financial record was changed
by these read-only checks.

Protected evidence in the activation directory below:
`first-enrolment.json`, `first-enrolment-baseline-comparison.json`, and
`first-enrolment-check_*.txt`. Customer reports enrolment success; email inbox
delivery was not independently rechecked. Controlled activation/enrolment acceptance
is complete. Recommend initial observation through **5 November 2026**, then review
operator/customer friction. This schedules no job and requires no new payment.
Preserve this production agreement through the normal lifecycle even though the
owner calls the customer journey a test; no record deletion or silent backdating.

### Configured intake activation and first offer publication - 29 October 2026

**Current runtime state: `CONFIGURED_PLANS_ENABLED=True`.** The owner approved the
prepared offer unchanged and explicitly authorized intake/publication. This
supersedes the disabled-first deployment instruction in the historical checkpoint
below; it is not approval to publish other drafts or enrol an unspecified customer.

Kept release `8f3ba5ad0000a3645f69eddf63607436f91720a8` and digest
`e9c126344938846b0e991644958265804317417636305447e364d99d10b75834` on
`172.235.9.77`. Verified the sole configured draft, zero configured agreements,
environment/image identity and the disabled flag as the sole publication blocker.
Captured protected baseline hashes/environment, changed only the intake flag,
validated Compose, recreated web using `--no-build --pull never --no-deps`, waited
for healthy, validated Caddy and recreated Caddy. No build, pull or migration ran.
Certificate-validated origin/public live/ready checks return the expected release.

Through the authenticated owner's **Review and publish** form, published only
**plan 3 / MC22K-5000-12M / 22K Monthly Jewellery Savings**, retaining configuration
**1/v1**. The confirmed audit reason records the owner's exact approval and all
contract boundaries. Immutable **publication revision 2 (ID 2)** and **SCHEME_CHANGE
audit 118** were appended at **29 October 2026 15:32:25 IST**. Plan 3 is active/listed;
public `/plans/` returns 200 with the fixed INR 5,000 offer, 22K grade, required
monthly terms and application CTA. Existing plans remain unchanged.

All **46** compared scheme-model record hashes/counts, all legacy offer fields and
separate liabilities match before activation and after publication: **13 legacy
agreements, zero configured agreements**, 22K **2.576623 g**, 24K **0.329272 g**,
silver **0.000000 g**, zero legacy cash/bonus and INR purchase-credit liability.
Plan configuration/agreement, financial exceptions, graded rates, live Razorpay,
INR principal and payment-operation checks pass. All grades remain OPEN; pending
orders remain zero. Both checkout-reconciliation and reminder timers remain active;
their services report Result=success / ExecMainStatus=0. One Python-client public
TLS timeout was followed by passing certificate-validated IPv4 curl health probes;
no security/DNS setting was changed. Activation/publication created no customer agreement, payment,
refund, rate, allocation or customer message.

Evidence is retained only on the host at
`/home/deploy/jsk-rollouts/20261029T100052Z-configured-intake` (mode 700): baseline,
after-enable/after-publication snapshots, public listing, revision/audit evidence,
check outputs and environment-before backup (mode 600). Never publish its environment
backup. Next: one genuine customer application and approved enrolment, checking its
frozen contract without payment. Do not invent a production test customer.

If intake needs suspension, disable `CONFIGURED_PLANS_ENABLED` and recreate web
on this compatible image, then validate/recreate Caddy and verify health. The flag
hides configured offers from public/intake selectors without changing their stored
publication status or existing agreements' payment/settlement rights; withdraw a
specific offer through its audited publication workflow if needed.
Preserve appended history; do not reverse migrations or restore old data to undo
publication. The pre-builder image remains unsuitable over configured records.

### Builder v1 production rollout - 29 October 2026; configured intake disabled

PR #77 merged as `8f3ba5ad0000a3645f69eddf63607436f91720a8` after reviewed-head CI
`40799459905` passed all 1,492 tests and build/security checks. The merge tree equals
tested head `46c7fd8`. Main CI `40818256991` passed and published
`ghcr.io/rajeshr188/jsk-savings@sha256:e9c126344938846b0e991644958265804317417636305447e364d99d10b75834`.
The exact-image PostgreSQL 18.6 upgrade, complete retained-history restore, guarded
downgrade, forward reapplication and application live/ready rehearsal passed (TESTING.md).
The dated foundation sections below retain their historical
implementation boundaries; the current release state is tracked in MVP_PLAN.md.

During that initial disabled-first rollout, `CONFIGURED_PLANS_ENABLED=False` was
explicitly retained in the production file; the later approved activation above
records the current value.
This switch governs new configured publication/enrolment, not existing agreement
payment/settlement rights. Do not run migrations or enable offers from this merge
record alone. The selected recovery strategy is forward with compatible application
code and retained database history. The old pre-builder image is not approved over
new configured records; never reverse migrations or restore an older database merely
to erase subsequent financial activity. Restoring a managed recovery point requires
incident review and reconciliation of changes after that point.

Before rollout, `/opt/jsk/app` on `172.235.9.77` was healthy at
release `d0e5dd1897debb054d99647d6ea16575d08b1a48`, image
`ghcr.io/rajeshr188/jsk-savings@sha256:00caf93dfa3933cc662f39745c4a3bd823768b523a73163d71bb60c474e0ec6d`.
It uses PostgreSQL 18.6. The prior image is retained for evidence; it is not a
compatible rollback authorization over new configured records.

The owner confirmed **29 October 2026 10:00 AM IST** is available and approved this
exact digest-pinned rollout with configured intake disabled. This is owner-confirmed
provider evidence, not an independent backup-console inspection by the agent.
Deployment checks passed with the existing HSTS scope/preload warnings. The operator
stopped both timer/service pairs through sudo; automation recorded the owner-approved
payment pause through the audited service, confirmed zero pending orders, stopped
web and captured original-field hashes across 20 existing scheme models. All **39
migrations** applied successfully through schemes.0057, including accounts.0009 and
both merge nodes. Original hashes, counts and separate liabilities matched afterward
and again against the running candidate. No existing financial record was rewritten.

| Production baseline retained | Value |
| --- | ---: |
| Customers / agreements | 15 / 13 |
| Pending Razorpay orders | 0 |
| Legacy cash principal / earned bonus | INR 0.00 / INR 0.00 |
| 22K gold / 24K gold | 2.576623 g / 0.329272 g |
| Silver | 0.000000 g |
| New INR purchase-credit liability | INR 0.00 |

Web runs the exact digest above and is healthy; no pending migrations remain.
Caddy validated and was recreated. Public live/ready/homepage returned HTTP 200
with the expected release; anonymous owner plans/configurations/manual routes return
302 to login. All plan/configuration/agreement, instalment, benefit, INR, closure,
optional-order, financial, live-readiness, graded-metal, in-store-cash and auth/email
checks passed. Registration/enrolment/Google integrity checks also passed. The
original payment controls were restored through the audited service: all grades OPEN.
Configured intake is false with zero configured offers/agreements. Existing intake
flags were preserved. Both timers are active again, future runs scheduled, last
service Result=success and ExecMainStatus=0. No new build or live transaction was used
for acceptance. Final capacity: 358 MiB available RAM and 8.2 GB disk free (65% used).

One operational exception remains: deletion checks report **three overdue owner
reviews**, all structural counters zero. The old image's same read-only check returns
the identical backlog; review these through the owner workflow rather than clearing
them to obtain a green command. An initial Python-client public health request was
rejected by Cloudflare; normal-browser-user-agent public and direct-origin probes
passed. No Cloudflare policy was weakened.

Protected host evidence is `/home/deploy/jsk-rollouts/20261029-8f3ba5a` (mode 700):
`migration-plan.txt`, `migrate.log`, original/running baseline hashes, control snapshot
and original environment backup (mode 600). The temporary candidate environment copy
was removed. Do not publish environment files. New configured offer activation is
a subsequent controlled decision. No build runs on the 1 GB serving Linode.
The accepted local exact-image rehearsal applies; separate staging remains deferred
under FW-PROD-009. No new real payment/refund or duplicate inbox/device ceremony is
required merely to repeat already accepted unchanged workflows.

### Captured-payment comparison and refund handoff (27 October 2026; local acceptance)

From **Exception queue → Review recovery**, use **Check provider** and compare the
latest retained payment/order IDs, INR amount, currency and captured state with the
local contribution. GET performs no provider call. Confirm and Apply with the same
owner login within ten minutes. The signed form binds that owner, event, latest
attempt and local payment facts. Newer failed/mismatched attempts, changed facts or
expired reviews require another check. Apply independently fetches provider state
and validates under existing financial locks; preview is never spending authority.
Owner authority is reloaded before I/O and before credit. Cross-linked event records
are held for INR and metal. New provider-error attempts retain a safe explanation,
not a raw provider error payload.

| Observed case | Operator action and acceptance evidence |
| --- | --- |
| Exact captured payment, matching pending contribution | Check, confirm and apply. Verify one principal receipt OR exact-grade allocation and one confirmed contribution. INR API confirmation alone does not qualify monthly timing; retain the original signed capture evidence. |
| Repeat delivery or retry of the same credited payment | Inspect again if needed. Original source/entitlement remains singular; never create a second contribution or invoice benefit. |
| Different captured payment on a credited order; abandoned/failed/unknown/mismatched source; late funds after disposition | Keep the event unresolved. Investigate exact payment and existing entitlement. Do not relabel the source, reopen the agreement or conceal the exception in ordinary settlement. |
| No local entitlement and an approved payment-error refund | Use the existing authorized manual provider-dashboard process. Retain payment/order/refund IDs, exact amount, approver, timestamps and final completion evidence in the incident record. Submitted is not completed. On the reviewed candidate, open the separate manual payment-refund review, inspect and confirm the exact fully refunded never-credited payment. Confirming resolution does not release an order: use the separate all-attempt order review and confirmation if retirement is needed. Other or contradictory events remain held. |
| Recorded INR purchase credit and agreed final settlement | Use the separate customer-authorized full INR disposition. Fulfil each original-source refund leg only after actual completion with required references/customer receipt evidence. Remaining legs stay liabilities and prevent closure; no bonus cashout or cash substitution for online sources. |

An exception note or refund screenshot cannot clear a financial hold. No refund API,
generic refund-status editor, manual-clear action or new fallback route is introduced.
Exact-grade metal is not converted into an INR refund. Missing signed capture events
require provider retry/support investigation, not a hand-created webhook. Validate
these cases on synthetic/isolated provider fixtures, never manufactured Live errors.

The private refund screens and bounded services are locally implemented, separate
from INR settlement fulfilment; this does not assert production deployment. Payment
resolution and order retirement are separately confirmed, owner/route-bound reviews
with a ten-minute lifetime and independent provider reinspection. GET only reads
retained evidence. Use Refund review history after an item leaves the queue; preserve
original webhook and source records. Provider processed status is not independent
proof of customer bank credit. Candidate operator/device acceptance, normal CI and
exact-image rehearsal are still required.

### Optional order investigation workspace (27 October 2026; not activated)

The owner exception queue now exposes durable optional-contribution requests without
a provider binding, including unexpired or locally failed attempts. The diagnostic
`check_financial_exceptions` reports `unresolved_optional_orders` and counts these
separately from expired checkouts, avoiding duplicate alerts for the same request.
Required-monthly recovery remains in the instalment period workspace.

Use **Unresolved order identity → Investigate order identity**. Locate the original
`opt_…` receipt in the correct Live merchant account/support, enter its candidate
order ID and investigation references, and submit for authenticated identity matching.
GET does not contact Razorpay. Only an active persisted owner can bind an exact match;
the service rechecks authority after provider I/O. Successful retries do not duplicate
evidence. Original deadlines, rate locks and financial entitlements are unchanged.

Recovery is reconciliation-only. Follow the expired-checkout workflow for a fresh
provider-backed untouched-order decision, or the existing capture exception/recovery
workflow when funds exist. No exact identity, an empty search or unavailable provider
means keep the case unresolved and escalate; do not clear rows or retry creation.
This workspace cannot cancel a provider order, renew checkout, issue a refund or
record principal/metal. No migration or activation change accompanies it.

Candidate acceptance still requires the complete uncertain/late/duplicate capture
and refund procedure, physical-device/inbox review, normal CI and exact-image
rehearsal. This closes the local optional-identity interface gap only.

### INR API capture evidence (0044; not activated)

`schemes.0044_inr_api_capture_evidence` adds immutable minimal authenticated API
capture observations and a third exclusive principal source. No historical receipts,
amounts, dates or signed timing are backfilled. Callback and owner recovery are
service-level integrations behind unchanged runtime gates; keep configured plans
disabled. This is not an instruction to deploy or activate INR offers.

Reverse migration refuses retained API observations before changing the schema.
Use compatible forward recovery; never delete evidence or run older code unable to
read API-backed principal. In the separately approved exact-image rehearsal, verify
`check_inr_principal` and the existing financial checks, callback/recovery atomicity,
signed-timing separation and original-source refund proofs. No provider refund API,
automatic recovery task or new owner recovery interface is introduced.

### Optional online request evidence (0043; not activated)

`schemes.0043_optional_payment_order_evidence` adds immutable optional order intents
and response/recovery bindings. It backfills no historical contribution and changes
no balance, rate or deadline. Keep configured-plan readiness gates closed; this is
not an instruction to deploy or activate incomplete schema-2 families.

Include `python manage.py check_optional_payment_orders` in the eventual exact-image
rehearsal. It is read-only and makes no provider calls. `status=review` identifies
unbound requests/unstarted pending attempts, not permission to delete them or blindly
retry. Integrity errors fail the command. Owner recovery requires exact authenticated
provider correlation; recovered orders are not resumable checkout. No optional owner
recovery UI or automatic recovery task is supplied by this development increment.

Reverse migration refuses once any optional request exists, including an uncertain
request without a bound order. Preserve evidence and use compatible forward recovery.
Never run an older application over these requests to retry provider creation.

### Independent contribution frequency (0042; not activated)

`schemes.0042_contribution_independent_frequency` adds the `ONCE_PER_PERIOD` model
choice for future independent contribution records. The accounting month remains a
calendar key; required reservations/optional cash receipt windows enforce the agreed
basis. No existing row, balance, period or legacy uniqueness constraint is rewritten.
Keep configured-plan readiness gates closed. Actual INR cash and required-monthly
online service tests are not optional-online/callback/recovery or full builder acceptance.
Rehearse the accumulated migration chain only as part of a separately approved release;
do not downgrade application code over independent agreements/receipts.

### INR verified-source system provenance (0041; not activated)

`schemes.0041_inr_system_receipts` makes only the INR principal receipt's human actor
nullable and restricts this shape to a captured-webhook source labelled
`system:razorpay-capture`. Existing owner receipts are unchanged. It does not enable
INR collection or configured plans; retain `CONFIGURED_PLANS_ENABLED=False` during
builder development. Rehearse on a disposable database and inspect `migrate --plan`
before any separately approved release. Reversal is refused while system receipts
exist: preserve financial history and use compatible forward recovery, never assign
a fictional human actor to make a downgrade succeed. The verified-source hooks do not
complete callback/API recovery, collection, eligibility or final builder acceptance.

### Independent agreement storage (0040; not activated)

`schemes.0040_independent_agreement_storage` preserves legacy accounts as storage
version 1 and adds explicit eligibility/count snapshots for future version-2 agreements.
Only version 2 can have a short duration or null duration/date for count-only/anytime.
No new agreement, instalment, balance, benefit or customer consent is generated.
Before eventual exact-image rehearsal, verify that no accounts already point at a
policy-schema-2 configuration: the forward preflight refuses such unversioned records
rather than converting their frozen terms implicitly. Review any such records explicitly;
do not bypass the preflight or relabel them with SQL to make migration succeed.

Reverse migration refuses when any version-2 agreement exists, even unused. Older
application code assumes non-null calendar dates and cannot interpret these contracts;
use compatible forward recovery once they exist. Retain all prior INR-history guards.
Keep configured-plan activation disabled. This is local storage preparation, not a
production deployment instruction; the normal local/production databases were not migrated.

### INR correction foundation (0039; not activated)

`schemes.0039_inr_settlement_corrections` retains resolution/physical-return records
and a linear replacement-proposal chain. Existing proposals become unretired roots;
no balances are rewritten and no provider action runs. This is a local internal
foundation, not permission to enable INR enrolment or deploy the accumulated work.
Rehearse the full pending chain and run `check_inr_principal` and
`check_scheme_closures` against the exact eventual image. Source/history drift fails
closed. All-retired histories awaiting replacement remain contained liabilities.

The reverse guard refuses to remove any correction, return or replacement evidence.
Old code assumes one proposal and ignores restored liability: do not roll application
code back over retained correction history. Use compatible forward recovery, preserving
all records. No ordinary local or production migration ran during implementation.

### INR manual settlement foundation (0038; not activated)

`schemes.0038_inr_manual_settlement` adds immutable full-disposition proposals,
manual jewellery/refund fulfilments and completion links. It changes no old balances
and performs no provider operations. Rehearse the entire pending migration chain in
the eventual exact-image release; no ordinary local/production migration ran here.
Keep configured-plan activation disabled. `check_inr_principal` now reports settlement
errors, remaining principal and pending refund amounts; an error means totals need
review, not permission to erase or rewrite evidence. `status=ok` is not activation.

Reverse migration refuses to drop any proposal/fulfilment/completion history. Older
code that ignores fulfilment debits is not a safe rollback after such records exist;
retain schema and history and use compatible forward recovery. The 0039 correction
foundation builds on this migration; runtime enrolment/payment and owner/customer
interfaces remain release gates.

### INR principal foundation (0037; not activated)

`schemes.0037_inr_principal_foundation` adds principal receipt/correction tables and
the distinct future `INR_CREDIT` account denomination. It backfills no balances,
relabels no old accounts, and does not activate payment, enrolment or settlement.
Keep the configured-plan release gate disabled. Include the complete pending chain
through 0037 in eventual exact-image migration rehearsal, not just the newest file.
After migration, `python manage.py check_inr_principal` is a read-only ledger-evidence
check; `workflow=not_activated` is intentional and `status=ok` is not release readiness.
No ordinary local/production migration ran during this implementation step.

If any INR contracts/receipts/corrections exist, 0037 reverse migration refuses to
drop them. Old code cannot safely interpret the denomination. Preserve the schema,
source records and liabilities and use a compatible forward fix; never delete evidence
or relabel INR credit as legacy CASH to force a rollback. No production activation is
approved by these local tests or by an owner recording a synthetic test fixture.

### Independent policy persistence (0036; local only)

`schemes.0036_independent_policy_fields` follows 0035. Existing configurations retain
policy schema 1, old values and serialized evidence. New schema-2 records have separate
duration/count/benefit terms and are preparation-only; no offers, payments, agreements
or entitlements are created by this migration. Keep `CONFIGURED_PLANS_ENABLED=False`.
Include 0036 in the eventual exact-image restored-database rehearsal and run
`python manage.py check_plan_configurations` after the schema is present.
No ordinary local or production migration was run for this implementation step.

Once schema-2 records exist, reverse migration deliberately refuses to remove their
contract evidence. Old code also cannot safely interpret those records. Preserve the
schema and use a compatible forward fix; do not delete contracts to force rollback.
This is not deployment approval or activation of INR, benefits or new eligibility.

### P4 controlled configured offers — local integration, gate remains off

Calendar extension `schemes.0035_calendar_month_instalments` now follows 0034 in
the local candidate. It expands the supported new configuration basis without
backfilling or reinterpreting any existing configuration, agreement or period.
Include 0035 in exact-image migration rehearsal and verify the short-first-month
disclosure, India-midnight attribution, minimum-duration floor, completion reminders
and full settlement. `CONFIGURED_PLANS_ENABLED` remains disabled until approved.
After creating any calendar-month configuration, do not reverse 0035 or roll back
to code that only validates anniversary configurations. Use a compatible forward
fix or a separately approved, data-aware recovery procedure; never relabel existing
calendar agreements to force an old image to accept them.

Migration `schemes.0034_configured_plan_publication` adds a nullable protected
publication revision and replaces the preparation-only constraint with a requirement
for publication evidence. No offers activate and no existing agreements or financial
records are converted. Keep `CONFIGURED_PLANS_ENABLED=False` during disabled-first
rehearsal and until explicit release approval; neither `.env` nor production was
enabled as part of this implementation.

Before any approved release, rehearse the entire 0021–0035 chain with the exact image
on a disposable restored database; review financial/grade/provider/closure baselines
and `python manage.py check_plan_configurations`. Do not build on the serving host.
Complete owner/mobile/keyboard offer-to-closure review and outstanding B4 exception
acceptance. Use only exact-grade, no-benefit calendar or approved monthly-completion
offers. An operator enabling the gate does not itself publish a draft: an owner must
review and publish through **Scheme plans → Publication review**, with a reason.

Disabling the gate hides configured offers and blocks new publication/intake/enrolment.
Withdrawal remains possible. This is NOT a financial kill switch: existing agreements
retain payment, instalment and full-closure rights. Use payment operations controls
for a payment pause. Withdraw before editing a published offer; policy changes need a
new configuration/draft. Never rewrite existing accepted terms or invent customer consent.
After any configured enrolment, do not reverse 0034 or downgrade to code that rejects
or ignores these contracts. Preserve schema/evidence and use a compatible recovery image.

### B3 full settlement — local implementation, not activation approval

Migration `schemes.0033_configured_full_settlement` creates immutable typed settlement/
correction proof and extends closure/status constraints, without backfill or financial
rewrites. Rehearse 0021–0033 against a disposable restored database and the exact approved
image before a future authorized release. Run `check_scheme_closures`, financial,
exact-grade, configuration, instalment and existing provider integrity checks.

Configured publication/enrolment remains blocked. Verify owner/customer/statement UI,
full six-decimal fulfilment, stale/duplicate submissions and reversal containment.
Failed/abandoned/Test/mock histories and unresolved payment/outage evidence are not
settleable in this version; don't delete records or change statuses to bypass holds.
Legacy partial-settlement rights require an inventory and separate cutover decision.

Once configured SETTLE/REVERSE evidence exists, don't downgrade to code that ignores it,
reverse 0033, delete evidence or restore an older database to undo a settlement. Preserve
schema and sources; pause new initiation and use a reviewed compatible recovery image.
A business reversal is the explicit audited workflow, not an infrastructure rollback.
After settlement, keep running both closure and financial/provider checks: a later
unexpected provider capture may require investigation even when remaining metal is zero.
Do not suppress the event, reopen contributions or mutate the completed invoice to
make a check green. Use the retained exception and separately authorized disposition.

### B2 unused cancellation — local, configured-only preparation

Migration `schemes.0032_unused_agreement_cancellation` extends closure action/status
constraints and adds configured-only agreement cancellation. No backfill or automatic
cancellation; no financial rows are changed. Rehearse the full 0021–0032 chain with the
exact approved image against a disposable restored database before any authorized
release. Run `check_scheme_closures` plus financial, configuration and instalment checks.
Configured publication/enrolment remains blocked; B3 is local-only as described above.

Once CANCEL evidence exists, older application code may misclassify cancelled agreements
as active. Do not roll back to such code or reverse 0032 with cancellation records present.
Preserve the schema, events and status, pause initiation/reminders and use a reviewed
compatible recovery image. Never delete cancellation evidence or restore an old database
to undo a closure. Owner/mobile acceptance and the B3/B4 release review remain outstanding.

### B1 closure lifecycle — local, configured-only preparation

Migration `schemes.0031_scheme_closure_lifecycle` creates empty request/event tables
and constraints. No backfill, legacy conversion or financial changes. It does not
implement unused cancellation or full settlement. Do not activate configured plans
or deploy this accumulated branch merely because migration generation/tests succeed.
Rehearse the complete 0021–0031 chain with the exact approved image against a disposable
restored database before a later authorized release; use `check_scheme_closures`
alongside existing financial/instalment checks. Zero integrity errors do not establish
resolved provider exposure or permission to cancel an agreement.

Once accepted requests exist, do not roll back to code that ignores closure payment
guards: that could reopen payment collection. Pause initiation and reminder dispatch
before any incompatible rollback and retain the schema/evidence. Never delete requests,
events or restore an old database to undo acceptance. Existing captures and allocation
recovery must remain operational. No new environment bypass is supplied.

### P3 monthly completion reminders — local, gated preparation

Migration `schemes.0030_monthly_completion_reminders` extends existing reminder
kind/shape constraints and choices. It performs no financial or message-data backfill.
Do not deploy it independently of the accepted P3/configured-plan release boundary.
Configured publication/enrolment and full-only settlement remain disabled.

For a future approved rollout, rehearse 0021–0030 against the exact candidate image
and a disposable restored database, including preservation of legacy reminders and
attempts. Pause reminder dispatch while versions/schema are mixed; then preview
`send_scheme_reminders` without `--apply`, check candidate kinds/dates/recipients, and
use a controlled approved recipient before resuming the timer. Do not create real
payments or synthetic obligations merely to manufacture notification evidence.
The command now reports `skipped`: state/date/recipient/switch changes can make a
planned candidate unsafe before delivery. Skips create no SMTP attempt; existing
failed or accepted attempt evidence is retained. Monthly notices are count-complete
progress notices, not forecasts, eligibility grants or settlement instructions.
They reuse configured lead days and have no automatic missed-day catch-up. A
confirmed historical `--as-of` override still cannot replay monthly qualification.

Retain 0030 and its historical monthly reminder rows on rollback; do not reverse
the constraint migration once such rows exist or delete them to fit an older schema.
Keep dispatch paused when reverting to code that does not understand the new kind.
Account locking prevents concurrent financial mutations during dispatch, but SMTP
acceptance cannot commit atomically with PostgreSQL. Investigate crash-window mail
duplicates rather than claiming exactly-once delivery. No deployment was performed
for this local preparation step.
Dispatch holds only one agreement per email, not the whole batch. It can briefly
delay a concurrent payment on that agreement; retain the bounded `EMAIL_TIMEOUT`
(default 10 seconds) and inspect SMTP failures before increasing it.

### Capture containment P2b.3b — local acceptance preparation only

No additional migration beyond 0029. Unresolved Live captured events for configured
monthly agreements now block new online/cash initiation and owner timing acceptance;
confirmation of independently verified in-flight funds continues. A second payment
for an already-paid order retains the original credit and records DUPLICATE_CAPTURE_REVIEW.
Owner instalment pages link retained exceptions to existing provider reconciliation.

`check_instalment_payments` now reports `unresolved_capture_events`. Check it separately
from `integrity_errors`: structurally valid evidence can still require financial
disposition. Neither investigation notes nor a manually reported refund clear this
hold. Do not edit event status to bypass it. Automated refunds/verified refund closure
are not delivered by this step; keep unresolved cases in the established manual
provider process. See ADR-0017's disposition matrix. Configured publication/enrolment
stays blocked. Owner/mobile, CI and exact-image acceptance remain outstanding; this
section is not permission to deploy, migrate an ordinary DB or create real test funds.

### Lost-order identity recovery P2b.3b — partial, preparation only

Migration `schemes.0029_instalment_order_recovery` adds a nullable unique request UUID
to payment decisions and an empty immutable identity-recovery table. It does not
backfill old requests or change historical orders, money, rates, deadlines or agreements.
New configured monthly requests carry their durable UUID in the provider receipt/notes.
The private owner instalment workspace links ORDERING cases to exact-order recovery.
Use only a candidate ID obtained from the correct Live merchant investigation; the
server verifies it independently. Missing/mismatched evidence remains held.

Recovered checkout is never resumed. Reconcile captured funds separately; an existing
unknown-order webhook in review requires explicit payment recovery before original
signed timing can qualify it. For expired untouched orders, use existing provider-backed
abandonment, not a database edit or replacement retry. `check_instalment_payments`
reports `recovered_orders` and `uncorrelated_order_requests`; neither a successful binding
nor zero integrity errors completes the exception/eligibility/settlement gates.
No normal local/production migration, activation or deployment is authorized here.

### Bounded outage amendments P2b.3b — partial, preparation only

Migration `schemes.0028_instalment_outage_resolutions` adds an empty immutable
resolution/amendment table, with no existing agreement, schedule, configuration hash
or financial backfill. The owner review workspace links each open hold to an
acknowledged resolution form. Maximum three extra anniversary months per agreement,
separate from ordinary extensions; original terms are retained. Customer acceptance
must be genuinely obtained and retained outside this form; do not manufacture test
consent or production agreements. No uncertain provider order can be released here.

After the schema exists, `check_instalment_schedules` validates base plus acknowledged
windows; `check_instalment_payments` reports open held accounts, resolutions and
compensation months. Zero errors do not grant eligibility or close unresolved holds.
Configured publication/enrolment remains blocked. External disposition/closure, final
exception acceptance, P3 and full-only settlement remain open. Local test success does
not authorize normal local/production migration, deployment or activation.

### Owner instalment review P2b.3a — preparation only

Migration `schemes.0027_instalment_owner_reviews` adds an empty append-only owner-review
table and payment-decision source link, without historical attribution. The owner
workspace is `/scheme/owner/instalment-reviews/`; it should have no monthly periods
until an independently approved configured-enrolment release. Do not create production
test agreements to populate it. `check_instalment_payments` additionally reports owner
reviews and outage-held accounts. A zero-integrity-error result does not clear a hold.
No arbitrary hold removal, timing override or uncertain-order release is provided.
P2b.3b owner/CI/release acceptance, P3 and full settlement remain open; capture
containment is not a verified refund-closure workflow.
Normal DB migration, production deployment, owner visual acceptance, CI and exact-image
PostgreSQL 18.6 rehearsal are not authorized by local test success.

### Monthly payment-service integration P2b.2 — not an activation release

Migration `schemes.0026_instalment_payment_integration` extends qualification lifecycle
constraints with awaiting timing, provider-reconciled release, and non-occupying late
capture review; decisions retain the reconciliation audit FK. Existing legacy payment
rows and agreements are not reinterpreted. Run `check_instalment_payments` only after
the schema exists. Current P4 diagnostics report `integration=gated_services` and
`configured_intake_enabled=true|false` from the release flag, replacing the P2-era
hard-coded `activation=disabled`. The closure check uses the same intake flag; it
does not describe whether existing agreements may accept payments or settle.
Configured enrolment/publication remains blocked. Do not manufacture production
agreements or use internal calls as an activation bypass. P2b.3 exception resolution,
P3 eligibility and B full settlement remain unfinished. Migration rehearsal, exact-image
PG18.6 and separately approved rollout are still required; this is not deployment approval.

### Instalment payment ledger P2b.1 — internal foundation only

Migration `schemes.0025_instalment_payment_ledger` adds empty reservation/decision
tables and constraints. It has no financial or qualification backfill. P2b.1 was an
internal foundation; P2b.2 service integration is described above. Publication and
enrolment gates remain closed. Do not invoke internal services on production to bypass them.
`check_instalment_payments` is read-only and explicitly reports activation disabled.
Before activation, both reservation and decision counts should remain zero. A successful
check is not rollout acceptance. Exact-image/PG18.6 rehearsal and separately approved
deployment remain necessary; no ordinary local or production migration is authorized here.

### Monthly schedule foundation P2a — preparation only

Migration `schemes.0024_monthly_completion_schedule` adds nullable policy fields and
an empty period snapshot table; it does not create obligations for existing agreements.
Approved monthly-completion definitions stay inactive/unlisted and cannot enrol or
initiate payments. No bypass flag exists. `check_instalment_schedules` is read-only;
before activation there should be zero monthly agreements/periods in production.
Do not call internal preparation services to manufacture production agreements.
Complete P2b attribution/reservations/exceptions, P3 eligibility and B settlement before
activating the family. An original calendar `paid_at` value is not capture-time evidence.
Migration/schema rehearsal, exact-image PostgreSQL validation and rollout approval
remain required; this development entry does not authorize deployment or DB rollback.

### Configured agreement integration P1b — activation remains blocked

Migration `schemes.0023_configured_agreement_terms` adds nullable agreement/request
configuration references and an optional agreement contribution increment. It has no
data backfill: preserve every legacy amount, date, grade, status and financial row.
The database gate on configured plan visibility/activity remains and the enrolment
service still rejects configured plans. Do not remove that constraint, forge agreements
via SQL or patch settings to test with customers. Full-only settlement is not released.

For any separately approved release, run `check_plan_agreements` and
`check_plan_configurations`; the latter must still report zero configured agreements.
Preserve schema and evidence on rollback. Synthetic contract tests are not proof of an
enabled customer journey; exact-image rehearsal, visual review and later full-lifecycle
acceptance remain required. No migration/deployment is authorized by this runbook update.

### Configuration preparation P1a — not activation authorization

`schemes.0022_plan_configuration_foundation` follows 0021. It adds immutable typed
configuration versions and an optional pinned configuration on plans; it does not
backfill configurations onto existing plans or mutate agreements/payments. New pinned
plans are inactive/unlisted by database constraint and rejected by enrolment services.
There is no environment flag to unlock them. P1a alone supports amount previews;
P1b adds gated agreement integration above. Full-only settlement is still separate work.

After a separately approved release/migration, run `check_plan_configurations` and
`check_plan_agreements` alongside normal integrity checks. Require zero activated
configured plans and zero configured agreements. Inspect **Scheme plans → Configuration
catalogue** as owner; customers must not access it. Do not remove the database gate or
enable drafts via SQL. Preserve configuration/revision evidence; rollback to code that
does not understand these drafts is not an activation path. No production rollout or
normal local-database migration was performed during this implementation slice.

### Plan governance A — prepared change, not deployment authorization

The subsequently approved owner plan builder/full-only settlement design in ADR-0017
is **not implemented by this release**. Do not advertise instalment-completion plans,
automatic benefits or anytime/full-only processing merely after applying 0021. Those
families need their own implementation, migration review, historical-contract checks,
integrity/acceptance tests and explicit activation. Customer-authored configurations
remain out of immediate scope. Current code still permits date-eligible partial settlement.

`schemes.0021_plan_agreement_governance` adds revision/identity metadata. Its data
migration freezes each legacy agreement's currently observed plan name/code and leaves
its revision null; it must not change economic snapshots, eligibility, grades or any
financial ledger record. Review the migration on a local synthetic PostgreSQL upgrade
before CI/image publication. Capture legacy agreement fields before/after and retain
the exact old image/configuration and a verified current managed-database recovery point.

For an approved future rollout, temporarily restrict owner plan edits and new enrolment
mutations while migrating and switching web code, so old workers cannot insert an
agreement without identity metadata. Preserve payment/webhook handling. Never build
on the 1 GB serving host. Check `check_plan_agreements`, health and existing financial,
grade, authentication and application checks after rollout. New enrolments should have
identity/revision evidence; legacy records should remain explicitly legacy. No feature
flag changes or early-discontinuation activation are part of A.

Review the updated Terms/Cancellation copy and advance the applicable terms/consent
version for future confirmations before enabling new applications; retain historical
consent records. No privacy-policy change is implied. Rollback must not reverse the
schema or discard new revisions; old code could create unsnapshotted agreements, so
keep enrolment/plan mutations restricted until a compatible recovery image is ready.

### Approved simpler rollout — 22 October 2026

The owner approved deploying release `4d92b57588d0714eb2e9b48661df1878824953d0`
without separate staging, after CI/security checks and the exact published-image
synthetic restore/upgrade rehearsal on PostgreSQL 18.6. This explicit exception
supersedes the separate-staging prerequisite for this release only; it does not
claim external staging/provider/log-sink acceptance. Track separate staging under
`FW-PROD-009`. Do not provision another stack on the 1 GB production host.

Target: owner-identified `ubuntu-in-maa-jsk`, `172.235.9.77`, serving www/apex
jaishrikrishnajewellery.com. Recovery point nominated by owner: 22 October 2026,
13:00 IST (07:30 UTC), not independently verified as latest PITR. Use only the
CI-published digest in STATUS.md; never build on the serving host.

Retain the old image/configuration, check current capacity and financial state,
temporarily restrict user mutations while preserving payment confirmation/webhooks,
review the exact migration plan, apply only approved additive migrations, and
verify health/private-route controls/static assets and financial invariants before
reopening normal operations. Preserve existing provider credentials and feature
settings; keep optional funnel measurement disabled. Do not reverse migrations or
restore an older financial database as routine rollback. Once linked plan-first
records exist, old identity-only approval must not resume; prefer a forward fix.

### Bounded production image housekeeping

After an accepted release, inspect `df -h /`, `docker system df`, all containers
(including stopped containers), and full image references. Preserve every image
referenced by a container, the running application, the designated rollback image,
and Caddy. Retaining one additional recent registry release is inexpensive insurance;
image retention alone does not establish database/workflow rollback compatibility.

Remove only explicitly inventoried obsolete references using `docker image rm`
without force, after checking their immutable manifests remain available in GHCR.
Recheck container references immediately before removal. Retain an image-reference
inventory so a removed download can be pulled again if the registry retains it.
Keep locally built images unless their recovery/disposal is separately reviewed.
Never use a blanket `docker system prune -a --volumes`; volumes, database CA files,
environment/rollback backups, Caddy certificate data and logs are not image cleanup.
Recheck disk space, container identities and public live/readiness after cleanup;
no application restart is needed. Do not build on the serving host.

### Prepared workflow refinement release (22 October 2026)

This is a local review candidate, not production authorization. No new migration, environment
setting, feature activation or financial backfill is needed for this refinement. Earlier pending
Phase 1/3/4 migrations remain combined release dependencies; follow their sections below.

1. Review the code/static-asset diff and regression/browser evidence in STATUS.md. Build the
   immutable application image with normal collectstatic; confirm the pinned local HTMX asset,
   project enhancement script and styles are present. The upstream 2.0.11 license is included;
   its official SHA-384 is checked during acquisition and included in the script tag.
2. Rehearse both roles on restored staging with desktop/mobile and JavaScript disabled. Check
   Today readiness, customer context/sections, search/page/review return, filtered list vs CSV,
   receipt/statement navigation, legacy cash access and pending-payment blockers. Never make
   a genuine financial mutation simply to test navigation. Keep existing feature switches and
   financial safeguards unchanged.
3. Include deploy/Caddyfile in the separately approved proxy release: it now strips query strings,
   Referer and Hx-Current-Url from access logs, retaining existing secret-route exclusions/IP
   masking. Validate with the actual pinned runtime before reload. The prepared configuration
   passes local validation in the existing caddy:2-alpine image with networking disabled. Verify
   synthetic search/return/header redaction in staging logs and the external log sink. A local
   loopback-only responder already confirms query/header stripping; no production
   logging configuration was changed here. Keep Gunicorn full-path access logging disabled.
4. Verify normal GET/full-page fallback, no-store/Vary responses and expired-session full login
   navigation for all five fragment routes (Customers, Applications, Contributions, Exceptions
   and customer payment status). Check stage counts, category/order, exact-customer privacy
   history/review return, six progress milestones and Test/practice print labels. Search must cancel stale results; pagination must
   retain scope and keyboard focus. A manual status refresh only reads recorded server state;
   it never contacts Razorpay, creates an order or retries payment. No automatic polling is enabled.
5. After owner approval, deploy and record scoped acceptance. Roll back the application image
   and corresponding collected assets if necessary; there is no refinement schema rollback.
   Retain query/header redaction when rolling back UI assets. Restore a prior proxy configuration
   only if needed to recover a failed configuration, preserving equivalent privacy controls.
   Do not roll back historical financial/identity records. Postmark/SES and Tamil publication remain
   separate work; neither is changed by this release.

### Synthetic local workflow upgrade rehearsal (22 October 2026)

The repeatable local preparation is:

```powershell
uv --cache-dir .uv-cache run --no-sync --env-file .env python -m schemes.rehearse_workflow_release --synthetic-local
```

Requires PostgreSQL clients on PATH and CREATE DATABASE permission on explicit loopback
PostgreSQL. The module accepts only --synthetic-local: it has no existing-database or backup
argument. It uses the local connection credentials to create two random empty databases;
it never dumps, migrates, restores or seeds the configured application database. Non-loopback
hosts and connection-option overrides are refused. PostgreSQL tools receive exact local
hosts/database names; Python outbound network calls are blocked. Email stays in memory,
provider keys are synthetic Test values, and no web server or scheduled task is started.
Only exact names successfully created by the invocation can be cleaned up, in finally;
the generated synthetic dump and temporary databases are removed on success or failure.

The synthetic predecessor has accounts through 0006, schemes through 0020, and pages through
0001. This is an explicit test baseline, not an inventory of the deployed production schema.
Observed pending upgrade: accounts.0007 plan applications, accounts.0008 invitation recovery,
and pages.0002 aggregate funnel counts. No new refinement/rehearsal migration is introduced.
The drill checks unchanged historical rows, separate cash/gold/silver liabilities, existing
customer/history access, owner permissions/fragments, renewed offer consent, repeat-safe
approval, recoverable mail failure, replacement activation and plan continuation. It does not
create a provider order or treat activation as payment. See STATUS.md for run evidence.

Before external staging, confirm the hostname/access method and who owns the isolated database,
record the exact candidate image digest and actual migration plan, and use an approved sanitized
backup with provenance/time. Do not copy raw production PII merely to inspect UI. Disable public
intake/outbound providers/jobs until the controlled staging workflow is ready; use separate
secrets and the existing Test Mode acceptance procedure for any later sandbox payment.
Rehearse the exact image/static manifest/proxy and browser flows, including JavaScript disabled,
HTMX session/error recovery, query/token redaction at every actual log sink, operational checks
and image rollback. Use the participant task/evidence protocol in TESTING.md. The local drill
cannot close these external checks, provider delivery or participant acceptance.

Local stakeholder acceptance is recorded: the owner tested both owner and customer roles and
reported satisfaction on 22 October 2026. A production image and internal-only container
restore/upgrade were verified locally; see the release candidate record below. External staging
target, published/CI-scanned digest and approved sanitized production-backup provenance are
not supplied for this release. Keep those checklist items open. Production deployment
and production data changes still require separate owner approval; no remote resource is created
by running this local drill.

### Accepted UI release candidate (22 October 2026)

The initial image identity below is superseded: PR #75's first security scan found fixable
critical advisories in certifi/Pillow/PyJWT. The release branch updates only those locked
packages to certifi 2026.10.19, Pillow 13.0.0 and PyJWT 2.15.1, with explicit minimum constraints.
Do not promote the original b1607523 image. Replacement local tag is
`jsk-savings:ui-release-20261022-rc-f57a8bb44665`, image ID
`sha256:4052110e1e50d1ad674a79e027bc91d832a6da1c66095a975f50ffd39e2a743a`.
Read [PR #75 checks](https://github.com/rajeshr188/jsk-ss/pull/75/checks) for the current-head
CI/security conclusion before progressing. Production is unchanged. See STATUS.md for gates.

The accepted code fingerprint is
`03ece8a68849506f012217c2ccfe2a95f982b0a27d251760586966b905814c40`.
Local build tag: `jsk-savings:ui-release-20261022-03ece8a68849`.
Local image ID: `sha256:b160752354552a928b4d0a0e3e017a146b3807e9f624a0ebc32b0b6eb5404ddb`.
These identify the local rehearsal only. Do not use the local image ID as a GHCR manifest digest.
The build used unchanged Dockerfile/uv.lock, Python 3.12, production static collection and a
curated source context excluding local secrets and unrelated notes. Evidence/manifest is in
`.uv-cache/ui-release-20261022/`; Git retains the reviewed source and canonical runbook.

The same image passed internal-network PostgreSQL 16 dump/restore, additive migration and
legacy/new workflow checks under the runtime read-only/non-root restrictions. Actual Gunicorn
readiness/liveness and hashed static HTTP responses passed. No ports were published and no
provider delivery/capture, actual R2 access or live account action was attempted. Caddy validates
locally; the existing local redaction probe does not replace checks at the actual edge/log sink.

Release progression remains:

1. Review the separate UI release branch and its stacked foundation dependency; leave Google
   Play PR #74 unchanged. Run the existing CI workflow and fixable-critical vulnerability gate.
2. Record the reviewed merged commit and CI-published GHCR manifest digest. Promote that exact
   image through staging; do not label the local build as CI-scanned or rebuild independently
   for production. Record the actual migration plan, backup provenance, current feature flags,
   operational/payment availability and previous compatible image before requesting rollout.
3. Rehearse the exact published image and prepared Caddy config on an agreed isolated staging
   target. Check secure cookies/CSRF, normal and enhanced flows, JS-disabled browser fallback,
   actual query/token/header redaction and external log sinks. Check providers using the existing
   controlled Test acceptance procedure; no artificial live payment is authorized.
4. Present that concrete digest, CI/staging evidence, migrations and rollback target to the
   owner for separate production deployment/data-change approval. Local role satisfaction is
   not that approval. Keep Postmark and existing switches unchanged unless separately requested.
5. Prefer a forward fix or disabling intake for recovery. Retain application/confirmation,
   invitation and financial evidence; never reverse the conversion migrations to roll back UI.
   Old identity-only approval code is unsafe for linked plan-first records; suspend review if
   forced to recover with an older application image. Do not restore an older financial database.

There is no new UX refinement/rehearsal migration. Earlier conversion migrations accounts.0007,
accounts.0008 and pages.0002 remain conditional on the actual target's migration inventory.
The local synthetic baseline is not proof those migrations are pending on production.

### Pending customer conversion Phases 1–2 release (5 October 2026)

This section prepares a local change for review; it does not authorize deployment,
production migrations, feature activation or edits to production plan records.

1. Review the image/code diff and normal release gates. The only new migration is
   `pages.0002_publicfunneldailycount`: an empty aggregate measurement table with
   day/stage/count constraints. It performs no data migration and touches no customer
   or financial table. Review `migrate --plan`; do not apply unrelated pending vendor
   migrations as part of this change. After approval, the bounded migration command
   is `python manage.py migrate pages 0002_publicfunneldailycount --noinput`.
2. Keep `PUBLIC_FUNNEL_MEASUREMENT_ENABLED=False` through cutover. Verify home/plans,
   selected-plan entry, disabled-feature fallbacks and existing login/request routes.
   The revised privacy notice is dated 5 October 2026. Review it and set
   `PUBLIC_REGISTRATION_PRIVACY_VERSION=2026-10-05` for new registration evidence
   during the approved release; explicit environment values override the code
   default. Do not rewrite previously accepted policy versions or change the
   separate deletion/terms versions as part of this notice amendment.
   When the schema and policy text are accepted, the owner may separately approve
   `PUBLIC_FUNNEL_MEASUREMENT_ENABLED=True`. No beacon/provider configuration is needed.
   Existing edge analytics injection/exclusion must be checked independently: tokens,
   authentication, customer/owner and payment paths must not leak through that provider.
3. Check mobile/desktop paused/no-rate/month-paid agreement cards, abandoned history,
   private payment-status authorization/no-store, and test-mode uncertain callback
   recovery. Callback/webhook verification stays enabled during initiation pauses.
   No real payment is necessary merely to inspect the status presentation.
4. Read aggregates with `python manage.py report_customer_funnel --start 2026-10-05
   --end 2026-10-05` (enter on one line). Output is JSON totals only. Report dates are
   inclusive India-local dates, at most 366 days. First-payment identity is determined
   across full history, not just the requested period. Outstanding allocation count
   is a current backlog snapshot. Counts are not unique visitors or a joined cohort.
   Navigation history starts at enablement; existing source-record throughput can be
   queried earlier. Manually account for known synthetic application identities.
5. Rollback: disable measurement and return to the prior immutable image. Keep the
   additive aggregate table; no customer/financial history rollback or deletion is
   needed. Public free-text plan descriptions remain stored; this release stops
   displaying them rather than rewriting production content. Cross-email selected
   plan continuity and combined owner approval are Phase 3, not part of this release.

Phase 2 is a code/template/static release and has no additional migration, feature
flag or production data backfill. The Phase 1 aggregate-table migration above is
still required if both phases ship together. After separate release approval,
include collected static assets and smoke-test owner login to `/scheme/owner/today/`,
Applications filters/pages, bounded customer search, historical registration/request
links, inline agreement review and exact-payment exception recovery. Check owner-only
permissions and customer-scoped document navigation with separate identities. No
real agreement approval or provider/payment recovery is needed for a read-only UI
smoke; any such production mutation needs the usual deliberate owner workflow.
Owner sign-in now starts on Today; the previous `/scheme/owner/` financial overview
and historical URLs remain available. Counts may include Test records and multiple
exception records for one payment, as labelled. Rollback restores the earlier image
and static assets; no identity, request, agreement or financial records need rewriting.

Production release `315f836ac0717fbaaf2d8d90268471ac1670e5b1` runs the accepted
Live Razorpay path, provider-backed abandoned-order lifecycle, exact-grade metal
contracts, payment-operations circuit breaker, snapshotted Checkout expiry, and
audited in-store cash contribution channel. This
proves those bounded application controls, but the deployment is **not fully
production-gate complete**:

- The deploy check accepts `test` and `live` only when `RAZORPAY_MODE` agrees with
  the `rzp_test_` or `rzp_live_` key prefix. Missing, unknown, and mixed-mode
  configuration fails closed.
- `FW-PAY-001` Live payment, capture, signed-webhook, allocation, and reconciliation
  acceptance is complete. Refund, dispute, incident, alert, webhook-recovery, and
  credential-rotation controls remain governed by the open items below.
- An owner must publish reviewed gold and silver Scheme Rates before metal
  contributions are enabled in an environment.
- `FW-PROD-001` is complete with the evidenced Linode restore drill recorded below.
  `FW-PROD-002` and `FW-PROD-003` in [Future work](FUTURE_WORK.md) retain the stable
  HTTPS/alerting activation and secret-rotation rehearsal requirements.

The owner deferred paid external monitoring under `FW-PROD-002` on 2026-08-27 to
preserve the operating budget. Existing bounded local logs, health endpoints,
financial-exception checks, and provider consoles remain useful manual controls, but
the deferral does not close the external alerting, retained-log, or escalation gate.

The owner explicitly accepted the remaining operational risk when enabling Live
checkout. Do not interpret that decision as closure of `FW-PROD-002`, `FW-PROD-003`,
or `FW-PAY-003`; use the manual controls in this guide and suspend checkout on any
unreconciled provider/local mismatch.

## Recommended topology

Use a managed container runtime and managed PostgreSQL unless the operator already
has the staff and procedures to run those components safely.

```text
Internet
   |
owned DNS name + TLS edge / load balancer
   |  (overwrites Host and X-Forwarded-Proto)
   v
Django container(s): Gunicorn -> WSGI application
   |        |                 |
   |        |                 +-> stdout logs -> retained log/alert service
   |        +-> WhiteNoise serves versioned static assets from the image
   v
managed PostgreSQL with TLS, snapshots, PITR, and restricted network access

External services: SMTP provider, mode-isolated Razorpay webhook/API
```

The application is stateless between requests except for PostgreSQL. Do not place
the database in the web container. The current application has no user-uploaded
media dependency; if uploads are added later, use durable object storage rather
than a container filesystem.

The checked-in `docker-compose.yml` runs Django's development server and a local
database with development credentials. It is **not** a production deployment file.

## Selected Linode deployment profile

The selected target for this business is:

| Layer | Selected implementation |
| --- | --- |
| Public host | `https://jaishrikrishnajewellery.com` |
| Redirect host | `https://www.jaishrikrishnajewellery.com` redirects to the apex host |
| Compute | One Ubuntu 24.04 LTS Linode Compute Instance running Docker Compose |
| TLS edge | Caddy 2.11.4 with automatic certificate issuance and renewal |
| Application | The approved `jsk-savings` image, private to the Compose network |
| Database | Linode Managed PostgreSQL 16 in the same core region |
| Database transport | CA-verified TLS using `sslmode=verify-full` |

The checked-in [production Compose file](../compose.production.yml),
[environment template](../.env.production.example), and
[Caddyfile](../deploy/Caddyfile) implement this topology. The application container
publishes no host port; only Caddy exposes TCP ports 80 and 443. Caddy ignores
client-supplied `X-Forwarded-*` values and sets `X-Forwarded-Proto`, which is the
required condition for this deployment to enable `TRUST_PROXY_SSL_HEADER=True`.

This single Compute Instance is appropriate for staging and an initial controlled
MVP deployment, but it is not compute-high-availability. A host outage requires
instance recovery. Before availability requirements increase, add a second instance
and a Linode NodeBalancer rather than placing a second proxy on the same host.

### Provision Linode resources

1. Create the Compute Instance and Managed PostgreSQL cluster in the same core
   region. Select PostgreSQL 16, the tested baseline. A single database node costs
   less and is acceptable for staging, but has maintenance/failure downtime. For
   real customer funds, use the available three-node highly available plan unless
   the business explicitly accepts the single-node outage risk.
2. In the database Networking settings, allow only the Compute Instance's exact
   outbound IPv4 and, when used, IPv6 addresses. Do not allow `0.0.0.0/0` or `::/0`.
   Linode clients can prefer IPv6, so the allow-list and chosen connection hostname
   must agree on the protocol being used.
3. Copy the exact host and port and download the database CA certificate from
   Connection Details. Linode Managed
   PostgreSQL requires encrypted connections; this deployment additionally verifies
   the server hostname against that CA.
4. Use the administrative `akmadmin` identity only to create a dedicated application
   role and database. In an interactive `psql` session, use `\password` so the new
   password does not enter shell history:

   ```sql
   CREATE ROLE jsk_app LOGIN;
   \password jsk_app
   CREATE DATABASE jsk_savings OWNER jsk_app;
   ```

5. Configure a Linode Cloud Firewall. Allow TCP 80 and 443 from the internet, allow
   TCP 22 only from the administrator's trusted IP range, and deny other inbound
   traffic. Do not expose ports 8000 or 5432 on the Compute Instance.
6. Point an `A` record for `@` at the Compute Instance IPv4 address and a `CNAME`
   record for `www` at `jaishrikrishnajewellery.com`. Add an `AAAA` record only when
   IPv6 and its firewall rules are ready. Start with a 300-second TTL. DNS may remain
   with the current registrar; moving authoritative DNS to Linode is optional.

As checked on 2026-08-18, the apex currently resolves to `3.33.130.190` and
`15.197.148.33`, returns a small HTTP `/lander` redirect, and does not provide a
usable HTTPS response. This appears to be parking rather than the Django application,
but the domain owner must confirm that replacing those `A` records will not displace
an intended site. Change only the web `A`/`AAAA`/`www` records; preserve existing MX,
TXT, CAA, and other email/domain-verification records unless their owners approve a
separate change.

### Prepare the Compute Instance

Use a named, non-root, sudo-capable deployment account. Keep the existing SSH session
open while testing a new account or firewall rule in a second session. On Ubuntu
24.04, install operating-system updates and the required host tools:

```bash
sudo apt update
sudo apt full-upgrade
sudo apt install -y git curl ca-certificates openssl postgresql-client unattended-upgrades
sudo timedatectl set-timezone UTC
sudo systemctl enable --now unattended-upgrades
```

Install Docker Engine, Buildx, and the Compose plugin from Docker's official Ubuntu
repository rather than the convenience script:

```bash
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
sudo tee /etc/apt/sources.list.d/docker.sources >/dev/null <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker containerd
sudo docker run --rm hello-world
sudo docker compose version
```

Add only the deployment operator to the `docker` group, then log out and back in:

```bash
sudo usermod -aG docker "$USER"
```

Membership in this group is effectively root-level host access. Do not add application
users or general staff. Keep the Linode Cloud Firewall as the public perimeter;
Docker-published ports can bypass uncomplicated host-firewall expectations.

After the approved commit exists on the remote, place an exact detached checkout under
`/opt/jsk`. Replace the example value with the full 40-character approved commit SHA:

```bash
sudo mkdir -p /opt/jsk/app /opt/jsk/secrets
sudo chown -R "$USER":"$USER" /opt/jsk/app
sudo chmod 700 /opt/jsk/secrets
git clone https://github.com/rajeshr188/jsk-ss.git /opt/jsk/app
cd /opt/jsk/app
git fetch --prune origin
export JSK_RELEASE_SHA=FULL_40_CHARACTER_APPROVED_COMMIT_SHA
git checkout --detach "$JSK_RELEASE_SHA"
test "$(git rev-parse HEAD)" = "$JSK_RELEASE_SHA"
cp .env.production.example .env.production
chmod 600 .env.production
```

Transfer the downloaded Linode CA from the administrator workstation to a temporary
host path using `scp`, then install and validate it on the Compute Instance:

```text
scp "C:\path\to\database-ca-certificate.crt" deploy@COMPUTE_IPV4:/tmp/linode-db-ca.crt
```

```bash
sudo install -o root -g root -m 0644 /tmp/linode-db-ca.crt \
  /opt/jsk/secrets/linode-db-ca.crt
sudo openssl x509 -in /opt/jsk/secrets/linode-db-ca.crt \
  -noout -subject -issuer -dates
sudo grep -q "PRIVATE KEY" /opt/jsk/secrets/linode-db-ca.crt \
  && echo "ERROR: private key found" || echo "CA certificate only"
rm /tmp/linode-db-ca.crt
```

The CA is public trust material, not a database credential. It must be readable by
the image's non-root `app` user because Compose implements a file-backed secret as a
bind mount and cannot remap its permissions. Keep `/opt/jsk/secrets` mode `0700`, keep
the database password only in the protected environment/secret store, and set:

```dotenv
LINODE_DB_CA_FILE=/opt/jsk/secrets/linode-db-ca.crt
DATABASE_URL=postgresql://jsk_app:<url-encoded-password>@<managed-host>:<port>/jsk_savings?sslmode=verify-full&sslrootcert=/run/secrets/linode_db_ca.pem
```

The `.crt` host filename and `.pem` container target deliberately differ; both are
PEM-encoded certificate files. Do not replace the managed hostname with its current
IP address because `verify-full` verifies the hostname and failover may change IPs.

Fill `.env.production` locally on the server without printing it into logs. Generate
a new Django signing key, percent-encode reserved database-password characters, and
use fresh Razorpay Test Mode credentials. Credentials previously pasted into chat or
shared in screenshots must be rotated rather than reused. `ACME_EMAIL` must be a real,
syntactically valid, monitored address; a placeholder prevents Caddy from registering
with its certificate authority. Before starting, check for template placeholders
without printing the environment:

```bash
if grep -qE 'replace-with|replace_me' .env.production; then
  echo "ERROR: production placeholders remain"
else
  echo "No template placeholders found"
fi
```

A mode-`600` environment file is a practical single-host staging baseline, not an
audited secret manager. Before financial go-live, select the controlled secret store,
access policy, backup, and rotation process that will be authoritative for these
values; root access to the Compute Instance can read container environment variables.

`APP_IMAGE` must name the approved public GHCR digest and `APP_RELEASE` must name its
matching full merged commit. Pull the digest from the successful protected-`main`
Actions summary and record `docker image inspect` output. Public pull access removes
the need to persist a GitHub credential on the Linode; it does not relax digest,
review, scanning, or release-evidence requirements. Never run an image build on this
serving host.

### Validate and start the Linode deployment

Always pass the production environment explicitly. `config --quiet` validates the
Compose model without printing expanded credentials:

```bash
docker compose --env-file .env.production -f compose.production.yml config --quiet
docker compose --env-file .env.production -f compose.production.yml \
  run --rm --no-deps web python manage.py check --deploy --fail-level ERROR
docker compose --env-file .env.production -f compose.production.yml \
  run --rm --no-deps web python manage.py migrate --plan
docker compose --env-file .env.production -f compose.production.yml \
  run --rm --no-deps web python manage.py migrate --noinput
docker compose --env-file .env.production -f compose.production.yml up -d
```

Caddy starts only after Django's PostgreSQL readiness check succeeds. Once DNS has
propagated and ports 80/443 are reachable, Caddy obtains certificates and redirects
HTTP to HTTPS automatically. Verify:

```bash
curl --fail-with-body https://jaishrikrishnajewellery.com/health/live/
curl --fail-with-body https://jaishrikrishnajewellery.com/health/ready/
curl -I http://jaishrikrishnajewellery.com/
curl -I https://www.jaishrikrishnajewellery.com/
```

Also inspect bounded startup logs. The image disables Gunicorn's unused control
socket because Gunicorn 25.1 and newer otherwise tries to create `$HOME/.gunicorn`
on the deliberately read-only application filesystem:

```bash
docker compose --env-file .env.production -f compose.production.yml logs --tail=100 web
docker compose --env-file .env.production -f compose.production.yml logs --tail=100 caddy
```

If `ACME_EMAIL`, application environment, or another Compose-injected value changes,
`docker compose restart` is insufficient because it retains the old container
environment. Re-run `config --quiet` and use `up -d --force-recreate` for the affected
service.

The first two responses must contain the expected `APP_RELEASE`; HTTP and `www` must
redirect once to the canonical HTTPS origin. Configure Razorpay Test Mode to deliver
`payment.captured` to:

```text
https://jaishrikrishnajewellery.com/scheme/payments/razorpay/webhook/
```

### Linode backup and restore evidence

Linode Managed Databases currently include daily backups retained for 14 days and
support restoration to a forked cluster. Run the first drill before real funds:

1. Select either the newest full backup plus incremental changes or a specific
   recovery time in the database Backups tab and restore it as a new cluster. Record
   which option was exercised. This temporarily incurs charges for both clusters.
2. Add only the isolated verification host to the restored cluster's access list and
   download its CA/connection details.
3. Point a temporary application container at the fork with payment, rate, and email
   providers disabled. Never point public DNS or Razorpay at the restored cluster.
4. Complete the record-count and denomination-specific liability reconciliation in
   this guide, recording achieved RPO and RTO.
5. Preserve the evidence, confirm the original cluster was never modified, and then
   delete the restored fork to stop the additional charge.

Linode's database backup does not replace portable encrypted `pg_dump` exports.
Maintain both controls and test them independently.

#### Completed restore evidence — 2026-08-27

- Restore option: newest full backup plus incremental changes.
- Restore initiated from the newest available state at 13:57 IST; the isolated fork
  finished provisioning at 14:12 IST, for an observed 15-minute RTO.
- The temporary application used the production image/release
  `5fa726b2d76666abe7063f8b48125d6869566ecc`, a fork-specific endpoint and CA, and
  disabled payment and email providers. No public service or migration was started.
- The restored schema contained every migration through
  `schemes.0011_razorpay_gateway_mode`.
- Reconciliation exactly matched the recorded source baseline: five customers, six
  scheme accounts, no pending Razorpay contribution, INR `0.00` cash principal, INR
  `0.00` earned cash bonus, `0.299097` gold grams, and `0.000000` silver grams.
- `check_auth_email_integrity` reported no duplicate groups or blank-email users;
  `check_financial_exceptions` reported zero paid-unallocated contributions and zero
  failed or mismatched webhooks.
- The original production live/readiness endpoints continued returning `ok` with the
  expected release. After evidence capture, the restored fork and its temporary
  environment and CA certificate were removed; the production CA was retained.

### Linode monitoring boundary

The selected baseline is Better Stack for independent HTTPS monitoring, Docker log
retention, incident routing, and the financial-exception heartbeat. Akamai Cloud
Pulse and Cloud Manager remain authoritative for Managed PostgreSQL and Compute
metrics and provider backup events. This split avoids making an application outage
invisible to the system that is supposed to detect it. An equivalent external
service may replace Better Stack only if it supports the same checks, retained logs,
explicit failure heartbeats, escalation, and exercised evidence.

The Compose profile still bounds local Docker logs so a collector outage cannot fill
the host disk. Local rotation is not durable retention. Before sending logs off-host,
approve the data region and retention period. A 30-day searchable window may be
useful for investigation but is not the full preservation period. The 180-day
security-log planning baseline below supersedes any interpretation of 30 days as
sufficient total retention. Logs do not replace immutable financial records.
Caddy access logs mask IPv4 addresses to `/24`, IPv6 addresses to
`/48`, remove user-agent headers, retain the release label, and rely on Caddy's
default credential-header redaction. Request/response bodies, cookies, payment
signatures, and database URLs must never be added.

### Budget-conscious security-log preservation plan (`FW-PROD-007`)

Status on 10 September 2026: **inventory and execution plan documented; no
collector, archive destination, retention change or production cleanup deployed**.
This is a bounded preservation workstream related to `FW-PROD-002`, not acceptance
of external monitoring/alerts. Paid monitoring remains deferred. The earlier
14-day/256-MB journal proposal is withdrawn as a standalone retention policy.

Planning basis: CERT-In Direction (iv) specifies rolling 180-day ICT-log
preservation; FAQ Q25 includes sole proprietorships within the relevant entity
definition. For this business, design for at least 180 days rather than assume an
exemption. This is not a legal compliance certification or a claim that Google Play
specifies 180 days. Review applicable log coverage, access, storage jurisdiction
and incident holds; do not generalize security-log retention to financial records,
email bodies or throttle tables.
[CERT-In directions](https://www.cert-in.org.in/PDF/CERT-In_Directions_70B_28.04.2022.pdf),
[official FAQ](https://www.cert-in.org.in/PDF/FAQs_on_CyberSecurityDirections_May2022.pdf).

#### Source inventory and current evidence

| Source | Observed setup | Preservation gap / next verification |
| --- | --- | --- |
| Django/Gunicorn | Console logging; known sensitive auth paths filtered | Not a universal scrubber, including arbitrary exceptions; audit synthetic error paths and security-event coverage |
| Caddy | JSON stdout, release label, masked IPs, user-agent removed, sensitive auth routes skipped | Preserve secret exclusions; assess safe event metadata for skipped routes and query-string leakage; masked addresses may limit investigation |
| Docker web/Caddy | Owner verified `local`, `max-size=20m`, `max-file=5` | Disk cap only; rotation or container removal can lose the sole copy; no durable export verified |
| Journald | Owner reports 798.2 MB; vendor drop-in sets `ForwardToSyslog=yes`; no explicit age override shown | Capture/export coverage and recoverability untested |
| Rsyslog / host security | Active; local auth/syslog/kernel/mail/UFW/cloud-init destinations; no remote action shown | Identify duplicates; supplied configuration does not rule out other exporting agents/providers |
| Host rotation | Syslog group and UFW weekly/four archives; daily timer triggered and scheduled | Service success unproven; no explicit cloud-init/mail.err match; inspect effective wildcard/include coverage |
| Managed DB / Cloudflare / Postmark | DB backups exist; website Logpush unavailable on Free; Postmark activity reported 45 days | Backups are not DB audit logs; inventory accessible security logs and export/retention options; provider defaults do not establish 180 days |

Repository evidence: `compose.production.yml`, `deploy/Caddyfile`,
`django_project/settings.py`, and `accounts/logging.py`. Host observations are
owner-supplied, not remote agent inspection. Missing historical logs cannot be
recreated; document earliest recoverable coverage and gaps honestly.

#### Proposed design and budget boundary

- Bounded local operational logs plus a separate encrypted, compressed archive;
  no searchable log database on the 1-GB serving host.
- A root-managed, resource-limited host collection/spooling job using supported
  journal/Docker interfaces, not Docker's private binary files. A daily `docker logs`
  snapshot alone can miss rotation and removed containers. Require incremental
  cursors, overlap/deduplication and source-identity handling before claiming continuity.
- Daily archive chunks (sooner for size), with encrypted manifests recording source,
  UTC interval, host/container/release, count, bytes, checksum and gaps. Commit
  checkpoints only after durable capture; acknowledge off-host preservation only
  after verifying the destination copy. A checksum alone does not prove authenticity
  against someone able to rewrite the manifest; require versioning or equivalent
  independently protected evidence.
- Preserve a chunk until at least 180 days after its newest event; retain longer
  under an applicable incident/legal hold. Encrypt before upload, with key recovery
  separate from storage credentials. No raw tokens, cookies, signatures, request
  bodies or environment files. Treat IPs/pseudonymous identifiers as restricted.
  Test synthetic samples before exporting; quarantine unexpected sensitive material
  for controlled handling rather than silently editing incident evidence.
- Destination is **unselected**. Existing business Workspace Drive with encrypted
  archives and independent USB is a reuse candidate, not authorization to upload
  logs there. Confirm capacity, automated access, key recovery, residency/legal
  requirements and retrieval timeliness. A separate private object store is an
  alternative only after a capped cost is approved. Never use the public catalogue
  R2 bucket or public Git/GHCR; do not assume Drive/R2 guarantees an Indian region.
- Daily manual review is not an unattended archive/alert guarantee. Explicitly
  assign log-operations cover and missed-export escalation; the deletion-record
  custody approval does not automatically assign these additional responsibilities.

#### Tracked execution sequence

1. **Inventory (partially complete):** confirm remaining host rotation, provider
   security-log scope, clock synchronization and redaction/event coverage. No purge,
   forced rotation, driver switch or container recreation solely for this audit.
2. **Measure and select (pending):** measure source bytes and compressed daily volume
   over representative days, including a busy day; record resource use. Estimate
   `daily compressed bytes × 180 × 1.5`, plus manifests, spool and independent copies.
   The 1.5 factor is a sizing assumption. Set disk headroom, outage spool, collection/
   upload frequency and budget from measurements. Collect before local rotation can
   lose data; one directory-size snapshot is not a daily growth measurement.
3. **Implement separately (pending):** select destination/access, then bounded
   collection, encryption, manifests, restart-safe checkpoints, retries, failure
   reporting, key recovery and hold-aware expiry. Test with synthetic data locally
   before production changes. Preserve existing logs during cutover; no automatic
   purge in the first rollout. No server-side image builds.
4. **Exercise (pending):** prove capture across restart/rotation/container replacement,
   duplicates/late records, destination outage, disk pressure, corrupt chunks and
   missing keys. Recover a chosen UTC interval independently; verify counts/checksums
   and unauthorized-access denial. Test expiry/holds with synthetic aged chunks,
   not real-log destruction. Record actual rotation-service success separately.
5. **Accept (pending):** owner approves scope/cost/custodians; enable capture in a
   controlled rollout and verify oldest/newest coverage, gaps and resource impact.
   Only then consider shorter local retention where verified archives preserve the
   required period. Do not claim 180 days of history until it actually exists.

Next read-only host checks (share metadata/configuration only, never log bodies):

```bash
sudo systemctl show logrotate.service -p Result -p ExecMainStatus
sudo logrotate --debug /etc/logrotate.conf
timedatectl status
df -h / /var/log
sudo du -sh /var/log/journal
```

`--debug` does not rotate logs or update state. Inspect wildcard coverage, errors
and affected files; redact private configuration details before sharing.
[Logrotate reference](https://man7.org/linux/man-pages/man5/logrotate.conf.5.html).

### Configure Better Stack monitoring and retained logs

This paid-service procedure remains deferred for this pilot; it is not required
for the inventory/measurement stages of `FW-PROD-007`.

1. Create a Better Stack team protected by multi-factor authentication. Name a
   primary incident responder and a backup responder using private operational
   contact details. Do not assume that the public shop support number is an on-call
   number.
2. In **Telemetry -> Sources**, connect a Docker source named `jsk-production`.
   Choose the approved region and retention period, then copy its source token. On
   the Compute Instance, keep the token out of shell history while using Better
   Stack's generated Vector installer:

   ```bash
   read -rsp "Better Stack source token: " JSK_BS_SOURCE_TOKEN
   echo
   curl -fsS \
     "https://telemetry.betterstack.com/setup-vector/docker/${JSK_BS_SOURCE_TOKEN}" \
     -o /tmp/jsk-vector-install.sh
   unset JSK_BS_SOURCE_TOKEN
   less /tmp/jsk-vector-install.sh
   sudo bash /tmp/jsk-vector-install.sh
   rm /tmp/jsk-vector-install.sh
   sudo usermod -aG docker vector
   sudo systemctl restart vector
   sudo systemctl --no-pager --full status vector
   ```

   The generated `/etc/vector` configuration contains ingestion credentials; keep it
   root-controlled and never commit it. In Live tail, confirm both `web` and `edge`
   container logs arrive and that `com.jsk.release`/the Caddy `release` field matches
   the deployed `APP_RELEASE`. Search for a known health request, then verify no
   cookie, authorization header, signature, full webhook body, or unmasked client IP
   is present.
3. Create two HTTP monitors using the production hostname:

   | Monitor | URL | Expected result | Initial timing |
   | --- | --- | --- | --- |
   | `JSK production liveness` | `https://jaishrikrishnajewellery.com/health/live/` | HTTP 200 and body contains `"status": "ok"` | 60-second checks; alert after 2 minutes; recover after 2 minutes |
   | `JSK production readiness` | `https://jaishrikrishnajewellery.com/health/ready/` | HTTP 200 and body contains `"status": "ok"` | 60-second checks; alert after 2 minutes; recover after 2 minutes |

   Do not match a fixed release value because a valid deployment changes it. Enable
   TLS certificate-expiry notification at 14 days and domain-expiry notification at
   30 days on the liveness monitor. Assign the production escalation policy to both.
4. Create a log alert named `JSK sustained edge 5xx`. Use the Caddy access-log schema
   shown in Live tail (parse the JSON `message` first if the collector has not done
   so) and select production `edge` events whose HTTP status is 500 through 599.
   Start with 5 events in 5 minutes and tune only from measured traffic. Include the
   release, status, method, and path in the incident; do not include headers or bodies.
5. Create a heartbeat named `JSK financial exceptions`, expected every 5 minutes
   with a 6-minute grace period for the bounded combined checkout inspection below,
   and assign the production escalation policy (or verify email recipients when
   the account's Free plan notifies the whole team). Store
   its secret URL separately from the application environment:

   ```bash
   sudo install -o root -g root -m 0600 /dev/null \
     /opt/jsk/secrets/observability.env
   sudoedit /opt/jsk/secrets/observability.env
   ```

   The file contains one line and must never be committed or printed:

   ```dotenv
   FINANCIAL_EXCEPTIONS_HEARTBEAT_URL=https://uptime.betterstack.com/api/v1/heartbeat/REPLACE_WITH_SECRET_TOKEN
   ```

   Install the versioned service and timer after each relevant deployment:

   ```bash
   cd /opt/jsk/app
   docker compose --env-file .env.production -f compose.production.yml \
     exec -T web python manage.py check_financial_exceptions
   sudo install -o root -g root -m 0644 \
     deploy/systemd/jsk-financial-exceptions.service \
     /etc/systemd/system/jsk-financial-exceptions.service
   sudo install -o root -g root -m 0644 \
     deploy/systemd/jsk-financial-exceptions.timer \
     /etc/systemd/system/jsk-financial-exceptions.timer
   sudo systemctl daemon-reload
   sudo systemctl enable --now jsk-financial-exceptions.timer
   sudo systemctl start jsk-financial-exceptions.service
   sudo systemctl --no-pager --full status jsk-financial-exceptions.timer
   sudo journalctl -u jsk-financial-exceptions.service -n 30 --no-pager
   ```

   The check reads authoritative database state, emits aggregate counts only, and
   exits non-zero for any unresolved failed webhook or `PAID_UNALLOCATED` payment.
   The wrapper reports `/fail` to the heartbeat and never transmits exception text,
   customer data, or provider IDs. A database, Docker, or app failure also prevents a
   healthy heartbeat.

6. Exercise the heartbeat route without creating or changing a financial record:

   ```bash
   sudo bash -c 'set -a; source /opt/jsk/secrets/observability.env; set +a; \
     /usr/bin/bash /opt/jsk/app/deploy/check-financial-exceptions.sh --test-alert'
   ```

   Confirm the named responder receives and acknowledges the test incident, then
   resolve it in Better Stack. Confirm the next normal timer run returns the
   heartbeat to healthy. This tests delivery, not the owner resolution workflow;
   separately retain the existing paid-unallocated recovery smoke evidence.

### Configure Linode capacity and backup alerts

In Cloud Manager, confirm the account's Read-Write notification recipients include
the named incident responder and subscribe to relevant Akamai status notifications.
Enable Compute Instance CPU, disk-I/O, traffic, and transfer-quota email alerts. Use
measured baselines; an initial CPU threshold is 80% of total core capacity sustained
for 15 minutes.

Managed Database metrics and custom alerts may require Akamai Cloud Pulse access. If
the database Metrics/Alerts pages are unavailable, open a support ticket requesting
access rather than pretending the control exists. Once available, route alerts to
the incident responder and start with warning/critical database disk usage at 75% and
85%, CPU at 80% for 15 minutes, and memory at 85% for 15 minutes. Review the plan's
PostgreSQL connection limit and the application's worker/connection budget alongside
readiness failures; do not infer connection capacity from CPU alone.

Managed PostgreSQL creates daily restore points, but the application cannot verify
provider-owned backup execution. Confirm a fresh restore point in the Backups tab
each day during initial go-live and at least weekly after stability, and ensure any
provider backup/system alert or support ticket reaches the incident responder. A
missed restore point or backup alert immediately marks recovery as degraded. This
notification control complements, but does not complete, the isolated restore drill
in `FW-PROD-001`.

Record screenshots or exported incident timestamps for each test below without
capturing secrets or customer data:

| Evidence | Pass condition |
| --- | --- |
| Liveness and readiness monitor test | Named responder receives, acknowledges, and resolves the test |
| Financial heartbeat `/fail` test | Incident arrives; next clean check recovers |
| Caddy 5xx log alert test | A controlled test event reaches the same escalation route |
| TLS/domain warning test | Monitor shows both checks enabled with the intended lead times |
| Compute/database capacity test | Notification channel and threshold test reaches the responder |
| Backup notification test | A provider test/system notification or documented support confirmation reaches the responder |
| Log retention test | A known release-tagged event remains searchable after local Docker rotation |

Do not mark `FW-PROD-002` complete until every applicable row has an owner, UTC test
time, result, and evidence location. Likewise, select an SMTP provider and prove
password-reset delivery under `FW-PROD-003`; observability does not complete email.

## Deployment responsibilities

Assign named owners before deployment. One person may hold multiple roles, but no
responsibility should be implicit.

| Responsibility | Required outcome |
| --- | --- |
| Release owner | Approves the commit, image digest, migration plan, and rollout |
| Database owner | Confirms backup/PITR status and can perform a restore |
| Domain/TLS owner | Controls DNS, certificates, proxy rules, and HSTS changes |
| Provider owner | Controls SMTP and Razorpay configuration |
| Incident owner | Receives alerts and can disable contributions or roll back |
| Business reconciler | Verifies INR principal/bonus, gold grams, and silver grams separately |

## Platform contract

Any target platform must provide all of the following:

- Linux/amd64 or Linux/arm64 container execution with secrets injected at runtime.
- An immutable image reference, preferably a registry digest as well as a commit tag.
- A stable owned HTTPS hostname and automatic certificate renewal.
- A proxy that rejects unknown hosts and overwrites, rather than merely appends,
  `X-Forwarded-Proto`.
- A one-off release job using the same image and environment as the web service.
- HTTP liveness and readiness probes.
- Graceful process termination with at least 30 seconds for Gunicorn shutdown.
- Retained stdout/stderr logs with searchable release identifiers and external alerts.
- Managed PostgreSQL with encrypted transport, tightly restricted network access
  (private where the provider supports it), automated snapshots, point-in-time
  recovery, and an isolated restore facility.
- A secret manager with access control and audit history.

The container listens on port `8000`, runs as the unprivileged `app` user, and starts:

```text
gunicorn --no-control-socket --bind :8000 --workers 2 --timeout 30 --graceful-timeout 30 \
  --max-requests 1000 --max-requests-jitter 100 \
  --access-logfile - --error-logfile - django_project.wsgi
```

Configure probes as follows:

| Probe | Path | Meaning | Platform behavior |
| --- | --- | --- | --- |
| Liveness | `/health/live/` | Django process can answer | Restart after a sustained failure, not one transient error |
| Readiness | `/health/ready/` | Django can execute `SELECT 1` on PostgreSQL | Remove instance from traffic while status is not `200` |

Both responses set `Cache-Control: no-store` and include the configured
`APP_RELEASE`. Do not expose a database error or secret in either response.

## Provisioning checklist

Provision these resources before the first build is promoted:

1. A private image repository.
2. A managed PostgreSQL database on a supported major version. PostgreSQL 16 is the
   tested baseline. Create a dedicated application database and least-privileged
   application identity; keep administrative credentials out of the web service.
3. Automated database snapshots and point-in-time recovery with documented
   retention. Define and approve the required recovery point objective (RPO) and
   recovery time objective (RTO); do not let a platform default make that decision.
4. Separate staging and production databases, secrets, hostnames, provider keys,
   webhook endpoints, and log destinations. Never clone production customer data
   into staging without an approved sanitization process.
5. An owned DNS name and TLS endpoint.
6. An SMTP or transactional email account with an authorized sender domain.
7. Razorpay Test Mode keys and a separate webhook signing secret.
8. Uptime, error, database, backup, and financial-exception alert destinations.
9. Separate Cloudflare R2 Standard buckets and bucket-scoped credentials for staging
   and production uploaded media. Production also requires an owned media domain.

## Production environment

Store values in the platform secret/configuration manager. Django does not load a
`.env` file by itself, and no production `.env` file should be copied into the image.
Generate the Django key locally with a cryptographically secure generator, for example:

```powershell
uv run python -c "import secrets; print(secrets.token_urlsafe(64))"
```

Use a profile equivalent to the following. Values in angle brackets are placeholders,
not literals:

```dotenv
DJANGO_DEBUG=False
DJANGO_SECRET_KEY=<long-random-production-only-value>
DJANGO_SECRET_KEY_FALLBACKS=
APP_RELEASE=<immutable-commit-or-image-id>

ALLOWED_HOSTS=savings.example.com
CSRF_TRUSTED_ORIGINS=https://savings.example.com
WAGTAILADMIN_BASE_URL=https://savings.example.com
PUBLIC_CATALOGUE_ENABLED=False
PUBLIC_BLOG_ENABLED=False

MEDIA_STORAGE_BACKEND=r2
R2_ACCOUNT_ID=<32-character-cloudflare-account-id>
R2_ACCESS_KEY_ID=<bucket-scoped-access-key-id>
R2_SECRET_ACCESS_KEY=<bucket-scoped-secret-access-key>
R2_BUCKET_NAME=<production-media-bucket>
R2_CUSTOM_DOMAIN=media.savings.example.com
R2_SIGNED_URL_EXPIRY_SECONDS=900

DATABASE_URL=postgresql://<app-user>:<url-encoded-password>@<private-host>:5432/<database>?sslmode=require
DATABASE_CONN_MAX_AGE=60

EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=<smtp-host>
EMAIL_PORT=587
EMAIL_HOST_USER=<smtp-user>
EMAIL_HOST_PASSWORD=<smtp-password>
EMAIL_USE_TLS=True
EMAIL_USE_SSL=False
EMAIL_TIMEOUT=10
DEFAULT_FROM_EMAIL=Jai Sri Krishna Jewellery <noreply@example.com>
SERVER_EMAIL=errors@example.com

CUSTOMER_INVITATION_EXPIRY_HOURS=72
PUBLIC_CUSTOMER_REGISTRATION_ENABLED=False
PUBLIC_REGISTRATION_EMAIL_EXPIRY_HOURS=24
PUBLIC_REGISTRATION_ATTEMPTS_PER_HOUR=5
PUBLIC_REGISTRATION_ATTEMPT_RETENTION_HOURS=24
PUBLIC_REGISTRATION_TERMS_VERSION=2026-09-04
PUBLIC_REGISTRATION_PRIVACY_VERSION=2026-09-04

PAYMENT_GATEWAY=razorpay
RAZORPAY_MODE=test
RAZORPAY_KEY_ID=<rzp_test_key-id>
RAZORPAY_KEY_SECRET=<test-key-secret>
RAZORPAY_WEBHOOK_SECRET=<separate-webhook-secret>
RAZORPAY_TIMEOUT_SECONDS=10
RAZORPAY_CHECKOUT_EXPIRY_MINUTES=10

SECURE_SSL_REDIRECT=True
TRUST_PROXY_SSL_HEADER=True
SECURE_HSTS_SECONDS=3600
SECURE_HSTS_INCLUDE_SUBDOMAINS=False
SECURE_HSTS_PRELOAD=False

LOG_LEVEL=INFO
```

Configuration rules:

- `DJANGO_DEBUG` must be exactly a supported false value such as `False`; never set
  generic `DEBUG`, because this project intentionally ignores it.
- `ALLOWED_HOSTS` contains bare hostnames, not schemes or paths. Do not use `*`.
- `CSRF_TRUSTED_ORIGINS` contains complete HTTPS origins and includes a port only if
  the public origin uses a non-default port.
- `WAGTAILADMIN_BASE_URL` is the public origin used to build absolute CMS links. Do
  not include `/cms/` or a trailing slash.
- `GOOGLE_BUSINESS_PROFILE_URL` is optional public information, not a Google OAuth
  credential. Set it to the exact showroom listing's HTTPS Google Maps/share URL
  only after the stakeholder confirms the name, address, phone, hours, and map pin.
  Do not use a Business Profile management URL or a general address-search URL.
  Blank hides the homepage/footer profile links and Contact review link, and omits
  `sameAs`/`hasMap` from structured data. Google-domain validation checks URL shape,
  not ownership or the destination behind a short link; manually open and verify it.
  The Contact directions link independently uses the published showroom address.
  No Google API key, OAuth permission, review widget, or tracking script is required.
  Add the value to Linode `.env.production`, validate Compose, and recreate `web`
  using the normal immutable-image rollout (then recreate Caddy as documented).
  Verify the links on desktop/mobile and that they open the correct listing.
  Clear the value and recreate to remove profile discovery if the listing is wrong.
  The stakeholder separately adds the canonical website to the Google Business
  Profile; deploying these links does not perform that Google-account change.
  The user-supplied listing inspected on 10 September 2026 is
  `GOOGLE_BUSINESS_PROFILE_URL=https://maps.app.goo.gl/TKpjGNXgNYpiFzDM7`.
  Its name, phone, and 155 Azad Road address match; ask the stakeholder to review
  Google's Ramset Nagar locality label versus Thorapadi on the website and its
  delivery attribute versus showroom-only scheme fulfilment. Do not automatically
  rewrite approved address or fulfilment terms from Google's listing.
  Showroom identity and opening hours are reviewed Django-owned data in
  `pages/business.py`, shared by Contact/home/footer display and the home/Contact
  `JewelryStore` JSON-LD. No guessed coordinates, product prices, stock-photo business
  images, self-serving ratings, or Google endorsement claims are published. After
  deployment, validate the two public URLs with Google's Rich Results Test; optional
  data warnings must not be filled with invented facts, and rich results are not
  guaranteed. See [Google LocalBusiness guidance](https://developers.google.com/search/docs/appearance/structured-data/local-business)
  and [Maps URLs](https://developers.google.com/maps/documentation/urls/get-started).
- Keep `PUBLIC_CATALOGUE_ENABLED=False` through the initial catalogue deployment.
  Change it to `True` only after the catalogue root and reviewed products are live and
  their direct public URLs pass desktop/mobile, metadata, rendition, and enquiry checks.
  The application independently requires the catalogue root to remain live/public;
  switching the flag back to `False` is the fast navigation rollback.
- Keep `PUBLIC_EDITORIAL_PAGES_ENABLED=False` through the initial editorial migration.
  With the flag disabled—or when a CMS page is draft, restricted, or unpublished—the
  stable `/about/` and `/our-story/` routes serve their reviewed Django fallbacks.
  Enable it only after editorial authorization and the live About revision pass review.
- Keep `PUBLIC_BLOG_ENABLED=False` through the blog schema and authorization rollout.
  Publishing the blog root or an article while disabled must not make either route
  public. Enable it only after genuine content, approval, direct-route, rendition,
  metadata, accessibility, and mobile checks pass.
- `MEDIA_STORAGE_BACKEND=r2` is mandatory when Wagtail is deployed. Use a separate
  R2 Standard bucket and Object Read & Write token for each environment. Scope each
  token to its one bucket; never expose either credential to browser code or logs.
- `R2_CUSTOM_DOMAIN` is a hostname without `https://`, port, path, or trailing slash.
  Production checks reject a missing domain and Cloudflare's rate-limited `r2.dev`.
  Private originals/documents use 15-minute signed S3 API URLs; only generated
  renditions use the unsigned custom domain.
- Percent-encode reserved characters in database usernames/passwords. Require
  `sslmode=require` or the stronger certificate-validation mode supported by the
  provider. Prefer a private network in addition to TLS where available; the selected
  Linode service instead uses its public database hostname plus exact-IP access controls.
- Set `TRUST_PROXY_SSL_HEADER=True` only after verifying that all requests traverse
  a trusted proxy which overwrites `X-Forwarded-Proto`. Otherwise a client may spoof
  the header. Keep `SECURE_SSL_REDIRECT=True` when Django is expected to enforce HTTPS.
- Start HSTS at `3600`. Increase it only after observing correct HTTPS behavior.
  Enable subdomains and preload only after every affected hostname is permanently
  HTTPS-capable and the domain owner accepts the long-lived consequences.
- `EMAIL_USE_TLS` and `EMAIL_USE_SSL` are mutually exclusive.
- Keep `PUBLIC_CUSTOMER_REGISTRATION_ENABLED=False` through the schema rollout and
  owner-only checks. The version values must identify the exact Terms and Privacy
  pages shown with the consent checkbox. Enabling this staged request never opens
  direct allauth signup and never creates a scheme automatically.
- Keep `PAYMENT_GATEWAY=razorpay` while pausing new payments so callbacks and signed
  webhooks remain available. Use the audited owner Payment Operations page for normal
  or volatility closure, or `PAYMENT_INITIATION_KILL_SWITCH=True` as the environment
  fail-safe. Never use the mock payment adapter outside debug mode. Metal
  contributions are independently unavailable until an owner has published the
  applicable Scheme Rate.
- `RAZORPAY_MODE` is required when Razorpay is selected and accepts only `test` or
  `live`. It must match the API key prefix. Change the mode, key ID, API key secret,
  and separately generated mode-specific webhook secret as one controlled cutover.
- Keep each Razorpay API secret distinct from the webhook secret. Do not log request
  signatures, secret values, full provider payloads, or database URLs.
- `APP_RELEASE` must identify exactly one source/image build and must be identical in
  the migration job and web service.

The complete variable reference is maintained in the [README](../README.md#environment-variables).

## Cloudflare R2 media setup and proof

The application sends uploads through Django; browsers do not upload directly to
R2. Wagtail originals and documents use the private `default` storage alias and
short-lived signed S3 API URLs. Generated image renditions use the separate
`renditions` alias and the public custom media domain. WhiteNoise remains responsible
for application static files.

1. Create two R2 **Standard** buckets such as `jsk-media-staging` and
   `jsk-media-production`. Do not share a bucket between environments.
2. Create a separate R2 API credential for each bucket. Select **Object Read &
   Write** and restrict it to that one bucket. Save the Access Key ID and Secret
   Access Key immediately in the relevant secret store; never commit or paste them
   into tickets, chat, screenshots, or shell output.
3. For the first non-production smoke, set `MEDIA_STORAGE_BACKEND=r2`, configure the
   account ID, key pair, and staging bucket, and leave `R2_CUSTOM_DOMAIN` empty. This
   keeps generated URLs signed and avoids making the staging bucket public.
4. Apply Wagtail migrations, run normal Django checks, and execute:

   ```powershell
   uv run --env-file .env.r2 python manage.py check_media_storage
   ```

   The command creates a small PNG, reads it back, creates and reads a Wagtail
   rendition, then deletes its database rows and both objects. It must report all
   four checks as successful, leave no `r2-storage-check-*` object, and expose no
   credential or signed URL in output.

   Evidence recorded 2026-08-24: the isolated non-production command reported that
   upload, read, rendition, and cleanup all passed. No credential, URL, or temporary
   object identifier is retained in the repository.
5. Before production, add `jaishrikrishnajewellery.com` as a zone in the same
   Cloudflare account and connect `media.jaishrikrishnajewellery.com` to the
   production bucket under **R2 → bucket → Settings → Custom Domains**. If the
   authoritative DNS is not already on Cloudflare, first inventory and preserve all
   apex, `www`, MX, TXT, CAA, and verification records before changing nameservers or
   using Cloudflare's supported partial-zone setup. Never CNAME the media hostname to
   an `r2.dev` address.

   DNS baseline observed 2026-08-24: authority remains on `ns1.linode.com` through
   `ns5.linode.com`; the apex and `www` resolve to `172.235.9.77`; MX records point
   to `smtp.secureserver.net` at priority 0 and `mailstore1.secureserver.net` at
   priority 10; TXT includes `v=spf1 include:secureserver.net -all` and `T1327472`.
   This public snapshot is not a complete zone export. Export and compare every
   Linode DNS record before changing the registrar's nameservers.

   Cutover evidence recorded 2026-08-24: Cloudflare received all 17 non-NS records,
   including the two GoDaddy DKIM CNAMEs and Postmark DKIM TXT record missed by the
   automatic import. Public authority changed to `carlane.ns.cloudflare.com` and
   `tony.ns.cloudflare.com` with no stale DS delegation. Both authoritative servers
   returned matching apex A/AAAA and MX answers; public apex, `www`, live, and ready
   HTTPS checks returned `200`. Keep the Linode zone intact as the short-term DNS
   rollback source until Cloudflare and mail delivery have remained stable.
6. Disable the production bucket's public `r2.dev` URL. On the Cloudflare zone, add
   one zone-level WAF custom rule with the **Block** action:

   ```text
   (http.host eq "media.jaishrikrishnajewellery.com" and
    (starts_with(http.request.uri.path, "/original_images/") or
     starts_with(http.request.uri.path, "/documents/")))
   ```

   The Free plan currently includes a limited number of zone custom rules, so retain
   evidence that requests to both protected prefixes return `403` while a generated
   `/images/` rendition returns `200`. The S3 API endpoint remains private and is not
   affected by this browser-facing WAF rule.
7. Add a cache rule only for `media.jaishrikrishnajewellery.com/images/*` and respect
   the object's `Cache-Control: public, max-age=86400`. Do not cache signed original
   or document responses. Purge the media hostname after changing cache or CORS rules.
8. No R2 CORS policy is required for the current server-side upload and ordinary
   HTML `<img>` flow. Record that explicit deny-by-default decision. If later browser
   JavaScript, canvas access, or direct uploads require CORS, allow only the exact
   production origins and required `GET`/`HEAD` methods or upload headers; never use
   a wildcard origin for credentialed operations.
9. Re-run `check_media_storage` with the production release candidate and production
   bucket before editor access is enabled. With `R2_CUSTOM_DOMAIN` configured, the
   command also requires the generated `/images/` rendition to return `200`, carry
   `Cache-Control: public, max-age=86400`, and produce a Cloudflare cache `HIT` within
   three requests. The direct custom-domain `/original_images/` and `/documents/`
   prefixes must return `403`. Confirm R2 metrics show the temporary writes, reads,
   and deletes and that the bucket is empty apart from approved media.

   Before running it, the bucket's Custom Domains panel must show the media hostname
   as Active and both Cloudflare authoritative nameservers must resolve it. `NXDOMAIN`
   means the R2 attachment is not ready; do not work around that by manually creating
   a generic CNAME. If the command warns that cleanup was incomplete, inspect and
   remove only `r2-storage-check-*` records and objects before retrying. Public
   rendition and private-prefix checks retry three times and distinguish an HTTP
   status failure from a DNS/network/TLS failure; use that classification before
   changing WAF or cache rules.

   Production evidence recorded 2026-08-24: an initial attachment mistakenly used
   the apex domain and was removed without disrupting the application. The corrected
   `media.jaishrikrishnajewellery.com` attachment became active with valid TLS;
   nonexistent `/images/` returned `404`, both private prefixes returned `403`, and
   the real production smoke passed upload, read, rendition, public delivery, access
   controls, and cleanup. Apex, `www`, live, and ready remained `200`.

   Cache evidence recorded 2026-08-24: after the host-scoped `/images/` cache rule
   was deployed, a fresh production smoke observed the required
   `Cache-Control: public, max-age=86400` response and a Cloudflare cache `HIT`; the
   private-prefix and cleanup checks continued to pass.

Credential rotation uses overlap, not downtime: create a second bucket-scoped token,
replace the two R2 key values, recreate the web service, run `check_media_storage`,
then revoke the old token and run the check again. Roll back to the previous token
only while it remains active; never keep both indefinitely.

Rotation evidence recorded 2026-08-24: a separately created replacement token scoped
to the production media bucket passed the full storage/custom-domain smoke. The old
token was deleted and the replacement passed the full smoke again. A transient local
DNS/TLS interruption affected only a public WAF probe; bounded retries then completed
without changing credentials or Cloudflare security rules.

R2 durability is not a backup against operator deletion or application mistakes.
Before real catalogue media is accepted, copy a non-sensitive test object to the
approved backup target, delete only that test object from the primary bucket, restore
it to the same key, and compare its size and SHA-256 hash. Record the date, operator,
bucket names, evidence, and cleanup. Define a scheduled copy/retention policy for real
media and test restoration periodically; database recovery and media recovery must use
compatible recovery points because Wagtail stores object keys in PostgreSQL.

Accepted deferral recorded 2026-08-24: this recovery drill is not required to begin
local catalogue-domain development. It remains `FW-MEDIA-002`; approved source images
must be retained outside R2, and R2 must not become the only copy until a backup target
and periodic restore proof exist.

## Edge, DNS, and TLS configuration

1. Configure the service on a temporary platform hostname and validate both health
   endpoints before changing public DNS.
2. Add the owned hostname to the edge, issue its certificate, and point DNS to the
   edge using a low TTL during the first rollout.
3. Configure an explicit allow-list for the public host. The edge should reject an
   unknown `Host` instead of forwarding it to Django.
4. Redirect port 80 to HTTPS at the edge. Forward the original client address using
   the platform's standard trusted mechanism and overwrite `X-Forwarded-Proto=https`.
5. Verify an HTTP request redirects once to HTTPS and an HTTPS request does not loop.
6. Verify secure session and CSRF cookies, login, logout, and a CSRF-protected form.
7. Begin with one-hour HSTS. Observe at least one normal release cycle before raising
   it. Treat `includeSubDomains` and preload as separate, reviewed changes.

Razorpay's webhook must use the stable URL:

```text
https://savings.example.com/scheme/payments/razorpay/webhook/
```

Subscribe only to the events currently handled by the application, which is
`payment.captured`. Keep the platform endpoint public, but do not add an authentication
layer that prevents Razorpay delivery; the application authenticates the untouched
request body with the webhook signature.

## Build and release artifacts

CI is the release gate. It uses PostgreSQL 16 to apply migrations, checks migration
drift, runs Django checks and the full regression suite, runs deploy checks, collects
static files, and builds the production image. Pull requests and non-`main` pushes
build and scan a local CI image without registry credentials. After an approved
change reaches protected `main`, a separate least-privilege job builds the merged
commit once, pushes only its full-commit tag to GHCR, scans the published digest, and
records the immutable deploy reference in the GitHub Actions job summary.

For a release candidate:

```powershell
git status --short
uv sync --frozen
uv run --env-file .env python manage.py makemigrations --check --dry-run
uv run --env-file .env python manage.py check
uv run --env-file .env python manage.py test
docker build --pull --tag jsk-savings:local-check .
```

Run tests only against a disposable CI/test database. Never let Django create or
destroy a test database beside production data.

After the merged build:

1. Record the source commit, CI run, image tag, and immutable image digest.
2. Require the published-digest critical-vulnerability gate to pass and review the
   scanner output before promotion.
3. Publish only the full-commit tag. Do not publish or deploy a mutable `latest` tag,
   and do not rebuild separately for staging and production.
4. Set `APP_RELEASE` to the recorded commit or digest-derived identifier.
5. Promote the exact same image digest through staging and production.

Static files are collected in the builder stage and served by WhiteNoise from the
image. A runtime `collectstatic` job is neither required nor desired.

### Public GHCR pull access on the Linode

The protected-`main` workflow creates or updates the repository-linked public package
`ghcr.io/rajeshr188/jsk-savings`. Public visibility is an accepted boundary because
the source repository is already public and the production image contains packaged
source and dependencies, not runtime secrets. `.dockerignore` excludes `.env` files,
deployment secrets, documentation, tests, and local media from the build context.
Production credentials remain runtime-only values supplied by `.env.production` and
Compose file-backed secrets.

Do not create or store a GitHub Personal Access Token on the Linode for this public
package. Prove anonymous access with an empty, temporary Docker client configuration,
then pull and inspect the exact digest from the successful protected-`main` Actions
summary:

```bash
test ! -e /tmp/jsk-ghcr-anonymous
mkdir -m 700 /tmp/jsk-ghcr-anonymous
DOCKER_CONFIG=/tmp/jsk-ghcr-anonymous \
  docker pull ghcr.io/rajeshr188/jsk-savings@sha256:<approved-manifest-digest>
rmdir /tmp/jsk-ghcr-anonymous
docker image inspect \
  ghcr.io/rajeshr188/jsk-savings@sha256:<approved-manifest-digest> \
  --format '{{json .RepoDigests}}'
```

The first anonymous Linode pull passed on 2026-09-04 for digest
`ghcr.io/rajeshr188/jsk-savings@sha256:30df12ac108ce90504c9c33e18e79d2c1c3d304e77e2d8cc9f64339bd5c86c54`.
The production environment and running containers were not changed; the web service
remained healthy on release `50bfd3673c57dff51b46238094bcad899a36c8fa`.
GitHub does not support changing a public Container registry package back to private.
If private registry access is required in future, publish a separately named private
package and treat its host credential as a reviewed credential-management change.

## Repository change to Linode deployment workflow

Follow this workflow for every application, dependency, configuration-template, or
deployment-file change. Never edit tracked source code directly in `/opt/jsk/app` on
the server, never deploy an uncommitted worktree, and never use a mutable `latest`
tag as release identity.

### 1. Make and validate the change locally

Start from an up-to-date `main` after the current release PR has been merged. Use a
short-lived branch; do not commit directly to `main`:

```powershell
git switch main
git pull --ff-only origin main
git switch -c agent/example-change
```

Implement one coherent change. Add tests for changed behavior and for every change
affecting payments, rates, allocations, balances, bonuses, redemptions, or other
financial invariants. When models change, create and inspect the migration locally;
never hand-edit an applied migration. Update canonical documentation when behavior or
operational state changes.

Run the release-candidate checks against a disposable local PostgreSQL database:

```powershell
uv sync --frozen
uv run --env-file .env python manage.py makemigrations --check --dry-run
uv run --env-file .env python manage.py check
uv run --env-file .env python manage.py test
docker build --pull --tag jsk-savings:local-candidate .
```

Never point these tests at the Linode production database. If a migration exists,
review its SQL/operations, expected locks, runtime, reversibility, and compatibility
with both the old and new application image.

### 2. Review, stage, commit, and push intentionally

Review the complete worktree and stage explicit paths so unrelated user work and
secrets cannot be swept into a commit:

```powershell
git status --short
git diff --check
git diff
git add -- path/to/changed-file another/changed-file
git diff --cached --check
git diff --cached
git commit -m "Describe the change"
git push -u origin HEAD
gh pr create --draft --fill
```

Do not stage `.env`, `.env.production`, CA files, database URLs, provider keys,
webhook secrets, SMTP passwords, exports, backups, or customer data. A tracked
`.env*.example` file must contain placeholders only. The pull request must describe:

- the behavior and reason for the change;
- migrations and old/new-image compatibility;
- financial-invariant and access-control impact;
- tests and manual checks performed;
- provider/configuration changes;
- the exact rollback image and any condition that makes application rollback unsafe.

### 3. Pass the repository release gate

Both GitHub Actions jobs (`django` and `container`) must pass for the exact pull-request
head commit. Review the diff, resolve conversations, and merge to `main`; record the
resulting full commit SHA. Configure GitHub branch protection to require a pull
request and successful checks before merging and to disallow force pushes.

An Actions run that did not start is not a passing run. If GitHub Actions is disabled
or blocked by an account/billing problem, restore it before treating CI as a
production release gate. Locally validated builds alone may be used only for the
documented staging/infrastructure exercise, not a real-funds deployment.

### 3a. Realign the local checkout after merge

A branch name is not the production release identity. Production runs the immutable
image and `APP_RELEASE` commit recorded during deployment; `main` is the protected
source branch from which that release was approved. After the pull request is merged,
refresh the developer checkout instead of continuing work on the merged feature
branch:

```powershell
git status --short
git fetch origin
git switch main
git pull --ff-only origin main
git status -sb
```

The final status should show `main...origin/main` with no tracked changes. An expected
untracked file may remain, but it is not part of `main` and must not be swept into a
later commit. If `git status` shows unfinished tracked or untracked work, do not use
`reset --hard`, forced checkout, or an indiscriminate stash. Move intentional work to
its own branch or stash only explicitly selected paths before switching.

After confirming that the pull request is merged and the production stabilization
window is complete, the merged local feature branch may be deleted safely:

```powershell
git branch -d agent/completed-feature
```

Deleting the remote feature branch is optional and should wait until the release is
stable. It does not affect the merge commit or deployed image. Do not reverse local
database migrations merely because a feature branch is deleted; the local schema
should match the migrations on updated `main`.

Start every later change from a freshly updated protected branch and use a new,
descriptive branch:

```powershell
git switch main
git pull --ff-only origin main
git switch -c agent/descriptive-feature-name
```

`--ff-only` is intentional: it stops instead of creating an accidental merge commit
when the local `main` has diverged. Never deploy by referring only to the current
feature branch; build and deploy the exact merged 40-character commit SHA.

### 4. Build once and identify the release immutably

The production target is the CI-published GHCR image built once from the merged
commit, scanned, and promoted by immutable digest, for example:

```dotenv
APP_IMAGE=ghcr.io/rajeshr188/jsk-savings@sha256:<approved-manifest-digest>
APP_RELEASE=<full-merged-commit-sha>
```

Record the commit, CI run, image digest, scan result, migration plan, and previous
production digest in the release evidence. A digest pins exact image content; a tag
alone can be moved.

The Actions summary from the successful protected-`main` run is the handoff record.
Copy its exact `ghcr.io/rajeshr188/jsk-savings@sha256:...` value; never derive a digest from
a tag by assumption and never deploy a red or incomplete workflow run.

There is no serving-host build fallback. Do not run `docker build`, Buildx, or a
language dependency build on the 1 GiB production Compute Instance. Release-layer
export plus an immediate one-off candidate container exhausted its 961 MiB RAM and
496 MiB swap on 2026-09-04 and caused an origin outage. If GitHub Actions is
unavailable, use a reviewed separate builder to build the exact merged commit, scan
it, push it to the approved registry package, and record its digest before deployment;
otherwise defer the release.

Before every production pull or candidate command, record capacity and confirm the
previous image remains pullable:

```bash
free -h
swapon --show
df -h / /var/lib/docker
docker stats --no-stream
```

Stop when memory or disk headroom is materially below the last accepted release
baseline. Run one-off candidate checks sequentially, remove each temporary container
on completion, and repeat the capacity check between them. External threshold and
notification testing remains tracked under `FW-PROD-002`; this preflight does not
claim that deferred alerting is complete.

### 5. Prepare the Linode release

Open a planned change window. Record the current `APP_IMAGE`, `APP_RELEASE`, container
status, owner-dashboard customer/account counts, cash principal, earned bonus, gold
grams, silver grams, and exception counts. Confirm a current managed recovery point
and that the previous image remains present or pullable.

Fetch source metadata and detach at the approved merged commit. A fetch alone does not
change the running container:

```bash
cd /opt/jsk/app
git status --short
git fetch --prune origin
export JSK_RELEASE_SHA=FULL_40_CHARACTER_APPROVED_COMMIT_SHA
git checkout --detach "$JSK_RELEASE_SHA"
test "$(git rev-parse HEAD)" = "$JSK_RELEASE_SHA"
```

For a registry release, there is no on-host build. Pull and inspect the approved
digest before editing any release identity:

```bash
export JSK_CANDIDATE_IMAGE='ghcr.io/rajeshr188/jsk-savings@sha256:<approved-manifest-digest>'
docker pull "$JSK_CANDIDATE_IMAGE"
docker image inspect "$JSK_CANDIDATE_IMAGE" --format '{{json .RepoDigests}}'
```

If authentication, manifest verification, architecture selection, or the pull
fails, stop without changing `.env.production`. Otherwise edit only the two release
identity values in the protected server environment; do not replace the file from
the example and thereby erase production secrets:

```bash
nano .env.production
```

Set `APP_IMAGE` to the approved digest and set `APP_RELEASE` to the matching full
commit SHA. Then validate the exact candidate against the real
production configuration and review database state without mutation:

```bash
docker compose --env-file .env.production -f compose.production.yml config --quiet
docker compose --env-file .env.production -f compose.production.yml \
  run --rm --no-deps web python manage.py check --deploy --fail-level ERROR
docker compose --env-file .env.production -f compose.production.yml \
  run --rm --no-deps web python manage.py showmigrations --plan
docker compose --env-file .env.production -f compose.production.yml \
  run --rm --no-deps web python manage.py migrate --plan
```

Stop if any output differs from the reviewed plan. A non-backward-compatible migration
requires its own maintenance and recovery procedure; do not apply it while the old
image serves traffic.

#### Customer-invitation migration preflight (`accounts.0003`)

Before applying `accounts.0003_customerinvitation_and_more`, run the candidate's
read-only integrity command against production:

```bash
docker compose --env-file .env.production -f compose.production.yml \
  run --rm --no-deps web python manage.py check_auth_email_integrity
```

Record `duplicate_groups=0`. Blank-email administrative users are reported but do not
block the conditional constraint. If duplicates exist, stop. In a private terminal
only, rerun with `--show-identifiers`, inspect each user's role, customer linkage,
scheme accounts, and audit/financial history, and decide which distinct email belongs
to each real person. Do not paste that personal-data output into shared logs, and do
not automatically delete, merge, deactivate, or reassign accounts. Rerun the default
command until it passes. The migration independently repeats this check immediately
before adding the case-insensitive unique constraint.

Set the bounded invitation lifetime in `.env.production` before candidate validation:

```dotenv
CUSTOMER_INVITATION_EXPIRY_HOURS=72
```

The schema addition is backward-compatible with the previous image, but the new owner
workflow must not go live until the candidate migration succeeds and Caddy has loaded
the candidate `deploy/Caddyfile`. That proxy configuration excludes password-reset
and invitation-secret paths from access logs. Validate and recreate Caddy during the
release, then verify its effective configuration before inviting a customer. The
candidate image also disables Gunicorn's redundant full-path access log; Caddy remains
the authoritative privacy-reduced request log while Gunicorn retains error output.
Django's console handler redacts invitation and password-reset secrets if a CSRF
warning or application error includes either path.

Token-bearing responses must return `Cache-Control: no-store`, `Pragma: no-cache`,
and `Referrer-Policy: strict-origin`. Do not use `no-referrer`: production browser
evidence showed that it can produce `Origin: null` on the password POST, which Django
correctly rejects. `strict-origin` supplies only the scheme and host needed for CSRF
validation and never discloses the invitation/reset path to subresources. Do not add
`null` to `CSRF_TRUSTED_ORIGINS` or exempt either password endpoint from CSRF.

Authentication email identity must also be correct. In Django admin, update the
`SITE_ID=1` Sites record to domain `jaishrikrishnajewellery.com` and display name
`Jai Sri Krishna Jewellery`; never leave `example.com`. In Postmark, keep click and open
tracking disabled for the authentication stream. The application additionally sends
per-message opt-out headers, but provider configuration remains defense in depth.

After rollout, use a controlled customer mailbox to verify all of the following:

1. Owner creation sends one direct `https://jaishrikrishnajewellery.com/accounts/invitations/...`
   link and creates no scheme account.
2. The customer sets a password once, can sign in, and remains unenrolled until the
   owner creates a separate agreement.
3. Resending before acceptance invalidates the earlier URL.
4. Provider acceptance is labelled as such and is not treated as proof of receipt.
5. Caddy logs contain neither `/accounts/invitations/` nor
   `/accounts/password/reset/key/` request entries, and web-container logs contain no
   Gunicorn access entries or raw authentication tokens. A deliberately induced safe
   warning may contain only `[REDACTED]`; do not print either real URL while testing.
6. Password reset uses the owned site name/domain and remains a direct, untracked URL.

Production evidence recorded 2026-08-26: release
`f9081c1a52a3ce3dc99e1d816cce9846a5b31f92` returned `strict-origin` on the
token paths, accepted a newly invited customer's password setup, and subsequently
accepted that customer's forgot-password reset flow. The earlier `Origin: null`
rejection no longer occurred; CSRF enforcement, `no-store`, token redaction, and
edge-log exclusions remained enabled.

If the candidate must be rolled back after this additive migration, the previous image
can run against the extended schema. Its old owner form would again ask for temporary
passwords, so suspend customer creation until the corrected candidate is restored.

#### Staged public-registration rollout (`accounts.0004`)

Keep the new public entry point closed for the migration and first verification:

```dotenv
PUBLIC_CUSTOMER_REGISTRATION_ENABLED=False
PUBLIC_REGISTRATION_EMAIL_EXPIRY_HOURS=24
PUBLIC_REGISTRATION_ATTEMPTS_PER_HOUR=5
PUBLIC_REGISTRATION_ATTEMPT_RETENTION_HOURS=24
PUBLIC_REGISTRATION_TERMS_VERSION=2026-09-04
PUBLIC_REGISTRATION_PRIVACY_VERSION=2026-09-04
```

The version values are audit identifiers for the exact public Terms and Privacy copy;
change them whenever either consent-bearing page materially changes. Review the
candidate plan and require it to contain only
`accounts.0004_customerregistrationattempt_customerregistration`. This migration adds
isolated application and rate-limit-evidence tables; the previous image ignores them,
so it is backward-compatible while the feature flag is false.

Apply the migration once using the approved candidate image. Recreate `web`, then
recreate Caddy because the candidate `deploy/Caddyfile` adds the public verification
token path to the edge-log exclusion. With the flag still false, verify:

```bash
docker compose --env-file .env.production -f compose.production.yml \
  exec -T web python manage.py showmigrations accounts
docker compose --env-file .env.production -f compose.production.yml \
  exec -T web python manage.py check_public_customer_registrations
```

Require migration `accounts.0004` to be `[X]`, aggregate command `status=ok`, and
`enabled=false`. Confirm the owner can open **Customers → Registration requests**,
while an unauthenticated request to `/accounts/register/` returns 404 and ordinary
allauth `/accounts/signup/` still says direct signup is closed.

Public activation is a separate, reversible configuration decision. Before changing
the flag, confirm Postmark delivery, the owned `SITE_ID=1` name/domain, current policy
versions, and that Caddy's effective configuration excludes
`/accounts/registrations/verify/*`. Set the flag to `True`, validate Compose, and
recreate only `web`; Caddy already contains the required rule. Use one controlled,
previously unused email and mobile number to prove:

1. The application response is generic and the direct, untracked verification email
   is accepted by Postmark.
2. Opening the link does not verify it; the CSRF-protected confirmation does, after
   which the owner queue shows `Awaiting owner approval`.
3. Approval is impossible without the owner confirming the mobile check and entering
   a reason. Rejection creates no login.
4. Approval creates one customer with no usable password and sends the existing
   password-setup invitation, but creates zero scheme accounts.
5. After password setup the customer can sign in and sees the explicit no-schemes
   state with no payment action. Enrolment remains a separate owner operation.
6. `check_public_customer_registrations` still reports `status=ok`, and neither Caddy
   nor application logs contain the verification token.

Do not test throttling by flooding production. Its database-backed per-source and
per-identity boundary is covered by CI; Cloudflare rate limiting or a challenge can
be added later as defence in depth. If behavior is unexpected, set
`PUBLIC_CUSTOMER_REGISTRATION_ENABLED=False`, recreate `web`, and retain the
application records for review. Do not reverse the additive migration or delete
registration evidence merely to disable the public form.

Production acceptance was completed on 2026-09-04. Protected-main CI run
`33872481777` passed the complete test/deploy/static gates, published and scanned
release `613e2f7363a67ea6d588273f54bcddb628f9549a`, and recorded immutable image
`ghcr.io/rajeshr188/jsk-savings@sha256:59543c618c533c96d2a3c048569d24d80ad12b47bd560a97e73157af4ea1e0a2`.
The retained rollback was release `c889ee6906a8bddd4c7852955025efe42ffa5752`
at digest `sha256:88eea68169da2ea04f9f104358ecb69ec929989b15f5e447825ab0f0bd806c33`,
and the managed PostgreSQL recovery point was 2026-09-04 5:00 PM IST.

The reviewed plan contained only `accounts.0004`; it applied successfully. The web
and Caddy services became healthy with the public flag disabled, the aggregate check
reported `status=ok enabled=false`, `/accounts/register/` returned 404, and allauth
signup remained closed. Financial exceptions, Razorpay Live readiness, payment
operations, exact-grade metal, in-store cash, abandoned-order dry-run, and reminder
dry-run checks all remained green. The operator then confirmed Site 1, policy
versions, Postmark delivery, and the effective Caddy exclusion before enabling the
flag. The public route returned 200 and the aggregate check reported
`status=ok enabled=true` with all approval-integrity counters at zero.

Controlled production journeys proved that a replacement verification invalidated
the earlier URL, email verification required the explicit CSRF-protected confirmation,
and rejection created no login. Approval required a recorded reason and manual mobile
confirmation, created one customer plus the existing password invitation, and created
zero scheme accounts. Password setup and customer login succeeded with no payment
action before separate enrolment. The final operator confirmation recorded one
approved and one rejected application. Neither Caddy nor application logs contained
the verification path or a raw token. This closes `FW-AUTH-002`; disabling the flag
remains the immediate rollback for the public entry point.

#### Customer enrolment-interest rollout (`schemes.0020`)

`FW-ENROL-001` is a separate step after customer access approval. Keep request
creation closed while applying and validating the additive migration:

```dotenv
CUSTOMER_ENROLMENT_REQUESTS_ENABLED=False
CUSTOMER_ENROLMENT_REQUEST_EXPIRY_DAYS=30
CUSTOMER_ENROLMENT_REQUEST_DISCLOSURE_VERSION=2026-09-04
```

The disclosure version identifies the exact non-binding acknowledgement shown to the
customer. Change it when that acknowledgement materially changes. Before deployment,
record the rollback image/release, a current Managed PostgreSQL recovery point, host
capacity, and the standard customer/account/liability baseline. Payment pausing is not
required because this migration does not alter contributions, rates, allocations,
balances, or existing agreements; operators may still pause if the broader release
contains financial changes.

Review the candidate migration plan and require only
`schemes.0020_scheme_enrolment_requests`. It adds the request table and audit-action
choices; it does not backfill or rewrite any customer, scheme account, contribution,
rate, allocation, redemption, or liability:

```bash
docker compose --env-file .env.production -f compose.production.yml \
  run --rm --no-deps web python manage.py check --deploy --fail-level ERROR
docker compose --env-file .env.production -f compose.production.yml \
  run --rm --no-deps web python manage.py showmigrations schemes
docker compose --env-file .env.production -f compose.production.yml \
  run --rm --no-deps web python manage.py migrate --plan
docker compose --env-file .env.production -f compose.production.yml \
  run --rm --no-deps web python manage.py migrate --noinput
```

Require `schemes.0020` to be `[X]`. Recreate only `web`; this phase adds no public
token route and requires no Caddy change:

```bash
docker compose --env-file .env.production -f compose.production.yml \
  up -d --force-recreate --no-deps web
docker compose --env-file .env.production -f compose.production.yml ps
docker compose --env-file .env.production -f compose.production.yml \
  exec -T web python manage.py check_scheme_enrolment_requests
```

Require a healthy candidate, the expected release, `status=ok enabled=false`, both
HTTPS health endpoints returning 200, and all applicable payment-operations,
financial-exception, Razorpay Live-readiness, exact-grade, in-store cash, and
abandoned-order dry-run gates remaining green. With the flag false, the owner may
open **Customers → Enrolment requests** to inspect the empty/historical queue, but the
public plans page must show no request button and a direct new-request URL must return
404. Existing request history remains viewable if the feature is disabled later.

Activation is a separate configuration decision. Confirm at least one active,
publicly listed plan has the intended active exact-grade offerings, its displayed INR
amount/duration terms have been reviewed, customer and owner email delivery works,
and the disclosure version is current. Set
`CUSTOMER_ENROLMENT_REQUESTS_ENABLED=True`, validate Compose, and recreate only
`web`. Then use a legitimate approved customer profile to prove:

1. The customer selects one public plan, exact metal grade, preferred INR
   contribution, preferred duration, and accepts the non-binding disclosure.
2. Exactly one pending request and one submission audit event are recorded. No
   `SchemeAccount`, contribution, Razorpay order, Scheme Rate lock, allocation, or
   liability is created by submission, and a repeat submission returns the same
   pending request.
3. The email provider accepts the customer acknowledgement and owner notification;
   both messages state that the request is not an agreement or payment permission.
4. The owner queue displays the request and current-offer check. Conversion is
   blocked if the plan/offering changed or the request expired.
5. After the owner actually reviews the current plan, grade, start date, amount rule,
   and duration with the customer, explicit confirmation creates exactly one ordinary
   snapshotted `SchemeAccount`, links it to the retained request, and sends the
   completion notice. Repeating conversion creates no second account.
6. The customer sees the linked scheme and only then receives the existing payment
   action subject to rates and payment controls. Run
   `check_scheme_enrolment_requests` again and require `status=ok`.

Also exercise withdrawal or decline in a non-production environment; do not create a
false production request merely to fill every terminal state. A request is not an
electronic signature, KYC decision, payment mandate, or proof that an email was read.

If activation behaves unexpectedly, set the flag to `False`, validate Compose, and
recreate only `web`. This immediately prevents new submissions while preserving the
owner queue and all request/audit evidence. Do not delete request rows or reverse the
additive migration. The previous application image can run against the extended
schema, but suspend use of the new queue until the corrected release is restored.

Production acceptance completed on 2026-09-04 in release
`bfbdad86c49855ffc5c9965d0848a657a62cf938`, using immutable image digest
`sha256:3d634e2c6c4149c94b7f82aaaee2e5b60c0b1db0821203e1f8d65d95205bf394` and the
recorded 8:00 PM IST Managed PostgreSQL recovery point. The rollback release was
`613e2f7363a67ea6d588273f54bcddb628f9549a`. The additive migration was applied as
the only planned operation with request creation disabled; the empty-queue,
integrity, financial, provider, exact-grade, and HTTPS health gates passed before
activation. One legitimate customer then submitted a `GOLD_22K_916`, INR 5000.00,
12-month interest request. It retained one submission audit while account count,
pending Razorpay orders, and all liabilities remained at baseline. Owner review of
current terms created exactly one linked agreement (`JSK-311D2A62`) with zero
contributions, delivered the completion email, and an idempotency check retained nine
total scheme accounts and one enrolment audit. This closes `FW-ENROL-001` and the
`FW-AUTH-003` separation between login, interest, and financial enrolment.

Before applying `schemes.0010_manual_scheme_rates`, confirm the old architecture has
no verified metal payment without an allocation and no open metal Razorpay order.
This deliberately includes both `PAID` and `PAID_UNALLOCATED`: an interrupted legacy
worker could have committed payment confirmation before recording the allocation.
Complete or reconcile those records on the old release first. The migration
intentionally stops instead of inventing a rate if either count is non-zero:

```bash
docker compose --env-file .env.production -f compose.production.yml \
  run --rm --no-deps web python manage.py shell -c \
  "from schemes.models import Contribution; modes=['GOLD','SILVER']; print('verified_metal_without_allocation=', Contribution.objects.filter(status__in=['PAID','PAID_UNALLOCATED'], scheme_account__savings_mode__in=modes, metal_allocation__isnull=True).count()); print('open_metal_orders=', Contribution.objects.filter(status='PENDING', payment_gateway='razorpay', gateway_order_id__isnull=False, scheme_account__savings_mode__in=modes).count())"
```

Record both zero results with the release evidence. This migration renames/removes
provider-era schema, so the previous image is not schema-compatible after it runs;
use the reviewed maintenance window, database recovery point, and roll-forward plan.
After recording the preflight, prevent a new payment or allocation from racing the
migration by stopping public traffic and the old web process:

```bash
docker compose --env-file .env.production -f compose.production.yml stop caddy
docker compose --env-file .env.production -f compose.production.yml stop web
docker compose --env-file .env.production -f compose.production.yml ps
```

Confirm both services are stopped. Keep them stopped until the migration succeeds and
the candidate web container is healthy. If migration fails, do not start the candidate;
retain the failed output, restore the recorded previous `APP_IMAGE` and `APP_RELEASE`,
start the previous web and Caddy services, and follow the incident/recovery procedure.

### 6. Apply once, deploy, and verify

After the backup/recovery point, migration plan, rollback image, operator, and business
reconciler are confirmed, run migrations exactly once:

```bash
docker compose --env-file .env.production -f compose.production.yml \
  run --rm --no-deps web python manage.py migrate --noinput
```

For a release containing the catalogue authorization milestone, reconcile the
application-owned CMS groups, catalogue subtree, media collection, and approval
workflow while Caddy is still stopped. The command is idempotent but intentionally
resets the three `Catalogue ...` groups to the reviewed least-privilege matrix; do
not reuse those group names for unrelated permissions:

```bash
docker compose --env-file .env.production -f compose.production.yml \
  run --rm --no-deps web python manage.py configure_catalog_permissions
docker compose --env-file .env.production -f compose.production.yml \
  run --rm --no-deps web python manage.py configure_catalog_permissions --check
```

This creates only a **draft** catalogue page and does not grant any user access.
After the production rollout and media-recovery limitation are accepted, a superuser
must explicitly assign an active staff user to `Catalogue Editors`, `Catalogue
Publishers`, or `Catalogue Administrators`. An application `OWNER` role alone must
never be treated as CMS authorization. Retain the successful check output with the
release evidence.

Keep `PUBLIC_CATALOGUE_ENABLED=False` during that authorization rollout. After an
authorized publisher has approved the catalogue root and initial products, verify the
direct `/jewellery/` and product URLs, responsive media-domain renditions, canonical
and Open Graph metadata, JSON-LD, filters, empty/no-result handling, enquiry links,
and mobile/desktop accessibility. Then set `PUBLIC_CATALOGUE_ENABLED=True`, validate
the Compose configuration, recreate `web`, and confirm the Jewellery link appears in
both primary and footer navigation. If discovery must be withdrawn, set the flag back
to `False` and recreate `web`; do not unpublish or delete content merely to hide the
navigation while an incident is assessed.

For a release containing `FW-CMS-003`, keep
`PUBLIC_EDITORIAL_PAGES_ENABLED=False`, apply `pages.0001_initial`, and reconcile the
separate Editorial groups, media collection, seeded draft pages, and approval workflow:

```bash
docker compose --env-file .env.production -f compose.production.yml \
  run --rm --no-deps web python manage.py configure_editorial_pages
docker compose --env-file .env.production -f compose.production.yml \
  run --rm --no-deps web python manage.py configure_editorial_pages --check
```

The command is idempotent and does not overwrite later editor revisions. It resets
only the dedicated `Editorial Editors`, `Editorial Publishers`, and
`Editorial Administrators` groups to their reviewed page/media scopes; never reuse
those names for other access. It creates About and Our Story as drafts and grants no
user membership. Explicitly assign an active staff user, review preview and metadata,
approve and publish About, and confirm `/about/` still shows the static fallback while
the flag is false. Our Story remains unlinked and may stay draft.

After approval, set `PUBLIC_EDITORIAL_PAGES_ENABLED=True`, validate Compose, recreate
only `web`, and verify `/about/` on desktop/mobile, its R2 rendition when an image is
used, and the unchanged policy, Contact, Savings Plans, homepage, and authenticated
routes. Verify `/our-story/` directly only if its CMS revision was deliberately
published; it must not appear in navigation. Fast rollback is to set the flag to
`False` and recreate `web`, which immediately restores both reviewed Django fallbacks
without deleting Wagtail revisions or media.

For a release containing `FW-CMS-004`, keep `PUBLIC_BLOG_ENABLED=False`, apply the
additive `blog.0001_initial` migration, and reconcile the dedicated Blog groups,
media collection, draft root, and approval workflow while Caddy is stopped:

```bash
docker compose --env-file .env.production -f compose.production.yml \
  run --rm --no-deps web python manage.py configure_blog_permissions
docker compose --env-file .env.production -f compose.production.yml \
  run --rm --no-deps web python manage.py configure_blog_permissions --check
```

The command is idempotent and creates no user membership or public article. It resets
only `Blog Editors`, `Blog Publishers`, and `Blog Administrators` to their reviewed
page/media scopes. Explicitly assign active staff, create genuine business-authored
content, and use the Blog workflow to preview and approve the root and posts. With the
flag false, confirm `/blog/` and published article URLs both return `404` and no
Journal link appears in primary or footer navigation.

Before enabling, review factual accuracy and confirm that articles contain no Scheme
Rates, authoritative plan/product/policy terms, personalized advice, or financial
claims. Verify canonical and social metadata, meaningful image alt text, responsive
R2 renditions, empty/paginated states, and mobile/desktop accessibility. Then set
`PUBLIC_BLOG_ENABLED=True`, validate Compose, recreate `web`, recreate Caddy, and
verify `/blog/`, each approved post, and both navigation links. Re-run CMS, R2,
authentication, payment, grade, and financial integrity checks.

Fast public rollback is to set `PUBLIC_BLOG_ENABLED=False` and recreate `web` and
Caddy. Preserve `blog` tables, Wagtail revisions, workflow history, and R2 objects;
never delete or reverse them merely to hide public discovery.

For the `FW-PRODUCT-001` metal-only boundary release, repeat the read-only CASH audit
immediately before stopping traffic. The approved baseline is one open CASH account,
zero pending CASH payments, zero verified CASH payments/INR, zero CASH redemptions,
and zero plans with a nonzero cash bonus. Stop and investigate if any monetary or
pending-payment value differs; do not strand or silently rewrite a customer payment.
This release has no schema migration and preserves the empty account as an inert
historical record.

Run the candidate image against production configuration while traffic is still on
the previous release:

```bash
docker compose --env-file .env.production -f compose.production.yml \
  run --rm --no-deps web python manage.py check_cash_boundary
```

The command must report `status=ok`, `cash_activity_enabled=False`, and zero pending
payments, verified payments/INR, redemptions, and nonzero cash-bonus plans. Account
counts are informational and may retain the approved empty historical record.

After the candidate is healthy, confirm `DJANGO_DEBUG=False`, verify gold/silver
enrolment remains available, and sign in as the historical CASH customer to prove the
account and statement remain readable, no Pay action is rendered, and the direct
contribution URL returns `403`. Re-run `check_financial_exceptions` and the aggregate
liability snapshot. The release must not change the approved zero CASH exposure.

On the current single-host topology, expect a brief maintenance window. Start the
candidate web container while Caddy remains stopped, and wait until `web` reports
healthy. Do not restore public traffic before that health gate:

```bash
docker compose --env-file .env.production -f compose.production.yml \
  up -d --no-deps web
docker compose --env-file .env.production -f compose.production.yml ps
```

Repeat `ps` until `web` is healthy. Then recreate Caddy so its upstream resolution
cannot retain the prior container address. Caddy's named volumes preserve certificates:

```bash
docker compose --env-file .env.production -f compose.production.yml \
  up -d --force-recreate --no-deps caddy
```

Verify the public release and recent logs:

```bash
curl --fail-with-body https://jaishrikrishnajewellery.com/health/live/
curl --fail-with-body https://jaishrikrishnajewellery.com/health/ready/
curl --fail-with-body https://jaishrikrishnajewellery.com/static/css/base.css
docker compose --env-file .env.production -f compose.production.yml logs --since=10m web
docker compose --env-file .env.production -f compose.production.yml logs --since=10m caddy
```

The health JSON must contain the new `APP_RELEASE`. Complete the production-safe smoke
test and compare post-release liabilities and exception counts with the baseline,
accounting for legitimate activity. Observe through the stabilization window before
closing the release record.

### Amazon SES migration (`FW-PROD-008`; in progress 24 October 2026)

The owner authorised SES setup and migration and accepted a brief interruption for
the final single-container replacement. Use the existing host; no second stack,
database migration or unrelated local application release belongs in this change.
Postmark continues serving customers until the gates below pass.

**31 October approved cutover:** production now runs privately built release
`a41e7277ac125e86f5a3aae258b26dc52a7d3bfc` with Mumbai SES at port 587, STARTTLS,
ten-second timeout and the unchanged admin sender. The owner explicitly approved
private transfer and this image in place of the normal CI-published-image gate.
The archive checksum was verified on the host; loaded image ID is
`sha256:52ff796c8f54ff9d24d5a406b91cb7d4f0f57de0ef17d7bbc8a280aad3a325c9`.
Layer/platform, runtime configuration, revision and source-file hash checks match
the reviewed artifact despite the different host representation of the image ID.
The original environment is protected mode 0600 at
`/home/deploy/.config/jsk/ses-release-a41e727/environment-before.env`; bounded phase
state is protected alongside it. Neither was downloaded or committed.

Sudo required a password to control the system timer. The approved change used the
existing application reminder switch for the dispatch hold, then restored it true
after actual post-cutover Inbox receipt, marker `c89f65b8358f`. Both timers have future
runs scheduled. All other runtime environment values and Caddy identity are unchanged.
Deployment checks pass at ERROR level with the existing HSTS warnings; all six
financial-exception counters remain zero. Final dry-run reports enabled reminders
and zero candidates/failures. Postmark rollback authentication still passes (235)
over validated TLS without a send. Keep its credentials, DNS and retained copies.

The first hold attempt restored the exact original environment after the server's
Cloudflare edge probe returned 403. The retry used validated origin TLS checks,
with browser edge verification separate; no security control changed. Origin
home/login/live/readiness are 200, private routes redirect, webhook GET is 405.
After recovering the minimized Chrome window, fresh post-cutover browser requests
verified the normal public homepage and retained owner session. The 11:57:54 IST
completion audit confirms the exact healthy release/image, unchanged other
configuration/Caddy, active timers/enabled reminders and six zero financial-exception
counters. No pending rollout phase or dispatcher hold remains. Migration acceptance
is complete. No schema/financial mutation, GitHub push, PR or Postmark retirement
occurred. Observe actual delivery and review retained data before retiring rollback;
no automatic retirement or provider cancellation is scheduled.

Pre-cutover 31 October inventory ran `b20241a` at image
`ghcr.io/rajeshr188/jsk-savings@sha256:c8f60b76ef601889b9ee10d440b00721556451a6194acc21a9f98a8f7f3cd86b`,
healthy and still on Postmark. AWS approved Mumbai production access on 30 October;
live Support/SES checks confirm 50,000 messages/day, 14/second and healthy status.
Both Postmark outbound and SES suppression lists are empty. SES bounce/complaint
suppression is enabled; the configuration set inherits it. Fresh controlled marker
`9aa30b08f1f8` proves two-second admin Inbox delivery with SPF/DKIM/DMARC pass,
custom MAIL FROM, direct links/no tracking image, and both failure types delivered
through the exact SNS topic. Archiving/Auto Validation remain disabled.

For the initial cutover, the owner required commits to remain unpublished. The
owner subsequently authorised normal GitHub PR/CI reconciliation; publishing the
source does not itself replace the serving private image. The adapted checkpoint is
`a41e7277ac125e86f5a3aae258b26dc52a7d3bfc`, based on that exact production release:
three provider-review strings, an existing read-only assertion and evidence docs.
All 199 affected regressions pass. A private local image preserves every production
base layer/platform and adds only the two reviewed wording files; its isolated
deployment checks pass. Image ID
`sha256:d8257f6ac5927324b0f584f31239236d1eb29e053beb474c77d9a8bae6305771`;
archive SHA-256 `b243a356d3eff43d668fea6c84de6ec1d4ce0048ab7ed4583a17b3611e55557e`.
Automatic approval review initially rejected the full image/source transfer without
exact payload/destination approval. The owner subsequently approved that exact
private transfer and release path; execution and verified archive are recorded above.
The protected artifact/rollback directory is
`/home/deploy/.config/jsk/ses-release-a41e727/`.

Use the refreshed SMTP-only rollback
`/home/deploy/.config/jsk/postmark-smtp-rollback-20261031.json` (mode 0600), not the
dated 24 October baseline, after checking current live settings. Keep the existing
checkout-reconciliation timer running; hold only reminder dispatch for the approved
replacement. No schema change, migration or unrelated worktree release is needed.
The earlier setup sequence and 24 October baseline below remain historical evidence.

Initial 24 October read-only production inventory confirmed release
`4d92b57588d0714eb2e9b48661df1878824953d0`, a healthy web container, standard Django
SMTP, `smtp.postmarkapp.com:587`, STARTTLS, a ten-second timeout and sender/server
address `admin@jaishrikrishnajewellery.com`. Cloudflare is authoritative DNS; root MX
is `smtp.google.com`, root SPF authorises Google, and DMARC is `p=reject` with relaxed
alignment. Preserve these and existing Postmark DKIM/`pm-bounces` records.

1. Prepare SES in Mumbai (`ap-south-1`) alongside Postmark. Create the domain identity
   with Easy DKIM RSA 2048 and enabled signatures. Publish its three CNAMEs as DNS
   only. Use the previously unused `ses-bounce.jaishrikrishnajewellery.com` for custom
   MAIL FROM: MX priority 10 to `feedback-smtp.ap-south-1.amazonses.com`, plus TXT
   `v=spf1 include:amazonses.com ~all`. These are additions, not root MX/SPF changes.
   Wait for identity/DKIM/custom MAIL FROM verification and SES production access.
2. Confirm the selected pricing mode before metered use; new SES regions may default
   to Essentials. Do not enable paid upgrades, dedicated IPs, archiving or additional
   deliverability products implicitly. Configure a default transactional configuration
   set with delivery/failure evidence, monitored bounce/complaint notifications,
   suppression handling and explicit disabling of open/click tracking, including
   applicable VDM settings. Existing `X-PM-*` headers do not configure SES tracking.
   Review/import applicable Postmark suppressions and define owner failure recovery.
   `jsk-failure-alerts` now publishes hard bounces, complaints, delivery delays,
   rejects and rendering failures to Standard SNS topic `jsk-ses-failures`. Its
   confirmed email endpoint is the business admin mailbox; the publish policy permits
   only the exact SES configuration set and source account. Bounce and complaint
   simulator events reached the Inbox (marker `f113e40c4751`). Direct feedback
   forwarding remains enabled as a second route; its simulator bounce landed in Spam,
   so include Spam in manual mailbox review rather than weakening spam protection.
   Review SNS event metadata and notification mailbox copies in the provider retention
   inventory; no message archive was enabled. Keep opens and clicks unselected.
   For failures, correlate the SES message ID and recipient privately with application
   evidence. Keep hard-bounce/complaint recipients suppressed and use a verified
   showroom/contact route for recovery. Correct addresses through existing owner
   workflows before a bounded resend; a delay or ambiguous acceptance is not permission
   to send a duplicate. Notification duplicates do not justify transactional resends.
3. Create restricted regional SMTP credentials, keeping secrets outside the repository
   and chat. Permit `ses:SendRawEmail` only for the verified identity ARN and the
   exact `jsk-transactional` configuration-set ARN in Mumbai, with `ses:FromAddress`
   restricted to `admin@jaishrikrishnajewellery.com`. The configuration-set resource
   is required even when assigned by default; identity-only permission was rejected.
   Keep console login disabled for this SMTP user. Production-container connectivity to
   `email-smtp.ap-south-1.amazonaws.com:587` was verified with certificate-validated
   STARTTLS/TLS 1.3, without authentication or sending. Authentication and actual
   message acceptance/delivery tests remain separate gates. Authentication (235) and
   controlled admin-inbox delivery have now passed, including SPF/DKIM/DMARC and direct
   links/no tracking image. Keep production SMTP unchanged until all other gates pass.
   The deploy user's protected candidate is `~/.config/jsk/ses-smtp-ap-south-1.env`;
   the SMTP-only Postmark snapshot is
   `~/.config/jsk/postmark-smtp-rollback-20261024.json` (both mode 0600). Revalidate
   current live settings before using that dated snapshot; do not restore it wholesale
   over the production environment or expose either file in a log/Compose dump.
4. Review current-provider privacy/disposition wording and retained Postmark copies.
   Run affected regressions and controlled recipient tests for all email workflows.
   Inspect received DKIM/SPF/DMARC results and direct private links/no tracking pixels;
   exercise simulator bounce/complaint and recovery paths. SMTP acceptance is not
   inbox delivery. Do not generate customer messages or financial mutations merely
   to test transport. Use an isolated reviewed release if code changes are needed;
   never deploy the accumulated unrelated worktree.
5. Before cutover, record the exact live image/release, health and financial-exception
   baseline, timer/cron inventory and current SMTP settings. Make a protected rollback
   copy of the server configuration and retain working Postmark credentials. Hold
   scheduled email dispatch and let in-flight sends finish; do not pause payment
   processing or provider reconciliation as an email-migration shortcut.
6. Edit only reviewed SMTP values in the protected environment (and any separately
   reviewed email-only release identity). Keep the sender unchanged. Validate Compose
   without printing secrets; run Django deployment checks. Recreate only `web` with
   `up -d --force-recreate --no-deps web`. A plain `restart` does not reload environment
   values. Keep Caddy running and verify public/readiness routes, TLS, sessions,
   existing payment/webhook paths and controlled SES delivery before resuming dispatch.
   Do not run `migrate` for an SMTP-only switch or replace the environment from an example.
7. If checks fail, restore only the saved SMTP values (and compatible email-only image
   if changed), recreate `web`, then verify Postmark recovery. Review ambiguous sends
   before retrying: do not automatically dual-send or claim exactly-once delivery.
   Observe real delivery/failure evidence through an agreed acceptance period before
   retiring Postmark credentials, DNS or retained data. No database restore is involved.

Remaining gates and execution evidence are tracked in FUTURE_WORK.md and STATUS.md.
No production SMTP switch is implied by DNS setup or a successful TLS handshake.

### 7. Propagate configuration-only changes

Validate configuration changes through the same review and change-window controls.
`restart` does not load changed environment values:

| Changed item | Required action after validation |
| --- | --- |
| Django/provider environment | `up -d --force-recreate --no-deps web`, then readiness and provider-specific verification |
| `ACME_EMAIL` or Caddy environment | `up -d --force-recreate --no-deps caddy`, then inspect ACME/TLS logs |
| `deploy/Caddyfile` | Validate with the pinned Caddy image, recreate Caddy, then test redirects/TLS |
| Managed database CA | Validate with OpenSSL, install mode `0644`, recreate `web`, then test readiness |
| Database/SMTP/provider credential | Activate replacement, recreate `web`, verify the affected path, then revoke the old credential |
| Application code/dependency | Build and deploy a new immutable release; never edit the running container |

### 8. Roll back safely

If the schema remains compatible, edit `.env.production` to restore the recorded
previous `APP_IMAGE` and `APP_RELEASE`, then replace `web`, wait for readiness, and
recreate Caddy as in the deployment step. Repeat health, smoke, liability, and
exception checks and preserve the failed release's logs and provider identifiers.

Do not run reverse migrations casually, and do not restore an older database merely
to roll back code. If the applied schema is incompatible with the previous image,
keep traffic stopped or use the migration-specific compatible image/recovery plan.
Any database timeline change after financial events requires full provider-event and
denomination-specific reconciliation.

## Pre-deployment gate

Run this check using the target environment's real non-secret configuration and
secret injection:

```powershell
python manage.py check --deploy --fail-level ERROR
```

The command must have no errors. Review every warning explicitly; a warning is not
automatically safe. The project's custom checks reject mock or unsupported payment
gateways, missing selected-payment credentials, non-delivering email backends, wildcard hosts,
and non-HTTPS CSRF origins. They also warn if `APP_RELEASE` is unknown or database TLS
is not required.

Then inspect the schema operation without mutating the database:

```powershell
python manage.py showmigrations --plan
python manage.py migrate --plan
```

Review migrations for locks, table rewrites, long data transformations, and backward
compatibility with the currently running image. For a large table or a non-backward-
compatible change, stop and create a migration-specific rollout and recovery plan.

The final gate requires:

- Green CI for the exact commit.
- Approved image digest and deploy-check output.
- A healthy staging rollout of that same image.
- A current restorable backup or confirmed PITR recovery point.
- A reviewed migration plan.
- An on-call operator and business reconciler for the deployment window.
- A defined rollback image.

## Razorpay Live Mode activation gate

Live-key acceptance is deliberately mode-bound. Migration
`schemes.0011_razorpay_gateway_mode` labels every historical Razorpay contribution
and webhook as `test`, which is truthful because earlier releases rejected Live keys.
New orders and events retain their mode, callback verification rejects a cross-mode
contribution, and webhook event uniqueness includes the provider mode. This migration
does not alter amounts, payment status, Scheme Rates, allocations, or liabilities.

First deploy the supporting release while production still uses Test Mode:

1. Add `RAZORPAY_MODE=test` beside the existing Test credentials.
2. Record the image identity, financial baseline, and current database recovery point.
3. Run the deploy check and review the `0011` migration plan.
4. Apply the migration once, deploy the web service, and confirm Test checkout,
   callback verification, signed webhook processing, financial exceptions, and CSV
   export still pass. The export now includes `gateway_mode` for reconciliation.

Do not activate Live Mode until all of these account-side controls are confirmed:

- Razorpay has activated the merchant account and approved the owned website.
- The owner generated Live API credentials and stored them only in the production
  secret location. Test and Live credentials are never mixed.
- In the Razorpay **Live Mode** dashboard, the stable webhook URL is
  `https://jaishrikrishnajewellery.com/scheme/payments/razorpay/webhook/`, its secret
  is distinct from the API key secret, `payment.captured` is enabled, and a monitored
  failure-alert email is configured.
- Payment Capture is configured to auto-capture. The application creates entitlement
  only after Razorpay reports the exact local order, INR amount, and `captured` state.
- Better Stack/Linode and the financial-exception heartbeat reach named responders.
- A business owner is assigned to daily reconciliation and an incident owner can
  pause new Checkout exposure without disabling Razorpay callback/webhook handling.
- The payment-error refund and dispute procedures below are accepted. General refunds
  of already credited scheme contributions remain unsupported because the application
  has no compensating payment-reversal workflow.

Use a short controlled cutover with no customer checkout in progress:

1. Set `PAYMENT_INITIATION_KILL_SWITCH=True`, validate Compose, and recreate `web`.
   Keep `PAYMENT_GATEWAY=razorpay` and all mode-matched credentials configured.
   Confirm Pay/Resume actions disappear while callbacks, webhooks, reads, statements,
   owner views, live, and ready remain healthy.
2. Confirm Razorpay has no unresolved Test payment for a locally pending order. Do not
   edit a pending contribution merely to pass this gate.
3. In `.env.production`, atomically set:

   ```dotenv
   PAYMENT_GATEWAY=razorpay
   PAYMENT_INITIATION_KILL_SWITCH=True
   RAZORPAY_MODE=live
   RAZORPAY_KEY_ID=rzp_live_...
   RAZORPAY_KEY_SECRET=<live-api-key-secret>
   RAZORPAY_WEBHOOK_SECRET=<separate-live-webhook-secret>
   ```

4. Before changing the running service, exercise the candidate configuration without
   printing credentials:

   ```bash
   docker compose --env-file .env.production -f compose.production.yml \
     run --rm --no-deps web python manage.py check --deploy --fail-level ERROR

   docker compose --env-file .env.production -f compose.production.yml \
     run --rm --no-deps web python manage.py check_razorpay_live_readiness

   docker compose --env-file .env.production -f compose.production.yml \
     run --rm --no-deps web python manage.py check_financial_exceptions
   ```

   Readiness blocks unknown/mixed credentials, missing mode labels, failed Live
   webhooks, and any pending contribution created in another mode (with or without a
   provider order). If it blocks, restore Test
   Mode and reconcile the named condition; never bypass the command or rewrite
   provider references.
5. After every gate passes, set `PAYMENT_INITIATION_KILL_SWITCH=False`, validate
   Compose, recreate `web`, wait for health, recreate Caddy so it resolves the
   replacement upstream, and confirm live/ready return the expected release.
6. Sign in with one controlled real customer account and complete one legitimate
   minimum-value metal contribution. Confirm the UI explicitly says **Live payment**,
   the Dashboard payment is captured, the local contribution has `gateway_mode=live`,
   the signed Live webhook is processed once, exactly one metal allocation uses the
   pre-payment Scheme Rate lock, and liabilities change by exactly that allocation.
   Treat this as a real contribution; do not refund it merely to clean up a smoke test.
7. Export contributions and reconcile mode, payment ID, order, amount, INR currency,
   captured status, local status, allocation, and Dashboard settlement. Re-run the
   financial-exception and readiness commands, inspect logs, and retain redacted
   evidence.

#### Completed Live acceptance evidence — 2026-08-31

- Production image/release: `5fa726b2d76666abe7063f8b48125d6869566ecc`;
  `schemes.0011_razorpay_gateway_mode` was already applied.
- Live readiness passed with no pending contribution from another mode, missing mode
  stamp, or failed Live webhook. Financial exceptions reported zero paid-unallocated,
  failed-webhook, and mismatched-webhook records.
- Two real Live contributions were captured for INR `150.00` and INR `200.00`.
  Their signed `payment.captured` events were each processed once; the corresponding
  `payment.authorized` events were safely retained as ignored.
- Each captured contribution created exactly one immutable gold allocation using its
  pre-payment Scheme Rate lock: `0.008973` g and `0.012229` g, totalling `0.021202` g.
- Two additional Live orders were still in Razorpay `created` state with zero attempts,
  zero payments, and their full amounts due. After provider verification, their local
  pending contributions were retired through `fail_contribution`; no provider or
  financial record was deleted.
- Final reconciliation: zero pending Live contributions, two paid and two safely failed
  Live contributions, two processed capture webhooks, `0.021202` g Live gold allocation,
  `0.329272` g total outstanding gold, and a clean financial-exception check.
- Paid external monitoring and rotation rehearsals remain explicitly deferred under
  `FW-PROD-002` and `FW-PROD-003`; webhook recovery remains `FW-PAY-003`.

### Payment operations circuit-breaker deployment (`FW-PAY-004`)

Migration `schemes.0013_payment_operations_control` adds one singleton control and
seven weekly schedule rows. It seeds Monday–Saturday 09:00–21:00 and Sunday
09:00–13:00 in the configured `Asia/Kolkata` timezone, but leaves the schedule
disabled. Applying the migration therefore does not close an otherwise available
production Checkout. It does not modify any contribution, provider reference, locked
Scheme Rate, allocation, webhook event, redemption, or liability.

Before deployment, retain a current recovery point and the usual financial baseline.
Then run the candidate gates:

```bash
docker compose --env-file .env.production -f compose.production.yml \
  run --rm --no-deps web python manage.py migrate --plan

docker compose --env-file .env.production -f compose.production.yml \
  run --rm --no-deps web python manage.py check --deploy --fail-level ERROR

docker compose --env-file .env.production -f compose.production.yml \
  run --rm --no-deps web python manage.py check_financial_exceptions
```

The migration plan must show only `schemes.0013`. Apply it once, confirm it appears as
`[X]`, then deploy the healthy candidate. After cutover run:

```bash
docker compose --env-file .env.production -f compose.production.yml \
  exec -T web python manage.py check_payment_operations

docker compose --env-file .env.production -f compose.production.yml \
  exec -T web python manage.py check_financial_exceptions
```

The first check must report `status=ok`, seven valid weekdays, the expected release,
and `schedule_enabled=false` on first deployment. Sign in as an owner and open
**Operations → Payment operations**. Review all seven windows and leave the schedule
disabled until a controlled test period is agreed.

For activation, first publish/review the current Gold and Silver Scheme Rates. Enable
the schedule with a mandatory reason. Verify during open hours that Pay is visible,
then use a short controlled manual Gold/Silver or Pause-All test to prove Pay/Resume
disappear while live/readiness and the webhook endpoint remain available. Clear the
manual pause with a second reason. Test the exact closing boundary separately without
creating a real contribution merely for the smoke.

For an owner-driven volatility pause, use the same page; no container recreation is
required. For an application-control incident, set this in `.env.production`:

```dotenv
PAYMENT_INITIATION_KILL_SWITCH=True
```

Validate Compose and recreate only `web`. Do not clear `PAYMENT_GATEWAY`, remove
Razorpay credentials, disable Caddy, or disable the Razorpay webhook. After the
incident, review provider/local pending orders and publish current rates before
setting the variable back to `False` and recreating `web` again.

#### Completed rollout and schedule-activation evidence — 2026-08-31

- Managed PostgreSQL recovery point: 2026-08-31 11:00 AM IST. Rollback image/release:
  `jsk-savings:c3e8c4618c9ec160fcdf764b38d05de6b7e5df9e`.
- Production image/release: `jsk-savings:e027b9ae1550c314584c551eb3da31d5529ea544` /
  `e027b9ae1550c314584c551eb3da31d5529ea544`; locally built image ID
  `sha256:a9e021ceed8b9d08d64b42fc71a3af0cd6c95facdc8f81d4fb90ed1d8623e558`.
- The reviewed migration plan contained only
  `schemes.0013_payment_operations_control`; it applied successfully. The baseline
  was seven customers, seven scheme accounts, zero pending Razorpay contributions,
  zero INR principal/earned bonus, `0.329272` g gold, and zero silver.
- Live/readiness returned the expected release. Payment operations reported
  `status=ok`, `kill_switch=false`, `schedule_enabled=false`, both metals `OPEN`, and
  zero pending exposure. Razorpay Live readiness and financial exceptions both
  reported `status=ok` with no missing/cross-mode records, failed webhooks,
  paid-unallocated records, or mismatches.
- The owner exercised audited Pause All with a customer-safe notice. Customer Pay was
  unavailable while the owner restriction warning remained visible; no Checkout or
  provider order was created. A second audited change restored both metals to `OPEN`,
  and the financial-exception check remained clean.
- After current-day Gold and Silver Scheme Rates were published and reviewed, the
  owner enabled the weekly schedule with an audit reason. Its exact closing and
  reopening boundary worked as expected; the schedule remains enabled in production.

### Expired Checkout operations (FW-PAY-008, deployed 26 October 2026)

Accepted in production on 26 October 2026 as merged release
`d0e5dd1897debb054d99647d6ea16575d08b1a48`, from protected-main CI
`40283793237` and immutable image
`ghcr.io/rajeshr188/jsk-savings@sha256:00caf93dfa3933cc662f39745c4a3bd823768b523a73163d71bb60c474e0ec6d`.
The exact published image passed synthetic PostgreSQL 18.6 restore/upgrade and
payment/recovery acceptance. The owner accepted the checkpoint 25 October 2026,
13:37:12 IST, which came from Linode cluster `updated` metadata; an exact latest
backed-up WAL timestamp was not independently established. No production restore
was performed. A restore would require reconciliation of all subsequent financial
events, rather than discarding received payments or the later incident repair.

The audited initiation pause, zero unresolved attempts, exact single-migration plan,
unchanged financial-source hashes/separate liabilities and health gates passed.
Seven customer/owner pages rendered within database read-only transactions with
provider calls forbidden; original controls were restored exactly and all grades
reopened. The previous release/image remains the rollback pair. New request evidence
and the additive schema must survive any application rollback.

The root-owned heartbeat configuration and systemd units were verified. Real healthy
inspection, controlled reported-failure incident `1038686832`, missed-heartbeat
incident `1038693817`, and both recoveries were observed; failure/missed-run and
recovery emails arrived in the existing business inbox. The five-minute timer is
enabled/active after testing, with the temporary resume safeguard stopped. Inspection
never applied financial reconciliation or created a payment. See STATUS.md for the
validation evidence; the operational rules below remain authoritative.

The combined 26 October prevention/recovery release adds migration
`schemes.0021_checkout_idempotency`. It creates retained submission/request/recovery
evidence and a partial uniqueness constraint covering unresolved Razorpay attempts
per agreement, including flexible plans and cross-mode/month attempts. It performs
no historical backfill. Preflight must find no agreement with multiple PENDING or
PAID_UNALLOCATED Razorpay rows; reconcile such rows through existing verified
workflows before migration. Never delete or arbitrarily fail rows to pass preflight.

Rehearse the exact release image against PostgreSQL 18.6 with synthetic historical
data and compare all source payments, allocations, rates and liabilities through the
upgrade. Exercise duplicate/stale form submission, simultaneous tabs, lost create
response, signed owner identity recovery, ordinary/late captures and unchanged rate
locks. Old browser forms without signed context fail safely and require a fresh
review from the customer's plan. Do not create a real payment as a release probe.

Retained checkout evidence refuses migration reversal. Preserve the additive schema
and history on application rollback. The old application does not honor durable
request holds, so keep new-payment initiation paused during rollback and until a
corrected version is verified; callbacks/webhooks must remain available. Do not
restore the database or discard request/audit evidence to resume the old flow.

For an uncertain create response without a local order ID, use the private payment
record's Recover provider order identity action. Obtain the candidate from the
provider investigation; inspect it, review and confirm. A fresh provider read must
match the original receipt/token/contribution/amount/currency/time. This binds only
identity and keeps checkout closed. Then use verified capture recovery or inspected
untouched-order reconciliation as appropriate. An unknown/no-order outcome remains
held for provider investigation; no local override asserts that money was not sent.

The queue and `check_financial_exceptions` now include `expired_checkouts` for all
modes as soon as a stored deadline expires. Normal unexpired checkouts are excluded.
The private payment detail and exception entry link to owner review. GET is read-only;
Check provider and Apply are CSRF-protected POSTs. Apply requires the current owner's
signed ten-minute review and explicit confirmation, re-fetches provider order and
payments, then uses the existing audited service. Attempted, mismatched, captured,
unknown or cross-mode results stay for investigation/verified payment recovery.
A received payment is never inferred to have failed from its browser deadline.

Operator dry-run (new default: deadline plus five minutes, not 24 hours):

```bash
docker exec jsk-savings-web-1 python manage.py reconcile_abandoned_razorpay_orders \
  --contribution-id=REVIEWED_ID
```

Review the result before an explicitly authorized exact-ID `--apply`; the apply pass
inspects the provider again. `--older-than-hours` is an optional additional age filter.
`--grace-minutes=0` allows urgent inspection after expiry without weakening provider
predicates. `--summary-only --fail-on-pending` is for monitoring, not automatic closure.
It fails if any scoped expired backlog remains, even beyond the provider batch or
outside the configured mode. Errors are redacted and never close a failing candidate.

For activation, release the isolated application image through normal CI/image gates
first; the monitoring component itself adds no further migration. Install `deploy/check-expired-checkouts.sh` and
`deploy/systemd/jsk-checkout-reconciliation.{service,timer}` from that reviewed release
into their documented `/opt/jsk/app/deploy/` and `/etc/systemd/system/` locations.
The service uses `/usr/bin/docker exec`, a private runtime Docker configuration and
a maximum of three order inspections per run (six provider requests). This respects
ProtectHome and the four-minute timeout. Both aggregate financial checks and provider
inspection must pass before its shared heartbeat reports health. Keep any older
financial heartbeat timer disabled when sharing this destination, so another job
cannot mask an inspection failure.

Configure a dedicated heartbeat with a five-minute period and six-minute monitoring
grace for this bounded inspection job. Use the existing Better Stack account and
verify/reuse or add its `JSK financial exceptions` heartbeat, following the canonical
Better Stack monitoring section above. No additional monitoring account is needed.
On 24 October 2026, this heartbeat was created in the verified JSK account/team
`t585600` as heartbeat `516408`; its saved five-minute/six-minute settings and email
notification were read back. It remains Pending until the first real job ping.
Its URL is configured in the root-only production file below; no URL belongs in
release evidence, repository files or command output. No timer was enabled and no
notification-delivery or missed-run/recovery exercise is yet claimed.
Verify its escalation recipients and email notification. These incidents go to the
owner/operator and concern expired provider checkouts; they are distinct from
customer reminders about agreed unpaid contributions. Store only
`FINANCIAL_EXCEPTIONS_HEARTBEAT_URL` in
`/opt/jsk/secrets/observability.env`, owned by root with mode 0600; systemd reads the
file before dropping privileges. Never commit or display its secret URL. The service
requires it by default and exits with `delivery=unconfigured` if absent. The wrapper
sends only success/failure POSTs, with no body or customer/provider/payment fields.
`/fail` signals either financial findings or failed provider inspection. A delivery
failure exits 69, allowing the missing-heartbeat alarm to detect a broken channel.
The explicit `REQUIRE_FINANCIAL_HEARTBEAT=false` override supports a deliberately
reviewed server-only setup; it does not establish external alert delivery.

After installing/configuring, run `systemd-analyze verify`, daemon-reload, one manual
service run and enable the timer. Verify active/scheduled status, successful provider
inspection, the monitor's received heartbeat, a controlled failure notification,
a deliberately missed heartbeat, and recovery. Do not create a real payment solely
for this acceptance test. Rollback disables the new timer before reverting the image;
retain all reconciliation audits and financial records. Never restore an old database
as an application rollback. The on-site owner still resolves held cases; this job is
inspection and notification, not automatic refunds or entitlement overrides.

Source: [Better Stack heartbeat and explicit failure monitoring](https://betterstack.com/docs/uptime/cron-and-heartbeat-monitor/).

### Abandoned Razorpay order deployment and operation (`FW-PAY-002`)

The release introduces `schemes.0012_abandoned_razorpay_orders`. Its approved plan
adds the `ABANDONED` contribution choice, expands the paid-confirmation constraint to
permit that unpaid terminal state, and adds the payment-order reconciliation audit
action. It does not delete, rewrite, or backfill a contribution.

After the normal recovery-point, candidate-image, baseline, migration-plan, migration,
health, readiness, and financial-exception gates, inspect aged orders from the running
web container. Dry-run is deliberately the default and makes provider reads without
changing the database:

```bash
docker compose --env-file .env.production -f compose.production.yml \
  exec -T web python manage.py reconcile_abandoned_razorpay_orders \
  --older-than-hours=24
```

Review every line against Razorpay Dashboard. `ELIGIBLE_FOR_ABANDONMENT` requires all
of the following from the mode-matched API credentials: order status `created`, zero
attempts, zero associated payments, zero amount paid, the expected INR amount, and the
full amount still due. `REVIEW_REQUIRED` remains pending and must not be overridden.
Provider/API errors make the command fail and leave the affected contribution open.

Only after review, apply the same bounded selection:

```bash
docker compose --env-file .env.production -f compose.production.yml \
  exec -T web python manage.py reconcile_abandoned_razorpay_orders \
  --older-than-hours=24 --apply

docker compose --env-file .env.production -f compose.production.yml \
  exec -T web python manage.py check_financial_exceptions
```

The apply pass re-reads Razorpay, marks only eligible local contributions
`ABANDONED`, and appends an immutable audit event containing the provider snapshot.
It retains the Razorpay order ID and locked Scheme Rate. The customer no longer sees
a resume link for that contribution; a once-per-month account may start a replacement
order, while flexible attempts remain independent.

Razorpay's Orders API has no order-cancellation operation: application-side
`ABANDONED` does **not** make the remote order unpayable. Run this process during an
observed window. If a late signed capture arrives, the application intentionally
creates a failed-webhook financial exception rather than silently issuing entitlement.
Suspend the affected checkout, reconcile the order/payment/amount and any replacement
contribution, and follow the approved no-entitlement payment-error refund procedure.
Never delete the old contribution, provider order, reconciliation audit event, or
failed webhook.

#### Expired pending Checkout incidents

Expiry is a local deadline, not a provider payment result. An expired pending
attempt suppresses the customer's primary payment action even on a flexible plan
with a later successful payment; any pending Razorpay order also blocks showroom
cash recording. The existing financial-exception queue/check does not include these
attempts, so an `ok` result alone does not rule out this customer-access incident.
Inspect pending exposure with `check_payment_operations` and the exact owner's
payment record; independently review the provider order and its payments.

The reconciliation command's default age is **24 hours from creation**, not the
Checkout deadline. For an urgent younger incident, select an explicit reviewed age
and target the exact contribution through
`reconcile_abandoned_razorpay_contribution(contribution_id=..., cutoff=..., apply=False)`
in the running image's Django shell. Verify customer/agreement, Live/Test mode, amount,
order ID and expired deadline before the dry-run. The existing CLI has no exact-ID
filter; do not use its bulk `--apply` merely to unblock one customer.
Only after an `ELIGIBLE_FOR_ABANDONMENT` dry-run, use the same exact ID and reviewed
cutoff with `apply=True` and a specific owner-authorized reason. The service re-reads
the provider, locks the agreement/contribution, preserves the locked rate and writes
the audit event. Any changed/uncertain provider result must remain for investigation.

Afterward, verify the audit ID, restored customer action and cash blocker, unchanged
successful payments and exact-grade entitlement, remaining pending exposure and
financial checks. Never create a real payment to test the restored button. The
24 October 2026 incident used this workflow for contribution 20, recorded audit 104,
preserved paid contribution 21 and 0.037169 g 22K entitlement, and left zero pending
Razorpay contributions. A read-only customer-view render verified the pay link.
`FW-PAY-008` tracks the missing owner recovery UI, overdue-attempt visibility and
bounded inspection/alert job; none is installed or enabled by this runbook update.

#### Completed production rollout evidence — 2026-08-31

- Recovery point: 2026-08-30 12:00 PM IST. Rollback image/release:
  `jsk-savings:5fa726b2d76666abe7063f8b48125d6869566ecc`.
- Production image/release: `jsk-savings:c3e8c4618c9ec160fcdf764b38d05de6b7e5df9e` /
  `c3e8c4618c9ec160fcdf764b38d05de6b7e5df9e`; locally built candidate image ID
  `sha256:d94f1063b5e362e2da2d4934d722623a60a7412efb606f462fb331f4f36343df`.
- The reviewed plan contained only `schemes.0012_abandoned_razorpay_orders`; it applied
  successfully and every scheme migration through `0012` is recorded as applied.
- Reported Live/Ready checks returned the expected release. The running gateway
  remained Razorpay Live; Live readiness and financial exceptions returned `ok` with
  no missing modes, cross-mode pending order, failed webhook, paid-unallocated record,
  or mismatch.
- The first production reconciliation remained a dry run and reported zero pending or
  aged candidate, zero review requirement, zero abandonment, and zero error. No
  contribution or provider order was changed by that check.

### Razorpay webhook recovery deployment (`FW-PAY-003`)

[ADR-0006](decisions/ADR-0006-razorpay-webhook-recovery.md) introduces additive
migration `schemes.0014_paymentwebhookevent_failure_code_and_more`. It adds a safe
failure code, the `REVIEW_REQUIRED` webhook state, append-only processing attempts,
and a webhook-recovery audit action. It does not backfill, delete, confirm, allocate,
or otherwise mutate an existing financial record. The previous application image is
schema-compatible with these additions, so the normal rollback image remains usable.

Before migration, record the recovery point, rollback image/release, candidate image
identity, financial baseline, and these checks from the candidate image:

```bash
docker compose --env-file .env.production -f compose.production.yml \
  run --rm --no-deps web python manage.py check --deploy --fail-level ERROR

docker compose --env-file .env.production -f compose.production.yml \
  run --rm --no-deps web python manage.py migrate --plan

docker compose --env-file .env.production -f compose.production.yml \
  exec -T web python manage.py check_financial_exceptions

docker compose --env-file .env.production -f compose.production.yml \
  exec -T web python manage.py check_razorpay_live_readiness
```

The reviewed migration plan must contain only `schemes.0014`. Apply it once, verify
that every migration through `0014` is marked `[X]`, recreate `web`, then verify the
expected release through Live/Ready and rerun both financial checks. Do not change
Razorpay mode or credentials as part of this release.

The owner exception queue now links failed or review-required captured-payment events
to **Review recovery**. Always use **Inspect provider state** first and record a
specific incident/reconciliation reason. **Apply verified recovery** performs a fresh
provider read and remains blocked unless payment ID, order ID, INR amount, captured
state, mode, and local contribution all match. It cannot override abandoned, failed,
unknown, or mismatched records. Those remain in the manual refund/reconciliation
boundary below.

Prove the complete review/dry-run/apply path first in an isolated Razorpay Test-mode
environment. In production, use Razorpay Dashboard's individual-event retry only for
an already-processed Live `payment.captured` event; expect HTTP `200`, no additional
allocation, and an `ALREADY_FINAL` processing attempt. Do not manufacture a Live
mismatch or pay real funds merely to create a recovery exception. Compare contribution,
allocation, webhook, attempt, audit, and financial-exception counts before and after.

The response contract is deliberate: unauthenticated/malformed/conflicting requests
return `400`; signed permanent mismatches are durably accepted as `REVIEW_REQUIRED`
with `200`; transient application failures return `503` for provider retry. Never
paste signatures, API credentials, full webhook bodies, or customer details into
deployment evidence.

#### Production rollout evidence — 2026-08-31

- Recovery point: 2026-08-31 11:30 AM IST. A preflight timestamp audit found zero
  customer, scheme-account, contribution, allocation, webhook, Scheme Rate, audit,
  redemption, or payment-control writes after that point. The one pending Gold
  contribution was created at 10:53 AM IST and was therefore included.
- Rollback image/release:
  `jsk-savings:e027b9ae1550c314584c551eb3da31d5529ea544` /
  `e027b9ae1550c314584c551eb3da31d5529ea544`, image ID
  `sha256:a9e021ceed8b9d08d64b42fc71a3af0cd6c95facdc8f81d4fb90ed1d8623e558`.
- Candidate image/release:
  `jsk-savings:69eecf9cdebb4f660ae4ed898476e18a6fe32905` /
  `69eecf9cdebb4f660ae4ed898476e18a6fe32905`, image ID
  `sha256:0f64b88ffb9657562d99f18ef333b7c8557d13cadf2acebde457855bd1a25578`.
- GitHub PR #27 was mergeable and all branch-push/PR Django and container checks
  passed before merge. The candidate deploy check had no errors; the existing
  HSTS include-subdomains/preload settings produced only `W005`/`W021` warnings.
- The reviewed plan contained only `schemes.0014`; it applied successfully, every
  schemes migration through `0014` is `[X]`, and the final plan reports no pending
  migration.
- Web became healthy before Caddy validation/recreation. External Live and Ready
  returned `200` with the expected release; HTTP redirected to HTTPS and `www`
  redirected once to the canonical apex. The authenticated owner exception route is
  present and redirects anonymous requests to login.
- Pre- and post-release liabilities matched: six customers, seven scheme accounts,
  INR `0.00` cash principal, INR `0.00` earned cash bonus, `0.329272` g Gold, and
  `0.000000` g Silver. The new attempt ledger began at zero.
- Financial exceptions and Razorpay Live readiness returned `status=ok` with no
  paid-unallocated, failed/mismatched webhook, missing/cross-mode, or failed-Live
  record. The abandoned-order dry run had zero candidates/errors. Payment operations
  remained unchanged: kill switch false, schedule disabled, Gold/Silver open, one
  pending Gold order, and no pending Silver order.
- Bounded web/Caddy logs showed normal Gunicorn startup, valid TLS service, and the
  successful health requests; no application, database, or certificate error appeared.
  Caddy's informational HTTP/3 receive-buffer message remains a host-tuning concern,
  not a failed deployment gate.
- No artificial Live mismatch or payment was created. The isolated Test-mode recovery
  exercise and an already-processed Live event replay remain explicit acceptance items.

### Grade-specific Scheme Rate deployment (`schemes.0015` and `0016`)

[ADR-0007](decisions/ADR-0007-grade-specific-metal-rates.md) introduces exact
`MetalGrade` contracts. This is a controlled-cutover migration, not a normal rolling
deployment. After `0015`, the old image cannot create a new metal allocation because
it does not populate the required grade field. Do not run old and candidate web
containers concurrently across this migration, and do not use the old image as a
write-capable rollback after the schema changes.

Before the maintenance window, use **Payment operations** to enable the audited
global pause and confirm no customer can create or resume Checkout. Reconcile or
retire every pending Razorpay order. Record the candidate/rollback image identities,
an immediately current managed PostgreSQL recovery point, the exact financial
baseline, and the owner/operator names. Then run from the candidate image against
the still-old schema:

```bash
docker compose --env-file .env.production -f compose.production.yml \
  run --rm --no-deps web python manage.py check --deploy --fail-level ERROR

docker compose --env-file .env.production -f compose.production.yml \
  run --rm --no-deps web python manage.py check_graded_metal_rates

docker compose --env-file .env.production -f compose.production.yml \
  run --rm --no-deps web python manage.py migrate --plan

docker compose --env-file .env.production -f compose.production.yml \
  exec -T web python manage.py check_financial_exceptions

docker compose --env-file .env.production -f compose.production.yml \
  exec -T web python manage.py check_razorpay_live_readiness
```

The grade preflight must report `status=ready` with zero paid-unallocated metal
payments, open Razorpay orders, allocation-contract mismatches, and
redemption-contract mismatches. The reviewed migration plan must contain only
`schemes.0015_graded_metal_rates` and
`schemes.0016_graded_rate_precision_labels`. Stop if either condition differs.

Keep the audited global pause enabled. Stop public traffic and the old application,
apply the migrations once with the candidate, and verify the new grade mappings
before reopening the stack:

```bash
docker compose --env-file .env.production -f compose.production.yml stop caddy web

docker compose --env-file .env.production -f compose.production.yml \
  run --rm --no-deps web python manage.py migrate --noinput

docker compose --env-file .env.production -f compose.production.yml \
  run --rm --no-deps web python manage.py check_graded_metal_rates

docker compose --env-file .env.production -f compose.production.yml \
  run --rm --no-deps web python manage.py showmigrations schemes

docker compose --env-file .env.production -f compose.production.yml \
  up -d --force-recreate --no-deps web
```

Wait for `web` to be healthy, validate/recreate Caddy using the standard procedure,
and require external Live/Ready responses to identify the candidate release. Rerun
the grade, financial-exception, Razorpay-live-readiness, payment-operations, and
financial-baseline checks. Verify in the owner UI that:

- every historical Gold account, locked rate, allocation, and redemption is labelled
  **24K Gold** with unchanged INR and six-decimal source quantities;
- every historical Silver record is labelled **999 Silver** and is unchanged;
- existing plans offer **22K Gold** and **999 Silver** for new enrolment, while legacy
  **24K Gold** is disabled unless the owner deliberately enables it;
- 22K, 24K, and 999 Silver have independent rate cards and liabilities; and
- customer pages show three-decimal grams while owner settlement/export paths retain
  exact six-decimal values.

Publish and review a `GOLD_22K_916` Scheme Rate before accepting a 22K payment. Keep
the global pause until the owner confirms the rate, plan offerings, a controlled
enrolment, and a non-chargeable/approved payment smoke path. Unpausing must be a
separate audited owner action.

#### Completed production rollout evidence — 2026-09-03

- Release `df5a7506bfa3c5b255faf284d3f90ef2ac7d7b28` was built as image
  `jsk-savings:df5a7506bfa3c5b255faf284d3f90ef2ac7d7b28`, identity
  `sha256:005c298d450e2682b50215d7ec78223302a41e78d30870629ca019f4a58ba2fb`.
  The previous release was `69eecf9cdebb4f660ae4ed898476e18a6fe32905`; it was
  retained only as evidence because it is not a safe write-capable rollback after
  the grade constraints are applied.
- The operator recorded the 2026-09-03 11:00 AM IST managed PostgreSQL recovery
  point. The pre-migration baseline was six customers, seven scheme accounts, zero
  pending Razorpay contributions, zero cash principal/earned bonus, `0.329272` g
  Gold, and zero Silver. The candidate old-schema preflight reported ready with zero
  unallocated metal payments, open orders, and allocation/redemption mismatches.
- The reviewed plan contained only `schemes.0015_graded_metal_rates` and
  `schemes.0016_graded_rate_precision_labels`. Both applied successfully with Caddy
  and the old web service stopped. Every Scheme migration through `0016` then
  reported applied, and the post-migration exact-grade check reported all mismatch
  and missing-grade counters at zero.
- The candidate web service became healthy, Caddy validated and was recreated, and
  external Live/Ready responses identified the exact candidate release. Financial
  exceptions and Razorpay Live readiness both reported `status=ok` with no pending
  cross-mode order, failed Live webhook, paid-unallocated contribution, failed
  webhook, or mismatched webhook.
- The owner reviewed independent 22K Gold, legacy 24K Gold, and 999 Silver rates and
  plan offerings before a separate audited reopening. A controlled INR `150.00`
  Live payment on contribution `14` used account grade, locked-rate grade, and
  allocation grade `GOLD_22K_916`; it locked INR `14667.0000`/g, allocated
  `0.010227` g, and its signed `payment.captured` webhook was `PROCESSED`. Final
  graded-rate, financial-exception, and Razorpay Live-readiness checks remained green.

If migration or candidate verification fails, keep traffic and payments stopped.
Prefer fixing and rolling forward with a compatible candidate. Restoring the recorded
database and old image is safe only if the operator proves no payment, webhook,
allocation, redemption, rate, enrolment, or other financial write occurred after the
recovery point; otherwise reconcile every later event before any restore. Never
reverse these migrations casually or relabel 24K history as 22K.

### Razorpay Checkout-expiry deployment (`schemes.0017`)

[ADR-0008](decisions/ADR-0008-razorpay-checkout-expiry.md) adds a required,
snapshotted application deadline to every pending Razorpay contribution. This is a
controlled cutover: after `0017`, an old image cannot create a valid pending Razorpay
row because it does not populate the deadline.

Set `RAZORPAY_CHECKOUT_EXPIRY_MINUTES=10` in the candidate environment. Before the
maintenance window, enable the audited global payment pause, record the image
identities and current managed-PostgreSQL recovery point, and require zero pending
Razorpay contributions. Dry-run provider reconciliation before applying it; do not
change an attempted or uncertain order merely to satisfy this gate.

```bash
docker compose --env-file .env.production -f compose.production.yml \
  exec -T web python manage.py shell -c \
'from schemes.models import Contribution; print("pending_razorpay=", Contribution.objects.filter(status="PENDING", payment_gateway="razorpay").count())'

docker compose --env-file .env.production -f compose.production.yml \
  exec -T web python manage.py reconcile_abandoned_razorpay_orders

docker compose --env-file .env.production -f compose.production.yml \
  run --rm --no-deps web python manage.py migrate --plan
```

The reviewed plan must contain only
`schemes.0017_contribution_checkout_expiry`. Stop Caddy and the old web service,
apply the migration once with the candidate, and start only the candidate web service.
Require it to become healthy before validating/recreating Caddy.

```bash
docker compose --env-file .env.production -f compose.production.yml stop caddy web

docker compose --env-file .env.production -f compose.production.yml \
  run --rm --no-deps web python manage.py migrate --noinput

docker compose --env-file .env.production -f compose.production.yml \
  up -d --force-recreate --no-deps web
```

After external Live/Ready checks identify the candidate, rerun financial exceptions,
Razorpay Live readiness, payment operations, and a zero-pending-order check. In a
controlled Test-mode environment, prove the page receives a bounded timeout, the
Resume action disappears after the snapshotted deadline, and an already verified
capture is still processed idempotently. Keep production paused until these checks
pass, then reopen through a separate audited owner action. Expiry is not provider
cancellation and never authorizes deleting or failing a pending contribution.

#### Completed production rollout evidence — 2026-09-03

- PR `#31` merged FW-PAY-005 as release
  `51c931a9de5b27349f781cd44670c41307479dfa`. The Linode candidate image was
  `jsk-savings:51c931a9de5b27349f781cd44670c41307479dfa`, identity
  `sha256:ebfe3fd78fc64e66e4f4e4bf8a42f8875835b9ce9fc4d98d56db040cc65f9c2a`;
  rollback evidence retained release/image
  `df5a7506bfa3c5b255faf284d3f90ef2ac7d7b28`.
- The operator recorded the 2026-09-03 1:00 PM IST managed PostgreSQL recovery
  point and enabled the audited global pause. All three exact grades reported
  `MANUAL_GLOBAL_PAUSE`, every per-grade pending count was zero, the aggregate
  pending Razorpay count was zero, and the Live provider reconciliation dry run
  found zero candidates, review cases, abandonments, or errors.
- The financial-exception, Razorpay Live-readiness, and exact-grade integrity checks
  all reported `status=ok`. The reviewed migration plan contained only
  `schemes.0017_contribution_checkout_expiry`; it applied successfully and every
  Scheme migration through `0017` reported applied.
- The candidate web service became healthy with
  `RAZORPAY_CHECKOUT_EXPIRY_MINUTES=10`, zero pending Razorpay contributions, and
  zero pending rows missing a deadline. Payment operations remained paused and all
  post-migration financial, Razorpay, grade, and reconciliation gates stayed green.
- Caddy was restored only after the candidate health gate. Public liveness and
  PostgreSQL readiness both returned `status=ok` with the exact candidate release.
  The owner then reopened payment initiation through a separate audited change; 22K
  Gold, legacy 24K Gold, and 999 Silver all reported `OPEN` with zero pending orders.
- No disposable Live order was created merely to exercise the timer. Confirm the
  snapshotted 10-minute deadline and normal completion/expiry behavior on the first
  legitimate post-release contribution without weakening provider reconciliation.

### In-store cash contribution deployment (`schemes.0018`)

[ADR-0009](decisions/ADR-0009-in-store-cash-contributions.md) introduces a non-null
payment channel plus immutable cash receipt/reversal ledgers. Treat this as a
controlled stop-the-old-web migration because the old image does not populate the new
channel column. This is not a Razorpay mode change and must not alter API/webhook
credentials.

Prepare the candidate environment with the feature closed:

```dotenv
IN_STORE_CASH_CONTRIBUTIONS_ENABLED=False
IN_STORE_CASH_REVERSAL_HOURS=24
```

Record the rollback image/release, candidate image digest, operator, current managed
PostgreSQL recovery point, customer/account/liability baseline, and daily physical
cash cutoff. Enable the audited global payment pause and require zero pending
Razorpay orders before stopping traffic. The old production image cannot run the new
integrity command, so use the existing payment, grade, financial, and reconciliation
checks for the pre-migration gate.

```bash
docker compose --env-file .env.production -f compose.production.yml \
  exec -T web python manage.py check_payment_operations

docker compose --env-file .env.production -f compose.production.yml \
  exec -T web python manage.py reconcile_abandoned_razorpay_orders

docker compose --env-file .env.production -f compose.production.yml \
  run --rm --no-deps web python manage.py migrate --plan
```

The reviewed plan must contain only
`schemes.0018_in_store_cash_contributions`. It backfills existing Razorpay and Mock
history; it does not create a cash receipt or change any balance. Stop Caddy and the
old web process, apply the migration once with the candidate, and start only the
candidate web service.

```bash
docker compose --env-file .env.production -f compose.production.yml stop caddy web

docker compose --env-file .env.production -f compose.production.yml \
  run --rm --no-deps web python manage.py migrate --noinput

docker compose --env-file .env.production -f compose.production.yml \
  up -d --force-recreate --no-deps web

docker compose --env-file .env.production -f compose.production.yml \
  exec -T web python manage.py check_in_store_cash_contributions
```

Require a healthy candidate, all prior financial/Razorpay/grade gates, and an
`in_store_cash_check status=ok` result with the feature still disabled. Validate and
recreate Caddy, then confirm public Live/Ready identify the exact candidate release.
Review the owner customer-detail, contribution ledger, receipt, reversal warning, CSV,
and customer statement paths without creating disposable production money records.

After sign-off, set `IN_STORE_CASH_CONTRIBUTIONS_ENABLED=True`, validate Compose, and
force-recreate only `web`. Reopening payment operations is a separate audited owner
action. Reconcile the first legitimate receipt against the physical drawer, optional
paper receipt, contribution acknowledgement, exact-grade allocation, customer
statement, audit log, CSV export, and the integrity command. A mistaken entry must use
the reversal screen; never edit/delete rows or describe reversal as a refund.

At each daily cash close, compare physical cash and the external books with the owner
ledger's received, reversed, and net figures. Investigate every difference, every
`PAID_UNALLOCATED` receipt, and every integrity-check failure before redemption. Keep
the flag and payment initiation paused during unresolved financial incidents.

#### Completed production rollout evidence — 2026-09-03

- PR `#33` merged FW-PAY-006 as release
  `315f836ac0717fbaaf2d8d90268471ac1670e5b1`. The Linode candidate image was
  `jsk-savings:315f836ac0717fbaaf2d8d90268471ac1670e5b1`, identity
  `sha256:3484b41b607ca1a6bdef7926b0ba5b13b133244c6fc678d589d4fb9a5479f881`;
  rollback evidence retained image/release
  `51c931a9de5b27349f781cd44670c41307479dfa`.
- The operator recorded the 2026-09-03 4:00 PM IST managed PostgreSQL recovery
  point. The pre-migration baseline was six customers, eight scheme accounts, zero
  pending Razorpay contributions, zero cash principal/earned bonus,
  `0.010227` g `GOLD_22K_916`, `0.329272` g `GOLD_24K_9999`, and zero
  `SILVER_999`. Every grade was under `MANUAL_GLOBAL_PAUSE`, provider
  reconciliation found no candidate or review case, and the financial-exception,
  Razorpay Live-readiness, and exact-grade checks all reported `status=ok`.
- The reviewed plan contained only
  `schemes.0018_in_store_cash_contributions`. It applied successfully with Caddy
  and the old web service stopped; every Scheme migration through `0018` then
  reported applied. The candidate became healthy while the feature remained
  disabled, Caddy was recreated, and public Live/Ready identified the exact release.
  The new integrity command reported zero missing receipts, invalid mappings,
  reversed-without-correction rows, status mismatches, and lifecycle errors.
- The owner reviewed the gated record-cash path, role restrictions, exact-grade
  scheme selection, confirmation fields, and legacy/customer exclusions without
  creating a record.
  `IN_STORE_CASH_CONTRIBUTIONS_ENABLED=True` was then activated while payment
  operations remained paused; all paths were reviewed again before a separately
  audited reopening of 22K Gold, legacy 24K Gold, and 999 Silver.
- The first legitimate physical-cash transaction created receipt `CASH-150E7205`
  and contribution `15` for INR `1000.00`. Account, locked-rate, and allocation
  grades all matched `GOLD_22K_916`; INR `14667.0000`/g produced exactly
  `0.068180` g. The contribution was `PAID` through `IN_STORE_CASH`, remained
  unreversed, and had exactly one receipt audit event. The receipt, customer
  statement, owner ledger, and CSV were verified, while the daily cash summary
  reconciled INR `1000.00` received, zero reversed, and INR `1000.00` net.
- Final in-store-cash, financial-exception, exact-grade, Razorpay Live-readiness,
  payment-operations, container-health, liveness, and readiness gates all passed.
  Application-only rollback to the old image is no longer write-safe after `0018`;
  any recovery must keep payments paused and reconcile all activity after the
  recorded recovery point before restoring the database and old image together.

### FW-ELIG-001 exact-calendar eligibility rollout

ADR-0010 changes no stored schema or existing agreement date. Deploy it through the
normal immutable-image path, require a no-op migration plan, and compare customer,
account, pending-payment, paid-unallocated, and exact-grade liability totals before
and after replacement. Verify the public Terms wording plus these deployed policy
boundaries: the day before is ineligible, the exact date is eligible, eligibility
does not expire, month-end clamps to the destination month's final day, and a weekend
date is not shifted. Reaching eligibility must not mutate stored account status.

#### Completed production rollout evidence — 2026-09-04

- PR `#36` passed both Django and container CI triggers and merged as release
  `50bfd3673c57dff51b46238094bcad899a36c8fa`. The Linode image
  `jsk-savings:50bfd3673c57dff51b46238094bcad899a36c8fa` has digest
  `sha256:c18d89243ad753e9eeca519cb1bc164ae25176051731e25834fe61639b9f0a43`;
  rollback image/release `315f836ac0717fbaaf2d8d90268471ac1670e5b1` remained present.
- Pre-release checks reported six customers, eight scheme accounts, zero pending
  Razorpay contributions, zero paid-unallocated contributions, `0.078407` g
  `GOLD_22K_916`, `0.329272` g `GOLD_24K_9999`, and zero `SILVER_999`.
  Financial-exception, Razorpay Live-readiness, exact-grade, in-store-cash,
  payment-operations, and provider dry-run reconciliation gates were green.
- The candidate deploy check passed with only two non-blocking staged-HSTS warnings,
  and the migration plan contained no operations. No migration or database mutation
  occurred. The latest previously recorded managed recovery point was 2026-09-03
  4:00 PM IST; it predates the first in-store receipt and was not treated as a safe
  financial restore point. This no-schema release retained application-image rollback
  as the recovery path.
- The first on-host build completed, but starting the immediate candidate preflight
  exhausted the 961 MiB RAM / 496 MiB swap Compute Instance. The kernel OOM killer
  terminated a process, SSH and HTTPS stopped responding, and Cloudflare reported an
  origin host error. At that point `.env.production`, running release, database, and
  schema were unchanged. A controlled host reboot restored healthy release
  `315f836a`; the candidate image and rollback image both survived. The deploy user
  lacked permission to read the root-only previous-boot kernel journal.
- After recovery, the existing candidate was reused without rebuilding. Each
  candidate gate ran sequentially with 418–431 MiB available; only the two release
  identity lines were changed, the web container was replaced rather than overlapped,
  and validated Caddy was recreated after web became healthy.
- Independent Live/Ready requests returned `200` with release `50bfd367...`; static
  CSS and the public exact-calendar Terms paragraph returned `200`. Post-release
  financial/provider gates remained green and the full baseline matched exactly.
  All eight stored agreements matched `start_date + agreed_months`; deployed probes
  confirmed day-before false, exact-day true, ten-years-later true, leap-year clamp
  `2024-02-29`, and unshifted Sunday `2026-09-06`. Recent logs contained no release
  failure; one routine WordPress-probe `404` and Caddy's known HTTP/3 receive-buffer
  notice required no action.

### FW-ELIG-002 scheme-reminder rollout (`schemes.0019`)

This release adds email reminders for configured upcoming-eligibility lead days,
owner-only `PAID_UNALLOCATED` exceptions, and same-day completed redemptions. It adds
communication evidence only: candidate selection and delivery do not mutate an
account, payment, allocation, eligibility date, redemption, or liability. Keep the
master switch closed through migration, recipient review, and dry-run validation:

```dotenv
SCHEME_REMINDERS_ENABLED=False
SCHEME_REMINDER_ELIGIBILITY_DAYS=30,7,1
SCHEME_REMINDER_CUSTOMER_ELIGIBILITY=True
SCHEME_REMINDER_OWNER_ELIGIBILITY=True
SCHEME_REMINDER_OWNER_ALLOCATION_EXCEPTIONS=True
SCHEME_REMINDER_CUSTOMER_REDEMPTIONS=True
SCHEME_REMINDER_OWNER_REDEMPTIONS=True
SCHEME_REMINDER_RETRY_LIMIT=3
SCHEME_REMINDER_BASE_URL=https://jaishrikrishnajewellery.com
```

Configured-builder extension (migration `0051_inr_completion_reminders`): the
existing customer/owner `*_REDEMPTIONS` switches also govern final INR settlement
notices; no new scheduler or credentials are required. Apply the additive migration
before running the new reminder code. Keep `CONFIGURED_PLANS_ENABLED=False` until
the coherent builder release is approved. Per-family operational readiness is
checked independently; setting the flag alone does not activate these notices.
Only fully recorded completion events qualify, never proposals or partial
fulfilment. Full returns and invalid source/benefit evidence suppress dispatch.
Old reminder identities and attempts are preserved. Once an INR-linked reminder
exists, migration reversal is refused: retain the records and use forward recovery.
These notices share the existing same-day processing/date-override and SMTP retry
limitations. Review dry-run counts and recipient settings before enabling dispatch;
SMTP acceptance is not proof of inbox delivery.

Use the exact protected-`main` GHCR digest from the successful Actions run. Do not
build on the Linode. Record the current immutable image/release, a current managed
PostgreSQL recovery point, capacity, customer/account/liability/exception baselines,
and every existing financial, Razorpay, grade, in-store-cash, payment-operations, and
provider-reconciliation gate. Run candidate one-offs sequentially and remove each
temporary container before continuing.

The reviewed migration plan must contain only
`schemes.0019_scheme_reminders`. It creates the append-oriented reminder and delivery-
attempt tables, indexes, and constraints; it does not backfill messages or send email.
It is additive and the previous application image ignores the new tables, so apply it
once with the candidate while the existing web remains available:

```bash
docker compose --env-file .env.production -f compose.production.yml \
  run --rm --no-deps web python manage.py migrate --plan

docker compose --env-file .env.production -f compose.production.yml \
  run --rm --no-deps web python manage.py migrate --noinput

docker compose --env-file .env.production -f compose.production.yml \
  up -d --force-recreate --no-deps web
```

Wait for the candidate to become healthy, validate and recreate Caddy, and require
public Live/Ready to identify the exact release. Run all prior integrity gates and
then preview reminder work without sending:

```bash
docker compose --env-file .env.production -f compose.production.yml \
  exec -T web python manage.py send_scheme_reminders
```

The summary intentionally contains counts rather than customer addresses. Require
`status=ok`, review the configured active owner addresses in the application, and
require `invalid_customer_recipients=0`. The candidate count may legitimately be zero.
Do not invent a financial event to force a reminder. A provider-accepted message for
the first legitimate candidate is the controlled SMTP smoke; acceptance does not
prove inbox receipt or reading.

Install the externally scheduled job while it is still fail-closed. These files are
versioned with the exact release. The service deliberately calls `docker exec`
against the stable `jsk-savings-web-1` container name and uses an empty systemd-owned
`DOCKER_CONFIG`; it does not depend on a Docker Compose plugin or credentials beneath
the protected deploy user's home directory:

```bash
sudo install -o root -g root -m 0644 \
  deploy/systemd/jsk-scheme-reminders.service \
  /etc/systemd/system/jsk-scheme-reminders.service
sudo install -o root -g root -m 0644 \
  deploy/systemd/jsk-scheme-reminders.timer \
  /etc/systemd/system/jsk-scheme-reminders.timer
sudo systemctl daemon-reload
sudo systemctl start jsk-scheme-reminders.service
sudo systemctl status jsk-scheme-reminders.service --no-pager
```

The manual run must report `enabled=false` and send nothing. After the owner approves
the audiences and dry-run, set `SCHEME_REMINDERS_ENABLED=True`, validate Compose, and
force-recreate only `web`. Confirm the setting inside Django before enabling the
timer:

```bash
docker compose --env-file .env.production -f compose.production.yml config --quiet
docker compose --env-file .env.production -f compose.production.yml \
  up -d --force-recreate --no-deps web
docker compose --env-file .env.production -f compose.production.yml \
  exec -T web python manage.py shell -c \
  'from django.conf import settings; print("release=", settings.APP_RELEASE); print("reminders_enabled=", settings.SCHEME_REMINDERS_ENABLED)'

sudo systemctl enable --now jsk-scheme-reminders.timer
sudo systemctl list-timers jsk-scheme-reminders.timer --no-pager
sudo journalctl -u jsk-scheme-reminders.service -n 50 --no-pager
```

The timer checks every fifteen minutes. One deterministic identity exists per event,
audience, and normalized recipient; provider-accepted messages are not resent and
failures stop retrying at the configured limit. Inspect aggregate command/journal
status and the owner-only Reminder deliveries page. Never place recipient addresses,
message bodies, or action URLs in shared rollout evidence.

Upcoming eligibility and completed-redemption candidates are date-bound. If the job
was unavailable for an entire India-local day, first perform a read-only catch-up
preview, investigate recipients privately, and apply only with explicit approval:

```bash
docker compose --env-file .env.production -f compose.production.yml \
  exec -T web python manage.py send_scheme_reminders --as-of YYYY-MM-DD
docker compose --env-file .env.production -f compose.production.yml \
  exec -T web python manage.py send_scheme_reminders \
  --as-of YYYY-MM-DD --confirm-date-override --apply
```

Application rollback is safe because `0019` is additive, but stop and disable the
timer before selecting the previous image. Retain the reminder tables and their
evidence; never reverse or delete accepted/failed history merely to roll back code.
An SMTP backend can accept a message immediately before a later database failure, so
end-to-end exactly-once delivery cannot be claimed. Treat a suspected duplicate as a
communication incident, preserve provider and local evidence, and do not edit the
financial record.

#### Production rollout evidence — 2026-09-04

- The operator recorded the 2026-09-04 12:00 PM IST managed PostgreSQL recovery
  point. The pre-release baseline was six customers, eight scheme accounts, zero
  pending Razorpay contributions, zero cash principal or earned bonus,
  `0.078407` g `GOLD_22K_916`, `0.329272` g `GOLD_24K_9999`, and zero
  `SILVER_999`. Payment operations were open with zero pending orders; financial-
  exception, Razorpay Live-readiness, exact-grade, in-store-cash, and provider dry-
  run reconciliation checks all reported `status=ok`.
- PR `#42` merged release `94cf3927a7138cf735da733c6ae68a8cce785cff`.
  Protected-`main` run `33862547971` passed tests, deployment/static checks, image
  publication, and its fixable-critical-vulnerability gate, producing
  `ghcr.io/rajeshr188/jsk-savings@sha256:8270e175b9f4789dc12f83b9b41f504b0b3dcd5814a1b82f904aa61116623a7e`.
  The Linode pulled that exact digest without credentials or an on-host build. With
  432 MiB available memory, the reviewed plan contained only
  `schemes.0019_scheme_reminders`; it applied successfully and every Scheme migration
  through `0019` reported applied.
- Release `94cf3927...` became healthy on the immutable digest. Its disabled dry-run
  reported zero candidates, two owner recipients, zero invalid customer recipients,
  zero sends, and no retry failures. All pre-release financial/provider gates
  remained green. The first installed systemd unit exited `125` before Django ran:
  `ProtectHome=true` hid per-user Docker state, the Compose subcommand was not
  resolved, and Docker rejected `--env-file`. No email or database mutation occurred.
- PR `#43` corrected that boundary without weakening `ProtectHome`: the unit uses a
  systemd-owned empty `DOCKER_CONFIG` and `docker exec` against the stable
  `jsk-savings-web-1` container. Protected-`main` run `33865158341` passed 294 tests,
  deployment/static checks, publication, and the vulnerability gate, producing
  release `c889ee6906a8bddd4c7852955025efe42ffa5752` at
  `ghcr.io/rajeshr188/jsk-savings@sha256:88eea68169da2ea04f9f104358ecb69ec929989b15f5e447825ab0f0bd806c33`.
  The Linode again pulled and deployed the exact digest without building. The
  corrected service exited successfully while fail-closed and explicitly reported
  that no email was sent; public Live/Ready returned `status=ok` with the exact
  hotfix release.
- This is the first application release deployed from the protected-`main` public
  GHCR artifact, closing `FW-PROD-006`. The reminder implementation, schema, command,
  owner view, and hardened scheduler boundary are accepted. Because there was no
  legitimate candidate, `FW-ELIG-002` retains one non-blocking first-use observation:
  confirm the first naturally occurring reminder is accepted by the configured SMTP
  provider (SES after 31 October 2026) and appears
  in the owner delivery view. Do not manufacture a financial or redemption event.

### Live reconciliation, payment-error refund, and dispute boundary

- **Daily reconciliation:** compare Razorpay Live captured payments against the owner
  contribution export using `gateway_mode`, payment reference, INR amount, and local
  status. Investigate provider-only payments, local-only confirmations, amount/order
  mismatches, failed webhooks, and `PAID_UNALLOCATED` records before redemption.
- **Payment-error refunds:** the approved manual path is limited to captured duplicate
  or otherwise erroneous payments that created **no** local contribution entitlement.
  Verify this from the payment ID, order, amount, webhook ledger, contribution, and
  allocation or INR principal receipt before an authorized owner initiates the refund in Razorpay Dashboard.
  Record the refund ID, amount, reason, approver, timestamps, and final status in the
  incident record. If entitlement exists, do not treat it as a no-entitlement payment
  error: contain affected activity and use only an approved audited disposition or
  correction workflow. Configured INR full settlement has source-specific actual
  fulfilment records; its release gates and customer authorization still apply.
  It does not clear unrelated provider errors.
- **Disputes:** monitor Razorpay Dashboard and its configured notification address,
  review each item before its response deadline, preserve the agreement, payment,
  acknowledgement, statement, Scheme Rate lock, allocation, and showroom evidence,
  and accept or contest only through an authorized owner. A dispute or chargeback
  against a locally credited contribution is a financial incident requiring checkout
  suspension as appropriate and explicit liability reconciliation; never delete or
  edit the contribution to imitate reversal.

## Staging rollout

Staging should exercise production topology while using its own data and credentials.

1. Inject staging configuration with `DJANGO_DEBUG=False`.
2. Deploy the release image by digest.
3. Run exactly one release job:

   ```powershell
   python manage.py migrate --noinput
   ```

4. Start or update the web service. Do not run migrations in the container start
   command and do not let every replica race to apply them.
5. Wait for `/health/live/` and `/health/ready/` to return `200` with the expected
   release.
6. Execute the smoke test below.
7. Observe logs, database connections, latency, provider calls, and exceptions for a
   representative period before approving production.

## Production rollout

Use a rolling or blue/green deployment only when the migration is compatible with
both old and new application versions. Otherwise schedule a maintenance window and
use a reviewed migration-specific procedure.

1. Announce the change window and name the release, database, and incident owners.
2. Confirm the previous image digest remains available.
3. Record a pre-release database snapshot or confirm a current PITR recovery point.
4. Record baseline customer/account counts and the owner dashboard's separate cash
   principal, earned cash bonus, gold grams, silver grams, and exception counts.
5. Re-run the deploy check in the production environment.
6. Run `python manage.py migrate --plan` and compare it with the approved plan.
7. Run `python manage.py migrate --noinput` once as the release job.
8. Deploy the approved image digest. Keep old instances until new readiness probes pass.
9. Confirm the live and ready responses show the new `APP_RELEASE`.
10. Execute the production-safe smoke test. Routine infrastructure releases must not
    create a payment merely as a health probe. In Test Mode use controlled test data;
    in Live Mode rely on non-mutating checks unless the business has approved a real,
    fully reconciled contribution.
11. Compare post-release counts, liabilities, and exceptions to the recorded baseline,
    accounting for any legitimate concurrent activity.
12. Observe the release through the agreed stabilization window, then close the change
    record with evidence.

## Smoke test

Start with unauthenticated checks:

```powershell
curl.exe --fail-with-body https://savings.example.com/health/live/
curl.exe --fail-with-body https://savings.example.com/health/ready/
curl.exe --fail-with-body https://savings.example.com/static/css/base.css
```

Confirm the health JSON contains the expected release. Then test in a browser:

1. Open the home page over HTTPS and confirm there is no redirect loop or mixed content.
2. Sign in as a designated owner and as a staging/test customer; verify role isolation.
3. Submit a CSRF-protected, non-financial form and sign out.
4. Request a password reset for a controlled address and verify sender, link hostname,
   delivery time, and successful reset. Do not inspect message bodies in shared logs.
5. Verify the owner dashboard loads and its INR, gold, and silver liabilities remain
   separate and match the pre-release baseline.
6. Verify the exception queue and audit log load without exposing provider secrets.
7. In staging, complete one Razorpay Test Mode contribution and confirm both browser
   callback verification and a signed `payment.captured` webhook are idempotent.
8. Publish reviewed gold and silver Scheme Rates as the staging owner. Start a
   controlled metal checkout, publish a newer rate, complete the original payment,
   and verify it uses the old lock while a new checkout uses the new rate. Also verify
   that no metal order can be created when no applicable rate exists.
9. Verify a contribution acknowledgement, customer statement, and owner CSV export.

Record time, operator, release, URLs, test identities, provider event identifiers,
and results. Never paste secrets or full webhook bodies into the record.

## Initial application bootstrap

After the first successful migration, create the initial owner through a one-off
platform job attached to the production database:

```powershell
python manage.py createsuperuser
```

Use a controlled mailbox, a unique password, and the organization's credential
handling policy. A Django superuser is authorized as an application owner. Do not
create shared customer/owner accounts. Confirm the deployed domain and display name
for Django's Sites entry in `/admin/`, because authentication emails may use site
context.

## Monitoring and alerting

Django and Gunicorn emit timestamped logs to stdout/stderr. The platform must attach
request metadata and retain logs according to the approved privacy and financial
record policy. Logs must be searchable by `APP_RELEASE`; never log secrets, cookies,
passwords, payment signatures, full webhook bodies, or database URLs.

The Linode profile implements this boundary with masked structured Caddy access logs,
Better Stack/Vector off-host collection, external HTTP monitors, and the versioned
`check_financial_exceptions` heartbeat timer described above. Provider-side account
configuration and exercised incident evidence remain deployment actions, not source
code behavior.

Create actionable alerts for:

| Signal | Initial response |
| --- | --- |
| Liveness failure | Replace the unhealthy instance; inspect startup and worker logs |
| Readiness failure | Remove from traffic; inspect PostgreSQL health and connection capacity |
| Sustained 5xx or latency increase | Correlate by release and endpoint; consider image rollback |
| Failed/mismatched Razorpay webhook | Preserve ledger evidence; compare provider and local IDs |
| Any new `PAID_UNALLOCATED` record | Investigate the unexpected allocation exception; retry only from its original locked Scheme Rate |
| Database storage/CPU/connections near limit | Stop scaling web replicas blindly; restore capacity margin |
| Backup/PITR failure or missed snapshot | Treat production recovery as degraded and repair immediately |
| SMTP delivery/authentication failure | Verify provider status and credentials; test password reset |
| Certificate expiry or TLS failure | Renew/replace at the edge before customer access is affected |

Choose thresholds from measured staging/production baselines. Every page-level alert
must name its responder, escalation path, and runbook. Exercise each route before
customer access is enabled; an untested alert is not a control.

Capacity planning must include database connections. Each container currently runs
two Gunicorn workers and may hold persistent connections for 60 seconds. Ensure the
database connection limit covers all workers across the maximum replica count plus
release jobs, administrative work, health traffic, and a safety margin. Do not solve
connection exhaustion by increasing one limit without checking database memory.

Run `python manage.py clearsessions` periodically as a platform-scheduled one-off job
to remove expired database-backed sessions. This job is maintenance, not a financial
workflow, and must use the deployed image and environment.

## Backup and restore

Managed snapshots and point-in-time recovery are the primary controls. PostgreSQL
custom-format exports are an additional portability control, not a substitute for
tested managed recovery. Use a restricted service definition or password file so a
password never appears in shell history:

```powershell
pg_dump --format=custom --no-owner --no-acl --file=<restricted-backup-path> <production-service-name>
```

Encrypt exports, restrict access, keep them outside the application container, and
verify retention and deletion policy. Monitor command exit status and warnings.

At least quarterly, and before relying on a new backup mechanism, restore into a
new isolated database that cannot receive production traffic:

```powershell
createdb <isolated-restore-database>
pg_restore --exit-on-error --no-owner --no-acl --dbname=<isolated-restore-service> <backup-file>
```

Never use the production database as the restore target. Treat a dump as trusted
code only when its source is trusted; PostgreSQL restores execute statements stored
in the archive.

After restoration:

1. Point a temporary application instance at the isolated database.
2. Run `python manage.py showmigrations --plan` and `python manage.py check`.
3. Record source backup time, restore start/end time, errors, and achieved RPO/RTO.
4. Compare customer, account, contribution, allocation, redemption, reversal,
   webhook-ledger, and audit-event counts with the source evidence.
5. Reconcile outstanding cash principal and earned bonus, gold grams, and silver grams
   separately against the restored owner dashboard. Do not use indicative current
   metal INR exposure as a booked balance.
6. Test controlled owner/customer reads without contacting live providers or sending
   real email.
7. Preserve the drill record, then destroy the isolated environment according to the
   platform's approved data-handling procedure.

## Rollback

### Application rollback

If probes, errors, or smoke tests fail and the schema remains compatible:

1. Stop further promotion and record the failure time and release IDs.
2. Route traffic to the previous image digest.
3. Confirm both health endpoints and repeat the safe smoke checks.
4. Verify liabilities and exception counts; reconcile activity during the rollback.
5. Preserve new logs, provider events, and database records for investigation.

### Migration failure

Do not improvise a reverse migration on production. Stop the rollout, retain the
current database, and execute the migration-specific recovery plan reviewed before
release. If old code is incompatible with the migrated schema, keep traffic stopped
or use the explicitly prepared compatible image.

### Database recovery warning

Do **not** restore an older database after newer payments, webhooks, allocations,
redemptions, reversals, or audit events have been recorded merely to roll back code.
That would discard the append-oriented financial source of truth. A database
point-in-time recovery is an incident operation requiring identification and
reconciliation of every event after the chosen recovery point.

## Provider incidents

### Payment or webhook incident

1. Prevent new checkout order creation through the audited Payment Operations page.
   If that path is unavailable, set `PAYMENT_INITIATION_KILL_SWITCH=True`, validate
   Compose, and recreate only `web`. Keep `PAYMENT_GATEWAY=razorpay` and the webhook
   secret configured.
2. Keep the webhook endpoint and provider retry evidence available when safe.
3. Preserve all local contributions and `PaymentWebhookEvent` records. Do not edit or
   delete them to force a match.
4. Reconcile Razorpay order, payment, amount, currency, captured status, event ID,
   and local contribution using authorized provider access.
5. Follow the bounded manual refund/dispute procedure above. The application does not
   implement refund, chargeback, or payment-reversal mutations.
6. Re-enable checkout only after reconciliation and a signed webhook test in the
   same Razorpay mode as the environment.

### Scheme Rate or allocation incident

1. Leave verified but unallocated payments in `PAID_UNALLOCATED`.
2. Confirm the contribution already has the expected locked Scheme Rate. Do not
   substitute the newest rate after payment.
3. Correct the underlying application/database issue and use the owner-controlled
   allocation retry action, which is idempotent and audited.
4. Confirm exactly one immutable Scheme Rate link and allocation exist and that gold and
   silver remain separate.
5. Never edit, replace, or backdate the contribution's locked rate.

### Database incident

1. Remove unready instances from traffic and prevent new financial actions.
2. Identify whether the failure is connectivity, capacity, credentials, corruption,
   or a provider outage.
3. Preserve the primary and its logs; use managed failover/PITR procedures.
4. If recovery changes the database timeline, reconcile all post-recovery provider
   activity before reopening contributions.

## Secret rotation

Rotate one credential class at a time and keep a tested rollback path.

### Django signing key

1. Generate a new key and keep the current key securely.
2. Deploy the new key as `DJANGO_SECRET_KEY` and the old key as the sole temporary
   value in `DJANGO_SECRET_KEY_FALLBACKS`.
3. Verify login, logout, password reset, and signed application flows.
4. After the approved session/token overlap window, deploy with an empty fallback.
5. Revoke the old secret and record completion. A fallback is still an active secret.

If a key is known to be exposed, do not preserve it merely for session continuity;
rotate immediately and accept the required session/token invalidation.

### Database and SMTP credentials

Create or activate the replacement credential, update the secret manager, roll the
web service, verify the relevant readiness/email path, then revoke the old
credential. Check that release jobs and administrative identities do not share the
web application's secret unnecessarily.

### Razorpay API keys

Use the provider's supported overlap/activation process, update both key ID and
secret atomically without changing `RAZORPAY_MODE`, roll the application, and verify
authenticated provider access in the same mode before deactivating the old key. Use
Test Mode for rehearsal; a Live rotation must not create an artificial customer
payment merely as a credential probe.

### Razorpay webhook secret

Webhook rotation must be coordinated because the provider and application must agree
on one signing secret. Use a controlled change window: pause financial activity,
update the endpoint and application secret in the provider-supported order, deploy,
send and verify a signed event in the environment's configured mode, check
idempotency, then resume. Older provider retries may still use the former secret, so
do not rotate while deliveries are outstanding. Preserve failed deliveries for
reconciliation; never accept unsigned events during the gap.

## Routine operations

| Frequency | Action |
| --- | --- |
| Every release | Green CI, image scan, deploy check, migration review, backup/PITR confirmation, smoke test, reconciliation |
| Daily | Review alerts, failed webhooks, allocation exceptions, backup success, database capacity |
| Weekly | Review error trends, certificate status, payment/email provider status, email delivery, and run expired-session cleanup |
| Monthly | Patch/rebuild base images and locked dependencies through a tested release; review access and secret age |
| Quarterly | Perform and evidence an isolated restore/reconciliation drill and an incident/alert exercise |
| After any incident | Preserve timeline/evidence, reconcile financial state, document cause/actions, and test prevention |

Dependency updates must change and review `uv.lock`; do not run an unlocked upgrade
inside a production build. Rebuild regularly with current trusted base-image patches,
then promote the resulting immutable digest through the normal release process.

## `FW-AUTH-004` Google linked-credential rollout

ADR-0013 permits Google only as an explicitly connected sign-in method for an
already-approved customer. It does not open social signup, match an unconnected
Google identity to a user by email, approve a registration, or create a scheme. Keep
the feature disabled until every step below passes.

### Google configuration

Use a production-owned Google Cloud project and create an **External** Web application
OAuth client. Configure the consent/branding screen with the owned homepage, support
email, privacy policy, and terms. Request only the `profile` and `email` identity
scopes used by django-allauth. Google recommends separate testing and production
projects; a project in Testing is restricted to its configured test users.

Register this exact authorized redirect URI, including scheme and trailing slash:

```text
https://jaishrikrishnajewellery.com/accounts/google/login/callback/
```

Do not register an IP address, HTTP production callback, wildcard, `/accounts/login/`,
or the `www` hostname unless the application is intentionally changed to generate
that exact callback. Google requires the requested redirect URI to exactly equal a
registered URI.

### Disabled schema rollout

Take and record the managed PostgreSQL recovery point and the current immutable image
and release. Add the credentials to `/opt/jsk/app/.env.production`; never put the
secret in Git, a browser variable, a template, or a command transcript:

```dotenv
CUSTOMER_GOOGLE_LOGIN_ENABLED=False
GOOGLE_OAUTH_CLIENT_ID=replace-with-google-web-client-id
GOOGLE_OAUTH_CLIENT_SECRET=replace-with-google-web-client-secret
PUBLIC_REGISTRATION_TERMS_VERSION=2026-09-05
PUBLIC_REGISTRATION_PRIVACY_VERSION=2026-09-05
```

Promote the approved registry digest through the normal release workflow. Before
migration, review the additive allauth plan:

```bash
cd /opt/jsk/app
docker compose --env-file .env.production -f compose.production.yml \
  run --rm --no-deps web python manage.py check --deploy --fail-level ERROR
docker compose --env-file .env.production -f compose.production.yml \
  run --rm --no-deps web python manage.py showmigrations socialaccount
docker compose --env-file .env.production -f compose.production.yml \
  run --rm --no-deps web python manage.py migrate --plan
```

The expected new schema is django-allauth's additive `socialaccount` migration chain.
Apply it, recreate `web`, then recreate Caddy so the OAuth callback log exclusion is
active:

```bash
docker compose --env-file .env.production -f compose.production.yml \
  run --rm --no-deps web python manage.py migrate --noinput
docker compose --env-file .env.production -f compose.production.yml \
  up -d --force-recreate --no-deps web
docker compose --env-file .env.production -f compose.production.yml \
  exec -T caddy caddy validate --config /etc/caddy/Caddyfile
docker compose --env-file .env.production -f compose.production.yml \
  up -d --force-recreate --no-deps caddy
docker compose --env-file .env.production -f compose.production.yml \
  exec -T web python manage.py check_customer_google_login
```

The integrity command must report `status=ok`, `enabled=false`, zero database Google
applications, zero stored tokens, and no invalid identity links. Confirm
`/accounts/login/` has no Google action and `/accounts/signup/` still reports direct
signup closed.

### Controlled connection and enablement

Record baseline counts for `CustomUser`, `Customer`, `SchemeAccount`, `Contribution`,
`MetalAllocation`, `SocialAccount`, and `SocialToken`. Set
`CUSTOMER_GOOGLE_LOGIN_ENABLED=True`, validate Compose, and recreate only `web`.
Use one approved, active, non-staff customer whose local email is verified and whose
Google verified email matches it exactly:

1. Sign in with the existing password.
2. Open **Account → Google sign-in** and connect Google.
3. Sign out and use **Continue with Google**.
4. Sign out again and prove the original password still works.
5. Request a password-reset email and confirm the owned-domain fallback remains usable.
6. Attempt Google login with an unconnected test identity and confirm only the generic
   instruction to sign in by password appears; no local account is created or revealed.

Run:

```bash
docker compose --env-file .env.production -f compose.production.yml \
  exec -T web python manage.py check_customer_google_login
docker compose --env-file .env.production -f compose.production.yml \
  exec -T web python manage.py check_auth_email_integrity
docker compose --env-file .env.production -f compose.production.yml \
  exec -T web python manage.py check_financial_exceptions
docker compose --env-file .env.production -f compose.production.yml \
  exec -T web python manage.py check_graded_metal_rates
```

Expect one additional `SocialAccount`, zero `SocialToken` rows, and no change caused
by linking in users, customers, schemes, contributions, allocations, redemptions, or
liabilities. Confirm Caddy access logs contain no
`/accounts/google/login/callback/` entry and application logs contain no OAuth
authorization code. Retain only aggregate evidence; never record the client secret,
OAuth code, state value, cookie, or provider subject identifier.

If any check fails, set `CUSTOMER_GOOGLE_LOGIN_ENABLED=False`, recreate `web`, and
continue password login while investigating. Do not reverse the additive allauth
migrations or delete a binding to make counts pass. A compromised individual must be
deactivated until reviewed; a safe audited unlink workflow is outside this phase.

### Production acceptance evidence

`FW-AUTH-004` completed its disabled-first rollout and controlled acceptance on
2026-09-05 in release `77141d0caa447028802ff1ec7166fad4fd198d8c`, published as
`ghcr.io/rajeshr188/jsk-savings@sha256:7e2f95e53333791ede60007f0a059377938574e63d574a55fb4da7fe48c63681`.
The recorded PostgreSQL recovery point was 2026-09-05 10:00 AM IST; rollback remained
release `bfbdad86c49855ffc5c9965d0848a657a62cf938` and image
`ghcr.io/rajeshr188/jsk-savings@sha256:3d634e2c6c4149c94b7f82aaaee2e5b60c0b1db0821203e1f8d65d95205bf394`.
All six additive `socialaccount` migrations applied with the feature disabled. The
disabled integrity check reported no links, stored tokens, database provider apps, or
invalid identities; live and ready health checks and the authentication, financial,
and exact-grade integrity gates passed.

After activation, one approved active non-staff customer explicitly connected a
matching verified Google identity, signed in through Google, and retained successful
password and password-reset fallback. Owner/administrator Google connection remained
unavailable by design. Aggregate before/after evidence remained eight users, seven
customers, nine scheme accounts, fifteen contributions, and six allocations; only
the intended single `SocialAccount` was added and `SocialToken` remained zero. No
OAuth secret, authorization code, state value, cookie, or provider subject identifier
is retained in this evidence.

Rotate the Google client secret as its own credential class: create a replacement in
Google, update the server environment, recreate `web`, prove a controlled login, then
delete the old secret. Disabling the feature is the immediate containment action if a
coordinated overlap is unavailable.

## `FW-PRIV-001A` account-deletion foundation rollout

### `FW-PRIV-001B` disabled production acceptance — 10 September 2026

Evidence source: owner-supplied terminal output and explicit confirmation of both
public health endpoints and ordinary customer journeys; no direct host operation
or independent browser acceptance was performed by the agent in this rollout.

| Item | Accepted evidence |
| --- | --- |
| PR / release | PR #72; `7819fd9552825c61ebc34a7844ba346c7ad92488` |
| Image | `ghcr.io/rajeshr188/jsk-savings@sha256:4f07a2b4a274130cca8bd079d6ffba60547cb2d49e3e9bf4aff39cfdbccaa806` |
| CI | Run `34461760984`; Django and published-image fixable-critical scan passed |
| Previous release | `6396371fa71cc4b53c2e4a92ee31b329a5c9419b` |
| Previous image | `ghcr.io/rajeshr188/jsk-savings@sha256:55c8f840cb023ff8760bdbb0f602472787cfac2186c01bbc7d608c630d32db7c`; local presence verified |
| Recovery point | Owner confirmed available in Linode: 10 September 2026, 13:00 IST (07:30 UTC), not the earlier proposed 15:00 timestamp |
| Candidate identity | Pulled digest and OCI revision matched the approved candidate |
| Preflight | Auth email integrity passed; planned only accounts `0006`; financial exception baseline clean |
| Capacity after pull | 438 MiB available RAM; 260 MiB swap used; 7.3 GiB free disk, 69% used |
| Migration | `accounts.0006_customer_deletion_completion` applied OK and marked `[X]` |
| Running checks | Web running/healthy; deletion check `enabled=false`, zero requests/completions and zero integrity/notice errors; financial exceptions all zero |
| Edge / public | Caddy valid; live and ready HTTPS responses `ok` on candidate; deletion route 404 |
| Customer smoke tests | Login, customer dashboard and Savings Plans confirmed working |

Production deploy-check output was not included in the supplied evidence; the
candidate's CI deployment check passed. No claim of a new full liability snapshot,
fresh real-money test, real deletion, external-copy disposal or enabled acceptance
is made. Keep deletion disabled. The former release is a recorded rollback identity,
not permission to reverse schema or restore a database; any later completion changes
the recovery boundary as described below.

### Independent recovery record — proposed operating procedure, not yet established

Use a restricted, encrypted record outside Git, the serving host and the managed
database being restored. Maintain a separately recoverable copy; do not put it in
the public catalogue R2 bucket. A private versioned JSON record per request/decision
is sufficient for this small pilot; do not introduce a second customer database.
Storage location, encryption/key recovery, authorized owner and backup custodian
must be explicitly selected and tested before the first real completion.

Responsibility split accepted by the owner on 10 September 2026: the showroom
owner reviews customer/financial obligations and approves deletion decisions;
Rajesh maintains the technical recovery record and verifies encrypted Drive and
USB copies after each completion or retention-decision change. The privately
identified backup custodian provides recovery cover when Rajesh is unavailable.
Keep the key-recovery instructions and contact/access details private. This role
acceptance did not itself approve restore handling or log limits. After separate
clarification, the owner accepted keeping restored databases isolated from public
access, payments, email and jobs until latest deletion decisions and newer financial
facts are reconciled. Missing evidence means remaining isolated. This is procedural
approval, not an executed production restore or authorization to restore now.

Record only request/customer/user identifiers, source database identity, application
release, policy version, verification/containment timestamps, completion timestamp,
decision IDs, retained/removed field names, category purposes/release conditions and
latest review date. Review free text for unnecessary personal details. These keys
remain sensitive/pseudonymous: restrict access. Never include original names,
addresses, phone numbers, email addresses, passwords or verification tokens.

For every completion or further minimization:

1. Independently save the reviewed intent and exact request identifiers **before**
   the mutation. Label it pending, not completed. If this write cannot be verified,
   stop the completion operation.
2. After the database commits, append the actual decision/outcome IDs and timestamp;
   verify the independent copy can be read. Preserve older versions and the latest
   field-removal decision. A failed notice does not mean minimization failed.
3. If a crash occurs between these steps, treat the pending record as unresolved:
   check database/audit evidence before recording an outcome. Do not invent success,
   restore login, or erase records solely because an intent exists.
4. Review the request queue daily. After each completion or review changes a
   decision, reconcile the database outcome with the independent record and update
   and verify both encrypted copies. No daily USB recopy is required when decisions
   have not changed. Freeze further completion if either copy or reconciliation
   is unreliable. The current application does not enforce or automate these steps.
5. On recovery, keep the restore isolated with providers/jobs/public access disabled.
   Reconcile the independent record against restored requests and current financial
   evidence. Missing verified requests, stale decisions or mismatched financial state
   require supervised recovery; the synthetic rehearsal is not a universal replay
   tool. Do not reopen until login/identity suppression and financial integrity pass.

Owner-confirmed storage test: the business Google Workspace Drive location is
restricted and a backup custodian has been identified privately. Following the
7-Zip encrypted synthetic-file exercise, both the downloaded Drive copy and the
independent USB copy decrypted successfully; an unauthorized account was denied
Drive access. This is owner-reported evidence, not an agent inspection. No passwords,
private links, custodian identity or customer records were supplied or recorded here.

Storage access and synthetic file recovery are verified to that scope. Still required:
maintain the accepted roles and separately recoverable key instructions privately;
exercise the before/after decision-record procedure with a synthetic deletion;
reconcile its latest review against both copies; and approve the handling of backups
predating a verified request. A readable test text file does not by itself establish
that the real decision register is complete/current. The agent created no external
storage, uploaded no records and changed no sharing settings.

Completed tabletop exercise: three explicitly fictional, non-customer JSON records were prepared
locally for pending intent, completion and latest retention review. They are not a
database export or substitute for actual decision IDs/timestamps. Preserve each
version as a separately named encrypted archive in Drive and on USB. The custodian
must recover all three, identify the latest review as authoritative for removed
fields, and recognize that a pending intent alone does not prove execution. Storage
access/decryption already passed. The owner confirmed sequence recognition:
version 3 is the latest decision; version 1 alone does not prove deletion occurred;
version 2 must not restore fields removed by version 3.
It does not close real before/after reconciliation or pre-request restore handling.

### Local `FW-PRIV-001B` completion increment — not an enablement approval

Migration `accounts.0006_customer_deletion_completion` adds the erased-login marker,
disposition constraints and completion-notice queue. It does not erase records.
For local synthetic testing, apply migrations with `uv run --env-file .env python
manage.py migrate`. Never use a real customer as a deletion smoke test. Review the
owner preview, reauthenticate, document every category, confirm the request UUID,
and verify the removed login/profile, preserved financial facts and outcome notice.
For synthetic local form tests, use the console or in-memory email backend rather than
sending fake-customer notices through production SMTP. Neither proves SMTP delivery.
Do not copy local synthetic policy versions or enablement flags
to Linode.

Production must remain `CUSTOMER_ACCOUNT_DELETION_ENABLED=False` until policy
wording and actual provider/export/log/backup procedures are owner-approved and a
separate rollout is reviewed. Use a CI-built GHCR digest; never build on the serving
host. Run `check_customer_account_deletions` with the existing auth, registration,
financial and health checks after the migration and disabled-stage recreation.

When eventual enablement is approved, the owner must check the privacy queue daily.
Completed requests remain visible for retention reviews and outcome-email retries.
The integrity command reports `completion_errors`, `orphaned_erased_logins`,
`notice_pending` and `notice_needs_review`; a failed notice or one pending more than
24 hours requires attention. Never repeat data removal to resend a notice. Provider
acceptance clears its temporary address but does not establish inbox receipt.

Before the first real completion, document a restricted, purpose-limited record of
completed deletion decisions that remains available during disaster recovery, and
exercise reapplication/suppression on an isolated restore before reopening access.
Do not restore erased identities to contact customers. If a completion has occurred,
do not roll back to a pre-completion-aware application or restore a database backup
without this suppression procedure. Prefer a forward fix. Automated external-copy
purging and financial-history destruction are not implemented.

#### Owner procedure review before enablement

Record the actual decisions in the ADR-0015 worksheet and restricted operational
records, not customer-identifying evidence in Git. Do not treat the synthetic test
retention text or its 30-day review date as the business retention schedule.

1. Name the owner responsible for daily privacy-queue checks, failed notices and
   overdue reviews. Record how that duty is covered during absence.
2. For Postmark/support mail, Razorpay, Cloudflare/application logs, R2 documents,
   downloaded exports, paper records and database backups, record whether customer
   data exists, its purpose, actual configured retention or disposal condition,
   access restrictions, responsible person and next review date. Verify provider
   settings rather than assuming a default. Mark non-applicable categories with
   evidence; application completion does not delete these external copies.
3. Keep a restricted recovery record outside the database being restored: request,
   customer and user identifiers; completion timestamp; policy/decision version;
   fields already removed; retained categories; and subsequent review decisions.
   Do not copy removed names, email addresses, tokens or passwords into that record.
   Establish who updates it after each completion/review and verifies it is current.
4. Rehearse using synthetic identities in an isolated restore with outbound email,
   payment actions, scheduled jobs and public access disabled. Compare the restored
   data against the recovery record, reconcile newer financial facts separately,
   and review the required minimization before any reopening. There is no automatic
   replay command: do not blindly rerun an old decision against a restored balance.
5. Record that erased login/contact fields remain unusable, Google links and sessions
   cannot restore access, financial facts are unchanged by minimization, and current
   integrity checks pass. Record discrepancies and resolve them before reopening.
   A successful ordinary database restore alone does not prove this deletion drill.
6. Align the public policy and customer notice with the approved procedures, including
   retained records and backup limitations. Review the disabled-stage release and
   authorize enablement separately; do not claim Play deletion acceptance yet.

#### Synthetic local restore rehearsal — 10 September 2026

Reproduce only on a local development PostgreSQL server with `pg_dump` and
`pg_restore` on PATH and permission to create temporary databases:

```powershell
uv run --env-file .env python -m accounts.rehearse_deletion_restore --synthetic-local
```

This is not a production recovery command. It refuses non-loopback database targets
and connection-option overrides, generates two fresh random database names, migrates
only its empty source database and creates test fixtures. It never dumps or migrates
the configured application database. Email is in-memory, payments are disabled and
no web server or scheduled job is started. It restores only its own synthetic dump
into its own fresh destination, then removes both databases and temporary artifacts.
Do not run this on the serving Linode or pass it a production environment file.

Observed result: real PostgreSQL 16 client `pg_dump`/`pg_restore` succeeded. The
backup contained verified/contained requests before completion. Restoration brought
back personal fields and removed completion markers, demonstrating the risk even
though those contained logins stayed inactive. An independent synthetic decision
record preserved identifiers, policy/version/timestamps, field dispositions and a
financial fingerprint, without copying removed customer contact values.

Two cases passed: no financial history, and a customer with a preserved exact-grade
gold entitlement. The first case included a later review removing name/email after
initial completion; replay used that latest decision, not the older retention list.
Reapplication preserved the full selected financial rows, removed eligible identity
and authentication bindings, cleared temporary notice contacts through in-memory
delivery, and passed deletion integrity. Missing-request and financial-mismatch
guards rejected replay. Cleanup removed two temporary databases and all generated
synthetic dump/decision files; no real customer data was used or removed.

Scope limit: this demonstrates local **post-containment** recovery using existing
completion services, not an automated production recovery facility. A backup predating
the verified request requires separately supervised recovery; the script refuses to
invent verification or authorization. Changed financial state also requires separate
reconciliation. The exercise does not prove recovery of decisions lost from the real
production backup, correctness/authenticity of a real independent recovery register,
external-provider erasure or Linode restore performance. Before real enablement,
establish the restricted independent register and approve the applicable recovery
procedure. Do not mark production restore suppression accepted from this result alone.

#### Owner-reported provider inventory — 10 September 2026

SES migration addition, verified 31 October 2026: message archiving is disabled.
The account-level suppression list retains recipient addresses for bounce/complaint
handling; the default configuration set publishes failure metadata, including the
recipient/message identity, to the confirmed business-admin SNS email subscription.
Those Workspace mailbox copies, AWS support correspondence, provider operational
records and historical Postmark copies remain part of external disposition review.
The sending identity uses a console-disabled SMTP IAM user with scoped sending
permission; owner console/support and business-mailbox access are separate from that
credential. Do not infer a fixed provider retention/deletion period from disabled
archiving, or claim copies were erased without provider/mailbox evidence. Apply the
existing documented purpose/minimum-data/review rules to suppression and alert copies.

- Postmark activity retention: 45 days (owner confirmed). Message activity/content
  expiry does not establish deletion of suppressions or support mailbox copies.
- No retained customer CSV exports, downloaded statements, paper records or customer
  documents in R2 (owner confirmed). Reassess if these practices change.
- Confirmed available Linode recovery point: 10 September 2026 at 13:00 IST,
  superseding the earlier 14:00 report.
  The reported 18 August cluster creation date is not confirmed backup availability;
  oldest available recovery point remains unknown.
- Journals occupy 798.2 MB (owner output). This is usage, not a time-retention policy.
  Both running web and Caddy containers use the `local` log driver with
  `max-size=20m` and `max-file=5` (owner-supplied inspection). These are size/rotation
  limits, not an age-based retention guarantee. A subsequent vendor drop-in shows
  `ForwardToSyslog=yes`; rsyslog is active with local destinations. Syslog and UFW
  rotation are weekly/four archives; a daily logrotate timer exists but its service
  success and cloud-init/mail.err coverage are not yet verified. The 14-day/256-MB
  proposal is withdrawn as a standalone policy; follow `FW-PROD-007` above before
  shortening retention. Cloudflare website Logpush is unavailable on the reported
  Free plan; this does not prove no Cloudflare-held logs or other export mechanisms.
  The owner subsequently accepted the restore-isolation rule; this is procedural
  approval, not evidence of an executed production restore/reconciliation.

Provider references: [Postmark retention](https://postmarkapp.com/support/article/how-does-the-retention-add-on-work)
and [Akamai backup management](https://techdocs.akamai.com/cloud-computing/docs/aiven-manage-database).
Provider defaults do not replace evidence of actual account configuration.

### Previously accepted disabled foundation

ADR-0015 permits an additive, disabled-first request and containment foundation while
the completion and retention procedures remain open. Its 10 September revision
allows owner-operated development without waiting for qualified written sign-off;
the read-only disposition preview does not change this rollout boundary.
This phase has no anonymization or
completion mutation and must not be described to Google Play or customers as a live,
completed deletion facility.

Add the bounded settings to `/opt/jsk/app/.env.production` without inventing a policy
version:

```dotenv
CUSTOMER_ACCOUNT_DELETION_ENABLED=False
CUSTOMER_ACCOUNT_DELETION_EMAIL_EXPIRY_HOURS=24
CUSTOMER_ACCOUNT_DELETION_ATTEMPTS_PER_HOUR=5
CUSTOMER_ACCOUNT_DELETION_ATTEMPT_RETENTION_HOURS=24
CUSTOMER_ACCOUNT_DELETION_OWNER_REVIEW_DAYS=7
CUSTOMER_ACCOUNT_DELETION_COMPLETION_TARGET_DAYS=30
CUSTOMER_ACCOUNT_DELETION_POLICY_VERSION=
```

After recording the recovery point, rollback image/release, financial baseline, and
capacity, promote the registry digest and inspect the additive plan:

```bash
docker compose --env-file .env.production -f compose.production.yml \
  run --rm --no-deps web python manage.py check --deploy --fail-level ERROR
docker compose --env-file .env.production -f compose.production.yml \
  run --rm --no-deps web python manage.py showmigrations accounts
docker compose --env-file .env.production -f compose.production.yml \
  run --rm --no-deps web python manage.py migrate --plan
```

The expected application change is `accounts.0005_customer_account_deletion_foundation`
and its request, bounded-attempt, decision, and append-only action tables. Apply it,
recreate `web`, validate/recreate Caddy for the deletion-token log exclusion, and run:

```bash
docker compose --env-file .env.production -f compose.production.yml \
  run --rm --no-deps web python manage.py migrate --noinput
docker compose --env-file .env.production -f compose.production.yml \
  up -d --force-recreate --no-deps web
docker compose --env-file .env.production -f compose.production.yml \
  exec -T caddy caddy validate --config /etc/caddy/Caddyfile
docker compose --env-file .env.production -f compose.production.yml \
  up -d --force-recreate --no-deps caddy
docker compose --env-file .env.production -f compose.production.yml \
  exec -T web python manage.py check_customer_account_deletions
```

Expect `status=ok`, `enabled=false`, and zero deletion requests/actions. Both deletion
entry points and their navigation links must remain unavailable. Re-run the existing
authentication and financial integrity commands and live/ready checks. Stop there:
`CUSTOMER_ACCOUNT_DELETION_POLICY_VERSION` must remain blank and the feature must not
be enabled until `FW-PRIV-001B` supplies owner-approved dispositions, the irreversible service,
policy wording, provider procedures, synthetic no-history and retained-history tests,
and a separately approved production runbook.

Production evidence recorded 2026-09-07: protected-`main` release
`e6a8ee0f20fe2324276fb75dad6bda9df64baf9d` was deployed from immutable image
`ghcr.io/rajeshr188/jsk-savings@sha256:6b65308d74165d6ca19b298dd507f45f8bb51416bd14c69f406a782810cccd18`, with
release `77141d0caa447028802ff1ec7166fad4fd198d8c` and digest
`sha256:7e2f95e53333791ede60007f0a059377938574e63d574a55fb4da7fe48c63681`
retained as rollback identities. The latest managed-PostgreSQL recovery point was
recorded as 4:00 PM IST on 7 September 2026. The plan contained only additive
`accounts.0005_customer_account_deletion_foundation`, which applied successfully.
The feature remained false with a blank policy version, all deletion counts and
integrity exceptions were zero, and the public route returned 404. Both HTTPS health
checks and the authentication, payment-operations, financial-exception, Razorpay Live,
exact-grade, in-store-cash, and Google-link checks passed. The seven-customer,
nine-account, zero-pending-order, zero-INR, `0.078407 g GOLD_22K_916`, `0.329272 g
GOLD_24K_9999`, and zero-silver baseline was unchanged.

## `FW-MOBILE-002` PWA foundation rollout

This release has no migration. Deploy it disabled first and keep the old image/release
identities as the rollback pair. Add this exact gate to `/opt/jsk/app/.env.production`:

```dotenv
PWA_ENABLED=False
```

After promoting the approved registry digest, recreate `web` and confirm the three PWA
routes are closed while both health checks and the existing financial/authentication
integrity commands pass:

```bash
docker compose --env-file .env.production -f compose.production.yml \
  config --quiet
docker compose --env-file .env.production -f compose.production.yml \
  up -d --force-recreate --no-deps web
curl -sS -o /dev/null -w 'manifest=%{http_code}\n' \
  https://jaishrikrishnajewellery.com/manifest.webmanifest
curl -sS -o /dev/null -w 'worker=%{http_code}\n' \
  https://jaishrikrishnajewellery.com/service-worker.js
curl -sS -o /dev/null -w 'offline=%{http_code}\n' \
  https://jaishrikrishnajewellery.com/offline/
```

All three must be `404` while disabled. In a browser that previously installed this
origin, load one online page and confirm this app's worker and `jsk-pwa-static-*` cache
are removed. Do not delete unrelated origin storage.

After the disabled checks pass, set `PWA_ENABLED=True`, validate the Compose config,
and recreate only `web`. Caddy does not require a configuration change:

```bash
docker compose --env-file .env.production -f compose.production.yml \
  config --quiet
docker compose --env-file .env.production -f compose.production.yml \
  up -d --force-recreate --no-deps web
curl -fsS https://jaishrikrishnajewellery.com/manifest.webmanifest
curl -sS -D - -o /dev/null https://jaishrikrishnajewellery.com/service-worker.js
curl -sS -D - -o /dev/null https://jaishrikrishnajewellery.com/offline/
curl -fsS https://jaishrikrishnajewellery.com/health/live/
curl -fsS https://jaishrikrishnajewellery.com/health/ready/
```

Expect the manifest to name Jai Sri Krishna Jewellery and declare 192/512 PNG icons,
the worker to return `Service-Worker-Allowed: /` plus
`Cache-Control: no-cache, no-store, must-revalidate`, and the offline page to state
that a connection is required and nothing was submitted.

Complete browser acceptance on the canonical HTTPS origin before marking
`FW-MOBILE-002` complete:

1. Inspect the manifest, both icons, maskable safe area, worker scope, and installability
   in browser developer tools; install and relaunch the standalone app.
2. Inspect Cache Storage. The current `jsk-pwa-static-*` cache must contain exactly
   `/offline/` and the two 192/512 icon URLs—no HTML response from any other route.
3. While online, confirm customer login, scheme views, current rates, receipts, and
   statements come from the server. Confirm health responses remain `no-store`.
4. Go offline and navigate to public, authentication, customer, payment, owner, admin,
   CMS, health, and token-bearing paths. Every navigation may show only the generic
   connection-required page; no prior response or customer detail may appear.
5. Submit an ordinary form and attempt a contribution while offline. After restoring
   connectivity, prove no request, order, contribution, rate lock, allocation,
   redemption, approval, or provider call was created by either attempt.
6. Deploy a harmless release change and confirm the old named cache is removed after
   activation. Then disable the flag once, load an online page, and confirm worker/cache
   retirement before re-enabling and repeating the installability check.

Record the commit, immutable image digest, rollback pair, recovery point, browser/
device versions, cache contents, no-mutation evidence, health/integrity outputs, and
the owner acceptance. A rollback sets `PWA_ENABLED=False`, recreates `web`, and relies
on the next online page load to retire the safe worker; it does not require a database
rollback.

Production acceptance was completed on 7 September 2026 with release
`049944412aa09668d6b04e45cabee2bc58dadc42` and immutable image
`ghcr.io/rajeshr188/jsk-savings@sha256:4f5d10d014c3f516c4194fe192a01df57387c5353c232aa80a88ad18a99bce02`.
The rollback pair is release `e6a8ee0f20fe2324276fb75dad6bda9df64baf9d` and image
`ghcr.io/rajeshr188/jsk-savings@sha256:6b65308d74165d6ca19b298dd507f45f8bb51416bd14c69f406a782810cccd18`;
the recovery point was recorded as 6:00 PM IST that day. Disabled routes returned
404, enabled routes returned 200, installation succeeded, and the browser confirmed
the canonical scope and exact offline-plus-two-icon cache. Offline navigation leaked
no customer or scheme data and offline submission changed no tracked application or
financial counts. The disable/re-enable cleanup removed and restored only this PWA's
worker/cache. Live/readiness, financial-exception, and Razorpay Live checks stayed
clean; the final container was healthy with 9.6 GiB free disk.

## `FW-MOBILE-003` Digital Asset Links rollout

This release has no migration and does not require a Caddy configuration change. The
application owns the exact well-known path. Keep the previous image/release as the
rollback pair and first add this disabled gate to `/opt/jsk/app/.env.production`:

```dotenv
ANDROID_TWA_ASSET_LINKS_ENABLED=False
```

Promote the approved registry digest, recreate only `web`, and verify the closed
stage:

```bash
docker compose --env-file .env.production -f compose.production.yml \
  config --quiet
docker compose --env-file .env.production -f compose.production.yml \
  up -d --force-recreate --no-deps web
curl -sS -o /dev/null -w 'assetlinks=%{http_code}\n' \
  https://jaishrikrishnajewellery.com/.well-known/assetlinks.json
```

The response must be `404`. Then set the gate to `True`, validate Compose, and
recreate only `web`. Verify the exact response and ordinary health endpoints:

```bash
docker compose --env-file .env.production -f compose.production.yml \
  config --quiet
docker compose --env-file .env.production -f compose.production.yml \
  up -d --force-recreate --no-deps web
curl -sS -D /tmp/jsk-assetlinks-headers.txt \
  -o /tmp/jsk-assetlinks.json \
  https://jaishrikrishnajewellery.com/.well-known/assetlinks.json
python3 -m json.tool /tmp/jsk-assetlinks.json
curl -fsS https://jaishrikrishnajewellery.com/health/live/
curl -fsS https://jaishrikrishnajewellery.com/health/ready/
```

Require HTTP 200 without a redirect, `Content-Type: application/json`, package
`com.jaishrikrishnajewellery.savings`, relation
`delegate_permission/common.handle_all_urls`, and these two Play App Signing
certificate fingerprints:

`25:78:42:37:4E:7A:C9:62:C8:AF:90:11:E3:8C:86:32:E2:08:DF:E4:6E:77:C0:86:59:7F:31:E7:32:D7:07:97`

`B8:A3:25:32:0B:80:2C:2A:E1:9B:EA:F7:30:27:C4:89:E5:2D:D6:1F:E4:60:F2:99:2F:6E:C6:54:14:24:17:B4`

The second certificate was independently extracted from the APK delivered by Play
Internal Testing on 9 September 2026. Retain both certificates so Play delivery or
signing-key segmentation does not break supported devices. Compare all 32 byte pairs
with Play Console and/or a signature-verified installed Play APK. Do not use the
upload-key or debug fingerprint. Remove
the temporary response files after review. Then verify the association from an
installed Play-signed Internal Testing build and retain the release/image, rollback
pair, HTTPS response, Play comparison, device result, health/integrity outputs, and
owner acceptance. A rollback sets the flag to `False` and recreates only `web`; no
database rollback is involved.

Production origin acceptance completed on 8 September 2026 with release
`1826afec8628d4f9288c1625091974687af7aba0` and immutable image
`ghcr.io/rajeshr188/jsk-savings@sha256:ac31ab070a9560a64b1239fff7b883573a6732b69b21fd133e858298750a2bf8`.
The rollback pair is release `049944412aa09668d6b04e45cabee2bc58dadc42` and image
`ghcr.io/rajeshr188/jsk-savings@sha256:4f5d10d014c3f516c4194fe192a01df57387c5353c232aa80a88ad18a99bce02`;
the managed-PostgreSQL recovery point was recorded as 8:00 PM IST that day. The
disabled stage returned 404. After enablement, the origin returned a direct HTTP/2
200 with `application/json`, the expected one-hour cache policy, and the then-known
registered package/Play-fingerprint statement. Automated comparison and both HTTPS
health checks passed, and the authentication, payment-operations,
financial-exception, Razorpay Live, exact-grade, in-store-cash, enrolment-request,
public-registration, and Google-link integrity checks remained clean. There was no
migration.

The additive Play keyset correction completed production acceptance on 9 September
2026 in release `0c611f6e51434aa7f0a3faa8ddba8ef492910af3`, immutable image
`ghcr.io/rajeshr188/jsk-savings@sha256:7a9cd29e01f1cd9240098622c11e869e43fb953e554d94dc97ed75e55203d374`.
The prior release/image immediately above is its rollback pair. There was no migration
or database mutation. The origin returned both exact Play certificates, both HTTPS
health endpoints returned that release, and Google's association API linked each
certificate. On the Internal Testing device, Android reported the installed Google
certificate and canonical domain as verified, link handling was enabled, Chrome was
the default browser, and relaunching the app removed the address bar. The upload-key
certificate remained absent. The wider customer-journey matrix remains an Android
release gate rather than part of this association acceptance.

### Daily contribution-channel metrics production evidence — 9 September 2026

PR `#65` merged the owner daily contribution-channel reporting as release
`9fa12943b9719e1c14d1894c4cfceb753b54376c`. Protected-`main` CI run
`34382198915` passed Django, static/deployment, immutable-image publication, and
fixable-critical-vulnerability gates and produced
`ghcr.io/rajeshr188/jsk-savings@sha256:4e8abb514e2ac33a757c3abfc545d414a9430edbcf4c085157fe2ce4a941616e`.
The rollback pair was release `0c611f6e51434aa7f0a3faa8ddba8ef492910af3`
and image
`ghcr.io/rajeshr188/jsk-savings@sha256:7a9cd29e01f1cd9240098622c11e869e43fb953e554d94dc97ed75e55203d374`.
The managed-PostgreSQL recovery point was recorded as 10:00 PM IST that day.

Before cutover, the owner applied the audited global payment pause. One INR 4,000.00
Live Gold 22K order was 97.9 minutes old and past its Checkout deadline; a fresh
provider inspection reported `created`, zero attempts, zero payments, zero paid, and
the full amount due. The standard dry-run classified it as
`ELIGIBLE_FOR_ABANDONMENT`, and apply abandoned exactly that contribution with zero
errors. Payment operations then reported zero pending orders for every grade, while
financial exceptions and Razorpay Live readiness remained clean.

The candidate used the approved digest, had no planned migrations, and previewed the
India-local daily selector as INR 0.00 physical cash, INR 4,000.00 captured Live
Razorpay, one verified contribution, and INR 4,000.00 total verified. The host retained
449 MiB available memory, 343 MiB free swap, and 8.4 GiB free disk before cutover.
After web and Caddy recreation, public liveness and PostgreSQL readiness returned the
exact release, the homepage returned `200`, and an unauthenticated owner contribution
request returned the expected login redirect. Payment-operations, financial-exception,
Razorpay Live, exact-grade, and in-store-cash checks all passed. The authenticated owner
confirmed the three displayed daily values, then removed the audited pause; all grades
reported `OPEN` with zero pending orders.

Cloudflare Web Analytics was separately confirmed enabled for the production site.
No analytics dependency, tag, cookie, consent state, Django setting, or privacy-policy
change was introduced by this release. Aggregate Cloudflare traffic reporting does not
close the independent health/log/financial-alert exercises still deferred under
`FW-PROD-002`.

## Wagtail 8.0 dependency rollout

Wagtail 8.0 is a major dependency release. Deploy it as its own immutable image and
do not combine the rollout with catalogue/editorial model changes or content
publication. Before changing the running web service, record the current image and
release, a current managed-PostgreSQL recovery point, host capacity, and the standard
financial/authentication integrity checks.

Run the candidate deploy check and migration plan sequentially. For this upgrade the
reviewed plan must add only Wagtail's vendor migration
`wagtailcore.0098_apitoken`; there is no project-generated migration:

```bash
docker compose --env-file .env.production -f compose.production.yml \
  run --rm --no-deps web python manage.py check --deploy --fail-level ERROR

docker compose --env-file .env.production -f compose.production.yml \
  run --rm --no-deps web python manage.py migrate --plan
```

Stop if any other unexpected migration appears. After reviewing the plan, apply it
once with the candidate, recreate only `web`, wait for health, then validate and
recreate Caddy through the normal release procedure. Verify both health endpoints,
public catalogue listing/product pages, About/Our Story fallbacks or enabled CMS
pages, Wagtail admin login, one non-publishing preview, catalogue/editorial
authorization checks, and the production R2 upload/read/rendition/cleanup check.
Run all standard integrity checks afterward.

The migration only adds Wagtail's API-token table. If application behavior fails but
database integrity remains clean, return to the recorded Wagtail 7.4.3 image; that
release ignores the additive table. Do not reverse or delete the vendor migration as
part of an application-only rollback.

### Production acceptance — 10 September 2026

The isolated Wagtail 8.0 rollout was accepted in release
`65eff0d80a2e23f5f7df1da9d610d7ae1ef26038` from immutable image
`ghcr.io/rajeshr188/jsk-savings@sha256:521ced1f7e0686728cebc73e4be89aba6db30963aa421ce0a7a3538d1e09f406`.
The managed-PostgreSQL recovery point was recorded as 10 September 2026 at
12:10 AM IST. The previous release
`9fa12943b9719e1c14d1894c4cfceb753b54376c` and image
`ghcr.io/rajeshr188/jsk-savings@sha256:4e8abb514e2ac33a757c3abfc545d414a9430edbcf4c085157fe2ce4a941616e`
remain the application rollback target; the additive API-token table must remain if
that rollback is used.

The reviewed and applied migration plan contained only
`wagtailcore.0098_apitoken`. Both health endpoints returned the candidate release,
and runtime inspection reported Wagtail 8.0. Catalogue and Editorial authorization
checks passed, as did the R2 upload, read, rendition, and cleanup exercise. The full
authentication and financial integrity suite reported no duplicate or blank login
emails, no blocked-grade or pending-payment exposure, no paid-unallocated records,
no failed or mismatched webhooks, no grade-contract mismatch, no invalid in-store
cash lifecycle, and no invalid enrolment, registration, Google-login, or
account-deletion lifecycle. Live Razorpay readiness passed, and the abandoned-order
dry run reported zero candidates and zero errors.

Manual checks confirmed the public catalogue and a product page, About, existing
images/renditions, Wagtail admin login, and a non-publishing preview. Existing
catalogue/editorial content remained unchanged. This acceptance covers the major
dependency upgrade only; it does not approve a blog model, new editorial scope, or
new publication permissions.

### Disabled-first Jewellery journal foundation acceptance — 10 September 2026

`FW-CMS-004` completed its disabled-first production foundation in release
`6396371fa71cc4b53c2e4a92ee31b329a5c9419b`, published as immutable image
`ghcr.io/rajeshr188/jsk-savings@sha256:55c8f840cb023ff8760bdbb0f602472787cfac2186c01bbc7d608c630d32db7c`.
The recorded managed-PostgreSQL recovery point was 10 September 2026 at 6:00 AM IST.
The retained application rollback pair is release
`65eff0d80a2e23f5f7df1da9d610d7ae1ef26038` and image
`ghcr.io/rajeshr188/jsk-savings@sha256:521ced1f7e0686728cebc73e4be89aba6db30963aa421ce0a7a3538d1e09f406`.
Because the migration is additive, an application rollback must preserve the blog
tables, Wagtail revisions, workflow evidence, and R2 objects.

The reviewed plan contained only `blog.0001_initial`; it applied successfully and is
recorded as applied. The idempotent authorization command created the draft Blog root,
dedicated media collection, `Blog Editors`, `Blog Publishers`, and
`Blog Administrators`, plus the publisher approval task and Blog review workflow. Its
check passed. No user was assigned, no article was created, and application roles were
not changed. Catalogue and Editorial authorization checks remained valid, and the R2
upload/read/rendition/cleanup exercise passed.

Both HTTPS health endpoints reported the candidate release. With
`PUBLIC_BLOG_ENABLED=False`, `/blog/` returned `404` and Journal discovery remained
absent from primary and footer navigation. Authentication email integrity, financial
exceptions, Razorpay Live readiness, exact-grade contracts, in-store cash lifecycle,
and abandoned-order reconciliation all passed with zero exceptions or open orders.
Payments were paused for the rollout, then reopened; every enabled grade reported
`OPEN` with zero pending contributions. This accepts only the private foundation.
Article approval, content accuracy, accessibility, metadata, R2 presentation, and the
separate `PUBLIC_BLOG_ENABLED=True` activation remain future controlled work.

## Go-live sign-off

The target full-production checklist remains below. Live acceptance does not mark
owner-deferred controls complete:

- [ ] The exact image passed CI, scanning, the approved isolated rehearsal (separate
      staging only when required by the release plan), and production deploy checks.
- [ ] Production uses `DJANGO_DEBUG=False`, explicit hosts/origins, HTTPS, secure
      cookies, staged HSTS, and verified proxy-header behavior.
- [ ] Database TLS/private access, backups, PITR, RPO/RTO, and an isolated restore
      plus denomination-specific reconciliation are proven.
- [ ] Real password-reset email delivery and sender-domain authentication are proven.
- [ ] Logs are retained and tested alerts reach named responders.
- [ ] Reviewed gold and silver Scheme Rates are published by an authorized owner,
      and rate-lock/no-rate staging smokes are evidenced.
- [ ] Razorpay uses a stable HTTPS webhook with signed, idempotent delivery testing.
- [ ] Separate Django, database, SMTP, Razorpay API, and webhook rotations
      have been rehearsed.
- [ ] Owner/customer access, documents, exports, audit, exceptions, and rollback have
      been smoke-tested.
- [ ] `FW-PROD-001` through `FW-PROD-003` are marked complete with evidence.
- [x] `FW-PAY-001` Live payment, capture, signed-webhook, allocation, and reconciliation
      acceptance is complete with the evidence above.
- [x] `FW-PAY-002` dry-run-first abandoned-order reconciliation is implemented with
      immutable provider snapshots and late-capture exception handling.
- [ ] Before expanding real-funds use, complete `FW-PAY-003` webhook recovery and the
      remaining refund/dispute, monitoring, and rotation controls, or retain explicit
      owner acceptance of their documented risk with manual compensating checks.

Record sign-off date, approvers, source commit, image digest, database recovery point,
test evidence, exceptions, and next review date. A checked box without evidence is
not a completed control.

## Primary references

- [Akamai/Linode Managed PostgreSQL](https://techdocs.akamai.com/cloud-computing/docs/aiven-postgresql)
- [Akamai/Linode managed database clusters](https://techdocs.akamai.com/cloud-computing/docs/aiven-database-clusters)
- [Akamai/Linode database backup management](https://techdocs.akamai.com/cloud-computing/docs/aiven-manage-database)
- [Akamai/Linode DNS A and AAAA records](https://techdocs.akamai.com/cloud-computing/docs/a-and-aaaa-records)
- [Caddy automatic HTTPS](https://caddyserver.com/docs/automatic-https)
- [Caddy reverse proxy headers](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy)
- [Django 6 deployment checklist](https://docs.djangoproject.com/en/6.0/howto/deployment/checklist/)
- [Django 6 with Gunicorn](https://docs.djangoproject.com/en/6.0/howto/deployment/wsgi/gunicorn/)
- [Docker build best practices](https://docs.docker.com/build/building/best-practices/)
- [Docker Engine on Ubuntu](https://docs.docker.com/engine/install/ubuntu/)
- [Docker Compose file-backed secrets](https://docs.docker.com/reference/compose-file/services/#secrets)
- [Docker image pulls by digest](https://docs.docker.com/reference/cli/docker/image/pull/#pull-an-image-by-digest-immutable-identifier)
- [GitHub protected branches and required checks](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)
- [GitHub package access and visibility](https://docs.github.com/en/packages/learn-github-packages/configuring-a-packages-access-control-and-visibility)
- [Google OAuth for web server applications](https://developers.google.com/identity/protocols/oauth2/web-server)
- [Google OAuth app audience and testing](https://support.google.com/cloud/answer/15549945)
- [Google OAuth app branding](https://support.google.com/cloud/answer/15549049)
- [Gunicorn control-socket settings](https://github.com/benoitc/gunicorn/blob/master/docs/content/reference/settings.md#control)
- [PostgreSQL backup and restore](https://www.postgresql.org/docs/current/backup.html)
- [PostgreSQL `pg_dump`](https://www.postgresql.org/docs/current/app-pgdump.html)
- [PostgreSQL `pg_restore`](https://www.postgresql.org/docs/current/app-pgrestore.html)
- [Razorpay webhook best practices](https://razorpay.com/docs/webhooks/best-practices/)
- [Razorpay webhook validation and testing](https://razorpay.com/docs/webhooks/validate-test/)
- [Razorpay Test and Live modes](https://razorpay.com/docs/payments/dashboard/test-live-modes/)
- [Razorpay Orders APIs](https://razorpay.com/docs/api/orders/)
- [Razorpay order payment inspection](https://razorpay.com/docs/api/orders/fetch-payments/)
- [Razorpay payment capture settings](https://razorpay.com/docs/payments/payments/capture-settings/)
- [Razorpay payment Dashboard actions](https://razorpay.com/docs/payments/payments/dashboard/)
- [Razorpay dispute Dashboard actions](https://razorpay.com/docs/payments/disputes/dashboard/)


## Customer conversion Phase 3: prepared release, not production authorization

Phase 3 adds `accounts.0007_planapplication_planapplicationconfirmation_and_more`.
It creates two empty tables, protected foreign keys, one-to-one agreement/registration
links and confirmation/preference constraints. It performs no historical registration,
customer, request, agreement or financial backfill. The earlier Phase 1 `pages.0002`
aggregate table remains a separate pending migration if not already deployed.

Rollout dependencies and acceptance (execute on production only after owner approval):

1. Review the complete pending migration plan, take the standard recoverable backup,
   and rehearse on a restored non-production PostgreSQL database. Run Django checks,
   migration consistency, the registration/invitation/enrolment/payment regressions
   and the new application/concurrency tests. Confirm consent/disclosure versions match
   the reviewed public Terms/Privacy copy; the developer's local `.env` is unchanged.
2. Apply additive migrations before the new web code receives traffic. Deploy the
   updated Caddy configuration before issuing progress links: `/accounts/applications/*`
   must be omitted from access logs along with verification/invitation paths. Validate
   Caddy configuration with the existing deployment tooling. Ensure any other edge or
   log-export layer obeys the same exclusions. No new runtime service is required.
3. Deploy the reviewed Django release. New plan-first intake uses the existing public
   registration and customer enrolment-request switches together. It adds no new
   automatic feature enablement or payment flag. Existing-customer requests and legacy
   access-only registrations remain supported; allauth direct signup remains closed.
4. Use synthetic applicants in the controlled acceptance environment: contact intake,
   one-use email POST, retained plan/grade/preferences, separate private progress email,
   session-gated address/current-offer confirmation, owner contact verification and
   coordinated approval. Verify changed terms/policy versions/start dates require
   customer reconfirmation; expired applications cannot be approved or have verification
   reissued. A missed start date requires today/a future date, not silent backdating.
5. Check distinct registration review, invitation, agreement and financial audit evidence;
   retry approval and verify the same agreement. Simulate mail failure: approval must
   persist and owner invitation recovery must work. Missing/failed progress delivery
   enters owner attention; verified incomplete applicants otherwise wait for customer
   details. Replacement progress links invalidate prior links and sessions and do not
   extend the original application expiry. No customer payment is tested on production
   without explicit authorization and the existing payment acceptance procedure.
6. Run `check_public_customer_registrations` (now includes missing/mismatched coordinated
   agreement checks) and the existing identity/enrolment integrity commands. The funnel
   report adds aggregate plan-application submissions and distinct customer-confirmed
   applications in the reporting period. These are subsets of registration throughput,
   not additional unique visitors or a joined conversion cohort. Reconfirmations count
   once per application in that period. No identity, link or reference is emitted.

Recovery/rollback: prefer disabling new public intake and deploying a forward fix.
Retain application/confirmation tables and every linked agreement, invitation and
identity review. Do not reverse `accounts.0007` after accepting applications: that would
remove retained evidence and relationships. Rolling back to old code can expose its
legacy identity-only approval path for newly linked records; do not use that old owner
approval endpoint or manual enrolment on those records. Put affected owner approval in
maintenance until a compatible fix is deployed. Existing financial reconciliation,
provider callbacks and historical customer access must remain available.

An interrupted after-commit email callback may leave delivery unrecorded; it must not
cause another agreement or invite on approval retry. Recover activation delivery through
the existing owner customer invitation replacement; recover progress through its
explicit owner replacement. No raw credential is retained for replay and no email
worker/outbox infrastructure is introduced. Original registration/consent timestamps
remain evidence; final policy/offer consent is retained in append-only confirmations.

Phase 4 implementation/release guidance follows below. Missing approved marketing benefits/descriptions and
showroom response-window input remain business follow-ups; no promises are added here.

## Customer conversion Phase 4: prepared release, not production authorization

`accounts.0008_customerinvitation_recovery_requested_at` adds one nullable timestamp
to the existing invitation table. It performs no historical or financial data backfill.
Review the complete pending migration plan including Phase 1/3 dependencies, back up
and rehearse on restored staging, and apply additive migrations before serving new code.
The developer's normal database and actual environment configuration remain unchanged.
No new flag or runtime service is required; existing intake/Google/payment switches
retain their independent rollout and fail-closed behavior. Do not enable Google merely
to inspect copy: use synthetic configuration in isolated local/staging acceptance.

Acceptance before approved rollout:

1. Exercise linked-plan password setup and subsequent password sign-in into the exact
   customer-owned agreement. Verify legacy setup, password reset and replaced/used
   invitations still work. Activation must not create financial records or auto-login.
2. Inspect customer dashboard/application stages and first-payment actions for future
   start dates, missing rates, pauses, monthly paid, uncertain/expired checkout,
   unallocated metal and Test versus Live records. GETs must call no payment provider.
3. POST setup-help from an eligible expired private link, then replay it. Only one
   timestamp is retained; no new invitation/mail/access is issued. Unknown/wrong/used/
   superseded/inactive/erased links show the same generic outcome. Verify CSRF, no-cache,
   strict-origin and existing token-path log exclusions at every edge/export layer.
4. Review Today/full login recovery queue and existing owner resend. Check latest-only
   records, 8-record preview and 25-record pages, retained recovery evidence, invitation
   supersession and delivery failure. Activated customers use password reset instead.
5. Review Google eligibility copy with connected/unconnected/disabled/ineligible
   fixtures; preserve adapter checks and closed signup. Follow the prepared Tamil
   protocol in `TESTING.md`; do not publish translations without business review.

Rollback: retain the new nullable column and recovery history; prefer disabling new
intake and a forward fix. Older compatible code may ignore recovery metadata, so owners
must manually review outstanding setup requests until the queue is restored. Phase 3's
warnings about old identity-only approval still apply. No agreement, registration,
financial record or invitation evidence is deleted for rollback. Production deployment
and production data changes require separate owner approval.
