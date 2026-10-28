import asyncio
import json
import logging
import time

from channels.generic.websocket import AsyncWebsocketConsumer

from authentication.websocket import PROTOCOL, has_operational_access

logger = logging.getLogger(__name__)


class FleetConsumer(AsyncWebsocketConsumer):
    group_name = 'fleet_updates'

    async def connect(self):
        self.joined = False
        self.closed = False
        self.expiry_task = None
        self.lifecycle_lock = asyncio.Lock()
        identity = self.scope.get('coin_identity')
        if not identity:
            await self.close(code=4401)
            return
        self.user_id, self.expires_at = identity
        if not await has_operational_access(self.user_id):
            await self.close(code=4403)
            return
        if time.time() >= self.expires_at:
            await self.close(code=4401)
            return

        try:
            await self.channel_layer.group_add(self.group_name, self.channel_name)
            self.joined = True
        except Exception:
            logger.error('Falha ao associar conexão ao grupo de frota.')
            try:
                await self.channel_layer.group_discard(self.group_name, self.channel_name)
            except Exception:
                logger.error('Falha ao limpar associação parcial do grupo de frota.')
            self.joined = False
            self.closed = True
            await self.close(code=1011)
            return

        try:
            await self.accept(subprotocol=PROTOCOL)
        except Exception:
            await self._discard_group_safely()
            raise
        self.expiry_task = asyncio.create_task(self._expire())

    async def _expire(self):
        try:
            await asyncio.sleep(max(0, self.expires_at - time.time()))
            async with self.lifecycle_lock:
                await self._close_authorized_connection(4401)
        except Exception:
            logger.error('Falha ao encerrar conexão WebSocket expirada.')

    async def _close_authorized_connection(self, code):
        if self.closed:
            return
        self.closed = True
        task = self.expiry_task
        if task and task is not asyncio.current_task():
            task.cancel()
        await self._discard_group_safely()
        await self.close(code=code)

    async def _discard_group_safely(self):
        if not self.joined:
            return
        try:
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
        except Exception:
            logger.error('Falha ao remover conexão do grupo de frota.')
        finally:
            self.joined = False

    async def disconnect(self, close_code):
        task = self.expiry_task
        if task and task is not asyncio.current_task():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        async with self.lifecycle_lock:
            self.closed = True
            await self._discard_group_safely()

    async def send_fleet_update(self, event):
        async with self.lifecycle_lock:
            if self.closed:
                return
            if time.time() >= self.expires_at:
                await self._close_authorized_connection(4401)
                return
            try:
                authorized = await has_operational_access(self.user_id)
            except Exception:
                logger.error('Falha ao revalidar autorização WebSocket.')
                await self._close_authorized_connection(1011)
                return
            if not authorized:
                await self._close_authorized_connection(4403)
                return
            if time.time() >= self.expires_at:
                await self._close_authorized_connection(4401)
                return
            await self.send(text_data=json.dumps(event['message']))
