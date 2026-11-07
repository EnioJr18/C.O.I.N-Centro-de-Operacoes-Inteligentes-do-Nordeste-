from django.db.models import Count, Q
from django.utils import timezone

from dispatch.models.mission import Mission
from fleet.models.vehicle import FleetUnit


RECENT_MISSIONS_LIMIT = 5


def get_dashboard_summary():
    fleet_counts = FleetUnit.objects.aggregate(
        total=Count('id'),
        available=Count('id', filter=Q(status=FleetUnit.UnitStatus.AVAILABLE)),
        busy=Count('id', filter=Q(status=FleetUnit.UnitStatus.BUSY)),
        maintenance=Count('id', filter=Q(status=FleetUnit.UnitStatus.MAINTENANCE)),
        with_location=Count('id', filter=Q(current_location__isnull=False)),
    )
    mission_counts = Mission.objects.aggregate(
        total=Count('id'),
        pending=Count('id', filter=Q(status=Mission.MissionStatus.PENDENTE)),
        in_progress=Count('id', filter=Q(status=Mission.MissionStatus.EM_ANDAMENTO)),
        completed=Count('id', filter=Q(status=Mission.MissionStatus.CONCLUIDA)),
        cancelled=Count('id', filter=Q(status=Mission.MissionStatus.CANCELADA)),
    )
    recent_missions = list(
        Mission.objects.select_related('assigned_unit')
        .order_by('-created_at', '-id')[:RECENT_MISSIONS_LIMIT]
    )

    total = fleet_counts['total']
    available = fleet_counts['available']
    return {
        'generated_at': timezone.now(),
        'fleet': {
            'total': total,
            'available': available,
            'availability_percentage': round((available / total) * 100, 1) if total else 0.0,
            'with_location': fleet_counts['with_location'],
            'without_location': total - fleet_counts['with_location'],
            'by_status': {
                FleetUnit.UnitStatus.AVAILABLE: available,
                FleetUnit.UnitStatus.BUSY: fleet_counts['busy'],
                FleetUnit.UnitStatus.MAINTENANCE: fleet_counts['maintenance'],
            },
        },
        'missions': {
            'total': mission_counts['total'],
            'by_status': {
                Mission.MissionStatus.PENDENTE: mission_counts['pending'],
                Mission.MissionStatus.EM_ANDAMENTO: mission_counts['in_progress'],
                Mission.MissionStatus.CONCLUIDA: mission_counts['completed'],
                Mission.MissionStatus.CANCELADA: mission_counts['cancelled'],
            },
            'recent': recent_missions,
        },
    }
