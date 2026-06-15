"""
API serializers for the Route Optimizer.

Defines input validation (request) and output formatting (response)
serializers, using DRF's serializer classes for automatic schema generation.
"""

from rest_framework import serializers


# ===========================================================================
# REQUEST SERIALIZERS
# ===========================================================================
class RouteRequestSerializer(serializers.Serializer):
    """
    Validates the input for a route optimization request.

    Both `start` and `finish` accept free-form location strings
    (e.g. "New York, NY", "Los Angeles, CA", "1600 Pennsylvania Ave, Washington DC").
    """

    start = serializers.CharField(
        max_length=500,
        help_text=(
            "Starting location (city/state, address, or landmark). "
            "Must be within the USA. Example: 'New York, NY'"
        ),
    )
    finish = serializers.CharField(
        max_length=500,
        help_text=(
            "Destination location (city/state, address, or landmark). "
            "Must be within the USA. Example: 'Los Angeles, CA'"
        ),
    )

    def validate_start(self, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise serializers.ValidationError(
                "Start location must be at least 2 characters."
            )
        return value

    def validate_finish(self, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise serializers.ValidationError(
                "Finish location must be at least 2 characters."
            )
        return value

    def validate(self, attrs):
        if attrs["start"].lower() == attrs["finish"].lower():
            raise serializers.ValidationError(
                "Start and finish locations must be different."
            )
        return attrs


# ===========================================================================
# RESPONSE SERIALIZERS
# ===========================================================================
class FuelStopSerializer(serializers.Serializer):
    """Serializes a single fuel stop along the route."""

    station_id = serializers.IntegerField(
        help_text="Internal station ID.",
    )
    station_name = serializers.CharField(
        help_text="Name of the fuel station.",
    )
    address = serializers.CharField(
        help_text="Station address / highway exit info.",
    )
    city = serializers.CharField(
        help_text="City of the station.",
    )
    state = serializers.CharField(
        help_text="Two-letter US state code.",
    )
    latitude = serializers.FloatField(
        help_text="Station latitude (WGS84).",
    )
    longitude = serializers.FloatField(
        help_text="Station longitude (WGS84).",
    )
    retail_price = serializers.FloatField(
        help_text="Fuel price per gallon in USD.",
    )
    distance_from_start_miles = serializers.FloatField(
        help_text="Distance from the route start to this stop in miles.",
    )
    gallons_needed = serializers.FloatField(
        help_text="Gallons of fuel to purchase at this stop.",
    )
    cost = serializers.FloatField(
        help_text="Total cost at this stop in USD.",
    )


class RouteSummarySerializer(serializers.Serializer):
    """High-level summary of the optimized route."""

    total_distance_miles = serializers.FloatField(
        help_text="Total driving distance in miles.",
    )
    total_duration_hours = serializers.FloatField(
        help_text="Estimated driving time in hours.",
    )
    total_fuel_gallons = serializers.FloatField(
        help_text="Total fuel consumption in gallons (at specified MPG).",
    )
    total_fuel_cost = serializers.FloatField(
        help_text="Total fuel expenditure in USD.",
    )
    number_of_stops = serializers.IntegerField(
        help_text="Number of recommended fuel stops.",
    )
    vehicle_range_miles = serializers.IntegerField(
        help_text="Vehicle maximum range on a full tank.",
    )
    vehicle_mpg = serializers.IntegerField(
        help_text="Vehicle fuel efficiency in miles per gallon.",
    )


class RouteEndpointSerializer(serializers.Serializer):
    """Serializes a route endpoint (origin or destination)."""

    name = serializers.CharField(help_text="Location name as resolved by geocoder.")
    latitude = serializers.FloatField(help_text="Latitude.")
    longitude = serializers.FloatField(help_text="Longitude.")


class RouteResponseSerializer(serializers.Serializer):
    """
    Complete response for a route optimization request.

    Includes route summary, fuel stops, route geometry (for map rendering),
    and endpoint details.
    """

    summary = RouteSummarySerializer(
        help_text="High-level route and cost summary.",
    )
    origin = RouteEndpointSerializer(
        help_text="Resolved origin location.",
    )
    destination = RouteEndpointSerializer(
        help_text="Resolved destination location.",
    )
    fuel_stops = FuelStopSerializer(
        many=True,
        help_text="Ordered list of recommended fuel stops (cheapest options along route).",
    )
    route = serializers.DictField(
        help_text=(
            "GeoJSON LineString geometry of the route. "
            "Can be rendered directly on a map."
        ),
    )


# ===========================================================================
# FUEL STATION QUERY SERIALIZER
# ===========================================================================
class FuelStationQuerySerializer(serializers.Serializer):
    """Query parameters for listing fuel stations."""

    state = serializers.CharField(
        max_length=2,
        required=False,
        help_text="Filter by US state code (e.g. 'TX', 'CA').",
    )
    min_price = serializers.FloatField(
        required=False,
        help_text="Minimum retail price filter.",
    )
    max_price = serializers.FloatField(
        required=False,
        help_text="Maximum retail price filter.",
    )
    limit = serializers.IntegerField(
        required=False,
        default=50,
        min_value=1,
        max_value=500,
        help_text="Number of results to return (default: 50, max: 500).",
    )


class FuelStationResponseSerializer(serializers.Serializer):
    """Serializes a fuel station for listing endpoints."""

    id = serializers.IntegerField()
    opis_id = serializers.IntegerField()
    name = serializers.CharField(source="station_name", default="")
    address = serializers.CharField()
    city = serializers.CharField()
    state = serializers.CharField()
    retail_price = serializers.FloatField()
    latitude = serializers.FloatField()
    longitude = serializers.FloatField()
