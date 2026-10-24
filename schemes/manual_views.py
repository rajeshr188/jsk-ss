"""Read-only owner handbook, sourced from the version-controlled illustrated guide."""
import re
from pathlib import Path

from django.conf import settings
from django.http import FileResponse, Http404, HttpResponse
from django.urls import reverse
from django.utils.html import format_html
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe
from django.views.decorators.vary import vary_on_cookie

from .permissions import owner_required


GUIDE_ASSETS = frozenset({
    "create-configuration.jpg", "configuration-preview.jpg", "draft-plan.jpg",
    "publication.jpg",
})


def _guide_directory():
    return Path(settings.BASE_DIR) / "docs" / "guides" / "plan-configuration"


def _protect_manual_response(response):
    response["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    response["X-Content-Type-Options"] = "nosniff"
    response["Content-Security-Policy"] = (
        "default-src 'none'; style-src 'unsafe-inline'; img-src 'self'; "
        "base-uri 'none'; frame-ancestors 'none'; form-action 'none'"
    )
    return response


@never_cache
@vary_on_cookie
@owner_required
@require_safe
def plan_manual(request):
    """No plan queries or mutations; availability is independent of intake activation."""
    html = (_guide_directory() / "index.html").read_text(encoding="utf-8")
    # Keep the standalone guide usable from disk and mount its illustrations through
    # authenticated URLs here. No general-purpose file/document serving endpoint.
    for filename in GUIDE_ASSETS:
        html = html.replace(
            f'"assets/{filename}"',
            f'"{reverse("schemes:plan_manual_asset", args=[filename])}"',
        )
    # Repository Markdown is developer context, not a public document directory.
    html = re.sub(
        r'<a href="\.\./\.\./[^"<>]+\.md">([^<>]+)</a>',
        r'<span>\1 (repository reference)</span>',
        html,
    )
    intake = "enabled" if settings.CONFIGURED_PLANS_ENABLED else "disabled"
    navigation = format_html(
        '<div class="note info" aria-label="Owner manual navigation">'
        '<p><a href="{}">Back to Scheme plans</a> · '
        '<a href="{}">Configuration catalogue</a></p>'
        '<p><strong>Owner reference manual.</strong> New configured-plan intake is '
        '<strong>{}</strong> in this environment. Reading this manual does not enable '
        'intake or change agreements. Release notes in the guide describe its dated '
        'edition, not a live deployment assessment. Use browser Print to print or save '
        'a PDF; repository references are maintained by the developer.</p></div>',
        reverse("schemes:plan_list"), reverse("schemes:plan_configuration_list"), intake,
    )
    html = html.replace('<header><div class="wrap">', '<header><div class="wrap">' + str(navigation), 1)
    return _protect_manual_response(HttpResponse(html))


@never_cache
@vary_on_cookie
@owner_required
@require_safe
def plan_manual_asset(request, filename):
    if filename not in GUIDE_ASSETS:
        raise Http404
    response = FileResponse(
        (_guide_directory() / "assets" / filename).open("rb"), content_type="image/jpeg",
    )
    return _protect_manual_response(response)
