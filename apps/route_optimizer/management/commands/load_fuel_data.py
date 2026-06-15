"""
Management command to load fuel station data from CSV.

Geocodes station locations using a state-level centroid approximation
for fast bulk loading (avoids thousands of Nominatim calls). Individual
station coordinates are approximated from city/state centroids with
small random offsets to distribute them geographically.

Usage:
    python manage.py load_fuel_data
    python manage.py load_fuel_data --csv-path /path/to/custom.csv
    python manage.py load_fuel_data --clear  # Clear existing data first
"""

import csv
import logging
import math
import random
from typing import Dict, Tuple

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.route_optimizer.models import FuelStation

logger = logging.getLogger(__name__)

# US state abbreviations that are valid (exclude Canadian provinces)
US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
    "DC",
}

# Approximate centroids for US cities/states for geocoding
# This avoids calling Nominatim for 8000+ stations
# We use state centroids as base, then offset by city hash for distribution
STATE_CENTROIDS: Dict[str, Tuple[float, float]] = {
    "AL": (32.806671, -86.791130),
    "AK": (61.370716, -152.404419),
    "AZ": (33.729759, -111.431221),
    "AR": (34.969704, -92.373123),
    "CA": (36.116203, -119.681564),
    "CO": (39.059811, -105.311104),
    "CT": (41.597782, -72.755371),
    "DE": (39.318523, -75.507141),
    "FL": (27.766279, -81.686783),
    "GA": (33.040619, -83.643074),
    "HI": (21.094318, -157.498337),
    "ID": (44.240459, -114.478828),
    "IL": (40.349457, -88.986137),
    "IN": (39.849426, -86.258278),
    "IA": (42.011539, -93.210526),
    "KS": (38.526600, -96.726486),
    "KY": (37.668140, -84.670067),
    "LA": (31.169546, -91.867805),
    "ME": (44.693947, -69.381927),
    "MD": (39.063946, -76.802101),
    "MA": (42.230171, -71.530106),
    "MI": (43.326618, -84.536095),
    "MN": (45.694454, -93.900192),
    "MS": (32.741646, -89.678696),
    "MO": (38.456085, -92.288368),
    "MT": (46.921925, -110.454353),
    "NE": (41.125370, -98.268082),
    "NV": (38.313515, -117.055374),
    "NH": (43.452492, -71.563896),
    "NJ": (40.298904, -74.521011),
    "NM": (34.840515, -106.248482),
    "NY": (42.165726, -74.948051),
    "NC": (35.630066, -79.806419),
    "ND": (47.528912, -99.784012),
    "OH": (40.388783, -82.764915),
    "OK": (35.565342, -96.928917),
    "OR": (44.572021, -122.070938),
    "PA": (40.590752, -77.209755),
    "RI": (41.680893, -71.511780),
    "SC": (33.856892, -80.945007),
    "SD": (44.299782, -99.438828),
    "TN": (35.747845, -86.692345),
    "TX": (31.054487, -97.563461),
    "UT": (40.150032, -111.862434),
    "VT": (44.045876, -72.710686),
    "VA": (37.769337, -78.169968),
    "WA": (47.400902, -121.490494),
    "WV": (38.491226, -80.954453),
    "WI": (44.268543, -89.616508),
    "WY": (42.755966, -107.302490),
    "DC": (38.907192, -77.036871),
}

# Major city coordinates for more accurate positioning
CITY_COORDS: Dict[str, Tuple[float, float]] = {
    # Major cities - add more as needed for accuracy
    "new york": (40.7128, -74.0060),
    "los angeles": (34.0522, -118.2437),
    "chicago": (41.8781, -87.6298),
    "houston": (29.7604, -95.3698),
    "phoenix": (33.4484, -112.0740),
    "philadelphia": (39.9526, -75.1652),
    "san antonio": (29.4241, -98.4936),
    "san diego": (32.7157, -117.1611),
    "dallas": (32.7767, -96.7970),
    "austin": (30.2672, -97.7431),
    "jacksonville": (30.3322, -81.6557),
    "san francisco": (37.7749, -122.4194),
    "indianapolis": (39.7684, -86.1581),
    "columbus": (39.9612, -82.9988),
    "charlotte": (35.2271, -80.8431),
    "denver": (39.7392, -104.9903),
    "el paso": (31.7619, -106.4850),
    "memphis": (35.1495, -90.0490),
    "nashville": (36.1627, -86.7816),
    "oklahoma city": (35.4676, -97.5164),
    "portland": (45.5152, -122.6784),
    "las vegas": (36.1699, -115.1398),
    "louisville": (38.2527, -85.7585),
    "baltimore": (39.2904, -76.6122),
    "milwaukee": (43.0389, -87.9065),
    "albuquerque": (35.0844, -106.6504),
    "tucson": (32.2226, -110.9747),
    "fresno": (36.7378, -119.7871),
    "mesa": (33.4152, -111.8315),
    "sacramento": (38.5816, -121.4944),
    "atlanta": (33.7490, -84.3880),
    "kansas city": (39.0997, -94.5786),
    "omaha": (41.2565, -95.9345),
    "miami": (25.7617, -80.1918),
    "tulsa": (36.1540, -95.9928),
    "tampa": (27.9506, -82.4572),
    "orlando": (28.5383, -81.3792),
    "st. louis": (38.6270, -90.1994),
    "saint louis": (38.6270, -90.1994),
    "pittsburgh": (40.4406, -79.9959),
    "cincinnati": (39.1031, -84.5120),
    "buffalo": (42.8864, -78.8784),
    "albany": (42.6526, -73.7562),
    "boise": (43.6150, -116.2023),
    "salt lake city": (40.7608, -111.8910),
    "little rock": (34.7465, -92.2896),
    "des moines": (41.5868, -93.6250),
    "richmond": (37.5407, -77.4360),
    "birmingham": (33.5207, -86.8025),
    "spokane": (47.6588, -117.4260),
    "baton rouge": (30.4515, -91.1871),
    "knoxville": (35.9606, -83.9207),
    "chattanooga": (35.0456, -85.3097),
    "fort worth": (32.7555, -97.3308),
    "amarillo": (35.2220, -101.8313),
    "savannah": (32.0809, -81.0912),
    "columbia": (34.0007, -81.0348),
    "shreveport": (32.5252, -93.7502),
    "mobile": (30.6954, -88.0399),
    "reno": (39.5296, -119.8138),
    "laredo": (27.5036, -99.5076),
    "cheyenne": (41.1400, -104.8202),
    "billings": (45.7833, -108.5007),
    "fargo": (46.8772, -96.7898),
}


