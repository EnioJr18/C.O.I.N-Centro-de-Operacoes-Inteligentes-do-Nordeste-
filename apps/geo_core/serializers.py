from django.contrib.gis.geos import Point
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers


@extend_schema_field(
    {
        'type': 'object',
        'required': ['latitude', 'longitude'],
        'properties': {
            'latitude': {'type': 'number', 'format': 'double', 'minimum': -90, 'maximum': 90},
            'longitude': {'type': 'number', 'format': 'double', 'minimum': -180, 'maximum': 180},
        },
    }
)
class CoordinatePointField(serializers.Field):
    """Serializes WGS84 points as latitude/longitude objects."""

    default_error_messages = {
        'invalid': 'Informe latitude e longitude numéricas.',
        'latitude_range': 'Latitude deve estar entre -90 e 90.',
        'longitude_range': 'Longitude deve estar entre -180 e 180.',
    }

    def to_representation(self, value):
        if value is None:
            return None
        return {'latitude': value.y, 'longitude': value.x}

    def to_internal_value(self, data):
        if not isinstance(data, dict):
            self.fail('invalid')
        latitude = data.get('latitude')
        longitude = data.get('longitude')
        if (
            isinstance(latitude, bool)
            or isinstance(longitude, bool)
            or not isinstance(latitude, (int, float))
            or not isinstance(longitude, (int, float))
        ):
            self.fail('invalid')
        if not -90 <= latitude <= 90:
            self.fail('latitude_range')
        if not -180 <= longitude <= 180:
            self.fail('longitude_range')
        return Point(longitude, latitude, srid=4326)
