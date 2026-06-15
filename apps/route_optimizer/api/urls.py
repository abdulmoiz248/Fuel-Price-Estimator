"""
URL configuration for the Route Optimizer API v1.
"""

from django.urls import path

from . import views

app_name = "route_optimizer"

urlpatterns = [
    # Core endpoint
    path(
        "route/optimize/",
        views.RouteOptimizeView.as_view(),
        name="route-optimize",
    ),
    # Fuel station listing
    path(
        "stations/",
        views.FuelStationListView.as_view(),
        name="station-list",
    ),
    # Health check
    path(
        "health/",
        views.HealthCheckView.as_view(),
        name="health-check",
    ),
]
