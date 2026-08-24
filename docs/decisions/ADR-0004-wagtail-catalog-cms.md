# ADR-0004 — Adopt Wagtail as a Bounded Catalogue CMS

**Status:** Accepted  
**Date:** 2026-08-24

## Context

Jai Sri Krishna Jewelley currently serves public information, savings-plan pages,
customer accounts, and owner financial workflows with ordinary Django views and
templates. A future public jewellery catalogue will require the owner to create,
preview, revise, publish, unpublish, and organize product content and images without
a software release for each content change.

Building those editorial capabilities directly in Django admin would duplicate
content-management features. Wagtail 7.4 is an LTS release that supports Django 6
and can be integrated into an existing Django project while retaining
`accounts.CustomUser`, PostgreSQL, the existing Bootstrap 5 public interface, and
the existing Django admin.

Production currently uses local `FileSystemStorage` while the web container is
read-only and has no persistent media volume. User-uploaded catalogue media
therefore requires durable object storage before any CMS upload workflow can be
released.

## Decision

Adopt Wagtail as a **bounded catalogue and editorial CMS**, not as a replacement for
the application or its financial domain. Implementation will begin from Wagtail
7.4 LTS on its current patched release and will remain compatible with the
project's supported Django 6 version.

The integration must observe these boundaries:

- Keep `accounts.CustomUser` as the only user model and use the same PostgreSQL
  database.
- Mount Wagtail administration at `/cms/`; retain Django administration at
  `/admin/`, owner financial workflows at `/scheme/`, and existing customer routes.
- Grant CMS access through explicit staff status and narrowly scoped Wagtail groups.
  An application `OWNER` role alone does not grant CMS access, and customers must
  not be able to enter the CMS.
- Keep plans, Scheme Rates, contributions, Razorpay records, metal allocations,
  balances, redemptions, bonuses, and audit events outside Wagtail. CMS code must
  not mutate or become authoritative for any financial record.
- Add a dedicated `catalog` application. Its initial public content model will use
  a `CatalogIndexPage` and `ProductPage`, with reusable categories or collections
  represented as Wagtail snippets where appropriate.
- Treat catalogue presentation as product discovery and showroom enquiry. Inventory,
  carts, online product checkout, invoicing, tax calculation, and fulfilment remain
  separate future domains. Catalogue product values must not reuse or imply the
  authoritative customer-allocation `SchemeRate`.
- Keep the public frontend on server-rendered Django/Wagtail templates and Bootstrap
  5. Use PostgreSQL-backed Wagtail search initially; do not introduce Elasticsearch
  without measured requirements.
- Leave existing public, policy, savings-plan, and account pages as ordinary Django
  views initially. Moving a page into Wagtail requires a later, explicit content and
  URL-migration decision.

Cloudflare R2 Standard storage is selected for uploaded media, initially using its
free usage allowance. The application will use R2's S3-compatible API through
`django-storages`; credentials and endpoints must be environment variables, and the
API token must have only Object Read & Write access to the dedicated media bucket.
Production media will use an owned custom media domain. Cloudflare's rate-limited
`r2.dev` URL is acceptable only during development or an isolated spike. WhiteNoise
continues to serve versioned application static files; R2 is for uploaded media,
not a replacement static-files deployment.

At the decision date, Cloudflare documents a monthly free allowance for R2 Standard
storage and operations. This is a pricing snapshot, not a capacity or availability
guarantee; usage and current pricing must be reviewed before production activation.

## Consequences

The owner gains mature revisions, preview, publishing, image rendition, collection,
and SEO workflows without embedding those concerns in the financial application.
Customers continue to use the current authentication and savings interfaces, and
the catalogue can retain the existing visual design.

The application gains Wagtail tables, dependencies, upgrades, permissions, and
media operations that must be tested and maintained. Django Sites and Wagtail Sites
will coexist and require deliberate configuration. Publication notifications must
not depend on email until production SMTP delivery is verified.

The R2 bucket, custom media domain, CORS/cache behavior, lifecycle, backup/recovery,
cost monitoring, and credential rotation become production responsibilities.
Original uploads and public renditions require an explicit exposure policy before
real product images are uploaded.

The rollout is additive and reversible at the application level. A failed spike may
remove its code before release; once production content exists, Wagtail migrations
and R2 objects must be preserved and rolled back through a planned forward change,
not destructive database or bucket deletion.

## Alternatives considered

- **Extend Django admin only:** technically feasible for basic product records, but
  it would require the project to build and maintain preview, revisions, scheduled
  publishing, image rendition, page hierarchy, and editorial permissions as catalogue
  needs grow.
- **Replace the public site with Wagtail immediately:** rejected because the current
  Django pages and financial workflows work, and a broad URL/content migration would
  add risk without helping the first catalogue release.
- **Use Wagtail as a headless CMS or run a separate CMS service:** rejected for the
  initial implementation because it would add an API/frontend or another deployed
  service with no current business need. In-process server-rendered integration is
  the smallest useful architecture.
- **Persist media on the Compute Instance:** rejected for production because the
  container is deliberately immutable and horizontally disposable; instance-local
  uploads would complicate recovery and future replacement.

## Delivery gates

1. Prove Wagtail 7.4 LTS installation, checks, migrations, `/cms/` routing, existing
   authentication compatibility, and unchanged financial regressions on a feature
   branch. Do not create catalogue models in this gate.
2. Configure an isolated R2 bucket and custom Django storage backend; prove upload,
   rendition, retrieval, deletion policy, and credential isolation before relying on
   CMS media.
3. Implement and validate the bounded catalogue model, editorial permissions, and
   draft/publish behavior.
4. Build the Bootstrap 5 public catalogue, product detail, enquiry, metadata, and
   accessible responsive image experience.
5. Exercise production migration, media recovery, security, performance, monitoring,
   and rollback procedures before owner training and public launch.

## References

- [Wagtail 7.4 LTS release and Django 6 support](https://docs.wagtail.org/en/stable-7.4.x/releases/7.4.html)
- [Integrating Wagtail into an existing Django project](https://docs.wagtail.org/en/stable-7.4.x/getting_started/integrating_into_django.html)
- [Wagtail custom user models](https://docs.wagtail.org/en/stable-7.4.x/advanced_topics/customization/custom_user_models.html)
- [Cloudflare R2 pricing](https://developers.cloudflare.com/r2/pricing/)
- [Cloudflare R2 S3 compatibility](https://developers.cloudflare.com/r2/api/s3/api/)
- [`django-storages` Cloudflare R2 configuration](https://django-storages.readthedocs.io/en/latest/backends/s3_compatible/cloudflare-r2.html)
