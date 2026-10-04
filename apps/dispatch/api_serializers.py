from rest_framework import serializers

from geo_core.serializers import CoordinatePointField
from fleet.api_serializers import FleetUnitSerializer
from fleet.models.vehicle import UnitType

from .models.history import MissionHistory
from .models.mission import Mission


class MissionSerializer(serializers.ModelSerializer):
    location = CoordinatePointField(read_only=True)
    assigned_unit = FleetUnitSerializer(read_only=True)

    class Meta:
        model = Mission
        fields = ('id', 'description', 'location', 'status', 'assigned_unit', 'created_at', 'updated_at')
        read_only_fields = fields


class MissionCreateSerializer(serializers.Serializer):
    description = serializers.CharField(trim_whitespace=True, allow_blank=False)
    location = CoordinatePointField()


class MissionHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = MissionHistory
        fields = ('id', 'status', 'notes', 'timestamp')
        read_only_fields = fields


class MissionFilterSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Mission.MissionStatus.choices, required=False)
    created_after = serializers.DateTimeField(required=False)
    created_before = serializers.DateTimeField(required=False)

    def validate(self, attrs):
        if (
            attrs.get('created_after')
            and attrs.get('created_before')
            and attrs['created_after'] > attrs['created_before']
        ):
            raise serializers.ValidationError('created_after deve ser anterior a created_before.')
        return attrs


class DispatchRequestSerializer(serializers.Serializer):
    description = serializers.CharField(trim_whitespace=True, allow_blank=False)
    location = CoordinatePointField()
    required_type = serializers.ChoiceField(choices=UnitType.choices, required=False)
    requirements = serializers.JSONField(required=False)

    def validate_requirements(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError('Requirements deve ser um objeto JSON.')
        return value


class DispatchResponseSerializer(serializers.Serializer):
    mission = MissionSerializer(read_only=True)
    dispatched_unit = FleetUnitSerializer(read_only=True)
    distance_meters = serializers.FloatField(read_only=True)
