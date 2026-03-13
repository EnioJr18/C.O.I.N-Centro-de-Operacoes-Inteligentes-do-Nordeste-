from django.db.models.signals import post_save
from django.dispatch import receiver
from .models.mission import Mission
from .models.history import MissionHistory

# 1. O Rádio que toca ANTES de salvar no banco
@receiver(post_save, sender=Mission)
def captura_status_antigo(sender, instance, **kwargrs):
    if instance.id:
        old_mission = Mission.objects.get(id=instance.id)
        instance._old_status = old_mission.status
    else:
        instance._old_status = None
        

# 2. O Rádio que toca DEPOIS de salvar no banco
@receiver(post_save, sender=Mission)
def create_mission_history(sender, instance, created, **kwargs):
    if created:
        MissionHistory.objects.create(
            mission=instance,
            status=instance.status,
            notes="Missão criada"
        )
    else:
        if hasattr(instance, '_old_status') and instance._old_status != instance.status:
            MissionHistory.objects.create(
                mission=instance, 
                status=instance.status, 
                notes=f"Status atualizado de '{instance._old_status}' para '{instance.status}'."
            )