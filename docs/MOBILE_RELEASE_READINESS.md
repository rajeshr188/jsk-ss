# Mobile Release Readiness

This document is the canonical readiness record for `FW-MOBILE-001`, the bounded
`FW-MOBILE-002` PWA foundation, and `FW-MOBILE-003` Android TWA delivery. It implements
ADR-0014 without adding a mobile API, native authentication, or client-authoritative
financial logic.

Status: **in progress — `FW-MOBILE-002` is production-accepted, the verified
organization owns the registered Play package and Play-managed app-signing identity,
and Play accepted a GitHub-built, upload-key-signed AAB for Internal Testing. The
additive Digital Asset Links keyset is production-published, Google and Android
verification pass, and the Play-installed app opens without browser chrome. The
account-deletion paths are enabled and the owner reauthentication UI is
production-accepted. A zero-history authenticated-path completion is production-
accepted; the separate signed-out email-verification path awaits a receiving
owner-controlled Workspace alias. Store listing, reviewer access, Data Safety,
financial classification and final Play submission remain open.**

## Product boundary

### Immediate submission path — owner-prioritized 10 September 2026

Keep release work bounded to this checklist. `FW-PROD-007` is a separate
operational/compliance workstream, not a prescribed Play archive design or permission
to disregard security obligations. Do not shorten/delete logs during the pilot.
Reuse the already-confirmed core customer journeys.

| Step | Evidence needed | Current status |
| --- | --- | --- |
| Recovery rule | Restores isolated until latest deletion and financial reconciliation passes; missing evidence blocks reopening | Owner accepted; earlier local synthetic restore passed, not a production restore |
| Deletion preflight | Running release, flag/policy version, integrity and financial checks; disposable test identities | Passed on `b349a84fdc716a87e85110386868923fad95326e`: enabled, both policy versions `2026-09-10`, public route and health checks 200, deletion/auth/financial checks clean |
| Controlled deletion | App and external request paths, actual minimization, notice, unusable login and independent before/after record | Authenticated zero-history completion accepted 15 September 2026: no profile fields retained, one immutable completion decision, outcome notice accepted and delivered, credentials unusable, Google unable to restore the account, and owner-confirmed integrity checks. The separate signed-out email-verification path still waits for Workspace alias delivery |
| Reviewer access | Dedicated non-privileged account, reusable password, accurate English access instructions | Instructions prepared below; account creation waits for an independently receiving Workspace alias and must remain separate from deletion identities |
| Console submission | Working deletion URL, Privacy/Data Safety/financial declarations, listing/build and remaining bounded device checks | Copy-ready worksheet prepared below; owner must enter/save drafts in Play Console and upload reviewed assets; submission remains separately authorized |

Prepare two disposable owner-controlled customer identities through normal invitations:
one for the app path, one for the external path. Use working controlled inboxes;
never supply passwords in Git/chat. Do not create schemes, enrolment requests,
payments, allocations or paper receipts for them. Confirm actual previews show no
obligations; an empty balance alone does not authorize erasing a real customer.

Before activation, owner reviews the deployed Privacy/deletion wording and chooses
the matching policy version; align registration privacy version without rewriting
historical consent or unnecessarily changing Terms. The current flag is global:
enabling exposes the path to all eligible customers, not only pilot accounts. Have
the owner ready to handle legitimate requests. Activation and irreversible completion
require explicit approval. No new build/migration is expected if the last accepted
release is still running.

Pilot sequence after approval:

1. Enable through the existing Compose procedure; verify public `/accounts/deletion/`
   and authenticated `/accounts/deletion/request/`, public health and integrity.
2. In the Play-installed app, first disposable customer submits a request. In a
   signed-out browser, second customer uses the public page and confirms the email
   verification link. Never share tokens/raw URLs. Verify containment and owner queue;
   submission is not completion.
3. Inspect the seven-category owner preview; record genuine fields, purposes, release
   conditions and review dates. Retain no unnecessary zero-history profile fields.
   Disclose remaining minimal privacy evidence, notices, provider/log/backup copies.
   Financial/export categories are not applicable only after checks; do not copy
   synthetic test retention text or claim external erasure not actually performed.
4. Save independent pending intent before completion. Complete using recent owner
   authentication and exact request confirmation; append actual decision IDs, time
   and disposition to verified encrypted Drive/USB copies. Retry failed notices,
   never repeat removal just to resend mail. No copied erased PII in the register.
5. Verify `COMPLETED_WITH_RETENTION`, intended profile/credential minimization,
   unusable old password/sessions and absent Google binding if one existed; outcome
   email, one completion decision, unchanged financial facts. Run
   `check_customer_account_deletions`, `check_auth_email_integrity`,
   `check_financial_exceptions` and `check_graded_metal_rates`; resolve notice and
   external-copy follow-ups honestly.
6. Keep reviewer credentials intact. Record app version/device, both paths, aggregate
   results and owner confirmation. Only then accept the deletion journey and provide
   the working public URL in Console. Applicant-only/ambiguous-identity cases remain
   a separate associated-data handling gap; do not claim this customer pilot covers them.

On failure stop completions and investigate. Disabling is not undo and must not
strand pending requests: continue owner support and resolve before submission.
Never restore erased identity as rollback. Deletion-specific procedure acceptance
does not mark every legal obligation, provider action or Play declaration complete.

