from django.urls import path
from .api_views import (
    FleetUnitDetailAPIView,
    FleetUnitHistoryListAPIView,
    FleetUnitListAPIView,
    FleetUnitMaintenanceAPIView,
)
from .controllers.dispatch_controller import DispatchEmergencyView

app_name = 'fleet'

urlpatterns = [
    path('fleet/units/', FleetUnitListAPIView.as_view(), name='fleet_unit_list'),
    path('fleet/units/<int:pk>/', FleetUnitDetailAPIView.as_view(), name='fleet_unit_detail'),
    path('fleet/units/<int:pk>/maintenance/', FleetUnitMaintenanceAPIView.as_view(), name='fleet_unit_maintenance'),
    path('fleet/units/<int:pk>/history/', FleetUnitHistoryListAPIView.as_view(), name='fleet_unit_history'),
    path('emergencies/dispatch/', DispatchEmergencyView.as_view(), name='dispatch_emergency'),
]

