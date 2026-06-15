"""
Django development settings.

Extends base settings with development-friendly defaults.
"""

from .base import *  # noqa: F401, F403

DEBUG = True
ALLOWED_HOSTS = ["*"]

# More permissive throttling for development
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {  # noqa: F405
    "anon": "300/minute",
}

# Verbose logging in development
LOGGING["loggers"]["apps.route_optimizer"]["level"] = "DEBUG"  # noqa: F405
