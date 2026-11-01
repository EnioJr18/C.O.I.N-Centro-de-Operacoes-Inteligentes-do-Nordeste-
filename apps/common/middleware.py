import logging
import time
from asgiref.sync import iscoroutinefunction, markcoroutinefunction
from uuid import uuid4

from .request_context import reset_request_id, set_request_id


logger = logging.getLogger(__name__)


class RequestIDMiddleware:
    sync_capable = True
    async_capable = True

    def __init__(self, get_response):
        self.get_response = get_response
        self.is_async = iscoroutinefunction(get_response)
        if self.is_async:
            markcoroutinefunction(self)

    def __call__(self, request):
        if self.is_async:
            return self.__acall__(request)
        request_id = str(uuid4())
        token = set_request_id(request_id)
        request.request_id = request_id
        started_at = time.monotonic()
        try:
            response = self.get_response(request)
            response['X-Request-ID'] = request_id
            logger.info(
                'HTTP concluído method=%s path=%s status=%s duration_ms=%s',
                request.method,
                request.path,
                response.status_code,
                round((time.monotonic() - started_at) * 1000, 2),
            )
            return response
        finally:
            reset_request_id(token)

    async def __acall__(self, request):
        request_id = str(uuid4())
        token = set_request_id(request_id)
        request.request_id = request_id
        started_at = time.monotonic()
        try:
            response = await self.get_response(request)
            response['X-Request-ID'] = request_id
            logger.info(
                'HTTP concluído method=%s path=%s status=%s duration_ms=%s',
                request.method,
                request.path,
                response.status_code,
                round((time.monotonic() - started_at) * 1000, 2),
            )
            return response
        finally:
            reset_request_id(token)
