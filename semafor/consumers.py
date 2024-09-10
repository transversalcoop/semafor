from channels.generic.websocket import AsyncWebsocketConsumer

from semafor.models import ProjectWorkAssignment


class AssignmentsConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.worker_id = self.scope["url_route"]["kwargs"].get("worker_id")
        if self.worker_id:
            self.subscription_group_name = f"assignments_worker_{self.worker_id}"
        else:
            self.subscription_group_name = "assignments_total"

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

    async def assignment(self, event):
        assignment = await ProjectWorkAssignment.objects.aget(id=event["assignment_id"])
        await self.send(
            text_data=f'<div id="worker-{self.worker_id}-2024-8">new assignment!</div>'
        )