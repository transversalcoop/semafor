import uuid
import copy
import decimal

from datetime import timedelta, date

from django.db import models
from django.db.models import Q
from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.models import AbstractUser

MAX_LENGTH = 1000


def months_range(date_start, date_end):
    ym_start = 12 * date_start.year + date_start.month - 1
    ym_end = 12 * date_end.year + date_end.month
    for ym in range(ym_start, ym_end):
        y, m = divmod(ym, 12)
        yield y, m + 1


class User(AbstractUser):
    pass


# TODO make everything organized inside organizations with authorized users; the views should be changed so that
# they can be seen by authorized users, not staff; the urls should be updated to always reference the organization
# from within we are working
#    organizations = models.ManyToManyField(
#        "Organization", related_name="authorized_users"
#    )
#
# class Organization(models.Model):
#    uuid = models.UUIDField(
#        default=uuid.uuid4,
#        editable=False,
#        primary_key=True,
#    )
#    name = models.CharField(max_length=MAX_LENGTH)
#    worker_monthly_cost = models.DecimalField(max_digits=10, decimal_places=2)
# inside Project
#    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
#    unique index [organization, name]


class Project(models.Model):
    uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        primary_key=True,
    )
    name = models.CharField(max_length=MAX_LENGTH, verbose_name=_("Nom"))
    date_start = models.DateField(
        verbose_name=_("Data d'inici"),
        validators=[MinValueValidator(date(2020, 1, 1))],
    )
    date_end = models.DateField(verbose_name=_("Data de finalització"))
    archived = models.BooleanField(
        default=False, verbose_name=_("Arxivat (s'oculta de totes les pàgines)")
    )
    confirmed = models.BooleanField(
        default=False, verbose_name=_("Confirmat (segur que s'executarà)")
    )
    income = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name=_("Ingressos esperats pel total del projecte (en €)"),
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("project_forecast", args=[self.uuid])

    def work_forecasts(self, worker=None):
        m = {}
        if worker:
            forecasts = [x for x in self.workforecast_set.all() if x.worker == worker]
        else:
            forecasts = self.workforecast_set.all()
        for wa in forecasts:
            m.setdefault((wa.year, wa.month), []).append(wa)

        totals, explanations = {}, {}
        for k, was in m.items():
            totals[k] = sum(x.forecast for x in was)
            explanations[k] = ", ".join(
                [f"{x.worker.name} ({x.forecast})" for x in was]
            )

        return totals, explanations

    def work_assessments(self, worker=None):
        m = {}
        if worker:
            assessments = [
                x for x in self.workassessment_set.all() if x.worker == worker
            ]
        else:
            assessments = self.workassessment_set.all()
        for a in assessments:
            m.setdefault((a.year, a.month), []).append(a)

        totals, explanations = {}, {}
        for k, was in m.items():
            totals[k] = sum((x.assessment for x in was), start=timedelta(0))
            explanations[k] = ", ".join(
                [f"{x.worker.name} ({x.assessment})" for x in was]
            )

        return totals, explanations

    def compute_forecasted_work_expenses(self, worker=None):
        return sum(
            v
            for _, v in self.compute_forecasted_work_expenses_by_months(
                worker=worker
            ).items()
        )

    def compute_forecasted_work_expenses_by_months(self, worker=None, min_month=None):
        if worker:
            forecasts = self.workforecast_set.filter(worker=worker)
        else:
            forecasts = self.workforecast_set.all()

        if min_month:
            year, month = min_month
            future_years = Q(year__gt=year)
            future_months = Q(year=year, month__gte=month)
            forecasts = forecasts.filter(future_years | future_months)

        months = list(months_range(self.date_start, self.date_end))
        return {
            (year, month): self.extract_work_expenses_from_forecasts(
                [f for f in forecasts if f.year == year and f.month == month]
            )
            for year, month in months
        }

    def extract_work_expenses_from_forecasts(self, forecasts):
        work = sum(x.forecast for x in forecasts)
        # TODO set this magic value in the Organization configuration; same in
        # compute_assessed_work_expenses
        return round(decimal.Decimal(work / 100 * settings.WORKER_MONTH_EXPENSE), 2)

    def compute_assessed_work_expenses(self, worker=None):
        return sum(
            v
            for _, v in self.compute_assessed_work_expenses_by_months(
                worker=worker
            ).items()
        )

    def compute_assessed_work_expenses_by_months(self, worker=None, max_month=None):
        if worker:
            assessments = self.workassessment_set.filter(worker=worker)
        else:
            assessments = self.workassessment_set.all()

        if max_month:
            year, month = max_month
            previous_years = Q(year__lt=year)
            previous_months = Q(year=year, month__lt=month)
            assessments = assessments.filter(previous_years | previous_months)

        months = list(months_range(self.date_start, self.date_end))
        return {
            (year, month): self.extract_work_expenses_from_assessments(
                [a for a in assessments if a.year == year and a.month == month]
            )
            for year, month in months
        }

    def extract_work_expenses_from_assessments(self, assessments):
        work = sum((x.assessment for x in assessments), start=timedelta(0))
        # TODO set this magic value in the Worker, probably computed from its
        # expenses and some parameter inside the Organization configuration
        hours = work.total_seconds() / 3600
        expense = decimal.Decimal(hours * settings.WORKER_HOURLY_EXPENSE)
        return round(expense, 2)

    def forecast_content_classes(self, worker=None):
        if worker:
            forecasts = (x for x in self.workforecast_set.all() if x.worker == worker)
        else:
            forecasts = self.workforecast_set.all()

        if sum([a.forecast for a in forecasts]) > 0:
            return "full"
        return "empty"

    def assessment_content_classes(self, worker=None):
        if worker:
            assessments = (
                x for x in self.workassessment_set.all() if x.worker == worker
            )
        else:
            assessments = self.workassessment_set.all()

        if sum((a.assessment for a in assessments), start=timedelta(0)) > timedelta(0):
            return "full"
        return "empty"

    def starts(self, year, month):
        return self.starts_pair() == (year, month)

    def starts_pair(self):
        return (self.date_start.year, self.date_start.month)

    def ends(self, year, month):
        return self.ends_pair() == (year, month)

    def ends_pair(self):
        return (self.date_end.year, self.date_end.month)

    def active(self, year, month):
        month, starts, ends = (year, month), self.starts_pair(), self.ends_pair()
        return month >= starts and month <= ends

    def amount_span(self):
        _, _, income, expenses, _, _ = self.economic_balance()
        income = sum(income[k] for k in income)
        expenses = sum(expenses[k] for k in expenses)
        return abs(income) + abs(expenses)

    def balance(self):
        months, balance_map, _, _, _, _ = self.economic_balance()
        balance_list = [balance_map.get(ym, 0) for ym in months]
        try:
            return balance_list[-1]
        except IndexError:
            return 0

    def economic_balance(self):
        balance, balance_map = 0, {}
        income, expenses = {}, {}
        for t in self.transactions.all():
            ym = t.date.year, t.date.month
            if t.amount > 0:
                income.setdefault(ym, decimal.Decimal())
                income[ym] += t.amount
            else:
                expenses.setdefault(ym, decimal.Decimal())
                expenses[ym] -= t.amount

        other_expenses = copy.deepcopy(expenses)
        now = timezone.now()
        present_month = (now.year, now.month)
        work_expenses = self.compute_assessed_work_expenses_by_months(
            max_month=present_month
        )
        forecasted_work_expenses = self.compute_forecasted_work_expenses_by_months(
            min_month=present_month
        )
        for k, v in forecasted_work_expenses.items():
            work_expenses.setdefault(k, decimal.Decimal())
            work_expenses[k] += v

        for k, v in work_expenses.items():
            expenses.setdefault(k, decimal.Decimal())
            expenses[k] += v

        months = list(months_range(self.date_start, self.date_end))
        for ym in months:
            balance += income.get(ym, 0)
            balance -= expenses.get(ym, 0)
            balance_map[ym] = balance

        return months, balance_map, income, expenses, work_expenses, other_expenses


