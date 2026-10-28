import re
from urllib.parse import urlsplit

from django.core.exceptions import ImproperlyConfigured


_PREFIX_PATTERN = re.compile(r'^[A-Za-z0-9_.:-]+$')


def validate_redis_url(value):
    value = (value or '').strip()
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as exc:
        raise ImproperlyConfigured('REDIS_URL possui formato inválido.') from exc

    if (
        not value
        or any(character.isspace() for character in value)
        or parsed.scheme not in ('redis', 'rediss')
        or not parsed.hostname
        or parsed.fragment
        or (port is not None and not 1 <= port <= 65535)
    ):
        raise ImproperlyConfigured('REDIS_URL possui formato inválido.')

    if parsed.path not in ('', '/'):
        database = parsed.path.removeprefix('/')
        if not database.isdigit():
            raise ImproperlyConfigured('REDIS_URL possui formato inválido.')

    return value


def validate_channel_layer_prefix(value, *, required=False, default=None):
    value = (value or '').strip()
    if not value and not required:
        value = default or ''
    if not value or not _PREFIX_PATTERN.fullmatch(value):
        raise ImproperlyConfigured(
            'CHANNEL_LAYER_PREFIX deve ser explícito e conter apenas letras, números, ponto, dois-pontos, hífen ou sublinhado.'
        )
    return value


def redis_channel_layer(redis_url, prefix):
    return {
        'default': {
            'BACKEND': 'channels_redis.core.RedisChannelLayer',
            'CONFIG': {
                'hosts': [validate_redis_url(redis_url)],
                'prefix': prefix,
            },
        },
    }
