import os
from urllib.parse import urlsplit

from django.core.exceptions import ImproperlyConfigured


def required_environment(name):
    value = os.environ.get(name, '').strip()
    if not value:
        raise ImproperlyConfigured(f'{name} é obrigatório em produção.')
    return value


PRODUCTION_SECRET_KEY = required_environment('SECRET_KEY')
required_environment('DATABASE_URL')
PRODUCTION_REDIS_URL = required_environment('REDIS_URL')
PRODUCTION_CHANNEL_PREFIX = required_environment('CHANNEL_LAYER_PREFIX')
required_environment('ALLOWED_HOSTS')
required_environment('WEBSOCKET_ALLOWED_ORIGINS')

if PRODUCTION_SECRET_KEY in {'change-me', 'sua-chave-secreta', 'ci-only-secret-key'}:
    raise ImproperlyConfigured('SECRET_KEY de produção não pode usar um placeholder conhecido.')
if len(PRODUCTION_SECRET_KEY) < 50 or len(set(PRODUCTION_SECRET_KEY)) < 5:
    raise ImproperlyConfigured('SECRET_KEY de produção não atende aos requisitos mínimos de segurança.')

from .base import *  # noqa: E402,F403
from .channel_layers import (  # noqa: E402
    redis_channel_layer,
    validate_channel_layer_prefix,
)

DEBUG = env.bool('DEBUG', default=False)
if DEBUG:
    raise ImproperlyConfigured('DEBUG deve permanecer desativado em produção.')

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

SECURE_SSL_REDIRECT = env.bool('SECURE_SSL_REDIRECT', default=False)
SECURE_HSTS_SECONDS = env.int('SECURE_HSTS_SECONDS', default=0)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool(
    'SECURE_HSTS_INCLUDE_SUBDOMAINS', default=False
)
SECURE_HSTS_PRELOAD = env.bool('SECURE_HSTS_PRELOAD', default=False)
if SECURE_HSTS_SECONDS < 0:
    raise ImproperlyConfigured('SECURE_HSTS_SECONDS não pode ser negativo.')
if SECURE_HSTS_PRELOAD and (
    SECURE_HSTS_SECONDS == 0 or not SECURE_HSTS_INCLUDE_SUBDOMAINS
):
    raise ImproperlyConfigured(
        'HSTS preload exige HSTS ativo e inclusão explícita de subdomínios.'
    )

TRUST_X_FORWARDED_PROTO = env.bool('TRUST_X_FORWARDED_PROTO', default=False)
if TRUST_X_FORWARDED_PROTO:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

CSRF_TRUSTED_ORIGINS = env.list('CSRF_TRUSTED_ORIGINS', default=[])
for origin in CSRF_TRUSTED_ORIGINS:
    parsed = urlsplit(origin)
    if (
        parsed.scheme != 'https'
        or not parsed.hostname
        or '*' in origin
        or parsed.username
        or parsed.password
        or parsed.path
        or parsed.query
        or parsed.fragment
    ):
        raise ImproperlyConfigured(
            'CSRF_TRUSTED_ORIGINS deve conter apenas origens HTTPS explícitas.'
        )

OPENAPI_ENABLED = env.bool('OPENAPI_ENABLED', default=False)

DATABASE_CONNECT_TIMEOUT = env.int('DATABASE_CONNECT_TIMEOUT', default=5)
if not 1 <= DATABASE_CONNECT_TIMEOUT <= 60:
    raise ImproperlyConfigured('DATABASE_CONNECT_TIMEOUT deve estar entre 1 e 60 segundos.')
DATABASES['default'].setdefault('OPTIONS', {})
DATABASES['default']['OPTIONS'].setdefault('connect_timeout', DATABASE_CONNECT_TIMEOUT)
DATABASES['default']['CONN_HEALTH_CHECKS'] = True

ALLOWED_HOSTS = env.list('ALLOWED_HOSTS')
if not ALLOWED_HOSTS or any(
    not host.strip()
    or host == '*'
    or host.startswith('.')
    or '://' in host
    or '/' in host
    or any(character.isspace() for character in host)
    for host in ALLOWED_HOSTS
):
    raise ImproperlyConfigured('ALLOWED_HOSTS deve conter apenas hosts explícitos em produção.')

if not WEBSOCKET_ALLOWED_ORIGINS or any(
    not origin.startswith('https://') for origin in WEBSOCKET_ALLOWED_ORIGINS
):
    raise ImproperlyConfigured(
        'WEBSOCKET_ALLOWED_ORIGINS deve conter ao menos uma origem HTTPS explícita em produção.'
    )

CHANNEL_LAYER_PREFIX = validate_channel_layer_prefix(
    PRODUCTION_CHANNEL_PREFIX,
    required=True,
)
CHANNEL_LAYERS = redis_channel_layer(PRODUCTION_REDIS_URL, CHANNEL_LAYER_PREFIX)

LOGGING['formatters']['structured'] = {'()': 'common.logging.JSONFormatter'}
LOGGING['handlers']['console']['formatter'] = 'structured'