Retention follow-up (10 September 2026): `FW-PROD-007` in
[Future work](FUTURE_WORK.md) tracks security-log coverage and a budget-conscious
archive plan. The earlier standalone 14-day journal suggestion is withdrawn in
favour of a 180-day CERT-In planning baseline; no archive is implemented or storage
destination approved. This is not a Google Play-specific duration requirement or
a legal compliance certification. Deletion/retention and Data Safety acceptance
remain open; do not claim that all operational/provider records are erased when
a customer account is minimized.

The first mobile product is an installable web application followed by a
customer-only Android Trusted Web Activity (TWA). It provides convenient access to
the existing Django application; it is not a second financial or identity system.

Included customer journeys:

1. Browse public jewellery, savings plans, policies, and showroom contact details.
2. Submit and verify a staged customer-registration request.
3. Sign in with a password or an already-linked eligible Google identity.
4. Submit and track a non-binding scheme-enrolment request.
5. View approved scheme accounts, grade-specific accumulated metal, contributions,
   receipts, statements, and eligibility information.
6. Start a Razorpay contribution, return from Checkout, and see only the result
   confirmed by the server-side payment workflow.
7. See payment pauses, expired checkouts, failures, and connection-required states
   without creating an entitlement.
8. Contact the showroom for support, fulfilment, correction, or redemption.

Excluded from the first mobile release:

- owner/staff administration, approvals, Scheme Rate publication, showroom-cash
  recording, payment controls, reconciliation, reversal, and redemption recording;
- mobile API tokens, direct database access, native Razorpay authority, push
  notifications, biometrics/passkeys, authoritative offline data, or background
  financial mutation;
- claims that the plan is an investment, bank deposit, interest product, tradable
  metal account, guaranteed return, or cash-withdrawal service.

## `FW-MOBILE-002` installable PWA foundation

The Django application now has a disabled-by-default `PWA_ENABLED` boundary. When
enabled it publishes `/manifest.webmanifest`, a root-scoped `/service-worker.js`, a
standalone `/offline/` response, and reviewed 192/512 PNG icons. The manifest uses the
canonical root start URL, standalone display, business name, and existing brown/gold
visual identity. It does not guess an Android package or declare a store category.

The worker's cache allowlist contains exactly the generic offline page and two app
icons. GET navigations are always fetched from the network with HTTP-cache reuse
disabled. A network failure may show only the generic connection-required message;
the worker never caches the preceding response. POST requests, subresources,
authentication and verification paths, scheme/customer data, rates, payments,
receipts, statements, eligibility, OAuth callbacks, health checks, owner pages, and
admin/CMS content are not intercepted or queued. There is no background sync,
IndexedDB, push, analytics, or offline financial state.

The feature is not a schema migration. Disabling it
hides the manifest/endpoints and causes the small registration script to unregister
this app's worker and delete only `jsk-pwa-static-*` caches on the next successful
online page load.

### Production acceptance — 7 September 2026

Release `049944412aa09668d6b04e45cabee2bc58dadc42` was promoted from immutable image
`ghcr.io/rajeshr188/jsk-savings@sha256:4f5d10d014c3f516c4194fe192a01df57387c5353c232aa80a88ad18a99bce02`.
The prior release `e6a8ee0f20fe2324276fb75dad6bda9df64baf9d` and image
`ghcr.io/rajeshr188/jsk-savings@sha256:6b65308d74165d6ca19b298dd507f45f8bb51416bd14c69f406a782810cccd18`
are the rollback pair. The latest managed-PostgreSQL recovery point was recorded as
6:00 PM IST on 7 September 2026; this release had no migration.

Disabled-first checks returned 404 for the manifest, worker, and offline page. With
the feature enabled, all three returned 200 and the app installed successfully. The
browser reported the canonical root worker scope and exactly one release-named cache
containing only `/offline/` and the hashed 192/512 icon URLs. Offline customer and
scheme navigation disclosed only the generic connection-required page. An offline
form/contribution exercise left accounts, enrolment requests, rates, contributions,
allocations, webhooks, and redemptions unchanged. Disabling the feature again removed
the worker and `jsk-pwa-static-*` cache on the next online load without manual browser
cleanup; re-enabling restored the expected scope and three-entry cache.

Both health endpoints, the financial-exception check, and Razorpay Live readiness
remained clean. The final web container was healthy with 377 MiB available memory,
422 MiB free swap, and 9.6 GiB free disk. The owner accepted the controlled rollout.
Exact browser/device versions were not retained here; the representative compatibility
matrix remains an `FW-MOBILE-001`/`FW-MOBILE-003` release gate rather than a claim of
Android-store readiness.

## Proposed permanent app identity

| Item | Proposed value | Gate |
| --- | --- | --- |
| Play app name | Jai Sri Krishna Jewellery | Confirm in Play Console |
| Android package | `com.jaishrikrishnajewellery.savings` | Owner approved 5 September 2026; registered to the verified organization with a Play App Signing SHA-256 identity on 8 September 2026; do not change it |
| Publisher | Jai Sri Krishna Jewellery | Must match the verified organization identity |
| Canonical origin | `https://jaishrikrishnajewellery.com` | Already production-owned; reverify before TWA work |
| Initial market | India | Confirm before store setup |
| App category | Shopping | Provisional; do not use it to avoid an accurate financial declaration |
| Target audience | Adults; not designed for children | Confirm through the Play audience/content forms |
| Advertising | None; do not request an advertising ID | Re-audit every Android dependency before release |
| Repository | Private `Jai-Sri-Krishna-Jewellery/jsk-savings-android` | Created 8 September 2026; build only on workstations/GitHub, never Linode |

