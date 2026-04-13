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

@method_decorator(csrf_exempt, name='dispatch')
class DispatchEmergencyView(View):
    def post(self, request, *args, **kwargs):
        try:

            data = json.loads(request.body)
            lat = data.get('latitude')
            lon = data.get('longitude')
            description = data.get('description')

            if lat is None or lon is None:
                return JsonResponse({"error": "Latitude e Longitude são obrigatórios!"}, status=400)
            
            nearest_units = get_nearest_available_units(lat, lon)
            
            if not nearest_units:
                return JsonResponse({"error": "Nenhuma viatura disponível na região!"}, status=404)

            best_unit = nearest_units[0]
            best_unit_id = best_unit.id
            
            best_distance = best_unit.distance.m if hasattr(best_unit, 'distance') else getattr(best_unit, 'distance_meters', 0)


            with transaction.atomic():
                unit = FleetUnit.objects.select_for_update().get(id=best_unit_id)
                
                if unit.status != 'AVAILABLE':
                    return JsonResponse({"error": "Viatura foi engajada por outro chamado uma fração de segundo atrás!"}, status=409)

                unit.status = 'Busy'
                unit.save()

                location_point = Point(float(lon), float(lat), srid=4326)

                mission = Mission.objects.create(
                    description=description,
                    assigned_unit=unit,
                    status='Em Andamento',
                    location=location_point
                )


            return JsonResponse({
                "message": "Despacho realizado com sucesso!",
                "mission_id": mission.id,
                "dispatched_unit": unit.name,
                "distance_meters": round(best_distance, 2)
            }, status=201)

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)