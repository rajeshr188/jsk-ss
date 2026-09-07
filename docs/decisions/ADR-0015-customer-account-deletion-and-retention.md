# ADR-0015: Verified account deletion with bounded financial retention

## Status

Accepted for staged implementation on 7 September 2026. The owner accepted the
24-hour verification, seven-day owner-review, and 30-day removable-data service
targets; owner-only review authority; entitlement-preserving containment; and plain-
language `COMPLETED_WITH_RETENTION` communication. The additive request,
verification, containment, owner-queue, and integrity foundation may be implemented
behind a disabled flag. Irreversible anonymization, completion decisions, production
enablement, and a public-store deletion claim remain blocked until the qualified
legal/accounting retention matrix is recorded.

## Context

The staged public registration flow lets a person create an approved customer login.
Google Play therefore requires both a discoverable in-app path and an external web
resource through which a person can request deletion of the account and associated
data. A general contact address is not a complete deletion workflow.

The current model deliberately prevents cascade deletion. `Customer.user`, approved
registrations, invitations, scheme accounts, enrolment requests, contributions,
allocations, receipts, redemptions, reversals, reminder evidence, and audit events use
`PROTECT` relationships where historical integrity matters. A blanket
`CustomUser.delete()` would either fail or, if those protections were weakened,
destroy the evidence used to prove customer entitlements and owner liabilities.

Keeping every personal field forever is also not acceptable. The Digital Personal
Data Protection Act, 2023 describes a right to erasure unless retention is necessary
for the specified purpose or compliance with law. The final DPDP Rules use phased
commencement dates, so the business must obtain current professional advice rather
than assume that every provision has the same effective date. Separately, tax and GST
record-retention duties may apply for multi-year periods and may extend during an
appeal, investigation, or other proceeding. The exact duties depend on the legal and
tax status of Jai Sri Krishna Jewellery and cannot be inferred by the application.

Deletion must therefore remove the customer's login and unnecessary personal data
without erasing an outstanding metal entitlement, payment evidence, receipt,
redemption, correction, consent decision, or audit trail that still has an approved
purpose or legal retention basis.

## Proposed decision

### 1. Explicit workflow, not direct deletion

- Implement a dedicated `FW-PRIV-001` workflow. Do not expose Django admin deletion,
  allauth deletion, model cascade, SQL scripts, signals, or background cleanup as an
  account-deletion mechanism.
- Provide an authenticated account-settings path and a stable public path at
  `/accounts/deletion/`. Both describe what deletion does, what may be retained, the
  expected timeline, and how to contact the showroom.
- The public form accepts an email address and always returns the same response. It
  never reveals whether a user, pending registration, customer, scheme, Google link,
  or deletion request exists.
- A public request becomes actionable only after a one-time email verification token
  is confirmed. Reuse the established secret boundary: random secret, stored digest,
  bounded expiry, one-time use, direct untracked email, no raw token in logs, no cache,
  no cross-origin referrer, database-backed throttling, and a CSRF-protected mutation.
- An authenticated request requires recent authentication. A connected Google
  credential alone must not silently authorize irreversible deletion; the password
  fallback or a separately reviewed independent verification route remains required.

### 2. Lifecycle and default timings

Use explicit states rather than a boolean:

1. `PENDING_VERIFICATION` — public request submitted; no account change.
2. `VERIFIED` — requester control verified; owner queue entry created.
3. `CONTAINED` — login and new customer-initiated actions blocked while review runs.
4. `AWAITING_SETTLEMENT` — provider state, open entitlement, dispute, refund,
   redemption, or another obligation prevents final minimization.
5. `APPROVED` — the owner approved the documented delete/anonymize/retain plan.
6. `COMPLETED` — user-facing account removed and applicable identity data erased or
   irreversibly anonymized; no personal retention remains beyond the approved audit
   tombstone.
7. `COMPLETED_WITH_RETENTION` — user-facing account removed, while specifically
   identified records remain under a documented purpose/legal hold and review date.
8. `REJECTED`, `WITHDRAWN`, or `EXPIRED` — terminal outcomes with an actor and reason.

Recommended service targets are a 24-hour verification link, immediate acknowledgement,
owner review within seven calendar days of verification, and completion of removable
data within 30 calendar days. An open financial/provider/legal hold may exceed 30 days,
but the customer must receive the reason, retained categories, next review date, and
support/grievance path. These are proposed service targets, not statements of statutory
deadlines.

