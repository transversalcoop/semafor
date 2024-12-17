import redis
import tempfile
import threading

from datetime import timedelta

from django.urls import reverse
from django.http import HttpResponse
from django.conf import settings
from django.shortcuts import redirect, render, get_object_or_404
from django.views.generic import DetailView, ListView, CreateView, UpdateView
from django.template.loader import render_to_string
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.mixins import UserPassesTestMixin

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from semafor.models import (
    Project,
    Worker,
    WorkerMonthDedication,
    WorkForecast,
    WorkAssessment,
    OutOfBoundsException,
)
from semafor.utils import months_range, parse_int_safe
from semafor.time_control import ControlHorari

r = redis.Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    decode_responses=True,
)

# Helpers


class StaffRequiredMixin(UserPassesTestMixin):
    login_url = "/admin/login/"

    def test_func(self):
        return self.request.user.is_staff


class IgnoreResponseMixin:
    def get_success_url(self):
        return reverse("ignore")


def add_time_span(context, projects):
    dates_start = [x.date_start for x in projects]
    dates_end = [x.date_end for x in projects]
    if len(dates_start) > 0:
        date_start = min(dates_start)
        date_end = max(dates_end)
        context["time_span"] = list(months_range(date_start, date_end))


def add_projects_forecast_context(context, worker=None):
    projects = Project.objects.filter(archived=False).prefetch_related(
        "workforecast_set__worker"
    )
    context["projects"] = projects
    context["workers"] = Worker.objects.all()
    add_time_span(context, projects)

    add_worked_forecast(context, projects, worker=worker)

    workforecasts = WorkForecast.objects.all().prefetch_related("project", "worker")
    if worker:
        project_forecasts = {}
        for p in projects:
            project_forecasts[p.uuid] = {}
            for pa in (
                x for x in workforecasts if x.project == p and x.worker == worker
            ):
                k = (pa.year, pa.month)
                project_forecasts[p.uuid][k] = pa

        context["project_forecasts"] = project_forecasts

    add_dedications(context, worker=worker)
    return context


def add_worked_forecast(context, projects, worker=None):
    confirmed_worked, total_worked = {}, {}
    for p in projects:
        totals, _ = p.work_forecasts(worker=worker)
        for k, v in totals.items():
            total_worked.setdefault(k, 0)
            confirmed_worked.setdefault(k, 0)
            total_worked[k] += v
            if p.confirmed:
                confirmed_worked[k] += v
    context["confirmed_worked"] = confirmed_worked
    context["total_worked"] = total_worked


def add_projects_assessment_context(context, worker=None):
    projects = Project.objects.filter(archived=False, confirmed=True)
    context["workers"] = Worker.objects.all()
    context["projects"] = projects
    add_time_span(context, projects)
    add_worked_assessment(context, projects, worker=worker)

    workassessments = WorkAssessment.objects.all().prefetch_related("project", "worker")
    if worker:
        project_assessments = {}
        for p in projects:
            project_assessments[p.uuid] = {}
            for pa in (
                x for x in workassessments if x.project == p and x.worker == worker
            ):
                k = (pa.year, pa.month)
                project_assessments[p.uuid][k] = pa

        context["project_assessments"] = project_assessments

    return context


def add_worked_assessment(context, projects, worker=None):
    total_worked = {}
    for p in projects:
        totals, _ = p.work_assessments(worker=worker)
        for k, v in totals.items():
            total_worked.setdefault(k, timedelta(0))
            total_worked[k] += v
    context["total_worked"] = total_worked


def add_dedications(context, worker=None):
    total_dedication = {}
    worker_dedications = {}
    if worker:
        dedications = WorkerMonthDedication.objects.filter(
            worker=worker
        ).prefetch_related("worker")
    else:
        dedications = WorkerMonthDedication.objects.all().prefetch_related("worker")
    for wd in dedications:
        k = (wd.year, wd.month)
        total_dedication.setdefault(k, 0)
        total_dedication[k] += wd.dedication
        worker_dedications.setdefault(wd.worker.uuid, {})
        worker_dedications[wd.worker.uuid][k] = wd

    context["total_dedication"] = total_dedication
    context["worker_dedications"] = worker_dedications


