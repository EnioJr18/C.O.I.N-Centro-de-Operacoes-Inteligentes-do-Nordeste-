import asyncio
from unittest.mock import patch

from django.test import TestCase, override_settings


class HealthCheckTests(TestCase):
    def test_liveness_never_accesses_database_and_methods_are_restricted(self):
        with patch('common.health.connection.cursor') as cursor:
            response = self.client.get('/health/live/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'ok'})
        cursor.assert_not_called()
        for path in ('/health/live/', '/health/ready/', '/health/realtime/'):
            with self.subTest(path=path):
                response = self.client.post(path)
                self.assertEqual(response.status_code, 405)
                self.assertEqual(response['Allow'], 'GET')

    def test_readiness_confirms_postgis_without_exposing_details(self):
        response = self.client.get('/health/ready/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'ok'})

    def test_readiness_database_failure_is_generic_and_safe(self):
        secret = 'postgresql://user:credential@private.example/coin'
        with self.assertLogs('common.health', level='WARNING') as logs, patch(
            'common.health.connection.cursor', side_effect=RuntimeError(secret)
        ):
            response = self.client.get('/health/ready/')
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {'status': 'unavailable'})
        self.assertNotIn(secret, response.content.decode() + ''.join(logs.output))

    def test_realtime_uses_selected_in_memory_layer_and_cleans_group(self):
        response = self.client.get('/health/realtime/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'ok'})

    @override_settings(HEALTHCHECK_TIMEOUT_MS=10)
    def test_realtime_timeout_is_generic(self):
        class SlowLayer:
            async def new_channel(self, prefix):
                await asyncio.sleep(1)

        with patch('common.health.get_channel_layer', return_value=SlowLayer()):
            response = self.client.get('/health/realtime/')
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {'status': 'unavailable'})

    def test_realtime_failure_attempts_cleanup_without_leaking_error(self):
        class FailingLayer:
            discarded = False

            async def new_channel(self, prefix):
                return 'health.test'

            async def group_add(self, group, channel):
                raise RuntimeError('redis://user:credential@private.example/0')

            async def group_discard(self, group, channel):
                self.discarded = True

        layer = FailingLayer()
        with patch('common.health.get_channel_layer', return_value=layer):
            response = self.client.get('/health/realtime/')
        self.assertEqual(response.status_code, 503)
        self.assertTrue(layer.discarded)
        self.assertNotIn('credential', response.content.decode())
