from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from authentication.permissions import IsOperatorOrAdmin

from .api_serializers import DashboardSummarySerializer
from .selectors import get_dashboard_summary


@extend_schema(
    tags=['dashboard'],
    responses={
        200: DashboardSummarySerializer,
        401: OpenApiResponse(description='Autenticação ausente, inválida ou expirada.'),
        403: OpenApiResponse(description='Usuário sem papel operacional.'),
    },
    description=(
        'Resumo operacional somente leitura para usuários ativos ADMIN, OPERADOR e '
        'superusuários. A disponibilidade representa unidades com status AVAILABLE '
        'sobre o total cadastrado; generated_at indica quando a resposta foi gerada.'
    ),
)
class DashboardSummaryAPIView(APIView):
    permission_classes = [IsOperatorOrAdmin]

    def get(self, request):
        summary = get_dashboard_summary()
        return Response(DashboardSummarySerializer(summary).data)
