import uuid

from django.db import models
from django.urls import reverse
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.auth.models import AbstractUser

MAX_LENGTH = 1000


class User(AbstractUser):
    pass


class Project(models.Model):
    uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        primary_key=True,
    )
    name = models.CharField(max_length=MAX_LENGTH)
    date_start = models.DateField()
    date_end = models.DateField()
    archived = models.BooleanField(default=False)
    confirmed = models.BooleanField(default=False)
    income = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def work_assignments(self, worker=None):
        m = {}
        if worker:
            assignments = self.projectworkassignment_set.filter(worker=worker)
        else:
            assignments = self.projectworkassignment_set.all()
        for wa in assignments:
            m.setdefault((wa.year, wa.month), []).append(wa)

        totals, explanations = {}, {}
        for k, was in m.items():
            totals[k] = sum([x.assignment for x in was])
            explanations[k] = ", ".join(
                [f"{x.worker.name} ({x.assignment})" for x in was]
            )

        return totals, explanations

    def starts(self, year, month):
        return self.starts_pair() == (year, month)

    def starts_pair(self):
        return (self.date_start.year, self.date_start.month)

    def ends(self, year, month):
        return self.ends_pair() == (year, month)

    def ends_pair(self):
        return (self.date_end.year, self.date_end.month)


class Worker(models.Model):
    uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        primary_key=True,
    )
    name = models.CharField(max_length=MAX_LENGTH)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


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
            raise Exception("Com a mínim pot haver una dedicació d'un 0% de jornada")
        if self.dedication > 100:
            raise Exception("Com a màxim pot haver una dedicació d'un 100% de jornada")
        return super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("worker_dedication", args=[self.id])


class ProjectWorkAssignment(models.Model):
    worker = models.ForeignKey(Worker, on_delete=models.CASCADE)
    project = models.ForeignKey(Project, on_delete=models.PROTECT)
    year = models.IntegerField()
    month = models.IntegerField()
    assignment = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )

    class Meta:
        unique_together = ["worker", "project", "year", "month"]

    def __str__(self):
        return f"{self.worker} - {self.project}: {self.year}-{self.month} {self.assignment}"

    def save(self, *args, **kwargs):
        if (self.year, self.month) < self.project.starts_pair():
            raise Exception("No es pot assignar feina abans del principi del projecte")
        if (self.year, self.month) > self.project.ends_pair():
            raise Exception("No es pot assignar feina després del final del projecte")
        if self.assignment < 0:
            raise Exception("Com a mínim cal assignar un 0% de jornada")
        if self.assignment > 100:
            raise Exception("Com a màxim es pot assignar un 100% de jornada")
        return super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("project_assignment", args=[self.id])
