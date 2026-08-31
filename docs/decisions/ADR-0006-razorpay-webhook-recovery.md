# ADR-0006 — Classify and Recover Razorpay Webhooks from Provider State

## Context

Razorpay can redeliver a webhook when the endpoint does not return a successful HTTP
response. Repeating a delivery is useful for temporary database or application
failures, but it cannot repair a durable business mismatch such as an unknown order,
an amount mismatch, or a late capture against an application-side abandoned order.
Returning an error forever for those permanent cases creates noise and can exhaust
the provider retry window without resolving the financial exception.

The existing event ledger verifies the signature over the untouched request body,
stores the provider event ID and a payload hash, and makes financial confirmation
idempotent. It did not retain processing-attempt history or provide an authorized,
provider-backed recovery path. Full webhook bodies are deliberately not retained.

## Decision

Classify every authenticated webhook delivery into one of three HTTP behaviors:

1. Invalid signatures, malformed requests, and an event-ID reuse with different
   content return `400`. They are not trusted financial events.
2. A signed event that is durably processed, ignored, or placed into
   `REVIEW_REQUIRED` returns `200`. Permanent mismatches retain a bounded failure code,
   safe detail, provider identifiers when available, and an immutable processing
   attempt. They never create entitlement merely because the delivery was accepted.
3. A signed event interrupted by a transient application failure remains `RECEIVED`,
   appends a safe transient attempt when possible, and returns `503` so the provider
   can retry. Internal exception details are not returned or persisted.

`WebhookProcessingAttempt` is an append-only operational ledger for provider
deliveries and owner recovery actions. It stores the source, outcome, actor label,
mandatory reason, bounded safe detail, and a compact provider snapshot. It never
stores credentials, signatures, customer contact details, or the full webhook body.

An active owner may open a captured-payment exception and first run a dry provider
inspection. Applying recovery requires a second provider read through credentials for
the event's exact Razorpay mode. Payment ID, order ID, amount in paise, INR currency,
captured status, and local contribution state must all match. Only an eligible
`PENDING` contribution, or an already-confirmed idempotent equivalent, may proceed
through the existing confirmation and locked-rate allocation services. The action
requires a reason and appends both a processing attempt and `WEBHOOK_RECOVERY` audit
event. Amount/order mismatches, failed contributions, and abandoned late captures
remain manual reconciliation/refund cases and cannot be overridden in this UI.

## Consequences

Provider retries are reserved for failures that can plausibly succeed later, while
durable exceptions become visible owner work without repeatedly rejecting an
authenticated delivery. Recovery uses current provider evidence and the established
financial services, so it cannot manufacture a second allocation or bypass Test/Live
mode isolation.

The owner needs working mode-matched Razorpay API credentials to inspect or apply a
recovery. Provider unavailability leaves the exception unchanged and records the
attempt. The application still relies on daily reconciliation and manual Razorpay
Dashboard refund/dispute procedures for cases where no entitlement is allowed.

This increment does not implement automatic refunds, background jobs, webhook-secret
overlap rotation, or external alert delivery. Stale `RECEIVED` monitoring and a
controlled webhook-secret rotation rehearsal remain follow-up work under
`FW-PAY-003`, `FW-PROD-002`, and `FW-PROD-003`.
