# ADR-0015: Verified account deletion with bounded financial retention

## Status

Accepted for staged implementation on 7 September 2026. The owner accepted the
24-hour verification, seven-day owner-review, and 30-day removable-data service
targets; owner-only review authority; entitlement-preserving containment; and plain-
language `COMPLETED_WITH_RETENTION` communication. The additive request,
verification, containment, owner-queue, and integrity foundation may be implemented
behind a disabled flag. Revised with owner acceptance on 10 September 2026:
qualified written legal/accounting sign-off is no longer a prerequisite to developing
the owner-operated completion workflow. Per-category owner disposition decisions,
necessary retention evidence, tested completion, accurate public disclosures and
production acceptance remain required. This is a project sequencing decision, not
legal certification or a waiver of statutory duties or Google Play requirements.

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

## Decision

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
and reconciled through the existing mode-matched workflow. A captured payment must
still follow the existing confirmation/allocation or reviewed recovery/refund rules
using its original lock. Abandoned orders are not automatically confirmed; account
deletion is not a payment bypass or a reason to discard evidence or an entitlement.

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

## Recorded owner decisions and revised execution boundary

The owner confirmed on 7 September 2026 that:

1. The 24-hour verification, seven-day owner-review, and 30-day removable-data
   targets are accepted as service targets rather than statutory claims.
2. Only active owners may record review decisions or execute later completion actions
   in the first release.
3. Deletion must not forfeit an entitlement; a customer whose account is completed
   with retention must receive a plain-language explanation of the retained categories,
   purpose, next review date, and support route.

On 10 September the owner reported a sole proprietorship registered under regular
GST, no PAN/Aadhaar or other identity-document collection, no outstanding tax
disputes/notices/investigations, and an existing accountant who is currently
unavailable. These are owner-reported facts, not independently verified findings.

The owner accepted a smaller owner-operated release: verified requests, a disposition
preview, removal of eligible account data, explicit justified retention, customer
notices and scheduled review. Development does not wait for accountant sign-off.
Professional review remains recommended for uncertain tax/contract questions; the
application must not invent legal applicability or automatically purge financial
records after a generic number of years. Automated destruction of old financial
evidence is deferred to separately reviewed future work.

Execution remains incremental. The local `FW-PRIV-001B` now supplies the preview,
explicit field minimization, owner dispositions, completion notices and retention
reviews described below. Production remains on the disabled foundation until a
separate reviewed rollout. A clean preview is
not approval: external disputes, exports, provider copies and backup expiry require
owner evidence. Outstanding entitlement or provider uncertainty must not be treated
as customer forfeiture or as justification for retaining unrelated personal data.

## Implemented completion boundary (local, not production-accepted)

- Migration `accounts.0006_customer_deletion_completion` adds `privacy_erased_at`,
  immutable disposition snapshots, uniqueness for one completion decision per
  request, and a durable per-decision notice queue. It does not erase existing data.
- Recently authenticated owners explicitly confirm the request UUID and seven
  categories: financial history, profile, privacy/consent, providers/mail, logs,
  exports/paper, and backups. Each needs treatment, purpose, minimum fields, a
  start event, duration/hold-release condition and next review date. The 365-day
  maximum between reviews is an application guard, not a statutory retention period.
- Completion serializes customer/user/request and agreement/contribution rows,
  rechecks current state, and refuses pending payments, unallocated payments,
  unresolved matched webhooks, pending enrolment decisions and ambiguous other
  email-matched registrations. Resolve them through the existing workflows first.
- All completions currently use `COMPLETED_WITH_RETENTION`, including no-financial-
  history customers: minimum privacy/consent evidence, temporary notice contact and
  backup/provider records still require transparent handling. `COMPLETED` and
  standalone `APPROVED` are not supported mutations. Internal keys are pseudonymous,
  not a claim that the retained graph is irreversibly anonymous.
