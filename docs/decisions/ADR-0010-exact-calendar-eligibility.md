# ADR-0010: Exact-calendar redemption eligibility

## Status

Accepted and implemented under `FW-ELIG-001`.

## Context

Every scheme agreement snapshots a start date, agreed duration in months, and an
`eligible_from` date. The application already treated that date as an entitlement
boundary, but the treatment of month ends, weekends, public holidays, showroom
closure, payment schedules, temporary payment pauses, grace periods, and long-open
eligible accounts was not stated as one authoritative policy. Leaving those cases
implicit could make enrolment, contribution, bonus, forecast, and redemption paths
reach different answers.

## Decision

- Contractual eligibility is the scheme start date plus the agreed number of exact
  calendar months. If the same day does not exist in the destination month, the date
  is clamped to that month's final day.
- Eligibility begins on that date in the configured India-local calendar. The day
  before remains ineligible; there is no early-redemption grace period.
- Weekends, public holidays, showroom closures, store hours, contribution schedules,
  and manual or automatic payment pauses do not move the contractual eligibility
  date. They can affect when staff are available to fulfil a redemption, not when the
  customer's entitlement becomes eligible.
- Eligibility does not expire. An eligible account remains open and eligible until
  the recorded entitlement is fully redeemed. Reaching eligibility does not mutate
  stored account status or create a redemption.
- The agreement's existing snapshotted setting continues to decide whether later
  contributions are permitted. Eligibility calendar policy does not rewrite that
  economic term.
- Owner forecast bands count ordinary calendar days from the India-local `as_of`
  date; they are not business-day forecasts.
- One pure policy module supplies eligibility-date calculation, boundary checks, and
  forecast distance to enrolment, contribution, bonus, status, forecast, and
  redemption code paths.

## Consequences

The contractual date is deterministic, auditable, and independent of a holiday
calendar or operational-control state. Customers may become eligible on a day when
the showroom is closed and complete fulfilment on the next opening day without losing
or changing that eligibility. Introducing business-day adjustment, early grace, or
post-eligibility expiry later would change customer rights and requires a new explicit
business decision, migration/backfill analysis, disclosure review, and regression
coverage.

This implementation adds no model field or database migration because existing
agreements already store the calculated `eligible_from` date.
