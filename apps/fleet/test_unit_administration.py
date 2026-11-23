from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.models import AnonymousUser
from django.contrib.gis.geos import Point
from django.db import IntegrityError, close_old_connections, transaction
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import UserRole
from dispatch.models.mission import Mission
from dispatch.services import (
    MissionStateError,
    UnitUnavailableError,
    assign_unit_to_mission,
    cancel_mission,
    complete_mission,
    create_mission,
)
from fleet.models.history import FleetUnitHistory
from fleet.models.vehicle import FleetUnit, UnitType
from fleet.services import (
    DuplicateLicensePlateError,
    FleetUnitAuditError,
    FleetUnitConflictError,
    create_fleet_unit,
    end_unit_maintenance,
    start_unit_maintenance,
    update_fleet_unit,
)


PASSWORD = 'StrongPassword123'


class FleetAdministrationMixin:
    request_id = '00000000-0000-0000-0000-000000000141'
    unit_sequence = 0

    def create_user(self, username='fleet-admin', role=UserRole.ADMIN, **extra):
        user = User.objects.create_user(username, password=PASSWORD, **extra)
        user.profile.role = role
        user.profile.save(update_fields=['role'])
        return user

    def create_unit(self, **overrides):
        self.unit_sequence += 1
        values = {
            'name': f'Unidade {self.unit_sequence}',
            'license_plate': f'FLT-{self.unit_sequence:04d}',
            'unit_type': UnitType.USB,
            'current_location': Point(-35, -9, srid=4326),
            'capabilities': {'oxygen': True},
        }
        values.update(overrides)
        return FleetUnit.objects.create(**values)


