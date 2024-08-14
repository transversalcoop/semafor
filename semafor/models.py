import uuid

from django.db import models
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
    income = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

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

class ProjectWorkAssignment(models.Model):
    worker = models.ForeignKey(Worker, on_delete=models.CASCADE)
    project = models.ForeignKey(Project, on_delete=models.PROTECT)
    year = models.IntegerField()
    month = models.IntegerField()
    assignment = models.DecimalField(max_digits=3, decimal_places=2)
