import os

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
