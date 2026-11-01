import os
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.production')

import django
from django.core.checks import run_checks


django.setup()

allowed_ids = {'security.W004', 'security.W008'}
allowed_message_prefixes = {
    'drf_spectacular.W001': (
        'Warning: encountered multiple names for the same choice set (UnitTypeEnum).',
        'Warning: enum naming encountered a non-optimally resolvable collision for fields named "status".',
    ),
}


def is_allowed(message):
    if message.id in allowed_ids:
        return True
    return any(
        message.msg.startswith(prefix)
        for prefix in allowed_message_prefixes.get(message.id, ())
    )


messages = run_checks(include_deployment_checks=True)
unexpected = [message for message in messages if not is_allowed(message)]

for message in messages:
    print(f'{message.id}: {message.msg}')

if unexpected:
    print('Verificações de deploy inesperadas encontradas.', file=sys.stderr)
    raise SystemExit(1)

print('Avisos limitados à política TLS/HSTS e aos dois conflitos de enum OpenAPI conhecidos.')
