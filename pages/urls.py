from django.urls import path

from .views import (
    AboutPageView,
    CancellationRefundPageView,
    ContactPageView,
    HomePageView,
    HowItWorksPageView,
    OurStoryPageView,
    PricingPageView,
    PrivacyPageView,
    ShippingDeliveryPageView,
    TermsPageView,
    android_asset_links,
    live_health,
    offline_page,
    pwa_manifest,
    ready_health,
    service_worker,
)

urlpatterns = [
    path(
        ".well-known/assetlinks.json",
        android_asset_links,
        name="android_asset_links",
    ),
    path("", HomePageView.as_view(), name="home"),
    path("how-it-works/", HowItWorksPageView.as_view(), name="how_it_works"),
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
    path("manifest.webmanifest", pwa_manifest, name="pwa_manifest"),
    path("service-worker.js", service_worker, name="service_worker"),
    path("offline/", offline_page, name="pwa_offline"),
]