class ProjectAlias(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    alias = models.CharField(max_length=MAX_LENGTH, unique=True)

    def __str__(self):
        return f"{self.alias} (alias de «{self.project.name}»)"


class Worker(models.Model):
    uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        primary_key=True,
    )
    name = models.CharField(max_length=MAX_LENGTH, verbose_name=_("Nom"))

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def forecast_content_classes(self, project=None):
        if project:
            forecasts = (x for x in self.workforecast_set.all() if x.project == project)
        else:
            forecasts = self.workforecast_set.all()

        if sum([a.forecast for a in forecasts]) > 0:
            return "full"
        return "empty"

    def assessment_content_classes(self, project=None):
        if project:
            assessments = (
                x for x in self.workassessment_set.all() if x.project == project
            )
        else:
            assessments = self.workassessment_set.all()

        if sum((a.assessment for a in assessments), start=timedelta(0)) > timedelta(0):
            return "full"
        return "empty"


class WorkerMonthDedication(models.Model):
    worker = models.ForeignKey(Worker, on_delete=models.CASCADE)
    year = models.IntegerField()
    month = models.IntegerField()
    dedication = models.IntegerField(
        default=100,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )

    class Meta:
        unique_together = ["worker", "year", "month"]

    def __str__(self):
        return f"{self.worker}: {self.year}-{self.month} {self.dedication}%"

    def save(self, *args, **kwargs):
        if self.dedication < 0:
            raise Exception(_("Com a mínim pot haver una dedicació d'un 0% de jornada"))
        if self.dedication > 100:
            raise Exception(
                _("Com a màxim pot haver una dedicació d'un 100% de jornada")
            )
        return super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("worker_dedication", args=[self.id])


