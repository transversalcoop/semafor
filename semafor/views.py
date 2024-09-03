from django.shortcuts import redirect, render
from django.views.generic import DetailView, ListView, CreateView, UpdateView
from django.contrib.auth.mixins import UserPassesTestMixin

from semafor.models import Project, Worker, WorkerMonthDedication
from semafor.utils import months_range

# Helpers

class StaffRequiredMixin(UserPassesTestMixin):
    login_url = "/admin/login/"

    def test_func(self):
        return self.request.user.is_staff

def add_projects_context(context, projects, worker=None):
    context["projects"] = projects
    context["workers"] = Worker.objects.all()
    dates_start = [x.date_start for x in projects]
    dates_end = [x.date_end for x in projects]
    if len(dates_start) > 0:
        date_start = min(dates_start)
        date_end = max(dates_end)
        context["time_span"] = list(months_range(date_start, date_end))

    total_worked = {}
    for p in projects:
        totals, _ = p.work_assignments(worker=worker)
        for k, v in totals.items():
            total_worked.setdefault(k, 0)
            total_worked[k] += v
    context["total_worked"] = total_worked

    total_dedication = {}
    worker_dedications = {}
    if worker:
        dedications = WorkerMonthDedication.objects.filter(worker=worker)
    else:
        dedications = WorkerMonthDedication.objects.all()
    for wd in dedications:
        k = (wd.year, wd.month)
        total_dedication.setdefault(k, 0)
        total_dedication[k] += wd.dedication
        worker_dedications[k] = wd
    context["total_dedication"] = total_dedication
    context["worker_dedications"] = worker_dedications

    return context

# Views

def index(request):
    return redirect("forecast")


class ForecastView(StaffRequiredMixin, ListView):
    model = Project

    def get_queryset(self):
        return super().get_queryset().filter(confirmed=True)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return add_projects_context(
            context,
            self.get_queryset(),
        )


class WorkerForecastView(StaffRequiredMixin, DetailView):
    model = Worker

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return add_projects_context(
            context,
            Project.objects.filter(confirmed=True),
            worker=self.get_queryset().first(),
        )


class WorkerDedicationView(StaffRequiredMixin, DetailView):
    model = WorkerMonthDedication
    template_name = "fragments/dedication.html"

class CreateWorkerDedicationView(StaffRequiredMixin, CreateView):
    model = WorkerMonthDedication
    fields = ["worker", "year", "month"]


class UpdateWorkerDedicationView(StaffRequiredMixin, UpdateView):
    model = WorkerMonthDedication
    fields = ["dedication"]
    template_name = "fragments/update_dedication.html"