### 3. Containment does not stop financial truth

After verification and before destructive minimization, one explicit service should:

- set the customer login inactive and revoke web sessions;
- remove the ability to begin/resume Checkout, submit enrolment requests, or perform
  other customer-initiated mutations;
- record the privacy restriction and reason so ordinary account reactivation cannot
  bypass the request;
- revoke/remove the linked Google credential through an audited path while retaining
  only a keyed, non-reversible provider-subject digest if the approved fraud/identity
  policy requires it;
- leave Razorpay callbacks, signed webhooks, allocation recovery, reconciliation,
  refunds/disputes, owner controls, reminder review, and audit reads operational.

Razorpay exposes no provider-order cancellation. Any pending order must be inspected
and reconciled through the existing mode-matched workflow. A late captured payment
must still be confirmed and allocated from its original lock; account deletion is not
a payment bypass or a reason to discard an entitlement.

Containment is reversible only before anonymization and only through an owner action
that independently re-verifies the customer and records a reason. Completed
anonymization is not reversible from backups or hidden copies.

### 4. Data disposition tiers

The owner preview must classify the request before approval:

- **Unapproved applicant:** remove/anonymize the registration's name, email, mobile,
  and address when no other approved purpose remains. Preserve only bounded throttle
  digests, policy-version/decision evidence, and a non-identifying privacy audit entry
  for their approved retention periods.
- **Approved customer with no scheme, transaction, or open request:** deactivate the
  credential; remove EmailAddress/social records, invitations, sessions, and
  unnecessary contact/profile data; replace required unique database values with
  generated non-personal tombstone values; retain only the minimum request/audit
  evidence needed to prevent accidental resurrection or abuse.
- **Customer with scheme or financial history:** remove login capability and
  unnecessary duplicates immediately, but retain the exact scheme, rate lock,
  contribution, provider, allocation, receipt, redemption, reversal, consent, and
  audit records required by the approved contractual, accounting, tax, dispute, or
  fraud purpose. Retain identifying fields only where that purpose actually requires
  them. Set a retention review date; once every hold ends, execute the same irreversible
  anonymization service without rewriting financial facts.
- **Customer with an outstanding entitlement or active dispute:** keep the minimum
  verified contact route needed to provide statements, support showroom settlement,
  or resolve the dispute. Deletion never forfeits the customer's metal entitlement.

The customer number and financial foreign-key graph may remain as non-public internal
keys. A tombstoned user must have an unusable password, no verified login email, no
social credential, no active session, no staff/owner flags, and no reusable original
email/mobile value. A later registration using the same identity must go through owner
review and must never be automatically merged with or granted the historical account.

### 5. Explicit records and services

Implementation should add narrowly scoped models, not a generic event system:

- `CustomerAccountDeletionRequest` for the public/authenticated request, digest,
  verification, current state, customer link when resolved, and timestamps;
- immutable `CustomerAccountDeletionDecision` for the owner-approved disposition,
  category-specific retention reasons, review/deadline dates, actor label, and policy
  version;
- append-only `CustomerAccountDeletionAction` rows for request, verification,
  containment, provider actions, anonymization, completion, rejection, withdrawal,
  and later retention review.

Do not store the raw verification token or copy removed personal data into audit
details. Database constraints should allow at most one open verified request per
customer and require actor/reason/timestamp shapes for every terminal decision.

All state transitions, containment, and anonymization run through explicit atomic
services using row locks and idempotency. The owner sees a dry-run preview containing
record counts, open scheme liabilities, pending provider state, disputes/holds,
proposed field dispositions, provider follow-ups, and the exact irreversible action.
The irreversible step requires recent owner authentication and explicit confirmation.

### 6. Provider, log, and backup boundary

The disposition plan must cover:

- Postmark message metadata/suppressions and any support mailbox copies;
- Google SocialAccount profile metadata and the absence of stored OAuth tokens;
- Razorpay customer/payment data retained for payment, dispute, refund, fraud, or
  legal purposes under the reviewed provider relationship;
- Cloudflare and Caddy request/security logs according to their configured retention;
- Linode/PostgreSQL backups, where deleted data remains inaccessible to the live app
  and ages out through the documented backup lifecycle rather than being edited in
  place;
- exported CSVs, downloaded receipts/statements, and manual showroom records, which
  require an owner-controlled retention and disposal procedure outside Django;
