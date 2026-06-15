"""
API views for the Route Optimizer.

Follows the thin-view / thick-service pattern — views handle HTTP concerns
(validation, serialization, status codes) while delegating business logic
to service classes.
"""

import logging
import time
from dataclasses import asdict

from django.conf import settings
from drf_spectacular.utils import extend_schema, OpenApiExample, OpenApiResponse
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.route_optimizer.models import FuelStation
from apps.route_optimizer.services.fuel_optimizer import FuelOptimizationService
from apps.route_optimizer.services.geocoding import GeocodingError, GeocodingService
from apps.route_optimizer.services.routing import RoutingError, RoutingService

from .serializers import (
    FuelStationQuerySerializer,
    FuelStationResponseSerializer,
    FuelStopSerializer,
    RouteRequestSerializer,
    RouteResponseSerializer,
)

logger = logging.getLogger(__name__)


class RouteOptimizeView(APIView):
    """
    Compute the optimal fuel stops along a route.

    Accepts start and finish locations, returns the route geometry,
    cost-effective fuel stops, and total expenditure breakdown.
    """

    @extend_schema(
        tags=["Route Optimization"],
        summary="Optimize fuel stops along a route",
        description=(
            "Given a start and finish location within the USA, computes the "
            "driving route and identifies the most cost-effective fuel stations "
            "along the way. The vehicle is assumed to have a maximum range of "
            "500 miles and achieves 10 miles per gallon.\n\n"
            "**How it works:**\n"
            "1. Geocodes start/finish locations to coordinates\n"
            "2. Computes the driving route via OSRM (single API call)\n"
            "3. Runs the fuel optimization algorithm on the route geometry\n"
            "4. Returns fuel stops ranked by price with cost breakdown\n\n"
            "**Response includes:**\n"
            "- Route summary (distance, duration, total fuel cost)\n"
            "- Ordered list of recommended fuel stops\n"
            "- GeoJSON route geometry for map rendering\n"
            "- Resolved origin/destination coordinates"
        ),
        request=RouteRequestSerializer,
        responses={
            200: OpenApiResponse(
                response=RouteResponseSerializer,
                description="Successfully computed optimal fuel route.",
            ),
            400: OpenApiResponse(description="Invalid input parameters."),
            422: OpenApiResponse(description="Could not geocode or route the given locations."),
            503: OpenApiResponse(description="External service (OSRM/Nominatim) unavailable."),
        },
        examples=[
            OpenApiExample(
                name="Cross-country route",
                value={
                    "start": "New York, NY",
                    "finish": "Los Angeles, CA",
                },
                request_only=True,
            ),
            OpenApiExample(
                name="Regional route",
                value={
                    "start": "Houston, TX",
                    "finish": "Dallas, TX",
                },
                request_only=True,
            ),
        ],
    )
    def post(self, request):
        """
        Handle POST request for route optimization.

        Flow:
        1. Validate input
        2. Geocode locations (2 Nominatim calls, cached)
        3. Compute route (1 OSRM call, cached)
        4. Run fuel optimization (DB queries only)
        5. Format and return response
        """
        start_time = time.time()

        # 1. Validate input
        serializer = RouteRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        start_location = serializer.validated_data["start"]
        finish_location = serializer.validated_data["finish"]

        # 2. Geocode locations
        geocoder = GeocodingService()
        try:
            origin = geocoder.geocode(start_location)
            destination = geocoder.geocode(finish_location)
        except GeocodingError as exc:
            return Response(
                {
                    "error": True,
                    "code": "GEOCODING_ERROR",
                    "message": str(exc),
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        # 3. Compute route (single OSRM API call)
        router = RoutingService()
        try:
            route = router.get_route(
                origin.latitude,
                origin.longitude,
                destination.latitude,
                destination.longitude,
            )
        except RoutingError as exc:
            return Response(
                {
                    "error": True,
                    "code": "ROUTING_ERROR",
                    "message": str(exc),
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        # 4. Run fuel optimization
        optimizer = FuelOptimizationService()
        result = optimizer.optimize(
            route_geometry=route.geometry_coordinates,
            total_distance_miles=route.distance_miles,
            total_duration_seconds=route.duration_seconds,
            origin_name=origin.display_name,
            destination_name=destination.display_name,
            origin_coords=(origin.latitude, origin.longitude),
            dest_coords=(destination.latitude, destination.longitude),
        )

        # 5. Format response
        response_data = {
            "summary": {
                "total_distance_miles": result.total_distance_miles,
                "total_duration_hours": round(result.total_duration_seconds / 3600, 2),
                "total_fuel_gallons": result.total_fuel_gallons,
                "total_fuel_cost": result.total_fuel_cost,
                "number_of_stops": len(result.fuel_stops),
                "vehicle_range_miles": result.vehicle_range_miles,
                "vehicle_mpg": result.vehicle_mpg,
            },
            "origin": {
                "name": origin.display_name,
                "latitude": origin.latitude,
                "longitude": origin.longitude,
            },
            "destination": {
                "name": destination.display_name,
                "latitude": destination.latitude,
                "longitude": destination.longitude,
            },
            "fuel_stops": [asdict(stop) for stop in result.fuel_stops],
            "route": {
                "type": "LineString",
                "coordinates": [
                    [coord[0], coord[1]]
                    for coord in result.route_geometry
                ],
            },
        }

        elapsed = round(time.time() - start_time, 3)
        logger.info("Route optimization completed in %.3fs", elapsed)

        response = Response(response_data, status=status.HTTP_200_OK)
        response["X-Processing-Time"] = f"{elapsed}s"
        return response


class FuelStationListView(APIView):
    """
    List fuel stations with optional filtering.

    Supports filtering by state, price range, and pagination.
    Useful for exploring the dataset.
    """

    @extend_schema(
        tags=["Fuel Stations"],
        summary="List fuel stations",
        description=(
            "Returns fuel stations from the dataset with optional filters. "
            "Results are ordered by retail price (ascending)."
        ),
        parameters=[FuelStationQuerySerializer],
        responses={
            200: OpenApiResponse(
                response=FuelStationResponseSerializer(many=True),
                description="List of fuel stations.",
            ),
        },
    )
    def get(self, request):
        """List fuel stations with optional query filters."""
        query_serializer = FuelStationQuerySerializer(data=request.query_params)
        query_serializer.is_valid(raise_exception=True)
        params = query_serializer.validated_data

        queryset = FuelStation.objects.filter(
            latitude__isnull=False,
            longitude__isnull=False,
        ).order_by("retail_price")

        if "state" in params and params["state"]:
            queryset = queryset.filter(state__iexact=params["state"])
        if "min_price" in params and params["min_price"] is not None:
            queryset = queryset.filter(retail_price__gte=params["min_price"])
        if "max_price" in params and params["max_price"] is not None:
            queryset = queryset.filter(retail_price__lte=params["max_price"])

        limit = params.get("limit", 50)
        stations = queryset[:limit]

        data = [
            {
                "id": s.id,
                "opis_id": s.opis_id,
                "name": s.name,
                "address": s.address,
                "city": s.city,
                "state": s.state,
                "retail_price": s.retail_price,
                "latitude": s.latitude,
                "longitude": s.longitude,
            }
            for s in stations
        ]

        return Response(
            {
                "count": len(data),
                "total_in_database": FuelStation.objects.count(),
                "results": data,
            }
        )


class HealthCheckView(APIView):
    """
    Service health check endpoint.

    Returns the health status and basic statistics about the loaded data.
    """

    @extend_schema(
        tags=["Health"],
        summary="Health check",
        description="Returns service health status and data statistics.",
        responses={
            200: OpenApiResponse(
                description="Service is healthy.",
            ),
        },
    )
    def get(self, request):
        """Return health status."""
        station_count = FuelStation.objects.count()
        geocoded_count = FuelStation.objects.filter(
            latitude__isnull=False
        ).count()

        return Response(
            {
                "status": "healthy",
                "version": "1.0.0",
                "data": {
                    "total_stations": station_count,
                    "geocoded_stations": geocoded_count,
                    "coverage_percent": (
                        round(geocoded_count / station_count * 100, 1)
                        if station_count > 0
                        else 0
                    ),
                },
                "config": {
                    "vehicle_range_miles": getattr(
                        settings, "VEHICLE_MAX_RANGE_MILES", 500
                    ),
                    "vehicle_mpg": getattr(settings, "VEHICLE_MPG", 10),
                    "search_corridor_miles": getattr(
                        settings, "FUEL_SEARCH_CORRIDOR_MILES", 25
                    ),
                },
            }
        )
