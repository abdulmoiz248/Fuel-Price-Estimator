"""
Custom exception handler for consistent API error responses.

Wraps DRF's default exception handler to provide a uniform error envelope.
"""

import logging

from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """
    Custom exception handler that wraps all errors in a consistent format:

    {
        "error": true,
        "code": "<ERROR_CODE>",
        "message": "Human-readable description",
        "details": { ... }  // optional
    }
    """
    response = exception_handler(exc, context)

    if response is not None:
        error_data = {
            "error": True,
            "code": _get_error_code(response.status_code),
            "message": _extract_message(response.data),
            "details": response.data if isinstance(response.data, dict) else None,
        }
        response.data = error_data
    else:
        # Unhandled exception
        logger.exception("Unhandled exception: %s", exc)
        response = Response(
            {
                "error": True,
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred. Please try again.",
                "details": None,
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    return response


def _get_error_code(status_code: int) -> str:
    """Map HTTP status code to an error code string."""
    code_map = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        405: "METHOD_NOT_ALLOWED",
        429: "RATE_LIMIT_EXCEEDED",
        500: "INTERNAL_SERVER_ERROR",
        502: "BAD_GATEWAY",
        503: "SERVICE_UNAVAILABLE",
    }
    return code_map.get(status_code, f"HTTP_{status_code}")


def _extract_message(data) -> str:
    """Extract a human-readable message from DRF error data."""
    if isinstance(data, str):
        return data
    if isinstance(data, list):
        return "; ".join(str(item) for item in data)
    if isinstance(data, dict):
        messages = []
        for key, value in data.items():
            if key == "detail":
                return str(value)
            if isinstance(value, list):
                messages.append(f"{key}: {'; '.join(str(v) for v in value)}")
            else:
                messages.append(f"{key}: {value}")
        return "; ".join(messages) if messages else "Validation error"
    return str(data)
