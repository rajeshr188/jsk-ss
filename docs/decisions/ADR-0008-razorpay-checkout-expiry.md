# ADR-0008: Snapshotted Razorpay Checkout expiry

## Status

Accepted for implementation under `FW-PAY-005`.

## Context

A Razorpay contribution locks its exact Scheme Rate before the provider order is
created. Previously the application kept offering that order through Checkout until
the contribution was paid, failed, or provider-reconciled as abandoned. A manual or
scheduled payment pause stopped a new page render, but an already rendered Checkout
could remain available longer than the business intended during market volatility.

Razorpay Standard Checkout accepts an integer `timeout` in seconds, but its
documentation warns that browsers may pause JavaScript timers. Razorpay Orders expose
`created`, `attempted`, and `paid` states and no cancellation operation. A local
deadline therefore cannot prove that the provider order is incapable of receiving a
payment.

## Decision

- Every new Razorpay contribution snapshots `checkout_expires_at` when its local
  pending record is created. The duration comes from
  `RAZORPAY_CHECKOUT_EXPIRY_MINUTES`, defaults to 10 minutes, and is constrained at
  process startup to the accepted 3–15 minute range. Changing the environment affects
  new contributions only; it never rewrites an existing rate lock or deadline.
- The customer Checkout view fails closed when the deadline is absent or reached.
  Scheme history stops showing its Resume action and identifies the still-pending
  order as awaiting provider reconciliation. Owner contribution history exposes the
  deadline.
- A rendered page passes the remaining whole seconds to Razorpay Standard Checkout
  and also disables its local button at the absolute deadline. These browser controls
  reduce exposure but are not treated as financial proof.
- Expiry alone does not change `PENDING` to `FAILED` or `ABANDONED`, does not release
  the once-per-month uniqueness guard, and does not create or remove entitlement.
  The existing dry-run-first abandoned-order workflow must inspect the provider. Only
  an exact `created`, zero-attempt, zero-payment, zero-paid-amount order can be marked
  application-side `ABANDONED`; attempted, captured, or uncertain orders remain for
  review.
- A correctly signed and server-verified capture received after Checkout expiry but
  before provider-verified abandonment is confirmed idempotently using the original
  locked Scheme Rate. Payment pauses and expiry never justify ignoring received
  funds. A capture after `ABANDONED` remains a financial exception for manual provider
  reconciliation/refund under ADR-0006.
- Migration `schemes.0017` adds the deadline, indexes pending-expiry review, and
  requires every pending Razorpay contribution to have a deadline. Any historical
  pending Razorpay row is backfilled as `created_at + 10 minutes`; finalized history
  is not rewritten.

## Consequences

The customer can no longer reopen an old locked-rate Checkout indefinitely, while
captured funds remain protected from accidental rejection. A customer may need to
wait for provider reconciliation before a replacement monthly attempt is available.
An old browser tab and the provider order cannot be made cryptographically invalid by
this application; operations must retain reconciliation monitoring and the late-
capture incident path.

Because the new database constraint rejects pending Razorpay rows without a deadline,
the old web image is not write-compatible after `0017`. Production deployment must
pause new payments, record and reconcile pending orders, stop the old web process,
migrate once, and then start the candidate. Rollback should be a compatible roll-
forward unless a database restore is proven safe against every post-recovery-point
financial event.

## References

- Razorpay Standard Checkout integration options:
  <https://razorpay.com/docs/payments/payment-gateway/web-integration/standard/integration-steps/>
- Razorpay Orders entity and states:
  <https://razorpay.com/docs/api/orders/entity/>
