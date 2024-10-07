from channels.generic.websocket import AsyncWebsocketConsumer


# TODO count how many consumers in each group using redis, and don't try to send to a group
# unless there are consumers in that group
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

        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.subscription_group_name, self.channel_name
        )

    async def receive(self, text_data):
        pass

    async def forecast_update(self, event):
        await self.send(event["content"])
