import io
import redis
import base64
import threading

import matplotlib
import pandas as pd

matplotlib.use("AGG")

import matplotlib.pyplot as plt

from datetime import date, datetime, timedelta

from django.urls import reverse
from django.conf import settings
from django.utils import timezone
from django.views.generic import UpdateView
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
    months_range,
)

r = redis.Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    decode_responses=True,
)


def previous_month(t):
    d = date(t.year, t.month, 1)
    d -= timedelta(3)
    return d


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
    except (ValueError, TypeError):
        return 0


def format_month(ym):
    return f"{ym[1]:02}/{ym[0]}"


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
    return "{:.2f}€".format(f).replace(".", ",")


# Add context utils


def add_time_span(context, projects, min_start=None):
    dates_start = [x.date_start for x in projects]
    dates_end = [x.date_end for x in projects]
    if len(dates_start) > 0:
        date_start = min(dates_start)
        date_end = max(dates_end)
        if min_start and min_start > date_start:
            date_start = min_start

        if date_end < date_start:
            date_end = date_start
        context["time_span"] = list(months_range(date_start, date_end))

    return context


def add_projects_forecast_context(context, worker=None):
    projects = Project.objects.filter(archived=False).prefetch_related(
        "workforecast_set__worker"
    )
    context["projects"] = projects
    context["workers"] = Worker.objects.all()
    now = datetime.now()
    add_time_span(context, projects, min_start=date(now.year, now.month, 1))

    context = add_worked_forecast(context, projects, worker=worker)

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

    return add_dedications(context, worker=worker)


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

    return context | {
        "confirmed_worked_forecast": confirmed_worked,
        "total_worked_forecast": total_worked,
    }


def add_projects_assessment_context(context):
    projects = Project.objects.filter(archived=False, confirmed=True).prefetch_related(
        "workassessment_set"
    )
    projects = sorted(projects, key=lambda p: -p.amount_span())
    context["projects"] = projects
    context["workers"] = Worker.objects.all()
    return context


def add_worker_projects_assessment_context(context, worker):
    projects = Project.objects.filter(archived=False, confirmed=True).prefetch_related(
        "workassessment_set__worker"
    )
    context["workers"] = Worker.objects.all()
    context["projects"] = projects
    context = add_time_span(context, projects)
    context = add_worked_assessment(context, projects, worker=worker)

    workassessments = WorkAssessment.objects.all().prefetch_related("project", "worker")
    project_assessments = {}
    for p in projects:
        project_assessments[p.uuid] = {}
        for pa in (x for x in workassessments if x.project == p and x.worker == worker):
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

    return context | {"total_worked_assessment": total_worked}


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

    return context | {
        "total_dedication": total_dedication,
        "worker_dedications": worker_dedications,
    }


def add_workers_forecast_context(project):
    context = {"object": project}
    context["time_span"] = list(months_range(project.date_start, project.date_end))
    context["workers"] = Worker.objects.all()
    context = add_worked_forecast(context, [project])
    return add_dedications(context)


def add_workers_assessment_context(project):
    now = timezone.now()
    assessed_time_span = list(months_range(project.date_start, previous_month(now)))
    forecasted_time_span = list(months_range(now, project.date_end))
    time_span = assessed_time_span + forecasted_time_span
    workers = Worker.objects.all().prefetch_related("workassessment_set__project")

    context = add_worked_assessment({}, [project])
    context = add_worked_forecast(context, [project])
    context = add_dedications(context)
    return context | {
        "object": project,
        "assessed_time_span": assessed_time_span,
        "forecasted_time_span": forecasted_time_span,
        "time_span": time_span,
        "workers": workers,
    }


def add_economic_balance_context(context, project):
    months, balance_map, income, expenses, work_expenses, other_expenses = (
        project.economic_balance()
    )
    context["economic_balance"] = balance_map
    context["income"] = income
    context["other_expenses"] = other_expenses
    context["work_expenses"] = work_expenses
    income_list = [float(income.get(ym, 0)) for ym in months]
    expenses_list = [-float(expenses.get(ym, 0)) for ym in months]
    balance_list = [float(balance_map.get(ym, 0)) for ym in months]

    income_col = str(_("Ingressos"))
    expenses_col = str(_("Despeses"))
    balance_col = str(_("Balanç"))
    df = pd.DataFrame(
        zip(income_list, expenses_list, balance_list),
        index=[format_month(ym) for ym in months],
        columns=[income_col, expenses_col, balance_col],
    )
    context["balance_df"] = df
    ax = df[[balance_col]].plot(color="black")
    ax = df[[income_col]].plot(kind="bar", ax=ax, color="tab:green")
    df[[expenses_col]].plot(kind="bar", ax=ax, color="tab:red", rot=30)
    plt.tight_layout()
    b = io.BytesIO()
    plt.savefig(b, format="png")
    b.seek(0)
    plot = base64.b64encode(b.read()).decode("utf-8")
    plt.close()
    context["balance_plot"] = plot
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
                "forecast_all",
                {"type": "forecast_update", "content": content},
            )

    # TODO do it with something cheaper than a thread? async?
    threading.Thread(target=f, args=[worker, project]).start()


class UpdateSingleFieldView(UpdateView):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["field"] = self.fields[0]
        context["post_url"] = reverse(self.url_name, kwargs=self.kwargs)
        context["edit"] = self.request.GET.get("edit", "") != "False"
        return context

    def get_success_url(self):
        return reverse(f"{self.url_name}", kwargs=self.kwargs) + "?edit=False"
