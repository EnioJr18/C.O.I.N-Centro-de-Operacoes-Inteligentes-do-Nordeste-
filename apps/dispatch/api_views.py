from drf_spectacular.utils import OpenApiResponse, extend_schema
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from authentication.permissions import IsOperatorOrAdmin
from fleet.events import build_dispatch_event, publish_fleet_event

from .api_serializers import (
    DispatchRequestSerializer,
    DispatchResponseSerializer,
    CancelMissionSerializer,
    CompleteMissionSerializer,
    MissionCreateSerializer,
    MissionFilterSerializer,
    MissionHistorySerializer,
    MissionSerializer,
)
from .selectors import get_mission_history, get_missions
from .models.mission import Mission
from .services import cancel_mission, complete_mission, create_mission, dispatch_emergency


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
            serializer.validated_data['description'], point.y, point.x,
            actor=request.user,
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
    tags=['missions'],
    request=CompleteMissionSerializer,
    responses={
        200: MissionSerializer,
        400: OpenApiResponse(description='Payload inválido.'),
        401: OpenApiResponse(description='Autenticação ausente, inválida ou expirada.'),
        403: OpenApiResponse(description='Usuário sem papel operacional.'),
        404: OpenApiResponse(description='Missão não encontrada.'),
        409: OpenApiResponse(description='Estado ou vínculo operacional inconsistente.'),
    },
    description='Conclui de forma idempotente uma missão em andamento.',
)
class CompleteMissionAPIView(APIView):
    permission_classes = [IsOperatorOrAdmin]

    def post(self, request, pk):
        serializer = CompleteMissionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        mission = get_object_or_404(Mission.objects.only('pk'), pk=pk)
        mission = complete_mission(mission, actor=request.user)
        return Response(MissionSerializer(mission).data)


@extend_schema(
    tags=['missions'],
    request=CancelMissionSerializer,
    responses={
        200: MissionSerializer,
        400: OpenApiResponse(description='Payload inválido.'),
        401: OpenApiResponse(description='Autenticação ausente, inválida ou expirada.'),
        403: OpenApiResponse(description='Usuário sem papel operacional.'),
        404: OpenApiResponse(description='Missão não encontrada.'),
        409: OpenApiResponse(description='Estado ou vínculo operacional inconsistente.'),
    },
    description='Cancela de forma idempotente uma missão pendente ou em andamento.',
)
class CancelMissionAPIView(APIView):
    permission_classes = [IsOperatorOrAdmin]

    def post(self, request, pk):
        serializer = CancelMissionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        mission = get_object_or_404(Mission.objects.only('pk'), pk=pk)
        mission = cancel_mission(
            mission,
            actor=request.user,
            reason=serializer.validated_data.get('reason'),
        )
        return Response(MissionSerializer(mission).data)


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
            actor=request.user,
        )

        event = build_dispatch_event(mission, point)
        transaction.on_commit(lambda: publish_fleet_event(event))
        payload = {
            'mission': mission,
            'dispatched_unit': mission.assigned_unit,
            'distance_meters': round(distance_meters, 2),
        }
        return Response(DispatchResponseSerializer(payload).data, status=status.HTTP_201_CREATED)
