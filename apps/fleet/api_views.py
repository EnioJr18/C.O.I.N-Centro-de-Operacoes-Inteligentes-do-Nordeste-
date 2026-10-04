from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.generics import ListAPIView, RetrieveAPIView

from authentication.permissions import IsOperatorOrAdmin

from .api_serializers import FleetUnitFilterSerializer, FleetUnitSerializer
from .selectors import get_fleet_units


@extend_schema(
    tags=['fleet'],
    parameters=[FleetUnitFilterSerializer],
    description='Lista viaturas, com filtros opcionais de status e tipo.',
)
class FleetUnitListAPIView(ListAPIView):
    permission_classes = [IsOperatorOrAdmin]
    serializer_class = FleetUnitSerializer

    def get_queryset(self):
        filters = FleetUnitFilterSerializer(data=self.request.query_params)
        filters.is_valid(raise_exception=True)
        return get_fleet_units(**filters.validated_data)


@extend_schema(tags=['fleet'], description='Obtém uma viatura pelo identificador.')
class FleetUnitDetailAPIView(RetrieveAPIView):
    permission_classes = [IsOperatorOrAdmin]
    serializer_class = FleetUnitSerializer
    queryset = get_fleet_units()
