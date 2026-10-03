from django.db import transaction
from django.contrib.gis.geos import Point
from fleet.models.vehicle import FleetUnit
from .models.mission import Mission


class DispatchDomainError(Exception):
    """Base exception for predictable dispatch-domain failures."""


class InvalidMissionError(DispatchDomainError):
    pass


class MissionStateError(DispatchDomainError):
    pass


class UnitUnavailableError(DispatchDomainError):
    pass


class NoEligibleUnitError(DispatchDomainError):
    pass


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
    if not isinstance(description, str) or not description.strip():
        raise InvalidMissionError("A descrição da missão é obrigatória.")

    location = Point(longitude, latitude, srid=4326)
    return Mission.objects.create(description=description.strip(), location=location)

def assign_unit_to_mission(mission, fleet_unit_id):
    with transaction.atomic():
        locked_mission = Mission.objects.select_for_update().get(pk=mission.pk)
        fleet_unit = FleetUnit.objects.select_for_update().get(id=fleet_unit_id)

        if locked_mission.status != Mission.MissionStatus.PENDENTE:
            raise MissionStateError("A missão não está pendente para despacho.")

        if fleet_unit.status != FleetUnit.UnitStatus.AVAILABLE:
            raise UnitUnavailableError("Viatura não está disponível.")

        fleet_unit.status = FleetUnit.UnitStatus.BUSY
        fleet_unit.save(update_fields=["status", "updated_at"])

        locked_mission.assigned_unit = fleet_unit
        locked_mission.status = Mission.MissionStatus.EM_ANDAMENTO
        locked_mission.save(update_fields=["assigned_unit", "status", "updated_at"])

        return locked_mission


def dispatch_emergency(description, latitude, longitude, required_type=None, requirements=None):
    from fleet.selectors import get_nearest_available_units

    candidates = get_nearest_available_units(
        lat=latitude,
        lon=longitude,
        required_type=required_type,
        requirements=requirements,
        limit=1,
    )
    if not candidates:
        raise NoEligibleUnitError("Nenhuma viatura elegível está disponível.")

    selected_unit = candidates[0]
    distance_meters = selected_unit.distance.m

    with transaction.atomic():
        mission = create_mission(description, latitude, longitude)
        assigned_mission = assign_unit_to_mission(mission, selected_unit.id)

    return assigned_mission, distance_meters

def complete_mission(mission):
    with transaction.atomic():
        locked_mission = Mission.objects.select_for_update().get(pk=mission.pk)
        if locked_mission.status != Mission.MissionStatus.EM_ANDAMENTO:
            raise MissionStateError("Apenas missões em andamento podem ser concluídas.")

        if locked_mission.assigned_unit:
            unit = FleetUnit.objects.select_for_update().get(pk=locked_mission.assigned_unit_id)
            unit.status = FleetUnit.UnitStatus.AVAILABLE
            unit.save(update_fields=["status", "updated_at"])

        locked_mission.status = Mission.MissionStatus.CONCLUIDA
        locked_mission.save(update_fields=["status", "updated_at"])
        return locked_mission

def cancel_mission(mission):
    with transaction.atomic():
        locked_mission = Mission.objects.select_for_update().get(pk=mission.pk)
        valid_status = [Mission.MissionStatus.PENDENTE, Mission.MissionStatus.EM_ANDAMENTO]
        if locked_mission.status not in valid_status:
            raise MissionStateError("Esta missão não pode mais ser cancelada.")

        if locked_mission.assigned_unit:
            unit = FleetUnit.objects.select_for_update().get(pk=locked_mission.assigned_unit_id)
            unit.status = FleetUnit.UnitStatus.AVAILABLE
            unit.save(update_fields=["status", "updated_at"])

        locked_mission.status = Mission.MissionStatus.CANCELADA
        locked_mission.save(update_fields=["status", "updated_at"])
        return locked_mission


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
