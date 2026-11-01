# ⛽ Spotter - Fuel Routing & Cost Optimization API

> **Backend Django Engineer Coding Assessment**  
> Developed for **Spotter** by **Matias**.

An API and interactive visualization tool built with **Django 6.1 / Django REST Framework** that calculates optimal driving routes across the continental United States and determines the most cost-effective fuel stops along the corridor, strictly adhering to vehicle range and consumption constraints.

---

## 🌟 Highlights & Key Features

- **Optimal Refueling Algorithm (Dynamic Programming)**:
  - Formulated as a Shortest Path on a Directed Acyclic Graph (DAG) solved via Dynamic Programming in **< 20 milliseconds**.
  - Respects vehicle physical constraints: **500-mile maximum single-tank range** ($R_{max}$) and **10 miles per gallon (MPG)**.
  - Minimizes total dollars spent on fuel using real OPIS retail pricing.
- **Lightning-Fast Spatial Search (< 20 ms)**:
  - Pre-geocoded database of **6,626 US truckstops** with exact latitude and longitude coordinates.
  - Vectorized Haversine distance and `scipy.spatial.cKDTree` corridor filtering within a 10-mile highway radius.
- **Minimal External API Calls (1 Call)**:
  - Free Open Source Routing Machine (**OSRM**) public engine: route distance, duration, and GeoJSON geometry fetched in **exactly 1 network call**.
  - Offline pre-cached coordinate dictionary for top US transport hubs and cities (zero network calls for common cities).
- **Interactive Leaflet Web Map & Postman Ready**:
  - Full GeoJSON `FeatureCollection` returned in API response.
  - Interactive Leaflet.js web application with gas pump markers, interactive sidebar, and live route recalibration.
  - Ready-to-import `Postman_Collection.json` with pre-configured requests.
- **Comprehensive Test Suite**:
  - 20 unit and integration tests covering geocoding, boundary validation, routing, spatial search, DP optimizer, and API endpoints.

---

## 📐 Architecture & Mathematical Optimization

```
                                      +--------------------+
[ Client / Postman ]                | OSRM Public Engine |
        |                             +--------------------+
        |                                       ^
        | 1. GET /api/route/?start=...&finish=  | (Single HTTP call)
        v                                       v
+--------------------------------------------------------------+
| Django REST Framework API Layer                              |
|                                                              |
|  1. GeocodingService                                         |
|     - Offline US Hub Dictionary (0 network calls)            |
|     - USA Boundary Enforcer (lat: 24°-50°, lon: -125°--66°)  |
|                                                              |
|  2. RoutingService                                           |
|     - Distance, duration, polyline coordinates via OSRM      |
|                                                              |
|  3. SpatialFuelService                                       |
|     - Pre-geocoded 6,626 OPIS Truckstops                     |
|     - KDTree corridor query (r = 10 miles)                   |
|     - Continuous route mile-marker projection                |
|                                                              |
|  4. FuelOptimizer (Dynamic Programming Solver)               |
|     - Nodes: S_0 (Origin), S_1..M (Stops), S_dest (Finish)    |
|     - Edge (i -> j) feasible iff dist(j) - dist(i) <= 500 mi |
|     - Edge Cost: ((dist(j) - dist(i)) / 10 mpg) * price(i)   |
|     - Reconstructs global minimum cost refueling path        |
+--------------------------------------------------------------+
        |
        v
[ JSON Response / GeoJSON / Interactive Web Map ]
```

---

## 🚀 Quickstart Guide

### Option A: Local Python Environment

1. **Clone the repository:**
   ```bash
   git clone <repo-url>
   cd proyectoRouting
   ```

2. **Create and activate a virtual environment (optional but recommended):**
   ```bash
   python -m venv venv
   # Windows:
   venv\Scripts\activate
   # Linux / macOS:
   source venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Apply database migrations:**
   ```bash
   python manage.py migrate
   ```

5. **Run the development server:**
   ```bash
   python manage.py runserver
   ```
   Open your browser at `http://127.0.0.1:8000/` to access the interactive map view!

