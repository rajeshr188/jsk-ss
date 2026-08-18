# Development

## Structure and conventions

- Keep authentication concerns in `accounts`, public content in `pages`, and current scheme domain work in `schemes`.
- Name mutation functions as commands (`create_customer`, `enroll_customer`) in `services.py`.
- Put reusable/non-trivial ORM reads in `selectors.py`.
- Keep views thin: authorize → validate → call a service/selector → render or redirect.
- Views must not contain substantial financial domain logic; signals must not orchestrate money workflows.
- Use class-based or function-based views according to clarity, server-rendered Bootstrap templates, named URLs, and crispy Django forms.
- Keep migrations committed and run `makemigrations --check --dry-run` before handoff.
- Keep payment and metal-rate providers behind their explicit boundaries; provider-specific fields must not leak through views or scheme models.
- Razorpay secrets remain server-side. Verify browser callbacks against the locally stored order, verify captured payment details through the server API, and validate webhooks against the unmodified request body before parsing.
- Webhook handlers must use the provider event ID for idempotency and route entitlement changes through the same contribution services as browser callbacks.
- Live rate adapters must use bounded network timeouts, validate provider identity/currency/timestamps/rates, avoid credentials in URLs or errors, and raise provider-neutral failures. Tests mock the HTTP boundary and never consume live quota.
- Once payment is verified, allocation failure must preserve the payment as `PAID_UNALLOCATED`; owner retry must call the idempotent allocation service rather than editing records directly.
- Redemption writes must go through `complete_redemption`, lock the scheme account, carry an idempotency key, and append an immutable record. Never edit historical contributions or allocations to represent settlement.

## Environment

Configuration comes from process environment variables. `.env.example` is documentation; use shell/IDE variables, Replit Secrets, or a deployment secret manager for real values.

## Adding a domain feature

Read the agent contract and domain rules, implement one milestone slice, add constraints and focused tests, apply migrations against PostgreSQL, run the regression suite and checks, manually exercise the flow, then update status/architecture only where reality changed.
