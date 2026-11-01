import pytest
from rest_framework.exceptions import ValidationError
from routing_api.services.geocoding_service import GeocodingService


class TestGeocodingService:

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
