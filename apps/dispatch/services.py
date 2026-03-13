from django.db import transaction
from django.contrib.gis.geos import Point
from fleet.models.vehicle import FleetUnit
from .models.mission import Mission
from .models.history import MissionHistory


def _format_mission_dict(mission):
    """Função interna para padronizar a saída de dados (Selector)"""
    return {
        "id": mission.id,
        "description": mission.description,
        "status": mission.status,
        "location": {
            "latitude": mission.location.y,
            "longitude": mission.location.x
        },
        "assigned_unit": {
            "id": mission.assigned_unit.id,
            "name": mission.assigned_unit.name
        } if mission.assigned_unit else None,
        "created_at": mission.created_at,
        "updated_at": mission.updated_at
    }


def create_mission(description, latitude, longitude):
    location = Point(longitude, latitude, srid=4326)
    return Mission.objects.create(description=description, location=location)

def assign_unit_to_mission(mission, fleet_unit_id):
    """Blindado contra concorrência usando Atomicidade e Lock"""
    with transaction.atomic():
        # Bloqueia a viatura no banco até o fim do 'with'
        fleet_unit = FleetUnit.objects.select_for_update().get(id=fleet_unit_id)
        
        if fleet_unit.status != FleetUnit.UnitStatus.AVAILABLE:
            raise ValueError("Viatura não está disponível.")
        
        # Atualiza Viatura
        fleet_unit.status = FleetUnit.UnitStatus.BUSY
        fleet_unit.save()
        
        # Atualiza Missão
        mission.assigned_unit = fleet_unit
        mission.status = Mission.MissionStatus.EM_ANDAMENTO
        mission.save()
        
        return mission

def complete_mission(mission):
    if mission.status != Mission.MissionStatus.EM_ANDAMENTO:
        raise ValueError("Apenas missões em andamento podem ser concluídas.")
    
    with transaction.atomic():
        mission.status = Mission.MissionStatus.CONCLUIDA
        mission.save()
        
        if mission.assigned_unit:
            unit = mission.assigned_unit
            unit.status = FleetUnit.UnitStatus.AVAILABLE
            unit.save()

def cancel_mission(mission):
    valid_status = [Mission.MissionStatus.PENDENTE, Mission.MissionStatus.EM_ANDAMENTO]
    if mission.status not in valid_status:
        raise ValueError("Esta missão não pode mais ser cancelada.")
    
    with transaction.atomic():
        mission.status = Mission.MissionStatus.CANCELADA
        mission.save()
        
        if mission.assigned_unit:
            unit = mission.assigned_unit
            unit.status = FleetUnit.UnitStatus.AVAILABLE
            unit.save()


def get_mission_details(mission_id):
    mission = Mission.objects.select_related('assigned_unit').filter(id=mission_id).first()
    return _format_mission_dict(mission) if mission else None

def list_missions(status=None):
    query = Mission.objects.select_related('assigned_unit').all()
    if status:
        query = query.filter(status=status)
    return [_format_mission_dict(m) for m in query]

def get_mission_history(mission_id):
    history = MissionHistory.objects.filter(mission_id=mission_id).order_by('-timestamp')
    return [
        {
            "status": record.status,
            "timestamp": record.timestamp,
            "notes": record.notes
        }
        for record in history
    ]