# Mobile Release Readiness

This document is the canonical no-code readiness record for `FW-MOBILE-001`. It
implements the planning decision in ADR-0014 without adding a PWA, Android project,
mobile API, or production behavior.

Status: **in progress — product defaults are recorded; owner, policy, and deletion
workflow gates remain open.**

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

## Proposed permanent app identity

| Item | Proposed value | Gate |
| --- | --- | --- |
| Play app name | Jai Sri Krishna Jewellery | Confirm in Play Console |
| Android package | `com.jaishrikrishnajewellery.savings` | Owner approved 5 September 2026; reserve by creating the Play app and do not change later |
| Publisher | Jai Sri Krishna Jewellery | Must match the verified organization identity |
| Canonical origin | `https://jaishrikrishnajewellery.com` | Already production-owned; reverify before TWA work |
| Initial market | India | Confirm before store setup |
| App category | Shopping | Provisional; do not use it to avoid an accurate financial declaration |
| Target audience | Adults; not designed for children | Confirm through the Play audience/content forms |
| Advertising | None; do not request an advertising ID | Re-audit every Android dependency before release |
| Repository | Separate business-controlled Android repository | Create during `FW-MOBILE-003`, not on Linode |

The business owner approved this permanent package identifier on 5 September 2026.
It is approved but not yet reserved; reservation occurs only when the app is created
in the organization Play Console account. Do not create another production package
or silently change this identifier during Android implementation.

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

Current status: **owner evidence not yet supplied.**

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
- [ ] Verified organization Play account, D-U-N-S, recovery and role evidence recorded.
- [ ] Qualified financial classification and retention review completed.
- [ ] Dedicated deletion workflow implemented, tested, and reflected in public policy.
- [ ] Release-candidate Data Safety answers reviewed against every dependency/provider.

`FW-MOBILE-002` may begin after the product/package defaults are approved, but no Play
public release may pass while any of the final five gates remains open.

## Authoritative references

- [Choose a Play developer account type](https://support.google.com/googleplay/android-developer/answer/13634885)
- [Financial features declaration](https://support.google.com/googleplay/android-developer/answer/13849271)
- [Play account deletion requirements](https://support.google.com/googleplay/android-developer/answer/13327111)
- [Play Data Safety guidance](https://support.google.com/googleplay/android-developer/answer/10787469)
- [Play reviewer sign-in requirements](https://support.google.com/googleplay/android-developer/answer/15748846)
- [Play target API requirements](https://support.google.com/googleplay/android-developer/answer/11926878)
- [Trusted Web Activity overview](https://developer.android.com/develop/ui/views/layout/webapps/trusted-web-activities)
- [ADR-0014](decisions/ADR-0014-pwa-twa-first-mobile-distribution.md)
