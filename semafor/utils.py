import redis
import threading

from datetime import timedelta

from django.conf import settings
from django.template.loader import render_to_string
from django.utils.translation import gettext_lazy as _

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from semafor.models import (
    Project,
    Worker,
    WorkerMonthDedication,
    WorkForecast,
    WorkAssessment,
)

r = redis.Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    decode_responses=True,
)


def months_range(date_start, date_end):
    ym_start = 12 * date_start.year + date_start.month - 1
    ym_end = 12 * date_end.year + date_end.month
    for ym in range(ym_start, ym_end):
        y, m = divmod(ym, 12)
        yield y, m + 1


def dedication_intensity(dedication, total_dedication):
    if not dedication:
        return ""
    if not total_dedication:
        return "dedication-error"

    intensity = dedication / total_dedication
    if intensity <= 0.20:
        return "dedication-green"
    elif intensity <= 0.40:
        return "dedication-blue"
    elif intensity <= 0.60:
        return "dedication-yellow"
    elif intensity <= 0.80:
        return "dedication-orange"
    elif intensity <= 1:
        return "dedication-red"
    return "dedication-black"


def link_active(request, urlpath, exact=False):
    if exact:
        return request.path == urlpath
    return str(request.path).startswith(urlpath)


def yes_no(b):
    if b:
        return _("Sí")
    return _("No")


def parse_int_safe(x):
    try:
        return int(x)
    except:
        return 0


def format_duration(d):
    if not d:
        return ""
    seconds = int(d.total_seconds())
    hours = seconds // 3600
    minutes = (seconds // 60) % 60
    seconds = seconds % 60
    return f"{hours}:{minutes:02}:{seconds:02}"


def format_currency(f):
    if f is None:
        return ""
    return "{:.2f}".format(f).replace(".", ",")


# Add context utils


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
    projects = Project.objects.filter(archived=False, confirmed=True).prefetch_related(
        "workassessment_set__worker"
    )
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


# Websocket updates utils


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