- R2 only if a future feature stores customer-specific media; the current public
  catalogue/media store is not assumed to contain customer account data.

Service-provider deletion is requested where appropriate, but immutable provider or
statutory transaction records are documented as retained rather than falsely claimed
deleted.

### 7. Customer communication and evidence

- Send direct, untracked acknowledgement after verification, containment notice,
  outcome notice, and any later retention-review result. Email-provider acceptance is
  delivery evidence, not proof of receipt.
- `COMPLETED_WITH_RETENTION` must list retained categories and purposes in plain
  language without exposing internal security details.
- Update Privacy, Terms, account settings, and the public deletion page together. The
  Play Data Safety deletion URL must point directly to the functional public resource.
- Add an owner queue and a privacy integrity command that reports open/overdue
  requests, completed active logins, missing decisions/actions, expired tokens,
  disposition mismatches, provider follow-ups, and retention reviews due. It must not
  print personal identifiers or secrets.
- A release requires tests for enumeration resistance, token/CSRF/cache/log safety,
  recent authentication, owner authorization, concurrent execution, idempotency,
  session/social revocation, no financial cascade, pending/late Razorpay capture,
  entitlement preservation, no-history anonymization, retained-history outcomes,
  provider failures, backup disclosure, and database constraints.

### 8. Deployment boundary

- Ship behind `CUSTOMER_ACCOUNT_DELETION_ENABLED=False`.
- Apply the additive migration and run integrity checks before exposing either entry
  point.
- Test with synthetic no-history and retained-financial-history customers first. Do
  not use a real customer as the initial destructive test.
- Enabling the feature requires the owner-approved retention schedule, public policy
  update, Postmark delivery check, provider procedure, recovery point, and rollback
  plan. Database rollback never means restoring an already completed customer's
  login or personal data without a new lawful decision.

## Consequences

The design satisfies the product need for a real deletion-request path while
preserving financial correctness and traceability. It creates more work than a single
delete button because the application must classify obligations, minimize duplicate
identity data, coordinate providers, and revisit retained records. That complexity is
deliberate: the unsafe alternatives are destroying liabilities or retaining all
personal data indefinitely.

Public Play release remains blocked until the retention schedule and implementation
are approved and production-accepted. `FW-MOBILE-002` PWA work may proceed after its
own gate, but neither the TWA public release nor its Data Safety form may claim account
deletion before this workflow is live and tested.

## Recorded owner decisions and remaining professional gate

The owner confirmed on 7 September 2026 that:

1. The 24-hour verification, seven-day owner-review, and 30-day removable-data
   targets are accepted as service targets rather than statutory claims.
2. Only active owners may record review decisions or execute later completion actions
   in the first release.
3. Deletion must not forfeit an entitlement; a customer whose account is completed
   with retention must receive a plain-language explanation of the retained categories,
   purpose, next review date, and support route.

The remaining gate is to obtain a qualified written retention matrix for registration/consent, scheme
   agreements, contributions/provider evidence, receipts/statements, redemptions,
   disputes/refunds, audit/security logs, communications, exports/manual records, and
   backups—including the rule that starts each retention period and any legal hold.
Until that matrix is recorded, the application must expose no anonymization,
`APPROVED`, `COMPLETED`, or `COMPLETED_WITH_RETENTION` mutation. The foundation may
only accept and verify requests, contain access, preserve financial processing, and
let an owner append a reasoned hold with a next review date.

## References

- [Google Play account deletion requirements](https://support.google.com/googleplay/android-developer/answer/13327111)
- [Digital Personal Data Protection Act, 2023](https://www.meity.gov.in/static/uploads/2024/02/Digital-Personal-Data-Protection-Act-2023.pdf)
- [Digital Personal Data Protection Rules, 2025](https://www.meity.gov.in/documents/act-and-policies/digital-personal-data-protection-rules-2025-gDOxUjMtQWa)
- [CGST Act section 36, official CBIC text](https://cbic-gst.gov.in/pdf/CGST-Act-Updated-01082021.pdf)
- [Income-tax Rules, 2026 notification](https://www.incometax.gov.in/iec/foportal/sites/default/files/2026-03/En-Notified-IT-Rules-2026-20-03-2026.pdf)
- [ADR-0014 mobile distribution boundary](ADR-0014-pwa-twa-first-mobile-distribution.md)
