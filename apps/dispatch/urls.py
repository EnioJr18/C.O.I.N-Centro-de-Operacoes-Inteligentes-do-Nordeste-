from django.urls import path

from .api_views import (
    DispatchEmergencyAPIView,
    MissionDetailAPIView,
    MissionHistoryListAPIView,
    MissionListAPIView,
)


app_name = 'dispatch'

urlpatterns = [
    path('missions/', MissionListAPIView.as_view(), name='mission_list'),
    path('missions/<int:pk>/', MissionDetailAPIView.as_view(), name='mission_detail'),
    path('missions/<int:pk>/history/', MissionHistoryListAPIView.as_view(), name='mission_history'),
    path('emergencies/dispatch/', DispatchEmergencyAPIView.as_view(), name='dispatch_emergency'),
]
