# ADR-0012: Customer enrolment interest requests

## Status

Product amendment approved 5 October 2026: plan-first public entry and one coordinated
showroom review replace the customer-facing two-application journey in phases documented
in `docs/MVP_PLAN.md`. Phase 1 routes an approved customer to the existing plan-request
form and a visitor to staged registration with a validated offer summary. Phase 3,
now implemented and verified locally as amended below, retains public
plan/grade/preferences and offer evidence, protects progress tracking, requires renewed
customer confirmation after material changes, and coordinates approval through one
owner workflow. Separate identity/agreement records, owner authorization, idempotency,
historical request evidence and all financial boundaries remain required. The decision
below preserves the authenticated existing-customer request conversion contract.

Phase 2 implementation (5 October 2026) places plan requests alongside registrations
in the owner Applications inbox. Review, recorded offer/preferences, confirmation,
agreement creation and decline/expiry now share one workspace. The earlier conversion
URL renders that workspace, and its POST continues calling the same transactional,
idempotent conversion service. Changed/closed offers and expired requests do not show
a conversion action; authoritative service checks remain mandatory on submission.
Today includes expired pending requests until an explicit closure records the
decision. Separate requests/agreements, customer isolation and historical evidence
remain intact; Phase 3 now implements cross-verification plan continuity and coordinated
approval for newly linked public applications as amended below.

Accepted for implementation under `FW-ENROL-001`. Production enablement remains a
separate, disabled-by-default rollout decision.

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

Dashboard application progress precedes balances and remains customer-scoped and
bounded. Linked approvals lead to their separate agreement; existing-customer request
stages show review, changed terms, expiry or conversion and the appropriate next action.
Agreement continuation reads recorded payment states and existing availability. Pending
confirmation or metal allocation directs to protected status; Test/practice is explicit
and cannot establish a live first payment. A saved variable amount can prefill the first
payment form while existing agreement/service validation remains authoritative.
No financial history, offer or agreement snapshot is changed. Google copy explains
activated, verified, explicitly connected credential eligibility. Tamil testing is
prepared in English; unreviewed translations remain unpublished. Production rollout
remains a separate decision.

## Context

An approved customer login is deliberately separate from a savings agreement. Today
the customer must contact the showroom without leaving a structured record of which
public plan, exact metal grade, contribution amount, or duration they are interested
in. Allowing a customer-facing button to call the existing enrolment service directly
would bypass review, create financial access without an agreed start date, and blur a
non-binding website enquiry with the snapshotted agreement.

Plan terms can also change after an expression of interest. The system must retain
what the customer saw without treating that historical display as an authoritative
rate, allocation, liability, or final contract.

## Decision

- Add a feature-gated, authenticated `SchemeEnrolmentRequest`. Only an active user
  with the existing `Customer` profile may submit one.
- A request identifies one active, publicly listed `SchemePlan` and one active exact-
  grade `SchemePlanOffering`. It records the customer's preferred contribution amount,
  preferred duration, optional message, disclosure version, and acceptance time.
- Snapshot the plan name/code and material public offer fields at submission. These snapshots are
  evidence of the non-binding request only; the `SchemeAccount` snapshot created at
  actual enrolment remains the financial contract.
- A request creates no `SchemeAccount`, contribution, Razorpay order, Scheme Rate
  lock, metal allocation, eligibility date, liability, or payment permission.
- Permit at most one pending request for the same customer, plan, and metal grade.
  Repeated submissions return the existing request instead of creating duplicates.
- Requests expire after a bounded configurable lifetime, defaulting to 30 days. A
  customer may withdraw a pending request. An owner may decline or explicitly expire
  it with a reason. Terminal requests and their decision evidence are retained.
- Material plan-term changes, plan withdrawal, or offering withdrawal prevent direct
  conversion. The customer must review the current offer and submit a new request;
  an owner may not silently substitute changed terms.
- Only an active owner may convert a pending request. Conversion requires an explicit
  confirmation that the current terms were reviewed with the customer, revalidates
  the plan and offering, calls the existing `enroll_customer()` service atomically,
  links exactly one resulting `SchemeAccount`, and records immutable audit evidence.
- Conversion is idempotent. Repeating it returns the linked account and never creates
  another agreement.
- Customer acknowledgement, owner notification, decline/expiry, and completion
  messages are transactional notices. Email-provider acceptance is not evidence that
  the recipient read or agreed to the offer.
- Scheme plans and request-to-agreement conversion remain Django-owned. Wagtail may
  present editorial marketing later but cannot create or alter these financial
  records.

## Consequences

Customers gain a clear self-service way to record interest and track its status,
while the showroom retains responsibility for identity contact, current-term review,
start date, and final enrolment. The owner receives a structured queue instead of an
untracked contact message.

The workflow adds an auditable lifecycle and offer snapshots, but it is intentionally
not an online contract-signing system. Electronic signatures, uploaded identity
documents, automated KYC, SMS OTP, and unattended enrolment remain outside this ADR.

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
