import os
import subprocess
import sys
import json
from pathlib import Path
from unittest import TestCase


BASE_DIR = Path(__file__).resolve().parent.parent
SETTINGS_SCRIPT = (
    "import importlib, os; "
    "module = importlib.import_module(os.environ['COIN_SETTINGS_UNDER_TEST']); "
    "print(module.CHANNEL_LAYERS['default']['BACKEND'])"
)
ENTRYPOINT_SCRIPT = (
    "import importlib, os; "
    "module = importlib.import_module(os.environ['COIN_ENTRYPOINT_UNDER_TEST']); "
    "print(type(module.application).__name__, flush=True); "
    "os._exit(0)"
)
PRODUCTION_SECURITY_SCRIPT = (
    "import json, os; "
    "from config.settings import production as settings; "
    "print(json.dumps({"
    "'debug': settings.DEBUG, "
    "'openapi': settings.OPENAPI_ENABLED, "
    "'ssl_redirect': settings.SECURE_SSL_REDIRECT, "
    "'hsts': settings.SECURE_HSTS_SECONDS, "
    "'hsts_subdomains': settings.SECURE_HSTS_INCLUDE_SUBDOMAINS, "
    "'hsts_preload': settings.SECURE_HSTS_PRELOAD, "
    "'proxy_header': getattr(settings, 'SECURE_PROXY_SSL_HEADER', None), "
    "'csrf_origins': settings.CSRF_TRUSTED_ORIGINS, "
    "'connect_timeout': settings.DATABASES['default']['OPTIONS']['connect_timeout'], "
    "'conn_health_checks': settings.DATABASES['default']['CONN_HEALTH_CHECKS'], "
    "'static_url': settings.STATIC_URL"
    "}))"
)
PRODUCTION_URLS_SCRIPT = (
    "import django; django.setup(); "
    "from django.urls import get_resolver; "
    "names = {pattern.name for pattern in get_resolver().url_patterns "
    "if getattr(pattern, 'name', None)}; "
    "print(','.join(sorted(names)))"
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

    def test_entrypoints_fail_closed_without_explicit_settings(self):
        for module in ('config.asgi', 'config.wsgi'):
            with self.subTest(module=module):
                result = subprocess.run(
                    [sys.executable, '-c', ENTRYPOINT_SCRIPT],
                    cwd=BASE_DIR,
                    env={
                        key: value for key, value in os.environ.items()
                        if key != 'DJANGO_SETTINGS_MODULE'
                    } | {'COIN_ENTRYPOINT_UNDER_TEST': module},
                    capture_output=True,
                    text=True,
                    timeout=60,
                    check=False,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('DJANGO_SETTINGS_MODULE deve ser definido explicitamente', result.stderr)
                self.assertNotIn('config.settings.local', result.stdout + result.stderr)
                self.assertNotIn('config.settings.base', result.stdout + result.stderr)

    def test_entrypoints_start_with_explicit_test_settings_without_external_connections(self):
        for module in ('config.asgi', 'config.wsgi'):
            with self.subTest(module=module):
                result = subprocess.run(
                    [sys.executable, '-c', ENTRYPOINT_SCRIPT],
                    cwd=BASE_DIR,
                    env={
                        **os.environ,
                        'COIN_ENTRYPOINT_UNDER_TEST': module,
                        'DJANGO_SETTINGS_MODULE': 'config.settings.test',
                        'SECRET_KEY': 'entrypoint-test-key',
                        'DATABASE_URL': 'postgresql://test:test@127.0.0.1:1/never-connected',
                    },
                    capture_output=True,
                    text=True,
                    timeout=60,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_production_security_defaults_are_explicit_and_conservative(self):
        result = subprocess.run(
            [sys.executable, '-c', PRODUCTION_SECURITY_SCRIPT],
            cwd=BASE_DIR,
            env={**os.environ, **PRODUCTION_ENV},
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        values = json.loads(result.stdout)
        self.assertEqual(
            values,
            {
                'debug': False,
                'openapi': False,
                'ssl_redirect': False,
                'hsts': 0,
                'hsts_subdomains': False,
                'hsts_preload': False,
                'proxy_header': None,
                'csrf_origins': [],
                'connect_timeout': 5,
                'conn_health_checks': True,
                'static_url': '/static/',
            },
        )

    def test_production_security_can_be_enabled_only_explicitly(self):
        result = subprocess.run(
            [sys.executable, '-c', PRODUCTION_SECURITY_SCRIPT],
            cwd=BASE_DIR,
            env={
                **os.environ,
                **PRODUCTION_ENV,
                'SECURE_SSL_REDIRECT': 'True',
                'SECURE_HSTS_SECONDS': '300',
                'SECURE_HSTS_INCLUDE_SUBDOMAINS': 'True',
                'TRUST_X_FORWARDED_PROTO': 'True',
                'CSRF_TRUSTED_ORIGINS': 'https://app.example.test',
                'DATABASE_CONNECT_TIMEOUT': '7',
            },
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        values = json.loads(result.stdout)
        self.assertTrue(values['ssl_redirect'])
        self.assertEqual(values['hsts'], 300)
        self.assertTrue(values['hsts_subdomains'])
        self.assertFalse(values['hsts_preload'])
        self.assertEqual(values['proxy_header'], ['HTTP_X_FORWARDED_PROTO', 'https'])
        self.assertEqual(values['csrf_origins'], ['https://app.example.test'])
        self.assertEqual(values['connect_timeout'], 7)

    def test_production_rejects_unsafe_http_security_combinations(self):
        cases = (
            ({'SECURE_HSTS_SECONDS': '-1'}, 'SECURE_HSTS_SECONDS não pode ser negativo'),
            ({'SECURE_HSTS_PRELOAD': 'True'}, 'HSTS preload exige HSTS ativo'),
            ({'CSRF_TRUSTED_ORIGINS': 'http://app.example.test'}, 'CSRF_TRUSTED_ORIGINS'),
            ({'DATABASE_CONNECT_TIMEOUT': '0'}, 'DATABASE_CONNECT_TIMEOUT'),
        )
        for values, message in cases:
            with self.subTest(values=values):
                result = self.run_settings(
                    'config.settings.production', values={**PRODUCTION_ENV, **values}
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(message, result.stderr)

    def test_openapi_is_disabled_by_default_and_requires_explicit_opt_in(self):
        for enabled, expected in (('False', False), ('True', True)):
            with self.subTest(enabled=enabled):
                result = subprocess.run(
                    [sys.executable, '-c', PRODUCTION_URLS_SCRIPT],
                    cwd=BASE_DIR,
                    env={
                        **os.environ,
                        **PRODUCTION_ENV,
                        'DJANGO_SETTINGS_MODULE': 'config.settings.production',
                        'OPENAPI_ENABLED': enabled,
                    },
                    capture_output=True,
                    text=True,
                    timeout=60,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                names = set(result.stdout.strip().split(','))
                self.assertEqual('schema' in names, expected)
                self.assertEqual('swagger-ui' in names, expected)
                self.assertEqual('redoc' in names, expected)