class FleetAdministrationServiceTests(FleetAdministrationMixin, TestCase):
    def setUp(self):
        self.actor = self.create_user()

    def test_creation_is_available_audited_and_case_sensitive(self):
        first = create_fleet_unit(
            actor=self.actor,
            request_id=self.request_id,
            name=' Alfa ',
            license_plate='ABC-1D23',
            unit_type=UnitType.USB,
            capabilities={'oxygen': True},
        )
        second = create_fleet_unit(
            actor=self.actor,
            request_id=self.request_id,
            name='Bravo',
            license_plate='abc-1d23',
            unit_type=UnitType.USA,
            capabilities={},
        )
        self.assertEqual(first.status, FleetUnit.UnitStatus.AVAILABLE)
        self.assertNotEqual(first.license_plate, second.license_plate)
        event = first.history.get()
        self.assertEqual(event.action, FleetUnitHistory.Action.UNIT_CREATED)
        self.assertEqual(event.actor, self.actor)
        self.assertEqual(event.request_id, self.request_id)
        self.assertEqual(event.new_status, FleetUnit.UnitStatus.AVAILABLE)
        self.assertEqual(event.changed_fields, [])

    def test_update_is_atomic_audited_and_idempotent(self):
        unit = self.create_unit()
        updated = update_fleet_unit(
            unit_id=unit.pk,
            actor=self.actor,
            request_id=self.request_id,
            values={'name': 'Renomeada', 'current_location': None},
        )
        self.assertEqual(updated.name, 'Renomeada')
        self.assertIsNone(updated.current_location)
        event = updated.history.get()
        self.assertEqual(event.action, FleetUnitHistory.Action.UNIT_UPDATED)
        self.assertEqual(event.changed_fields, ['current_location', 'name'])
        update_fleet_unit(
            unit_id=unit.pk,
            actor=self.actor,
            request_id=self.request_id,
            values={'name': 'Renomeada', 'current_location': None},
        )
        self.assertEqual(unit.history.count(), 1)

    def test_restricted_update_rejects_busy_or_active_without_partial_change(self):
        unit = self.create_unit(status=FleetUnit.UnitStatus.BUSY)
        with self.assertRaises(FleetUnitConflictError):
            update_fleet_unit(
                unit_id=unit.pk, actor=self.actor, request_id=self.request_id,
                values={'name': 'Não salvar', 'unit_type': UnitType.USA},
            )
        unit.refresh_from_db()
        self.assertNotEqual(unit.name, 'Não salvar')
        self.assertEqual(unit.unit_type, UnitType.USB)
        self.assertFalse(unit.history.exists())

        unit.status = FleetUnit.UnitStatus.AVAILABLE
        unit.save(update_fields=['status'])
        Mission.objects.create(
            description='Ativa', location=Point(-35, -9, srid=4326),
            status=Mission.MissionStatus.EM_ANDAMENTO, assigned_unit=unit,
        )
        with self.assertRaises(FleetUnitConflictError):
            update_fleet_unit(
                unit_id=unit.pk, actor=self.actor, request_id=self.request_id,
                values={'capabilities': {'uti': True}},
            )

    def test_maintenance_transitions_idempotency_events_and_transport_failure(self):
        unit = self.create_unit()
        with patch('fleet.services.publish_fleet_event') as publish:
            with self.captureOnCommitCallbacks(execute=True):
                started = start_unit_maintenance(
                    unit_id=unit.pk, actor=self.actor, request_id=self.request_id,
                )
        self.assertEqual(started.status, FleetUnit.UnitStatus.MAINTENANCE)
        publish.assert_called_once()
        self.assertEqual(publish.call_args.args[0]['action'], 'UNIT_MAINTENANCE_STARTED')
        self.assertEqual(started.history.count(), 1)

        with patch('fleet.services.publish_fleet_event') as publish:
            with self.captureOnCommitCallbacks(execute=True):
                start_unit_maintenance(
                    unit_id=unit.pk, actor=self.actor, request_id=self.request_id,
                )
        publish.assert_not_called()
        self.assertEqual(started.history.count(), 1)

        with patch('fleet.events.get_channel_layer', side_effect=RuntimeError('sensitive')):
            with self.captureOnCommitCallbacks(execute=True):
                ended = end_unit_maintenance(
                    unit_id=unit.pk, actor=self.actor, request_id=self.request_id,
                )
        self.assertEqual(ended.status, FleetUnit.UnitStatus.AVAILABLE)
        self.assertEqual(ended.history.count(), 2)

    def test_maintenance_rejects_busy_and_any_active_link(self):
        busy = self.create_unit(status=FleetUnit.UnitStatus.BUSY)
        with self.assertRaises(FleetUnitConflictError):
            start_unit_maintenance(
                unit_id=busy.pk, actor=self.actor, request_id=self.request_id,
            )
        active = self.create_unit(status=FleetUnit.UnitStatus.MAINTENANCE)
        Mission.objects.create(
            description='Inconsistente', location=Point(-35, -9, srid=4326),
            status=Mission.MissionStatus.EM_ANDAMENTO, assigned_unit=active,
        )
        with self.assertRaises(FleetUnitConflictError):
            start_unit_maintenance(
                unit_id=active.pk, actor=self.actor, request_id=self.request_id,
            )
        with self.assertRaises(FleetUnitConflictError):
            end_unit_maintenance(
                unit_id=active.pk, actor=self.actor, request_id=self.request_id,
            )

    def test_history_failure_rolls_back_and_protects_actor_and_unit(self):
        unit = self.create_unit()
        with patch('fleet.services._record_history', side_effect=RuntimeError('failure')):
            with self.assertRaises(RuntimeError):
                start_unit_maintenance(
                    unit_id=unit.pk, actor=self.actor, request_id=self.request_id,
                )
        unit.refresh_from_db()
        self.assertEqual(unit.status, FleetUnit.UnitStatus.AVAILABLE)

        start_unit_maintenance(
            unit_id=unit.pk, actor=self.actor, request_id=self.request_id,
        )
        with self.assertRaises(IntegrityError):
            self.actor.delete()
        with self.assertRaises(IntegrityError):
            unit.delete()

    def test_actor_is_required_at_service_and_database_boundaries(self):
        with self.assertRaises(FleetUnitAuditError):
            create_fleet_unit(
                actor=None, request_id=self.request_id,
                name='Sem ator', license_plate='AUD-0001',
                unit_type=UnitType.USB, capabilities={},
            )
        self.assertFalse(FleetUnit.objects.filter(license_plate='AUD-0001').exists())

        unit = self.create_unit()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                FleetUnitHistory.objects.create(
                    unit=unit, actor=None,
                    action=FleetUnitHistory.Action.UNIT_CREATED,
                    request_id=self.request_id,
                )

        for actor in (
            AnonymousUser(),
            User(username='unsaved'),
            User(pk=987654321, username='missing-in-db'),
            self.create_user('inactive-auditor', is_active=False),
        ):
            with self.subTest(actor=type(actor).__name__, pk=getattr(actor, 'pk', None)):
                with self.assertRaises(FleetUnitAuditError):
                    create_fleet_unit(
                        actor=actor, request_id=self.request_id,
                        name='Ator inválido', license_plate=f'BAD-{getattr(actor, "pk", 0)}',
                        unit_type=UnitType.USB, capabilities={},
                    )

    def test_unrelated_integrity_error_is_not_reported_as_duplicate_plate(self):
        unit = self.create_unit()
        with patch('fleet.services._record_history', side_effect=IntegrityError('other constraint')):
            with self.assertRaises(IntegrityError) as raised:
                update_fleet_unit(
                    unit_id=unit.pk, actor=self.actor, request_id=self.request_id,
                    values={'name': 'Não persistir'},
                )
        self.assertNotIsInstance(raised.exception, DuplicateLicensePlateError)
        unit.refresh_from_db()
        self.assertNotEqual(unit.name, 'Não persistir')

    def test_license_plate_constraint_is_the_only_translated_integrity_error(self):
        self.create_unit(license_plate='DUP-0001')
        with self.assertRaises(DuplicateLicensePlateError):
            create_fleet_unit(
                actor=self.actor, request_id=self.request_id,
                name='Duplicada', license_plate='DUP-0001',
                unit_type=UnitType.USB, capabilities={},
            )


