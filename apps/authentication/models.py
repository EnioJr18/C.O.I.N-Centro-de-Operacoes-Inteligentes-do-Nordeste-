from django.conf import settings
from django.db import models


class UserRole(models.TextChoices):
    ADMIN = 'ADMIN', 'Administrador'
    OPERADOR = 'OPERADOR', 'Operador'


class UserProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=10, choices=UserRole.choices, default=UserRole.OPERADOR, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
