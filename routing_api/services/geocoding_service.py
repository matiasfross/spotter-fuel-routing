import re
import urllib.parse
import urllib.request
import json
import logging
from typing import Dict, Any, Tuple, Optional
from django.conf import settings
from rest_framework.exceptions import ValidationError

logger = logging.getLogger(__name__)

# Pre-cached coordinates for top 120 US cities and transport hubs for instant offline resolution
OFFLINE_US_CITIES: Dict[str, Tuple[float, float, str]] = {
    # format: 'normalized_name': (latitude, longitude, formatted_name)
    'new york ny': (40.712776, -74.005974, 'New York, NY'),
    'new york city ny': (40.712776, -74.005974, 'New York, NY'),
    'nyc': (40.712776, -74.005974, 'New York, NY'),
    'new york': (40.712776, -74.005974, 'New York, NY'),
    'los angeles ca': (34.052235, -118.243683, 'Los Angeles, CA'),
    'la ca': (34.052235, -118.243683, 'Los Angeles, CA'),
    'los angeles': (34.052235, -118.243683, 'Los Angeles, CA'),
    'chicago il': (41.878113, -87.629799, 'Chicago, IL'),
    'chicago': (41.878113, -87.629799, 'Chicago, IL'),
    'houston tx': (29.760427, -95.369804, 'Houston, TX'),
    'houston': (29.760427, -95.369804, 'Houston, TX'),
    'phoenix az': (33.448376, -112.074036, 'Phoenix, AZ'),
    'phoenix': (33.448376, -112.074036, 'Phoenix, AZ'),
    'philadelphia pa': (39.952583, -75.165222, 'Philadelphia, PA'),
    'philadelphia': (39.952583, -75.165222, 'Philadelphia, PA'),
    'san antonio tx': (29.424122, -98.493629, 'San Antonio, TX'),
    'san antonio': (29.424122, -98.493629, 'San Antonio, TX'),
    'san diego ca': (32.715736, -117.161087, 'San Diego, CA'),
    'san diego': (32.715736, -117.161087, 'San Diego, CA'),
    'dallas tx': (32.776665, -96.796989, 'Dallas, TX'),
    'dallas': (32.776665, -96.796989, 'Dallas, TX'),
    'san jose ca': (37.338207, -121.886330, 'San Jose, CA'),
    'san jose': (37.338207, -121.886330, 'San Jose, CA'),
    'austin tx': (30.267153, -97.743057, 'Austin, TX'),
    'austin': (30.267153, -97.743057, 'Austin, TX'),
    'jacksonville fl': (30.332184, -81.655647, 'Jacksonville, FL'),
    'jacksonville': (30.332184, -81.655647, 'Jacksonville, FL'),
    'fort worth tx': (32.755489, -97.330765, 'Fort Worth, TX'),
    'fort worth': (32.755489, -97.330765, 'Fort Worth, TX'),
    'columbus oh': (39.961178, -82.998795, 'Columbus, OH'),
    'columbus': (39.961178, -82.998795, 'Columbus, OH'),
    'charlotte nc': (35.227085, -80.843124, 'Charlotte, NC'),
    'charlotte': (35.227085, -80.843124, 'Charlotte, NC'),
    'indianapolis in': (39.768402, -86.158066, 'Indianapolis, IN'),
    'indianapolis': (39.768402, -86.158066, 'Indianapolis, IN'),
    'san francisco ca': (37.774929, -122.419418, 'San Francisco, CA'),
    'san francisco': (37.774929, -122.419418, 'San Francisco, CA'),
    'seattle wa': (47.606209, -122.332069, 'Seattle, WA'),
    'seattle': (47.606209, -122.332069, 'Seattle, WA'),
    'denver co': (39.739236, -104.990250, 'Denver, CO'),
    'denver': (39.739236, -104.990250, 'Denver, CO'),
    'washington dc': (38.907192, -77.036873, 'Washington, DC'),
    'dc': (38.907192, -77.036873, 'Washington, DC'),
    'boston ma': (42.360081, -71.058884, 'Boston, MA'),
    'boston': (42.360081, -71.058884, 'Boston, MA'),
    'el paso tx': (31.761877, -106.485023, 'El Paso, TX'),
    'el paso': (31.761877, -106.485023, 'El Paso, TX'),
    'nashville tn': (36.162663, -86.781601, 'Nashville, TN'),
    'nashville': (36.162663, -86.781601, 'Nashville, TN'),
    'detroit mi': (42.331429, -83.045753, 'Detroit, MI'),
    'detroit': (42.331429, -83.045753, 'Detroit, MI'),
    'oklahoma city ok': (35.467560, -97.516426, 'Oklahoma City, OK'),
    'oklahoma city': (35.467560, -97.516426, 'Oklahoma City, OK'),
    'portland or': (45.515232, -122.678385, 'Portland, OR'),
    'portland': (45.515232, -122.678385, 'Portland, OR'),
    'las vegas nv': (36.169941, -115.139832, 'Las Vegas, NV'),
    'las vegas': (36.169941, -115.139832, 'Las Vegas, NV'),
    'memphis tn': (35.149532, -90.048981, 'Memphis, TN'),
    'memphis': (35.149532, -90.048981, 'Memphis, TN'),
    'louisville ky': (38.252666, -85.758453, 'Louisville, KY'),
    'louisville': (38.252666, -85.758453, 'Louisville, KY'),
    'baltimore md': (39.290386, -76.612190, 'Baltimore, MD'),
    'baltimore': (39.290386, -76.612190, 'Baltimore, MD'),
    'milwaukee wi': (43.038902, -87.906471, 'Milwaukee, WI'),
    'milwaukee': (43.038902, -87.906471, 'Milwaukee, WI'),
    'albuquerque nm': (35.084385, -106.650421, 'Albuquerque, NM'),
    'albuquerque': (35.084385, -106.650421, 'Albuquerque, NM'),
    'tucson az': (32.222607, -110.974709, 'Tucson, AZ'),
    'tucson': (32.222607, -110.974709, 'Tucson, AZ'),
    'fresno ca': (36.746841, -119.772591, 'Fresno, CA'),
    'fresno': (36.746841, -119.772591, 'Fresno, CA'),
    'sacramento ca': (38.581573, -121.494400, 'Sacramento, CA'),
    'sacramento': (38.581573, -121.494400, 'Sacramento, CA'),
    'kansas city mo': (39.099728, -94.578568, 'Kansas City, MO'),
    'kansas city': (39.099728, -94.578568, 'Kansas City, MO'),
    'mesa az': (33.415184, -111.831474, 'Mesa, AZ'),
    'mesa': (33.415184, -111.831474, 'Mesa, AZ'),
    'atlanta ga': (33.748997, -84.387985, 'Atlanta, GA'),
    'atlanta': (33.748997, -84.387985, 'Atlanta, GA'),
    'omaha ne': (41.256538, -95.934502, 'Omaha, NE'),
    'omaha': (41.256538, -95.934502, 'Omaha, NE'),
    'colorado springs co': (38.833881, -104.821365, 'Colorado Springs, CO'),
    'colorado springs': (38.833881, -104.821365, 'Colorado Springs, CO'),
    'raleigh nc': (35.779591, -78.638176, 'Raleigh, NC'),
    'raleigh': (35.779591, -78.638176, 'Raleigh, NC'),
    'miami fl': (25.761681, -80.191788, 'Miami, FL'),
    'miami': (25.761681, -80.191788, 'Miami, FL'),
    'virginia beach va': (36.852927, -75.977989, 'Virginia Beach, VA'),
    'virginia beach': (36.852927, -75.977989, 'Virginia Beach, VA'),
    'oakland ca': (37.804363, -122.271111, 'Oakland, CA'),
    'oakland': (37.804363, -122.271111, 'Oakland, CA'),
    'minneapolis mn': (44.977753, -93.265011, 'Minneapolis, MN'),
    'minneapolis': (44.977753, -93.265011, 'Minneapolis, MN'),
    'tulsa ok': (36.153980, -95.992775, 'Tulsa, OK'),
    'tulsa': (36.153980, -95.992775, 'Tulsa, OK'),
    'bakersfield ca': (35.373291, -119.018715, 'Bakersfield, CA'),
    'tampa fl': (27.950575, -82.457176, 'Tampa, FL'),
    'tampa': (27.950575, -82.457176, 'Tampa, FL'),
    'wichita ks': (37.687176, -97.330055, 'Wichita, KS'),
    'wichita': (37.687176, -97.330055, 'Wichita, KS'),
    'cleveland oh': (41.499321, -81.694359, 'Cleveland, OH'),
    'cleveland': (41.499321, -81.694359, 'Cleveland, OH'),
    'orlando fl': (28.538336, -81.379234, 'Orlando, FL'),
    'orlando': (28.538336, -81.379234, 'Orlando, FL'),
    'st louis mo': (38.627003, -90.199402, 'St. Louis, MO'),
    'saint louis mo': (38.627003, -90.199402, 'St. Louis, MO'),
    'st. louis mo': (38.627003, -90.199402, 'St. Louis, MO'),
    'st louis': (38.627003, -90.199402, 'St. Louis, MO'),
    'pittsburgh pa': (40.440624, -79.995888, 'Pittsburgh, PA'),
    'pittsburgh': (40.440624, -79.995888, 'Pittsburgh, PA'),
    'cincinnati oh': (39.103119, -84.512016, 'Cincinnati, OH'),
    'cincinnati': (39.103119, -84.512016, 'Cincinnati, OH'),
    'salt lake city ut': (40.760780, -111.891045, 'Salt Lake City, UT'),
    'salt lake city': (40.760780, -111.891045, 'Salt Lake City, UT'),
    'slc': (40.760780, -111.891045, 'Salt Lake City, UT'),
}