The business owner approved this permanent package identifier on 5 September 2026.
On 8 September 2026 the owner confirmed that the Play organization is verified, the
draft app was created successfully, the package is registered, and Play App Signing
already exposes its SHA-256 certificate fingerprint. The fingerprint is public but
its exact value must be copied directly from Play Console and independently checked
before it enters Digital Asset Links. No signing private key, account identifier, or
recovery credential is recorded here. Do not create another production package,
publish an independently signed build first, or silently change this identifier.

## Android TWA foundation evidence

On 8 September 2026 the business organization created the private repository
`https://github.com/Jai-Sri-Krishna-Jewellery/jsk-savings-android`. Bootstrap commits
`983226f` and `7317a51` establish:

- the permanent package `com.jaishrikrishnajewellery.savings` bound to the canonical
  origin and root start URL;
- Bubblewrap 1.25.0 with Android 10/API 29 as the minimum and API 36 as the compile and
  target SDK;
- no Play Billing, geolocation, notification permission, native financial workflow,
  mobile API, production credential, or signing material;
- a non-repository upload-key location (`../.signing/jsk-savings-upload.keystore`)
  whose key has not yet been created;
- disabled native backup/data transfer, a pinned Gradle distribution checksum, and
  immutable CI action revisions; and
- a release-invariant check plus release lint and unsigned AAB build. Local build and
  GitHub Actions run `34235149531` both passed; the retained CI artifact is explicitly
  unsigned and cannot be uploaded as a release artifact.

The repository remains private. GitHub rejected server-enforced branch protection on
the current organization plan, requiring either a paid plan or making the repository
public. Neither change is implied by this record; until the owner chooses one,
feature-branch/green-PR discipline is procedural rather than server-enforced.

On 8 September 2026 the owner supplied the first **Play App Signing key certificate**
SHA-256 fingerprint for the registered package:

`25:78:42:37:4E:7A:C9:62:C8:AF:90:11:E3:8C:86:32:E2:08:DF:E4:6E:77:C0:86:59:7F:31:E7:32:D7:07:97`

On 9 September read-only inspection of the APK delivered through Play Internal
Testing established the additional Google-managed signing certificate:

`B8:A3:25:32:0B:80:2C:2A:E1:9B:EA:F7:30:27:C4:89:E5:2D:D6:1F:E4:60:F2:99:2F:6E:C6:54:14:24:17:B4`

These public certificate identities are intentionally recorded; no private signing
material is present. On 8 September 2026 production release
`1826afec8628d4f9288c1625091974687af7aba0` published
`/.well-known/assetlinks.json` after a disabled-first rollout. The canonical HTTPS
origin returned a direct HTTP/2 200, `application/json`, a one-hour public cache
policy, and the then-known package/fingerprint association; the exact automated
comparison and both health checks passed. The immutable image was
`ghcr.io/rajeshr188/jsk-savings@sha256:ac31ab070a9560a64b1239fff7b883573a6732b69b21fd133e858298750a2bf8`,
with release `049944412aa09668d6b04e45cabee2bc58dadc42` and image
`ghcr.io/rajeshr188/jsk-savings@sha256:4f5d10d014c3f516c4194fe192a01df57387c5353c232aa80a88ad18a99bce02`
retained as the rollback pair. The managed-PostgreSQL recovery point was recorded as
8:00 PM IST that day; no migration or database mutation was required. The installed
build exposed the additive keyset requirement when Android rejected the second
certificate against the single-certificate origin response. On 9 September release
`0c611f6e51434aa7f0a3faa8ddba8ef492910af3`, immutable image
`ghcr.io/rajeshr188/jsk-savings@sha256:7a9cd29e01f1cd9240098622c11e869e43fb953e554d94dc97ed75e55203d374`,
published both Play certificates with no migration or environment-key change. The
previous release/image above is the rollback pair. The direct origin response, both
health endpoints, and Google's association check for each certificate passed.
Android then reported the installed Google certificate and canonical domain as
verified, link handling was enabled, Chrome was confirmed as default, and a clean
relaunch displayed no address bar. Do not add an upload-key or local debug
certificate fingerprint to the production statement.

## Store listing copy draft

Use English (India) as the default listing language. The following text is
copy-ready but must still be previewed in Play Console against its current length and
metadata validation.

**App name**

> Jai Sri Krishna Jewellery

**Short description**

> Manage jewellery savings plans, contributions and accumulated metal records.

**Full description**

> Plan your future jewellery purchase with Jai Sri Krishna Jewellery in Vellore.
>
> The app gives approved customers a convenient way to:
>
> - browse available jewellery savings plans and eligible metal grades;
> - apply for customer access and request plan enrolment;
> - view approved scheme accounts and contribution history;
> - make scheduled INR contributions securely through Razorpay;
> - see the grade-specific metal quantity recorded from verified contributions;
> - access contribution receipts, scheme statements and eligibility information; and
> - contact the showroom or request account deletion.
>
> Registration and enrolment requests are reviewed by the showroom. Plan approval,
> jewellery selection, fulfilment and redemption follow the customer's recorded
> terms and are completed with the Vellore showroom. Jewellery availability and the
> final showroom invoice are separate from the savings-plan record.
>
> The app does not provide a bank deposit, interest, lending, securities or
> cryptocurrency trading, a transferable metal wallet, person-to-person transfer, or
> cash withdrawal. Metal quantities recorded under an approved plan are intended for
> application toward eligible jewellery or permitted items under that plan's terms.
>
> Support: admin@jaishrikrishnajewellery.com · +91 94894 81436
> Showroom: No. 155, Azad Road, Thorapadi, Vellore, Tamil Nadu 632001

