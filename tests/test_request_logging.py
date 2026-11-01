import asyncio
import logging
import sys
from io import StringIO
from uuid import UUID

from django.test import AsyncClient, Client, SimpleTestCase, override_settings

from common.logging import JSONFormatter, SafeLogFilter
from common.request_context import get_request_id


class CaptureHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records = []
        self.addFilter(SafeLogFilter())

    def emit(self, record):
        self.records.append(record)


@override_settings(ROOT_URLCONF='tests.request_id_urls')
class RequestIDTests(SimpleTestCase):
    def test_generated_id_ignores_client_header_and_matches_logs(self):
        logger = logging.getLogger('tests.request_id')
        handler = CaptureHandler()
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        try:
            response = Client().get('/sync/', HTTP_X_REQUEST_ID='client-controlled')
        finally:
            logger.removeHandler(handler)
        request_id = response['X-Request-ID']
        UUID(request_id)
        self.assertNotEqual(request_id, 'client-controlled')
        self.assertEqual(response.json()['request_id'], request_id)
        self.assertEqual(handler.records[-1].request_id, request_id)
        self.assertEqual(get_request_id(), '-')

    async def test_async_requests_have_isolated_ids(self):
        first, second = await asyncio.gather(
            AsyncClient().get('/async/'),
            AsyncClient().get('/async/'),
        )
        first_id = first['X-Request-ID']
        second_id = second['X-Request-ID']
        UUID(first_id)
        UUID(second_id)
        self.assertNotEqual(first_id, second_id)
        self.assertEqual(first.json()['request_id'], first_id)
        self.assertEqual(second.json()['request_id'], second_id)
        self.assertEqual(get_request_id(), '-')

    def test_logging_redacts_credentials_and_exception_messages(self):
        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.addFilter(SafeLogFilter())
        handler.setFormatter(JSONFormatter())
        logger = logging.getLogger('tests.redaction')
        logger.addHandler(handler)
        logger.setLevel(logging.ERROR)
        logger.propagate = False
        try:
            try:
                raise RuntimeError('redis://user:exception-passphrase@private.example/0')
            except RuntimeError:
                logger.error(
                    'Authorization=Bearer access-secret protocol=coin.jwt.jwt-secret '
                    'database=postgresql://user:db-secret@private.example/coin',
                    exc_info=sys.exc_info(),
                )
        finally:
            logger.removeHandler(handler)
            logger.propagate = True
        output = stream.getvalue()
        for secret in ('access-secret', 'jwt-secret', 'db-secret', 'exception-passphrase'):
            self.assertNotIn(secret, output)
        self.assertIn('[REDACTED]', output)
        self.assertIn('RuntimeError', output)
