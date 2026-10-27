import logging
from datetime import datetime, timezone
from uuid import uuid4

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from .models.vehicle import FleetUnit


logger = logging.getLogger(__name__)


def build_dispatch_event(mission, point):
    return {
        'event_id': str(uuid4()),
        'schema_version': 1,
        'occurred_at': datetime.now(timezone.utc).isoformat(),
        'action': 'DISPATCH',
        'unit_id': mission.assigned_unit_id,
        'unit_name': mission.assigned_unit.name,
        'new_status': FleetUnit.UnitStatus.BUSY,
        'mission_id': mission.id,
        'lat': point.y,
        'lon': point.x,
    }


def publish_fleet_event(event):
    try:
        async_to_sync(get_channel_layer().group_send)(
            'fleet_updates', {'type': 'send_fleet_update', 'message': event}
        )
    except Exception:
        # Channel exceptions can contain payloads or credentials: do not log them.
        logger.error('Falha ao publicar atualização de frota após o commit.')
