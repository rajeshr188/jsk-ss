from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from wagtail import urls as wagtail_urls
from wagtail.admin import urls as wagtailadmin_urls
from wagtail.documents import urls as wagtaildocs_urls

urlpatterns = [
    path("admin/", admin.site.urls),
    path("cms/", include(wagtailadmin_urls)),
    path("documents/", include(wagtaildocs_urls)),
    path("accounts/", include("accounts.urls")),
    path("accounts/", include("allauth.urls")),
    path("scheme/", include("schemes.urls")),
    path("", include("pages.urls")),
]

if "debug_toolbar" in settings.INSTALLED_APPS:
    import debug_toolbar

    urlpatterns = [
        path("__debug__/", include(debug_toolbar.urls)),
    ] + urlpatterns
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Existing Django routes take precedence. Wagtail receives only paths that were
# not matched above, leaving catalogue page types for a later implementation phase.
urlpatterns += [path("", include(wagtail_urls))]
