# Mobile Release Readiness

This document is the canonical readiness record for `FW-MOBILE-001`, the bounded
`FW-MOBILE-002` PWA foundation, and `FW-MOBILE-003` Android TWA delivery. It implements
ADR-0014 without adding a mobile API, native authentication, or client-authoritative
financial logic.

Status: **in progress — `FW-MOBILE-002` is production-accepted, the verified
organization owns the registered Play package and Play-managed app-signing identity,
and the isolated Android TWA foundation passes local and GitHub-hosted unsigned
release builds. The owner supplied the exact Play App Signing fingerprint and the
canonical origin now has a disabled-by-default Digital Asset Links implementation.
Production association verification, Financial classification, retention/deletion,
Data Safety, signed release, device, and Play release gates remain open.**

## Product boundary

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

On 8 September 2026 the owner supplied the exact **Play App Signing key certificate**
SHA-256 fingerprint for the registered package:

`25:78:42:37:4E:7A:C9:62:C8:AF:90:11:E3:8C:86:32:E2:08:DF:E4:6E:77:C0:86:59:7F:31:E7:32:D7:07:97`

This public certificate identity is intentionally recorded; no private signing
material is present. The Django origin has a disabled-by-default implementation for
`/.well-known/assetlinks.json` that binds only this fingerprint and
`com.jaishrikrishnajewellery.savings`. It must still be deployed, enabled, compared
character-for-character with Play Console, and verified from an installed Play-signed
build. Do not add an upload-key or local debug certificate fingerprint to the
production statement.

## Store listing copy draft

Short description:

> View jewellery savings plans, track contributions and access scheme records.

Full-description foundation:

> Jai Sri Krishna Jewellery customers can browse showroom jewellery and savings
> plans, request enrolment, view approved scheme accounts, make INR contributions
> through Razorpay, and review contribution receipts, accumulated grade-specific
> metal quantity and eligibility information. Scheme approval, jewellery selection,
> fulfilment and redemption remain controlled by the Vellore showroom and the
> customer's recorded terms. This is not a bank deposit, interest-bearing account,
> investment or metal-trading application.

Public listing links:

| Purpose | URL/status |
| --- | --- |
| Website | `https://jaishrikrishnajewellery.com/` — available |
| Privacy policy | `https://jaishrikrishnajewellery.com/privacy/` — available; must be updated for the app and deletion process |
| Terms | `https://jaishrikrishnajewellery.com/terms/` — available |
| Support | `https://jaishrikrishnajewellery.com/contact/` and `admin@jaishrikrishnajewellery.com` — available |
| Account deletion | **Missing — public release blocker** |

Store screenshots, feature graphics, icon assets, and final copy belong to
`FW-MOBILE-002`/`FW-MOBILE-003`, after the real mobile presentation exists. Do not
submit desktop mockups as release evidence.

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
registration, and Play-managed signing-identity creation on 8 September 2026. The
next signing task is not to invent another app-signing key: it is to capture and
independently compare the Play App Signing SHA-256 fingerprint, create a distinct
recoverable upload key outside every repository and serving host, and use only the
Play fingerprint in the production Digital Asset Links statement.

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
fund categories unless a qualified review establishes that they apply. Save the form
as a draft until the business's legal/accounting adviser and Razorpay have reviewed
the actual app flow and wording.

Current status: **provisional classification; qualified review is a public-release
blocker.** This does not replace `FW-PROD-005`.

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

No exact financial-record retention period is approved here. The owner and a
qualified Indian legal/accounting adviser must document the lawful retention basis
and period before the privacy notice, Data Safety form, or deletion promise is
finalized. Application implementation requires a separate scoped change with tests;
it may not use a bulk `CustomUser` deletion or hidden database edits.

Current status: **workflow and retention basis not implemented or approved; public
release blocker.**

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

Current status: **not created; required before Play review.**

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
- [ ] Exact Play signing fingerprint deployed and independently compared; matching payments profile, recovery and least-privilege role evidence recorded.
- [ ] Qualified financial classification and retention review completed.
- [ ] Dedicated deletion workflow implemented, tested, and reflected in public policy.
- [ ] Release-candidate Data Safety answers reviewed against every dependency/provider.

`FW-MOBILE-002` may begin after the product/package defaults are approved, but no Play
public release may pass while any of the final five gates remains open.

## Authoritative references

- [W3C Web Application Manifest](https://www.w3.org/TR/appmanifest/)
- [Chrome installable-manifest criteria](https://developer.chrome.com/docs/lighthouse/pwa/installable-manifest)
- [Chrome DevTools PWA inspection](https://developer.chrome.com/docs/devtools/progressive-web-apps)
- [Choose a Play developer account type](https://support.google.com/googleplay/android-developer/answer/13634885)
- [Financial features declaration](https://support.google.com/googleplay/android-developer/answer/13849271)
- [Play account deletion requirements](https://support.google.com/googleplay/android-developer/answer/13327111)
- [Play Data Safety guidance](https://support.google.com/googleplay/android-developer/answer/10787469)
- [Play reviewer sign-in requirements](https://support.google.com/googleplay/android-developer/answer/15748846)
- [Play target API requirements](https://support.google.com/googleplay/android-developer/answer/11926878)
- [Registering Android package names](https://support.google.com/googleplay/android-developer/answer/16761053)
- [Trusted Web Activity overview](https://developer.android.com/develop/ui/views/layout/webapps/trusted-web-activities)
- [ADR-0014](decisions/ADR-0014-pwa-twa-first-mobile-distribution.md)
