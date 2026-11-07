from rest_framework import serializers


class DashboardAssignedUnitSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(read_only=True)


class DashboardRecentMissionSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    description = serializers.CharField(read_only=True)
    status = serializers.CharField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    assigned_unit = DashboardAssignedUnitSerializer(read_only=True, allow_null=True)


class DashboardFleetSummarySerializer(serializers.Serializer):
    total = serializers.IntegerField(read_only=True)
    available = serializers.IntegerField(read_only=True)
    availability_percentage = serializers.FloatField(read_only=True)
    with_location = serializers.IntegerField(read_only=True)
    without_location = serializers.IntegerField(read_only=True)
    by_status = serializers.DictField(
        child=serializers.IntegerField(read_only=True),
        read_only=True,
        help_text='Contagens para AVAILABLE, BUSY e MAINTENANCE.',
    )


class DashboardMissionSummarySerializer(serializers.Serializer):
    total = serializers.IntegerField(read_only=True)
    by_status = serializers.DictField(
        child=serializers.IntegerField(read_only=True),
        read_only=True,
        help_text='Contagens para Pendente, Em Andamento, Concluída e Cancelada.',
    )
    recent = DashboardRecentMissionSerializer(many=True, read_only=True)


class DashboardSummarySerializer(serializers.Serializer):
    generated_at = serializers.DateTimeField(read_only=True)
    fleet = DashboardFleetSummarySerializer(read_only=True)
    missions = DashboardMissionSummarySerializer(read_only=True)
