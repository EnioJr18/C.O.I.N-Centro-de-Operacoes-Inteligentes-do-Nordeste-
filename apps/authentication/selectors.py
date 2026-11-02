from django.contrib.auth import get_user_model
from django.db.models import Q
from django.shortcuts import get_object_or_404

from .models import UserRole


User = get_user_model()

ORDERING_FIELDS = {
    'date_joined': 'date_joined',
    '-date_joined': '-date_joined',
    'id': 'id',
    '-id': '-id',
    'username': 'username',
    '-username': '-username',
    'first_name': 'first_name',
    '-first_name': '-first_name',
    'last_name': 'last_name',
    '-last_name': '-last_name',
}


def get_users(*, search='', role=None, is_active=None, ordering=None):
    queryset = User.objects.select_related('profile').all()
    if search:
        queryset = queryset.filter(
            Q(first_name__icontains=search)
            | Q(last_name__icontains=search)
            | Q(email__icontains=search)
            | Q(username__icontains=search)
        )
    if role == UserRole.ADMIN:
        queryset = queryset.filter(Q(is_superuser=True) | Q(profile__role=UserRole.ADMIN))
    elif role == UserRole.OPERADOR:
        queryset = queryset.filter(is_superuser=False, profile__role=UserRole.OPERADOR)
    if is_active is not None:
        queryset = queryset.filter(is_active=is_active)
    if ordering:
        return queryset.order_by(ORDERING_FIELDS[ordering], '-id')
    return queryset.order_by('-date_joined', '-id')


def get_user_or_404(user_id):
    return get_object_or_404(User.objects.select_related('profile'), pk=user_id)
