from django.urls import path

from .api_views import (
    CancelMissionAPIView,
    CompleteMissionAPIView,
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
    path('missions/<int:pk>/complete/', CompleteMissionAPIView.as_view(), name='mission_complete'),
    path('missions/<int:pk>/cancel/', CancelMissionAPIView.as_view(), name='mission_cancel'),
    path('emergencies/dispatch/', DispatchEmergencyAPIView.as_view(), name='dispatch_emergency'),
]
