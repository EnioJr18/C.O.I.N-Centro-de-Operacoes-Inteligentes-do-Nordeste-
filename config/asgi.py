import os

if not os.environ.get('DJANGO_SETTINGS_MODULE', '').strip():
    raise RuntimeError(
        'DJANGO_SETTINGS_MODULE deve ser definido explicitamente antes de iniciar o ASGI.'
    )

from django.core.asgi import get_asgi_application

django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import OriginValidator
from django.conf import settings
from apps.fleet.routing import websocket_urlpatterns
from authentication.websocket import JWTWebSocketMiddleware


async def websocket_application(scope, receive, send):
    application = OriginValidator(
        JWTWebSocketMiddleware(URLRouter(websocket_urlpatterns)),
        settings.WEBSOCKET_ALLOWED_ORIGINS,
    )
    return await application(scope, receive, send)

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": websocket_application,
})
