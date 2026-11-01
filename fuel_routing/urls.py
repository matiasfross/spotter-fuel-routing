"""
URL configuration for fuel_routing project.
"""

from django.contrib import admin
from django.urls import include, path

from routing_api.views import RouteMapView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('routing_api.urls')),
    # Root path directly renders the interactive map interface
    path('', RouteMapView.as_view(), name='root_map'),
]
