# ADR-0011: Staged public customer registration

## Status

Product amendment approved 5 October 2026: implement a plan-first application and
one coordinated showroom review in the four phases in `docs/MVP_PLAN.md`. Phase 1
changed public entry/copy and measurement: a validated selected plan was shown on
the existing registration form without durable cross-verification preferences.
Phase 3 is now implemented and verified locally as amended below. It revises
AUTH-003/010 for newly linked applications: contact-first intake, remaining fields
before approval, explicit contact/current-terms review, transactional identity plus
agreement orchestration, distinct audit evidence and retryable after-commit notices.
Existing registrations, identity records, agreements and login access are preserved.
No production enablement is authorized by this amendment.

Phase 2 implementation (5 October 2026) consolidates owner navigation into Today,
Applications, Customers and the retained financial overview/Operations. Registration
and plan-request records share a bounded inbox and review layout with an explicit
next action. Unverified delivery/expiry recovery remains available without approval
bypass. Approved registrations link to customer context by `approved_user` only.
The registration approval service, invitation evidence, separate agreement action
and historical registration URLs remain unchanged in authority. This is workspace
consolidation; coordinated identity/agreement approval is implemented by the Phase 3
amendment below.

Accepted for implementation under `FW-AUTH-002`. Public registration remains
disabled until its separate production rollout is approved.

### Phase 3 implementation amendment (5 October 2026)

The earlier decisions below remain the historical access-only and existing-customer
contracts. Phase 3 supersedes their two-review public journey for newly linked plan
applications only; it does not merge identity with the financial agreement or migrate
historical registrations into plan intent.

`PlanApplication` links one registration to its selected offer/preferences and at most
one separate `SchemeAccount`. Append-only `PlanApplicationConfirmation` revisions
retain initial and renewed customer evidence. Contact submission retains plan, exact
grade, amount, duration and message; postal address and explicit current policy/offer
and requested start-date confirmation follow protected email verification. A changed
offer or a start date that passes before approval requires renewed customer confirmation.
The form digest binds consent to displayed terms; money is serialized as decimal strings.

Owner coordinated approval locks registration, application, plan and offering, rechecks
identity conflicts and customer evidence, and calls the existing identity/invitation and
`enroll_customer` services in one transaction. Any financial failure rolls back identity
and invitation too. The one-to-one agreement link and row locks make retries/concurrent
approval return the same agreement. Identity actor/reason/contact evidence and the
financial audit/agreement snapshots remain distinct. Legacy identity-only approval
cannot bypass this service for linked applications.

Activation delivery occurs after commit; failed/absent delivery remains recoverable
from the existing customer invitation controls. Progress access has a separate random,
digest-only credential, the application expiry and a CSRF-confirmed session grant.
Verification remains one-use; progress access is resumable within its scope/expiry.
Owner replacement revokes old progress links/sessions without extending expiry. Progress
emails opt out of tracking; edge/Django logs exclude/redact these paths. No progress
route sends identifiers or tokens to analytics. Disabled/erased customers lose access.

Existing customers keep the authenticated request flow using the held profile; they do
not repeat contact/address intake. Current disclosure changes or a different duration
require withdrawal/closure and a new customer request. Legacy records, authentication,
permissions, liabilities and historical financial evidence remain unchanged. No new
worker, API, frontend framework, authentication system or production rollout is added.
Phase 4 still owns activation continuation, dashboard prominence and expired-activation
recovery. Production migration/deployment requires separate approval.

### Phase 4 implementation amendment (5 October 2026)

Linked-plan password setup retains the approved agreement destination through the
existing password login. Activation still creates no financial record and does not
auto-authenticate; legacy access-only invitations retain their login entry.
An eligible expired invitation's exact secret may record a CSRF-protected, repeat-safe
setup-help request. `CustomerInvitation.recovery_requested_at` is additive metadata,
not an access grant or an automatic invitation. Response pages reveal no account state.
User-then-invitation locks serialize recovery with issue/accept. Replacement remains
active-owner-only; existing resend revokes previous unused links, records mail failure
and leaves agreement/history unchanged. Today includes latest eligible expired or
failed/pending delivery in a bounded, paginated owner recovery queue.
The implementation is locally reviewable; production migration/rollout is not authorized.

