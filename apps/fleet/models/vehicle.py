from django.contrib.gis.db import models
from django.contrib.postgres.indexes import GinIndex
from django.utils.translation import gettext_lazy as _


class UnitType(models.TextChoices):
    USB = "USB", _("Unidade de Suporte Básico")
    USA = "USA", _("Unidade de Suporte Avançado")
    UR  = "UR",  _("Unidade de Resgate")


class FleetUnit(models.Model):

    class UnitStatus(models.TextChoices):
        AVAILABLE   = "AVAILABLE",   _("Disponível")
        BUSY        = "BUSY",        _("Em Atendimento")
        MAINTENANCE = "MAINTENANCE", _("Em Manutenção")


    name = models.CharField(
        _("nome"),
        max_length=100,
        help_text=_("Ex: Ambulância Alfa-01"),
    )
    license_plate = models.CharField(
        _("placa"),
        max_length=20,
        unique=True,
    )


    unit_type = models.CharField(
        _("tipo de unidade"),
        max_length=3,
        choices=UnitType.choices,
        db_index=True,
        help_text=_(
            "Classificação operacional da viatura (USB / USA / UR). "
            "Primeiro critério de triagem no despacho."
        ),
    )

    current_location = models.PointField(
        _("localização atual"),
        geography=True,
        srid=4326,
        null=True,
        blank=True,
        spatial_index=True,
    )


    status = models.CharField(
        _("status"),
        max_length=20,
        choices=UnitStatus.choices,
        default=UnitStatus.AVAILABLE,
        db_index=True,
    )


    capabilities = models.JSONField(
        _("capacidades"),
        default=dict,
        help_text=_(
            "Capacidades específicas da unidade. "
            'Exemplo: {"uti": true, "oxygen": true, "cardiac_monitor": true, "capacity": 2}'
        ),
    )

    created_at = models.DateTimeField(_("criado em"), auto_now_add=True)
    updated_at = models.DateTimeField(_("atualizado em"), auto_now=True)


    class Meta:
        db_table = "fleet_units"
        verbose_name = _("Unidade de Frota")
        verbose_name_plural = _("Unidades de Frota")
        ordering = ["unit_type", "name"]
        indexes = [
            GinIndex(
                fields=["capabilities"],
                name="capabilities_gin_idx",
                opclasses=["jsonb_path_ops"],
            ),
           
            models.Index(
                fields=["unit_type", "status"],
                name="fleet_type_status_idx",
            ),
        ]


    def __str__(self) -> str:
        return f"[{self.unit_type}] {self.name} — {self.get_status_display()}"

    def has_capability(self, key: str) -> bool:
        """
        Verifica se a unidade possui uma capacidade específica.

            if unit.has_capability("cardiac_monitor"):
                dispatch(unit)
        """
        return bool(self.capabilities.get(key, False))

    def is_available(self) -> bool:
        return self.status == self.UnitStatus.AVAILABLE