from django.urls import path
from .controllers.dispatch_controller import DispatchEmergencyView

app_name = 'fleet'

urlpatterns = [
    path('api/v1/emergencies/dispatch/', DispatchEmergencyView.as_view(), name='dispatch_emergency')
]

