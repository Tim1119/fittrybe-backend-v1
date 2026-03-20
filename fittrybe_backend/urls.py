from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

urlpatterns = [
    path("admin/", admin.site.urls),
    # API v1
    path("api/v1/", include("apps.core.urls")),
    path("api/v1/auth/", include("apps.accounts.urls")),
    path("api/v1/profiles/", include("apps.profiles.urls")),
    path("api/v1/clients/", include("apps.clients.urls")),
    path("api/v1/chat/", include("apps.chat.urls")),
    path("api/v1/marketplace/", include("apps.marketplace.urls")),
    path("api/v1/badges/", include("apps.badges.urls")),
    path("api/v1/subscriptions/", include("apps.subscriptions.urls")),
    path("api/v1/trackers/", include("apps.trackers.urls")),
    path("api/v1/analytics/", include("apps.analytics.urls")),
    path("api/v1/notifications/", include("apps.notifications.urls")),
    # API Schema
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]

if settings.DEBUG:
    import debug_toolbar

    urlpatterns += [path("__debug__/", include(debug_toolbar.urls))]
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
