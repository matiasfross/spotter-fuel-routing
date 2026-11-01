import json
import logging
import urllib.request
import urllib.error
from typing import Dict, Any, Tuple
from django.conf import settings
from rest_framework.exceptions import APIException, ValidationError

logger = logging.getLogger(__name__)

METERS_TO_MILES = 0.000621371
SECONDS_TO_HOURS = 1.0 / 3600.0


class RoutingService:
    """
    Service interfacing with free routing engines (OSRM by default).
    Returns route distance, duration, and GeoJSON geometry in a single API call.
    """

    @classmethod
    def get_route(cls, start: Tuple[float, float], finish: Tuple[float, float]) -> Dict[str, Any]:
        """
        Calculates driving route between start (lat, lon) and finish (lat, lon).
        Returns:
            {
                'distance_miles': float,
                'duration_hours': float,
                'coordinates': list, # [[lon, lat], ...]
                'bounding_box': [min_lon, min_lat, max_lon, max_lat]
            }
        """
        start_lat, start_lon = start
        finish_lat, finish_lon = finish

        base_url = getattr(settings, 'OSRM_BASE_URL', 'http://router.project-osrm.org')
        # OSRM expects coordinates in order: lon,lat
        url = (
            f"{base_url}/route/v1/driving/"
            f"{start_lon:.6f},{start_lat:.6f};{finish_lon:.6f},{finish_lat:.6f}"
            f"?overview=full&geometries=geojson&steps=false"
        )

        req = urllib.request.Request(
            url,
            headers={'User-Agent': 'FuelRoutingSpotterAssessment/1.0'}
        )

        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode('utf-8'))

                if data.get('code') != 'Ok' or not data.get('routes'):
                    code = data.get('code', 'Unknown')
                    msg = data.get('message', 'No driving route found between specified points.')
                    logger.error(f"OSRM error code {code}: {msg}")
                    raise ValidationError({
                        'route': f"Unable to find driving route: {msg} (OSRM code: {code})"
                    })

                best_route = data['routes'][0]
                distance_meters = float(best_route['distance'])
                duration_seconds = float(best_route['duration'])
                geometry = best_route['geometry']
                coordinates = geometry.get('coordinates', [])

                if not coordinates:
                    raise ValidationError({'route': "Route geometry is empty."})

                distance_miles = distance_meters * METERS_TO_MILES
                duration_hours = duration_seconds * SECONDS_TO_HOURS

                # Compute bounding box
                lons = [c[0] for c in coordinates]
                lats = [c[1] for c in coordinates]
                bbox = [min(lons), min(lats), max(lons), max(lats)]

                return {
                    'distance_miles': round(distance_miles, 2),
                    'duration_hours': round(duration_hours, 2),
                    'coordinates': coordinates,
                    'bounding_box': bbox,
                }

        except urllib.error.URLError as e:
            logger.error(f"Network error contacting routing engine: {e}")
            raise APIException(
                "Failed to contact external routing engine. Please check internet connection or retry."
            )
        except Exception as e:
            if isinstance(e, (ValidationError, APIException)):
                raise e
            logger.error(f"Unexpected error in routing service: {e}")
            raise APIException(f"Routing failed: {str(e)}")
