from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from authentication.permissions import IsOperatorOrAdmin
from fleet.models.vehicle import FleetUnit

from .api_serializers import (
    DispatchRequestSerializer,
    DispatchResponseSerializer,
    MissionCreateSerializer,
    MissionFilterSerializer,
    MissionHistorySerializer,
    MissionSerializer,
)
from .selectors import get_mission_history, get_missions
from .services import create_mission, dispatch_emergency


@extend_schema(tags=['missions'], parameters=[MissionFilterSerializer])
class MissionListAPIView(ListAPIView):
    permission_classes = [IsOperatorOrAdmin]
    serializer_class = MissionSerializer

    def get_queryset(self):
        filters = MissionFilterSerializer(data=self.request.query_params)
        filters.is_valid(raise_exception=True)
        return get_missions(**filters.validated_data)

    @extend_schema(request=MissionCreateSerializer, responses={201: MissionSerializer})
    def post(self, request):
        serializer = MissionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        point = serializer.validated_data['location']
        mission = create_mission(
            serializer.validated_data['description'], point.y, point.x
        )
        return Response(MissionSerializer(mission).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=['missions'])
class MissionDetailAPIView(RetrieveAPIView):
    permission_classes = [IsOperatorOrAdmin]
    serializer_class = MissionSerializer
    queryset = get_missions()


@extend_schema(tags=['missions'], responses=MissionHistorySerializer(many=True))
class MissionHistoryListAPIView(ListAPIView):
    permission_classes = [IsOperatorOrAdmin]
    serializer_class = MissionHistorySerializer

    def get_queryset(self):
        return get_mission_history(self.kwargs['pk'])


@extend_schema(
    tags=['dispatch'],
    request=DispatchRequestSerializer,
    responses={201: DispatchResponseSerializer},
    description='Cria e despacha uma missão usando o selector geoespacial e o serviço transacional.',
)
class DispatchEmergencyAPIView(APIView):
    permission_classes = [IsOperatorOrAdmin]

    def post(self, request):
        serializer = DispatchRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        point = serializer.validated_data['location']
        mission, distance_meters = dispatch_emergency(
            description=serializer.validated_data['description'],
            latitude=point.y,
            longitude=point.x,
            required_type=serializer.validated_data.get('required_type'),
            requirements=serializer.validated_data.get('requirements'),
        )

        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            'fleet_updates',
            {
                'type': 'send_fleet_update',
                'message': {
                    'action': 'DISPATCH',
                    'unit_id': mission.assigned_unit_id,
                    'unit_name': mission.assigned_unit.name,
                    'new_status': FleetUnit.UnitStatus.BUSY,
                    'mission_id': mission.id,
                    'lat': point.y,
                    'lon': point.x,
                },
            },
        )
        payload = {
            'mission': mission,
            'dispatched_unit': mission.assigned_unit,
            'distance_meters': round(distance_meters, 2),
        }
        return Response(DispatchResponseSerializer(payload).data, status=status.HTTP_201_CREATED)
