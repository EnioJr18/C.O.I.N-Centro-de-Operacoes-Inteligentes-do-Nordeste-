from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    # A rota que o mapa vai acessar: ws://127.0.0.1:8000/ws/fleet/
    re_path(r'ws/fleet/$', consumers.FleetConsumer.as_asgi()),
]