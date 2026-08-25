from django.core.exceptions import ValidationError
from django.db import models
from wagtail.admin.panels import FieldPanel, MultiFieldPanel
from wagtail.fields import RichTextField
from wagtail.models import Page
from wagtail.search import index


EDITORIAL_RICH_TEXT_FEATURES = ["h2", "h3", "bold", "italic", "ol", "ul", "link"]


class AboutPage(Page):
    eyebrow = models.CharField(max_length=80, default="About us")
    introduction = models.TextField(
        max_length=600,
        help_text="A concise introduction to the business. Do not enter plan or policy terms.",
    )
    business_story_heading = models.CharField(
        max_length=120,
        default="Personal service, supported by dependable records",
    )
    business_story = RichTextField(
        features=EDITORIAL_RICH_TEXT_FEATURES,
        help_text=(
            "Business background only. Savings, payment, eligibility, and policy "
            "facts remain application-owned below this section."
        ),
    )
    hero_image = models.ForeignKey(
        "wagtailimages.Image",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    hero_image_alt = models.CharField(max_length=160, blank=True)

    max_count = 1
    parent_page_types = ["wagtailcore.Page"]
    subpage_types = []

    content_panels = Page.content_panels + [
        FieldPanel("eyebrow"),
        FieldPanel("introduction"),
        FieldPanel("business_story_heading"),
        FieldPanel("business_story"),
        MultiFieldPanel(
            [FieldPanel("hero_image"), FieldPanel("hero_image_alt")],
            heading="Optional business image",
        ),
    ]
    search_fields = Page.search_fields + [
        index.SearchField("introduction"),
        index.SearchField("business_story"),
    ]

    def clean(self):
        super().clean()
        if self.hero_image_id and not self.hero_image_alt.strip():
            raise ValidationError(
                {"hero_image_alt": "Describe the business image."}
            )

    class Meta:
        verbose_name = "About page"


class OurStoryPage(Page):
    eyebrow = models.CharField(
        max_length=80,
        default="The people behind the name",
    )
    introduction = models.TextField(max_length=600)
    business_owner_name = models.CharField(max_length=120, default="Dilip Kumar")
    business_owner_role = models.CharField(
        max_length=120,
        default="Owner & business lead",
    )
    business_owner_tagline = models.CharField(
        max_length=240,
        default="Computer science engineer by qualification, businessman by heart.",
    )
    business_owner_bio = RichTextField(features=EDITORIAL_RICH_TEXT_FEATURES)
    business_owner_image = models.ForeignKey(
        "wagtailimages.Image",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    business_owner_image_alt = models.CharField(max_length=160, blank=True)
    developer_name = models.CharField(max_length=120, default="Rajesh Rathod H")
    developer_role = models.CharField(max_length=120, default="Developer")
    developer_tagline = models.CharField(
        max_length=240,
        default="Software developer by heart.",
    )
    developer_bio = RichTextField(features=EDITORIAL_RICH_TEXT_FEATURES)
    developer_email = models.EmailField(default="rajeshrathodh@gmail.com")
    developer_image = models.ForeignKey(
        "wagtailimages.Image",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    developer_image_alt = models.CharField(max_length=160, blank=True)
    partnership_heading = models.CharField(
        max_length=160,
        default="Built together, for the customers they serve",
    )
    partnership_story = RichTextField(features=EDITORIAL_RICH_TEXT_FEATURES)

    max_count = 1
    parent_page_types = ["wagtailcore.Page"]
    subpage_types = []

    content_panels = Page.content_panels + [
        FieldPanel("eyebrow"),
        FieldPanel("introduction"),
        MultiFieldPanel(
            [
                FieldPanel("business_owner_name"),
                FieldPanel("business_owner_role"),
                FieldPanel("business_owner_tagline"),
                FieldPanel("business_owner_bio"),
                FieldPanel("business_owner_image"),
                FieldPanel("business_owner_image_alt"),
            ],
            heading="Owner profile",
        ),
        MultiFieldPanel(
            [
                FieldPanel("developer_name"),
                FieldPanel("developer_role"),
                FieldPanel("developer_tagline"),
                FieldPanel("developer_bio"),
                FieldPanel("developer_email"),
                FieldPanel("developer_image"),
                FieldPanel("developer_image_alt"),
            ],
            heading="Developer profile",
        ),
        MultiFieldPanel(
            [FieldPanel("partnership_heading"), FieldPanel("partnership_story")],
            heading="Partnership",
        ),
    ]
    search_fields = Page.search_fields + [
        index.SearchField("introduction"),
        index.SearchField("business_owner_name"),
        index.SearchField("business_owner_bio"),
        index.SearchField("developer_name"),
        index.SearchField("developer_bio"),
        index.SearchField("partnership_story"),
    ]

    def clean(self):
        super().clean()
        errors = {}
        for image_id, alt_text, field_name, label in (
            (
                self.business_owner_image_id,
                self.business_owner_image_alt,
                "business_owner_image_alt",
                "owner profile",
            ),
            (
                self.developer_image_id,
                self.developer_image_alt,
                "developer_image_alt",
                "developer profile",
            ),
        ):
            if image_id and not alt_text.strip():
                errors[field_name] = f"Describe the {label} image."
        if errors:
            raise ValidationError(errors)

    class Meta:
        verbose_name = "Our Story page"
