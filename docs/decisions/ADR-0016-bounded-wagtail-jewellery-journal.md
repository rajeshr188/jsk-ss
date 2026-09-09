# ADR-0016 — Add a Bounded Wagtail Jewellery Journal

**Status:** Accepted
**Date:** 2026-09-10

## Context

The business wants to publish genuine jewellery guidance, care information, and
showroom stories without requiring a software release for every article. Wagtail 8
is already production-accepted for the catalogue and bounded editorial pages, with
durable R2 media, revision history, preview, and publisher approval.

A journal can improve public discovery and trust, but it must not become a second
source for Scheme Rates, savings-plan terms, product offers, customer advice, or
financial records. It must also be possible to deploy its schema and authorization
before exposing any incomplete or placeholder content.

## Decision

Add a separate `blog` Wagtail application with one `BlogIndexPage` at `/blog/` and
`BlogPostPage` children. The public label is **Jewellery journal**.

- Articles are business-authored educational or editorial content only. There are no
  public submissions, comments, customer profiles, or user-generated content.
- Scheme plans, Scheme Rates, product pricing, policy text, payments, allocations,
  eligibility, redemption, and all authenticated workflows remain authoritative in
  their existing Django domains. Articles link to those surfaces rather than copy or
  control their data.
- A post contains a publication date, public byline, short summary, constrained rich
  text, an optional featured image with required alt text, and a featured-order flag.
- Public listing is bounded to live, unrestricted children of the single blog root,
  ordered by featured status and publication date, and paginated to nine posts.
- `PUBLIC_BLOG_ENABLED` is an independent, disabled-by-default rollout control. When
  false, both direct Wagtail blog routes and global discovery links return or behave
  as unavailable. It does not delete or unpublish revisions, so authorized preview
  and approval remain possible before launch.
- Blog Editors, Publishers, and Administrators are distinct from Catalogue and
  Editorial groups. Access requires explicit staff membership. Images are scoped to
  a dedicated Blog media collection, and publication requires the Blog publisher
  approval workflow.
- Public templates remain server-rendered and use the existing Bootstrap 5 design.
  No analytics, advertising, comments, personalization, or new frontend framework is
  introduced by this decision.

## Consequences

The owner can prepare, preview, revise, approve, publish, and unpublish journal
articles through the existing CMS. Public URLs, navigation, metadata, accessible
images, and pagination are available without a separate service or API.

The application gains two Wagtail page tables, a new authorization configuration,
and another public content surface requiring factual review, accessibility checks,
media recovery, and ongoing editorial ownership. Publication is not sufficient for
exposure while the feature flag is disabled. Existing R2 source-original retention
limits continue to apply.

The foundation intentionally does not seed public articles. Real content must be
written and approved by the business. Categories, tags, site search, feeds, comments,
and article analytics may be evaluated only after actual content volume demonstrates
a need.

## Alternatives considered

- **Place articles in the catalogue app:** rejected because a journal has a different
  hierarchy, approval scope, and lifecycle from product discovery.
- **Use the existing Editorial groups and media collection:** rejected because those
  permissions govern the fixed About and Our Story pages and should not implicitly
  grant authority over an expanding article collection.
- **Publish static Django templates:** feasible for a few articles, but every content
  edit would require a code release and would bypass the accepted CMS review tools.
- **Add a third-party or headless blog:** rejected because it adds another service,
  identity boundary, and rendering path without a present need.

## Delivery gates

1. Apply the additive `blog.0001_initial` migration with public exposure disabled.
2. Reconcile and validate the dedicated groups, media collection, draft root, and
   publisher workflow; grant no implicit user membership.
3. Assign staff explicitly, create genuine articles, and verify preview, approval,
   metadata, responsive R2 renditions, accessibility, and mobile presentation.
4. Publish the approved root and posts, then enable `PUBLIC_BLOG_ENABLED`, recreate
   the web service, and verify `/blog/`, article routes, navigation, and existing
   application safety checks.
5. Roll back public exposure by disabling the flag. Preserve all database revisions
   and R2 objects; do not destructively reverse the migration after content exists.
