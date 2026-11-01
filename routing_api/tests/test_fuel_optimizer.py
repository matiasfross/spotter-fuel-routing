import pytest
from django.test import SimpleTestCase
from routing_api.services.fuel_optimizer import FuelOptimizer


class TestFuelOptimizer(SimpleTestCase):

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

    def test_fuel_accounting_reconciliation_dp(self):
        optimizer = FuelOptimizer(max_range_miles=500.0, mpg=10.0, stop_penalty=0.5)
        candidates = [
            {'truckstop_id': 101, 'name': 'Stop 1', 'address': '101 Rd', 'city': 'City1', 'state': 'OH',
             'latitude': 40.0, 'longitude': -80.0, 'retail_price': 3.15, 'route_dist_miles': 350.0},
            {'truckstop_id': 102, 'name': 'Stop 2', 'address': '102 Rd', 'city': 'City2', 'state': 'IN',
             'latitude': 40.0, 'longitude': -84.0, 'retail_price': 2.95, 'route_dist_miles': 700.0},
            {'truckstop_id': 103, 'name': 'Stop 3', 'address': '103 Rd', 'city': 'City3', 'state': 'IL',
             'latitude': 40.0, 'longitude': -88.0, 'retail_price': 3.20, 'route_dist_miles': 1050.0},
        ]
        start = {'name': 'Origin', 'latitude': 40.0, 'longitude': -75.0}
        finish = {'name': 'Destination', 'latitude': 40.0, 'longitude': -92.0}

        res = optimizer.optimize(
            candidates=candidates,
            total_distance_miles=1200.0,
            start_location=start,
            finish_location=finish,
        )

        assert res['number_of_stops'] >= 2
        stops = res['fuel_stops']

        # Reconciled accounting checks
        sum_cost = round(sum(s['cost_at_stop'] for s in stops), 2)
        assert sum_cost == res['total_fuel_cost']

        sum_gal = round(sum(s['gallons_purchased'] for s in stops), 2)
        assert sum_gal == res['total_fuel_consumed_gallons']
        assert sum_gal == res['total_fuel_purchased_gallons']
        assert res['total_fuel_consumed_gallons'] == 120.0

        # Initial leg is attributed to stop 0
        first_leg_gal = round(stops[0]['mile_marker'] / 10.0, 2)
        assert stops[0]['gallons_purchased'] >= first_leg_gal

    def test_sparse_corridor_greedy_fallback(self):
        optimizer = FuelOptimizer(max_range_miles=500.0, mpg=10.0, stop_penalty=0.5)
        # Sparse corridor: first station is at mile 592.0 (> 500 max range)
        candidates = [
            {'truckstop_id': 201, 'name': 'Station Nevada', 'address': 'I-80 W', 'city': 'Winnemucca', 'state': 'NV',
             'latitude': 40.9, 'longitude': -117.7, 'retail_price': 3.75, 'route_dist_miles': 592.0},
            {'truckstop_id': 202, 'name': 'Station Utah', 'address': 'I-80 E', 'city': 'Salt Lake', 'state': 'UT',
             'latitude': 40.7, 'longitude': -111.9, 'retail_price': 3.25, 'route_dist_miles': 1050.0},
            {'truckstop_id': 203, 'name': 'Station Wyoming', 'address': 'I-80 E', 'city': 'Cheyenne', 'state': 'WY',
             'latitude': 41.1, 'longitude': -104.8, 'retail_price': 3.10, 'route_dist_miles': 1500.0},
        ]
        start = {'name': 'San Francisco, CA', 'latitude': 37.77, 'longitude': -122.41}
        finish = {'name': 'Omaha, NE', 'latitude': 41.25, 'longitude': -95.93}

        res = optimizer.optimize(
            candidates=candidates,
            total_distance_miles=1900.0,
            start_location=start,
            finish_location=finish,
        )

        assert res['number_of_stops'] > 0
        assert res['fuel_stops'][0]['mile_marker'] == 592.0
        assert 'message' in res
        assert 'exceeds vehicle max range' in res['message']

        # Accounting reconciliation holds in fallback
        sum_cost = round(sum(s['cost_at_stop'] for s in res['fuel_stops']), 2)
        assert sum_cost == res['total_fuel_cost']
        sum_gal = round(sum(s['gallons_purchased'] for s in res['fuel_stops']), 2)
        assert sum_gal == res['total_fuel_consumed_gallons']
        assert sum_gal == res['total_fuel_purchased_gallons']
        assert res['total_fuel_consumed_gallons'] == 190.0

    def test_terminal_leg_warning_greedy_fallback(self):
        optimizer = FuelOptimizer(max_range_miles=500.0, mpg=10.0, stop_penalty=0.5)
        # Station at 400.0, finish at 1000.0 -> terminal leg = 600 miles (> 500 max range)
        candidates = [
            {'truckstop_id': 301, 'name': 'Station Mid', 'address': 'Route 66', 'city': 'Midtown', 'state': 'OK',
             'latitude': 35.5, 'longitude': -97.5, 'retail_price': 3.10, 'route_dist_miles': 400.0},
        ]
        start = {'name': 'Start', 'latitude': 35.0, 'longitude': -100.0}
        finish = {'name': 'Finish', 'latitude': 35.0, 'longitude': -80.0}

        res = optimizer.optimize(
            candidates=candidates,
            total_distance_miles=1000.0,
            start_location=start,
            finish_location=finish,
        )

        assert res['number_of_stops'] == 1
        assert 'Terminal leg distance' in res.get('message', '')
        sum_cost = round(sum(s['cost_at_stop'] for s in res['fuel_stops']), 2)
        assert sum_cost == res['total_fuel_cost']
        sum_gal = round(sum(s['gallons_purchased'] for s in res['fuel_stops']), 2)
        assert sum_gal == res['total_fuel_consumed_gallons']
        assert sum_gal == res['total_fuel_purchased_gallons']
        assert res['total_fuel_consumed_gallons'] == 100.0

    def test_stop_penalty_prevents_redundant_clustered_stops(self):
        # 600-mile trip: 1 stop needed
        # Station A at mile 300 ($3.00), Station B at mile 310 ($2.99)
        # With stop_penalty = 0.5, driver won't stop at both for negligible price diff
        candidates = [
            {'truckstop_id': 401, 'name': 'Stop A', 'address': 'A', 'city': 'A', 'state': 'OH',
             'latitude': 40.0, 'longitude': -80.0, 'retail_price': 3.00, 'route_dist_miles': 300.0},
            {'truckstop_id': 402, 'name': 'Stop B', 'address': 'B', 'city': 'B', 'state': 'OH',
             'latitude': 40.0, 'longitude': -80.2, 'retail_price': 2.99, 'route_dist_miles': 310.0},
        ]
        start = {'name': 'Start', 'latitude': 40.0, 'longitude': -75.0}
        finish = {'name': 'Finish', 'latitude': 40.0, 'longitude': -85.0}

        optimizer = FuelOptimizer(max_range_miles=500.0, mpg=10.0, stop_penalty=0.5)
        res = optimizer.optimize(
            candidates=candidates,
            total_distance_miles=600.0,
            start_location=start,
            finish_location=finish,
        )

        assert res['number_of_stops'] == 1