def add_workers_forecast_context(project):
    context = {"object": project}
    context["time_span"] = list(months_range(project.date_start, project.date_end))
    context["workers"] = Worker.objects.all()
    add_worked_forecast(context, [project])
    add_dedications(context)
    return context


def add_workers_assessment_context(project):
    context = {"object": project}
    context["time_span"] = list(months_range(project.date_start, project.date_end))
    context["workers"] = Worker.objects.all()
    add_worked_assessment(context, [project])
    return context


def add_total_dedication_context(context, obj):
    try:
        wd = WorkerMonthDedication.objects.get(
            worker=obj.worker,
            year=obj.year,
            month=obj.month,
        )
        dedication = wd.dedication
    except WorkerMonthDedication.DoesNotExist:
        dedication = 0
    context["total_dedication"] = dedication
    return context


# Views


def index(request):
    return redirect("forecast")


def ignore(request):
    return HttpResponse("")


class ForecastView(StaffRequiredMixin, ListView):
    model = Project
    template_name = "semafor/forecast_all.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return add_projects_forecast_context(context)


class WorkerForecastView(StaffRequiredMixin, DetailView):
    model = Worker
    template_name = "semafor/worker_forecast.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return add_projects_forecast_context(context, worker=self.get_object())


class ProjectForecastView(StaffRequiredMixin, DetailView):
    model = Project
    template_name = "semafor/project_forecast.html"

    def get_queryset(self):
        return super().get_queryset().prefetch_related("workforecast_set__worker")

    def get_context_data(self, **kwargs):
        return add_workers_forecast_context(self.get_object())


class WorkerDedicationView(StaffRequiredMixin, DetailView):
    model = WorkerMonthDedication
    template_name = "fragments/dedication.html"


class CreateWorkerDedicationView(StaffRequiredMixin, CreateView):
    model = WorkerMonthDedication
    fields = ["worker", "year", "month"]

    def post(self, *args, **kwargs):
        response = super().post(*args, **kwargs)
        update_forecast_pages(worker=self.object.worker)
        return response


class UpdateWorkerDedicationView(StaffRequiredMixin, UpdateView):
    model = WorkerMonthDedication
    fields = ["dedication"]
    template_name = "fragments/update_dedication.html"

    def post(self, *args, **kwargs):
        response = super().post(*args, **kwargs)
        d = self.get_object()
        update_forecast_pages(worker=d.worker)
        return response


class WorkForecastView(StaffRequiredMixin, DetailView):
    model = WorkForecast
    template_name = "fragments/worker_month_forecast.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return add_total_dedication_context(context, self.object)


class CreateWorkForecastView(StaffRequiredMixin, CreateView):
    model = WorkForecast
    fields = ["worker", "project", "year", "month"]

    def get_success_url(self):
        return reverse("update_work_forecast", args=[self.object.id])


class UpdateProjectConfirmedView(StaffRequiredMixin, IgnoreResponseMixin, UpdateView):
    model = Project
    fields = ["confirmed"]

    def post(self, *args, **kwargs):
        response = super().post(*args, **kwargs)
        update_forecast_pages()
        return response


class UpdateWorkForecastView(StaffRequiredMixin, UpdateView):
    model = WorkForecast
    fields = ["forecast"]
    template_name = "fragments/update_forecast.html"

    def post(self, *args, **kwargs):
        response = super().post(*args, **kwargs)
        a = self.get_object()
        update_forecast_pages(worker=a.worker, project=a.project)
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return add_total_dedication_context(context, self.object)


class AssessmentView(StaffRequiredMixin, ListView):
    model = Project
    template_name = "semafor/assessment_all.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return add_projects_assessment_context(context)


class WorkerAssessmentView(StaffRequiredMixin, DetailView):
    model = Worker
    template_name = "semafor/worker_assessment.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return add_projects_assessment_context(context, worker=self.get_object())


