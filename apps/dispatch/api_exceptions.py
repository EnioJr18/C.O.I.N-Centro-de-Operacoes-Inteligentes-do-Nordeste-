import logging

from rest_framework.response import Response
from rest_framework.views import exception_handler

from .services import (
    InvalidMissionError,
    MissionStateError,
    NoEligibleUnitError,
    UnitUnavailableError,
)


logger = logging.getLogger(__name__)


def api_exception_handler(exc, context):
    """Maps predictable domain errors to safe, consistent DRF responses."""
    if isinstance(exc, InvalidMissionError):
        return Response({'detail': str(exc)}, status=400)
    if isinstance(exc, NoEligibleUnitError):
        return Response({'detail': str(exc)}, status=404)
    if isinstance(exc, (MissionStateError, UnitUnavailableError)):
        return Response({'detail': str(exc)}, status=409)

    response = exception_handler(exc, context)
    if response is not None:
        return response

    logger.exception('Erro interno não tratado na API', exc_info=exc)
    return Response({'detail': 'Erro interno do servidor.'}, status=500)
