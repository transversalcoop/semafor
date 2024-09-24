from django.urls import reverse
from django.shortcuts import redirect, render
from django.views.generic import DetailView, ListView, CreateView, UpdateView
from django.template.loader import render_to_string
from django.contrib.auth.mixins import UserPassesTestMixin

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from semafor.models import Project, Worker, WorkerMonthDedication, ProjectWorkAssignment
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

    if worker:
        project_assignments = {}
        for p in projects:
            project_assignments[p.uuid] = {}
            for pa in ProjectWorkAssignment.objects.filter(project=p, worker=worker):
                k = (pa.year, pa.month)
                project_assignments[p.uuid][k] = pa

        context["project_assignments"] = project_assignments

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
            worker=self.get_object(),
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


class ProjectWorkAssignmentView(StaffRequiredMixin, DetailView):
    model = ProjectWorkAssignment
    template_name = "fragments/assignment.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return add_total_dedication_context(context, self.object)


class CreateProjectWorkAssignmentView(StaffRequiredMixin, CreateView):
    model = ProjectWorkAssignment
    fields = ["worker", "project", "year", "month"]

    def get_success_url(self):
        return reverse("update_project_assignment", args=[self.object.id])


class UpdateProjectWorkAssignmentView(StaffRequiredMixin, UpdateView):
    model = ProjectWorkAssignment
    fields = ["assignment"]
    template_name = "fragments/update_assignment.html"

    def post(self, *args, **kwargs):
        response = super().post(*args, **kwargs)
        assignment = self.object
        try:
            month_dedication = WorkerMonthDedication.objects.get(
                worker=assignment.worker,
                year=assignment.year,
                month=assignment.month,
            )
            total_dedication = month_dedication.dedication
        except WorkerMonthDedication.DoesNotExist:
            total_dedication = 0

        worker_project_td = render_to_string(
            "fragments/assignment.html",
            {"object": assignment, "total_dedication": total_dedication},
        )

        total_worked = 0
        for a in ProjectWorkAssignment.objects.filter(
            worker=assignment.worker, year=assignment.year, month=assignment.month
        ):
            total_worked += a.assignment
        worker_total_td = render_to_string(
            "fragments/assignment_total.html",
            {
                "worker": assignment.worker,
                "year": assignment.year,
                "month": assignment.month,
                "total_worked": total_worked,
                "total_dedication": total_dedication,
            },
        )
        # TODO check there are the proper quantity of sends done
        print("WORKER PROJECT:", worker_project_td)
        print("WORKER TOTAL:", worker_total_td)
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"assignments_worker_{self.object.worker.uuid}",
            {
                "type": "assignment",
                "worker_project": worker_project_td,
                "worker_total": worker_total_td,
            },
        )
        # TODO send also project update for global
        # TODO send also total update for global
        # async_to_sync(channel_layer.group_send)(
        #    f"assignments_total",
        #    {"type": "assignment_total", "project": project_td, "total": total_td},
        # )
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return add_total_dedication_context(context, self.object)
