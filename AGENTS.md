# Agent Contract

## Project

This is the Jai Shri Krishna Jewellery Savings Scheme: a single-business Django application, not a multi-tenant SaaS product.

## Technology

Django 6, PostgreSQL, django-allauth, Bootstrap 5, crispy forms, and the Lithium foundation.

## Architecture rules

- Keep `accounts.CustomUser`; never introduce a replacement user model.
- Put financial mutations in explicit services and non-trivial reads in selectors.
- Use the Django ORM directly; do not add a generic repository layer.
- Treat immutable or append-oriented transaction records as the financial source of truth.
- Use `Decimal`, never float, for money, rates, or metal quantities.
- Do not use signals for critical financial workflows or hidden payment bypasses.
- Keep INR, gold, and silver liabilities separate.
- Preserve historical financial records and enforce invariants in the database where practical.

## Agent workflow

Before a significant change:

1. Read this file and `docs/STATUS.md`.
2. Read the relevant `docs/MVP_PLAN.md` and `docs/DOMAIN_RULES.md` sections.
3. Inspect the affected code and implement only the requested scope.
4. Run affected tests, broader regression tests when appropriate, and Django checks.
5. Update `docs/STATUS.md` when project state changes.

Any change affecting payments, metal quantity, rates, balances, redemption, bonus, or liability must include appropriate tests.

## Forbidden architectural drift

Do not introduce multi-tenancy, PostgreSQL RLS/schema tenancy, React, an internal REST API, microservices, Celery, Redis, double-entry accounting, inventory, a generic event bus/repository, a new authentication framework, or a replacement `CustomUser` without an explicit architecture decision.

Do not create Markdown files casually. Update canonical documentation unless a significant, hard-to-reverse decision requires an ADR.
