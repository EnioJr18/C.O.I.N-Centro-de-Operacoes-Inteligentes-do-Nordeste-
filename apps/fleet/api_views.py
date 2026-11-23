from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView

from authentication.permissions import IsAdminRole, IsOperatorOrAdmin

from .api_serializers import (
    EmptyActionSerializer,
    FleetUnitCreateSerializer,
    FleetUnitFilterSerializer,
    FleetUnitHistorySerializer,
    FleetUnitSerializer,
    FleetUnitUpdateSerializer,
)
from .models.vehicle import FleetUnit
from .selectors import get_fleet_unit_history, get_fleet_units
from .services import (
    create_fleet_unit,
    end_unit_maintenance,
    start_unit_maintenance,
    update_fleet_unit,
)


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

    def get_permissions(self):
        classes = [IsAdminRole] if self.request.method == 'POST' else [IsOperatorOrAdmin]
        return [permission() for permission in classes]

    @extend_schema(
        request=FleetUnitCreateSerializer,
        responses={
            201: FleetUnitSerializer,
            400: OpenApiResponse(description='Payload ou dados inválidos.'),
            401: OpenApiResponse(description='Autenticação inválida ou ausente.'),
            403: OpenApiResponse(description='Operação exclusiva de administrador.'),
        },
        description=(
            'Cadastra uma unidade disponível e registra sua auditoria. '
            'Placas duplicadas, inclusive em concorrência, retornam 400.'
        ),
    )
    def post(self, request):
        serializer = FleetUnitCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        unit = create_fleet_unit(
            actor=request.user,
            request_id=request.request_id,
            **serializer.validated_data,
        )
        return Response(FleetUnitSerializer(unit).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=['fleet'], description='Obtém uma viatura pelo identificador.')
class FleetUnitDetailAPIView(RetrieveAPIView):
    permission_classes = [IsOperatorOrAdmin]
    serializer_class = FleetUnitSerializer
    queryset = get_fleet_units()

    def get_permissions(self):
        classes = [IsAdminRole] if self.request.method == 'PATCH' else [IsOperatorOrAdmin]
        return [permission() for permission in classes]

    @extend_schema(
        request=FleetUnitUpdateSerializer,
        responses={
            200: FleetUnitSerializer,
            400: OpenApiResponse(description='Payload ou dados inválidos.'),
            401: OpenApiResponse(description='Autenticação inválida ou ausente.'),
            403: OpenApiResponse(description='Operação exclusiva de administrador.'),
            404: OpenApiResponse(description='Unidade não encontrada.'),
            409: OpenApiResponse(description='Estado ou vínculo operacional incompatível.'),
        },
        description='Atualiza campos administrativos permitidos de uma unidade.',
    )
    def patch(self, request, pk):
        get_object_or_404(FleetUnit.objects.only('pk'), pk=pk)
        serializer = FleetUnitUpdateSerializer(
            data=request.data,
            partial=True,
            context={'unit_id': pk},
        )
        serializer.is_valid(raise_exception=True)
        unit = update_fleet_unit(
            unit_id=pk,
            actor=request.user,
            request_id=request.request_id,
            values=serializer.validated_data,
        )
        return Response(FleetUnitSerializer(unit).data)


@extend_schema(
    tags=['fleet'],
    request=EmptyActionSerializer,
    responses={
        200: FleetUnitSerializer,
        400: OpenApiResponse(description='Payload inválido.'),
        401: OpenApiResponse(description='Autenticação inválida ou ausente.'),
        403: OpenApiResponse(description='Operação exclusiva de administrador.'),
        404: OpenApiResponse(description='Unidade não encontrada.'),
        409: OpenApiResponse(description='Estado ou vínculo operacional incompatível.'),
    },
    description='Inicia ou encerra manutenção de forma idempotente.',
)
class FleetUnitMaintenanceAPIView(APIView):
    permission_classes = [IsAdminRole]

    def _validate(self, request, pk):
        get_object_or_404(FleetUnit.objects.only('pk'), pk=pk)
        serializer = EmptyActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

    def post(self, request, pk):
        self._validate(request, pk)
        unit = start_unit_maintenance(
            unit_id=pk,
            actor=request.user,
            request_id=request.request_id,
        )
        return Response(FleetUnitSerializer(unit).data)

    def delete(self, request, pk):
        self._validate(request, pk)
        unit = end_unit_maintenance(
            unit_id=pk,
            actor=request.user,
            request_id=request.request_id,
        )
        return Response(FleetUnitSerializer(unit).data)


@extend_schema(
    tags=['fleet'],
    responses={
        200: FleetUnitHistorySerializer(many=True),
        401: OpenApiResponse(description='Autenticação inválida ou ausente.'),
        403: OpenApiResponse(description='Operação exclusiva de administrador.'),
        404: OpenApiResponse(description='Unidade não encontrada.'),
    },
    description='Lista o histórico administrativo paginado de uma unidade.',
)
class FleetUnitHistoryListAPIView(ListAPIView):
    permission_classes = [IsAdminRole]
    serializer_class = FleetUnitHistorySerializer

    def get_queryset(self):
        get_object_or_404(FleetUnit.objects.only('pk'), pk=self.kwargs['pk'])
        return get_fleet_unit_history(self.kwargs['pk'])
