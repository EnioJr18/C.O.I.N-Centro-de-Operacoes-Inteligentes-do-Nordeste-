import os
import subprocess
import sys
from pathlib import Path
from unittest import TestCase


BASE_DIR = Path(__file__).resolve().parent.parent
SETTINGS_SCRIPT = (
    "import importlib, os; "
    "module = importlib.import_module(os.environ['COIN_SETTINGS_UNDER_TEST']); "
    "print(module.CHANNEL_LAYERS['default']['BACKEND'])"
)
PRODUCTION_ENV = {
    'SECRET_KEY': 'test-only-production-key-with-more-than-fifty-characters-ABC123xyz',
    'DATABASE_URL': 'postgresql://test:test@127.0.0.1:5432/coin_test',
    'REDIS_URL': 'rediss://redis.example.test:6380/0',
    'CHANNEL_LAYER_PREFIX': 'coin-test-production',
    'ALLOWED_HOSTS': 'api.example.test',
    'WEBSOCKET_ALLOWED_ORIGINS': 'https://app.example.test',
    'DEBUG': 'False',
}


class SettingsSelectionTests(TestCase):
    def run_settings(self, module, *, values=None, remove=()):
        environment = os.environ.copy()
        environment['COIN_SETTINGS_UNDER_TEST'] = module
        if values:
            environment.update(values)
        for name in remove:
            environment.pop(name, None)
        return subprocess.run(
            [sys.executable, '-c', SETTINGS_SCRIPT],
            cwd=BASE_DIR,
            env=environment,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )

    def test_local_uses_memory_without_redis_and_redis_when_explicit(self):
        common = {
            'SECRET_KEY': 'local-test-key',
            'DATABASE_URL': 'postgresql://test:test@127.0.0.1:5432/coin_test',
            'REDIS_URL': '',
        }
        memory = self.run_settings('config.settings.local', values=common)
        self.assertEqual(memory.returncode, 0, memory.stderr)
        self.assertEqual(memory.stdout.strip(), 'channels.layers.InMemoryChannelLayer')

        redis = self.run_settings(
            'config.settings.local',
            values={
                **common,
                'REDIS_URL': 'redis://127.0.0.1:6379/0',
                'CHANNEL_LAYER_PREFIX': 'coin-local-test',
            },
        )
        self.assertEqual(redis.returncode, 0, redis.stderr)
        self.assertEqual(redis.stdout.strip(), 'channels_redis.core.RedisChannelLayer')

    def test_local_rejects_invalid_redis_url_without_exposing_it(self):
        marker = 'credential-must-not-appear'
        result = self.run_settings(
            'config.settings.local',
            values={
                'SECRET_KEY': 'local-test-key',
                'DATABASE_URL': 'postgresql://test:test@127.0.0.1:5432/coin_test',
                'REDIS_URL': f'http://user:{marker}@invalid.example/0',
                'CHANNEL_LAYER_PREFIX': 'coin-local-test',
            },
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('REDIS_URL possui formato inválido.', result.stderr)
        self.assertNotIn(marker, result.stdout + result.stderr)

    def test_test_settings_always_use_memory_even_with_redis_url(self):
        result = self.run_settings(
            'config.settings.test',
            values={
                'SECRET_KEY': 'test-settings-key',
                'DATABASE_URL': 'postgresql://test:test@127.0.0.1:5432/coin_test',
                'REDIS_URL': 'redis://127.0.0.1:6379/0',
                'CHANNEL_LAYER_PREFIX': 'ignored-test-prefix',
            },
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), 'channels.layers.InMemoryChannelLayer')

    def test_production_requires_every_setting_and_does_not_load_dotenv(self):
        required = (
            'SECRET_KEY',
            'DATABASE_URL',
            'REDIS_URL',
            'CHANNEL_LAYER_PREFIX',
            'ALLOWED_HOSTS',
            'WEBSOCKET_ALLOWED_ORIGINS',
        )
        for name in required:
            with self.subTest(name=name):
                result = self.run_settings(
                    'config.settings.production',
                    values=PRODUCTION_ENV,
                    remove=(name,),
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(f'{name} é obrigatório em produção.', result.stderr)

    def test_production_rejects_unsafe_values_without_leaking_redis_url(self):
        cases = (
            ({'DEBUG': 'True'}, 'DEBUG deve permanecer desativado'),
            ({'ALLOWED_HOSTS': '*'}, 'ALLOWED_HOSTS deve conter apenas hosts explícitos'),
            (
                {'WEBSOCKET_ALLOWED_ORIGINS': 'http://app.example.test'},
                'WEBSOCKET_ALLOWED_ORIGINS deve conter ao menos uma origem HTTPS',
            ),
            ({'CHANNEL_LAYER_PREFIX': 'bad prefix'}, 'CHANNEL_LAYER_PREFIX deve ser explícito'),
        )
        for values, message in cases:
            with self.subTest(values=values):
                result = self.run_settings(
                    'config.settings.production',
                    values={**PRODUCTION_ENV, **values},
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(message, result.stderr)

        marker = 'credential-must-not-appear'
        result = self.run_settings(
            'config.settings.production',
            values={
                **PRODUCTION_ENV,
                'REDIS_URL': f'https://user:{marker}@redis.example.test/0',
            },
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('REDIS_URL possui formato inválido.', result.stderr)
        self.assertNotIn(marker, result.stdout + result.stderr)

    def test_valid_production_never_uses_memory(self):
        result = self.run_settings(
            'config.settings.production',
            values=PRODUCTION_ENV,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), 'channels_redis.core.RedisChannelLayer')
