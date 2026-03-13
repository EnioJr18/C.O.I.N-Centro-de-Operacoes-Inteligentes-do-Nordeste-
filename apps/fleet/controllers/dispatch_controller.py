import json
from django.http import JsonResponse
from django.views import View
from fleet.selectors import get_nearest_available_units

class DispatchEmergencyView(View):
    def post(self, request, *args, **kwargs):
        data = json.loads(request.body)
        lat = data.get('latitude')
        lon = data.get('longitude')
        equipment = data.get('equipamento_necessario')

        nearest_units = get_nearest_available_units(lat, lon, equipment)

        response_data = [
            {
                "id": unit.id,
                "name": unit.name,
                "distance_meters": round(unit.distance.m, 2)
            }
            for unit in nearest_units
        ]

        return JsonResponse({"available_units": response_data})