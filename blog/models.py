from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.core.paginator import Paginator
from django.http import Http404
from django.utils import timezone
from wagtail.admin.panels import FieldPanel, MultiFieldPanel
from wagtail.fields import RichTextField
from wagtail.models import Page
from wagtail.search import index


BLOG_RICH_TEXT_FEATURES = ["h2", "h3", "bold", "italic", "ol", "ul", "link"]


class PublicBlogGateMixin:
    def serve(self, request, *args, **kwargs):
        if not settings.PUBLIC_BLOG_ENABLED:
            raise Http404
        return super().serve(request, *args, **kwargs)


class BlogIndexPage(PublicBlogGateMixin, Page):
    intro = RichTextField(
        blank=True,
        features=["bold", "italic", "link"],
        help_text="A concise introduction to the jewellery journal.",
    )

    max_count = 1
    parent_page_types = ["wagtailcore.Page"]
    subpage_types = ["blog.BlogPostPage"]

    content_panels = Page.content_panels + [FieldPanel("intro")]

    def get_context(self, request, *args, **kwargs):
        from .selectors import BLOG_PAGE_SIZE, published_blog_posts

        context = super().get_context(request, *args, **kwargs)
        paginator = Paginator(published_blog_posts(self), BLOG_PAGE_SIZE)
        context["posts"] = paginator.get_page(request.GET.get("page"))
        return context

    class Meta:
        verbose_name = "blog index page"


class BlogPostPage(PublicBlogGateMixin, Page):
    publication_date = models.DateField(default=timezone.localdate)
    author_name = models.CharField(
        max_length=120,
        default="Jai Sri Krishna Jewellery",
        help_text="Public byline shown on the article.",
    )
    summary = models.CharField(
        max_length=280,
        help_text="A short, factual introduction shown in article listings.",
    )
    body = RichTextField(
        features=BLOG_RICH_TEXT_FEATURES,
        help_text=(
            "Business-authored educational or editorial content only. Do not enter "
            "Scheme Rates, customer-specific advice, or authoritative plan terms."
        ),
    )
    featured_image = models.ForeignKey(
        "wagtailimages.Image",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="blog_featured_placements",
    )
    featured_image_alt = models.CharField(max_length=160, blank=True)
    featured = models.BooleanField(default=False)

    parent_page_types = ["blog.BlogIndexPage"]
    subpage_types = []

    content_panels = Page.content_panels + [
        MultiFieldPanel(
            [
                FieldPanel("publication_date"),
                FieldPanel("author_name"),
                FieldPanel("featured"),
            ],
            heading="Article details",
        ),
        FieldPanel("summary"),
        FieldPanel("body"),
        MultiFieldPanel(
            [FieldPanel("featured_image"), FieldPanel("featured_image_alt")],
            heading="Optional featured image",
        ),
    ]
    search_fields = Page.search_fields + [
        index.SearchField("summary"),
        index.SearchField("body"),
        index.FilterField("publication_date"),
        index.FilterField("featured"),
    ]

    def clean(self):
        super().clean()
        self.author_name = self.author_name.strip()
        self.summary = self.summary.strip()
        if not self.author_name:
            raise ValidationError({"author_name": "Enter the public author name."})
        if not self.summary:
            raise ValidationError({"summary": "Enter a short article summary."})
        if self.featured_image_id and not self.featured_image_alt.strip():
            raise ValidationError(
                {"featured_image_alt": "Describe the featured image."}
            )

    def save(self, *args, **kwargs):
        self.author_name = self.author_name.strip()
        self.summary = self.summary.strip()
        return super().save(*args, **kwargs)

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)
        context["blog_index"] = self.get_parent().specific
        return context

    class Meta:
        verbose_name = "blog post"