Public listing links:

| Purpose | URL/status |
| --- | --- |
| Website | `https://jaishrikrishnajewellery.com/` — production available |
| Privacy policy | `https://jaishrikrishnajewellery.com/privacy/` — production available with app/deletion wording under policy version `2026-09-10` |
| Terms | `https://jaishrikrishnajewellery.com/terms/` — production available |
| Support | `https://jaishrikrishnajewellery.com/contact/` and `admin@jaishrikrishnajewellery.com` — production available |
| Account deletion | `https://jaishrikrishnajewellery.com/accounts/deletion/` — production available; authenticated zero-history completion accepted, separate signed-out email-verification completion pending |

### Store asset specification

Use the existing production visual identity rather than inventing a second mobile
brand. `static/images/pwa-icon-512.png` is the source candidate for the required
512-by-512 Play icon; export and inspect it outside the repository before upload.
Prepare a 1024-by-500 JPEG or 24-bit PNG feature graphic with no alpha, little or no
text, a central jewellery focal point, and the existing brown/gold/cream palette.
Do not include ratings, rankings, discounts, returns, guaranteed-value language,
Razorpay/Google endorsement, or claims that the app is an investment.

Capture phone screenshots from the Play-installed build, not a desktop mockup. Use a
controlled reviewer identity and remove or crop every customer name, email, mobile,
address, scheme number, receipt number, payment/order identifier and deletion token.
Recommended order:

1. Home — business identity and primary Savings Plans action.
2. Savings Plans — representative Gold 22K/Gold 24K/Silver choices without a price or
   benefit claim not present in the live app.
3. Enrolment request — non-binding request and showroom-approval explanation.
4. Customer dashboard — synthetic, privacy-safe account summary.
5. Contributions — synthetic history and separate INR/grade-specific quantities.
6. Receipts/statements — privacy-safe document access.
7. Account and privacy — support and deletion-request entry point.

Give each uploaded screenshot a unique plain-language alternative description. Keep
the focal UI legible on a phone and avoid decorative device frames that imply a
different operating system or unavailable feature.

## Copy-ready Play Console worksheet

Save each section as a draft until the alias-dependent deletion completion and stable
reviewer account pass. The owner must answer current Console wording truthfully if it
differs from this worksheet.

| Console item | Recommended value | Manual gate |
| --- | --- | --- |
| App or game | App | Confirm in Console |
| Pricing | Free | Confirm; do not configure Play Billing |
| Default language | English (India) | Confirm |
| Category | Shopping | Confirm available category/tags; this does not replace the financial declaration |
| Countries/regions | India only for initial production | Owner confirms business availability before saving |
| Contains ads | No | Reconfirm exact AAB has no advertising SDK or advertising ID |
| Privacy policy | `https://jaishrikrishnajewellery.com/privacy/` | Open publicly in a signed-out browser |
| Account deletion | `https://jaishrikrishnajewellery.com/accounts/deletion/` | Submit only after completed zero-history evidence |
| App access | Some functionality is restricted | Add the durable reviewer credentials and English steps only in Play Console |
| Target audience | Adults; not designed for children | Owner confirms minors are not offered app accounts before selecting age groups |
| Financial features | Other | Use the reviewed explanation below; do not select no financial features |
| Ads/UGC/social/gambling | None in this release | Answer the exact content-rating questions from observed behavior |

**Financial-features explanation**

> Customer portal for showroom jewellery purchase savings plans. Customers make INR
> contributions through Razorpay and receive non-tradable, grade-specific metal
> quantity records for later application under their approved plan terms. The app
> does not provide lending, a bank deposit, interest, securities or cryptocurrency
> trading, a wallet, person-to-person transfer, crowdfunding, a chit fund, or cash
> withdrawal.

**App-access instructions template**

> 1. Open the app and select Sign in.
> 2. Enter the reusable reviewer email address and password supplied in the protected
>    credential fields below.
> 3. The account is an ordinary customer account. It has no owner, staff, Django admin
>    or CMS permissions.
> 4. Use Dashboard to review the synthetic plan/account information and open
>    Contributions and Documents from the customer navigation.
> 5. Savings-plan enrolment is a non-binding request that normally requires showroom
>    approval. Do not submit a real payment; the production Razorpay screen can move
>    real funds.
> 6. Account deletion is available from the signed-in account area. The external
>    deletion page is also available at
>    https://jaishrikrishnajewellery.com/accounts/deletion/.
> 7. For review assistance contact admin@jaishrikrishnajewellery.com or
>    +91 94894 81436 during published business hours.

Never put the reviewer email or password in this file. The reviewer account must be
separate from deletion-test identities and remain stable for the complete review
window.

### Manual-only owner queue

These actions cannot be completed safely by repository automation:

- wait for each Workspace alias to receive an independently sent message; reactivate
  a Postmark hard-bounce suppression only after delivery works;
- enter and save Play Console forms under the verified organization account;
- confirm that app accounts are limited to the selected adult audience before saving
  the Target audience declaration;
- capture privacy-safe screenshots from the Play-installed app and upload the icon,
  feature graphic and screenshots;