class FleetAdministrationAPITests(FleetAdministrationMixin, TestCase):
    def setUp(self):
        self.admin_user = self.create_user('api-admin')
        self.operator = self.create_user('api-operator', UserRole.OPERADOR)
        self.superuser = User.objects.create_superuser('api-root', password=PASSWORD)
        self.no_profile = User.objects.create_user('api-no-profile', password=PASSWORD)
        self.no_profile.profile.delete()
        self.inactive = self.create_user('api-inactive', is_active=False)
        self.client = APIClient()
        self.list_url = reverse('fleet:fleet_unit_list')

    def payload(self, **overrides):
        values = {
            'name': 'Alfa', 'license_plate': 'API-0001',
            'unit_type': UnitType.USB,
            'current_location': {'latitude': -9, 'longitude': -35},
            'capabilities': {'oxygen': True},
        }
        values.update(overrides)
        return values

    def test_create_permissions_payload_and_safe_response(self):
        self.assertEqual(self.client.post(self.list_url, self.payload(), format='json').status_code, 401)
        for user in (self.operator, self.no_profile):
            self.client.force_authenticate(user)
            self.assertEqual(self.client.post(self.list_url, self.payload(), format='json').status_code, 403)
        self.client.force_authenticate(user=None)
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.inactive)}'
        )
        self.assertEqual(self.client.post(self.list_url, self.payload(), format='json').status_code, 401)
        self.client.credentials()
        for index, user in enumerate((self.admin_user, self.superuser), 1):
            self.client.force_authenticate(user)
            response = self.client.post(
                self.list_url,
                self.payload(license_plate=f'API-000{index}'),
                format='json',
            )
            self.assertEqual(response.status_code, 201)
            self.assertEqual(response.data['status'], FleetUnit.UnitStatus.AVAILABLE)
            self.assertNotIn('actor', response.data)

    def test_create_rejects_forbidden_unknown_duplicate_and_invalid_fields(self):
        self.client.force_authenticate(self.admin_user)
        invalid = [
            self.payload(status='BUSY'), self.payload(secret='x'),
            self.payload(name=' '), self.payload(license_plate=' '),
            self.payload(unit_type='INVALID'),
            self.payload(current_location={'latitude': 91, 'longitude': -35}),
            self.payload(capabilities=[]), self.payload(capabilities='oxygen'),
        ]
        for payload in invalid:
            self.assertEqual(self.client.post(self.list_url, payload, format='json').status_code, 400)
        self.assertEqual(self.client.post(self.list_url, self.payload(), format='json').status_code, 201)
        self.assertEqual(self.client.post(self.list_url, self.payload(), format='json').status_code, 400)
        self.assertEqual(
            self.client.post(
                self.list_url,
                self.payload(license_plate='api-0001'),
                format='json',
            ).status_code,
            201,
        )

    def test_capability_defensive_limits(self):
        self.client.force_authenticate(self.admin_user)
        cases = [
            {'a': {'b': {'c': {'d': {'e': {'f': True}}}}}},
            {f'key-{index}': True for index in range(101)},
            {'x' * 65: True},
            {'large': 'x' * (16 * 1024)},
        ]
        for index, capabilities in enumerate(cases):
            response = self.client.post(
                self.list_url,
                self.payload(license_plate=f'LIM-{index}', capabilities=capabilities),
                format='json',
            )
            self.assertEqual(response.status_code, 400)

    def test_patch_is_strict_atomic_idempotent_and_audited(self):
        unit = self.create_unit(status=FleetUnit.UnitStatus.BUSY)
        url = reverse('fleet:fleet_unit_detail', args=[unit.pk])
        self.client.force_authenticate(self.operator)
        self.assertEqual(self.client.patch(url, {'name': 'No'}, format='json').status_code, 403)
        self.client.force_authenticate(self.admin_user)
        for payload in ({'status': 'AVAILABLE'}, {'assigned_unit': 1}, {'unknown': True}):
            self.assertEqual(self.client.patch(url, payload, format='json').status_code, 400)
        response = self.client.patch(url, {'name': 'Permitida', 'current_location': None}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['name'], 'Permitida')
        self.assertEqual(
            self.client.patch(url, {'name': 'Não salvar', 'unit_type': UnitType.USA}, format='json').status_code,
            409,
        )
        unit.refresh_from_db()
        self.assertEqual(unit.name, 'Permitida')
        self.assertEqual(unit.history.count(), 1)

    def test_maintenance_history_permissions_pagination_and_schema(self):
        unit = self.create_unit()
        maintenance = reverse('fleet:fleet_unit_maintenance', args=[unit.pk])
        history = reverse('fleet:fleet_unit_history', args=[unit.pk])
        self.client.force_authenticate(self.operator)
        self.assertEqual(self.client.post(maintenance, {}, format='json').status_code, 403)
        self.assertEqual(self.client.get(history).status_code, 403)
        self.client.force_authenticate(self.admin_user)
        response = self.client.post(maintenance, {}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], FleetUnit.UnitStatus.MAINTENANCE)
        self.assertEqual(self.client.post(maintenance, {'status': 'BUSY'}, format='json').status_code, 400)
        self.assertEqual(self.client.delete(maintenance, {}, format='json').status_code, 200)
        FleetUnitHistory.objects.bulk_create([
            FleetUnitHistory(
                unit=unit, actor=self.admin_user,
                action=FleetUnitHistory.Action.UNIT_UPDATED,
                changed_fields=['name'],
                request_id=f'00000000-0000-0000-0000-{index:012d}',
            )
            for index in range(23)
        ])
        expected_ids = list(
            FleetUnitHistory.objects.filter(unit=unit)
            .order_by('-created_at', '-id').values_list('id', flat=True)
        )
        listed = self.client.get(history)
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.data['count'], 25)
        self.assertEqual(len(listed.data['results']), 20)
        self.assertEqual(listed.data['results'][0]['actor']['username'], self.admin_user.username)
        self.assertNotIn('email', listed.data['results'][0]['actor'])
        second_page = self.client.get(history, {'page': 2})
        self.assertEqual(second_page.status_code, 200)
        self.assertEqual(len(second_page.data['results']), 5)
        first_ids = [entry['id'] for entry in listed.data['results']]
        second_ids = [entry['id'] for entry in second_page.data['results']]
        self.assertFalse(set(first_ids) & set(second_ids))
        self.assertEqual(first_ids + second_ids, expected_ids)
        self.assertEqual(self.client.get(reverse('fleet:fleet_unit_history', args=[999999])).status_code, 404)

        schema = APIClient().get(reverse('schema'), HTTP_ACCEPT='application/vnd.oai.openapi+json')
        self.assertIn('/api/v1/fleet/units/{id}/maintenance/', schema.data['paths'])
        self.assertIn('/api/v1/fleet/units/{id}/history/', schema.data['paths'])


