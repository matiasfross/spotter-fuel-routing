import json
from unittest.mock import patch
import pytest
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status


class TestRouteApiEndpoints(APITestCase):

    def test_health_check_endpoint(self):
        url = reverse('health_check')
        response = self.client.get(url)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['status'] == 'healthy'
        assert data['fuel_stops_loaded'] > 5000
        assert data['max_vehicle_range_miles'] == 500.0
        assert data['fuel_efficiency_mpg'] == 10.0

    def test_route_missing_parameters(self):
        url = reverse('route_optimization')
        # Missing finish
        response = self.client.get(url, {'start': 'New York, NY'})
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @patch('routing_api.services.routing_service.RoutingService.get_route')
    def test_route_get_success(self, mock_get_route):
        # Mock OSRM call to make test fast and network-independent
        mock_get_route.return_value = {
            'distance_miles': 800.0,
            'duration_hours': 12.0,
            'coordinates': [
                [-74.006, 40.7128],
                [-77.0, 40.5],
                [-80.0, 40.2],
                [-84.0, 39.8],
                [-87.6298, 41.8781]
            ],
            'bounding_box': [-87.6298, 39.8, -74.006, 41.8781]
        }

        url = reverse('route_optimization')
        response = self.client.get(url, {
            'start': 'New York, NY',
            'finish': 'Chicago, IL'
        })

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert 'origin' in data
        assert 'destination' in data
        assert 'summary' in data
        assert 'fuel_stops' in data
        assert 'map_geojson' in data
        assert 'map_url' in data

        summary = data['summary']
        assert summary['total_distance_miles'] == 800.0
        assert summary['vehicle_max_range_miles'] == 500.0
        assert summary['vehicle_mpg'] == 10.0
        assert summary['total_fuel_consumed_gallons'] == 80.0
        assert summary['total_fuel_cost_dollars'] > 0.0

        # GeoJSON verification
        geojson = data['map_geojson']
        assert geojson['type'] == 'FeatureCollection'
        assert len(geojson['features']) >= 3  # Route + Origin + Destination + Stops

    @patch('routing_api.services.routing_service.RoutingService.get_route')
    def test_route_post_success(self, mock_get_route):
        mock_get_route.return_value = {
            'distance_miles': 300.0,
            'duration_hours': 5.0,
            'coordinates': [[-74.006, 40.7128], [-77.0369, 38.9072]],
            'bounding_box': [-77.0369, 38.9072, -74.006, 40.7128]
        }

        url = reverse('route_optimization')
        payload = {
            'start': 'New York, NY',
            'finish': 'Washington, DC',
            'max_range': 500.0,
            'mpg': 10.0
        }
        response = self.client.post(
            url,
            data=json.dumps(payload),
            content_type='application/json'
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['summary']['total_distance_miles'] == 300.0
        assert data['summary']['total_fuel_consumed_gallons'] == 30.0

    def test_route_outside_usa_error(self):
        url = reverse('route_optimization')
        response = self.client.get(url, {
            'start': 'Paris, France',
            'finish': 'Berlin, Germany'
        })
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @patch('routing_api.services.routing_service.RoutingService.get_route')
    def test_route_map_html_view(self, mock_get_route):
        mock_get_route.return_value = {
            'distance_miles': 200.0,
            'duration_hours': 3.0,
            'coordinates': [[-74.0, 40.7], [-75.0, 40.0]],
            'bounding_box': [-75.0, 40.0, -74.0, 40.7]
        }

        url = reverse('route_map')
        response = self.client.get(url, {
            'start': 'New York, NY',
            'finish': 'Philadelphia, PA'
        })
        assert response.status_code == status.HTTP_200_OK
        assert 'text/html' in response['Content-Type']
        content = response.content.decode('utf-8')
        assert "Spotter Fuel Route Optimizer" in content
        assert "L.map('map'" in content
