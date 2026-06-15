"""
Geocoding service using Nominatim (OpenStreetMap).

Provides forward geocoding to resolve place names into lat/lon coordinates.
Implements caching and rate limiting to respect Nominatim's usage policy.
"""

import logging
import time
from dataclasses import dataclass
from typing import Optional

import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GeocodingResult:
    """Immutable result from a geocoding lookup."""

    latitude: float
    longitude: float
    display_name: str


class GeocodingError(Exception):
    """Raised when geocoding fails."""

    pass


class GeocodingService:
    """
    Geocoding service backed by Nominatim (OpenStreetMap).

    Features:
    - Result caching (1 hour TTL) to minimize external API calls
    - Rate limiting (1 request/second per Nominatim policy)
    - USA-biased search for relevant results
    """

    CACHE_TTL = 3600  # 1 hour
    CACHE_PREFIX = "geocode:"
    _last_request_time: float = 0.0

    def __init__(self):
        self.base_url = getattr(
            settings, "NOMINATIM_BASE_URL", "https://nominatim.openstreetmap.org"
        )
        self.user_agent = getattr(
            settings, "NOMINATIM_USER_AGENT", "FuelRouteOptimizer/1.0"
        )
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.user_agent})

    def _rate_limit(self) -> None:
        """Enforce Nominatim's 1 request/second policy."""
        elapsed = time.time() - GeocodingService._last_request_time
        if elapsed < 1.0:
            time.sleep(1.0 - elapsed)
        GeocodingService._last_request_time = time.time()

    def geocode(self, location: str) -> GeocodingResult:
        """
        Resolve a location string to geographic coordinates.

        Args:
            location: Free-form location string (e.g. "New York, NY" or
                      "123 Main St, Springfield, IL").

        Returns:
            GeocodingResult with latitude, longitude, and display name.

        Raises:
            GeocodingError: If the location cannot be resolved or the API
                           call fails.
        """
        cache_key = f"{self.CACHE_PREFIX}{location.lower().strip()}"
        cached = cache.get(cache_key)
        if cached is not None:
            logger.debug("Cache hit for geocoding: %s", location)
            return GeocodingResult(**cached)

        self._rate_limit()

        try:
            response = self.session.get(
                f"{self.base_url}/search",
                params={
                    "q": location,
                    "format": "json",
                    "limit": 1,
                    "countrycodes": "us",
                    "addressdetails": 1,
                },
                timeout=10,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            logger.error("Geocoding API error for '%s': %s", location, exc)
            raise GeocodingError(
                f"Failed to geocode location '{location}': {exc}"
            ) from exc

        data = response.json()
        if not data:
            raise GeocodingError(
                f"No results found for location '{location}'. "
                "Please provide a valid US location."
            )

        result = GeocodingResult(
            latitude=float(data[0]["lat"]),
            longitude=float(data[0]["lon"]),
            display_name=data[0]["display_name"],
        )

        # Cache the result
        cache.set(
            cache_key,
            {
                "latitude": result.latitude,
                "longitude": result.longitude,
                "display_name": result.display_name,
            },
            self.CACHE_TTL,
        )

        logger.info(
            "Geocoded '%s' -> (%.4f, %.4f)", location, result.latitude, result.longitude
        )
        return result

    def geocode_for_station(
        self, city: str, state: str, address: str = ""
    ) -> Optional[GeocodingResult]:
        """
        Geocode a fuel station by its city/state/address.

        Returns None instead of raising on failure (used during bulk data loading).
        """
        location = f"{city}, {state}, USA"
        if address:
            location = f"{address}, {city}, {state}, USA"

        try:
            return self.geocode(location)
        except GeocodingError:
            logger.warning("Could not geocode station at %s", location)
            return None
