from django.db import models
from django.contrib.gis.db import models as gis_models

class Mission(models.Model):
    class MissionStatus(models.TextChoices):
        PENDENTE = 'Pendente', 'Pendente'
        EM_ANDAMENTO = 'Em Andamento', 'Em Andamento'
        CONCLUIDA = 'Concluída', 'Concluída'
        CANCELADA = 'Cancelada', 'Cancelada'

    description = models.TextField()
    location = gis_models.PointField(srid=4326)
    status = models.CharField(max_length=20, choices=MissionStatus.choices, default=MissionStatus.PENDENTE)
    
    assigned_unit = models.ForeignKey(
        'fleet.FleetUnit',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='missions'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Mission {self.id} - {self.status}"