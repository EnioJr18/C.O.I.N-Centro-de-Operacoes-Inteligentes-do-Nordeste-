from unittest.mock import patch

from django.contrib.auth.models import User
from django.contrib.gis.geos import Point
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from dispatch.models.mission import Mission
from dispatch.services import UnitUnavailableError, assign_unit_to_mission, create_mission
from fleet.models.vehicle import FleetUnit, UnitType


class ApiTestCase(TestCase):
    def setUp(self):
        self.operator = User.objects.create_user(
            'operator-api', 'operator-api@example.com', 'StrongPassword123'
        )
        self.admin = User.objects.create_superuser(
            'admin-api', 'admin-api@example.com', 'StrongPassword123'
        )
        self.client = APIClient()

    def authenticate_as(self, user):
        self.client.force_authenticate(user)

    def create_unit(self, suffix=1, **overrides):
        values = {
            'name': f'Unidade {suffix}',
            'license_plate': f'API-{suffix:04d}',
            'unit_type': UnitType.USB,
            'current_location': Point(-35.0, -9.0, srid=4326),
            'capabilities': {'oxygen': True},
        }
        values.update(overrides)
        return FleetUnit.objects.create(**values)


class FleetApiTestCase(ApiTestCase):
    def test_list_detail_filters_pagination_and_permissions(self):
        available = self.create_unit(1)
        self.create_unit(2, unit_type=UnitType.USA, status=FleetUnit.UnitStatus.MAINTENANCE)

        self.assertEqual(self.client.get(reverse('fleet:fleet_unit_list')).status_code, 401)
        self.authenticate_as(self.operator)
        response = self.client.get(reverse('fleet:fleet_unit_list'), {'status': 'AVAILABLE'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['id'], available.id)
        self.assertEqual(
            response.data['results'][0]['current_location'],
            {'latitude': -9.0, 'longitude': -35.0},
        )
        self.assertEqual(
            self.client.get(reverse('fleet:fleet_unit_list'), {'status': 'UNKNOWN'}).status_code,
            400,
        )
        self.assertEqual(
            self.client.get(reverse('fleet:fleet_unit_detail', args=[available.id])).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(reverse('fleet:fleet_unit_detail', args=[9999])).status_code,
            404,
        )

    def test_fleet_is_read_only_until_an_administration_service_exists(self):
        self.authenticate_as(self.operator)
        self.assertEqual(self.client.post(reverse('fleet:fleet_unit_list'), {}, format='json').status_code, 405)
        self.authenticate_as(self.admin)
        self.assertEqual(self.client.post(reverse('fleet:fleet_unit_list'), {}, format='json').status_code, 405)

    def test_fleet_pagination_uses_consistent_result_envelope(self):
        for index in range(1, 22):
            self.create_unit(index)
        self.authenticate_as(self.admin)
        response = self.client.get(reverse('fleet:fleet_unit_list'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 21)
        self.assertEqual(len(response.data['results']), 20)
        self.assertIsNotNone(response.data['next'])


class MissionApiTestCase(ApiTestCase):
    def test_list_create_detail_and_filters(self):
        older = create_mission('Primeira missão', -9.0, -35.0)
        older.status = Mission.MissionStatus.CANCELADA
        older.save()
        active = create_mission('Segunda missão', -9.1, -35.1)

        self.assertEqual(self.client.get(reverse('dispatch:mission_list')).status_code, 401)
        self.authenticate_as(self.operator)
        listed = self.client.get(reverse('dispatch:mission_list'), {'status': Mission.MissionStatus.PENDENTE})
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.data['count'], 1)
        self.assertEqual(listed.data['results'][0]['id'], active.id)
        self.assertEqual(
            self.client.get(reverse('dispatch:mission_list'), {'created_after': 'not-a-date'}).status_code,
            400,
        )
        created = self.client.post(
            reverse('dispatch:mission_list'),
            {'description': 'Missão criada pela API', 'location': {'latitude': -9.2, 'longitude': -35.2}},
            format='json',
        )
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.data['location'], {'latitude': -9.2, 'longitude': -35.2})
        self.assertIsNone(created.data['assigned_unit'])
        self.assertEqual(
            self.client.post(
                reverse('dispatch:mission_list'),
                {'description': '', 'location': {'latitude': 91, 'longitude': -35.0}},
                format='json',
            ).status_code,
            400,
        )
        self.assertEqual(
            self.client.get(reverse('dispatch:mission_detail', args=[active.id])).status_code,
            200,
        )
        self.assertEqual(self.client.get(reverse('dispatch:mission_detail', args=[9999])).status_code, 404)

    def test_history_is_read_only_and_available_to_operator_and_admin(self):
        mission = create_mission('Missão com histórico', -9.0, -35.0)
        url = reverse('dispatch:mission_history', args=[mission.id])
        self.assertEqual(self.client.get(url).status_code, 401)
        self.authenticate_as(self.operator)
        history = self.client.get(url)
        self.assertEqual(history.status_code, 200)
        self.assertEqual(history.data['count'], 1)
        self.assertEqual(self.client.post(url, {}, format='json').status_code, 405)
        self.authenticate_as(self.admin)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.get(reverse('dispatch:mission_history', args=[9999])).status_code, 404)


