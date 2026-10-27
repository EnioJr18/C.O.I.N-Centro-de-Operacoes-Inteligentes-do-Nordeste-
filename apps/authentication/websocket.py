from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import AccessToken

from .models import UserRole
from .permissions import user_role


PROTOCOL = 'coin.v1'
TOKEN_PREFIX = 'coin.jwt.'


@database_sync_to_async
def authenticate_websocket(raw_token):
    try:
        token = AccessToken(raw_token)
        user = JWTAuthentication().get_user(token)
    except (TokenError, InvalidToken, AuthenticationFailed):
        return None
    if not user.is_active:
        return None
    return user.pk, token['exp']


@database_sync_to_async
def has_operational_access(user_id):
    user = get_user_model().objects.filter(pk=user_id).first()
    return bool(
        user and user.is_active
        and user_role(user) in (UserRole.ADMIN, UserRole.OPERADOR)
    )


class JWTWebSocketMiddleware:
    def __init__(self, application):
        self.application = application

    async def __call__(self, scope, receive, send):
        protocols = scope.get('subprotocols', [])
        identity = None
        if (len(protocols) == 2 and protocols[0] == PROTOCOL
                and protocols[1].startswith(TOKEN_PREFIX)):
            raw_token = protocols[1][len(TOKEN_PREFIX):]
            if raw_token and len(raw_token) <= 8192:
                identity = await authenticate_websocket(raw_token)
            raw_token = None
        scope = dict(scope)
        scope['headers'] = [
            (name, value) for name, value in scope.get('headers', [])
            if name.lower() != b'sec-websocket-protocol'
        ]
        scope['subprotocols'] = [PROTOCOL] if identity else []
        scope['coin_identity'] = identity
        protocols = None
        return await self.application(scope, receive, send)
