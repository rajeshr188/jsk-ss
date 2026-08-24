from dataclasses import dataclass

from django.db.models import Prefetch, Q

from .models import (
    CatalogIndexPage,
    ProductCategory,
    ProductCollection,
    ProductImage,
    ProductPage,
)


CATALOG_PAGE_SIZE = 12
CATALOG_QUERY_MAX_LENGTH = 100


def public_catalogue_root():
    return CatalogIndexPage.objects.live().public().first()


@dataclass(frozen=True)
class CatalogueFilters:
    query: str = ""
    category_slug: str = ""
    collection_slug: str = ""

    @classmethod
    def from_request(cls, request):
        return cls(
            query=request.GET.get("q", "").strip()[:CATALOG_QUERY_MAX_LENGTH],
            category_slug=request.GET.get("category", "").strip(),
            collection_slug=request.GET.get("collection", "").strip(),
        )

    @property
    def is_active(self):
        return bool(self.query or self.category_slug or self.collection_slug)


def published_products(catalogue):
    gallery = ProductImage.objects.select_related("image").order_by("sort_order", "pk")
    return (
        ProductPage.objects.child_of(catalogue)
        .live()
        .public()
        .select_related("category")
        .prefetch_related("collections", Prefetch("gallery_images", queryset=gallery))
    )


def catalogue_facets(products):
    categories = (
        ProductCategory.objects.filter(products__in=products)
        .distinct()
        .order_by("name")
    )
    collections = (
        ProductCollection.objects.filter(products__in=products)
        .distinct()
        .order_by("name")
    )
    return categories, collections


def filter_catalogue_products(products, filters):
    if filters.category_slug:
        products = products.filter(category__slug=filters.category_slug)
    if filters.collection_slug:
        products = products.filter(collections__slug=filters.collection_slug)
    if filters.query:
        products = products.filter(
            Q(title__icontains=filters.query)
            | Q(product_code__icontains=filters.query)
            | Q(short_description__icontains=filters.query)
            | Q(description__icontains=filters.query)
        )
    return products.distinct().order_by("-featured", "title")
