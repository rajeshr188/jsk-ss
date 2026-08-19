import logging

from django.conf import settings
from django.db import DatabaseError, connection
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.views.generic import ListView, TemplateView

from schemes.models import SchemePlan

logger = logging.getLogger(__name__)


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


class AboutPageView(TemplateView):
    template_name = "pages/about.html"


class ContactPageView(TemplateView):
    template_name = "pages/contact.html"


class PricingPageView(ListView):
    template_name = "pages/pricing.html"
    context_object_name = "plans"

    def get_queryset(self):
        return SchemePlan.objects.filter(active=True, publicly_listed=True).order_by(
            "name", "code"
        )


class TermsPageView(TemplateView):
    template_name = "pages/terms.html"


class PrivacyPageView(TemplateView):
    template_name = "pages/privacy.html"


class CancellationRefundPageView(TemplateView):
    template_name = "pages/cancellation_refund.html"


class ShippingDeliveryPageView(TemplateView):
    template_name = "pages/shipping_delivery.html"
