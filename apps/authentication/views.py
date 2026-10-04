from django.contrib.auth import get_user_model
from rest_framework.generics import ListCreateAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .permissions import IsAdminRole
from .serializers import CurrentUserSerializer, EmailTokenObtainPairSerializer, OperationalUserCreateSerializer

class LoginView(TokenObtainPairView):
    permission_classes = [AllowAny]
    serializer_class = EmailTokenObtainPairSerializer
class RefreshView(TokenRefreshView):
    permission_classes = [AllowAny]
class MeView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = CurrentUserSerializer
    def get(self, request): return Response(CurrentUserSerializer(request.user).data)
class UserListView(ListCreateAPIView):
    permission_classes = [IsAdminRole]
    queryset = get_user_model().objects.order_by('id')
    def get_serializer_class(self):
        return OperationalUserCreateSerializer if self.request.method == 'POST' else CurrentUserSerializer