class FleetAdministrationAdminTests(FleetAdministrationMixin, TestCase):
    def setUp(self):
        self.root = User.objects.create_superuser('fleet-root', password=PASSWORD)
        self.client.force_login(self.root)
        self.unit = self.create_unit()

    def test_unit_and_history_admin_are_read_only(self):
        unit_admin = admin.site._registry[FleetUnit]
        self.assertFalse(unit_admin.has_add_permission(None))
        change_url = reverse('admin:fleet_fleetunit_change', args=[self.unit.pk])
        response = self.client.post(change_url, {
            'name': 'Alterada', 'license_plate': 'NEW-0001', 'unit_type': UnitType.USA,
            'status': FleetUnit.UnitStatus.MAINTENANCE, 'capabilities': '{}', '_save': 'Salvar',
        })
        self.assertEqual(response.status_code, 403)
        self.unit.refresh_from_db()
        self.assertNotEqual(self.unit.name, 'Alterada')
        self.assertEqual(self.client.post(reverse('admin:fleet_fleetunit_add'), {}).status_code, 403)
        self.assertEqual(
            self.client.post(reverse('admin:fleet_fleetunit_delete', args=[self.unit.pk]), {'post': 'yes'}).status_code,
            403,
        )

        history = FleetUnitHistory.objects.create(
            unit=self.unit, actor=self.root,
            action=FleetUnitHistory.Action.UNIT_CREATED,
            request_id=self.request_id,
        )
        self.assertEqual(
            self.client.post(
                reverse('admin:fleet_fleetunithistory_change', args=[history.pk]),
                {'action': FleetUnitHistory.Action.UNIT_UPDATED, '_save': 'Salvar'},
            ).status_code,
            403,
        )


