# ADR-0013: Google as a linked customer credential

## Status

Accepted for implementation under `FW-AUTH-004`. Production enablement remains a
separate, disabled-by-default rollout decision.

## Context

The application already has a controlled identity lifecycle. Public registration is
a staged application with email verification and owner approval; an approved customer
then activates a password through the existing invitation flow. Login is deliberately
separate from scheme enrolment and every financial entitlement.

Allowing django-allauth's normal social signup or email-based account matching would
create a second onboarding path. It could create a user before owner approval or bind
an external identity to a local financial account merely because email strings match.
That would weaken the existing boundary and make provider behavior part of customer
approval.

## Decision

- Google is the only social provider in this phase and is an optional authentication
  credential, not a registration, approval, profile, or enrolment mechanism.
- Only an active, non-staff `CUSTOMER` with a usable password and a verified local
  login email may initiate connection from an authenticated account-security page.
- The Google response must contain a provider-verified email that exactly matches the
  customer's verified local login email, case-insensitively. The stable Google subject
  identifier is trusted for subsequent login only after that explicit connection.
- An unconnected Google identity never creates a `CustomUser`, searches for or reveals
  a customer by email, auto-links, or authenticates. Direct allauth signup remains
  closed.
- Owner, staff, superuser, inactive, and passwordless accounts cannot connect or use
  Google under this phase.
- Password login and owned-domain password reset remain available. A recent local
  authentication is required before connection.
- OAuth access and refresh tokens are not retained. Only the allauth social-account
  binding and provider profile metadata required by allauth are stored.
- `CUSTOMER_GOOGLE_LOGIN_ENABLED` is a fail-closed operational switch. Disabling it
  removes the UI and rejects Google login while leaving local password access intact.
- Customer self-service disconnect is withheld in this phase so an identity binding
  cannot be silently deleted without retained correction evidence. A suspected
  compromise is handled by disabling the customer or the global feature and contacting
  the showroom; an audited unlink workflow requires a later decision.
- The OAuth callback is non-cacheable and omitted from Caddy access logs so its
  short-lived authorization code is not retained there.
- Connecting or using Google changes no `Customer`, `CustomerRegistration`,
  `SchemeAccount`, contribution, rate lock, allocation, eligibility, redemption, or
  liability record.

## Consequences

Approved customers can gain a convenient login method without weakening the staged
onboarding or financial-enrolment boundaries. Compromise of Google configuration can
be contained by disabling the feature, and compromise of a particular customer can be
contained by deactivating that user while the binding is investigated.

The first release intentionally provides no public social signup, automatic email
linking, owner/staff social login, provider-token retention, or online unlink. It also
depends on correct Google OAuth branding, an exact HTTPS callback URI, and separate
server-side protection and rotation of the client secret.
