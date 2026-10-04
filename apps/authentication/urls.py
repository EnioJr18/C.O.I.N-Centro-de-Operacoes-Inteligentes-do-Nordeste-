from django.urls import path
from .views import LoginView, RefreshView, MeView, UserListView
app_name = 'authentication'
urlpatterns = [
    path('login/', LoginView.as_view(), name='login'),
    path('refresh/', RefreshView.as_view(), name='refresh'),
    path('me/', MeView.as_view(), name='me'),
    path('users/', UserListView.as_view(), name='users'),
]
