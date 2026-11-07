from django.urls import path

from .api_views import DashboardSummaryAPIView


app_name = 'dashboard'

urlpatterns = [
    path('dashboard/summary/', DashboardSummaryAPIView.as_view(), name='summary'),
]