## Context

The current owner-created customer workflow deliberately separates a login from a
savings agreement. Simply opening django-allauth signup would create an immediately
usable login with only an email address and password. It would not collect the
customer profile, prove control of the contact address, handle duplicate identities,
record policy consent, obtain owner approval, or create the explicit showroom
enrolment contract required before contributions are allowed.

Public forms also create enumeration and abuse risks. A safe design must not reveal
whether an email or mobile number already exists, must not store a customer-selected
password before approval, and must not let an unapproved applicant reach payment or
financial records.

## Decision

- Keep django-allauth self-signup closed. Public registration is a separate,
  feature-gated customer-access application, disabled by default.
- An application collects the complete profile needed by the existing owner flow:
  name, email address, Indian mobile number, and postal address. It also records the
  exact Terms and Privacy Policy versions accepted and the consent timestamp.
- A submitted application is not a `CustomUser`, `Customer`, `SchemeAccount`, or
  financial entitlement. No password is collected or stored at this stage.
- Email control is verified through a bounded, one-time, digest-only token. A link
  opens a confirmation page; verification occurs only on a CSRF-protected POST so
  mail scanners cannot consume the token by following a GET.
- After email verification the application enters an explicit
  `AWAITING_OWNER_APPROVAL` state. Only an active owner may approve or reject it, and
  every decision records the actor label, timestamp, and reason.
- The owner must confirm that the mobile number was checked with the applicant before
  approval. Automated SMS verification is not claimed or introduced without a
  separately selected provider and threat/cost review.
- Approval rechecks email and mobile conflicts, creates the existing customer login
  and profile atomically, and issues the existing one-time password-setup invitation.
  The approved customer still has no usable password until accepting that invitation.
- Approval never creates a `SchemeAccount`. Showroom enrolment remains a separate,
  owner-only action after terms are reviewed; an approved login with no enrolment sees
  no contribution action or financial entitlement.
- Public responses are deliberately generic for existing identities, active
  applications, and throttled submissions. Database-backed per-source and
  per-identity attempt limits plus a honeypot provide baseline abuse control without
  Redis or a new service. Edge rate limiting or a challenge may be added later as
  defence in depth.
- Secret-bearing verification paths are excluded from edge access logs, redacted
  from application logs, non-cacheable, and governed by the same direct-link policy
  as invitation and password-reset URLs.
- Expired unverified applications may be replaced by a later submission. Approved
  and rejected records are retained as review evidence and are never silently merged
  with an existing customer.

## Consequences

The public journey is longer than direct signup, but it preserves the existing
identity, approval, and financial boundaries. Owners receive a review queue and use
the already-tested invitation mechanism instead of transmitting passwords.

Enabling registration requires reviewed public copy, working transactional email,
current consent-version settings, and controlled production verification. This ADR
does not enable the feature. SMS OTP, automated identity verification, applicant
self-service status lookup, and edge challenge products remain separate future
decisions rather than hidden dependencies of this phase.

## Presentation amendment (22 October 2026)

The approved workflow refinement adds role-specific navigation, bounded applicant search,
safe filtered inbox return paths, customer Applications/Documents destinations and clearer
contact/duration/stage guidance. The owner customer workspace groups related records;
customer Home avoids duplicate payment actions for a converted application/agreement.
HTMX is limited to read-only owner customer/application/payment/exception filtering and manual
customer recorded-payment status;
it does not enhance registration/verification/progress, identity approval, agreement
conversion or credential setup. Transactional orchestration, renewed material-term consent,
separate identity/agreement evidence, after-commit notices and recoverable delivery remain
unchanged. Protected progress now shows six record-derived milestones through real first
payment; Test/practice and reversed records cannot complete it. Scoped stage counts and
exact-customer privacy context add no schema or financial mutation. See ARCHITECTURE.md and
DOMAIN_RULES.md UX-006 through UX-010.
