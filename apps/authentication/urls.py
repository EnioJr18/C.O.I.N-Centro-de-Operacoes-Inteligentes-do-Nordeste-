from django.urls import path
from .views import LoginView, MeView, PasswordChangeView, RefreshView, UserListView
app_name = 'authentication'
urlpatterns = [
    path('login/', LoginView.as_view(), name='login'),
    path('refresh/', RefreshView.as_view(), name='refresh'),
    path('me/', MeView.as_view(), name='me'),
    path('me/password/', PasswordChangeView.as_view(), name='password-change'),
    path('users/', UserListView.as_view(), name='users'),
]
