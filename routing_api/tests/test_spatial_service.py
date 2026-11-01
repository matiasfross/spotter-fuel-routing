import pytest
from django.test import SimpleTestCase
from routing_api.services.spatial_service import SpatialFuelService


class TestSpatialFuelService(SimpleTestCase):

    def test_dataset_loaded(self):
        service = SpatialFuelService()
        assert service._fuel_df is not None
        assert len(service._fuel_df) > 5000
        assert 'Retail Price' in service._fuel_df.columns
        assert 'lat' in service._fuel_df.columns
        assert 'lon' in service._fuel_df.columns

    def test_find_candidates_along_simple_route(self):
        service = SpatialFuelService()
        # Segment through Ohio/Pennsylvania along I-80: (approx lat 41.1, lon -80.5 to -81.5)
        coords = [
            [-80.5, 41.1],
            [-80.8, 41.15],
            [-81.2, 41.2],
            [-81.5, 41.25]
        ]
        candidates = service.find_candidate_stops_along_route(coords, corridor_radius_miles=15.0)
        assert isinstance(candidates, list)
        if candidates:
            first = candidates[0]
            assert 'truckstop_id' in first
            assert 'retail_price' in first
            assert 'route_dist_miles' in first
            assert 'off_route_miles' in first
            assert first['off_route_miles'] <= 15.0
            # Ensure ordered by route distance
            dists = [c['route_dist_miles'] for c in candidates]
            assert dists == sorted(dists)
