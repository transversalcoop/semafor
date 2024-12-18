from django.conf import settings
from django.urls import include, path

import semafor.views as views

urlpatterns = [
    path("", views.index, name="index"),
    path("ignore/", views.ignore, name="ignore"),
    path("forecast/", views.ForecastView.as_view(), name="forecast"),
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
    path("assessment/", views.AssessmentView.as_view(), name="assessment"),
    path(
        "assessment/worker/<uuid:pk>/",
        views.WorkerAssessmentView.as_view(),
        name="worker_assessment",
    ),
    path(
        "assessment/worker/<uuid:pk>/update/",
        views.UpdateWorkerAssessmentsView.as_view(),
        name="update_worker_assessment",
    ),
    path(
        "assessment/project/<uuid:pk>/",
        views.ProjectAssessmentView.as_view(),
        name="project_assessment",
    ),
    path("liquidity", views.LiquidityView.as_view(), name="liquidity"),
    path(
        "liquidity/upload/",
        views.UploadLiquidityView.as_view(),
        name="upload_liquidity",
    ),
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
