from datetime import timedelta

from django.contrib.auth.models import User
from django.contrib.gis.geos import Point
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import UserRole
from dispatch.models.mission import Mission
from fleet.models.vehicle import FleetUnit, UnitType

from .selectors import get_dashboard_summary


PASSWORD = 'StrongPassword123'


class DashboardSummarySelectorTestCase(TestCase):
    def create_unit(self, suffix, **overrides):
        values = {
            'name': f'Unidade {suffix}',
            'license_plate': f'DSH-{suffix:04d}',
            'unit_type': UnitType.USB,
            'current_location': Point(-35.0, -9.0, srid=4326),
        }
        values.update(overrides)
        return FleetUnit.objects.create(**values)

    def create_mission(self, suffix, status, **overrides):
        values = {
            'description': f'Missão {suffix}',
            'location': Point(-35.0, -9.0, srid=4326),
            'status': status,
        }
        values.update(overrides)
        return Mission.objects.create(**values)

    def test_empty_database_has_complete_zeroed_contract(self):
        with self.assertNumQueries(3):
            summary = get_dashboard_summary()

        self.assertEqual(summary['fleet'], {
            'total': 0,
            'available': 0,
            'availability_percentage': 0.0,
            'with_location': 0,
            'without_location': 0,
            'by_status': {'AVAILABLE': 0, 'BUSY': 0, 'MAINTENANCE': 0},
        })
        self.assertEqual(summary['missions'], {
            'total': 0,
            'by_status': {
                'Pendente': 0,
                'Em Andamento': 0,
                'Concluída': 0,
                'Cancelada': 0,
            },
            'recent': [],
        })

    def test_single_available_unit_has_full_availability_without_location(self):
        self.create_unit(1, current_location=None)

        summary = get_dashboard_summary()

        self.assertEqual(summary['fleet']['total'], 1)
        self.assertEqual(summary['fleet']['available'], 1)
        self.assertEqual(summary['fleet']['availability_percentage'], 100.0)
        self.assertEqual(summary['fleet']['with_location'], 0)
        self.assertEqual(summary['fleet']['without_location'], 1)
        self.assertEqual(summary['fleet']['by_status'], {
            'AVAILABLE': 1, 'BUSY': 0, 'MAINTENANCE': 0,
        })

    def test_aggregates_fleet_missions_and_recent_rows_in_three_queries(self):
        assigned = self.create_unit(1)
        self.create_unit(2, current_location=None)
        busy_one = self.create_unit(3, status=FleetUnit.UnitStatus.BUSY)
        busy_two = self.create_unit(4, status=FleetUnit.UnitStatus.BUSY, current_location=None)
        self.create_unit(5, status=FleetUnit.UnitStatus.BUSY)
        self.create_unit(6, status=FleetUnit.UnitStatus.MAINTENANCE, current_location=None)

        statuses = (
            Mission.MissionStatus.PENDENTE,
            Mission.MissionStatus.PENDENTE,
            Mission.MissionStatus.PENDENTE,
            Mission.MissionStatus.EM_ANDAMENTO,
            Mission.MissionStatus.EM_ANDAMENTO,
            Mission.MissionStatus.CONCLUIDA,
            Mission.MissionStatus.CANCELADA,
        )
        base = timezone.now() - timedelta(days=1)
        missions = []
        for index, status in enumerate(statuses, start=1):
            mission = self.create_mission(
                index,
                status,
                assigned_unit=(
                    busy_one if index == 4
                    else busy_two if index == 5
                    else assigned if index == 7
                    else None
                ),
            )
            Mission.objects.filter(pk=mission.pk).update(
                created_at=base + timedelta(minutes=index if index < 6 else 6),
            )
            mission.refresh_from_db()
            missions.append(mission)

        with self.assertNumQueries(3):
            summary = get_dashboard_summary()

        self.assertEqual(summary['fleet']['total'], 6)
        self.assertEqual(summary['fleet']['available'], 2)
        self.assertEqual(summary['fleet']['availability_percentage'], 33.3)
        self.assertEqual(summary['fleet']['with_location'], 3)
        self.assertEqual(summary['fleet']['without_location'], 3)
        self.assertEqual(summary['fleet']['by_status'], {
            'AVAILABLE': 2, 'BUSY': 3, 'MAINTENANCE': 1,
        })
        self.assertEqual(summary['missions']['total'], 7)
        self.assertEqual(summary['missions']['by_status'], {
            'Pendente': 3, 'Em Andamento': 2, 'Concluída': 1, 'Cancelada': 1,
        })
        recent = summary['missions']['recent']
        self.assertEqual(len(recent), 5)
        self.assertEqual([mission.id for mission in recent], [missions[6].id, missions[5].id, missions[4].id, missions[3].id, missions[2].id])
        self.assertEqual(recent[0].assigned_unit, assigned)
        self.assertIsNone(recent[1].assigned_unit)


