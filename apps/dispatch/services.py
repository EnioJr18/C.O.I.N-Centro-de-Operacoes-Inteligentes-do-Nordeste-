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


@transaction.atomic
def create_mission(description, latitude, longitude, actor=None):
    if not isinstance(description, str) or not description.strip():
        raise InvalidMissionError("A descrição da missão é obrigatória.")

    location = Point(longitude, latitude, srid=4326)
    mission = Mission(description=description.strip(), location=location)
    mission._history_actor = actor
    mission.save()
    return mission

def assign_unit_to_mission(mission, fleet_unit_id, actor=None):
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
        locked_mission._history_actor = actor
        locked_mission.save(update_fields=["assigned_unit", "status", "updated_at"])

        return locked_mission


def dispatch_emergency(
    description, latitude, longitude, required_type=None, requirements=None,
    actor=None,
):
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
        mission = create_mission(description, latitude, longitude, actor=actor)
        assigned_mission = assign_unit_to_mission(
            mission, selected_unit.id, actor=actor,
        )

    return assigned_mission, distance_meters

def _active_mission_uses_unit(unit_id, excluded_mission_id):
    return Mission.objects.filter(
        assigned_unit_id=unit_id,
        status=Mission.MissionStatus.EM_ANDAMENTO,
    ).exclude(pk=excluded_mission_id).exists()


def _lock_and_validate_active_unit(locked_mission):
    if not locked_mission.assigned_unit_id:
        raise MissionStateError("Missão em andamento sem unidade associada.")
    unit = FleetUnit.objects.select_for_update().get(
        pk=locked_mission.assigned_unit_id,
    )
    if _active_mission_uses_unit(unit.pk, locked_mission.pk):
        raise MissionStateError("A unidade está associada a outra missão em andamento.")
    if unit.status == FleetUnit.UnitStatus.AVAILABLE:
        raise MissionStateError(
            "A unidade associada está disponível enquanto a missão permanece em andamento."
        )
    if unit.status not in (
        FleetUnit.UnitStatus.BUSY,
        FleetUnit.UnitStatus.MAINTENANCE,
    ):
        raise MissionStateError("Status operacional da unidade é inconsistente.")
    return unit


def _schedule_transition_event(
    *, action, mission, previous_status, unit, unit_previous_status,
):
    from fleet.events import build_mission_transition_event, publish_fleet_event

    event = build_mission_transition_event(
        action=action,
        mission_id=mission.pk,
        previous_status=previous_status,
        new_status=mission.status,
        unit_id=unit.pk if unit else None,
        unit_previous_status=unit_previous_status,
        unit_new_status=unit.status if unit else None,
    )
    transaction.on_commit(lambda event=event: publish_fleet_event(event))


def complete_mission(mission, actor=None):
    with transaction.atomic():
        locked_mission = Mission.objects.select_for_update().get(pk=mission.pk)
        if locked_mission.status == Mission.MissionStatus.CONCLUIDA:
            return locked_mission
        if locked_mission.status != Mission.MissionStatus.EM_ANDAMENTO:
            raise MissionStateError("Apenas missões em andamento podem ser concluídas.")

        unit = _lock_and_validate_active_unit(locked_mission)
        unit_previous_status = unit.status
        if unit.status == FleetUnit.UnitStatus.BUSY:
            unit.status = FleetUnit.UnitStatus.AVAILABLE
            unit.save(update_fields=["status", "updated_at"])

        previous_status = locked_mission.status
        locked_mission.status = Mission.MissionStatus.CONCLUIDA
        locked_mission.assigned_unit = unit
        locked_mission._history_actor = actor
        locked_mission.save(update_fields=["status", "updated_at"])
        _schedule_transition_event(
            action='MISSION_COMPLETED',
            mission=locked_mission,
            previous_status=previous_status,
            unit=unit,
            unit_previous_status=unit_previous_status,
        )
        return locked_mission

def cancel_mission(mission, actor=None, reason=None):
    with transaction.atomic():
        locked_mission = Mission.objects.select_for_update().get(pk=mission.pk)
        if locked_mission.status == Mission.MissionStatus.CANCELADA:
            return locked_mission
        if locked_mission.status == Mission.MissionStatus.CONCLUIDA:
            raise MissionStateError("Esta missão não pode mais ser cancelada.")

        unit = None
        unit_previous_status = None
        if locked_mission.status == Mission.MissionStatus.PENDENTE:
            if locked_mission.assigned_unit_id:
                FleetUnit.objects.select_for_update().get(
                    pk=locked_mission.assigned_unit_id,
                )
                raise MissionStateError(
                    "Missão pendente possui uma unidade associada inesperadamente."
                )
        elif locked_mission.status == Mission.MissionStatus.EM_ANDAMENTO:
            unit = _lock_and_validate_active_unit(locked_mission)
            unit_previous_status = unit.status
        else:
            raise MissionStateError("Esta missão não pode mais ser cancelada.")

        if unit and unit.status == FleetUnit.UnitStatus.BUSY:
            unit.status = FleetUnit.UnitStatus.AVAILABLE
            unit.save(update_fields=["status", "updated_at"])

        previous_status = locked_mission.status
        locked_mission.status = Mission.MissionStatus.CANCELADA
        if unit:
            locked_mission.assigned_unit = unit
        locked_mission._history_actor = actor
        locked_mission._history_notes = reason.strip() if reason and reason.strip() else None
        locked_mission.save(update_fields=["status", "updated_at"])
        _schedule_transition_event(
            action='MISSION_CANCELLED',
            mission=locked_mission,
            previous_status=previous_status,
            unit=unit,
            unit_previous_status=unit_previous_status,
        )
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
