from django.urls import path

import semafor.views as views

urlpatterns = [
    path("", views.index, name="index"),
    path("forecast", views.ForecastView.as_view(), name="forecast"),
    path(
        "forecast/worker/<uuid:pk>/",
        views.WorkerForecastView.as_view(),
        name="worker_forecast",
    ),
    path("forecast/project/<uuid:pk>/", views.index, name="project_forecast"),  # TODO
    path("liquidity", views.index, name="liquidity"),  # TODO
    path("assessment", views.index, name="assessment"),  # TODO
    path("assessment/worker/<uuid:pk>/", views.index, name="worker_assessment"),  # TODO
    path(
        "assessment/project/<uuid:pk>/", views.index, name="project_assessment"
    ),  # TODO
    path(
        "worker/dedication/create/",
        views.CreateWorkerDedicationView.as_view(),
        name="create_worker_dedication",
    ),
    path(
        "worker/dedication/<int:pk>/",
        views.WorkerDedicationView.as_view(),
        name="worker_dedication",
    ),
    path(
        "worker/dedication/<int:pk>/update/",
        views.UpdateWorkerDedicationView.as_view(),
        name="update_worker_dedication",
    ),
    path(
        "project/assignment/create/<uuid:project_id>/<uuid:worker_id>/<int:year>/<int:month>/",
        views.CreateWorkAssignmentView.as_view(),
        name="create_project_assignment",
    ),
    path(
        "project/assignment/<int:pk>/",
        views.WorkAssignmentView.as_view(),
        name="project_assignment",
    ),
    path(
        "project/assignment/<int:pk>/update/",
        views.UpdateWorkAssignmentView.as_view(),
        name="update_project_assignment",
    ),
]
