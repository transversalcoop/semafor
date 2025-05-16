from django.contrib import admin

from semafor.models import Project
from semafor.models import ProjectAlias
from semafor.models import Worker
from semafor.models import ExpectedTransaction
from semafor.models import WorkAssessment


class ProjectAdmin(admin.ModelAdmin):
    model = Project
    fields = (
        ("name", "income"),
        ("archived", "confirmed"),
    )


admin.site.register(Project, ProjectAdmin)
admin.site.register(ProjectAlias)
admin.site.register(Worker)
admin.site.register(ExpectedTransaction)
admin.site.register(WorkAssessment)
