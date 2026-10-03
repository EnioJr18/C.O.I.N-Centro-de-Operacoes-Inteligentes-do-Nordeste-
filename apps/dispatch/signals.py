from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from .models.mission import Mission
from .models.history import MissionHistory

@receiver(pre_save, sender=Mission)
def capture_previous_status(sender, instance, **kwargs):
    if not instance.pk:
        instance._previous_status = None
        return

    instance._previous_status = (
        sender.objects.filter(pk=instance.pk)
        .values_list("status", flat=True)
        .first()
    )


@receiver(post_save, sender=Mission)
def create_mission_history(sender, instance, created, **kwargs):
    if created:
        MissionHistory.objects.create(
            mission=instance,
            status=instance.status,
            notes="Missão criada"
        )
    elif instance._previous_status != instance.status:
        MissionHistory.objects.create(
            mission=instance,
            status=instance.status,
            notes=(
                f"Status atualizado de '{instance._previous_status}' "
                f"para '{instance.status}'."
            ),
        )
