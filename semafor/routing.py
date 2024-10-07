from django.urls import re_path

from . import consumers

websocket_urlpatterns = [
    re_path(r"ws/forecast/total/$", consumers.ForecastConsumer.as_asgi()),
    re_path(
        r"ws/forecast/worker/(?P<worker_id>.+)/$",
        consumers.ForecastConsumer.as_asgi(),
    ),
    re_path(
        r"ws/forecast/project/(?P<project_id>.+)/$",
        consumers.ForecastConsumer.as_asgi(),
    ),
]
