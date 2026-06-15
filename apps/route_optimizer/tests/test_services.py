"""
Tests for the Route Optimizer services.
"""

import math
from unittest.mock import patch, MagicMock

from django.test import TestCase

from apps.route_optimizer.services.fuel_optimizer import (
    FuelOptimizationService,
    haversine,
)
from apps.route_optimizer.services.geocoding import GeocodingService, GeocodingResult
from apps.route_optimizer.services.routing import RoutingService, RouteResult
from apps.route_optimizer.models import FuelStation


class HaversineTests(TestCase):
    """Test the Haversine distance calculation."""

    def test_zero_distance(self):
        """Same point should return 0."""
        dist = haversine(40.0, -74.0, 40.0, -74.0)
        self.assertAlmostEqual(dist, 0.0, places=5)

    def test_known_distance(self):
        """NYC to LA should be approximately 2451 miles (great circle)."""
        dist = haversine(40.7128, -74.0060, 34.0522, -118.2437)
        self.assertAlmostEqual(dist, 2451, delta=50)

    def test_short_distance(self):
        """Short distance should be positive."""
        dist = haversine(40.7128, -74.0060, 40.7580, -73.9855)
        self.assertGreater(dist, 0)
        self.assertLess(dist, 10)  # Within Manhattan


class FuelOptimizationServiceTests(TestCase):
    """Test the fuel optimization algorithm."""

    def setUp(self):
        """Create test fuel stations."""
        # Create stations along a hypothetical east-west route
        self.stations = []
        for i in range(10):
            station = FuelStation.objects.create(
                opis_id=1000 + i,
                name=f"Test Station {i}",
                address=f"Highway Exit {i}",
                city=f"City {i}",
                state="TX",
                rack_id=100,
                retail_price=2.50 + (i * 0.1),
                latitude=32.0 + (i * 0.01),  # Slight lat variation
                longitude=-100.0 + (i * 1.0),  # Spread along longitude
            )
            self.stations.append(station)

    def test_short_route_no_stops(self):
        """A route shorter than max range should need no stops."""
        optimizer = FuelOptimizationService(max_range=500, mpg=10)

        # 100-mile route geometry (roughly)
        geometry = [
            (-100.0, 32.0),
            (-99.0, 32.0),  # ~60 miles
        ]

        result = optimizer.optimize(
            route_geometry=geometry,
            total_distance_miles=60.0,
            total_duration_seconds=3600,
        )

        self.assertEqual(len(result.fuel_stops), 0)
        self.assertEqual(result.total_fuel_gallons, 6.0)

    def test_fuel_gallons_calculation(self):
        """Total fuel should be distance / mpg."""
        optimizer = FuelOptimizationService(max_range=500, mpg=10)

        result = optimizer.optimize(
            route_geometry=[(-100.0, 32.0), (-99.0, 32.0)],
            total_distance_miles=1000.0,
            total_duration_seconds=36000,
        )

        self.assertEqual(result.total_fuel_gallons, 100.0)

    def test_service_initialization(self):
        """Service should accept custom parameters."""
        optimizer = FuelOptimizationService(
            max_range=400, mpg=15, corridor_width=30
        )
        self.assertEqual(optimizer.max_range, 400)
        self.assertEqual(optimizer.mpg, 15)
        self.assertEqual(optimizer.corridor_width, 30)


class GeocodingServiceTests(TestCase):
    """Test the geocoding service."""

    @patch("apps.route_optimizer.services.geocoding.requests.Session")
    def test_geocode_success(self, mock_session_class):
        """Successful geocoding should return coordinates."""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session

        mock_response = MagicMock()
        mock_response.json.return_value = [
            {
                "lat": "40.7128",
                "lon": "-74.0060",
                "display_name": "New York, NY, USA",
            }
        ]
        mock_response.raise_for_status = MagicMock()
        mock_session.get.return_value = mock_response

        service = GeocodingService()
        result = service.geocode("New York, NY")

        self.assertIsInstance(result, GeocodingResult)
        self.assertAlmostEqual(result.latitude, 40.7128)
        self.assertAlmostEqual(result.longitude, -74.0060)


class RoutingServiceTests(TestCase):
    """Test the routing service."""

    @patch("apps.route_optimizer.services.routing.requests.Session")
    def test_route_success(self, mock_session_class):
        """Successful routing should return route data."""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "code": "Ok",
            "routes": [
                {
                    "distance": 100000,  # 100km
                    "duration": 3600,
                    "geometry": {
                        "coordinates": [
                            [-74.006, 40.7128],
                            [-118.2437, 34.0522],
                        ]
                    },
                }
            ],
        }
        mock_response.raise_for_status = MagicMock()
        mock_session.get.return_value = mock_response

        service = RoutingService()
        result = service.get_route(40.7128, -74.006, 34.0522, -118.2437)

        self.assertIsInstance(result, RouteResult)
        self.assertGreater(result.distance_miles, 0)
        self.assertEqual(len(result.geometry_coordinates), 2)
