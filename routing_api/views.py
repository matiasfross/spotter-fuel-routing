import json
import logging
from typing import Dict, Any
from django.shortcuts import render
from django.urls import reverse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import ValidationError

from .serializers import RouteRequestSerializer, RouteResponseSerializer
from .services import (
    GeocodingService,
    RoutingService,
    SpatialFuelService,
    FuelOptimizer,
)

logger = logging.getLogger(__name__)


def build_geojson(
    route_coords: list,
    start_loc: Dict[str, Any],
    finish_loc: Dict[str, Any],
    fuel_stops: list
) -> Dict[str, Any]:
    """
    Constructs a valid GeoJSON FeatureCollection containing the route line,
    start/finish markers, and fuel stop markers with popup metadata.
    """
    features = [
        # Route LineString
        {
            'type': 'Feature',
            'geometry': {
                'type': 'LineString',
                'coordinates': route_coords,
            },
            'properties': {
                'name': 'Route Polyline',
                'stroke': '#2563eb',
                'stroke-width': 5,
                'stroke-opacity': 0.85,
            }
        },
        # Origin Marker
        {
            'type': 'Feature',
            'geometry': {
                'type': 'Point',
                'coordinates': [start_loc['longitude'], start_loc['latitude']],
            },
            'properties': {
                'type': 'origin',
                'title': f"Start: {start_loc['name']}",
                'marker-color': '#16a34a',
                'marker-symbol': 'star',
            }
        },
        # Destination Marker
        {
            'type': 'Feature',
            'geometry': {
                'type': 'Point',
                'coordinates': [finish_loc['longitude'], finish_loc['latitude']],
            },
            'properties': {
                'type': 'destination',
                'title': f"Finish: {finish_loc['name']}",
                'marker-color': '#dc2626',
                'marker-symbol': 'flag',
            }
        }
    ]

    # Fuel Stops
    for stop in fuel_stops:
        features.append({
            'type': 'Feature',
            'geometry': {
                'type': 'Point',
                'coordinates': [stop['longitude'], stop['latitude']],
            },
            'properties': {
                'type': 'fuel_stop',
                'stop_number': stop['stop_number'],
                'truckstop_id': stop['truckstop_id'],
                'name': stop['name'],
                'address': stop['address'],
                'city': stop['city'],
                'state': stop['state'],
                'retail_price': stop['retail_price'],
                'mile_marker': stop['mile_marker'],
                'distance_from_last_stop': stop['distance_from_last_stop'],
                'gallons_purchased': stop['gallons_purchased'],
                'cost_at_stop': stop['cost_at_stop'],
                'marker-color': '#f59e0b',
                'marker-symbol': 'fuel',
            }
        })

    return {
        'type': 'FeatureCollection',
        'features': features,
    }


def compute_route_data(
    start_input: Any,
    finish_input: Any,
    max_range: float = 500.0,
    mpg: float = 10.0,
    corridor_radius: float = 10.0,
    request=None
) -> Dict[str, Any]:
    """
    Core pipeline executing geocoding, routing, spatial candidate search,
    fuel optimization, and GeoJSON generation.
    """
    # 1. Geocode locations within the USA
    start_loc = GeocodingService.resolve_location(start_input, field_name='start')
    finish_loc = GeocodingService.resolve_location(finish_input, field_name='finish')

    # 2. Get driving route from free routing API (OSRM)
    route_info = RoutingService.get_route(
        (start_loc['latitude'], start_loc['longitude']),
        (finish_loc['latitude'], finish_loc['longitude'])
    )

    # 3. Find candidate truckstops along the route corridor
    spatial_service = SpatialFuelService()
    candidates = spatial_service.find_candidate_stops_along_route(
        route_coords=route_info['coordinates'],
        corridor_radius_miles=corridor_radius
    )

    # 4. Optimize fuel stops using DP
    optimizer = FuelOptimizer(max_range_miles=max_range, mpg=mpg)
    fuel_result = optimizer.optimize(
        candidates=candidates,
        total_distance_miles=route_info['distance_miles'],
        start_location=start_loc,
        finish_location=finish_loc
    )

    # 5. Build GeoJSON Map
    geojson_map = build_geojson(
        route_coords=route_info['coordinates'],
        start_loc=start_loc,
        finish_loc=finish_loc,
        fuel_stops=fuel_result['fuel_stops']
    )

    # Construct map URL
    start_str = start_loc['name']
    finish_str = finish_loc['name']
    map_rel_url = f"/api/route/map/?start={start_str}&finish={finish_str}"
    map_url = request.build_absolute_uri(map_rel_url) if request else map_rel_url

    response_data = {
        'origin': start_loc,
        'destination': finish_loc,
        'summary': {
            'total_distance_miles': route_info['distance_miles'],
            'estimated_duration_hours': route_info['duration_hours'],
            'vehicle_max_range_miles': max_range,
            'vehicle_mpg': mpg,
            'total_fuel_consumed_gallons': fuel_result['total_fuel_consumed_gallons'],
            'total_fuel_purchased_gallons': fuel_result['total_fuel_purchased_gallons'],
            'total_fuel_cost_dollars': fuel_result['total_fuel_cost'],
            'average_fuel_price_dollars': fuel_result['average_price_per_gallon'],
            'number_of_fuel_stops': fuel_result['number_of_stops'],
        },
        'fuel_stops': fuel_result['fuel_stops'],
        'map_geojson': geojson_map,
        'map_url': map_url,
    }

    if 'message' in fuel_result:
        response_data['summary']['message'] = fuel_result['message']

    return response_data


