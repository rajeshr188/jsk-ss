from wagtail.models import Site


def public_editorial_page(page_model):
    """Return the single live editorial page inside the default Site tree."""
    site = Site.objects.select_related("root_page").filter(is_default_site=True).first()
    if site is None:
        return None
    return (
        page_model.objects.live()
        .public()
        .descendant_of(site.root_page, inclusive=True)
        .first()
    )
