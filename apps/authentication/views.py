from django.contrib.auth import get_user_model
from rest_framework.generics import ListCreateAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from drf_spectacular.utils import OpenApiResponse, extend_schema
from .permissions import IsAdminRole, IsOperatorOrAdmin
from .serializers import (
    CurrentUserSerializer,
    CurrentUserUpdateSerializer,
    EmailTokenObtainPairSerializer,
    OperationalUserCreateSerializer,
    PasswordChangeSerializer,
)

class LoginView(TokenObtainPairView):
    permission_classes = [AllowAny]
    serializer_class = EmailTokenObtainPairSerializer
class RefreshView(TokenRefreshView):
    permission_classes = [AllowAny]
class MeView(APIView):
    serializer_class = CurrentUserSerializer
    def get_permissions(self):
        permission_classes = [IsOperatorOrAdmin] if self.request.method == 'PATCH' else [IsAuthenticated]
        return [permission() for permission in permission_classes]
    @extend_schema(responses=CurrentUserSerializer, tags=['authentication'], description='Retorna o usuário autenticado.')
    def get(self, request): return Response(CurrentUserSerializer(request.user).data)
    @extend_schema(
        request=CurrentUserUpdateSerializer,
        responses={
            200: CurrentUserSerializer,
            400: OpenApiResponse(description='Payload inválido ou campo não permitido.'),
            401: OpenApiResponse(description='Autenticação ausente, inválida ou usuário inativo.'),
            403: OpenApiResponse(description='Usuário sem papel operacional.'),
        },
        tags=['authentication'],
        description='Atualiza somente nome e sobrenome do próprio usuário operacional.',
    )
    def patch(self, request):
        serializer = CurrentUserUpdateSerializer(request.user, data=request.data, partial=True, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(CurrentUserSerializer(user).data)


class PasswordChangeView(APIView):
    permission_classes = [IsOperatorOrAdmin]
    serializer_class = PasswordChangeSerializer

    @extend_schema(
        request=PasswordChangeSerializer,
        responses={
            204: OpenApiResponse(description='Senha alterada. A sessão deve ser encerrada.'),
            400: OpenApiResponse(description='Senha atual ou nova senha inválida.'),
            401: OpenApiResponse(description='Autenticação ausente, inválida ou usuário inativo.'),
            403: OpenApiResponse(description='Usuário sem papel operacional.'),
        },
        tags=['authentication'],
        description='Altera a senha do próprio usuário após validar a senha atual.',
    )
    def post(self, request):
        serializer = PasswordChangeSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(status=status.HTTP_204_NO_CONTENT)

class UserListView(ListCreateAPIView):
    permission_classes = [IsAdminRole]
    queryset = get_user_model().objects.order_by('id')
    def get_serializer_class(self):
        return OperationalUserCreateSerializer if self.request.method == 'POST' else CurrentUserSerializer
