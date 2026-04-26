import json
from channels.generic.websocket import AsyncWebsocketConsumer

class FleetConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.group_name = 'fleet_updates'

        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        
        await self.accept()
        print("🚑 Novo Mapa Conectado ao C.O.I.N.!")

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )
        print("🔌 Mapa Desconectado.")

    async def send_fleet_update(self, event):
        dados = event['message']
        await self.send(text_data=json.dumps(dados))