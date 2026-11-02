from django.urls import path
from .views import (
    LoginView,
    MeView,
    PasswordChangeView,
    RefreshView,
    UserActivateView,
    UserDeactivateView,
    UserDetailView,
    UserListView,
    UserRoleView,
)
app_name = 'authentication'
urlpatterns = [
    path('login/', LoginView.as_view(), name='login'),
    path('refresh/', RefreshView.as_view(), name='refresh'),
    path('me/', MeView.as_view(), name='me'),
    path('me/password/', PasswordChangeView.as_view(), name='password-change'),
    path('users/', UserListView.as_view(), name='users'),
    path('users/<int:user_id>/', UserDetailView.as_view(), name='user-detail'),
    path('users/<int:user_id>/role/', UserRoleView.as_view(), name='user-role'),
    path('users/<int:user_id>/activate/', UserActivateView.as_view(), name='user-activate'),
    path('users/<int:user_id>/deactivate/', UserDeactivateView.as_view(), name='user-deactivate'),
]
