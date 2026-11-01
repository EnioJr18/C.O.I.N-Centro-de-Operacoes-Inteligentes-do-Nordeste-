import asyncio
import logging

from django.http import JsonResponse

from common.request_context import get_request_id


logger = logging.getLogger('tests.request_id')


def sync_view(request):
    logger.info('Requisição de teste concluída.')
    return JsonResponse({'request_id': get_request_id()})


async def async_view(request):
    await asyncio.sleep(0)
    logger.info('Requisição assíncrona de teste concluída.')
    return JsonResponse({'request_id': get_request_id()})


from django.urls import path


urlpatterns = [
    path('sync/', sync_view),
    path('async/', async_view),
]
