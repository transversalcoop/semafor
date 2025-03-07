import copy
import decimal
import tempfile
import datetime


from django.urls import reverse
from django.http import HttpResponse
from django.db.utils import IntegrityError
from django.shortcuts import redirect, render, get_object_or_404
from django.views.generic import (
    TemplateView,
    DetailView,
    ListView,
    CreateView,
    UpdateView,
)
from django.contrib.auth.mixins import UserPassesTestMixin


from semafor.models import (
    Project,
    ProjectAlias,
    Worker,
    WorkerMonthDedication,
    WorkForecast,
    Transaction,
    ExpectedTransaction,
    months_range,
)

from semafor.utils import UpdateSingleFieldView
from semafor.utils import (
    add_projects_forecast_context,
    add_projects_assessment_context,
    add_workers_forecast_context,
    add_workers_assessment_context,
    add_economic_balance_context,
    add_total_dedication_context,
    update_forecast_pages,
)

from semafor.time_control import update_worker_assessments
from semafor.banking import RuralVia


# Permission mixins


# TODO ORG should be changed to UserOwnsOrganizationMixin or similar when organizations are introduced
class StaffRequiredMixin(UserPassesTestMixin):
    login_url = "/admin/login/"

    def test_func(self):
        return self.request.user.is_staff


class IgnoreResponseMixin:
    def get_success_url(self):
        return reverse("ignore")


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


class UpdateProjectDateStartView(StaffRequiredMixin, UpdateSingleFieldView):
    model = Project
    fields = ["date_start"]
    url_name = "update_project_date_start"


class UpdateProjectDateEndView(StaffRequiredMixin, UpdateSingleFieldView):
    model = Project
    fields = ["date_end"]
    url_name = "update_project_date_end"


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

    def get_queryset(self):
        return super().get_queryset().prefetch_related("workassessment_set")

    def get_context_data(self, **kwargs):
        context = add_workers_assessment_context(self.get_object())
        return add_economic_balance_context(context, self.get_object())


class LiquidityView(StaffRequiredMixin, ListView):
    model = Transaction
    template_name = "semafor/liquidity.html"

    def get_queryset(self):
        return super().get_queryset().prefetch_related("projects", "workers")


class ExpectedLiquidityView(StaffRequiredMixin, ListView):
    model = ExpectedTransaction
    template_name = "semafor/expected_liquidity.html"

    def get_queryset(self):
        until = datetime.date(2025, 12, 1)
        lst = list(super().get_queryset())
        repeated = []
        for x in lst:
            if x.repeat == "MONTHLY":
                start = datetime.date(x.year, x.month, 1)
                for month in months_range(start, until):
                    repetition = copy.deepcopy(x)
                    repetition.year, repetition.month = month
                    repeated.append(repetition)

        balance = decimal.Decimal(0)
        lst += repeated
        for i in range(len(lst)):
            balance += lst[i].amount
            lst[i].balance = balance

        return lst


class UploadLiquidityView(StaffRequiredMixin, TemplateView):
    template_name = "fragments/upload_liquidity.html"

    def post(self, request, *args, **kwargs):
        try:
            with tempfile.NamedTemporaryFile(delete_on_close=False) as fp:
                fp.write(request.FILES["transactions_file"].read())
                fp.close()

                for t in RuralVia(fp.name).get_transactions():
                    try:
                        t.save()
                    except IntegrityError:
                        Transaction.objects.get(id=t.id).update(
                            date=t.date,
                            concept=t.concept,
                            amount=t.amount,
                            balance=t.balance,
                        )

            return render(request, self.template_name, {"ok": True})
        except Exception as ex:
            print("EXCEPTION:", ex)

        return super().get(request)


class UpdateWorkerAssessmentsView(StaffRequiredMixin, TemplateView):
    template_name = "fragments/update_worker_assessment.html"

    def setup(self, request, *args, **kwargs):
        self.worker = get_object_or_404(Worker, pk=kwargs["pk"])
        super().setup(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["object"] = self.worker
        return context

    def post(self, request, *args, **kwargs):
        try:
            with tempfile.NamedTemporaryFile(delete_on_close=False) as fp:
                fp.write(request.FILES["checks_file"].read())
                fp.close()

                missing_projects, errors = update_worker_assessments(
                    self.worker, fp.name
                )
                if len(missing_projects) > 0 or len(errors) > 0:
                    self.extra_context = {
                        "projects": Project.objects.all(),
                        "missing_projects": missing_projects,
                        "errors": errors,
                    }
                    return super().get(request)

            self.extra_context = {"ok": True}
            return super().get(request)
        except Exception:
            self.extra_context = {"error": True}
            return super().get(request)


class UpdateTransactionProjectsView(StaffRequiredMixin, TemplateView):
    template_name = "fragments/update_transaction_projects.html"

    def setup(self, request, pk, *args, **kwargs):
        self.transaction = get_object_or_404(Transaction, pk=pk)
        super().setup(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["transaction"] = self.transaction
        return context

    def get(self, request, *args, **kwargs):
        self.extra_context = {"projects": Project.objects.all()}
        return super().get(request)

    def post(self, request, *args, **kwargs):
        project_id = request.POST.get("project")
        try:
            project = Project.objects.get(pk=project_id)
            self.transaction.projects.add(project)
        except Exception:
            pass
        return super().get(request)

    def delete(self, request, *args, **kwargs):
        self.transaction.projects.clear()
        return super().get(request)


# TODO REFACTOR with UpdateTransactionProjectsView, almost identical; same for its templates
class UpdateTransactionWorkersView(StaffRequiredMixin, TemplateView):
    template_name = "fragments/update_transaction_workers.html"

    def setup(self, request, pk, *args, **kwargs):
        self.transaction = get_object_or_404(Transaction, pk=pk)
        super().setup(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["transaction"] = self.transaction
        return context

    def get(self, request, *args, **kwargs):
        self.extra_context = {"workers": Worker.objects.all()}
        return super().get(request)

    def post(self, request, *args, **kwargs):
        worker_id = request.POST.get("worker")
        try:
            worker = Worker.objects.get(pk=worker_id)
            self.transaction.workers.add(worker)
        except Exception:
            pass
        return super().get(request)

    def delete(self, request, *args, **kwargs):
        self.transaction.workers.clear()
        return super().get(request)


class CreateProjectAlias(StaffRequiredMixin, CreateView):
    model = ProjectAlias
    fields = ["project", "alias"]

    def get_success_url(self):
        return reverse("create_project_alias")
