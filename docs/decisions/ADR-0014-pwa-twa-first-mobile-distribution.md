# ADR-0014: PWA and Trusted Web Activity first for mobile distribution

## Status

Accepted for phased planning under `FW-MOBILE-001` through `FW-MOBILE-005`.
Implementation and public-store release remain separate reviewed decisions.

## Context

Stakeholders expect an Android application to make the customer savings-plan journey
easier to discover and revisit. The current responsive Django application already has
production-accepted customer registration, owner approval, password and linked-Google
authentication, non-binding enrolment requests, exact-grade Scheme Rates, Razorpay
Checkout, signed webhooks, receipts, eligibility, operational pauses, and append-
oriented financial records.

The repository has no Progressive Web App manifest or service worker and exposes no
mobile API. A native client would therefore require a new public authentication and
authorization boundary, token lifecycle, versioned API, native Razorpay integration,
client release process, and duplicated presentation work before proving that customers
need those costs. It would also risk moving financial decisions away from the existing
tested Django services.

A generic embedded WebView is unsuitable. Google OAuth policy prohibits authorization
through a developer-controlled embedded user agent. Android Trusted Web Activity (TWA)
instead renders an owned web application using a supporting browser and verifies the
relationship between the signed Android package and domain through Digital Asset
Links.

The public product must continue to be described as a jewellery savings-plan
contribution and recorded metal accumulation journey. Mobile copy must not introduce
unreviewed investment, yield, guaranteed-return, cash-conversion, or provider claims.

## Decision

- Deliver mobile capability in stages: a safe installable PWA, an Android TWA shell,
  a controlled Play internal-test pilot, and only then a native/API go-or-no-go review.
- The first Android release is customer-only. Owner, staff, rate publication, approval,
  showroom-cash recording, redemption recording, and operational-control workflows
  remain on the authenticated web application.
- The TWA uses the canonical owned HTTPS origin and current Django session, CSRF,
  password/reset, and explicitly linked Google flows. It does not introduce a mobile
  authentication token or API.
- Django and PostgreSQL remain the sole financial source of truth. The Android shell
  never calculates or persists an authoritative balance, rate lock, allocation,
  eligibility decision, payment result, or liability.
- Razorpay order creation, signature verification, webhook processing, idempotency,
  checkout expiry, payment-operation controls, and allocation remain server-side.
  Neither a PWA nor Android package contains a Razorpay secret or treats a client
  callback as proof of payment.
- The PWA service worker, if implemented, uses an explicit allowlist. Authenticated,
  identity, registration-token, scheme, rate, contribution, payment, receipt,
  statement, eligibility, OAuth callback, health, and administrative responses are
  network-only and are never served from a cache. Offline mode may provide only a
  static connection-required response and previously approved non-authoritative public
  assets.
- The Android shell lives in a separate repository and is built, signed, scanned, and
  released through CI. It is never built on the resource-constrained Linode serving
  host. This Django repository owns the web manifest, safe service-worker boundary,
  canonical routes, and `/.well-known/assetlinks.json`.
- The Android package identifier and signing identity are permanent release contracts.
  Digital Asset Links must cover the actual Play App Signing certificate and any
  separately approved development fingerprint without weakening production matching.
- Public release is blocked until the organization Play account, store identity,
  financial-features declaration, Data Safety answers, privacy disclosures, support
  details, and an in-app plus external account-deletion request path are reviewed.
  Deletion must distinguish removable profile data from financial records that require
  justified retention; historical financial records are never silently erased.
- The pilot measures customer activation, plan-to-enrolment conversion, contribution
  completion, payment failure/cancellation, repeat use, and app-caused support demand.
  It must exercise password and linked-Google login, an unconnected Google rejection,
  payment cancellation/expiry, operational pause, Razorpay Test mode, and one approved
  low-value Live reconciliation before wider release.
- A native client requires a new ADR. It must authorize a versioned customer API,
  mobile credential and revocation lifecycle, native provider integrations,
  idempotency and rate limiting, secure device storage, and a separate threat model.
  Existing services/selectors remain authoritative and no mobile client may write the
  database directly.
- If the pilot later justifies native Android and near-term iOS delivery, evaluate a
  shared cross-platform client such as Flutter. If Android remains the only native
  target, evaluate Kotlin and Jetpack Compose. Neither choice is made by this ADR.
- An installable web application is the interim iOS path. A future App Store client
  must provide genuine app-specific utility and receives its own architecture and
  review decision; a simple website wrapper is not assumed acceptable.

## Consequences

Customers can receive an Android app-like entry point without creating a second
financial or identity system. PWA work improves the ordinary mobile website and the
pilot can validate stakeholder assumptions before the project accepts native-client
cost and API risk. Web, TWA, and desktop users continue to receive the same server-
enforced controls and immediate application updates.

The first Android release depends on network availability and a compatible browser.
It offers no authoritative offline balance or payment behavior, native biometric
credential, owner features, or native push-notification promise. TWA behavior and
Razorpay/UPI return paths require real-device testing. Future iOS App Store delivery is
not solved by the Android shell.

Store policy and business classification can block public release even when the
software is technically ready. Qualified legal/accounting and provider review remain
necessary before selecting the savings plan's financial declaration or claiming that
an external-payment exception applies.

## References

- [Android Trusted Web Activity overview](https://developer.android.com/develop/ui/views/layout/webapps/trusted-web-activities)
- [Android Trusted Web Activity quick start and Digital Asset Links](https://developer.android.com/develop/ui/views/layout/webapps/guide-trusted-web-activities-version2)
- [Google OAuth 2.0 policies](https://developers.google.com/identity/protocols/oauth2/policies)
- [Google Play Financial features declaration](https://support.google.com/googleplay/android-developer/answer/13849271)
- [Google Play account deletion requirements](https://support.google.com/googleplay/android-developer/answer/13327111)
- [Google Play Data Safety guidance](https://support.google.com/googleplay/android-developer/answer/10787469)
- [Google Play payments policy](https://support.google.com/googleplay/android-developer/answer/9858738)
- [Google Play target API requirements](https://support.google.com/googleplay/android-developer/answer/11926878)
- [Razorpay Android Standard Checkout guidance](https://razorpay.com/docs/payments/payment-gateway/android-integration/standard/troubleshooting-faqs/)
- [Apple App Review Guidelines](https://developer.apple.com/app-store/review/guidelines/)
