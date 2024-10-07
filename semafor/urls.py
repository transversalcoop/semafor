from django.conf import settings
from django.urls import include, path

import semafor.views as views

urlpatterns = [
    path("", views.index, name="index"),
    path("ignore", views.ignore, name="ignore"),
    path("forecast", views.ForecastView.as_view(), name="forecast"),
    path(
        "forecast/worker/<uuid:pk>/",
        views.WorkerForecastView.as_view(),
        name="worker_forecast",
    ),
    path(
        "forecast/project/<uuid:pk>/",
        views.ProjectForecastView.as_view(),
        name="project_forecast",
    ),
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
        "work/forecast/create/",
        views.CreateWorkForecastView.as_view(),
        name="create_work_forecast",
    ),
    path(
        "work/forecast/<int:pk>/",
        views.WorkForecastView.as_view(),
        name="work_forecast",
    ),
    path(
        "work/forecast/<int:pk>/update/",
        views.UpdateWorkForecastView.as_view(),
        name="update_work_forecast",
    ),
    path(
        "project/<uuid:pk>/update-confirmed/",
        views.UpdateProjectConfirmedView.as_view(),
        name="update_project_confirmed",
    ),
]

if settings.DEBUG:
    urlpatterns += [
        path("__debug__/", include("debug_toolbar.urls")),
    ]