- create and privately store the stable reviewer credentials after its alias works;
- review the Data Safety preview, financial declaration and country availability;
- press Submit for production review only after an explicit final release decision.

Repository work covers copy, evidence, field mapping and review. It never needs the
owner's Play password, recovery codes, OAuth secret, signing key or reviewer password.

## Play organization and signing ownership

The app represents a commercial jewellery business and must use a business-owned
Google Play organization account. Before development begins, record evidence that:

- the organization account is verified for Jai Sri Krishna Jewellery and its public
  contact details match the website;
- the required D-U-N-S and payments-profile checks are complete;
- the owner-controlled business identity is the primary account owner and at least
  one separately controlled recovery method exists;
- Rajesh Rathod H receives only the roles required for development/release work;
- Play App Signing is enabled and the owner can recover account and signing access;
- production and development signing fingerprints are recorded separately and only
  approved fingerprints enter Digital Asset Links;
- no signing key, service-account credential, OAuth secret, or Play credential is
  stored in this Django repository or on the Linode serving host.

Current status: **the owner confirmed on 8 September 2026 that the organization is
verified, the package is registered, and a Play App Signing SHA-256 fingerprint
exists.** The D-U-N-S number itself remains in the private Play/payments verification
flow and must not be committed. Exact fingerprint comparison, payments-profile
matching, account recovery, and least-privilege role evidence still need to be
retained before an Android release.

### Manual Play account and draft-app sequence

Perform these steps only through the official Google Play Console while signed in to
an owner-controlled business Google account:

1. Check the Dun & Bradstreet record first. Its legal organization name and address
   must exactly match the organization payments profile; the public developer name
   may still be `Jai Sri Krishna Jewellery`.
2. Protect the owner Google account with two-step verification and owner-controlled
   recovery methods. Do not use the developer's personal Google account as the sole
   business owner and do not share a password.
3. Start Play Console registration and select **Organization**, not Personal. Link or
   create the organization Google Payments profile and enter the D-U-N-S number only
   in that private flow.
4. Supply the organization website, phone, authorized-representative identity, and
   any requested organization documents. Verify the contact email and phone. Use
   supported unmodified documents whose names and addresses match the payments/Dun &
   Bradstreet records.
5. Use `Jai Sri Krishna Jewellery` as the public developer name. Use the business
   website and monitored business support details; expect organization developer
   contact details to be displayed publicly.
6. Complete the registration payment and every identity/contact verification task,
   then wait until Play Console shows the developer identity as verified. Do not
   interpret a submitted or pending state as verification.
7. From **Home → Create app**, choose an English (India) default language, app name
   `Jai Sri Krishna Jewellery`, **App**, **Free**, and
   `admin@jaishrikrishnajewellery.com` as the support email. Review the declarations
   and Play App Signing terms before accepting them.
8. Keep the new app as a draft. Do not upload an empty/placeholder AAB or APK merely
   to occupy the package name, do not begin production review, and do not complete
   policy declarations with guessed answers.
9. In **Users and permissions**, invite the developer through a separate Google
   identity only after the owner account is verified. Grant app-specific and release
   permissions needed for the work; avoid account-wide Admin and financial-data
   permissions unless a later task proves they are necessary.
10. Record only non-secret evidence in this document: organization/identity verified,
    payments-profile match confirmed, public developer name, recovery ownership,
    role review completed, and draft app created. Never record the D-U-N-S number,
    identity documents, payment profile identifiers, recovery codes, credentials, or
    signing private keys.

The owner completed organization verification, draft-app creation, package
registration, and Play-managed signing-identity creation on 8 September 2026. On 9
September the distinct upload key was created outside every repository and serving
host, two encrypted owner-controlled backups were checksum-verified, and encrypted
GitHub secrets produced a signature-verified AAB in workflow run `34263042974`. Play
accepted it for Internal Testing and displayed the matching upload-certificate
fingerprint. The upload certificate is not a Digital Asset Links identity.

Read-only inspection of the app installed from Play independently identified Google
app-signing certificate
`B8:A3:25:32:0B:80:2C:2A:E1:9B:EA:F7:30:27:C4:89:E5:2D:D6:1F:E4:60:F2:99:2F:6E:C6:54:14:24:17:B4`.
The installed package, version `1.0.0`/code `1`, and canonical origin were correct,
but Android reported failed domain verification because production listed only the
previously recorded Play certificate. The safe correction retains both Play-managed
certificates and continues excluding the distinct upload key.

## Financial-features declaration draft

Every Play app must complete the declaration, including apps on testing tracks. The
recommended conservative draft is **Other**, described as:

> Customer portal for showroom jewellery purchase savings plans. Customers make INR
> contributions through Razorpay and receive non-tradable, grade-specific metal
> quantity records for later application under their approved plan terms. The app
> does not provide lending, a bank deposit, interest, securities or cryptocurrency
> trading, a wallet, person-to-person transfer, or cash withdrawal.

Do not select "no financial features" merely because the plan is not presented as an
investment. Do not select lending, wallet, transfer, trading, crowdfunding, or chit
fund categories unless the actual service changes or a review establishes that they
apply. The owner may use the conservative **Other** classification above after
checking it against the exact current Console choices. Seek professional advice if
the business cannot confidently distinguish its service from a listed regulated
category; external sign-off is recommended but is not a blanket repository or form-
drafting prerequisite.

