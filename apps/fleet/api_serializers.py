from rest_framework import serializers

from geo_core.serializers import CoordinatePointField

from .models.vehicle import FleetUnit


class FleetUnitSerializer(serializers.ModelSerializer):
    current_location = CoordinatePointField(allow_null=True, required=False)

    class Meta:
        model = FleetUnit
        fields = (
            'id',
            'name',
            'license_plate',
            'unit_type',
            'current_location',
            'status',
            'capabilities',
            'created_at',
            'updated_at',
        )
        read_only_fields = fields


class FleetUnitFilterSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=FleetUnit.UnitStatus.choices, required=False)
    unit_type = serializers.ChoiceField(choices=FleetUnit._meta.get_field('unit_type').choices, required=False)
