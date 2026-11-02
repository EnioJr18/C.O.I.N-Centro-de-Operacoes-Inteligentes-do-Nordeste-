from django.conf import settings
from django.db import models


class UserRole(models.TextChoices):
    ADMIN = 'ADMIN', 'Administrador'
    OPERADOR = 'OPERADOR', 'Operador'


class UserProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=10, choices=UserRole.choices, default=UserRole.OPERADOR, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)


class UserAdministrationAction(models.TextChoices):
    USER_CREATED = 'USER_CREATED', 'Usuário criado'
    PROFILE_UPDATED = 'PROFILE_UPDATED', 'Perfil atualizado'
    ROLE_CHANGED = 'ROLE_CHANGED', 'Papel alterado'
    USER_ACTIVATED = 'USER_ACTIVATED', 'Usuário ativado'
    USER_DEACTIVATED = 'USER_DEACTIVATED', 'Usuário desativado'


class UserAdministrationEvent(models.Model):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='user_administration_events_performed',
    )
    target = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='user_administration_events_received',
    )
    action = models.CharField(max_length=32, choices=UserAdministrationAction.choices)
    previous_role = models.CharField(max_length=10, choices=UserRole.choices, null=True, blank=True)
    new_role = models.CharField(max_length=10, choices=UserRole.choices, null=True, blank=True)
    previous_is_active = models.BooleanField(null=True, blank=True)
    new_is_active = models.BooleanField(null=True, blank=True)
    changed_fields = models.JSONField(default=list, blank=True)
    request_id = models.CharField(max_length=36)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ('-created_at', '-id')