- Remove login email/username identity, password, names and last-login data; clear
  sessions, social records/tokens, allauth email bindings, invitations and permission
  memberships. Keep an inactive, unusable-password tombstone `CustomUser` with
  protected foreign keys. A database constraint enforces the erased-login shape;
  ordinary model/admin edits cannot reactivate it. Deliberate SQL is not a supported
  restoration or correction path.
- Remove unselected `Customer` name/email/mobile/address fields. Keep only the
  explicitly selected fields; open agreements or nonzero entitlements require name
  and email for settlement. Retained email may prevent duplicate customer creation;
  that conflict needs owner review, never automatic merging or access to history.
- Minimize the linked approved registration's contact fields, source-IP digest,
  free-text review reason and delivery error while preserving approval/consent
  timestamps, policy versions and reviewer evidence. Do not guess ownership of
  other email-matched applications. Privacy-request emails/digests and customer
  actor labels are minimized through this explicit audited service. Historical
  decision free text may still identify a person and belongs in the reviewed
  privacy-evidence category; do not paste unnecessary personal data into new decisions.
- Financial source records, including financial audit text and reminder history,
  are not rewritten. No new enrolment or contribution may start for the removed
  account, while already-paid replays, reconciliation, settlement and existing
  provider recovery semantics remain intact. Abandoned-order late captures still
  require the existing reviewed recovery/refund path, not automatic confirmation.
- The notice row is committed with the minimization decision. SMTP runs separately
  and can be retried without repeating erasure. Successful SMTP acceptance clears
  the delivery address from that queue; failure retains it temporarily and is
  surfaced in the owner request and integrity check. SMTP acceptance is not proof
  of receipt; a crash after provider acceptance may cause a duplicate retry.
- Completed requests remain in the owner review queue. Reviews append new category
  decisions, update the next review date, and may remove previously retained profile
  fields only if obligations permit. They cannot restore erased identity or purge
  financial records. A review notice uses only an already-retained contact email;
  if none remains, do not recover it from backups or claim a notice was sent.
- The owner must inspect the queue/integrity command daily. Due dates are recorded,
  not an automatic disposal schedule. Provider/export disposal and restore
  suppression remain manual procedures needing evidence before enablement.

## FW-PRIV-001B review worksheet and execution plan

Prepared 10 September 2026. This worksheet collects the outstanding decision; it
does not approve a retention period or establish a legal duty. Under the revised
boundary, the owner records each applicable category before executing a completion;
uncertain legal/accounting questions are referred for professional advice. The
existing service targets remain accepted.

For every row, record the purpose/legal basis, minimum identifying fields, retention
duration, event that starts the duration, legal-hold exceptions, review/disposal
action, and responsible owner. Mark a category not applicable only with a reason.
Record the schedule version, review date, decision-maker role and owner acceptance; keep
professional correspondence and sensitive business documents outside the repository.

| Category | Current data to consider | Decision required |
| --- | --- | --- |
| Applicants and consent | Registration name, email, phone, address, verification and approval evidence, policy versions | Separate unapproved/expired applicants from approved customers; identify removable duplicates and the consent evidence still needed |
| Login and profile | CustomUser, Customer, allauth email/Google binding, invitations, sessions | Define removal/tombstone fields, necessary contact for unresolved obligations, and re-registration treatment |
| Scheme agreements | Plan/grade contract, enrolment request, acceptance and account history | Identify contract evidence and customer identity needed during and after settlement; define the starting event |
| Contributions and payment evidence | Razorpay orders, payment identifiers, webhook payloads, cash receipts | Separate immutable amounts/status/rate locks from personal payload fields; define transaction-evidence retention |
| Allocations, receipts and statements | Exact-grade quantities, printed/downloaded documents and identity copies | Preserve entitlements and financial facts; identify which customer-identifying fields require retention |
| Redemptions, corrections and disputes | Settlement, reversal, refund/dispute records and supporting correspondence | Define unresolved-obligation holds, settlement evidence and release/review conditions |
| Audit and security | Audit actor labels/details, registration/deletion attempts, Caddy/Cloudflare/application logs | Minimize personal identifiers; define distinct operational/security retention and disposal periods |
| Communications and provider copies | Postmark metadata, reminder/invitation emails, support mailbox, Google/Razorpay provider data | Identify processor follow-ups, retained provider records, response evidence and message-copy disposal |
| Exports and showroom records | CSVs, downloaded statements, printed receipts, manual customer records | Assign a person to find, retain or dispose of copies under the same approved schedule |
| Backups and restoration | Linode managed backups and any local/manual database exports | Document actual expiry/access restrictions and how a restore reapplies completed deletion decisions before reopening access |
| Privacy request evidence | Verification digests, decisions, actions, retained categories and notification result | Define minimal completion evidence and its own retention so the audit does not retain erased personal data |

