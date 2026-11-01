import json
from unittest.mock import patch, MagicMock
import pytest
from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError, APIException
from routing_api.services.routing_service import RoutingService


class TestRoutingService(SimpleTestCase):

    @patch('urllib.request.urlopen')
    def test_get_route_success(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            'code': 'Ok',
            'routes': [{
                'distance': 160934.4,  # ~100 miles in meters
                'duration': 5400.0,    # 1.5 hours in seconds
                'geometry': {
                    'type': 'LineString',
                    'coordinates': [[-74.0, 40.7], [-74.5, 40.8], [-75.0, 40.9]]
                }
            }]
        }).encode('utf-8')
        mock_urlopen.return_value.__enter__.return_value = mock_response

        res = RoutingService.get_route((40.7, -74.0), (40.9, -75.0))
        assert pytest.approx(res['distance_miles'], 0.1) == 100.0
        assert pytest.approx(res['duration_hours'], 0.1) == 1.5
        assert len(res['coordinates']) == 3
        assert res['bounding_box'] == [-75.0, 40.7, -74.0, 40.9]

    @patch('urllib.request.urlopen')
    def test_get_route_no_route(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            'code': 'NoRoute',
            'message': 'No route could be found'
        }).encode('utf-8')
        mock_urlopen.return_value.__enter__.return_value = mock_response

        with pytest.raises(ValidationError):
            RoutingService.get_route((40.7, -74.0), (40.9, -75.0))

    @patch('urllib.request.urlopen')
    def test_get_route_http_400_error(self, mock_urlopen):
        import urllib.error
        import io
        fp = io.BytesIO(b'{"message": "Invalid coordinates"}')
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url='http://router.project-osrm.org',
            code=400,
            msg='Bad Request',
            hdrs={},
            fp=fp
        )

        with pytest.raises(ValidationError) as exc:
            RoutingService.get_route((40.7, -74.0), (40.9, -75.0))
        assert "Routing engine rejected coordinates" in str(exc.value)

    @patch('urllib.request.urlopen')
    def test_get_route_http_500_error(self, mock_urlopen):
        import urllib.error
        import io
        fp = io.BytesIO(b'{"message": "Internal Server Error"}')
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url='http://router.project-osrm.org',
            code=500,
            msg='Internal Server Error',
            hdrs={},
            fp=fp
        )

        with pytest.raises(APIException):
            RoutingService.get_route((40.7, -74.0), (40.9, -75.0))

