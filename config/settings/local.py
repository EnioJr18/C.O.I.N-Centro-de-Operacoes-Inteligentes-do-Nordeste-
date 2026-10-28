import os
from pathlib import Path

import environ


LOCAL_BASE_DIR = Path(__file__).resolve().parent.parent.parent
environ.Env.read_env(LOCAL_BASE_DIR / '.env', overwrite=False)

from .base import *  # noqa: E402,F403
from .channel_layers import (  # noqa: E402
    redis_channel_layer,
    validate_channel_layer_prefix,
)

DEBUG = True

ALLOWED_HOSTS = ['localhost', '127.0.0.1', '*']

REDIS_URL = os.environ.get('REDIS_URL', '').strip()
if REDIS_URL:
    CHANNEL_LAYER_PREFIX = validate_channel_layer_prefix(
        os.environ.get('CHANNEL_LAYER_PREFIX'),
        default='coin-local',
    )
    CHANNEL_LAYERS = redis_channel_layer(REDIS_URL, CHANNEL_LAYER_PREFIX)
