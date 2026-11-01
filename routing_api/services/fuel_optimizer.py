import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class FuelOptimizer:
    """
    Mathematical Dynamic Programming (DP) optimizer for the Minimum-Cost
    Vehicle Fueling Problem along a 1D highway route corridor.
    Guarantees that at no point does distance between refueling exceed max_range.
    """

    def __init__(
        self,
        max_range_miles: float = 500.0,
        mpg: float = 10.0,
        stop_penalty: float = 0.5
    ):
        self.max_range = float(max_range_miles)
        self.mpg = float(mpg)
        self.tank_capacity = self.max_range / self.mpg  # e.g. 50 gallons
        self.stop_penalty = float(stop_penalty)

    def optimize(
        self,
        candidates: List[Dict[str, Any]],
        total_distance_miles: float,
        start_location: Dict[str, Any],
        finish_location: Dict[str, Any],
        start_full_tank: bool = True
    ) -> Dict[str, Any]:
        """
        Computes the optimal sequence of fuel stops minimizing total fuel cost.
        """
        # If trip is 0 or negative
        if total_distance_miles <= 0:
            return {
                'fuel_stops': [],
                'total_fuel_cost': 0.0,
                'total_fuel_consumed_gallons': 0.0,
                'total_fuel_purchased_gallons': 0.0,
                'average_price_per_gallon': 0.0,
                'number_of_stops': 0,
            }

        total_consumed = round(total_distance_miles / self.mpg, 2)

        # Edge case: trip distance is within initial full tank range
        if start_full_tank and total_distance_miles <= self.max_range:
            # Trip can be completed without any refueling stops!
            # We can optionally find the cheapest station along route if the driver wishes to replenish
            cheapest_station = None
            if candidates:
                cheapest_station = min(candidates, key=lambda s: s['retail_price'])
                refill_cost = round(total_consumed * cheapest_station['retail_price'], 2)
            else:
                refill_cost = 0.0

            return {
                'fuel_stops': [],
                'total_fuel_cost': 0.0,
                'total_fuel_consumed_gallons': total_consumed,
                'total_fuel_purchased_gallons': 0.0,
                'average_price_per_gallon': round(cheapest_station['retail_price'], 3) if cheapest_station else 0.0,
                'number_of_stops': 0,
                'message': (
                    f"Trip distance ({total_distance_miles:.1f} miles) is within vehicle's single-tank range "
                    f"({self.max_range:.0f} miles). No intermediate fuel stops required."
                )
            }

        # Filter and deduplicate candidates within route bounds
        filtered_candidates = [
            c for c in candidates
            if 0.0 < c['route_dist_miles'] < total_distance_miles
        ]

        # Deduplicate stations that are very close (e.g. < 3 miles apart) by keeping cheapest
        deduped = []
        for c in sorted(filtered_candidates, key=lambda x: x['route_dist_miles']):
            if not deduped:
                deduped.append(c)
            else:
                prev = deduped[-1]
                if abs(c['route_dist_miles'] - prev['route_dist_miles']) < 2.0:
                    # Same exit / interchange: keep cheaper
                    if c['retail_price'] < prev['retail_price']:
                        deduped[-1] = c
                else:
                    deduped.append(c)

        # Build Graph Nodes:
        # Node 0: Origin (mile 0)
        # Node 1..M: candidate stops
        # Node M+1: Destination (mile total_distance_miles)
        nodes = [{
            'id': 0,
            'name': start_location.get('name', 'Origin'),
            'city': 'Origin',
            'state': '',
            'latitude': start_location.get('latitude', 0.0),
            'longitude': start_location.get('longitude', 0.0),
            'retail_price': 0.0,
            'route_dist_miles': 0.0,
            'is_station': False,
        }]

        for c in deduped:
            nodes.append({
                'id': c['truckstop_id'],
                'name': c['name'],
                'address': c['address'],
                'city': c['city'],
                'state': c['state'],
                'latitude': c['latitude'],
                'longitude': c['longitude'],
                'retail_price': c['retail_price'],
                'route_dist_miles': c['route_dist_miles'],
                'is_station': True,
            })

        nodes.append({
            'id': -1,
            'name': finish_location.get('name', 'Destination'),
            'city': 'Destination',
            'state': '',
            'latitude': finish_location.get('latitude', 0.0),
            'longitude': finish_location.get('longitude', 0.0),
            'retail_price': 0.0,
            'route_dist_miles': total_distance_miles,
            'is_station': False,
        })

        N = len(nodes)
        dp = [float('inf')] * N
        parent = [-1] * N
        leg_gallons = [0.0] * N
        dp[0] = 0.0

        # DP on DAG
        for i in range(N):
            if dp[i] == float('inf'):
                continue
            curr_dist = nodes[i]['route_dist_miles']

            for j in range(i + 1, N):
                next_dist = nodes[j]['route_dist_miles']
                dist_diff = next_dist - curr_dist

                if dist_diff > self.max_range:
                    # Stations are ordered by distance; no further station is reachable
                    break

                if dist_diff < 0.1:
                    continue

                gallons = dist_diff / self.mpg

                # Cost calculation:
                # When moving from i to j:
                # - If j is Destination: the fuel for leg (i -> Dest) was purchased at stop i.
                # - If i is Origin: vehicle started with fuel or replenishes at stop j.
                # In fuel replenishment model: at stop j you replenish the gallons burned on leg (i -> j).
                # At destination, remaining gallons are replenished at last stop's price.
                if j == N - 1:
                    # Final stretch to destination: fueled at station i
                    unit_price = nodes[i]['retail_price'] if i > 0 else 3.10
                    edge_cost = gallons * unit_price
                elif i == 0:
                    # First leg from origin: replenished at stop j
                    unit_price = nodes[j]['retail_price']
                    edge_cost = (gallons * unit_price) + self.stop_penalty
                else:
                    # Intermediate stop: fuel bought at station i (or replenished at station j)
                    unit_price = nodes[i]['retail_price']
                    edge_cost = (gallons * unit_price) + self.stop_penalty

                if dp[i] + edge_cost < dp[j]:
                    dp[j] = dp[i] + edge_cost
                    parent[j] = i
                    leg_gallons[j] = gallons

        # Verify reachability
        if dp[N - 1] == float('inf'):
            # Fallback greedy if discrete DP had a narrow gap
            return self._fallback_greedy_solver(
                deduped, total_distance_miles, start_location, finish_location
            )

        # Reconstruct path
        path_indices = []
        curr = N - 1
        while curr != -1:
            path_indices.append(curr)
            curr = parent[curr]
        path_indices.reverse()

        # Build stops response
        fuel_stops = []
        for step, idx in enumerate(path_indices):
            # Skip origin (idx 0) and destination (idx N-1) as fuel stops
            if idx == 0 or idx == N - 1:
                continue

            prev_idx = path_indices[step - 1]
            next_idx = path_indices[step + 1]

            node = nodes[idx]
            prev_node = nodes[prev_idx]
            next_node = nodes[next_idx]

            leg_from_prev = node['route_dist_miles'] - prev_node['route_dist_miles']
            leg_to_next = next_node['route_dist_miles'] - node['route_dist_miles']

            # At this stop, truck buys fuel for the leg to next_node
            gallons_to_buy = round(leg_to_next / self.mpg, 2)
            cost_at_stop = round(gallons_to_buy * node['retail_price'], 2)

            fuel_stops.append({
                'stop_number': len(fuel_stops) + 1,
                'truckstop_id': node['id'],
                'name': node['name'],
                'address': node.get('address', ''),
                'city': node.get('city', ''),
                'state': node.get('state', ''),
                'latitude': node['latitude'],
                'longitude': node['longitude'],
                'retail_price': node['retail_price'],
                'mile_marker': round(node['route_dist_miles'], 1),
                'distance_from_last_stop': round(leg_from_prev, 1),
                'leg_distance_to_next': round(leg_to_next, 1),
                'gallons_purchased': gallons_to_buy,
                'cost_at_stop': cost_at_stop,
            })

        if fuel_stops:
            # Reconcile fuel accounting:
            # Attribute initial leg (from origin to stop 0) to stop 0
            first_leg = fuel_stops[0]['mile_marker']
            first_leg_gal = round(first_leg / self.mpg, 2)
            fuel_stops[0]['gallons_purchased'] = round(fuel_stops[0]['gallons_purchased'] + first_leg_gal, 2)
            fuel_stops[0]['cost_at_stop'] = round(fuel_stops[0]['gallons_purchased'] * fuel_stops[0]['retail_price'], 2)

            # Reconcile float rounding residual into final stop so:
            # sum(s['gallons_purchased']) == total_consumed == total_trip_gallons
            gal_sum = round(sum(s['gallons_purchased'] for s in fuel_stops), 2)
            gal_residual = round(total_consumed - gal_sum, 2)
            if gal_residual != 0.0:
                fuel_stops[-1]['gallons_purchased'] = round(fuel_stops[-1]['gallons_purchased'] + gal_residual, 2)
                fuel_stops[-1]['cost_at_stop'] = round(fuel_stops[-1]['gallons_purchased'] * fuel_stops[-1]['retail_price'], 2)

            total_trip_cost = round(sum(s['cost_at_stop'] for s in fuel_stops), 2)
            total_trip_gallons = round(sum(s['gallons_purchased'] for s in fuel_stops), 2)
        else:
            total_trip_cost = 0.0
            total_trip_gallons = 0.0

        avg_price = (
            round(total_trip_cost / total_trip_gallons, 3)
            if total_trip_gallons > 0 else 0.0
        )

        return {
            'fuel_stops': fuel_stops,
            'total_fuel_cost': total_trip_cost,
            'total_fuel_consumed_gallons': total_consumed,
            'total_fuel_purchased_gallons': total_trip_gallons,
            'average_price_per_gallon': avg_price,
            'number_of_stops': len(fuel_stops),
        }

    def _fallback_greedy_solver(
        self,
        candidates: List[Dict[str, Any]],
        total_dist: float,
        start_location: Dict[str, Any],
        finish_location: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Fallback greedy strategy if graph has sparse connectivity.
        Selects the cheapest accessible station in each 450-mile horizon.
        If a gap exceeds vehicle max range, selects the nearest reachable station ahead
        and logs a warning.
        """
        fuel_stops = []
        curr_dist = 0.0
        warnings = []
        total_consumed = round(total_dist / self.mpg, 2)

        while curr_dist + self.max_range < total_dist:
            # Candidate window: from curr_dist to curr_dist + max_range
            # Prefer stations in [curr_dist + 200, curr_dist + max_range - 10]
            horizon_stops = [
                s for s in candidates
                if curr_dist < s['route_dist_miles'] <= curr_dist + self.max_range - 10.0
            ]

            if not horizon_stops:
                # Broaden search to max range exactly
                horizon_stops = [
                    s for s in candidates
                    if curr_dist < s['route_dist_miles'] <= curr_dist + self.max_range
                ]

            if not horizon_stops:
                # Gap exceeds max range: find nearest available future station ahead
                future_stops = [s for s in candidates if s['route_dist_miles'] > curr_dist]
                if not future_stops:
                    warnings.append(
                        f"No fuel stations found along the route corridor between mile {curr_dist:.1f} and destination ({total_dist:.1f} miles)."
                    )
                    break
                best_stop = min(future_stops, key=lambda s: s['route_dist_miles'])
                gap = best_stop['route_dist_miles'] - curr_dist
                warnings.append(
                    f"Warning: Station gap of {gap:.1f} miles between mile {curr_dist:.1f} and {best_stop['route_dist_miles']:.1f} "
                    f"exceeds vehicle max range ({self.max_range:.0f} miles). Selected nearest available future station."
                )
            else:
                best_stop = min(horizon_stops, key=lambda s: s['retail_price'])

            leg = best_stop['route_dist_miles'] - curr_dist
            gal = round(leg / self.mpg, 2)
            cost = round(gal * best_stop['retail_price'], 2)

            fuel_stops.append({
                'stop_number': len(fuel_stops) + 1,
                'truckstop_id': best_stop['truckstop_id'],
                'name': best_stop['name'],
                'address': best_stop.get('address', ''),
                'city': best_stop.get('city', ''),
                'state': best_stop.get('state', ''),
                'latitude': best_stop['latitude'],
                'longitude': best_stop['longitude'],
                'retail_price': best_stop['retail_price'],
                'mile_marker': round(best_stop['route_dist_miles'], 1),
                'distance_from_last_stop': round(leg, 1),
                'gallons_purchased': gal,
                'cost_at_stop': cost,
            })
            curr_dist = best_stop['route_dist_miles']

        # Check terminal leg to destination
        rem_dist = total_dist - curr_dist
        if rem_dist > self.max_range:
            warnings.append(
                f"Warning: Terminal leg distance ({rem_dist:.1f} miles) from last fuel stop "
                f"(mile {curr_dist:.1f}) to destination ({total_dist:.1f} miles) exceeds vehicle max range ({self.max_range:.0f} miles)."
            )

        # Attribute remaining leg to destination to the final fuel stop
        if fuel_stops:
            rem_gal = round(rem_dist / self.mpg, 2)
            fuel_stops[-1]['gallons_purchased'] = round(fuel_stops[-1]['gallons_purchased'] + rem_gal, 2)
            fuel_stops[-1]['cost_at_stop'] = round(fuel_stops[-1]['gallons_purchased'] * fuel_stops[-1]['retail_price'], 2)

            # Reconcile float rounding residual into final stop so:
            # sum(s['gallons_purchased']) == total_consumed == total_purchased_gallons
            gal_sum = round(sum(s['gallons_purchased'] for s in fuel_stops), 2)
            gal_residual = round(total_consumed - gal_sum, 2)
            if gal_residual != 0.0:
                fuel_stops[-1]['gallons_purchased'] = round(fuel_stops[-1]['gallons_purchased'] + gal_residual, 2)
                fuel_stops[-1]['cost_at_stop'] = round(fuel_stops[-1]['gallons_purchased'] * fuel_stops[-1]['retail_price'], 2)

            total_cost = round(sum(s['cost_at_stop'] for s in fuel_stops), 2)
            total_gal = round(sum(s['gallons_purchased'] for s in fuel_stops), 2)
        else:
            total_cost = 0.0
            total_gal = 0.0

        avg_price = round(total_cost / total_gal, 3) if total_gal > 0 else 0.0

        result = {
            'fuel_stops': fuel_stops,
            'total_fuel_cost': total_cost,
            'total_fuel_consumed_gallons': total_consumed,
            'total_fuel_purchased_gallons': total_gal,
            'average_price_per_gallon': avg_price,
            'number_of_stops': len(fuel_stops),
        }
        if warnings:
            result['message'] = " ".join(warnings)

        return result
