"""
Django base settings for Fuel Route Optimizer.

This module contains settings common to all environments.
Environment-specific overrides go in development.py / production.py.

Generated for Django 5.2 LTS.
"""

import os
from pathlib import Path

from decouple import config, Csv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# =============================================================================
# SECURITY
# =============================================================================
SECRET_KEY = config(
    "DJANGO_SECRET_KEY",
    default="django-insecure-dev-only-change-in-production",
)
DEBUG = config("DJANGO_DEBUG", default=False, cast=bool)
ALLOWED_HOSTS = config("DJANGO_ALLOWED_HOSTS", default="*", cast=Csv())

# =============================================================================
# APPLICATION DEFINITION
# =============================================================================
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "corsheaders",
    "drf_spectacular",
]

LOCAL_APPS = [
    "apps.route_optimizer",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# =============================================================================
# MIDDLEWARE
# =============================================================================
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# =============================================================================
# DATABASE
# =============================================================================
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# =============================================================================
# PASSWORD VALIDATION
# =============================================================================
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# =============================================================================
# INTERNATIONALIZATION
# =============================================================================
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# =============================================================================
# STATIC FILES
# =============================================================================
STATIC_URL = "static/"

# =============================================================================
# DEFAULT AUTO FIELD
# =============================================================================
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# =============================================================================
# CORS
# =============================================================================
CORS_ALLOW_ALL_ORIGINS = config("CORS_ALLOW_ALL", default=True, cast=bool)

# =============================================================================
# DJANGO REST FRAMEWORK
# =============================================================================
REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "60/minute",
    },
    "EXCEPTION_HANDLER": "apps.route_optimizer.api.exceptions.custom_exception_handler",
}

# =============================================================================
# DRF-SPECTACULAR (OpenAPI / Swagger)
# =============================================================================
SPECTACULAR_SETTINGS = {
    "TITLE": "Fuel Route Optimizer API",
    "DESCRIPTION": (
        "REST API that computes the most cost-effective fuel stops along a "
        "route between two locations in the USA. Returns the route geometry, "
        "optimal fuel stations ranked by price, and total fuel expenditure "
        "assuming a vehicle with 500-mile range at 10 mpg."
    ),
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "CONTACT": {
        "name": "API Support",
        "email": "support@fueloptimizer.dev",
    },
    "LICENSE": {
        "name": "MIT",
    },
    "TAGS": [
        {
            "name": "Route Optimization",
            "description": "Endpoints for computing optimal fuel routes.",
        },
        {
            "name": "Fuel Stations",
            "description": "Endpoints for querying fuel station data.",
        },
        {
            "name": "Health",
            "description": "Service health and readiness checks.",
        },
    ],
    "COMPONENT_SPLIT_REQUEST": True,
}

# =============================================================================
# CACHING
# =============================================================================
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "fuel-route-optimizer",
        "TIMEOUT": 3600,  # 1 hour default
    }
}

# =============================================================================
# LOGGING
# =============================================================================
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {asctime} {module} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
    },
    "loggers": {
        "apps.route_optimizer": {
            "handlers": ["console"],
            "level": config("LOG_LEVEL", default="INFO"),
            "propagate": True,
        },
    },
}

# =============================================================================
# APPLICATION-SPECIFIC SETTINGS
# =============================================================================
# Vehicle parameters
VEHICLE_MAX_RANGE_MILES = config("VEHICLE_MAX_RANGE", default=500, cast=int)
VEHICLE_MPG = config("VEHICLE_MPG", default=10, cast=int)

# Fuel station search parameters
FUEL_SEARCH_CORRIDOR_MILES = config("FUEL_SEARCH_CORRIDOR", default=25, cast=float)

# External API configuration
OSRM_BASE_URL = config(
    "OSRM_BASE_URL",
    default="https://router.project-osrm.org",
)
NOMINATIM_BASE_URL = config(
    "NOMINATIM_BASE_URL",
    default="https://nominatim.openstreetmap.org",
)
NOMINATIM_USER_AGENT = config(
    "NOMINATIM_USER_AGENT",
    default="FuelRouteOptimizer/1.0",
)

# Path to the fuel prices CSV data
FUEL_DATA_CSV_PATH = config(
    "FUEL_DATA_CSV_PATH",
    default=str(BASE_DIR / "data" / "fuel-prices-for-be-assessment.csv"),
)
