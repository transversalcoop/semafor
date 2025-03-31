import redis

from django.conf import settings
from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

r = redis.Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    decode_responses=True,
)
r.flushall()


class ForecastConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.worker_id = self.scope["url_route"]["kwargs"].get("worker_id")
        self.project_id = self.scope["url_route"]["kwargs"].get("project_id")

        if self.worker_id:
            self.subscription_group_name = f"forecast_worker_{self.worker_id}"
        elif self.project_id:
            self.subscription_group_name = f"forecast_project_{self.project_id}"
        else:
            self.subscription_group_name = "forecast_all"

        await self.channel_layer.group_add(
            self.subscription_group_name, self.channel_name
        )

        await sync_to_async(r.incr)(self.subscription_group_name)
        await self.accept()

    async def disconnect(self, close_code):
        await sync_to_async(r.decr)(self.subscription_group_name)
        await self.channel_layer.group_discard(
            self.subscription_group_name, self.channel_name
        )

    async def receive(self, text_data):
        pass

    async def forecast_update(self, event):
        await self.send(event["content"])
