"""
Models for the Route Optimizer application.

Stores fuel station data with geographic coordinates for efficient
corridor-based lookups during route optimization.
"""

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator


class FuelStation(models.Model):
    """
    Represents a truck-stop / fuel station with its location and retail price.

    The latitude and longitude are geocoded from the address data during the
    data loading phase (management command). Indexed for fast range queries.
    """

    opis_id = models.IntegerField(
        db_index=True,
        help_text="OPIS Truckstop ID from the source dataset.",
    )
    name = models.CharField(
        max_length=255,
        help_text="Commercial name of the truckstop.",
    )
    address = models.CharField(
        max_length=500,
        help_text="Street address / highway exit info.",
    )
    city = models.CharField(
        max_length=100,
        help_text="City where the station is located.",
    )
    state = models.CharField(
        max_length=2,
        db_index=True,
        help_text="Two-letter US state abbreviation.",
    )
    rack_id = models.IntegerField(
        help_text="Rack pricing region identifier.",
    )
    retail_price = models.FloatField(
        validators=[MinValueValidator(0.0)],
        help_text="Retail price per gallon in USD.",
    )
    latitude = models.FloatField(
        null=True,
        blank=True,
        db_index=True,
        validators=[MinValueValidator(-90.0), MaxValueValidator(90.0)],
        help_text="Geographic latitude (WGS84).",
    )
    longitude = models.FloatField(
        null=True,
        blank=True,
        db_index=True,
        validators=[MinValueValidator(-180.0), MaxValueValidator(180.0)],
        help_text="Geographic longitude (WGS84).",
    )

    class Meta:
        ordering = ["retail_price"]
        verbose_name = "Fuel Station"
        verbose_name_plural = "Fuel Stations"
        indexes = [
            models.Index(
                fields=["latitude", "longitude"],
                name="idx_station_coords",
            ),
            models.Index(
                fields=["state", "retail_price"],
                name="idx_state_price",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.city}, {self.state}) - ${self.retail_price:.3f}/gal"
