from django.urls import path

from .views import (
    AboutPageView,
    CancellationRefundPageView,
    ContactPageView,
    HomePageView,
    OurStoryPageView,
    PricingPageView,
    PrivacyPageView,
    ShippingDeliveryPageView,
    TermsPageView,
    live_health,
    ready_health,
)

urlpatterns = [
    path("", HomePageView.as_view(), name="home"),
    path("about/", AboutPageView.as_view(), name="about"),
    path("our-story/", OurStoryPageView.as_view(), name="our_story"),
    path("contact/", ContactPageView.as_view(), name="contact"),
    path("plans/", PricingPageView.as_view(), name="pricing"),
    path("terms/", TermsPageView.as_view(), name="terms"),
    path("privacy/", PrivacyPageView.as_view(), name="privacy"),
    path(
        "cancellation-and-refunds/",
        CancellationRefundPageView.as_view(),
        name="cancellation_refund",
    ),
    path(
        "shipping-and-delivery/",
        ShippingDeliveryPageView.as_view(),
        name="shipping_delivery",
    ),
    path("health/live/", live_health, name="health_live"),
    path("health/ready/", ready_health, name="health_ready"),
]