### Release disposition baseline — prepared 10 September 2026

The owner authorized release preparation after the retention review. The following
is the implementation-aligned baseline, not evidence that external settings were
verified, every category's legal applicability was settled, or production execution
was approved. Do not copy synthetic test purposes into a real decision.

| Category | Fields and treatment | Start / release condition | Review and remaining evidence |
| --- | --- | --- | --- |
| Login | Remove original username/email, password, names, last login, sessions, Google/allauth bindings, invitations and memberships; keep unusable protected user key | Verified completion after current safety checks | Implemented; verify through the installed app at rollout |
| Showroom profile | Remove unneeded name/email/mobile/address; open agreements or balances require name and email for settlement | Reassess when agreement and entitlement obligations end; retain further fields only with a specific purpose | Owner records the next review; identity needed in historical documents requires separate consideration |
| Financial | Preserve scheme terms, contributions, exact-grade allocations, receipts, settlements and corrections; retain only necessary identifying evidence | GST-covered records: section 36's 72 months from the relevant annual-return due date, extended for applicable proceedings; other obligations/holds require their own basis | Review applicability and due date per record year; no automatic financial purge; generic audit text/reminder metadata is not automatically statutory evidence |
| Privacy and consent | Retain minimal request/customer keys, decisions, dates, consent/policy versions and outcome evidence; no copied erased contact or secrets | While needed to evidence handling and prevent restoration, with a documented release condition | Owner must specify the purpose and review; current service does not purge historical decision rows or free text |
| Notice delivery | Temporary recipient email only in durable outcome queue | Clear after SMTP acceptance; failed or over-24-hour pending notice needs attention | Existing integrity check; provider copy remains a separate question |
| Providers and mail | Identify necessary Razorpay evidence separately from disposable Postmark/support message copies; remove unnecessary copies or request provider disposal | Actual provider settings and applicable transaction/dispute obligations | Unverified: record settings, requests, responses and exceptions, without placing private evidence in Git |
| Logs and attempts | Avoid tokens/contact in logs; use short-lived throttle digests | Configured window and actual cleanup execution, not merely token expiry | Unverified external log periods; attempt cleanup is request-triggered, not a guaranteed timed purge |
| Exports and paper | Apply source-record disposition to CSVs, statements, receipts and showroom copies | Same underlying purpose/start event as source; remove unnecessary duplicates | Owner inventory and disposal evidence required |
| Backups | Restricted copies age out under the actual backup lifecycle; no restoration of erased identity | Actual backup expiry plus reviewed restore suppression | Verify provider window and independent minimal recovery record; isolated synthetic restore drill required |
| Unapproved/expired applicants | Separate manual-reviewed request path; do not guess ownership or bypass model protections | Purpose ends or verified applicant request, subject to specific holds | Dedicated minimization workflow remains incomplete; support intake is not evidence of completed erasure |

