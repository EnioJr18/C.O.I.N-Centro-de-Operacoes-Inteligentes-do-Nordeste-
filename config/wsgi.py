import os

if not os.environ.get('DJANGO_SETTINGS_MODULE', '').strip():
    raise RuntimeError(
        'DJANGO_SETTINGS_MODULE deve ser definido explicitamente antes de iniciar o WSGI.'
    )

from django.core.wsgi import get_wsgi_application

application = get_wsgi_application()
