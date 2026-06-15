# Fuel Route Optimizer API

A high-performance, Senior Software Engineer (SSE) level Django REST API that computes the most cost-effective fuel stops along a travel route between two locations in the USA.

The system assumes a vehicle with a maximum range of **500 miles**, a fuel consumption rate of **10 MPG**, and computes the optimal refueling locations and total fuel cost using a fast greedy corridor-search algorithm.

---

## Architecture & SSE Design Highlights

1. **Service-Oriented Architecture (Thin Views, Rich Services)**:
   - **`GeocodingService`**: Interacts with Nominatim (OSM) to resolve place names to geographic coordinates. Implements local-memory caching and strict 1-second rate-limiting compliance.
   - **`RoutingService`**: Calls OSRM (Open Source Routing Machine) to retrieve the complete route path and geometry in a **single API call** (minimizing external network overhead).
   - **`FuelOptimizationService`**: Core algorithmic service that processes route geometry and database records to select optimal stops.
2. **Algorithmic Efficiency ($O(N)$ with Spatial Pruning)**:
   - Route geometry is sampled at 1-mile intervals.
   - Database queries are pruned using a dynamic **corridor search** (bounding box query centered on the current route window with a default buffer of 25 miles).
   - Candidate fuel stations are filtered using composite DB indexes `(latitude, longitude)` and `(state, retail_price)` to ensure sub-millisecond query execution times.
3. **Robust Caching**:
   - Out-of-the-box local memory caching for geocoding and routing results to prevent redundant calls to public APIs.
4. **Structured API Schema**:
   - Clean, versioned endpoint structuring under `/api/v1/`.
   - Comprehensive interactive documentation via **Swagger UI** (using OpenAPI 3.0 / `drf-spectacular`).
5. **Production Hardening**:
   - Environment separation (`settings/base.py`, `settings/development.py`, `settings/production.py`).
   - Unified error envelopes for all unexpected API failures via a global custom exception handler.

---

## Tech Stack

- **Backend Framework**: Django 5.2 (Latest Stable)
- **API Framework**: Django REST Framework (DRF)
- **API Documentation**: drf-spectacular (OpenAPI 3.0)
- **Routing API**: Open Source Routing Machine (OSRM)
- **Geocoding API**: OpenStreetMap Nominatim
- **Database**: SQLite (Highly optimized indexes)

---

## Installation & Setup

### 1. Clone & Prepare Environment
Create a virtual environment and install the required dependencies:

```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install requirements
pip install -r requirements.txt
```

### 2. Configure Environment Variables
Copy the `.env.example` template to `.env` and adjust the variables if needed:

```bash
cp .env.example .env
```

### 3. Database Initialization & Data Import
Run database migrations and load the US fuel prices dataset using the custom bulk loader:

```bash
# Run database migrations
python manage.py migrate

# Bulk load and geocode fuel stations from CSV
python manage.py load_fuel_data --clear
```

---

## Running the Application

Start the local Django development server:

```bash
python manage.py runserver
```

Once running, the following endpoints are available:
- **Interactive Swagger UI**: [http://127.0.0.1:8000/api/docs/](http://127.0.0.1:8000/api/docs/)
- **Interactive ReDoc**: [http://127.0.0.1:8000/api/redoc/](http://127.0.0.1:8000/api/redoc/)
- **Raw OpenAPI Schema**: [http://127.0.0.1:8000/api/schema/](http://127.0.0.1:8000/api/schema/)

--- 

## API Endpoints

### 1. Optimize Fuel Stops (`POST /api/v1/route/optimize/`)
Computes the optimal route and fuel stops between two USA locations.

**Request Body:**
```json
{
  "start": "New York, NY",
  "finish": "Los Angeles, CA"
}
```

**Success Response (200 OK):**
```json
{
  "summary": {
    "total_distance_miles": 2790.45,
    "total_duration_hours": 41.5,
    "total_fuel_gallons": 279.05,
    "total_fuel_cost": 865.05,
    "number_of_stops": 6,
    "vehicle_range_miles": 500,
    "vehicle_mpg": 10
  },
  "origin": {
    "name": "New York, NY, USA",
    "latitude": 40.7128,
    "longitude": -74.0060
  },
  "destination": {
    "name": "Los Angeles, CA, USA",
    "latitude": 34.0522,
    "longitude": -118.2437
  },
  "fuel_stops": [
    {
      "station_id": 432,
      "station_name": "PILOT TRAVEL CENTER #468",
      "address": "I-57, EXIT 283 & US-24",
      "city": "Gilman",
      "state": "IL",
      "latitude": 40.3494,
      "longitude": -88.9861,
      "retail_price": 3.399,
      "distance_from_start_miles": 450.2,
      "gallons_needed": 45.02,
      "cost": 153.02
    }
    // ... additional optimal stops (every ~450-480 miles)
  ],
  "route": {
    "type": "LineString",
    "coordinates": [
      [-74.0060, 40.7128],
      // ... coordinates array for drawing on standard map engines
      [-118.2437, 34.0522]
    ]
  }
}
```

### 2. Query Fuel Stations (`GET /api/v1/stations/`)
Allows querying the imported stations with state/price filters.

**Parameters:**
- `state` (optional): Filter by 2-letter US state code (e.g. `TX`).
- `min_price` (optional): Minimum retail price.
- `max_price` (optional): Maximum retail price.
- `limit` (optional): Limit records returned (default 50, max 500).

### 3. Health Check (`GET /api/v1/health/`)
Returns DB coverage metrics, service status, and current configuration settings.

---

## Testing

A comprehensive test suite of unit and integration tests is included.

Run all tests:
```bash
python manage.py test
```
# Fuel-Price-Estimator
