import logging

from django.conf import settings
from django.db import DatabaseError, connection
from django.http import Http404, HttpResponse, JsonResponse
from django.template.loader import render_to_string
from django.templatetags.static import static
from django.views.decorators.http import require_GET
from django.views.generic import ListView, TemplateView

from schemes.selectors import get_public_scheme_plans
from .models import AboutPage, OurStoryPage
from .selectors import public_editorial_page

logger = logging.getLogger(__name__)


def _require_pwa_enabled():
    if not settings.PWA_ENABLED:
        raise Http404


@require_GET
def android_asset_links(request):
    if not settings.ANDROID_TWA_ASSET_LINKS_ENABLED:
        raise Http404

    response = JsonResponse(
        [
            {
                "relation": ["delegate_permission/common.handle_all_urls"],
                "target": {
                    "namespace": "android_app",
                    "package_name": settings.ANDROID_TWA_PACKAGE_NAME,
                    "sha256_cert_fingerprints": list(
                        settings.ANDROID_TWA_PLAY_SHA256_FINGERPRINTS
                    ),
                },
            }
        ],
        safe=False,
    )
    # Keep certificate rotation recoverable without forcing every request to Django.
    response["Cache-Control"] = "public, max-age=3600"
    response["X-Robots-Tag"] = "noindex, nofollow"
    return response


@require_GET
def pwa_manifest(request):
    _require_pwa_enabled()
    response = JsonResponse(
        {
            "id": "/",
            "name": "Jai Sri Krishna Jewellery",
            "short_name": "JSK Jewellery",
            "description": (
                "Customer access to jewellery savings plans and scheme records."
            ),
            "lang": "en-IN",
            "start_url": "/",
            "scope": "/",
            "display": "standalone",
            "background_color": "#f8f5ef",
            "theme_color": "#2d1811",
            "prefer_related_applications": False,
            "icons": [
                {
                    "src": static("images/pwa-icon-192.png"),
                    "sizes": "192x192",
                    "type": "image/png",
                    "purpose": "any",
                },
                {
                    "src": static("images/pwa-icon-512.png"),
                    "sizes": "512x512",
                    "type": "image/png",
                    "purpose": "any maskable",
                },
            ],
        }
    )
    response["Content-Type"] = "application/manifest+json"
    response["Cache-Control"] = "no-cache"
    return response


@require_GET
def service_worker(request):
    _require_pwa_enabled()
    response = HttpResponse(
        render_to_string(
            "pages/service_worker.js",
            {"app_release": settings.APP_RELEASE},
        ),
        content_type="text/javascript",
    )
    response["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response["Service-Worker-Allowed"] = "/"
    return response


@require_GET
def offline_page(request):
    _require_pwa_enabled()
    response = HttpResponse(render_to_string("pages/offline.html"))
    response["Cache-Control"] = "public, max-age=86400"
    response["X-Robots-Tag"] = "noindex, nofollow"
    return response


def _health_response(payload, *, status=200):
    response = JsonResponse(payload, status=status)
    response["Cache-Control"] = "no-store"
    return response


@require_GET
def live_health(request):
    return _health_response({"status": "ok", "release": settings.APP_RELEASE})


@require_GET
def ready_health(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except DatabaseError:
        logger.warning("Database readiness check failed")
        return _health_response(
            {"status": "unavailable", "release": settings.APP_RELEASE}, status=503
        )
    return _health_response({"status": "ok", "release": settings.APP_RELEASE})


class HomePageView(TemplateView):
    template_name = "pages/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["featured_plans"] = get_public_scheme_plans(limit=3)
        context["customer_enrolment_requests_enabled"] = (
            settings.CUSTOMER_ENROLMENT_REQUESTS_ENABLED
        )
        return context


class EditorialPageFallbackMixin:
    editorial_page_model = None

    def get(self, request, *args, **kwargs):
        if settings.PUBLIC_EDITORIAL_PAGES_ENABLED:
            page = public_editorial_page(self.editorial_page_model)
            if page is not None:
                return page.specific.serve(request)
        return super().get(request, *args, **kwargs)


class AboutPageView(EditorialPageFallbackMixin, TemplateView):
    template_name = "pages/about.html"
    editorial_page_model = AboutPage


class OurStoryPageView(EditorialPageFallbackMixin, TemplateView):
    template_name = "pages/our_story.html"
    editorial_page_model = OurStoryPage


class ContactPageView(TemplateView):
    template_name = "pages/contact.html"


class PricingPageView(ListView):
    template_name = "pages/pricing.html"
    context_object_name = "plans"

    def get_queryset(self):
        return get_public_scheme_plans()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["customer_enrolment_requests_enabled"] = (
            settings.CUSTOMER_ENROLMENT_REQUESTS_ENABLED
        )
        return context


class HowItWorksPageView(TemplateView):
    template_name = "pages/how_it_works.html"


class TermsPageView(TemplateView):
    template_name = "pages/terms.html"


class PrivacyPageView(TemplateView):
    template_name = "pages/privacy.html"


class CancellationRefundPageView(TemplateView):
    template_name = "pages/cancellation_refund.html"


class ShippingDeliveryPageView(TemplateView):
    template_name = "pages/shipping_delivery.html"
