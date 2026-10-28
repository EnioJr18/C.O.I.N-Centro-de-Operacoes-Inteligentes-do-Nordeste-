from pathlib import Path

import environ


TEST_BASE_DIR = Path(__file__).resolve().parent.parent.parent
environ.Env.read_env(TEST_BASE_DIR / '.env', overwrite=False)

from .base import *  # noqa: E402,F403

DEBUG = False
ALLOWED_HOSTS = ['testserver', 'localhost', '127.0.0.1']
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels.layers.InMemoryChannelLayer',
    },
}
