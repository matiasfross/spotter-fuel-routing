from rest_framework import serializers


class RouteRequestSerializer(serializers.Serializer):
    """
    Serializer validating incoming route request parameters.
    Supports either string queries (e.g. "New York, NY" or "40.7128,-74.0060")
    or structured objects/arrays.
    """
    start = serializers.JSONField(
        required=True,
        help_text="Starting location: city/state string (e.g. 'New York, NY') or coordinates ('40.7128,-74.0060' or [40.7128, -74.0060])"
    )
    finish = serializers.JSONField(
        required=True,
        help_text="Finish location: city/state string (e.g. 'Los Angeles, CA') or coordinates ('34.0522,-118.2437' or [34.0522, -118.2437])"
    )
    max_range = serializers.FloatField(
        required=False,
        default=500.0,
        min_value=50.0,
        max_value=2000.0,
        help_text="Maximum vehicle range on a single tank in miles (default: 500 miles)"
    )
    mpg = serializers.FloatField(
        required=False,
        default=10.0,
        min_value=1.0,
        max_value=100.0,
        help_text="Vehicle fuel efficiency in miles per gallon (default: 10 mpg)"
    )
    corridor_radius = serializers.FloatField(
        required=False,
        default=10.0,
        min_value=1.0,
        max_value=50.0,
        help_text="Search radius in miles along the highway corridor to look for truckstops (default: 10 miles)"
    )

    def validate_start(self, value):
        if value is None or (isinstance(value, str) and not value.strip()):
            raise serializers.ValidationError("Location input cannot be empty.")
        return value

    def validate_finish(self, value):
        if value is None or (isinstance(value, str) and not value.strip()):
            raise serializers.ValidationError("Location input cannot be empty.")
        return value


class LocationSerializer(serializers.Serializer):
    name = serializers.CharField()
    latitude = serializers.FloatField()
    longitude = serializers.FloatField()


class FuelStopSerializer(serializers.Serializer):
    stop_number = serializers.IntegerField()
    truckstop_id = serializers.IntegerField()
    name = serializers.CharField()
    address = serializers.CharField(allow_blank=True)
    city = serializers.CharField()
    state = serializers.CharField()
    latitude = serializers.FloatField()
    longitude = serializers.FloatField()
    retail_price = serializers.FloatField()
    mile_marker = serializers.FloatField()
    distance_from_last_stop = serializers.FloatField()
    gallons_purchased = serializers.FloatField()
    cost_at_stop = serializers.FloatField()


class RouteSummarySerializer(serializers.Serializer):
    total_distance_miles = serializers.FloatField()
    estimated_duration_hours = serializers.FloatField()
    vehicle_max_range_miles = serializers.FloatField()
    vehicle_mpg = serializers.FloatField()
    total_fuel_consumed_gallons = serializers.FloatField()
    total_fuel_purchased_gallons = serializers.FloatField()
    total_fuel_cost_dollars = serializers.FloatField()
    average_fuel_price_dollars = serializers.FloatField()
    number_of_fuel_stops = serializers.IntegerField()


class RouteResponseSerializer(serializers.Serializer):
    origin = LocationSerializer()
    destination = LocationSerializer()
    summary = RouteSummarySerializer()
    fuel_stops = FuelStopSerializer(many=True)
    map_geojson = serializers.DictField()
    map_url = serializers.CharField()
