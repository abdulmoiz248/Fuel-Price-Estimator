"""
Tests for the Route Optimizer API serializers.
"""

from django.test import TestCase

from apps.route_optimizer.api.serializers import (
    RouteRequestSerializer,
    FuelStationQuerySerializer,
)


class RouteRequestSerializerTests(TestCase):
    """Test input validation for route optimization requests."""

    def test_valid_input(self):
        data = {"start": "New York, NY", "finish": "Los Angeles, CA"}
        serializer = RouteRequestSerializer(data=data)
        self.assertTrue(serializer.is_valid())

    def test_missing_start(self):
        data = {"finish": "Los Angeles, CA"}
        serializer = RouteRequestSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("start", serializer.errors)

    def test_missing_finish(self):
        data = {"start": "New York, NY"}
        serializer = RouteRequestSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("finish", serializer.errors)

    def test_same_start_and_finish(self):
        data = {"start": "New York, NY", "finish": "New York, NY"}
        serializer = RouteRequestSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("non_field_errors", serializer.errors)

    def test_too_short_location(self):
        data = {"start": "A", "finish": "Los Angeles, CA"}
        serializer = RouteRequestSerializer(data=data)
        self.assertFalse(serializer.is_valid())

    def test_whitespace_trimming(self):
        data = {"start": "  New York, NY  ", "finish": "  Los Angeles, CA  "}
        serializer = RouteRequestSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["start"], "New York, NY")
        self.assertEqual(serializer.validated_data["finish"], "Los Angeles, CA")


class FuelStationQuerySerializerTests(TestCase):
    """Test query parameter validation for station listing."""

    def test_empty_params(self):
        serializer = FuelStationQuerySerializer(data={})
        self.assertTrue(serializer.is_valid())

    def test_state_filter(self):
        serializer = FuelStationQuerySerializer(data={"state": "TX"})
        self.assertTrue(serializer.is_valid())

    def test_price_range(self):
        serializer = FuelStationQuerySerializer(
            data={"min_price": 2.5, "max_price": 4.0}
        )
        self.assertTrue(serializer.is_valid())

    def test_limit_bounds(self):
        serializer = FuelStationQuerySerializer(data={"limit": 0})
        self.assertFalse(serializer.is_valid())

        serializer = FuelStationQuerySerializer(data={"limit": 501})
        self.assertFalse(serializer.is_valid())

        serializer = FuelStationQuerySerializer(data={"limit": 100})
        self.assertTrue(serializer.is_valid())