class RouteOptimizationView(APIView):
    """
    Main API endpoint: Takes start and finish locations within USA,
    returns optimal fuel stops, fuel costs, and route map data.
    """

    def get(self, request, *args, **kwargs):
        """
        GET /api/route/?start=New+York,+NY&finish=Los+Angeles,+CA
        """
        start = request.query_params.get('start')
        finish = request.query_params.get('finish')
        max_range = float(request.query_params.get('max_range', 500.0))
        mpg = float(request.query_params.get('mpg', 10.0))
        corridor = float(request.query_params.get('corridor_radius', 10.0))

        if not start or not finish:
            return Response(
                {'error': "Both 'start' and 'finish' query parameters are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check if caller wants direct HTML map view
        if request.query_params.get('format') == 'html' or 'text/html' in request.headers.get('Accept', ''):
            data = compute_route_data(start, finish, max_range, mpg, corridor, request=request)
            return render(request, 'routing_api/map.html', {
                'data_json': json.dumps(data),
                'summary': data['summary'],
                'origin': data['origin'],
                'destination': data['destination'],
                'fuel_stops': data['fuel_stops'],
            })

        data = compute_route_data(start, finish, max_range, mpg, corridor, request=request)
        return Response(data, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        """
        POST /api/route/
        Body:
        {
            "start": "New York, NY",
            "finish": "Los Angeles, CA",
            "max_range": 500.0,
            "mpg": 10.0
        }
        """
        serializer = RouteRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated = serializer.validated_data

        data = compute_route_data(
            start_input=validated['start'],
            finish_input=validated['finish'],
            max_range=validated.get('max_range', 500.0),
            mpg=validated.get('mpg', 10.0),
            corridor_radius=validated.get('corridor_radius', 10.0),
            request=request
        )

        return Response(data, status=status.HTTP_200_OK)


class RouteMapView(APIView):
    """
    Interactive web view displaying the Leaflet map with route polyline,
    start/finish markers, optimal fuel stops, and summary sidebar.
    """

    def get(self, request, *args, **kwargs):
        start = request.query_params.get('start', 'New York, NY')
        finish = request.query_params.get('finish', 'Los Angeles, CA')
        max_range = float(request.query_params.get('max_range', 500.0))
        mpg = float(request.query_params.get('mpg', 10.0))
        corridor = float(request.query_params.get('corridor_radius', 10.0))

        try:
            data = compute_route_data(start, finish, max_range, mpg, corridor, request=request)
            return render(request, 'routing_api/map.html', {
                'data_json': json.dumps(data),
                'summary': data['summary'],
                'origin': data['origin'],
                'destination': data['destination'],
                'fuel_stops': data['fuel_stops'],
                'start_query': start,
                'finish_query': finish,
            })
        except Exception as e:
            return render(request, 'routing_api/map.html', {
                'error': str(e),
                'start_query': start,
                'finish_query': finish,
            })


class HealthCheckView(APIView):
    """
    Health check verifying the service and dataset availability.
    """

    def get(self, request, *args, **kwargs):
        spatial_service = SpatialFuelService()
        stops_count = len(spatial_service._fuel_df) if spatial_service._fuel_df is not None else 0
        return Response({
            'status': 'healthy',
            'fuel_stops_loaded': stops_count,
            'max_vehicle_range_miles': 500.0,
            'fuel_efficiency_mpg': 10.0,
            'routing_engine': 'OSRM Free API',
        }, status=status.HTTP_200_OK)
