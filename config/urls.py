"""
Root URL configuration for Fuel Route Optimizer.

Mounts the API versioned under /api/v1/ and serves OpenAPI docs at /api/docs/.
"""

from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

urlpatterns = [
    # Frontend Dashboard
    path("", include("apps.route_optimizer.urls")),
    # Admin
    path("admin/", admin.site.urls),
    # API v1
    path("api/v1/", include("apps.route_optimizer.api.urls")),
    # OpenAPI schema & interactive docs
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path(
        "api/redoc/",
        SpectacularRedocView.as_view(url_name="schema"),
        name="redoc",
    ),
]
