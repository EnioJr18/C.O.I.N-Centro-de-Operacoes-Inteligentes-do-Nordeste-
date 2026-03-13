from django.db import models
from .mission import Mission


class MissionHistory(models.Model):
    # Relacionamento com a Missão.
    mission = models.ForeignKey(
        Mission,
        on_delete=models.CASCADE,
        related_name='history'
    )

    status = models.CharField(
        max_length=20,
        choices=Mission.MissionStatus.choices
    )

    # Campo livre para anotações (ex: "Ambulância pneu furou, reatribuindo")
    notes = models.TextField(blank=True, null=True)

    # O momento exato em que o evento ocorreu
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Ordena do evento mais recente para o mais antigo por padrão
        ordering = ['-timestamp']
        db_table = 'mission_history'

    def __str__(self):
        return f"Missão {self.mission.id} -> {self.status}"
