from django.urls import path

import semafor.views as views

urlpatterns = [
    path("", views.IndexView.as_view(), name="index"),
]