class ProjectAssessmentView(StaffRequiredMixin, DetailView):
    model = Project
    template_name = "semafor/project_assessment.html"

    def get_context_data(self, **kwargs):
        return add_workers_assessment_context(self.get_object())


def update_worker_assessment(request, pk):
    worker = get_object_or_404(Worker, pk=pk)
    if request.method == "POST":
        try:
            with tempfile.NamedTemporaryFile(delete_on_close=False) as fp:
                fp.write(request.FILES["checks_file"].read())
                fp.close()

                missing_projects, errors = update_worker_assessments(worker, fp.name)
                if len(missing_projects) > 0 or len(errors) > 0:
                    return render(
                        request,
                        "fragments/update_worker_assessment.html",
                        {
                            "missing_projects": missing_projects,
                            "errors": errors,
                            "object": worker,
                        },
                    )

            return render(
                request,
                "fragments/update_worker_assessment.html",
                {"ok": True, "object": worker},
            )
        except Exception as ex:
            print("EXCEPTION:", ex)
            return render(
                request,
                "fragments/update_worker_assessment.html",
                {"error": True, "object": worker},
            )

    return render(
        request, "fragments/update_worker_assessment.html", {"object": worker}
    )


def update_worker_assessments(worker, dbfile):
    WorkAssessment.objects.filter(worker=worker).delete()
    projects = ControlHorari(dbfile).get_projects_worked_time()
    db_projects, missing_projects = {}, set()
    for k in projects:
        try:
            project = Project.objects.get(name=k)
            db_projects[k] = project
        except Project.DoesNotExist:
            missing_projects.add(k)

    errors = []
    if len(missing_projects) == 0:
        for pname, assessments in projects.items():
            project = db_projects[pname]
            for assessment in assessments:
                year = assessment["year"]
                month = assessment["month"]
                try:
                    WorkAssessment.objects.create(
                        worker=worker,
                        project=project,
                        year=year,
                        month=month,
                        assessment=assessment["worked_time"],
                    )
                except OutOfBoundsException as ex:
                    errors.append(f"{project.name} ({year}-{month:02}): {ex}")

    return missing_projects, errors


# TODO better performance for rendering those templates; django debug toolbar does not know how many
# db requests are made
def update_forecast_pages(worker=None, project=None):
    def f(worker, project):
        channel_layer = get_channel_layer()

        if worker:
            workers = [worker]
        else:
            workers = Worker.objects.all()

        if project:
            projects = [project]
        else:
            projects = Project.objects.all()

        subscription_groups = (
            [f"forecast_worker_{worker.uuid}" for worker in workers]
            + [f"forecast_project_{project.uuid}" for project in projects]
            + ["forecast_all"]
        )
        counts = [parse_int_safe(x) for x in r.mget(subscription_groups)]
        group_counts = dict(zip(subscription_groups, counts))

        for worker in workers:
            group = f"forecast_worker_{worker.uuid}"
            if group_counts[group] > 0:
                content = render_to_string(
                    "fragments/worker_forecast.html",
                    add_projects_forecast_context({"object": worker}, worker=worker),
                )
                async_to_sync(channel_layer.group_send)(
                    group,
                    {"type": "forecast_update", "content": content},
                )

        for project in projects:
            group = f"forecast_project_{project.uuid}"
            if group_counts[group] > 0:
                content = render_to_string(
                    "fragments/project_forecast.html",
                    add_workers_forecast_context(project),
                )
                async_to_sync(channel_layer.group_send)(
                    group,
                    {"type": "forecast_update", "content": content},
                )

        if group_counts["forecast_all"] > 0:
            content = render_to_string(
                "fragments/forecast_all.html",
                add_projects_forecast_context({}),
            )
            async_to_sync(channel_layer.group_send)(
                f"forecast_all",
                {"type": "forecast_update", "content": content},
            )

    # TODO do it with something cheaper than a thread? async?
    threading.Thread(target=f, args=[worker, project]).start()
