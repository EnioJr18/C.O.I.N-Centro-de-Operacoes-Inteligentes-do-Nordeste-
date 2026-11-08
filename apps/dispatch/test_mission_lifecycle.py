from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from django.contrib.auth.models import User
from django.contrib.gis.geos import Point
from django.db import IntegrityError, close_old_connections, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.db.models.deletion import ProtectedError
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import UserRole
from dispatch.models.history import MissionHistory
from dispatch.models.mission import Mission
from dispatch.services import (
    MissionStateError,
    UnitUnavailableError,
    assign_unit_to_mission,
    cancel_mission,
    complete_mission,
    create_mission,
    dispatch_emergency,
)
from fleet.models.vehicle import FleetUnit, UnitType


PASSWORD = 'StrongPassword123'


class MissionLifecycleMixin:
    unit_sequence = 0

    def create_unit(self, status=FleetUnit.UnitStatus.AVAILABLE):
        self.unit_sequence += 1
        return FleetUnit.objects.create(
            name=f'Unidade {self.unit_sequence}',
            license_plate=f'LFC-{self.unit_sequence:04d}',
            unit_type=UnitType.USB,
            current_location=Point(-35, -9, srid=4326),
            status=status,
            capabilities={},
        )

    def create_active_mission(self, actor=None, unit_status=FleetUnit.UnitStatus.BUSY):
        unit = self.create_unit()
        mission = create_mission('Ocorrência ativa', -9, -35, actor=actor)
        mission = assign_unit_to_mission(mission, unit.pk, actor=actor)
        if unit_status != FleetUnit.UnitStatus.BUSY:
            FleetUnit.objects.filter(pk=unit.pk).update(status=unit_status)
            unit.refresh_from_db()
        return mission, unit