Source for the narrow GST baseline: [CBIC section 36](https://taxinformation.cbic.gov.in/content-page/explore-act/1000306/1000001).
It is not a universal retention rule for all personal data or all tax obligations.
Google requires associated-data deletion and disclosure of justified exceptions;
service-provider follow-up is part of the boundary, not fulfilled by a Django-only
change: [Play deletion requirements](https://support.google.com/googleplay/android-developer/answer/13327111).

Public wording is prepared in the Privacy page and a shared explanation on the two
deletion entry pages. It identifies the Android app, removal/retention distinction,
review-versus-disposal distinction, entitlement protection and external-copy limits.
Detailed deletion wording remains feature-gated. Do not advance the production
policy version until the actual release wording and procedures are approved; at that
release align `PUBLIC_REGISTRATION_PRIVACY_VERSION` and
`CUSTOMER_ACCOUNT_DELETION_POLICY_VERSION` with the approved policy. Do not change
the Terms version unless Terms themselves change. Existing consent snapshots remain
historical evidence and must not be rewritten.

### Execution checkpoints

- [x] Inspect the existing foundation: selectors expose request history and counts;
  services support verified containment and owner holds; completion and anonymization
  are intentionally unavailable.
- [x] Prepare the category worksheet and record the Play-installed pilot core results.
- [x] Record owner acceptance of the owner-operated release and replace the
  blanket qualified-sign-off development prerequisite (10 September 2026).
- [ ] Record the owner-approved field/category schedule, start events, holds and
  provider/export/backup procedures before irreversible production execution.
- [ ] Map the approved schedule to exact model fields and provider/export/backup
  procedures. Identify outstanding entitlements and pending provider events using
  existing financial selectors; counts alone cannot authorize completion.
- [x] Implement a read-only owner disposition preview: related-record inventory,
  per-agreement INR principal/earned bonus and exact-grade six-decimal balances,
  pending/paid-unallocated contributions, unresolved matched webhooks, open
  agreements/enrolment requests and explicit external unknowns. Keep behind the
  existing flag, owner-only and non-cacheable. No mutation or provider call on GET.
- [x] Implement versioned disposition decisions and supported terminal lifecycle
  constraints. Show retained categories, purpose and next review before confirmation.
- [x] Implement recently authenticated, atomic, idempotent owner completion services
  for approved no-history and retained-history cases; preserve financial foreign
  keys and quantities, and prevent account reactivation from restoring removed data.
- [x] Add recorded external follow-ups/outcome notices and retention-review handling; ensure
  email or provider failures remain visible and retryable without repeating erasure.
- [x] Test synthetic no-history/history cases, holds, captured-payment processing,
  concurrent/double completion, owner authorization, and identity/cache/log safety.
  Full regression: 421 tests passed; final accounts rerun: 95 passed. These are local
  automated tests, not external provider, restore or production acceptance evidence.
- [ ] Update policies, account entry point and public deletion page to match the
  approved behavior. Validate the in-app and external request journeys.
- [ ] Deploy disabled, verify migrations/integrity and recovery procedures, then
  perform synthetic acceptance before approved production enablement.
- [ ] Record production evidence and update Play Data Safety/deletion declarations.

The next gate is owner review of the implemented disposition and real category-
specific procedures, plus policy wording, synthetic acceptance and the disabled-first
rollout. It is not additional customer payments or waiting for accountant availability.
The owner-confirmed Android pilot does not supply retention decisions or authorize
erasing any pilot customer's records. Do not enable the production deletion flag or
claim the public-store deletion gate complete on the strength of the preview alone.

## References

- [Google Play account deletion requirements](https://support.google.com/googleplay/android-developer/answer/13327111)
- [Digital Personal Data Protection Act, 2023](https://www.meity.gov.in/static/uploads/2024/02/Digital-Personal-Data-Protection-Act-2023.pdf)
- [Digital Personal Data Protection Rules, 2025](https://www.meity.gov.in/documents/act-and-policies/digital-personal-data-protection-rules-2025-gDOxUjMtQWa)
- [CGST Act section 36, official CBIC text](https://cbic-gst.gov.in/pdf/CGST-Act-Updated-01082021.pdf)
- [Income-tax Rules, 2026 notification](https://www.incometax.gov.in/iec/foportal/sites/default/files/2026-03/En-Notified-IT-Rules-2026-20-03-2026.pdf)
- [ADR-0014 mobile distribution boundary](ADR-0014-pwa-twa-first-mobile-distribution.md)
