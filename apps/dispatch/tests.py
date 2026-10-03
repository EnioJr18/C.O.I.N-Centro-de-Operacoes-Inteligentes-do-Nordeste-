from django.contrib.gis.geos import Point
from django.test import TestCase

from dispatch.models.history import MissionHistory
from dispatch.models.mission import Mission
from dispatch.services import (
    InvalidMissionError,
    MissionStateError,
    assign_unit_to_mission,
    cancel_mission,
    complete_mission,
    create_mission,
    dispatch_emergency,
)
from fleet.models.vehicle import FleetUnit, UnitType


class MissionTestCase(TestCase):
    def create_unit(self, **overrides):
        values = {
            "name": "Bravo 01",
            "license_plate": "DEF-1234",
            "unit_type": UnitType.USB,
            "current_location": Point(-35.0, -9.0, srid=4326),
            "capabilities": {"oxygen": True},
        }
        values.update(overrides)
        return FleetUnit.objects.create(**values)

    def test_mission_creation_uses_pending_status_and_srid(self):
        mission = create_mission("Ocorrência", -9.0, -35.0)

        self.assertEqual(mission.status, Mission.MissionStatus.PENDENTE)
        self.assertEqual(mission.location.srid, 4326)
        self.assertIsNone(mission.assigned_unit)

    def test_blank_description_is_not_a_valid_mission(self):
        with self.assertRaises(InvalidMissionError):
            create_mission("   ", -9.0, -35.0)

    def test_assigns_available_unit_and_rejects_invalid_state(self):
        unit = self.create_unit()
        mission = create_mission("Ocorrência", -9.0, -35.0)

        assigned = assign_unit_to_mission(mission, unit.id)

        self.assertEqual(assigned.status, Mission.MissionStatus.EM_ANDAMENTO)
        self.assertEqual(assigned.assigned_unit_id, unit.id)
        with self.assertRaises(MissionStateError):
            assign_unit_to_mission(assigned, unit.id)


class MissionHistoryTestCase(TestCase):
    def test_creation_status_changes_and_unchanged_updates_are_audited_correctly(self):
        mission = create_mission("Ocorrência", -9.0, -35.0)
        self.assertEqual(
            list(mission.history.values_list("status", flat=True)),
            [Mission.MissionStatus.PENDENTE],
        )

        mission.description = "Descrição atualizada"
        mission.save()
        self.assertEqual(mission.history.count(), 1)

        mission.status = Mission.MissionStatus.EM_ANDAMENTO
        mission.save()
        mission.save()

        self.assertEqual(
            list(mission.history.order_by("id").values_list("status", flat=True)),
            [Mission.MissionStatus.PENDENTE, Mission.MissionStatus.EM_ANDAMENTO],
        )

    def test_dispatch_completion_and_cancellation_generate_expected_history(self):
        unit = FleetUnit.objects.create(
            name="Bravo 01",
            license_plate="DEF-1234",
            unit_type=UnitType.USB,
            current_location=Point(-35.0, -9.0, srid=4326),
            capabilities={"oxygen": True},
        )
        mission, _ = dispatch_emergency("Ocorrência", -9.0, -35.0)
        completed = complete_mission(mission)

        self.assertEqual(completed.status, Mission.MissionStatus.CONCLUIDA)
        self.assertEqual(
            list(completed.history.order_by("id").values_list("status", flat=True)),
            [
                Mission.MissionStatus.PENDENTE,
                Mission.MissionStatus.EM_ANDAMENTO,
                Mission.MissionStatus.CONCLUIDA,
            ],
        )
        unit.refresh_from_db()
        self.assertEqual(unit.status, FleetUnit.UnitStatus.AVAILABLE)

        pending = create_mission("Outra ocorrência", -9.0, -35.0)
        cancelled = cancel_mission(pending)
        self.assertEqual(cancelled.status, Mission.MissionStatus.CANCELADA)
        self.assertEqual(cancelled.history.count(), 2)


class MissionTransitionTestCase(TestCase):
    def create_mission_in_progress(self):
        sequence = FleetUnit.objects.count() + 1
        unit = FleetUnit.objects.create(
            name=f"Charlie {sequence:02d}",
            license_plate=f"GHI-{sequence:04d}",
            unit_type=UnitType.USB,
            current_location=Point(-35.0, -9.0, srid=4326),
            capabilities={},
        )
        mission = create_mission("Ocorrência", -9.0, -35.0)
        return assign_unit_to_mission(mission, unit.id), unit

    def test_complete_releases_unit_and_rejects_invalid_states(self):
        pending = create_mission("Pendente", -9.0, -35.0)
        with self.assertRaises(MissionStateError):
            complete_mission(pending)

        mission, unit = self.create_mission_in_progress()
        complete_mission(mission)
        unit.refresh_from_db()
        self.assertEqual(unit.status, FleetUnit.UnitStatus.AVAILABLE)

        with self.assertRaises(MissionStateError):
            complete_mission(mission)

    def test_cancel_accepts_pending_or_in_progress_and_rejects_completed(self):
        pending = create_mission("Pendente", -9.0, -35.0)
        self.assertEqual(cancel_mission(pending).status, Mission.MissionStatus.CANCELADA)

        mission, unit = self.create_mission_in_progress()
        self.assertEqual(cancel_mission(mission).status, Mission.MissionStatus.CANCELADA)
        unit.refresh_from_db()
        self.assertEqual(unit.status, FleetUnit.UnitStatus.AVAILABLE)

        completed, _ = self.create_mission_in_progress()
        complete_mission(completed)
        with self.assertRaises(MissionStateError):
            cancel_mission(completed)
