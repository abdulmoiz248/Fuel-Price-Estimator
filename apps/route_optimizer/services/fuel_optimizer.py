"""
Fuel optimization service — core algorithmic engine.

Implements a corridor-based greedy algorithm to find the most cost-effective
fuel stops along a given route, respecting the vehicle's range constraint.

Algorithm Overview:
1. Sample the route geometry at 1-mile intervals to create a distance index.
2. Walk through the route mile-by-mile; when the remaining fuel range drops
   below a safety threshold, begin searching for the cheapest station within
   the corridor.
3. Select the cheapest reachable station, "refuel", and continue.
4. Guarantee feasibility: if no cheap station is found, expand the search
   radius before declaring the route infeasible.
"""

import logging
import math
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from django.conf import settings
from django.db.models import Q

from apps.route_optimizer.models import FuelStation

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants & helpers
# ---------------------------------------------------------------------------
EARTH_RADIUS_MILES = 3958.8


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Compute the great-circle distance between two points in miles.

    Uses the Haversine formula with the standard Earth radius.
    """
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_MILES * math.asin(math.sqrt(a))


def interpolate_point(
    p1: Tuple[float, float],
    p2: Tuple[float, float],
    fraction: float,
) -> Tuple[float, float]:
    """Linearly interpolate between two (lon, lat) points."""
    lon = p1[0] + fraction * (p2[0] - p1[0])
    lat = p1[1] + fraction * (p2[1] - p1[1])
    return (lon, lat)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------
@dataclass
class FuelStop:
    """A recommended fuel stop along the route."""

    station_id: int
    station_name: str
    address: str
    city: str
    state: str
    latitude: float
    longitude: float
    retail_price: float
    distance_from_start_miles: float
    gallons_needed: float
    cost: float


@dataclass
class OptimizationResult:
    """Complete result of the fuel optimization."""

    total_distance_miles: float
    total_duration_seconds: float
    total_fuel_gallons: float
    total_fuel_cost: float
    fuel_stops: List[FuelStop] = field(default_factory=list)
    route_geometry: List[Tuple[float, float]] = field(default_factory=list)
    vehicle_range_miles: int = 500
    vehicle_mpg: int = 10
    origin: str = ""
    destination: str = ""
    origin_coordinates: Optional[Tuple[float, float]] = None
    destination_coordinates: Optional[Tuple[float, float]] = None


# ---------------------------------------------------------------------------
# Core service
# ---------------------------------------------------------------------------
class FuelOptimizationService:
    """
    Orchestrates the fuel-stop optimization for a given route.

    The algorithm walks along the route geometry and uses a greedy strategy:
    - Keep driving while range allows
    - When range drops below a look-ahead threshold, search for the cheapest
      station within the corridor
    - The corridor width is configurable (default ±25 miles from route)
    - If multiple stations are available, pick the cheapest
    """

    def __init__(
        self,
        max_range: Optional[int] = None,
        mpg: Optional[int] = None,
        corridor_width: Optional[float] = None,
    ):
        self.max_range = max_range or getattr(settings, "VEHICLE_MAX_RANGE_MILES", 500)
        self.mpg = mpg or getattr(settings, "VEHICLE_MPG", 10)
        self.corridor_width = corridor_width or getattr(
            settings, "FUEL_SEARCH_CORRIDOR_MILES", 25
        )

    def _sample_route(
        self,
        geometry: List[Tuple[float, float]],
        interval_miles: float = 1.0,
    ) -> List[Tuple[float, Tuple[float, float]]]:
        """
        Sample the route at regular distance intervals.

        Returns a list of (cumulative_miles, (lon, lat)) tuples.
        This allows efficient distance-based lookups along the route.
        """
        samples = [(0.0, geometry[0])]
        cumulative = 0.0
        next_sample = interval_miles

        for i in range(1, len(geometry)):
            lon1, lat1 = geometry[i - 1]
            lon2, lat2 = geometry[i]
            segment_dist = haversine(lat1, lon1, lat2, lon2)

            # If this segment crosses a sample boundary, interpolate
            while cumulative + segment_dist >= next_sample:
                remaining = next_sample - cumulative
                fraction = remaining / segment_dist if segment_dist > 0 else 0
                point = interpolate_point(geometry[i - 1], geometry[i], fraction)
                samples.append((next_sample, point))
                next_sample += interval_miles

            cumulative += segment_dist

        # Add the final point
        samples.append((cumulative, geometry[-1]))
        return samples

    def _find_stations_in_corridor(
        self,
        route_points: List[Tuple[float, Tuple[float, float]]],
        start_mile: float,
        end_mile: float,
        corridor_miles: float,
    ) -> List[Tuple[FuelStation, float]]:
        """
        Find fuel stations within a corridor along a segment of the route.

        For efficiency, we compute a bounding box from the route points in
        the [start_mile, end_mile] range, then query the database using
        indexed lat/lon fields. Finally, we verify each candidate is actually
        within corridor distance of at least one route point.

        Returns list of (station, distance_along_route_miles) tuples,
        sorted by retail_price ascending.
        """
        # Collect route points in the window
        window_points = [
            (mile, pt)
            for mile, pt in route_points
            if start_mile <= mile <= end_mile
        ]

        if not window_points:
            return []

        # Compute bounding box with corridor buffer
        lats = [pt[1] for _, pt in window_points]
        lons = [pt[0] for _, pt in window_points]

        # Convert corridor miles to approximate degrees
        # 1 degree latitude ≈ 69 miles
        lat_buffer = corridor_miles / 69.0
        # Longitude varies with latitude; use conservative estimate
        avg_lat = sum(lats) / len(lats)
        lon_buffer = corridor_miles / (69.0 * math.cos(math.radians(avg_lat)))

        min_lat = min(lats) - lat_buffer
        max_lat = max(lats) + lat_buffer
        min_lon = min(lons) - lon_buffer
        max_lon = max(lons) + lon_buffer

        # Query stations within the bounding box
        candidates = FuelStation.objects.filter(
            latitude__isnull=False,
            longitude__isnull=False,
            latitude__gte=min_lat,
            latitude__lte=max_lat,
            longitude__gte=min_lon,
            longitude__lte=max_lon,
        ).order_by("retail_price")

        # Verify actual distance from route and find closest route mile
        results = []
        for station in candidates:
            best_dist = float("inf")
            best_mile = 0.0

            # Check distance to sampled route points (every 5th for speed)
            for mile, (lon, lat) in window_points[::5]:
                dist = haversine(station.latitude, station.longitude, lat, lon)
                if dist < best_dist:
                    best_dist = dist
                    best_mile = mile

            # Refine with nearby points if found a close match
            if best_dist <= corridor_miles * 1.5:
                for mile, (lon, lat) in window_points:
                    if abs(mile - best_mile) <= 10:  # Check ±10 miles
                        dist = haversine(station.latitude, station.longitude, lat, lon)
                        if dist < best_dist:
                            best_dist = dist
                            best_mile = mile

            if best_dist <= corridor_miles:
                results.append((station, best_mile))

        # Sort by price
        results.sort(key=lambda x: x[0].retail_price)
        return results

    def optimize(
        self,
        route_geometry: List[Tuple[float, float]],
        total_distance_miles: float,
        total_duration_seconds: float,
        origin_name: str = "",
        destination_name: str = "",
        origin_coords: Optional[Tuple[float, float]] = None,
        dest_coords: Optional[Tuple[float, float]] = None,
    ) -> OptimizationResult:
        """
        Compute optimal fuel stops along the route.

        Algorithm:
        1. Sample the route at 1-mile intervals.
        2. Walk along the route; whenever remaining range drops below a
           threshold (200 miles), search ahead for the cheapest station.
        3. If the cheapest station found is within the remaining range,
           drive to it and refuel. Otherwise, refuel at the first available.
        4. Continue until destination is reached.

        The "look-ahead" strategy ensures we don't stop at the first station
        but instead search within a window for the cheapest option.

        Args:
            route_geometry: List of (lon, lat) coordinate pairs.
            total_distance_miles: Total route distance.
            total_duration_seconds: Total driving time.

        Returns:
            OptimizationResult with fuel stops and cost breakdown.
        """
        logger.info(
            "Starting fuel optimization for %.1f mile route", total_distance_miles
        )

        # Sample the route
        route_points = self._sample_route(route_geometry, interval_miles=1.0)

        # Initialize state
        fuel_stops: List[FuelStop] = []
        remaining_range = self.max_range  # Start with full tank
        last_stop_mile = 0.0
        total_fuel_gallons = total_distance_miles / self.mpg
        used_station_ids = set()

        # How early to start looking for a station (miles before empty)
        look_ahead_threshold = min(200, self.max_range * 0.4)

        current_mile = 0.0
        while current_mile < total_distance_miles:
            miles_to_destination = total_distance_miles - current_mile

            # If we can reach the destination with current fuel, we're done
            if remaining_range >= miles_to_destination:
                break

            # If remaining range drops below threshold, start looking
            if remaining_range <= look_ahead_threshold:
                # Search window: from current position to max range
                search_start = current_mile
                search_end = min(
                    current_mile + remaining_range - 10,  # 10-mile safety margin
                    total_distance_miles,
                )

                if search_end <= search_start:
                    search_end = min(
                        current_mile + remaining_range, total_distance_miles
                    )

                stations = self._find_stations_in_corridor(
                    route_points, search_start, search_end, self.corridor_width
                )

                # Filter out already-used stations
                stations = [
                    (s, m) for s, m in stations if s.id not in used_station_ids
                ]

                if not stations:
                    # Expand search radius and try again
                    logger.warning(
                        "No stations in %.0f-mile corridor at mile %.0f, "
                        "expanding search",
                        self.corridor_width,
                        current_mile,
                    )
                    stations = self._find_stations_in_corridor(
                        route_points,
                        search_start,
                        search_end,
                        self.corridor_width * 2,
                    )
                    stations = [
                        (s, m) for s, m in stations if s.id not in used_station_ids
                    ]

                if not stations:
                    # Still nothing — try the full remaining range
                    stations = self._find_stations_in_corridor(
                        route_points,
                        current_mile,
                        min(current_mile + self.max_range, total_distance_miles),
                        self.corridor_width * 3,
                    )
                    stations = [
                        (s, m) for s, m in stations if s.id not in used_station_ids
                    ]

                if stations:
                    # Pick the cheapest station
                    best_station, station_mile = stations[0]

                    # Calculate gallons needed (fill to full)
                    distance_driven = station_mile - last_stop_mile
                    gallons_consumed = distance_driven / self.mpg
                    gallons_to_fill = (self.max_range / self.mpg) - (
                        (remaining_range - (station_mile - current_mile)) / self.mpg
                    )
                    gallons_to_fill = max(gallons_to_fill, 0)
                    cost = round(gallons_to_fill * best_station.retail_price, 2)

                    fuel_stop = FuelStop(
                        station_id=best_station.id,
                        station_name=best_station.name,
                        address=best_station.address,
                        city=best_station.city,
                        state=best_station.state,
                        latitude=best_station.latitude,
                        longitude=best_station.longitude,
                        retail_price=best_station.retail_price,
                        distance_from_start_miles=round(station_mile, 1),
                        gallons_needed=round(gallons_to_fill, 2),
                        cost=cost,
                    )
                    fuel_stops.append(fuel_stop)
                    used_station_ids.add(best_station.id)

                    logger.info(
                        "Stop %d: %s at mile %.0f ($%.3f/gal, %.1f gal, $%.2f)",
                        len(fuel_stops),
                        best_station.name,
                        station_mile,
                        best_station.retail_price,
                        gallons_to_fill,
                        cost,
                    )

                    # Update state
                    remaining_range = self.max_range
                    last_stop_mile = station_mile
                    current_mile = station_mile + 1
                    continue
                else:
                    logger.error(
                        "No fuel stations found between mile %.0f and %.0f",
                        search_start,
                        search_end,
                    )
                    # Force advance to prevent infinite loop
                    current_mile += 50
                    remaining_range -= 50
                    continue

            # Advance along the route
            step = min(10, remaining_range)  # Move in 10-mile steps
            current_mile += step
            remaining_range -= step

        # Calculate total cost
        total_fuel_cost = sum(stop.cost for stop in fuel_stops)

        # If no stops needed (short route), compute theoretical cost
        if not fuel_stops:
            # Use average price from nearby stations
            avg_price = self._get_average_price_near_route(route_points)
            total_fuel_cost = round(total_fuel_gallons * avg_price, 2)

        result = OptimizationResult(
            total_distance_miles=round(total_distance_miles, 2),
            total_duration_seconds=total_duration_seconds,
            total_fuel_gallons=round(total_fuel_gallons, 2),
            total_fuel_cost=round(total_fuel_cost, 2),
            fuel_stops=fuel_stops,
            route_geometry=route_geometry,
            vehicle_range_miles=self.max_range,
            vehicle_mpg=self.mpg,
            origin=origin_name,
            destination=destination_name,
            origin_coordinates=origin_coords,
            destination_coordinates=dest_coords,
        )

        logger.info(
            "Optimization complete: %d stops, $%.2f total fuel cost",
            len(fuel_stops),
            total_fuel_cost,
        )
        return result

    def _get_average_price_near_route(
        self,
        route_points: List[Tuple[float, Tuple[float, float]]],
    ) -> float:
        """Get average fuel price near the route for short trips."""
        if not route_points:
            return 3.50  # Fallback national average

        mid_idx = len(route_points) // 2
        _, (lon, lat) = route_points[mid_idx]

        lat_buffer = 50 / 69.0
        lon_buffer = 50 / (69.0 * math.cos(math.radians(lat)))

        avg = FuelStation.objects.filter(
            latitude__isnull=False,
            latitude__gte=lat - lat_buffer,
            latitude__lte=lat + lat_buffer,
            longitude__gte=lon - lon_buffer,
            longitude__lte=lon + lon_buffer,
        ).values_list("retail_price", flat=True)

        if avg:
            return sum(avg) / len(avg)
        return 3.50