class FleetAdministrationConcurrencyTests(FleetAdministrationMixin, TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.actor = self.create_user('concurrent-admin')

    def concurrent(self, operations):
        barrier = Barrier(len(operations))

        def run(operation):
            close_old_connections(); barrier.wait()
            try:
                operation()
                return 'ok'
            except (
                FleetUnitConflictError, DuplicateLicensePlateError,
                MissionStateError, UnitUnavailableError, IntegrityError,
            ):
                return 'conflict'
            finally:
                close_old_connections()

        with patch('fleet.services.publish_fleet_event'):
            with ThreadPoolExecutor(max_workers=len(operations)) as executor:
                return list(executor.map(run, operations))

    def test_maintenance_competes_with_dispatch_without_partial_state(self):
        unit = self.create_unit()
        mission = create_mission('Concorrente', -9, -35)
        results = self.concurrent([
            lambda: start_unit_maintenance(
                unit_id=unit.pk, actor=User.objects.get(pk=self.actor.pk),
                request_id='00000000-0000-0000-0000-000000000201',
            ),
            lambda: assign_unit_to_mission(Mission.objects.get(pk=mission.pk), unit.pk),
        ])
        self.assertEqual(sorted(results), ['conflict', 'ok'])
        unit.refresh_from_db(); mission.refresh_from_db()
        valid = (
            unit.status == FleetUnit.UnitStatus.MAINTENANCE
            and mission.status == Mission.MissionStatus.PENDENTE
            and unit.history.count() == 1
        ) or (
            unit.status == FleetUnit.UnitStatus.BUSY
            and mission.status == Mission.MissionStatus.EM_ANDAMENTO
            and unit.history.count() == 0
        )
        self.assertTrue(valid)

    def test_simultaneous_maintenance_and_duplicate_plate_are_serialized(self):
        unit = self.create_unit()
        results = self.concurrent([
            lambda: start_unit_maintenance(
                unit_id=unit.pk, actor=User.objects.get(pk=self.actor.pk),
                request_id='00000000-0000-0000-0000-000000000202',
            ),
            lambda: start_unit_maintenance(
                unit_id=unit.pk, actor=User.objects.get(pk=self.actor.pk),
                request_id='00000000-0000-0000-0000-000000000203',
            ),
        ])
        self.assertEqual(results, ['ok', 'ok'])
        unit.refresh_from_db()
        self.assertEqual(unit.status, FleetUnit.UnitStatus.MAINTENANCE)
        self.assertEqual(unit.history.count(), 1)

        results = self.concurrent([
            lambda: create_fleet_unit(
                actor=User.objects.get(pk=self.actor.pk), request_id=self.request_id,
                name='Primeira', license_plate='RACE-0001', unit_type=UnitType.USB,
                capabilities={},
            ),
            lambda: create_fleet_unit(
                actor=User.objects.get(pk=self.actor.pk), request_id=self.request_id,
                name='Segunda', license_plate='RACE-0001', unit_type=UnitType.USA,
                capabilities={},
            ),
        ])
        self.assertEqual(sorted(results), ['conflict', 'ok'])
        self.assertEqual(FleetUnit.objects.filter(license_plate='RACE-0001').count(), 1)

    def test_maintenance_competes_with_completion_and_cancellation(self):
        for transition in (complete_mission, cancel_mission):
            unit = self.create_unit(status=FleetUnit.UnitStatus.BUSY)
            mission = Mission.objects.create(
                description='Ativa', location=Point(-35, -9, srid=4326),
                status=Mission.MissionStatus.EM_ANDAMENTO, assigned_unit=unit,
            )
            results = self.concurrent([
                lambda unit_id=unit.pk: start_unit_maintenance(
                    unit_id=unit_id, actor=User.objects.get(pk=self.actor.pk),
                    request_id='00000000-0000-0000-0000-000000000204',
                ),
                lambda mission_id=mission.pk, operation=transition: operation(
                    Mission.objects.get(pk=mission_id),
                ),
            ])
            self.assertEqual(sorted(results), ['conflict', 'ok'])
            unit.refresh_from_db(); mission.refresh_from_db()
            self.assertEqual(unit.status, FleetUnit.UnitStatus.AVAILABLE)
            self.assertIn(
                mission.status,
                (Mission.MissionStatus.CONCLUIDA, Mission.MissionStatus.CANCELADA),
            )
            self.assertEqual(unit.history.count(), 0)

    def test_restricted_update_competes_with_dispatch_consistently(self):
        unit = self.create_unit()
        mission = create_mission('Despacho versus edição', -9, -35)
        results = self.concurrent([
            lambda: update_fleet_unit(
                unit_id=unit.pk, actor=User.objects.get(pk=self.actor.pk),
                request_id='00000000-0000-0000-0000-000000000205',
                values={'capabilities': {'oxygen': False}},
            ),
            lambda: assign_unit_to_mission(Mission.objects.get(pk=mission.pk), unit.pk),
        ])
        unit.refresh_from_db(); mission.refresh_from_db()
        self.assertEqual(mission.status, Mission.MissionStatus.EM_ANDAMENTO)
        self.assertEqual(unit.status, FleetUnit.UnitStatus.BUSY)
        self.assertIn(results, (['ok', 'ok'], ['conflict', 'ok']))
        self.assertEqual(unit.history.count(), 1 if results[0] == 'ok' else 0)
        self.assertEqual(
            unit.capabilities,
            {'oxygen': False} if results[0] == 'ok' else {'oxygen': True},
        )

    def test_simultaneous_exit_and_patches_are_serialized(self):
        maintenance = self.create_unit(status=FleetUnit.UnitStatus.MAINTENANCE)
        results = self.concurrent([
            lambda: end_unit_maintenance(
                unit_id=maintenance.pk, actor=User.objects.get(pk=self.actor.pk),
                request_id='00000000-0000-0000-0000-000000000206',
            ),
            lambda: end_unit_maintenance(
                unit_id=maintenance.pk, actor=User.objects.get(pk=self.actor.pk),
                request_id='00000000-0000-0000-0000-000000000207',
            ),
        ])
        self.assertEqual(results, ['ok', 'ok'])
        maintenance.refresh_from_db()
        self.assertEqual(maintenance.status, FleetUnit.UnitStatus.AVAILABLE)
        self.assertEqual(maintenance.history.count(), 1)

        unit = self.create_unit()
        results = self.concurrent([
            lambda: update_fleet_unit(
                unit_id=unit.pk, actor=User.objects.get(pk=self.actor.pk),
                request_id='00000000-0000-0000-0000-000000000208',
                values={'name': 'Nome concorrente'},
            ),
            lambda: update_fleet_unit(
                unit_id=unit.pk, actor=User.objects.get(pk=self.actor.pk),
                request_id='00000000-0000-0000-0000-000000000209',
                values={'current_location': Point(-36, -10, srid=4326)},
            ),
        ])
        self.assertEqual(results, ['ok', 'ok'])
        unit.refresh_from_db()
        self.assertEqual(unit.name, 'Nome concorrente')
        self.assertTrue(unit.current_location.equals_exact(Point(-36, -10, srid=4326), 0))
        self.assertEqual(unit.history.count(), 2)
