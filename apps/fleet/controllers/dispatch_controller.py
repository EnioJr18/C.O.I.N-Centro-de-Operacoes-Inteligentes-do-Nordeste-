import json
import logging
from django.http import JsonResponse
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from fleet.models.vehicle import FleetUnit, UnitType
from dispatch.services import (
    DispatchDomainError,
    InvalidMissionError,
    NoEligibleUnitError,
    UnitUnavailableError,
    dispatch_emergency,
)
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync


logger = logging.getLogger(__name__)


def _validate_payload(data):
    if not isinstance(data, dict):
        raise InvalidMissionError("O corpo da requisição deve ser um objeto JSON.")

    description = data.get("description")
    if not isinstance(description, str) or not description.strip():
        raise InvalidMissionError("A descrição da missão é obrigatória.")

    lat = data.get("latitude")
    lon = data.get("longitude")
    if isinstance(lat, bool) or isinstance(lon, bool) or not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
        raise InvalidMissionError("Latitude e longitude devem ser valores numéricos.")
    if not -90 <= lat <= 90 or not -180 <= lon <= 180:
        raise InvalidMissionError("Latitude ou longitude fora dos limites permitidos.")

    required_type = data.get("required_type")
    if required_type is not None and required_type not in UnitType.values:
        raise InvalidMissionError("Tipo de viatura inválido.")

    requirements = data.get("requirements")
    if requirements is not None and not isinstance(requirements, dict):
        raise InvalidMissionError("Requirements deve ser um objeto JSON.")

    return description, lat, lon, required_type, requirements

@method_decorator(csrf_exempt, name='dispatch')
class DispatchEmergencyView(View):
    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
            description, lat, lon, required_type, requirements = _validate_payload(data)
            mission, distance_meters = dispatch_emergency(
                description=description,
                latitude=lat,
                longitude=lon,
                required_type=required_type,
                requirements=requirements,
            )

            channel_layer = get_channel_layer()
            
            evento_mapa = {
                'type': 'send_fleet_update',
                'message': {
                    'action': 'DISPATCH',
                    'unit_id': mission.assigned_unit_id,
                    'unit_name': mission.assigned_unit.name,
                    'new_status': FleetUnit.UnitStatus.BUSY,
                    'mission_id': mission.id,
                    'lat': lat,
                    'lon': lon
                }
            }
            
            async_to_sync(channel_layer.group_send)(
                'fleet_updates',
                evento_mapa
            )

            return JsonResponse({
                "message": "Despacho realizado com sucesso!",
                "mission_id": mission.id,
                "dispatched_unit": mission.assigned_unit.name,
                "distance_meters": round(distance_meters, 2)
            }, status=201)

        except json.JSONDecodeError:
            return JsonResponse({"error": "JSON inválido."}, status=400)
        except NoEligibleUnitError as exc:
            return JsonResponse({"error": str(exc)}, status=404)
        except UnitUnavailableError as exc:
            return JsonResponse({"error": str(exc)}, status=409)
        except DispatchDomainError as exc:
            return JsonResponse({"error": str(exc)}, status=400)
        except Exception:
            logger.exception("Erro inesperado ao despachar emergência")
            return JsonResponse({"error": "Erro interno ao processar o despacho."}, status=500)