class MissionLifecycleServiceTests(MissionLifecycleMixin, TestCase):
    def setUp(self):
        self.actor = User.objects.create_user('lifecycle-operator', password=PASSWORD)

    def test_actor_is_recorded_for_creation_dispatch_completion_and_system_operation(self):
        mission = create_mission('Criada por operador', -9, -35, actor=self.actor)
        self.assertEqual(mission.history.get().actor, self.actor)

        system_mission = create_mission('Criada pelo sistema', -9, -35)
        self.assertIsNone(system_mission.history.get().actor)

        self.create_unit()
        dispatched, _ = dispatch_emergency('Despacho', -9, -35, actor=self.actor)
        self.assertEqual(
            list(dispatched.history.order_by('id').values_list('actor_id', flat=True)),
            [self.actor.pk, self.actor.pk],
        )
        complete_mission(dispatched, actor=self.actor)
        self.assertEqual(dispatched.history.order_by('-id').first().actor, self.actor)

    def test_completion_releases_busy_preserves_maintenance_and_is_idempotent(self):
        mission, unit = self.create_active_mission(actor=self.actor)
        with patch('fleet.events.publish_fleet_event') as publish:
            with self.captureOnCommitCallbacks(execute=True):
                completed = complete_mission(mission, actor=self.actor)
            self.assertEqual(publish.call_count, 1)
            event = publish.call_args.args[0]
            self.assertEqual(event['action'], 'MISSION_COMPLETED')
            self.assertEqual(event['unit_previous_status'], 'BUSY')
            self.assertEqual(event['unit_new_status'], 'AVAILABLE')
            history_count = completed.history.count()
            with self.captureOnCommitCallbacks(execute=True):
                repeated = complete_mission(completed, actor=self.actor)
            self.assertEqual(publish.call_count, 1)
        unit.refresh_from_db()
        self.assertEqual(unit.status, FleetUnit.UnitStatus.AVAILABLE)
        self.assertEqual(repeated.status, Mission.MissionStatus.CONCLUIDA)
        self.assertEqual(repeated.history.count(), history_count)

        maintenance, maintenance_unit = self.create_active_mission(
            actor=self.actor, unit_status=FleetUnit.UnitStatus.MAINTENANCE,
        )
        complete_mission(maintenance, actor=self.actor)
        maintenance_unit.refresh_from_db()
        self.assertEqual(maintenance_unit.status, FleetUnit.UnitStatus.MAINTENANCE)

    def test_cancellation_reason_states_and_idempotency(self):
        pending = create_mission('Pendente', -9, -35, actor=self.actor)
        with patch('fleet.events.publish_fleet_event') as publish:
            with self.captureOnCommitCallbacks(execute=True):
                cancelled = cancel_mission(
                    pending, actor=self.actor, reason='  Área sem acesso  ',
                )
            self.assertEqual(cancelled.history.order_by('-id').first().notes, 'Área sem acesso')
            self.assertEqual(publish.call_args.args[0]['unit_id'], None)
            history_count = cancelled.history.count()
            with self.captureOnCommitCallbacks(execute=True):
                cancel_mission(cancelled, actor=self.actor, reason='Outro motivo')
            self.assertEqual(publish.call_count, 1)
        self.assertEqual(cancelled.history.count(), history_count)

        active, unit = self.create_active_mission(actor=self.actor)
        cancel_mission(active, actor=self.actor)
        unit.refresh_from_db()
        self.assertEqual(unit.status, FleetUnit.UnitStatus.AVAILABLE)

        maintenance, maintenance_unit = self.create_active_mission(
            actor=self.actor, unit_status=FleetUnit.UnitStatus.MAINTENANCE,
        )
        cancel_mission(maintenance, actor=self.actor)
        maintenance_unit.refresh_from_db()
        self.assertEqual(maintenance_unit.status, FleetUnit.UnitStatus.MAINTENANCE)

    def test_opposite_terminal_and_inconsistent_available_unit_are_conflicts(self):
        completed, _ = self.create_active_mission(actor=self.actor)
        completed = complete_mission(completed, actor=self.actor)
        with self.assertRaises(MissionStateError):
            cancel_mission(completed, actor=self.actor)

        cancelled = create_mission('Cancelada', -9, -35, actor=self.actor)
        cancelled = cancel_mission(cancelled, actor=self.actor)
        with self.assertRaises(MissionStateError):
            complete_mission(cancelled, actor=self.actor)

        inconsistent, unit = self.create_active_mission(actor=self.actor)
        FleetUnit.objects.filter(pk=unit.pk).update(status=FleetUnit.UnitStatus.AVAILABLE)
        with self.assertRaises(MissionStateError):
            complete_mission(inconsistent, actor=self.actor)
        inconsistent.refresh_from_db()
        self.assertEqual(inconsistent.status, Mission.MissionStatus.EM_ANDAMENTO)

    def test_shared_active_detection_and_history_failure_roll_back_everything(self):
        mission, unit = self.create_active_mission(actor=self.actor)
        with patch('dispatch.services._active_mission_uses_unit', return_value=True):
            with self.assertRaises(MissionStateError):
                complete_mission(mission, actor=self.actor)

        with patch('dispatch.signals.MissionHistory.objects.create', side_effect=RuntimeError('history failed')):
            with self.assertRaises(RuntimeError):
                complete_mission(mission, actor=self.actor)
        mission.refresh_from_db(); unit.refresh_from_db()
        self.assertEqual(mission.status, Mission.MissionStatus.EM_ANDAMENTO)
        self.assertEqual(unit.status, FleetUnit.UnitStatus.BUSY)

    def test_pending_mission_with_unexpected_unit_is_rejected_without_changes(self):
        unit = self.create_unit()
        unrelated = self.create_unit(status=FleetUnit.UnitStatus.MAINTENANCE)
        mission = Mission.objects.create(
            description='Pendente inconsistente',
            location=Point(-35, -9, srid=4326),
            assigned_unit=unit,
        )
        with self.assertRaises(MissionStateError):
            cancel_mission(mission, actor=self.actor)
        mission.refresh_from_db(); unit.refresh_from_db(); unrelated.refresh_from_db()
        self.assertEqual(mission.status, Mission.MissionStatus.PENDENTE)
        self.assertEqual(unit.status, FleetUnit.UnitStatus.AVAILABLE)
        self.assertEqual(unrelated.status, FleetUnit.UnitStatus.MAINTENANCE)

    def test_history_actor_protects_user_deletion(self):
        create_mission('Protegida', -9, -35, actor=self.actor)
        with self.assertRaises(ProtectedError):
            self.actor.delete()

    def test_terminal_event_is_discarded_on_rollback_and_transport_failure_is_safe(self):
        mission, unit = self.create_active_mission(actor=self.actor)
        with patch('fleet.events.publish_fleet_event') as publish:
            with self.captureOnCommitCallbacks(execute=True):
                with transaction.atomic():
                    complete_mission(mission, actor=self.actor)
                    transaction.set_rollback(True)
            publish.assert_not_called()
        mission.refresh_from_db(); unit.refresh_from_db()
        self.assertEqual(mission.status, Mission.MissionStatus.EM_ANDAMENTO)
        self.assertEqual(unit.status, FleetUnit.UnitStatus.BUSY)

        with patch('fleet.events.get_channel_layer', side_effect=RuntimeError('sensitive-value')):
            with self.assertLogs('fleet.events', level='ERROR') as logs:
                with self.captureOnCommitCallbacks(execute=True):
                    completed = complete_mission(mission, actor=self.actor)
        self.assertEqual(completed.status, Mission.MissionStatus.CONCLUIDA)
        self.assertNotIn('sensitive-value', str(logs.output))


