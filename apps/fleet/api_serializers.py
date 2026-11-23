import json
from collections.abc import Mapping

from rest_framework import serializers

from geo_core.serializers import CoordinatePointField

from .models.history import FleetUnitHistory
from .models.vehicle import FleetUnit, UnitType


MAX_CAPABILITIES_DEPTH = 5
MAX_CAPABILITIES_PROPERTIES = 100
MAX_CAPABILITIES_BYTES = 16 * 1024
MAX_CAPABILITY_KEY_LENGTH = 64


def validate_capabilities(value):
    if not isinstance(value, dict):
        raise serializers.ValidationError('Capacidades devem ser um objeto JSON.')

    properties = 0

    def visit(item, depth):
        nonlocal properties
        if depth > MAX_CAPABILITIES_DEPTH:
            raise serializers.ValidationError(
                f'Capacidades permitem no máximo {MAX_CAPABILITIES_DEPTH} níveis.'
            )
        if isinstance(item, dict):
            properties += len(item)
            if properties > MAX_CAPABILITIES_PROPERTIES:
                raise serializers.ValidationError(
                    f'Capacidades permitem no máximo {MAX_CAPABILITIES_PROPERTIES} propriedades.'
                )
            for key, child in item.items():
                if len(key) > MAX_CAPABILITY_KEY_LENGTH:
                    raise serializers.ValidationError(
                        f'Chaves de capacidades permitem no máximo {MAX_CAPABILITY_KEY_LENGTH} caracteres.'
                    )
                visit(child, depth + 1)
        elif isinstance(item, list):
            for child in item:
                visit(child, depth + 1)

    visit(value, 1)
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            separators=(',', ':'),
            allow_nan=False,
        ).encode('utf-8')
    except (TypeError, ValueError) as exc:
        raise serializers.ValidationError('Capacidades contêm JSON inválido.') from exc
    if len(encoded) > MAX_CAPABILITIES_BYTES:
        raise serializers.ValidationError('Capacidades excedem o limite de 16 KiB.')
    return value


class StrictSerializerMixin:
    def to_internal_value(self, data):
        if not isinstance(data, Mapping):
            raise serializers.ValidationError('O payload deve ser um objeto JSON.')
        unknown = set(data) - set(self.fields)
        if unknown:
            raise serializers.ValidationError({
                field: ['Campo não permitido.'] for field in sorted(unknown)
            })
        return super().to_internal_value(data)


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


class FleetUnitCreateSerializer(StrictSerializerMixin, serializers.Serializer):
    name = serializers.CharField(max_length=100, trim_whitespace=True, allow_blank=False)
    license_plate = serializers.CharField(max_length=20, trim_whitespace=True, allow_blank=False)
    unit_type = serializers.ChoiceField(choices=UnitType.choices)
    current_location = CoordinatePointField(required=False, allow_null=True)
    capabilities = serializers.JSONField(required=False, default=dict, validators=[validate_capabilities])

    def validate_license_plate(self, value):
        if FleetUnit.objects.filter(license_plate=value).exists():
            raise serializers.ValidationError('Já existe uma unidade com esta placa.')
        return value


class FleetUnitUpdateSerializer(StrictSerializerMixin, serializers.Serializer):
    name = serializers.CharField(max_length=100, trim_whitespace=True, allow_blank=False, required=False)
    license_plate = serializers.CharField(max_length=20, trim_whitespace=True, allow_blank=False, required=False)
    unit_type = serializers.ChoiceField(choices=UnitType.choices, required=False)
    current_location = CoordinatePointField(required=False, allow_null=True)
    capabilities = serializers.JSONField(required=False, validators=[validate_capabilities])

    def validate_license_plate(self, value):
        unit_id = self.context.get('unit_id')
        if FleetUnit.objects.filter(license_plate=value).exclude(pk=unit_id).exists():
            raise serializers.ValidationError('Já existe uma unidade com esta placa.')
        return value


class EmptyActionSerializer(StrictSerializerMixin, serializers.Serializer):
    pass


class FleetUnitHistoryActorSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    username = serializers.CharField(read_only=True)
    first_name = serializers.CharField(read_only=True)
    last_name = serializers.CharField(read_only=True)


class FleetUnitHistorySerializer(serializers.ModelSerializer):
    actor = FleetUnitHistoryActorSerializer(read_only=True)

    class Meta:
        model = FleetUnitHistory
        fields = (
            'id', 'action', 'previous_status', 'new_status', 'changed_fields',
            'request_id', 'created_at', 'actor',
        )
        read_only_fields = fields