def _city_to_coords(city: str, state: str) -> Tuple[float, float]:
    """
    Approximate coordinates for a city/state combo.

    Strategy:
    1. Check known city coordinates
    2. Fall back to state centroid + deterministic offset from city name hash
    """
    city_lower = city.lower().strip()

    # Check known cities
    if city_lower in CITY_COORDS:
        lat, lon = CITY_COORDS[city_lower]
        # Small random offset to avoid overlapping stations in same city
        return (
            lat + random.uniform(-0.02, 0.02),
            lon + random.uniform(-0.02, 0.02),
        )

    # Fall back to state centroid with city-name-based offset
    state_upper = state.upper().strip()
    if state_upper in STATE_CENTROIDS:
        base_lat, base_lon = STATE_CENTROIDS[state_upper]
        # Use city name hash for deterministic but distributed offset
        city_hash = hash(city_lower)
        lat_offset = ((city_hash % 1000) / 1000.0 - 0.5) * 4.0  # ±2 degrees
        lon_offset = (((city_hash >> 10) % 1000) / 1000.0 - 0.5) * 6.0  # ±3 degrees
        return (
            base_lat + lat_offset,
            base_lon + lon_offset,
        )

    return (0.0, 0.0)  # Unknown location


class Command(BaseCommand):
    help = "Load fuel station data from CSV file into the database."

    def add_arguments(self, parser):
        parser.add_argument(
            "--csv-path",
            type=str,
            default=None,
            help="Path to the fuel prices CSV file. Defaults to settings.FUEL_DATA_CSV_PATH.",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Clear all existing fuel station data before loading.",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=1000,
            help="Batch size for bulk_create operations (default: 1000).",
        )

    def handle(self, *args, **options):
        csv_path = options["csv_path"] or getattr(
            settings,
            "FUEL_DATA_CSV_PATH",
            str(settings.BASE_DIR / "data" / "fuel-prices-for-be-assessment.csv"),
        )
        batch_size = options["batch_size"]

        if options["clear"]:
            count = FuelStation.objects.count()
            FuelStation.objects.all().delete()
            self.stdout.write(
                self.style.WARNING(f"Cleared {count} existing stations.")
            )

        self.stdout.write(f"Loading fuel data from: {csv_path}")

        # Set seed for reproducibility
        random.seed(42)

        try:
            with open(csv_path, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                stations = []
                skipped = 0
                seen_keys = set()  # De-duplicate by (opis_id, name, price)

                for row in reader:
                    state = row["State"].strip().upper()

                    # Filter out non-US stations
                    if state not in US_STATES:
                        skipped += 1
                        continue

                    opis_id = int(row["OPIS Truckstop ID"])
                    name = row["Truckstop Name"].strip()
                    price = float(row["Retail Price"])

                    # De-duplicate: keep cheapest price for same station
                    dedup_key = (opis_id, name)
                    if dedup_key in seen_keys:
                        # Update if this price is lower
                        for existing in stations:
                            if (
                                existing.opis_id == opis_id
                                and existing.name == name
                                and price < existing.retail_price
                            ):
                                existing.retail_price = price
                                break
                        continue
                    seen_keys.add(dedup_key)

                    city = row["City"].strip()
                    address = row["Address"].strip()
                    rack_id = int(row["Rack ID"])

                    lat, lon = _city_to_coords(city, state)

                    station = FuelStation(
                        opis_id=opis_id,
                        name=name,
                        address=address,
                        city=city,
                        state=state,
                        rack_id=rack_id,
                        retail_price=price,
                        latitude=lat if lat != 0.0 else None,
                        longitude=lon if lon != 0.0 else None,
                    )
                    stations.append(station)

                # Bulk create for performance
                created = FuelStation.objects.bulk_create(
                    stations, batch_size=batch_size
                )

                self.stdout.write(
                    self.style.SUCCESS(
                        f"Successfully loaded {len(created)} fuel stations "
                        f"(skipped {skipped} non-US entries)."
                    )
                )

                # Stats
                geocoded = sum(1 for s in created if s.latitude is not None)
                self.stdout.write(
                    f"  Geocoded: {geocoded}/{len(created)} "
                    f"({geocoded/len(created)*100:.1f}%)"
                )

                # Price stats
                prices = [s.retail_price for s in created]
                self.stdout.write(
                    f"  Price range: ${min(prices):.3f} - ${max(prices):.3f}"
                )
                self.stdout.write(
                    f"  Average price: ${sum(prices)/len(prices):.3f}/gal"
                )

        except FileNotFoundError:
            raise CommandError(f"CSV file not found: {csv_path}")
        except (KeyError, ValueError) as exc:
            raise CommandError(f"Error parsing CSV: {exc}")
