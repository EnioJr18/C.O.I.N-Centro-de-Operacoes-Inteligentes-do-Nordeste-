import json
from django.http import JsonResponse
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from fleet.models.vehicle import FleetUnit
from dispatch.models.mission import Mission
from fleet.selectors import get_nearest_available_units
from django.contrib.gis.geos import Point
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

@method_decorator(csrf_exempt, name='dispatch')
class DispatchEmergencyView(View):
    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
            lat = data.get('latitude')
            lon = data.get('longitude')
            description = data.get('description')
            
            required_type = data.get('required_type')
            requirements = data.get('requirements')

            if lat is None or lon is None:
                return JsonResponse({"error": "Latitude e Longitude são obrigatórios!"}, status=400)
            
            nearest_units = get_nearest_available_units(
                lat=lat, 
                lon=lon, 
                required_type=required_type, 
                requirements=requirements
            )
            
            if not nearest_units:
                return JsonResponse({"error": "Nenhuma viatura disponível na região com os requisitos solicitados!"}, status=404)

            best_unit = nearest_units[0]
            best_unit_id = best_unit.id
            
            best_distance = best_unit.distance.m if hasattr(best_unit, 'distance') else getattr(best_unit, 'distance_meters', 0)

            with transaction.atomic():
                unit = FleetUnit.objects.select_for_update().get(id=best_unit_id)
                
                if unit.status != 'AVAILABLE':
                    return JsonResponse({"error": "Viatura foi engajada por outro chamado uma fração de segundo atrás!"}, status=409)

                unit.status = 'BUSY'
                unit.save()

                location_point = Point(float(lon), float(lat), srid=4326)

                mission = Mission.objects.create(
                    description=description,
                    assigned_unit=unit,
                    status='Em Andamento',
                    location=location_point
                )

            channel_layer = get_channel_layer()
            
            evento_mapa = {
                'type': 'send_fleet_update',
                'message': {
                    'action': 'DISPATCH',
                    'unit_id': best_unit_id,
                    'unit_name': unit.name,
                    'new_status': unit.status,
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
                "dispatched_unit": unit.name,
                "distance_meters": round(best_distance, 2)
            }, status=201)

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)