Current status: **copy-ready owner-reviewed working classification; Play Console
entry and final owner submission remain manual release gates.** This does not replace
the deferred wider production controls under `FW-PROD-005`.

## Data Safety working inventory

This is a conservative working inventory, not a submitted Play declaration. The
final form must be regenerated from the exact PWA, TWA, Android dependencies,
Cloudflare settings, Razorpay flow, Google login, logging, and provider contracts in
the release candidate.

| Play data area | Current application behavior | Working answer |
| --- | --- | --- |
| Name | Registration/profile and customer records | Collected |
| Email address | Registration, login, notifications, support | Collected |
| User IDs | User, customer, scheme, provider and linked-Google identifiers | Collected |
| Address | Required by the staged registration request | Collected |
| Phone number | Registration and owner verification | Collected |
| Purchase history | Contributions, receipts, redemptions and transaction state | Collected |
| Other financial info | Grade-specific Scheme Rates, quantities and scheme balances | Treat as collected pending Play-form review |
| User payment info | Entered directly into Razorpay Checkout; the app does not store card number, CVV, UPI PIN or bank password | Do not declare provider-only credentials if the release audit confirms the app never accesses them |
| App interactions | Page/use telemetry may be visible to edge or web-analytics services | Pending Cloudflare analytics and access-log audit |
| Device or other IDs | IP/user-agent/security metadata and any provider identifiers require exact classification | Pending release audit; pseudonymous data is not automatically exempt |
| Crash/diagnostic data | Server errors and Android/TWA diagnostics are not yet fully designed | Pending Android dependency and Play reporting decision |

Expected purposes are app functionality, account management, fraud prevention,
security/compliance, and developer communications where applicable. No advertising
or data-sale purpose is approved. Whether transfers to Cloudflare, Linode/Akamai,
Postmark, Google, or Razorpay qualify as service-provider processing or reportable
sharing must be checked against the final contracts and integration. Data is sent
over HTTPS, but encryption and deletion answers must be verified again at submission.

For the pilot, prefer aggregate server-side measures already derivable from Django
records and privacy-reduced operational logs. Do not add an advertising identifier,
cross-app tracking, session replay, or a third-party mobile analytics SDK merely to
measure the pilot.

## Account-deletion and retention design gate

Because the mobile experience includes account creation, Play requires both a
discoverable in-app path and an external web resource where a person can request
account and associated-data deletion. The existing contact/privacy text permits a
general privacy request but is not a dedicated deletion-request workflow.

The future implementation must:

1. Accept a deletion request from authenticated account settings and from a public,
   stable HTTPS page usable after uninstalling the app.
2. Verify the requester without emailing a reusable raw credential or exposing
   whether an unrelated account exists.
3. Immediately define containment for a compromised account: disable login, revoke
   sessions and linked social access, and block new financial actions while review is
   pending.
4. Distinguish profile/contact data that can be deleted or irreversibly anonymized
   from append-oriented scheme, contribution, allocation, receipt, redemption,
   reversal, provider, consent and audit records that may require justified
   retention.
5. State the request acknowledgement, review, completion, rejection/partial-retention
   explanation, and appeal/support process in plain language.
6. Propagate deletion requests to applicable service providers where their retained
   data is not independently required.
7. Record an auditable owner decision without deleting or rewriting financial source
   records, and test referential integrity before release.

No blanket financial-record retention period is approved here. On 10 September
2026 the owner accepted ADR-0015's revised owner-operated implementation boundary:
professional written sign-off is no longer a blanket development prerequisite.
Category-specific purposes, necessary identifying fields, start events, retention
periods/hold-release conditions, external follow-ups and review dates must still be
documented before execution and accurately reflected in the privacy notice and Data
Safety form. Seek professional advice where applicability is uncertain; an AI-assisted
implementation is not legal/accounting certification.

Current status: **completion is deployed and request intake is enabled.** Release
`b349a84fdc716a87e85110386868923fad95326e` passed owner-reported Live/Ready,
deletion, authentication-email and financial checks with policy version `2026-09-10`.
The Bootstrap owner reauthentication page is production-accepted. The first app-path
request is held because it has two agreements and a failed Test-mode contribution;
a second authenticated request also proved unsuitable for the zero-history exercise
because it has one agreement and one enrolment request. On 15 September a later
authenticated-path candidate with zero agreements, enrolments, contributions,
allocations and redemptions completed successfully with no profile fields retained,
one immutable completion decision, an accepted and delivered outcome notice,
unusable credentials and no Google recovery path. The owner confirmed the deletion,
authentication, Google, financial and graded-metal checks. New owner-controlled
Workspace aliases are awaiting mail propagation for a separate public-path,
zero-history completion test. Owner preview,
completion/minimization, retryable notices and retention reviews are automatically
tested; the authenticated production completion is accepted, while end-to-end public
email-verification deletion acceptance has not occurred.
Public wording and an implementation-aligned category baseline are now prepared in
ADR-0015, Privacy and the two feature-gated deletion entry pages. Actual provider
settings, per-category release conditions, restore suppression and applicant disposal
are not verified by that wording. Actual completion evidence, provider follow-up and
recovery-record reconciliation remain public-release blockers; enablement itself is
complete.
The preview is not proof that any records may be erased. No bulk `CustomUser`
deletion or hidden database edits are permitted.

## Platform and device support baseline

