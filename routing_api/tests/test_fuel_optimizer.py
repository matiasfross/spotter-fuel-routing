import pytest
from routing_api.services.fuel_optimizer import FuelOptimizer


class TestFuelOptimizer:

    def test_short_trip_under_500_miles(self):
        optimizer = FuelOptimizer(max_range_miles=500.0, mpg=10.0)
        candidates = [
            {'truckstop_id': 1, 'name': 'Station A', 'address': '123 Rd', 'city': 'CityA', 'state': 'OH',
             'latitude': 40.0, 'longitude': -80.0, 'retail_price': 3.10, 'route_dist_miles': 150.0}
        ]
        start = {'name': 'Origin', 'latitude': 40.0, 'longitude': -79.0}
        finish = {'name': 'Destination', 'latitude': 40.0, 'longitude': -83.0}

        res = optimizer.optimize(
            candidates=candidates,
            total_distance_miles=250.0,
            start_location=start,
            finish_location=finish,
            start_full_tank=True
        )

        assert res['number_of_stops'] == 0
        assert res['total_fuel_consumed_gallons'] == 25.0
        assert res['total_fuel_cost'] == 0.0
        assert "within vehicle's single-tank range" in res.get('message', '')

    def test_medium_trip_requiring_stops(self):
        optimizer = FuelOptimizer(max_range_miles=500.0, mpg=10.0)
        # 900-mile trip: needs at least 1 stop (e.g. between 400 and 500)
        candidates = [
            {'truckstop_id': 1, 'name': 'Expensive Stop', 'address': '100 Rd', 'city': 'Town1', 'state': 'PA',
             'latitude': 40.0, 'longitude': -78.0, 'retail_price': 4.50, 'route_dist_miles': 400.0},
            {'truckstop_id': 2, 'name': 'Cheap Stop', 'address': '200 Rd', 'city': 'Town2', 'state': 'OH',
             'latitude': 40.0, 'longitude': -82.0, 'retail_price': 2.80, 'route_dist_miles': 450.0},
        ]
        start = {'name': 'Start', 'latitude': 40.0, 'longitude': -74.0}
        finish = {'name': 'Finish', 'latitude': 40.0, 'longitude': -88.0}

        res = optimizer.optimize(
            candidates=candidates,
            total_distance_miles=900.0,
            start_location=start,
            finish_location=finish
        )

        assert res['number_of_stops'] >= 1
        assert res['total_fuel_consumed_gallons'] == 90.0
        # The optimizer should pick the cheap stop (ID 2, $2.80) over ID 1 ($4.50)
        stop_ids = [s['truckstop_id'] for s in res['fuel_stops']]
        assert 2 in stop_ids

    def test_long_trip_max_range_constraint(self):
        optimizer = FuelOptimizer(max_range_miles=500.0, mpg=10.0)
        # Create a series of stations every 200 miles up to 2,000 miles
        candidates = []
        for d in range(200, 2000, 200):
            candidates.append({
                'truckstop_id': d,
                'name': f'Stop at {d}',
                'address': f'{d} Hwy',
                'city': f'City_{d}',
                'state': 'US',
                'latitude': 35.0,
                'longitude': -100.0 + (d / 100.0),
                'retail_price': 3.00 if d % 400 == 0 else 3.50,
                'route_dist_miles': float(d)
            })

        start = {'name': 'Start', 'latitude': 35.0, 'longitude': -100.0}
        finish = {'name': 'Finish', 'latitude': 35.0, 'longitude': -80.0}

        res = optimizer.optimize(
            candidates=candidates,
            total_distance_miles=2000.0,
            start_location=start,
            finish_location=finish
        )

        assert res['number_of_stops'] >= 4
        # Verify no leg exceeds 500 miles
        stops = res['fuel_stops']
        for i in range(len(stops)):
            if i == 0:
                assert stops[i]['mile_marker'] <= 500.0
            else:
                leg = stops[i]['mile_marker'] - stops[i - 1]['mile_marker']
                assert leg <= 500.0
        # Distance to finish from last stop
        assert 2000.0 - stops[-1]['mile_marker'] <= 500.0
