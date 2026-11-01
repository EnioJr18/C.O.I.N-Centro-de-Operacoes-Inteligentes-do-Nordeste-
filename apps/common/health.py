import asyncio
import logging
from uuid import uuid4

from channels.layers import get_channel_layer
from django.conf import settings
from django.db import connection, transaction
from django.http import JsonResponse


logger = logging.getLogger(__name__)


def _method_not_allowed():
    response = JsonResponse({'status': 'method_not_allowed'}, status=405)
    response['Allow'] = 'GET'
    return response


def live(request):
    if request.method != 'GET':
        return _method_not_allowed()
    return JsonResponse({'status': 'ok'})


def ready(request):
    if request.method != 'GET':
        return _method_not_allowed()
    try:
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(
                "SELECT set_config('statement_timeout', %s, true)",
                [str(settings.HEALTHCHECK_TIMEOUT_MS)],
            )
            cursor.execute('SELECT PostGIS_Version()')
            cursor.fetchone()
    except Exception:
        logger.warning('Readiness do banco indisponível.')
        return JsonResponse({'status': 'unavailable'}, status=503)
    return JsonResponse({'status': 'ok'})


async def realtime(request):
    if request.method != 'GET':
        return _method_not_allowed()
    layer = get_channel_layer()
    group = f'health.{uuid4().hex}'
    channel = None
    timeout = settings.HEALTHCHECK_TIMEOUT_MS / 1000
    try:
        if layer is None:
            raise RuntimeError('Channel layer ausente.')
        channel = await asyncio.wait_for(layer.new_channel('health.'), timeout)
        await asyncio.wait_for(layer.group_add(group, channel), timeout)
        await asyncio.wait_for(
            layer.group_send(group, {'type': 'health.check', 'nonce': group}), timeout
        )
        message = await asyncio.wait_for(layer.receive(channel), timeout)
        if message.get('nonce') != group:
            raise RuntimeError('Resposta de saúde inválida.')
    except Exception:
        logger.warning('Saúde do tempo real indisponível.')
        return JsonResponse({'status': 'unavailable'}, status=503)
    finally:
        if layer is not None and channel is not None:
            try:
                await asyncio.wait_for(layer.group_discard(group, channel), timeout)
            except Exception:
                logger.warning('Falha ao limpar verificação de saúde do tempo real.')
    return JsonResponse({'status': 'ok'})