- Product support floor: Android 10 (API 29) or newer with an actively supported,
  TWA-capable browser and working Android System WebView/Google Play services where
  needed. Older devices are best-effort web-browser access, not a promised app target.
- Build target: Android 16/API 36 for a new Play submission after 31 August 2026.
  Recheck Play policy immediately before every release rather than freezing this
  value in long-lived guidance.
- Primary test browser: current stable Chrome. Browser fallback must also be tested
  when no verified TWA-capable browser is available.
- Required device coverage: one Android 10/11 lower-memory device, one Android 12/13
  mid-range device, and one Android 14–16 current device; include slow mobile data,
  Wi-Fi-to-mobile switching, offline launch, browser/process death, and low-memory
  restart.
- Required display/input coverage: small phone, large phone, increased font size,
  screen reader/keyboard navigation where applicable, portrait/landscape, Tamil and
  English keyboard input, and India-local date/time/currency presentation.

The support floor is a product default and must be checked against the actual devices
used by pilot customers before it becomes a public promise.

## Review account

Play reviewers need durable English instructions and reusable credentials that work
independently of OTP or a developer's personal Google account. Before submission:

- create a dedicated non-privileged customer reviewer account with synthetic data;
- keep password login active and do not grant owner, staff, Django admin, or Wagtail
  access;
- provide stable instructions through Play Console only, never in the repository;
- show representative scheme/receipt/statement history without copying a real
  customer's identity or payment data;
- explain that enrolment needs owner approval and that a live contribution can move
  real funds; do not add a production mock-payment bypass;
- verify the account before every submission and rotate it after the review window if
  policy permits while keeping the next submission maintainable.

Current status: **instructions prepared; account creation waits for a receiving
Workspace alias.** The account must remain distinct from every deletion-test identity
and must be verified from the Play-installed app before its credentials are entered
only in Play Console.

## Internal Testing customer-journey matrix

### Owner-reported pilot evidence — 10 September 2026

The owner reports approximately five pilot customers, with more expected, and
confirms that authentication, registration, enrolment, payments, and documents work
through the Play-installed Android app. These are accepted as owner-reported core
journey passes. Exact build/web release, device versions, payment mode, individual
negative cases, and log inspection evidence were not supplied with this confirmation.
Do not infer that every assertion in the detailed matrix below has been exercised.

| Core journey | Reported result |
| --- | --- |
| Authentication | Owner-confirmed pass in Play-installed app |
| Registration | Owner-confirmed pass in Play-installed app |
| Enrolment | Owner-confirmed pass in Play-installed app |
| Payment journey | Owner-confirmed pass in Play-installed app |
| Receipts/statements | Owner-confirmed pass in Play-installed app |

`FW-MOBILE-004` is underway. `FW-MOBILE-003` remains in final acceptance pending
the remaining device, edge-case, and privacy evidence. Collect missing metadata
from the existing pilot where available; repeat a successful core journey only if a
changed release or unresolved defect requires it. The rows below track the more
specific assertions, not a denial of the reported core journey results.

Run this matrix against one immutable Internal Testing build before inviting a wider
pilot. Record only the build/version, production release, device/Android/browser,
date, pass/fail result, and a redacted support reference. Never store passwords,
verification/reset links, Razorpay signatures, API credentials, full payment
identifiers, or customer personal data in repository evidence.

Use a dedicated non-privileged test customer and a separate owner session. Start and
finish with the application integrity commands named in the production guide. A
registration or enrolment test must prove that no scheme account or financial record
is created before its owner approval boundary. A Live payment is limited to one
owner-approved low-value transaction after all Test-mode payment cases pass.
Run Razorpay Test cases on an isolated test deployment with separate credentials
and data. Do not switch the serving Live deployment to Test mode for this matrix.
Use existing accepted payment evidence when sufficient; no additional real payment
is implied by recording these results.

| Area | Controlled case | Acceptance | State |
| --- | --- | --- | --- |
| TWA | Launch the Play-installed build from the launcher | Canonical origin opens without browser chrome; association remains verified | Passed 9 Sep 2026 |
| Password identity | Login, logout, relaunch, password reset, then login again | Only the intended customer session exists; reset link is single-use and absent from logs | Not run |
| Google identity | Login with the linked Google identity, then try an unlinked identity | Linked customer reaches the same account; unlinked identity creates no user/profile | Not run |
| Registration | Submit, verify, approve, and complete one staged registration | Direct allauth signup remains blocked; no customer exists before owner approval | Not run |
| Enrolment | Submit interest, inspect both queues, then approve it | No account/contribution/order/rate lock/allocation exists before approval; one account exists after | Not run |
| Razorpay Test | Complete success, explicit failure, modal cancellation, and checkout expiry | State and messages are correct; only captured success allocates metal; reconciliation is clean | Not run |
| Operations pause | Pause the applicable grade before checkout and while an order is open | New initiation is blocked; webhook truth remains accepted; no duplicate allocation occurs | Not run |
| Razorpay Live | Make one pre-approved low-value contribution | Captured webhook, one allocation, receipt, statement, and reconciliation all agree | Not run |
| Documents | Open and print/download the accepted contribution receipt and statement | Amount, grade, rate, grams, identifiers, and totals agree; no other customer is exposed | Not run |
| Lifecycle | Background/kill/relaunch during login and checkout return; reboot once | Server state remains authoritative; no duplicated request, order, payment, or allocation | Not run |
| Network/offline | Launch offline, use slow data, and switch Wi-Fi/mobile during safe reads | Generic offline behavior appears; authenticated/financial pages are not served from cache | Not run |
| Update | Upgrade from the previous Internal Testing build | Session behavior is intentional; data and Digital Asset Links verification remain intact | Not run |
| Accessibility | Test 200% text, portrait/landscape, TalkBack labels/focus, and contrast | Core customer journey remains readable, operable, labelled, and free of blocking defects | Not run |
| Privacy/logs | Inspect Android, Caddy, and web logs after all cases | No credential, token, signature, personal-data payload, or authenticated document body is retained | Not run |

