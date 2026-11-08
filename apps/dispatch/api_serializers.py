from rest_framework import serializers

from geo_core.serializers import CoordinatePointField
from fleet.api_serializers import FleetUnitSerializer
from fleet.models.vehicle import UnitType

from .models.history import MissionHistory
from .models.mission import Mission


MAX_CANCELLATION_REASON_LENGTH = 1000


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


class MissionHistoryActorSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    username = serializers.CharField(read_only=True)
    first_name = serializers.CharField(read_only=True)
    last_name = serializers.CharField(read_only=True)


class MissionHistorySerializer(serializers.ModelSerializer):
    actor = MissionHistoryActorSerializer(read_only=True, allow_null=True)

    class Meta:
        model = MissionHistory
        fields = ('id', 'status', 'notes', 'timestamp', 'actor')
        read_only_fields = fields


class StrictActionSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        if not isinstance(data, dict):
            raise serializers.ValidationError('O payload deve ser um objeto JSON.')
        unknown = set(data) - set(self.fields)
        if unknown:
            raise serializers.ValidationError({
                field: ['Campo não permitido.'] for field in sorted(unknown)
            })
        return super().to_internal_value(data)


class CompleteMissionSerializer(StrictActionSerializer):
    pass


class CancelMissionSerializer(StrictActionSerializer):
    reason = serializers.CharField(
        required=False,
        allow_blank=True,
        trim_whitespace=True,
        max_length=MAX_CANCELLATION_REASON_LENGTH,
    )


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
