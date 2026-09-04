# ADR-0011: Staged public customer registration

## Status

Accepted for implementation under `FW-AUTH-002`. Public registration remains
disabled until its separate production rollout is approved.

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
