"""
Frontend views for the Route Optimizer application.
"""

from django.views.generic import TemplateView


class IndexView(TemplateView):
    """
    Serves the main interactive dashboard for route optimization.
    """
    template_name = "route_optimizer/index.html"