class DashboardSummaryAPITestCase(TestCase):
    def setUp(self):
        self.operator = User.objects.create_user('operator', 'operator@example.com', PASSWORD)
        self.admin = User.objects.create_user('admin', 'admin@example.com', PASSWORD)
        self.admin.profile.role = UserRole.ADMIN
        self.admin.profile.save(update_fields=['role'])
        self.superuser = User.objects.create_superuser('root', 'root@example.com', PASSWORD)
        self.url = reverse('dashboard:summary')

    def authenticated_client(self, user):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        return client

    def test_operational_roles_and_superuser_can_read_safe_contract(self):
        for user in (self.operator, self.admin, self.superuser):
            response = self.authenticated_client(user).get(self.url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(set(response.data), {'generated_at', 'fleet', 'missions'})
            self.assertEqual(
                set(response.data['fleet']),
                {'total', 'available', 'availability_percentage', 'with_location', 'without_location', 'by_status'},
            )
            self.assertEqual(set(response.data['missions']), {'total', 'by_status', 'recent'})
            self.assertNotIn('users', response.data)
            self.assertNotIn('events', response.data)

    def test_anonymous_invalid_and_inactive_credentials_are_rejected(self):
        self.assertEqual(APIClient().get(self.url).status_code, 401)
        invalid = APIClient()
        invalid.credentials(HTTP_AUTHORIZATION='Bearer invalid-token')
        self.assertEqual(invalid.get(self.url).status_code, 401)
        expired_token = AccessToken.for_user(self.operator)
        expired_token.set_exp(lifetime=timedelta(seconds=-1))
        expired = APIClient()
        expired.credentials(HTTP_AUTHORIZATION=f'Bearer {expired_token}')
        self.assertEqual(expired.get(self.url).status_code, 401)
        inactive = User.objects.create_user(
            'inactive', 'inactive@example.com', PASSWORD, is_active=False,
        )
        self.assertEqual(self.authenticated_client(inactive).get(self.url).status_code, 401)

    def test_users_without_operational_role_are_forbidden(self):
        no_profile = User.objects.create_user('legacy', 'legacy@example.com', PASSWORD)
        no_profile.profile.delete()
        self.assertEqual(self.authenticated_client(no_profile).get(self.url).status_code, 403)

        no_role = User.objects.create_user('staff', 'staff@example.com', PASSWORD, is_staff=True)
        no_role.profile.role = 'OTHER'
        no_role.profile.save(update_fields=['role'])
        self.assertEqual(self.authenticated_client(no_role).get(self.url).status_code, 403)

    def test_openapi_documents_dashboard_contract(self):
        response = APIClient().get(reverse('schema'), HTTP_ACCEPT='application/vnd.oai.openapi+json')
        self.assertEqual(response.status_code, 200)
        operation = response.data['paths']['/api/v1/dashboard/summary/']['get']
        self.assertIn('dashboard', operation['tags'])
        self.assertIn('200', operation['responses'])
        self.assertIn('401', operation['responses'])
        self.assertIn('403', operation['responses'])
