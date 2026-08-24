from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models.functions import Lower
from django.utils.text import slugify
from modelcluster.fields import ParentalKey, ParentalManyToManyField
from wagtail.admin.panels import FieldPanel, InlinePanel, MultiFieldPanel
from wagtail.fields import RichTextField
from wagtail.models import Orderable, Page
from wagtail.search import index
from wagtail.snippets.models import register_snippet


class CatalogueTaxonomy(models.Model):
    name = models.CharField(max_length=80)
    slug = models.SlugField(max_length=80, unique=True, blank=True)
    description = models.CharField(max_length=240, blank=True)

    panels = [
        FieldPanel("name"),
        FieldPanel("slug"),
        FieldPanel("description"),
    ]

    class Meta:
        abstract = True
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                Lower("name"),
                name="%(app_label)s_%(class)s_name_ci_unique",
            ),
        ]

    def __str__(self):
        return self.name

    def _normalize(self):
        self.name = self.name.strip()
        self.slug = slugify(self.slug or self.name)

    def clean(self):
        super().clean()
        self._normalize()
        if not self.name:
            raise ValidationError({"name": "Enter a category or collection name."})
        if not self.slug:
            raise ValidationError({"slug": "Enter a URL-safe slug."})

    def save(self, *args, **kwargs):
        self._normalize()
        return super().save(*args, **kwargs)


@register_snippet
class ProductCategory(CatalogueTaxonomy):
    class Meta(CatalogueTaxonomy.Meta):
        verbose_name = "product category"
        verbose_name_plural = "product categories"


@register_snippet
class ProductCollection(CatalogueTaxonomy):
    class Meta(CatalogueTaxonomy.Meta):
        verbose_name = "product collection"
        verbose_name_plural = "product collections"


class CatalogIndexPage(Page):
    intro = RichTextField(
        blank=True,
        features=["bold", "italic", "link"],
        help_text="A concise introduction shown above the product catalogue.",
    )

    max_count = 1
    parent_page_types = ["wagtailcore.Page"]
    subpage_types = ["catalog.ProductPage"]

    content_panels = Page.content_panels + [FieldPanel("intro")]

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)
        context["products"] = self.get_children().live().public().specific()
        return context

    class Meta:
        verbose_name = "catalogue index page"


class ProductPage(Page):
    product_code = models.CharField(
        max_length=40,
        help_text="Stable internal catalogue reference, for example JSK-G-001.",
    )
    category = models.ForeignKey(
        ProductCategory,
        on_delete=models.PROTECT,
        related_name="products",
    )
    collections = ParentalManyToManyField(
        ProductCollection,
        blank=True,
        related_name="products",
    )
    short_description = models.CharField(max_length=280)
    description = RichTextField(
        blank=True,
        features=["h2", "h3", "bold", "italic", "ol", "ul", "link"],
    )
    display_price_inr = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.01"))],
        help_text=(
            "Optional informational catalogue price in INR. This is not a Scheme Rate, "
            "customer entitlement, invoice, or online checkout price."
        ),
    )
    enquiry_note = models.CharField(
        max_length=240,
        default="Contact our Vellore showroom for current availability and final price.",
    )
    featured = models.BooleanField(default=False)

    parent_page_types = ["catalog.CatalogIndexPage"]
    subpage_types = []

    content_panels = Page.content_panels + [
        MultiFieldPanel(
            [
                FieldPanel("product_code"),
                FieldPanel("category"),
                FieldPanel("collections", widget=forms.CheckboxSelectMultiple),
                FieldPanel("featured"),
            ],
            heading="Catalogue classification",
        ),
        FieldPanel("short_description"),
        FieldPanel("description"),
        MultiFieldPanel(
            [
                FieldPanel("display_price_inr"),
                FieldPanel("enquiry_note"),
            ],
            heading="Showroom information",
        ),
        InlinePanel("gallery_images", label="Product image"),
    ]

    search_fields = Page.search_fields + [
        index.SearchField("product_code", partial_match=True),
        index.SearchField("short_description"),
        index.SearchField("description"),
        index.FilterField("category"),
        index.FilterField("featured"),
    ]

    class Meta:
        verbose_name = "product page"
        constraints = [
            models.UniqueConstraint(
                Lower("product_code"),
                name="catalog_product_code_ci_unique",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(display_price_inr__isnull=True)
                    | models.Q(display_price_inr__gt=0)
                ),
                name="catalog_product_display_price_positive",
            ),
        ]

    def _normalize(self):
        self.product_code = self.product_code.strip().upper()

    def clean(self):
        super().clean()
        self._normalize()
        if not self.product_code:
            raise ValidationError({"product_code": "Enter a product code."})

    def save(self, *args, **kwargs):
        self._normalize()
        return super().save(*args, **kwargs)


class ProductImage(Orderable):
    page = ParentalKey(
        ProductPage,
        on_delete=models.CASCADE,
        related_name="gallery_images",
    )
    image = models.ForeignKey(
        "wagtailimages.Image",
        on_delete=models.PROTECT,
        related_name="catalogue_placements",
    )
    alt_text = models.CharField(
        max_length=160,
        help_text="Describe the jewellery for customers who cannot see the image.",
    )
    caption = models.CharField(max_length=160, blank=True)

    panels = [
        FieldPanel("image"),
        FieldPanel("alt_text"),
        FieldPanel("caption"),
    ]

    class Meta(Orderable.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=["page", "image"],
                name="catalog_product_image_once",
            ),
        ]
