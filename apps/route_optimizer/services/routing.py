"""
Routing service using OSRM (Open Source Routing Machine).

Provides route computation between two geographic coordinates.
Returns the full route geometry, distance, and duration in a single API call.
"""

import logging
from dataclasses import dataclass, field
from typing import List, Tuple

import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RouteResult:
    """Immutable result from a routing computation."""

    distance_miles: float
    duration_seconds: float
    geometry_coordinates: List[Tuple[float, float]]  # [(lon, lat), ...]
    waypoints: List[dict] = field(default_factory=list)


class RoutingError(Exception):
    """Raised when routing computation fails."""

    pass


class RoutingService:
    """
    Routing service backed by OSRM (Open Source Routing Machine).

    Uses a single API call to get the full route with geometry.
    The geometry is returned as a list of (longitude, latitude) pairs
    which can be sampled for fuel station lookups.

    Features:
    - Single API call for full route (meets the "1 call ideal" requirement)
    - Result caching
    - GeoJSON-compatible coordinate output
    """

    CACHE_TTL = 1800  # 30 minutes
    CACHE_PREFIX = "route:"
    METERS_TO_MILES = 0.000621371

    def __init__(self):
        self.base_url = getattr(
            settings, "OSRM_BASE_URL", "https://router.project-osrm.org"
        )
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "FuelRouteOptimizer/1.0",
        })

    def get_route(
        self,
        origin_lat: float,
        origin_lon: float,
        dest_lat: float,
        dest_lon: float,
    ) -> RouteResult:
        """
        Compute a driving route between two points.

        Uses OSRM's route service with full geometry overview to get
        a detailed polyline in a single API call.

        Args:
            origin_lat: Origin latitude
            origin_lon: Origin longitude
            dest_lat: Destination latitude
            dest_lon: Destination longitude

        Returns:
            RouteResult with distance, duration, and route geometry.

        Raises:
            RoutingError: If the route cannot be computed or the API fails.
        """
        cache_key = (
            f"{self.CACHE_PREFIX}"
            f"{origin_lat:.4f},{origin_lon:.4f}-"
            f"{dest_lat:.4f},{dest_lon:.4f}"
        )
        cached = cache.get(cache_key)
        if cached is not None:
            logger.debug("Cache hit for route")
            return RouteResult(**cached)

        # OSRM expects coordinates as lon,lat
        coordinates = f"{origin_lon},{origin_lat};{dest_lon},{dest_lat}"
        url = f"{self.base_url}/route/v1/driving/{coordinates}"

        try:
            response = self.session.get(
                url,
                params={
                    "overview": "full",
                    "geometries": "geojson",
                    "steps": "false",
                },
                timeout=15,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            logger.error("OSRM routing error: %s", exc)
            raise RoutingError(f"Failed to compute route: {exc}") from exc

        data = response.json()

        if data.get("code") != "Ok":
            msg = data.get("message", "Unknown routing error")
            raise RoutingError(f"OSRM returned error: {msg}")

        if not data.get("routes"):
            raise RoutingError("No route found between the given locations.")

        route = data["routes"][0]
        geometry_coords = route["geometry"]["coordinates"]  # [[lon, lat], ...]

        # Convert to list of tuples
        coords = [(coord[0], coord[1]) for coord in geometry_coords]

        distance_miles = route["distance"] * self.METERS_TO_MILES
        duration_seconds = route["duration"]

        result = RouteResult(
            distance_miles=round(distance_miles, 2),
            duration_seconds=round(duration_seconds, 0),
            geometry_coordinates=coords,
        )

        # Cache the result
        cache.set(
            cache_key,
            {
                "distance_miles": result.distance_miles,
                "duration_seconds": result.duration_seconds,
                "geometry_coordinates": result.geometry_coordinates,
            },
            self.CACHE_TTL,
        )

        logger.info(
            "Computed route: %.1f miles, %.0f seconds",
            result.distance_miles,
            result.duration_seconds,
        )
        return result
