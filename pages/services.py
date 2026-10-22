import logging

from django.conf import settings
from django.db import DatabaseError, transaction
from django.db.models import F
from django.utils import timezone

from .models import PublicFunnelDailyCount

logger = logging.getLogger(__name__)


def record_public_funnel_step(request, step):
    """Count allowed public GET navigation; telemetry must never block a journey."""
    if not settings.PUBLIC_FUNNEL_MEASUREMENT_ENABLED or request.method != "GET":
        return
    user = request.user
    if user.is_authenticated and (user.is_staff or user.is_superuser or user.role != "CUSTOMER"):
        return
    if step not in PublicFunnelDailyCount.Step.values:
        raise ValueError("Unsupported public funnel step")
    try:
        with transaction.atomic():
            row, created = PublicFunnelDailyCount.objects.get_or_create(
                day=timezone.localdate(), step=step, defaults={"count": 1},
            )
            if not created:
                PublicFunnelDailyCount.objects.filter(pk=row.pk).update(count=F("count") + 1)
    except DatabaseError:
        # Static warning only: never log the request, URL, identity or exception.
        logger.warning("Public funnel aggregate could not be recorded")
