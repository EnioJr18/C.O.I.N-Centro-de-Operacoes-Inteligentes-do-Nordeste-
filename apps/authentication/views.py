from django.contrib.auth import get_user_model
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.exceptions import APIException, NotFound, PermissionDenied, ValidationError
from rest_framework.generics import ListCreateAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .permissions import IsAdminRole, IsOperatorOrAdmin
from .selectors import get_user_or_404, get_users
from .serializers import (
    AdminUserRoleSerializer,
    AdminUserSerializer,
    AdminUserUpdateSerializer,
    CurrentUserSerializer,
    CurrentUserUpdateSerializer,
    EmailTokenObtainPairSerializer,
    OperationalUserCreateSerializer,
    PasswordChangeSerializer,
    UserListFilterSerializer,
)
from .services import (
    UserAdministrationConflictError,
    UserAdministrationForbiddenError,
    UserProfileMissingError,
    change_user_role,
    set_user_active,
    update_managed_user,
)


User = get_user_model()


class Conflict(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = 'conflict'


def _run_administration(operation):
    try:
        return operation()
    except UserAdministrationForbiddenError as error:
        raise PermissionDenied(str(error)) from error
    except UserAdministrationConflictError as error:
        raise Conflict(str(error)) from error
    except UserProfileMissingError as error:
        raise ValidationError({'detail': str(error)}) from error
    except User.DoesNotExist as error:
        raise NotFound('Usuário não encontrado.') from error


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
    def get(self, request):
        return Response(CurrentUserSerializer(request.user).data)

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


@extend_schema(tags=['user administration'])
class UserListView(ListCreateAPIView):
    permission_classes = [IsAdminRole]

    def get_queryset(self):
        serializer = UserListFilterSerializer(data={
            key: self.request.query_params.get(key)
            for key in self.request.query_params
        })
        serializer.is_valid(raise_exception=True)
        filters = dict(serializer.validated_data)
        filters.pop('page', None)
        return get_users(**filters)

    def get_serializer_class(self):
        return OperationalUserCreateSerializer if self.request.method == 'POST' else AdminUserSerializer

    @extend_schema(parameters=[UserListFilterSerializer], responses=AdminUserSerializer(many=True))
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        request=OperationalUserCreateSerializer,
        responses={201: AdminUserSerializer, 400: OpenApiResponse(description='Payload inválido.')},
    )
    def post(self, request, *args, **kwargs):
        serializer = OperationalUserCreateSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(AdminUserSerializer(user).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=['user administration'])
class UserDetailView(APIView):
    permission_classes = [IsAdminRole]

    @extend_schema(responses={200: AdminUserSerializer, 404: OpenApiResponse(description='Usuário não encontrado.')})
    def get(self, request, user_id):
        return Response(AdminUserSerializer(get_user_or_404(user_id)).data)

    @extend_schema(
        request=AdminUserUpdateSerializer,
        responses={
            200: AdminUserSerializer,
            400: OpenApiResponse(description='Payload inválido ou campo não permitido.'),
            403: OpenApiResponse(description='Autogerenciamento ou superusuário protegido.'),
            404: OpenApiResponse(description='Usuário não encontrado.'),
        },
    )
    def patch(self, request, user_id):
        serializer = AdminUserUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        user = _run_administration(lambda: update_managed_user(
            actor=request.user,
            target_id=user_id,
            values=serializer.validated_data,
            request_id=request.request_id,
        ))
        return Response(AdminUserSerializer(user).data)


@extend_schema(tags=['user administration'])
class UserRoleView(APIView):
    permission_classes = [IsAdminRole]

    @extend_schema(
        request=AdminUserRoleSerializer,
        responses={
            200: AdminUserSerializer,
            400: OpenApiResponse(description='Papel inválido ou perfil operacional ausente.'),
            403: OpenApiResponse(description='Autogerenciamento ou superusuário protegido.'),
            404: OpenApiResponse(description='Usuário não encontrado.'),
            409: OpenApiResponse(description='Proteção do último administrador ativo.'),
        },
    )
    def patch(self, request, user_id):
        serializer = AdminUserRoleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = _run_administration(lambda: change_user_role(
            actor=request.user,
            target_id=user_id,
            new_role=serializer.validated_data['role'],
            request_id=request.request_id,
        ))
        return Response(AdminUserSerializer(user).data)


class UserActiveBaseView(APIView):
    permission_classes = [IsAdminRole]
    is_active = None

    def post(self, request, user_id):
        user = _run_administration(lambda: set_user_active(
            actor=request.user,
            target_id=user_id,
            is_active=self.is_active,
            request_id=request.request_id,
        ))
        return Response(AdminUserSerializer(user).data)


@extend_schema(
    tags=['user administration'],
    request=None,
    responses={
        200: AdminUserSerializer,
        403: OpenApiResponse(description='Autogerenciamento ou superusuário protegido.'),
        404: OpenApiResponse(description='Usuário não encontrado.'),
    },
)
class UserActivateView(UserActiveBaseView):
    is_active = True


@extend_schema(
    tags=['user administration'],
    request=None,
    responses={
        200: AdminUserSerializer,
        403: OpenApiResponse(description='Autogerenciamento ou superusuário protegido.'),
        404: OpenApiResponse(description='Usuário não encontrado.'),
        409: OpenApiResponse(description='Proteção do último administrador ativo.'),
    },
)
class UserDeactivateView(UserActiveBaseView):
    is_active = False