class MissionConstraintTests(MissionLifecycleMixin, TestCase):
    def test_active_mission_requires_unit_and_only_one_active_mission_per_unit(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Mission.objects.create(
                description='Sem unidade',
                location=Point(-35, -9, srid=4326),
                status=Mission.MissionStatus.EM_ANDAMENTO,
            )

        unit = self.create_unit(status=FleetUnit.UnitStatus.BUSY)
        Mission.objects.create(
            description='Ativa', location=Point(-35, -9, srid=4326),
            status=Mission.MissionStatus.EM_ANDAMENTO, assigned_unit=unit,
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            Mission.objects.create(
                description='Duplicada', location=Point(-35, -9, srid=4326),
                status=Mission.MissionStatus.EM_ANDAMENTO, assigned_unit=unit,
            )

    def test_terminal_pending_and_null_actor_records_remain_valid(self):
        unit = self.create_unit()
        for status in (Mission.MissionStatus.CONCLUIDA, Mission.MissionStatus.CANCELADA):
            Mission.objects.create(
                description=status, location=Point(-35, -9, srid=4326),
                status=status, assigned_unit=unit,
            )
        pending = create_mission('Pendente legada', -9, -35)
        self.assertIsNone(pending.history.get().actor)


class MissionLifecycleAPITests(MissionLifecycleMixin, TestCase):
    def setUp(self):
        self.operator = User.objects.create_user('api-operator-life', password=PASSWORD)
        self.admin = User.objects.create_user('api-admin-life', password=PASSWORD)
        self.admin.profile.role = UserRole.ADMIN
        self.admin.profile.save(update_fields=['role'])
        self.superuser = User.objects.create_superuser('api-super-life', password=PASSWORD)

    def client_for(self, user):
        client = APIClient()
        client.force_authenticate(user)
        return client

    def test_operational_roles_complete_and_cancel_with_actor(self):
        for user in (self.operator, self.admin, self.superuser):
            mission, _ = self.create_active_mission()
            response = self.client_for(user).post(
                reverse('dispatch:mission_complete', args=[mission.pk]), {}, format='json',
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data['status'], Mission.MissionStatus.CONCLUIDA)
            self.assertEqual(mission.history.order_by('-id').first().actor, user)

        pending = create_mission('Cancelar via API', -9, -35)
        response = self.client_for(self.operator).post(
            reverse('dispatch:mission_cancel', args=[pending.pk]),
            {'reason': '  Sem acesso  '}, format='json',
        )
        self.assertEqual(response.status_code, 200)
        history = self.client_for(self.operator).get(
            reverse('dispatch:mission_history', args=[pending.pk]),
        )
        self.assertEqual(history.data['results'][0]['notes'], 'Sem acesso')
        self.assertEqual(history.data['results'][0]['actor']['username'], self.operator.username)
        self.assertNotIn('email', history.data['results'][0]['actor'])

    def test_permissions_not_found_payload_and_conflict_contracts(self):
        mission = create_mission('Protegida', -9, -35)
        complete_url = reverse('dispatch:mission_complete', args=[mission.pk])
        cancel_url = reverse('dispatch:mission_cancel', args=[mission.pk])
        self.assertEqual(APIClient().post(cancel_url, {}, format='json').status_code, 401)

        no_profile = User.objects.create_user('life-no-profile', password=PASSWORD)
        no_profile.profile.delete()
        no_profile.refresh_from_db()
        self.assertEqual(self.client_for(no_profile).post(cancel_url, {}, format='json').status_code, 403)

        inactive = User.objects.create_user('life-inactive', password=PASSWORD, is_active=False)
        inactive_client = APIClient()
        inactive_client.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(inactive)}')
        self.assertEqual(inactive_client.post(cancel_url, {}, format='json').status_code, 401)

        client = self.client_for(self.operator)
        self.assertEqual(client.post(reverse('dispatch:mission_cancel', args=[999999]), {}, format='json').status_code, 404)
        self.assertEqual(client.post(cancel_url, {'unknown': True}, format='json').status_code, 400)
        self.assertEqual(client.post(cancel_url, {'reason': 'x' * 1001}, format='json').status_code, 400)
        self.assertEqual(client.post(complete_url, {}, format='json').status_code, 409)

    def test_creation_and_dispatch_api_record_actor_and_openapi_paths(self):
        client = self.client_for(self.operator)
        created = client.post(
            reverse('dispatch:mission_list'),
            {'description': 'Criada', 'location': {'latitude': -9, 'longitude': -35}},
            format='json',
        )
        self.assertEqual(created.status_code, 201)
        self.assertEqual(MissionHistory.objects.get(mission_id=created.data['id']).actor, self.operator)

        self.create_unit()
        dispatched = client.post(
            reverse('fleet:dispatch_emergency'),
            {'description': 'Despachada', 'location': {'latitude': -9, 'longitude': -35}},
            format='json',
        )
        self.assertEqual(dispatched.status_code, 201)
        self.assertEqual(
            set(MissionHistory.objects.filter(mission_id=dispatched.data['mission']['id']).values_list('actor_id', flat=True)),
            {self.operator.pk},
        )

        schema = APIClient().get(reverse('schema'), HTTP_ACCEPT='application/vnd.oai.openapi+json')
        self.assertIn('/api/v1/missions/{id}/complete/', schema.data['paths'])
        self.assertIn('/api/v1/missions/{id}/cancel/', schema.data['paths'])


class MissionLifecycleAdminTests(MissionLifecycleMixin, TestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser(
            'lifecycle-admin', password=PASSWORD,
        )
        self.client.force_login(self.superuser)

    def test_admin_cannot_change_operational_fields_or_delete_domain_records(self):
        mission, assigned = self.create_active_mission()
        replacement = self.create_unit()
        change_mission = reverse('admin:dispatch_mission_change', args=[mission.pk])
        response = self.client.post(change_mission, {
            'description': 'Descrição administrativa',
            'location': 'POINT (-35 -9)',
            'status': Mission.MissionStatus.CANCELADA,
            'assigned_unit': replacement.pk,
            '_save': 'Salvar',
        })
        self.assertEqual(response.status_code, 302)
        mission.refresh_from_db()
        self.assertEqual(mission.status, Mission.MissionStatus.EM_ANDAMENTO)
        self.assertEqual(mission.assigned_unit_id, assigned.pk)
        self.assertEqual(mission.description, 'Descrição administrativa')

        change_unit = reverse('admin:fleet_fleetunit_change', args=[assigned.pk])
        response = self.client.post(change_unit, {
            'name': assigned.name,
            'license_plate': assigned.license_plate,
            'unit_type': assigned.unit_type,
            'current_location': 'POINT (-35 -9)',
            'capabilities': '{"oxygen": true}',
            'status': FleetUnit.UnitStatus.MAINTENANCE,
            '_save': 'Salvar',
        })
        if response.status_code == 200:
            self.assertFalse(
                response.context['adminform'].form.errors,
                response.context['adminform'].form.errors.as_json(),
            )
        self.assertEqual(response.status_code, 302)
        assigned.refresh_from_db()
        self.assertEqual(assigned.status, FleetUnit.UnitStatus.BUSY)

        self.assertEqual(
            self.client.post(
                reverse('admin:dispatch_mission_delete', args=[mission.pk]),
                {'post': 'yes'},
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(
                reverse('admin:fleet_fleetunit_delete', args=[assigned.pk]),
                {'post': 'yes'},
            ).status_code,
            403,
        )
        self.assertTrue(Mission.objects.filter(pk=mission.pk).exists())
        self.assertTrue(FleetUnit.objects.filter(pk=assigned.pk).exists())

    def test_history_admin_is_read_only_and_bulk_delete_is_unavailable(self):
        mission = create_mission('Histórico protegido', -9, -35)
        history = mission.history.get()
        change_url = reverse('admin:dispatch_missionhistory_change', args=[history.pk])
        response = self.client.post(change_url, {
            'status': Mission.MissionStatus.CANCELADA,
            'notes': 'Alterada',
            '_save': 'Salvar',
        })
        self.assertEqual(response.status_code, 403)
        history.refresh_from_db()
        self.assertEqual(history.status, Mission.MissionStatus.PENDENTE)

        list_url = reverse('admin:dispatch_mission_changelist')
        response = self.client.post(list_url, {
            'action': 'delete_selected',
            '_selected_action': [mission.pk],
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Mission.objects.filter(pk=mission.pk).exists())


class MissionLifecycleConcurrencyTests(MissionLifecycleMixin, TransactionTestCase):
    reset_sequences = True

    def concurrent(self, functions):
        barrier = Barrier(len(functions))

        def run(function):
            close_old_connections()
            barrier.wait()
            try:
                function()
                return 'ok'
            except (MissionStateError, UnitUnavailableError, IntegrityError):
                return 'conflict'
            finally:
                close_old_connections()

        with patch('fleet.events.publish_fleet_event'):
            with ThreadPoolExecutor(max_workers=len(functions)) as executor:
                return list(executor.map(run, functions))

    def test_complete_and_cancel_compete_without_partial_state(self):
        mission, unit = self.create_active_mission()
        results = self.concurrent([
            lambda: complete_mission(Mission.objects.get(pk=mission.pk)),
            lambda: cancel_mission(Mission.objects.get(pk=mission.pk)),
        ])
        mission.refresh_from_db(); unit.refresh_from_db()
        self.assertEqual(sorted(results), ['conflict', 'ok'])
        self.assertIn(mission.status, [Mission.MissionStatus.CONCLUIDA, Mission.MissionStatus.CANCELADA])
        self.assertEqual(unit.status, FleetUnit.UnitStatus.AVAILABLE)
        self.assertEqual(mission.history.filter(status__in=[Mission.MissionStatus.CONCLUIDA, Mission.MissionStatus.CANCELADA]).count(), 1)

    def test_repeated_complete_and_cancel_are_serialized_and_idempotent(self):
        complete_target, complete_unit = self.create_active_mission()
        self.assertEqual(self.concurrent([
            lambda: complete_mission(Mission.objects.get(pk=complete_target.pk)),
            lambda: complete_mission(Mission.objects.get(pk=complete_target.pk)),
        ]), ['ok', 'ok'])
        complete_target.refresh_from_db(); complete_unit.refresh_from_db()
        self.assertEqual(complete_target.history.filter(status=Mission.MissionStatus.CONCLUIDA).count(), 1)
        self.assertEqual(complete_unit.status, FleetUnit.UnitStatus.AVAILABLE)

        cancel_target = create_mission('Cancelar', -9, -35)
        self.assertEqual(self.concurrent([
            lambda: cancel_mission(Mission.objects.get(pk=cancel_target.pk)),
            lambda: cancel_mission(Mission.objects.get(pk=cancel_target.pk)),
        ]), ['ok', 'ok'])
        cancel_target.refresh_from_db()
        self.assertEqual(cancel_target.history.filter(status=Mission.MissionStatus.CANCELADA).count(), 1)

    def test_dispatch_assignment_competes_with_cancel_and_another_assignment(self):
        unit = self.create_unit()
        mission = create_mission('Pendente', -9, -35)
        results = self.concurrent([
            lambda: assign_unit_to_mission(Mission.objects.get(pk=mission.pk), unit.pk),
            lambda: cancel_mission(Mission.objects.get(pk=mission.pk)),
        ])
        mission.refresh_from_db(); unit.refresh_from_db()
        self.assertIn(results, (['ok', 'ok'], ['conflict', 'ok'], ['ok', 'conflict']))
        self.assertEqual(mission.status, Mission.MissionStatus.CANCELADA)
        self.assertEqual(unit.status, FleetUnit.UnitStatus.AVAILABLE)

        shared = self.create_unit()
        first = create_mission('Primeira', -9, -35)
        second = create_mission('Segunda', -9, -35)
        results = self.concurrent([
            lambda: assign_unit_to_mission(Mission.objects.get(pk=first.pk), shared.pk),
            lambda: assign_unit_to_mission(Mission.objects.get(pk=second.pk), shared.pk),
        ])
        self.assertEqual(sorted(results), ['conflict', 'ok'])
        self.assertEqual(Mission.objects.filter(assigned_unit=shared, status=Mission.MissionStatus.EM_ANDAMENTO).count(), 1)

    def test_dispatch_assignment_competes_with_completion_consistently(self):
        unit = self.create_unit()
        mission = create_mission('Despacho versus conclusão', -9, -35)
        results = self.concurrent([
            lambda: assign_unit_to_mission(Mission.objects.get(pk=mission.pk), unit.pk),
            lambda: complete_mission(Mission.objects.get(pk=mission.pk)),
        ])
        mission.refresh_from_db(); unit.refresh_from_db()
        self.assertIn(sorted(results), (['conflict', 'ok'], ['ok', 'ok']))
        if mission.status == Mission.MissionStatus.EM_ANDAMENTO:
            self.assertEqual(unit.status, FleetUnit.UnitStatus.BUSY)
        else:
            self.assertEqual(mission.status, Mission.MissionStatus.CONCLUIDA)
            self.assertEqual(unit.status, FleetUnit.UnitStatus.AVAILABLE)


class MissionIntegrityMigrationTests(TransactionTestCase):
    migrate_from = ('dispatch', '0001_initial')
    migrate_to = ('dispatch', '0002_missionhistory_actor_and_mission_constraints')

    def test_preflight_reports_conflicting_ids_and_rolls_back_without_correction(self):
        executor = MigrationExecutor(connection)
        from_targets = [self.migrate_from, ('fleet', '0001_initial')]
        executor.migrate(from_targets)
        old_apps = executor.loader.project_state(from_targets).apps
        OldMission = old_apps.get_model('dispatch', 'Mission')
        OldFleetUnit = old_apps.get_model('fleet', 'FleetUnit')
        unit = OldFleetUnit.objects.create(
            name='Legada', license_plate='LEG-0001',
            current_location=Point(-35, -9, srid=4326), capabilities={},
        )
        missing = OldMission.objects.create(
            description='Sem unidade', location=Point(-35, -9, srid=4326),
            status='Em Andamento',
        )
        first = OldMission.objects.create(
            description='Duplicada 1', location=Point(-35, -9, srid=4326),
            status='Em Andamento', assigned_unit_id=unit.pk,
        )
        second = OldMission.objects.create(
            description='Duplicada 2', location=Point(-35, -9, srid=4326),
            status='Em Andamento', assigned_unit_id=unit.pk,
        )

        executor = MigrationExecutor(connection)
        with self.assertRaises(RuntimeError) as raised:
            executor.migrate([self.migrate_to])
        message = str(raised.exception)
        self.assertIn(str(missing.pk), message)
        self.assertIn(f'({unit.pk}, {first.pk})', message)
        self.assertIn(f'({unit.pk}, {second.pk})', message)
        self.assertFalse(
            executor.recorder.migration_qs.filter(
                app='dispatch', name=self.migrate_to[1],
            ).exists()
        )
        self.assertEqual(OldMission.objects.count(), 3)

        OldMission.objects.all().delete()
        OldFleetUnit.objects.all().delete()
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
