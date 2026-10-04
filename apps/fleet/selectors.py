from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.geos import Point
from .models.vehicle import FleetUnit


def get_fleet_units(status: str | None = None, unit_type: str | None = None):
    queryset = FleetUnit.objects.all()
    if status:
        queryset = queryset.filter(status=status)
    if unit_type:
        queryset = queryset.filter(unit_type=unit_type)
    return queryset


def get_nearest_available_units(
    lat: float,
    lon: float,
    required_type: str | None = None,
    requirements: dict | None = None,
    limit: int = 3,
) -> list[FleetUnit]:
    emergency_point = Point(lon, lat, srid=4326)

    queryset = FleetUnit.objects.filter(
        status=FleetUnit.UnitStatus.AVAILABLE,
        current_location__isnull=False,
    )

    if required_type:
        queryset = queryset.filter(unit_type=required_type)

    if requirements:
        queryset = queryset.filter(capabilities__contains=requirements)

    return (
        queryset
        .annotate(distance=Distance("current_location", emergency_point))
        .order_by("distance")[:limit]
    )