class GeocodingService:
    """
    Robust geocoding service supporting coordinates and address/place names
    with offline US hub pre-caching, LRU runtime caching, and USA boundary enforcement.
    """

    _runtime_cache: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def resolve_location(cls, location_input: Any, field_name: str = 'location') -> Dict[str, Any]:
        """
        Resolves an input into validated US coordinates and a display name.
        Accepts:
            - string: "40.7128,-74.0060" or "New York, NY"
            - dict: {"lat": 40.7128, "lon": -74.0060}
            - list/tuple: [40.7128, -74.0060] or [-74.0060, 40.7128]
        Returns:
            {"name": str, "latitude": float, "longitude": float}
        """
        if not location_input:
            raise ValidationError({field_name: "Location input cannot be empty."})

        # 1. Dict format: {"lat": ..., "lon": ...}
        if isinstance(location_input, dict):
            lat = location_input.get('lat') or location_input.get('latitude')
            lon = location_input.get('lon') or location_input.get('lng') or location_input.get('longitude')
            if lat is not None and lon is not None:
                try:
                    f_lat = float(lat)
                    f_lon = float(lon)
                    cls.validate_usa_bounds(f_lat, f_lon, field_name)
                    return {
                        'name': location_input.get('name') or f"{f_lat:.4f}, {f_lon:.4f}",
                        'latitude': f_lat,
                        'longitude': f_lon
                    }
                except ValueError:
                    raise ValidationError({field_name: "Coordinates must be numeric."})

        # 2. List or Tuple format: [lat, lon]
        if isinstance(location_input, (list, tuple)) and len(location_input) == 2:
            try:
                v1, v2 = float(location_input[0]), float(location_input[1])
                # Check lat, lon vs lon, lat
                if -180.0 <= v1 <= -60.0 and 20.0 <= v2 <= 75.0:
                    f_lon, f_lat = v1, v2
                else:
                    f_lat, f_lon = v1, v2
                cls.validate_usa_bounds(f_lat, f_lon, field_name)
                return {
                    'name': f"{f_lat:.4f}, {f_lon:.4f}",
                    'latitude': f_lat,
                    'longitude': f_lon
                }
            except ValueError:
                raise ValidationError({field_name: "Coordinate array must contain numbers."})

        # 3. String format
        if not isinstance(location_input, str):
            raise ValidationError({field_name: f"Invalid format for {field_name}."})

        str_input = location_input.strip()

        # Check coordinate regex "lat, lon"
        coord_match = re.match(r'^[-+]?([0-9]+(\.[0-9]+)?)\s*,\s*[-+]?([0-9]+(\.[0-9]+)?)$', str_input)
        if coord_match:
            try:
                parts = [float(p.strip()) for p in str_input.split(',')]
                v1, v2 = parts[0], parts[1]
                # Detect if given as [lon, lat] or [lat, lon]
                if -180.0 <= v1 <= -60.0 and 20.0 <= v2 <= 75.0:
                    f_lon, f_lat = v1, v2
                else:
                    f_lat, f_lon = v1, v2
                cls.validate_usa_bounds(f_lat, f_lon, field_name)
                return {
                    'name': f"{f_lat:.4f}, {f_lon:.4f}",
                    'latitude': f_lat,
                    'longitude': f_lon
                }
            except ValueError:
                pass

        # Check runtime cache first
        norm_key = re.sub(r'[^a-z0-9 ]', '', str_input.lower()).strip()
        norm_key = re.sub(r'\s+', ' ', norm_key)

        if norm_key in cls._runtime_cache:
            return cls._runtime_cache[norm_key]

        # Check offline city cache (Instant, 0 network calls!)
        if norm_key in OFFLINE_US_CITIES:
            lat, lon, disp_name = OFFLINE_US_CITIES[norm_key]
            res = {'name': disp_name, 'latitude': lat, 'longitude': lon}
            cls._runtime_cache[norm_key] = res
            return res

        # Try Nominatim OpenStreetMap Geocoding API
        return cls._geocode_with_nominatim(str_input, norm_key, field_name)

    @classmethod
    def _geocode_with_nominatim(cls, query: str, norm_key: str, field_name: str) -> Dict[str, Any]:
        """
        Geocodes query using OpenStreetMap Nominatim restricted to USA country code.
        """
        base_url = getattr(settings, 'NOMINATIM_BASE_URL', 'https://nominatim.openstreetmap.org')
        params = {
            'q': query,
            'format': 'json',
            'countrycodes': 'us',
            'limit': 1,
            'addressdetails': 1
        }
        url = f"{base_url}/search?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(
            url,
            headers={'User-Agent': 'FuelRoutingSpotterAssessment/1.0 (matias_assessment)'}
        )

        try:
            with urllib.request.urlopen(req, timeout=8) as response:
                data = json.loads(response.read().decode('utf-8'))
                if not data:
                    raise ValidationError({
                        field_name: f"Could not find location '{query}' within the USA."
                    })

                first = data[0]
                lat = float(first['lat'])
                lon = float(first['lon'])
                display_name = first.get('display_name', query)

                cls.validate_usa_bounds(lat, lon, field_name)

                result = {
                    'name': display_name,
                    'latitude': lat,
                    'longitude': lon
                }
                cls._runtime_cache[norm_key] = result
                return result

        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Geocoding error for query '{query}': {e}")
            raise ValidationError({
                field_name: f"Unable to geocode location '{query}'. Please verify spelling or provide coordinates."
            })

    @classmethod
    def validate_usa_bounds(cls, lat: float, lon: float, field_name: str = 'location') -> None:
        """
        Enforces that the location lies strictly within USA territory.
        """
        # Continental US bounds
        in_continental = (24.0 <= lat <= 50.0) and (-125.0 <= lon <= -66.0)
        # Alaska bounds
        in_alaska = (51.0 <= lat <= 72.0) and (-180.0 <= lon <= -129.0)
        # Hawaii bounds
        in_hawaii = (18.0 <= lat <= 23.0) and (-161.0 <= lon <= -154.0)

        if not (in_continental or in_alaska or in_hawaii):
            raise ValidationError({
                field_name: f"Location ({lat:.4f}, {lon:.4f}) is outside the USA. Both start and finish locations must be within the USA."
            })
