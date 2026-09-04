# ADR-0012: Customer enrolment interest requests

## Status

Accepted for implementation under `FW-ENROL-001`. Production enablement remains a
separate, disabled-by-default rollout decision.

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
