from django.contrib.gis.db import models
from django.db.models import JSONField
from django.contrib.postgres.indexes import GinIndex


class FleetUnit(models.Model):
    class UnitStatus(models.TextChoices):
        AVAILABLE = 'AVAILABLE', 'Disponível'
        BUSY = 'BUSY', 'Em Atendimento'
        MAINTENANCE = 'MAINTENANCE', 'Em Manutenção'

    name = models.CharField(max_length=100, help_text="Ex: Ambulância Alfa-01")
    license_plate = models.CharField(max_length=20, unique=True)
    
    # SRID 4326 é o padrão WGS84 (GPS global)
    current_location = models.PointField(
        geography=True, 
        srid=4326, 
        null=True, 
        blank=True,
        spatial_index=True # Crucial para buscas rápidas de raio
    )
    
    status = models.CharField(
        max_length=20, 
        choices=UnitStatus.choices, 
        default=UnitStatus.AVAILABLE
    )
    
    capabilities = JSONField(
        default=dict, 
        help_text="Ex: {'uti': true, 'oxygen': true, 'capacity': 2}"
    )

    class Meta:
        db_table = 'fleet_units'
        indexes = [
            GinIndex(fields=['capabilities'], name='capabilities_idx', opclasses=['jsonb_path_ops']),
        ]

    def __str__(self):
        return f"{self.name} - {self.get_status_display()}"