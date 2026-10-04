from django.shortcuts import get_object_or_404

from .models.history import MissionHistory
from .models.mission import Mission


def get_missions(status=None, created_after=None, created_before=None):
    queryset = Mission.objects.select_related('assigned_unit').all()
    if status:
        queryset = queryset.filter(status=status)
    if created_after:
        queryset = queryset.filter(created_at__gte=created_after)
    if created_before:
        queryset = queryset.filter(created_at__lte=created_before)
    return queryset.order_by('-created_at')


def get_mission_or_404(mission_id):
    return get_object_or_404(get_missions(), pk=mission_id)


def get_mission_history(mission_id):
    mission = get_mission_or_404(mission_id)
    return MissionHistory.objects.filter(mission=mission).select_related('mission')
