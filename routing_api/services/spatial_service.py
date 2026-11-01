import math
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
import pandas as pd
import numpy as np
from scipy.spatial import cKDTree
from django.conf import settings

logger = logging.getLogger(__name__)

EARTH_RADIUS_MILES = 3958.8


def haversine_vectorized(lons1: np.ndarray, lats1: np.ndarray, lons2: np.ndarray, lats2: np.ndarray) -> np.ndarray:
    """
    Vectorized Haversine distance in miles between coordinate arrays.
    """
    dlat = np.radians(lats2 - lats1)
    dlon = np.radians(lons2 - lons1)
    a = (
        np.sin(dlat / 2.0) ** 2
        + np.cos(np.radians(lats1)) * np.cos(np.radians(lats2)) * np.sin(dlon / 2.0) ** 2
    )
    c = 2.0 * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0)))
    return EARTH_RADIUS_MILES * c


class SpatialFuelService:
    """
    Singleton service managing the pre-geocoded fuel stops dataset and
    performing lightning-fast spatial corridor queries (<20ms).
    """

    _instance: Optional['SpatialFuelService'] = None
    _fuel_df: Optional[pd.DataFrame] = None
    _stops_xy: Optional[np.ndarray] = None
    _mean_lat: float = 38.0  # Approx center of continental US
    _cos_lat: float = math.cos(math.radians(38.0))

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SpatialFuelService, cls).__new__(cls)
            cls._instance._initialize_data()
        return cls._instance

    def _initialize_data(self) -> None:
        """
        Loads geocoded CSV and initializes coordinate arrays.
        """
        csv_path = getattr(settings, 'FUEL_STOPS_CSV_PATH', None)
        if not csv_path or not Path(csv_path).exists():
            # Fallback path check
            fallback = Path(settings.BASE_DIR) / 'fuel_stops_geocoded.csv'
            if fallback.exists():
                csv_path = fallback
            else:
                csv_path = Path(settings.BASE_DIR) / 'data' / 'fuel_stops_geocoded.csv'

        logger.info(f"Loading fuel stops dataset from: {csv_path}")
        df = pd.read_csv(csv_path)

        # Ensure valid coords and retail price
        df = df[df['lat'].notna() & df['lon'].notna() & df['Retail Price'].notna()].copy()
        df['Retail Price'] = pd.to_numeric(df['Retail Price'], errors='coerce')
        df = df[df['Retail Price'] > 0.5]  # Filter anomalous non-positive prices

        # Keep minimum price if multiple entries exist for the same truckstop/address
        df = df.sort_values('Retail Price').drop_duplicates(
            subset=['OPIS Truckstop ID', 'City', 'State']
        ).reset_index(drop=True)

        self._fuel_df = df
        logger.info(f"Successfully loaded {len(df)} geocoded US truckstops.")

    def find_candidate_stops_along_route(
        self,
        route_coords: List[List[float]],
        corridor_radius_miles: float = 10.0
    ) -> List[Dict[str, Any]]:
        """
        Given route polyline coordinates [[lon, lat], ...], finds all fuel stops within
        corridor_radius_miles of the route, tagged with their distance along the route.
        """
        if self._fuel_df is None or len(self._fuel_df) == 0:
            self._initialize_data()

        coords_arr = np.array(route_coords)  # [N, 2] -> lon, lat
        N = len(coords_arr)
        if N < 2:
            return []

        # 1. Calculate cumulative distance along polyline segments
        segs = haversine_vectorized(
            coords_arr[:-1, 0], coords_arr[:-1, 1],
            coords_arr[1:, 0], coords_arr[1:, 1]
        )
        cum_dist = np.insert(np.cumsum(segs), 0, 0.0)
        total_route_dist = float(cum_dist[-1])

        # 2. Local equirectangular projection for fast KDTree search
        route_mean_lat = float(np.mean(coords_arr[:, 1]))
        cos_lat = math.cos(math.radians(route_mean_lat))

        # Project coordinates to Cartesian miles: (x: lon * 69.17 * cos(lat), y: lat * 69.17)
        MILES_PER_DEGREE = 69.17
        route_xy = np.column_stack([
            coords_arr[:, 0] * MILES_PER_DEGREE * cos_lat,
            coords_arr[:, 1] * MILES_PER_DEGREE
        ])

        stops_lon = self._fuel_df['lon'].values
        stops_lat = self._fuel_df['lat'].values
        stops_xy = np.column_stack([
            stops_lon * MILES_PER_DEGREE * cos_lat,
            stops_lat * MILES_PER_DEGREE
        ])

        # Build KDTree on the route coordinates
        route_tree = cKDTree(route_xy)

        # Query distances from each fuel stop to the nearest point on the route polyline
        dists_miles, nearest_idx = route_tree.query(stops_xy, distance_upper_bound=corridor_radius_miles)
        valid_mask = dists_miles < corridor_radius_miles

        valid_stops = self._fuel_df[valid_mask].copy()
        if len(valid_stops) == 0:
            return []

        matched_indices = nearest_idx[valid_mask]
        valid_stops['route_dist_miles'] = cum_dist[matched_indices]
        valid_stops['off_route_miles'] = dists_miles[valid_mask]

        # Filter out any station projected beyond total route distance
        valid_stops = valid_stops[valid_stops['route_dist_miles'] <= total_route_dist]

        # Sort by route distance
        valid_stops = valid_stops.sort_values('route_dist_miles').reset_index(drop=True)

        # Convert to list of dictionaries
        candidates = []
        for _, row in valid_stops.iterrows():
            candidates.append({
                'truckstop_id': int(row['OPIS Truckstop ID']),
                'name': str(row['Truckstop Name']).strip(),
                'address': str(row['Address']).strip(),
                'city': str(row['City']).strip(),
                'state': str(row['State']).strip(),
                'latitude': float(row['lat']),
                'longitude': float(row['lon']),
                'retail_price': round(float(row['Retail Price']), 3),
                'route_dist_miles': round(float(row['route_dist_miles']), 2),
                'off_route_miles': round(float(row['off_route_miles']), 2),
            })

        return candidates