---

### Option B: Docker

```bash
docker compose up --build
```
Access the application at `http://127.0.0.1:8000/`.

---

## 🧪 Running the Test Suite

Run the full automated test suite with pytest:

```bash
pytest -v
```

All 20 test cases will execute:
```
routing_api/tests/test_api_endpoints.py::TestRouteApiEndpoints::test_health_check_endpoint PASSED
routing_api/tests/test_api_endpoints.py::TestRouteApiEndpoints::test_route_get_success PASSED
routing_api/tests/test_api_endpoints.py::TestRouteApiEndpoints::test_route_map_html_view PASSED
routing_api/tests/test_fuel_optimizer.py::TestFuelOptimizer::test_short_trip_under_500_miles PASSED
routing_api/tests/test_fuel_optimizer.py::TestFuelOptimizer::test_long_trip_max_range_constraint PASSED
...
20 passed in ~1.9s
```

---

## 📡 API Reference

### 1. Optimize Fuel Route

- **Endpoint**: `GET /api/route/` or `POST /api/route/`
- **Query Parameters (GET)** or **JSON Body (POST)**:
  - `start` *(string or object, required)*: Origin city/state name (e.g. `"New York, NY"`) or coordinates (`"40.7128,-74.0060"` or `{"lat": 40.7128, "lon": -74.0060}`).
  - `finish` *(string or object, required)*: Destination city/state name or coordinates.
  - `max_range` *(float, optional)*: Single tank range in miles (default: `500.0`).
  - `mpg` *(float, optional)*: Miles per gallon (default: `10.0`).
  - `corridor_radius` *(float, optional)*: Search radius along route in miles (default: `10.0`).

#### Sample Request (GET)
```http
GET /api/route/?start=New+York,+NY&finish=Los+Angeles,+CA HTTP/1.1
Host: 127.0.0.1:8000
```

#### Sample Request (POST)
```http
POST /api/route/ HTTP/1.1
Host: 127.0.0.1:8000
Content-Type: application/json

{
    "start": "New York, NY",
    "finish": "Los Angeles, CA",
    "max_range": 500.0,
    "mpg": 10.0
}
```

#### Sample Response (Truncated for brevity)
```json
{
  "origin": {
    "name": "New York, NY",
    "latitude": 40.712776,
    "longitude": -74.005974
  },
  "destination": {
    "name": "Los Angeles, CA",
    "latitude": 34.052235,
    "longitude": -118.243683
  },
  "summary": {
    "total_distance_miles": 2794.21,
    "estimated_duration_hours": 41.25,
    "vehicle_max_range_miles": 500.0,
    "vehicle_mpg": 10.0,
    "total_fuel_consumed_gallons": 279.42,
    "total_fuel_purchased_gallons": 279.42,
    "total_fuel_cost_dollars": 856.20,
    "average_fuel_price_dollars": 3.064,
    "number_of_fuel_stops": 11
  },
  "fuel_stops": [
    {
      "stop_number": 1,
      "truckstop_id": 639,
      "name": "SHEETZ #639",
      "address": "1301 N CANFIELD NILES RD",
      "city": "Youngstown",
      "state": "OH",
      "latitude": 41.1033,
      "longitude": -80.7601,
      "retail_price": 3.059,
      "mile_marker": 390.4,
      "distance_from_last_stop": 390.4,
      "leg_distance_to_next": 164.7,
      "gallons_purchased": 16.47,
      "cost_at_stop": 50.38
    }
  ],
  "map_geojson": {
    "type": "FeatureCollection",
    "features": [...]
  },
  "map_url": "http://127.0.0.1:8000/api/route/map/?start=New%20York,%20NY&finish=Los%20Angeles,%20CA"
}
```

---

### 2. Interactive Map View

