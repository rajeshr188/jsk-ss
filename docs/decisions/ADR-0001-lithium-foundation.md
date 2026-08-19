# ADR-0001 — Use Lithium as the Application Foundation

## Context

The selected starter already provides a custom user, django-allauth, Bootstrap/crispy forms, static-file handling, common templates, and production dependencies.

## Decision

Reuse Lithium's `CustomUser`, authentication, Bootstrap templates, crispy forms, static configuration, and Django project structure rather than rebuilding them.

## Consequences

Delivery starts from a proven conventional base and avoids a risky authentication migration. Product-specific domain apps and branding are added incrementally.
