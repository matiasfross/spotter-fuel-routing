from django.urls import path
from .views import RouteOptimizationView, RouteMapView, HealthCheckView

urlpatterns = [
    path('route/', RouteOptimizationView.as_view(), name='route_optimization'),
    path('route/map/', RouteMapView.as_view(), name='route_map'),
    path('health/', HealthCheckView.as_view(), name='health_check'),
]