class WorkForecast(models.Model):
    worker = models.ForeignKey(Worker, on_delete=models.CASCADE)
    project = models.ForeignKey(Project, on_delete=models.PROTECT)
    year = models.IntegerField()
    month = models.IntegerField()
    forecast = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )

    class Meta:
        unique_together = ["worker", "project", "year", "month"]

    def __str__(self):
        return (
            f"{self.worker} - {self.project}: {self.year}-{self.month} {self.forecast}"
        )

    def save(self, *args, **kwargs):
        if (self.year, self.month) < self.project.starts_pair():
            raise Exception(
                _("No es pot assignar feina abans del principi del projecte")
            )
        if (self.year, self.month) > self.project.ends_pair():
            raise Exception(
                _("No es pot assignar feina després del final del projecte")
            )
        if self.forecast < 0:
            raise Exception(_("Com a mínim cal assignar un 0% de jornada"))
        if self.forecast > 100:
            raise Exception(_("Com a màxim es pot assignar un 100% de jornada"))
        return super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("work_forecast", args=[self.id])


class OutOfBoundsException(Exception):
    pass


class WorkAssessment(models.Model):
    worker = models.ForeignKey(Worker, on_delete=models.CASCADE)
    project = models.ForeignKey(Project, on_delete=models.PROTECT)
    year = models.IntegerField()
    month = models.IntegerField()
    assessment = models.DurationField()

    class Meta:
        unique_together = ["worker", "project", "year", "month"]

    def __str__(self):
        return f"{self.worker} - {self.project}: {self.year}-{self.month} {self.assessment}"

    def save(self, *args, **kwargs):
        if (self.year, self.month) < self.project.starts_pair():
            raise OutOfBoundsException(
                _("No es pot assignar feina abans del principi del projecte")
            )
        if (self.year, self.month) > self.project.ends_pair():
            raise OutOfBoundsException(
                _("No es pot assignar feina després del final del projecte")
            )
        return super().save(*args, **kwargs)


class Tag(models.Model):
    uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        primary_key=True,
    )
    name = models.CharField(max_length=MAX_LENGTH)


class Transaction(models.Model):
    id = models.IntegerField(primary_key=True)
    date = models.DateField()
    concept = models.CharField(max_length=MAX_LENGTH)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    balance = models.DecimalField(max_digits=10, decimal_places=2)

    tags = models.ManyToManyField(Tag, related_name="transactions")
    projects = models.ManyToManyField(
        Project,
        related_name="transactions",
        through="TransactionProjectAssignment",
    )
    workers = models.ManyToManyField(
        Worker,
        related_name="transactions",
        through="TransactionWorkerAssignment",
    )

    class Meta:
        ordering = ["id"]


class ExpectedTransaction(models.Model):
    REPEAT_CHOICES = [
        ("NO", _("No")),
        ("MONTHLY", _("Mensual")),
    ]

    uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        primary_key=True,
    )
    concept = models.CharField(max_length=MAX_LENGTH)
    amount = models.DecimalField(max_digits=10, decimal_places=2)

    # starting date to happen
    year = models.IntegerField()
    month = models.IntegerField()

    repeat = models.CharField(max_length=10, choices=REPEAT_CHOICES)

    projects = models.ManyToManyField(
        Project,
        related_name="expected_transactions",
        through="ExpectedTransactionProjectAssignment",
    )
    workers = models.ManyToManyField(
        Worker,
        related_name="expected_transactions",
        through="ExpectedTransactionWorkerAssignment",
    )

    class Meta:
        ordering = ["year", "month", "concept"]

    def __str__(self):
        s = f"({self.amount}€) {self.concept} - {self.year}-{self.month}"
        if self.repeat == "MONTHLY":
            s += " (repetit mensualment)"
        return s


class TransactionProjectAssignment(models.Model):
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)


class TransactionWorkerAssignment(models.Model):
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE)
    worker = models.ForeignKey(Worker, on_delete=models.CASCADE)


class ExpectedTransactionProjectAssignment(models.Model):
    transaction = models.ForeignKey(ExpectedTransaction, on_delete=models.CASCADE)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)


class ExpectedTransactionWorkerAssignment(models.Model):
    transaction = models.ForeignKey(ExpectedTransaction, on_delete=models.CASCADE)
    worker = models.ForeignKey(Worker, on_delete=models.CASCADE)