class DispatchApiTestCase(ApiTestCase):
    def payload(self, **overrides):
        value = {
            'description': 'Ocorrência API',
            'location': {'latitude': -9.0, 'longitude': -35.0},
        }
        value.update(overrides)
        return value

    def test_dispatch_response_and_domain_errors_are_consistent(self):
        self.create_unit()
        url = reverse('fleet:dispatch_emergency')
        self.assertEqual(self.client.post(url, self.payload(), format='json').status_code, 401)
        self.client.credentials(HTTP_AUTHORIZATION='Bearer invalid-token')
        self.assertEqual(self.client.post(url, self.payload(), format='json').status_code, 401)
        self.authenticate_as(self.operator)
        response = self.client.post(url, self.payload(), format='json')
        self.assertEqual(response.status_code, 201)
        self.assertIn('mission', response.data)
        self.assertIn('dispatched_unit', response.data)
        self.assertIn('distance_meters', response.data)
        self.assertEqual(response.data['mission']['status'], Mission.MissionStatus.EM_ANDAMENTO)
        self.assertEqual(
            self.client.post(url, self.payload(location={'latitude': -91, 'longitude': -35.0}), format='json').status_code,
            400,
        )

    def test_dispatch_maps_expected_conflict_without_leaking_internal_details(self):
        self.authenticate_as(self.admin)
        with patch('dispatch.api_views.dispatch_emergency', side_effect=UnitUnavailableError('conflito seguro')):
            response = self.client.post(reverse('fleet:dispatch_emergency'), self.payload(), format='json')
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data['detail'], 'conflito seguro')


class OpenApiTestCase(ApiTestCase):
    def test_schema_and_documentation_expose_the_real_versioned_contract(self):
        schema = self.client.get(reverse('schema'), HTTP_ACCEPT='application/vnd.oai.openapi+json')
        self.assertEqual(schema.status_code, 200)
        self.assertIn('/api/v1/fleet/units/', schema.data['paths'])
        self.assertIn('/api/v1/missions/', schema.data['paths'])
        self.assertIn('/api/v1/missions/{id}/history/', schema.data['paths'])
        self.assertIn('/api/v1/emergencies/dispatch/', schema.data['paths'])
        self.assertIn('/api/v1/auth/login/', schema.data['paths'])
        self.assertNotIn('/fleet/api/v1/emergencies/dispatch/', schema.data['paths'])
        security_schemes = schema.data['components']['securitySchemes']
        self.assertTrue(any(scheme.get('scheme') == 'bearer' for scheme in security_schemes.values()))
        self.assertEqual(self.client.get(reverse('swagger-ui')).status_code, 200)
        self.assertEqual(self.client.get(reverse('redoc')).status_code, 200)

    def test_legacy_dispatch_path_uses_the_same_protected_view(self):
        response = self.client.post(
            reverse('legacy-dispatch-emergency'),
            {'description': 'Compatibilidade', 'location': {'latitude': -9.0, 'longitude': -35.0}},
            format='json',
        )
        self.assertEqual(response.status_code, 401)
