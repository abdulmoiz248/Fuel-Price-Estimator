"""
Tests for the Route Optimizer API views.
"""

from unittest.mock import patch, MagicMock

from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.route_optimizer.models import FuelStation


class HealthCheckViewTests(TestCase):
    """Test the health check endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.url = reverse("route_optimizer:health-check")

    def test_health_check_returns_200(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "healthy")

    def test_health_check_includes_data_stats(self):
        FuelStation.objects.create(
            opis_id=1, name="Test", address="Test",
            city="Test", state="TX", rack_id=100,
            retail_price=3.0, latitude=32.0, longitude=-97.0,
        )
        response = self.client.get(self.url)
        self.assertEqual(response.data["data"]["total_stations"], 1)
        self.assertEqual(response.data["data"]["geocoded_stations"], 1)


class FuelStationListViewTests(TestCase):
    """Test the fuel station listing endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.url = reverse("route_optimizer:station-list")

        # Create test stations
        for i in range(5):
            FuelStation.objects.create(
                opis_id=i,
                name=f"Station {i}",
                address=f"Exit {i}",
                city=f"City {i}",
                state="TX" if i < 3 else "CA",
                rack_id=100,
                retail_price=2.50 + (i * 0.25),
                latitude=32.0 + i,
                longitude=-97.0 + i,
            )

    def test_list_all_stations(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 5)

    def test_filter_by_state(self):
        response = self.client.get(self.url, {"state": "TX"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 3)

    def test_filter_by_price_range(self):
        response = self.client.get(self.url, {"min_price": 3.0, "max_price": 3.5})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for station in response.data["results"]:
            self.assertGreaterEqual(station["retail_price"], 3.0)
            self.assertLessEqual(station["retail_price"], 3.5)

    def test_limit_parameter(self):
        response = self.client.get(self.url, {"limit": 2})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)

    def test_results_ordered_by_price(self):
        response = self.client.get(self.url)
        prices = [s["retail_price"] for s in response.data["results"]]
        self.assertEqual(prices, sorted(prices))


class RouteOptimizeViewTests(TestCase):
    """Test the route optimization endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.url = reverse("route_optimizer:route-optimize")

    def test_missing_fields_returns_400(self):
        response = self.client.post(self.url, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_same_start_finish_returns_400(self):
        response = self.client.post(
            self.url,
            {"start": "Dallas, TX", "finish": "Dallas, TX"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_get_method_not_allowed(self):
        response = self.client.get(self.url)
        self.assertEqual(
            response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED
        )
