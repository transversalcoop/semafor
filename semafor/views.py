from django.views.generic import DetailView, ListView
from django.contrib.auth.mixins import UserPassesTestMixin

from semafor.models import Project, Worker
from semafor.utils import months_range


class StaffRequiredMixin(UserPassesTestMixin):
    login_url = "/admin/login/"

    def test_func(self):
        return self.request.user.is_staff


class IndexView(StaffRequiredMixin, ListView):
    model = Project

    def get_queryset(self):
        return super().get_queryset().filter(confirmed=True)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        dates_start = [x.date_start for x in self.get_queryset()]
        dates_end = [x.date_end for x in self.get_queryset()]
        if len(dates_start) > 0:
            date_start = min(dates_start)
            date_end = max(dates_end)
            context["time_span"] = list(months_range(date_start, date_end))

        context["workers_count"] = Worker.objects.count()
        total_worked = {}
        for p in self.get_queryset():
            totals, _ = p.work_assignments()
            for k, v in totals.items():
                total_worked.setdefault(k, 0)
                total_worked[k] += v
        context["total_worked"] = total_worked
        print(total_worked)
        return context
