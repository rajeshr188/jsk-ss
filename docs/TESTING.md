# Testing

## Checkout prevention and identity recovery (26 October 2026)

`schemes.tests.test_checkout_idempotency` covers retained submission replay and
concurrent-tab aliases; signed account/mode/history context; stale unsubmitted forms;
monthly versus sequential flexible payments; one unresolved source across modes and
months; immutable original terms; durable request commit before provider I/O; timeout,
malformed response and interrupted binding holds; legacy missing identity; provider
receipt/token adapters; owner/CSRF/preview/fresh-apply recovery; reconciliation-only
recovered checkout and idempotent capture. Migration tests exercise overlapping-history
preflight refusal, preservation through upgrade and retained-evidence reverse refusal.
All fixtures are synthetic; provider responses are mocked. No real order is created.

Protocol references: [Create an order](https://razorpay.com/docs/api/orders/create/)
and [Fetch an order](https://razorpay.com/docs/api/orders/fetch-with-id/).
The receipt and request token correlate a single durable application request; they
are not treated as a provider idempotency API. Final combined release verification
and production/monitoring acceptance are recorded in STATUS.md as completed.

## Release rehearsal and stakeholder task protocol (22 October 2026)

Run the opt-in synthetic local drill described in PRODUCTION_DEPLOYMENT.md:

```powershell
uv --cache-dir .uv-cache run --no-sync --env-file .env python -m schemes.rehearse_workflow_release --synthetic-local
```

The drill creates a pre-conversion synthetic baseline at accounts.0006 / schemes.0020 /
pages.0001, dumps it, restores a fresh database and applies the current pending migrations.
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
