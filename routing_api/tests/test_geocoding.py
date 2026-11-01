import pytest
from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError

from routing_api.services.geocoding_service import GeocodingService


class TestGeocodingService(SimpleTestCase):

    def test_resolve_offline_major_cities(self):
        nyc = GeocodingService.resolve_location("New York, NY", field_name="start")
        assert "New York" in nyc['name']
        assert pytest.approx(nyc['latitude'], 0.1) == 40.71
        assert pytest.approx(nyc['longitude'], 0.1) == -74.00

        la = GeocodingService.resolve_location("Los Angeles, CA", field_name="finish")
        assert "Los Angeles" in la['name']
        assert pytest.approx(la['latitude'], 0.1) == 34.05
        assert pytest.approx(la['longitude'], 0.1) == -118.24

    def test_resolve_coordinate_string(self):
        res = GeocodingService.resolve_location("41.8781, -87.6298", field_name="start")
        assert pytest.approx(res['latitude'], 0.001) == 41.8781
        assert pytest.approx(res['longitude'], 0.001) == -87.6298

    def test_resolve_coordinate_dict(self):
        res = GeocodingService.resolve_location({"lat": 29.7604, "lon": -95.3698}, field_name="start")
        assert pytest.approx(res['latitude'], 0.001) == 29.7604
        assert pytest.approx(res['longitude'], 0.001) == -95.3698

    def test_resolve_coordinate_list(self):
        res = GeocodingService.resolve_location([33.4484, -112.0740], field_name="finish")
        assert pytest.approx(res['latitude'], 0.001) == 33.4484
        assert pytest.approx(res['longitude'], 0.001) == -112.0740

    def test_reject_empty_input(self):
        with pytest.raises(ValidationError):
            GeocodingService.resolve_location("", field_name="start")

        with pytest.raises(ValidationError):
            GeocodingService.resolve_location(None, field_name="start")

    def test_reject_outside_usa_coordinates(self):
        # Paris, France (48.8566, 2.3522)
        with pytest.raises(ValidationError) as exc:
            GeocodingService.resolve_location("48.8566, 2.3522", field_name="start")
        assert "outside the USA" in str(exc.value)

        # Tokyo, Japan (35.6762, 139.6503)
        with pytest.raises(ValidationError) as exc:
            GeocodingService.resolve_location("35.6762, 139.6503", field_name="finish")
        assert "outside the USA" in str(exc.value)

    def test_usa_bounds_validation(self):
        # Continental US valid points
        GeocodingService.validate_usa_bounds(40.0, -100.0)
        GeocodingService.validate_usa_bounds(25.0, -80.0)

        # Invalidation
        with pytest.raises(ValidationError):
            GeocodingService.validate_usa_bounds(10.0, -75.0)  # Colombia

    def test_resolve_json_string_dict_and_list(self):
        # JSON-encoded dict string
        res_dict = GeocodingService.resolve_location('{"lat": 40.7128, "lon": -74.0060}')
        assert pytest.approx(res_dict['latitude'], 0.001) == 40.7128
        assert pytest.approx(res_dict['longitude'], 0.001) == -74.0060

        # JSON-encoded list string
        res_list = GeocodingService.resolve_location('[40.7128, -74.0060]')
        assert pytest.approx(res_list['latitude'], 0.001) == 40.7128
        assert pytest.approx(res_list['longitude'], 0.001) == -74.0060

    def test_resolve_bracketed_and_space_separated_coordinates(self):
        # Bracketed coordinates with spaces
        res1 = GeocodingService.resolve_location('[ 40.7128, -74.0060 ]')
        assert pytest.approx(res1['latitude'], 0.001) == 40.7128
        assert pytest.approx(res1['longitude'], 0.001) == -74.0060

        # Space separated coordinates
        res2 = GeocodingService.resolve_location('40.7128 -74.0060')
        assert pytest.approx(res2['latitude'], 0.001) == 40.7128
        assert pytest.approx(res2['longitude'], 0.001) == -74.0060

    def test_resolve_state_name_normalization(self):
        # Full state names should normalize to offline cache entries
        la = GeocodingService.resolve_location("Los Angeles, California")
        assert "Los Angeles" in la['name']
        assert pytest.approx(la['latitude'], 0.1) == 34.05

        nyc = GeocodingService.resolve_location("New York, New York")
        assert "New York" in nyc['name']
        assert pytest.approx(nyc['latitude'], 0.1) == 40.71

        chi = GeocodingService.resolve_location("Chicago, Illinois")
        assert "Chicago" in chi['name']
        assert pytest.approx(chi['latitude'], 0.1) == 41.88
