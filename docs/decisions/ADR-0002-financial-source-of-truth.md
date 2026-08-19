# ADR-0002 — Financial Records Are the Source of Truth

## Context

Mutable running balances are difficult to audit and can drift from the transactions that created customer entitlements.

## Decision

Derive balances from successful contributions, metal allocations, redemptions, and append-oriented reversals/corrections. Do not make mutable customer balance fields authoritative.

## Consequences

Historical allocations remain stable, aggregates can be reconciled to individual records, and corrections remain visible. Read-time aggregation may later be optimized with rebuildable projections without changing the source of truth.