- **Endpoint**: `GET /api/route/map/?start=...&finish=...` or root `GET /`
- Returns an HTML webpage rendering a Leaflet.js interactive map with:
  - Complete highway route polyline.
  - Green start marker and red finish checkered flag.
  - Numbered fuel stop pins with interactive modal popups showing gas station name, address, price, and leg costs.
  - Sidebar showing distance, fuel cost, gallons, and clickable stops list.

---

### 3. Health Check

- **Endpoint**: `GET /api/health/`
- Returns system health and dataset status:
  ```json
  {
    "status": "healthy",
    "fuel_stops_loaded": 6626,
    "max_vehicle_range_miles": 500.0,
    "fuel_efficiency_mpg": 10.0,
    "routing_engine": "OSRM Free API"
  }
  ```

---

## 📮 Postman Collection

Import `Postman_Collection.json` directly into Postman. It includes 6 pre-configured requests:
1. `1. Health Check`: Verifies dataset is loaded.
2. `2. Route Optimization (GET) - New York to Los Angeles`: Cross-country transcontinental route.
3. `3. Route Optimization (POST) - Chicago to Houston`: JSON body payload.
4. `4. Route Optimization (Coordinates) - Miami to Seattle`: Coordinate inputs.
5. `5. Short Route (< 500 miles, Zero Stops Required)`: Philadelphia to New York edge case.
6. `6. Validation Error - Location Outside USA`: Demonstrates 400 Bad Request boundary enforcement.

---

## 📹 Loom Video Recording Script (5-Minute Guide for Matias)

Here is a recommended script for recording the 5-minute Loom video:

1. **Introduction (30s)**:
   - "Hi Spotter team! I'm Matias, and this is my solution for the Backend Django Engineer coding assessment."
   - State the problem: start/finish in USA, 500-mile max range, 10 MPG, optimal fuel stops based on OPIS prices, total fuel cost, and a route map.

2. **Architecture & Engineering Decisions (90s)**:
   - Explain how you solved the geocoding constraint: The provided CSV had addresses and cities but no lat/lon coordinates. You built an enriched dataset of 6,626 US truckstops offline using US Census & GeoNames data.
   - Mention that spatial queries use a KDTree on projected miles, finding candidate stations along the corridor in **< 15 milliseconds**.
   - Explain the routing engine: A single call to OSRM gets the full route polyline and distance, fulfilling the requirement of making 1 (max 2-3) calls.
   - Explain the Dynamic Programming optimizer: Formulated as shortest path on a DAG, guaranteeing global minimum cost while ensuring no leg between fuel stops ever exceeds 500 miles.

3. **Demonstration in Postman (90s)**:
   - Open Postman, show the `Postman_Collection.json`.
   - Send `GET /api/health/` -> show 6,626 stops loaded.
   - Send `GET /api/route/?start=New York, NY&finish=Los Angeles, CA` -> show response in ~1.5s.
   - Highlight:
     - Total distance: 2,794 miles.
     - Fuel consumed: 279.4 gallons (exact 10 MPG).
     - Total cost: ~$856 (average $3.06/gal).
     - Show the array of `fuel_stops`: each leg is under 500 miles.
   - Send `POST /api/route/` with coordinates or short route (<500 miles) showing 0 stops needed.
   - Send a query outside USA (e.g. Toronto) showing 400 validation error.

4. **Demonstration of the Interactive Map (60s)**:
   - Switch to the browser at `http://127.0.0.1:8000/`.
   - Show the interactive Leaflet map with the blue polyline, green start, red finish, and numbered gas pump icons.
   - Click a fuel stop pin to show the popup with station name, retail price, and cost.
   - Click a stop in the left sidebar to show smooth camera flight to the station.
   - Type a new route (e.g. "Miami, FL" to "Seattle, WA") and hit "Calculate Route".

5. **Conclusion & Testing (30s)**:
   - Show terminal running `pytest -v` (20 passed in 1.9s).
   - "Thank you for reviewing my assessment. I look forward to the next steps!"
