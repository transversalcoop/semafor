from django.views.generic import DetailView, ListView
from django.contrib.auth.mixins import UserPassesTestMixin

from semafor.models import Project

class StaffRequiredMixin(UserPassesTestMixin):
    login_url = '/admin/login/'

    def test_func(self):
        return self.request.user.is_staff

class IndexView(StaffRequiredMixin, ListView):
    model = Project
