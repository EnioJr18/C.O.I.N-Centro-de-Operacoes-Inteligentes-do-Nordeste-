from rest_framework.permissions import BasePermission
from .models import UserProfile, UserRole


def user_role(user):
    if user.is_superuser:
        return UserRole.ADMIN
    try:
        return user.profile.role
    except UserProfile.DoesNotExist:
        return None


class IsOperatorOrAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and user_role(request.user) in (UserRole.ADMIN, UserRole.OPERADOR))


class IsAdminRole(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and user_role(request.user) == UserRole.ADMIN)