Any critical/high defect, financial mismatch, identity-boundary breach, or secret/data
leak stops the matrix. Fix it in a separate reviewed release and rerun every affected
case plus the opening and closing integrity checks.

## Pilot measures and acceptance gates

Use approximately five to ten legitimate customers under `FW-MOBILE-004`. Retain
aggregate evidence only.

| Gate | Acceptance |
| --- | --- |
| Financial safety | Zero duplicate entitlements, cross-grade allocations, paid-unallocated exceptions, client-authoritative payment results, or cached authenticated records |
| Identity | Password/reset and linked-Google flows pass; unlinked Google identities create no account; owner/staff routes are not exposed as mobile features |
| Core journey | At least 80% of observed participants complete login, scheme viewing, and enrolment-request tasks without staff operating their device |
| Payment | Razorpay Test success/cancel/failure/expiry and pause behavior pass, followed by one pre-approved low-value Live payment with webhook, allocation, receipt, and reconciliation evidence |
| Reliability | No unresolved critical/high defect; TWA verification, fallback, process death, update, offline and slow-network cases pass on the device matrix |
| Accessibility | No known blocking keyboard, screen-reader, zoom/font-size, focus, label, or contrast defect in the customer journey |
| Support | Record app-caused contacts and recurring confusion; do not claim success if staff must routinely finish the journey for customers |
| Privacy | No secrets or registration/payment tokens in logs, cache, package, screenshots or analytics; submitted policy answers match observed release behavior |

Metrics are decision evidence, not marketing claims. `FW-MOBILE-005` must use them to
decide whether native Android/API cost and future iOS development are justified.

## Exit checklist for FW-MOBILE-001

- [x] Customer-only journey and exclusions recorded.
- [x] Proposed app name, package identifier, origin, market, category and audience recorded.
- [x] Savings-not-investment store-copy foundation recorded.
- [x] Conservative Financial features declaration draft recorded.
- [x] Data Safety working inventory recorded.
- [x] Deletion/retention workflow requirements recorded.
- [x] Android support floor, target API and device/browser matrix recorded.
- [x] Reviewer-account and pilot acceptance requirements recorded.
- [x] Business owner approved the permanent package identifier and store identity on 5 September 2026.
- [x] Business owner confirmed the organization D-U-N-S prerequisite is available on 7 September 2026; the number is not stored here.
- [x] Verified organization Play account recorded.
- [x] Approved package registered and Play App Signing identity created.
- [x] Exact Play signing fingerprint deployed and independently compared on the canonical origin.
- [ ] Matching payments profile, recovery and least-privilege role evidence recorded.
- [ ] Financial classification review and owner-approved category-specific retention procedures completed (ADR-0015 revision).
- [x] Dedicated deletion workflow implemented, regression-tested, deployed/enabled and reflected in public policy; authenticated zero-history completion accepted 15 September 2026.
- [ ] Separate signed-out deletion verification/completion, provider follow-up and independent recovery-record reconciliation accepted; authenticated acceptance does not close this gate.
- [ ] Release-candidate Data Safety answers reviewed against every dependency/provider.

Reconciled against recorded implementation/acceptance on 22 October 2026; no new
Console, provider or production inspection was performed. `FW-MOBILE-002` is already
production-accepted, and the signed TWA is in Internal Testing. Do not repeat those
foundations as pending work. No Play public release may pass while an outstanding
exit gate or the immediate submission/device checks above remain open. Recheck
platform requirements against the release candidate before submission.

## Authoritative references

- [W3C Web Application Manifest](https://www.w3.org/TR/appmanifest/)
- [Chrome installable-manifest criteria](https://developer.chrome.com/docs/lighthouse/pwa/installable-manifest)
- [Chrome DevTools PWA inspection](https://developer.chrome.com/docs/devtools/progressive-web-apps)
- [Choose a Play developer account type](https://support.google.com/googleplay/android-developer/answer/13634885)
- [Financial features declaration](https://support.google.com/googleplay/android-developer/answer/13849271)
- [Play account deletion requirements](https://support.google.com/googleplay/android-developer/answer/13327111)
- [Play Data Safety guidance](https://support.google.com/googleplay/android-developer/answer/10787469)
- [Play App content requirements](https://support.google.com/googleplay/android-developer/answer/9859455)
- [Play store-listing preview asset requirements](https://support.google.com/googleplay/android-developer/answer/9866151)
- [Play reviewer sign-in requirements](https://support.google.com/googleplay/android-developer/answer/15748846)
- [Play target API requirements](https://support.google.com/googleplay/android-developer/answer/11926878)
- [Registering Android package names](https://support.google.com/googleplay/android-developer/answer/16761053)
- [Trusted Web Activity overview](https://developer.android.com/develop/ui/views/layout/webapps/trusted-web-activities)
- [ADR-0014](decisions/ADR-0014-pwa-twa-first-mobile-distribution.md)
