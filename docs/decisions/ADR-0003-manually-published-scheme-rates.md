# ADR-0003 — Use Manually Published Scheme Rates for Metal Allocations

## Context

The original gold/silver workflow fetched an external XAU/XAG-to-INR quote only
after payment verification, created a one-off `RateSnapshot`, and could leave a
verified payment unallocated when the provider, network, credentials, or response
failed. External market data can also differ from the rate Jai Sri Krishna Jewellery
intends to offer under its customer scheme.

That architecture added a critical external dependency, provider configuration and
secrets, quota/cache behavior, retry paths, and a payment/allocation mismatch risk.
The application now has a live deployment and applied migrations, so the schema
must change through a forward migration that preserves existing financial history;
applied migrations and the production database must not be reset.

## Decision

Gold and silver allocations use only append-only `SchemeRate` records manually
published by an active owner. Under
[ADR-0007](ADR-0007-grade-specific-metal-rates.md), a publication belongs to one
exact metal grade and stores its base metal, fineness, positive INR rate per gram,
effective timestamp, publisher, publication timestamp, and optional notes, and
creates an immutable audit event. Current means the latest applicable publication
for that grade; there is no mutable active flag or cross-grade fallback.

The current `SchemeRate` is locked to a pending metal contribution before mock
payment initiation or Razorpay order creation. Payment confirmation and webhook
processing allocate only from that lock. Without an applicable rate, the system
creates no payable metal contribution or order. A verified metal payment is first
durably recorded as `PAID_UNALLOCATED` and becomes `PAID` only after allocation;
exceptions or process interruption therefore remain visible, and retry reuses the
original lock.

Migration `schemes.0010_manual_scheme_rates` converts existing `RateSnapshot` rows
to historical `SchemeRate` rows, links existing allocations and contributions, and
removes provider-only fields. A null publisher is permitted only for those migrated
historical rows; every new publication requires an owner.

## Consequences

The authoritative workflow is simpler and deterministic, customer rate language is
clearer, historical allocations remain self-evident, and provider outages can no
longer occur between verified payment and rate selection. Publishing a newer rate
cannot change an existing checkout or historical grams. Manual-entry risk is
mitigated with positive `Decimal` validation, fixed fineness, an owner-only audited
service, a current/new/difference display, and additional confirmation above 5%.

Owners must publish and review each offered grade operationally. Metal checkout
is unavailable if a rate has not been published. A pending contribution currently
retains its lock without expiry; coordinated Scheme Rate/Razorpay order expiry is
deferred because it would add lifecycle complexity.

External APIs may later supply owner-facing reference information, but they must not
become authoritative for customer allocations unless a later ADR explicitly changes
this decision.
