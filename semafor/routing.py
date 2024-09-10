from django.urls import re_path

from . import consumers

websocket_urlpatterns = [
    re_path(r"ws/worker/(?P<worker_id>.+)/$", consumers.AssignmentsConsumer.as_asgi()),
]
