from django.db import IntegrityError, transaction
from django.contrib.auth import get_user_model

from dispatch.models.mission import Mission

from .events import build_unit_maintenance_event, publish_fleet_event
from .models.history import FleetUnitHistory
from .models.vehicle import FleetUnit


class FleetUnitDomainError(Exception):
    pass


class FleetUnitConflictError(FleetUnitDomainError):
    pass


class DuplicateLicensePlateError(FleetUnitDomainError):
    pass


class FleetUnitAuditError(FleetUnitDomainError):
    pass


LICENSE_PLATE_UNIQUE_CONSTRAINT = 'fleet_units_license_plate_key'


def _is_duplicate_license_plate_error(exc):
    cause = exc.__cause__
    diagnostics = getattr(cause, 'diag', None)
    sqlstate = getattr(cause, 'sqlstate', None) or getattr(cause, 'pgcode', None)
    return (
        sqlstate == '23505'
        and getattr(diagnostics, 'constraint_name', None)
        == LICENSE_PLATE_UNIQUE_CONSTRAINT
    )


def _record_history(
    *, unit, actor, action, request_id, previous_status=None, new_status=None,
    changed_fields=None,
):
    user_model = get_user_model()
    if (
        not isinstance(actor, user_model)
        or not getattr(actor, 'pk', None)
        or not getattr(actor, 'is_authenticated', False)
        or not getattr(actor, 'is_active', False)
        or not user_model.objects.filter(pk=actor.pk, is_active=True).exists()
    ):
        raise FleetUnitAuditError(
            'Um usuário autenticado, ativo e persistido é obrigatório para auditar a operação.'
        )
    return FleetUnitHistory.objects.create(
        unit=unit,
        actor=actor,
        action=action,
        previous_status=previous_status,
        new_status=new_status,
        changed_fields=changed_fields or [],
        request_id=request_id,
    )


def _same_value(current, proposed):
    if current is None or proposed is None:
        return current is proposed
    if hasattr(current, 'equals_exact') and hasattr(proposed, 'equals_exact'):
        return current.equals_exact(proposed, 0)
    return current == proposed


def _lock_active_missions_then_unit(unit_id):
    list(
        Mission.objects.select_for_update()
        .filter(
            assigned_unit_id=unit_id,
            status=Mission.MissionStatus.EM_ANDAMENTO,
        )
        .order_by('id')
        .values_list('id', flat=True)
    )
    return FleetUnit.objects.select_for_update().get(pk=unit_id)


def _has_active_mission(unit_id):
    # This revalidation intentionally does not acquire mission locks after the
    # unit lock. Dispatch must acquire the unit lock before it can commit.
    return Mission.objects.filter(
        assigned_unit_id=unit_id,
        status=Mission.MissionStatus.EM_ANDAMENTO,
    ).exists()


def create_fleet_unit(*, actor, request_id, **values):
    try:
        with transaction.atomic():
            unit = FleetUnit.objects.create(
                **values,
                status=FleetUnit.UnitStatus.AVAILABLE,
            )
            _record_history(
                unit=unit,
                actor=actor,
                action=FleetUnitHistory.Action.UNIT_CREATED,
                request_id=request_id,
                new_status=FleetUnit.UnitStatus.AVAILABLE,
            )
            return unit
    except IntegrityError as exc:
        if _is_duplicate_license_plate_error(exc):
            raise DuplicateLicensePlateError('Já existe uma unidade com esta placa.') from exc
        raise


def update_fleet_unit(*, unit_id, actor, request_id, values):
    restricted_requested = bool({'unit_type', 'capabilities'} & set(values))
    try:
        with transaction.atomic():
            if restricted_requested:
                unit = _lock_active_missions_then_unit(unit_id)
            else:
                unit = FleetUnit.objects.select_for_update().get(pk=unit_id)

            changed = [
                field for field, value in values.items()
                if not _same_value(getattr(unit, field), value)
            ]
            restricted_changed = {'unit_type', 'capabilities'} & set(changed)
            if restricted_changed and (
                unit.status != FleetUnit.UnitStatus.AVAILABLE
                or _has_active_mission(unit.pk)
            ):
                raise FleetUnitConflictError(
                    'Tipo e capacidades só podem ser alterados quando a unidade '
                    'está disponível e sem missão ativa.'
                )

            if not changed:
                return unit

            for field in changed:
                setattr(unit, field, values[field])
            unit.save(update_fields=[*changed, 'updated_at'])
            _record_history(
                unit=unit,
                actor=actor,
                action=FleetUnitHistory.Action.UNIT_UPDATED,
                request_id=request_id,
                changed_fields=sorted(changed),
            )
            return unit
    except IntegrityError as exc:
        if _is_duplicate_license_plate_error(exc):
            raise DuplicateLicensePlateError('Já existe uma unidade com esta placa.') from exc
        raise


def _change_maintenance(*, unit_id, actor, request_id, entering):
    with transaction.atomic():
        unit = _lock_active_missions_then_unit(unit_id)
        if _has_active_mission(unit.pk):
            raise FleetUnitConflictError(
                'A unidade possui uma missão em andamento associada.'
            )

        target = (
            FleetUnit.UnitStatus.MAINTENANCE
            if entering else FleetUnit.UnitStatus.AVAILABLE
        )
        if unit.status == target:
            return unit
        expected = (
            FleetUnit.UnitStatus.AVAILABLE
            if entering else FleetUnit.UnitStatus.MAINTENANCE
        )
        if unit.status != expected:
            raise FleetUnitConflictError(
                'O estado atual da unidade não permite esta transição de manutenção.'
            )

        previous_status = unit.status
        unit.status = target
        unit.save(update_fields=['status', 'updated_at'])
        action = (
            FleetUnitHistory.Action.UNIT_MAINTENANCE_STARTED
            if entering else FleetUnitHistory.Action.UNIT_MAINTENANCE_ENDED
        )
        _record_history(
            unit=unit,
            actor=actor,
            action=action,
            request_id=request_id,
            previous_status=previous_status,
            new_status=target,
        )
        event = build_unit_maintenance_event(
            action=action,
            unit_id=unit.pk,
            unit_name=unit.name,
            previous_status=previous_status,
            new_status=target,
        )
        transaction.on_commit(lambda event=event: publish_fleet_event(event))
        return unit


def start_unit_maintenance(*, unit_id, actor, request_id):
    return _change_maintenance(
        unit_id=unit_id,
        actor=actor,
        request_id=request_id,
        entering=True,
    )


def end_unit_maintenance(*, unit_id, actor, request_id):
    return _change_maintenance(
        unit_id=unit_id,
        actor=actor,
        request_id=request_id,
        entering=False,
    )
