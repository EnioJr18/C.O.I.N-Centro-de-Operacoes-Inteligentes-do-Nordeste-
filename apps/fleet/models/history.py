from django.conf import settings
from django.db import models

from .vehicle import FleetUnit


class FleetUnitHistory(models.Model):
    class Action(models.TextChoices):
        UNIT_CREATED = 'UNIT_CREATED', 'Unidade criada'
        UNIT_UPDATED = 'UNIT_UPDATED', 'Unidade atualizada'
        UNIT_MAINTENANCE_STARTED = 'UNIT_MAINTENANCE_STARTED', 'Manutenção iniciada'
        UNIT_MAINTENANCE_ENDED = 'UNIT_MAINTENANCE_ENDED', 'Manutenção encerrada'

    unit = models.ForeignKey(
        FleetUnit,
        on_delete=models.PROTECT,
        related_name='history',
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='fleet_unit_history_entries',
    )
    action = models.CharField(max_length=32, choices=Action.choices)
    previous_status = models.CharField(
        max_length=20,
        choices=FleetUnit.UnitStatus.choices,
        null=True,
        blank=True,
    )
    new_status = models.CharField(
        max_length=20,
        choices=FleetUnit.UnitStatus.choices,
        null=True,
        blank=True,
    )
    changed_fields = models.JSONField(default=list, blank=True)
    request_id = models.CharField(max_length=36)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at', '-id')
        indexes = [
            models.Index(
                fields=('unit', '-created_at', '-id'),
                name='fleet_history_unit_time_idx',
            ),
        ]

    def __str__(self):
        return f'{self.unit_id} - {self.action}'
