from django.contrib import admin

from semafor.models import Project
from semafor.models import Worker
from semafor.models import ExpectedTransaction


class ProjectAdmin(admin.ModelAdmin):
    model = Project
    fields = (
        ("name", "income"),
        ("date_start", "date_end"),
        ("archived", "confirmed"),
    )


admin.site.register(Project, ProjectAdmin)
admin.site.register(Worker)
admin.site.register(ExpectedTransaction)
