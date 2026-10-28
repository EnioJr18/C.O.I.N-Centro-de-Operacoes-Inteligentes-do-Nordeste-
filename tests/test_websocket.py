import asyncio
from datetime import datetime, timedelta
from unittest.mock import patch
from uuid import UUID

from asgiref.sync import async_to_sync
from channels.db import database_sync_to_async
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator
from django.contrib.auth.models import User
from django.contrib.gis.geos import Point
from django.db import transaction
from django.test import TransactionTestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from authentication.models import UserProfile, UserRole
from apps.fleet.consumers import FleetConsumer
from config.asgi import application
from dispatch.models.mission import Mission
from fleet.events import build_dispatch_event
from fleet.models.vehicle import FleetUnit, UnitType


@override_settings(
    WEBSOCKET_ALLOWED_ORIGINS=['http://localhost:5173'],
    CHANNEL_LAYERS={'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}},
    ALLOWED_HOSTS=['testserver'],
)
class FleetWebSocketTests(TransactionTestCase):
    def setUp(self):
        async_to_sync(get_channel_layer().flush)()
        self.operator = User.objects.create_user('ws-operator', password='test-password')
        self.admin = User.objects.create_user('ws-admin', password='test-password')
        self.admin.profile.role = UserRole.ADMIN
        self.admin.profile.save()
        self.superuser = User.objects.create_superuser('ws-super', password='test-password')
        self.superuser.profile.delete()
        self.inactive = User.objects.create_user('ws-inactive', password='test-password', is_active=False)
        self.no_profile = User.objects.create_user('ws-no-profile', password='test-password')
        self.no_profile.profile.delete()
        self.staff = User.objects.create_user('ws-staff', password='test-password', is_staff=True)
        self.staff.profile.role = 'OTHER'
        self.staff.profile.save()

    def communicator(self, token=None, origin=b'http://localhost:5173', protocols=None):
        if protocols is None:
            protocols = ['coin.v1', 'coin.jwt.' + str(token)] if token else []
        headers = [(b'origin', origin)] if origin is not None else []
        return WebsocketCommunicator(application, '/ws/fleet/', headers=headers, subprotocols=protocols)

    def test_handshake_authentication_and_authorization(self):
        expired = AccessToken.for_user(self.operator)
        expired.set_exp(lifetime=timedelta(seconds=-10))
        missing_user = User.objects.create_user('ws-deleted', password='test-password')
        deleted_token = str(AccessToken.for_user(missing_user))
        missing_user.delete()
        cases = [
            (None, None, 4401),
            (None, ['coin.v1', 'wrong-format'], 4401),
            ('invalid', None, 4401),
            (str(expired), None, 4401),
            (str(RefreshToken.for_user(self.operator)), None, 4401),
            (deleted_token, None, 4401),
            (str(AccessToken.for_user(self.inactive)), None, 4401),
            (str(AccessToken.for_user(self.no_profile)), None, 4403),
            (str(AccessToken.for_user(self.staff)), None, 4403),
        ]
        allowed = [str(AccessToken.for_user(user)) for user in (self.operator, self.admin, self.superuser)]

        async def scenario():
            for token, protocols, code in cases:
                communicator = self.communicator(token, protocols=protocols)
                self.assertEqual(await communicator.connect(), (False, code))
                self.assertFalse(get_channel_layer().groups.get('fleet_updates'))
                await communicator.disconnect()
            for token in allowed:
                communicator = self.communicator(token)
                self.assertEqual(await communicator.connect(), (True, 'coin.v1'))
                await communicator.disconnect()
                self.assertFalse(get_channel_layer().groups.get('fleet_updates'))

        async_to_sync(scenario)()

    def test_origin_policy(self):
        token = str(AccessToken.for_user(self.operator))

        async def scenario():
            for origin in (None, b'https://malicious.example'):
                communicator = self.communicator(token, origin=origin)
                connected, _ = await communicator.connect()
                self.assertFalse(connected)
                self.assertFalse(get_channel_layer().groups.get('fleet_updates'))
                await communicator.disconnect()
            communicator = self.communicator(token)
            self.assertEqual(await communicator.connect(), (True, 'coin.v1'))
            await communicator.disconnect()

        async_to_sync(scenario)()

    def test_expiration_after_handshake_closes_connection(self):
        token = AccessToken.for_user(self.operator)
        token.set_exp(lifetime=timedelta(seconds=2))
        token = str(token)

        async def scenario():
            communicator = self.communicator(token)
            self.assertEqual(await communicator.connect(), (True, 'coin.v1'))
            message = await communicator.receive_output(timeout=4)
            self.assertEqual(message, {'type': 'websocket.close', 'code': 4401})
            self.assertFalse(get_channel_layer().groups.get('fleet_updates'))
            await communicator.disconnect()

        async_to_sync(scenario)()

    def test_disconnect_cancels_expiry_monitor_and_removes_membership(self):
        token = str(AccessToken.for_user(self.operator))

        async def scenario():
            started = asyncio.Event()
            stopped = asyncio.Event()
            gate = asyncio.Event()

            async def monitor(consumer):
                started.set()
                try:
                    await gate.wait()
                finally:
                    stopped.set()

            with patch.object(FleetConsumer, '_expire', monitor):
                communicator = self.communicator(token)
                self.assertEqual(await communicator.connect(), (True, 'coin.v1'))
                await asyncio.wait_for(started.wait(), timeout=2)
                await communicator.disconnect()
                self.assertTrue(stopped.is_set())
                self.assertFalse(get_channel_layer().groups.get('fleet_updates'))

        async_to_sync(scenario)()

    def test_group_add_failure_is_cleaned_and_logged_safely(self):
        token = str(AccessToken.for_user(self.operator))
        marker = 'redis://user:sensitive-value@redis.example.test/0'

        async def scenario():
            layer = get_channel_layer()
            original_add = layer.group_add

            async def partially_add_then_fail(group, channel):
                await original_add(group, channel)
                raise RuntimeError(marker)

            with patch.object(layer, 'group_add', side_effect=partially_add_then_fail):
                with self.assertLogs(FleetConsumer.__module__, level='ERROR') as logs:
                    communicator = self.communicator(token)
                    self.assertEqual(await communicator.connect(), (False, 1011))
                    await communicator.disconnect()
            self.assertFalse(layer.groups.get('fleet_updates'))
            self.assertNotIn(marker, str(logs.output))
            self.assertIn('Falha ao associar conexão ao grupo de frota.', str(logs.output))

        async_to_sync(scenario)()

    def test_group_discard_failure_does_not_escape_disconnect(self):
        token = str(AccessToken.for_user(self.operator))
        marker = 'redis://user:sensitive-value@redis.example.test/0'

        async def scenario():
            layer = get_channel_layer()
            communicator = self.communicator(token)
            self.assertEqual(await communicator.connect(), (True, 'coin.v1'))
            with patch.object(layer, 'group_discard', side_effect=RuntimeError(marker)):
                with self.assertLogs(FleetConsumer.__module__, level='ERROR') as logs:
                    await communicator.disconnect()
            self.assertNotIn(marker, str(logs.output))
            self.assertIn('Falha ao remover conexão do grupo de frota.', str(logs.output))
            await layer.flush()

        async_to_sync(scenario)()

    def test_revocation_prevents_delivery(self):
        token = str(AccessToken.for_user(self.operator))

        async def scenario():
            communicator = self.communicator(token)
            self.assertEqual(await communicator.connect(), (True, 'coin.v1'))
            await database_sync_to_async(User.objects.filter(pk=self.operator.pk).update)(is_active=False)
            await get_channel_layer().group_send('fleet_updates', {'type': 'send_fleet_update', 'message': {'action': 'DISPATCH'}})
            self.assertEqual(await communicator.receive_output(), {'type': 'websocket.close', 'code': 4403})
            self.assertFalse(get_channel_layer().groups.get('fleet_updates'))
            await communicator.disconnect()

        async_to_sync(scenario)()

    def test_role_revocation_prevents_delivery(self):
        token = str(AccessToken.for_user(self.operator))

        async def scenario():
            communicator = self.communicator(token)
            self.assertEqual(await communicator.connect(), (True, 'coin.v1'))
            await database_sync_to_async(UserProfile.objects.filter(user_id=self.operator.pk).delete)()
            await get_channel_layer().group_send('fleet_updates', {'type': 'send_fleet_update', 'message': {'action': 'DISPATCH'}})
            self.assertEqual(await communicator.receive_output(), {'type': 'websocket.close', 'code': 4403})
            await communicator.disconnect()

        async_to_sync(scenario)()

    def test_two_clients_receive_one_safe_event_and_client_frames_do_not_dispatch(self):
        unit = FleetUnit.objects.create(name='Alfa', license_plate='WS-1234', unit_type=UnitType.USB)
        mission = Mission.objects.create(description='Teste', location=Point(-35, -9, srid=4326), assigned_unit=unit)
        event = build_dispatch_event(mission, mission.location)
        UUID(event['event_id'])
        self.assertEqual(event['schema_version'], 1)
        self.assertIsNotNone(datetime.fromisoformat(event['occurred_at']).utcoffset())
        self.assertEqual(set(event), {'event_id', 'schema_version', 'occurred_at', 'action', 'unit_id', 'unit_name', 'new_status', 'mission_id', 'lat', 'lon'})
        tokens = [str(AccessToken.for_user(user)) for user in (self.operator, self.admin)]

        async def scenario():
            clients = [self.communicator(token) for token in tokens]
            for client in clients:
                self.assertEqual(await client.connect(), (True, 'coin.v1'))
            await clients[0].send_json_to({'action': 'dispatch'})
            await get_channel_layer().group_send('fleet_updates', {'type': 'send_fleet_update', 'message': event})
            for client in clients:
                self.assertEqual(await client.receive_json_from(), event)
                self.assertTrue(await client.receive_nothing())
            for client in clients:
                await client.disconnect()
            self.assertFalse(get_channel_layer().groups.get('fleet_updates'))

        async_to_sync(scenario)()
        self.assertEqual(Mission.objects.count(), 1)

    def test_publication_failure_does_not_turn_confirmed_dispatch_into_http_error(self):
        unit = FleetUnit.objects.create(
            name='Alfa', license_plate='WS-1234', unit_type=UnitType.USB,
            current_location=Point(-35, -9, srid=4326),
        )
        client = APIClient()
        client.force_authenticate(self.operator)
        with patch('fleet.events.get_channel_layer', side_effect=RuntimeError('sensitive')):
            with self.assertLogs('fleet.events', level='ERROR') as logs:
                response = client.post(
                    reverse('fleet:dispatch_emergency'),
                    {'description': 'Teste', 'location': {'latitude': -9, 'longitude': -35}},
                    format='json',
                )
        self.assertEqual(response.status_code, 201)
        self.assertNotIn('sensitive', str(logs.output))
        unit.refresh_from_db()
        self.assertEqual(unit.status, FleetUnit.UnitStatus.BUSY)
        self.assertTrue(Mission.objects.filter(pk=response.data['mission']['id']).exists())

    def test_dispatch_publishes_once_only_after_commit_and_never_after_rollback(self):
        FleetUnit.objects.create(
            name='Alfa', license_plate='WS-1234', unit_type=UnitType.USB,
            current_location=Point(-35, -9, srid=4326),
        )
        client = APIClient()
        client.force_authenticate(self.operator)
        payload = {'description': 'Teste', 'location': {'latitude': -9, 'longitude': -35}}
        with patch('dispatch.api_views.publish_fleet_event') as publish:
            with transaction.atomic():
                response = client.post(reverse('fleet:dispatch_emergency'), payload, format='json')
                self.assertEqual(response.status_code, 201)
                publish.assert_not_called()
            publish.assert_called_once()
            self.assertEqual(publish.call_args.args[0]['mission_id'], response.data['mission']['id'])

        FleetUnit.objects.update(status=FleetUnit.UnitStatus.AVAILABLE)
        with patch('dispatch.api_views.publish_fleet_event') as publish:
            with transaction.atomic():
                response = client.post(reverse('fleet:dispatch_emergency'), payload, format='json')
                self.assertEqual(response.status_code, 201)
                transaction.set_rollback(True)
            publish.assert_not_called()
