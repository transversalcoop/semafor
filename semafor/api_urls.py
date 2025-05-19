from django.urls import path

import semafor.views as views

urlpatterns = [
    path(
        "assessment/worker/<str:token>/update/",
        views.api_update_worker_assessment,
        name="api_update_worker_assessment",
    ),
]
