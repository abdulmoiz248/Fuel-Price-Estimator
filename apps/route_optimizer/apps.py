from django.apps import AppConfig


class RouteOptimizerConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.route_optimizer"
    verbose_name = "Route Optimizer"

    def ready(self):
        """Perform app initialization on startup."""
        pass
