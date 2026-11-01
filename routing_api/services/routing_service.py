import json
import logging
import urllib.error
import urllib.request
from typing import Any

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
    def get_route(cls, start: tuple[float, float], finish: tuple[float, float]) -> dict[str, Any]:
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

        except urllib.error.HTTPError as e:
            logger.error(f"HTTP error contacting routing engine: {e.code} {e.reason}")
            if e.code == 400:
                try:
                    err_content = e.read().decode('utf-8')
                    err_json = json.loads(err_content)
                    msg = err_json.get('message', 'Invalid routing request coordinates.')
                except (json.JSONDecodeError, TypeError, ValueError):
                    msg = "Invalid routing request coordinates."
                raise ValidationError({'route': f"Routing engine rejected coordinates: {msg}"})
            elif e.code == 429:
                raise APIException("Routing engine rate limit exceeded. Please retry in a few moments.")
            raise APIException(f"Routing engine returned error status {e.code}: {e.reason}")
        except urllib.error.URLError as e:
            logger.error(f"Network error contacting routing engine: {e}")
            raise APIException(
                "Failed to contact external routing engine. Please check internet connection or retry."
            )
        except Exception as e:
            if isinstance(e, (ValidationError, APIException)):
                raise
            logger.error(f"Unexpected error in routing service: {e}")
            raise APIException(f"Routing failed: {e!s}")
