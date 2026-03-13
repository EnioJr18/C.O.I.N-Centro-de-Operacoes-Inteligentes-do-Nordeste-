from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.geos import Point
from .models.vehicle import FleetUnit

def get_nearest_available_units(lat, lon, required_equipment=None, limit=3):
    emergency_point = Point(lon, lat, srid=4326)

    query = FleetUnit.objects.filter(
        status=FleetUnit.UnitStatus.AVAILABLE
    )

    if required_equipment:
        equipment_filter = {f"capabilities__{required_equipment}": True}
        query = query.filter(**equipment_filter)

    return query.annotate(
        distance=Distance('current_location', emergency_point)
    ).order_by('distance')[:limit]