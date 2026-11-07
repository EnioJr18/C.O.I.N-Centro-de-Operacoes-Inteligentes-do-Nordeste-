from django.contrib import admin
from django.conf import settings
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from rest_framework.permissions import AllowAny
from fleet.legacy_views import LegacyDispatchEmergencyAPIView
from common.health import live, ready, realtime

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/auth/', include('authentication.urls')),
    path('api/v1/', include('fleet.urls')),
    path('api/v1/', include('dispatch.urls')),
    path('api/v1/', include('dashboard.urls')),
    path('fleet/api/v1/emergencies/dispatch/', LegacyDispatchEmergencyAPIView.as_view(), name='legacy-dispatch-emergency'),
    path('health/live/', live, name='health-live'),
    path('health/ready/', ready, name='health-ready'),
    path('health/realtime/', realtime, name='health-realtime'),
]

if settings.OPENAPI_ENABLED:
    urlpatterns += [
        path('api/schema/', SpectacularAPIView.as_view(permission_classes=[AllowAny]), name='schema'),
        path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema', permission_classes=[AllowAny]), name='swagger-ui'),
        path('api/redoc/', SpectacularRedocView.as_view(url_name='schema', permission_classes=[AllowAny]), name='redoc'),
    ]
