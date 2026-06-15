"""
Frontend URL configuration for the Route Optimizer application.
"""

from django.urls import path
from .views import IndexView

app_name = "route_optimizer_frontend"

urlpatterns = [
    path("", IndexView.as_view(), name="index"),
]
